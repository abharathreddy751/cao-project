"""AD-7 / audit D4: train/serve parity and leakage of decision-time features.

PARITY: on a recorded real run (Coordinator + worker processes) the features the
dataset builder reconstructs from the log equal the features the policy used online.
LEAKAGE: feature values come only from ``task_dispatched`` records, so removing or
altering anything after the decision cannot change them.
"""
import dataclasses
import json

import pytest

from caosched.core.coordinator import Coordinator
from caosched.core.dag import build_independent_dag
from caosched.core.event_log import EventLogger, read_events
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task
from caosched.core.dag import DAG
from caosched.core.worker_pool import WorkerPool
from caosched.dataset.build import CalibrationProfiles, build_dataset
from caosched.dataset.campaign import RandomOccupancyPolicy
from caosched.dataset.events import decision_contexts, rows_from_events
from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator
from caosched.estimators.profile import StaticProfileEstimator, latest_profile_path
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.heft import HeftScheduler


class SpyEstimator(ExecutionTimeEstimator):
    """Context-using estimator that remembers the context each task was fed back with."""
    name = "spy"
    uses_context = True

    def __init__(self):
        self.observed = {}

    def estimate(self, task, pool, ctx=None):
        return 0.01 * (1 + (ctx.busy_total if ctx else 0))

    def observe(self, task, pool, kernel_seconds, ctx=None):
        self.observed[task.task_id] = ctx


@pytest.fixture(scope="module")
def recorded_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("parity")
    spy = SpyEstimator()
    dag = build_independent_dag(10, size=96)
    with WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=False) as pool:
        with EventLogger("parity", output_dir=out) as log:
            summary = Coordinator(dag, pool, EarliestFinishTimeScheduler(spy, "spy"), log).run(run_timeout=60)
    assert summary.status == "completed"
    return read_events(out / "parity.jsonl"), spy


def test_parity_offline_features_equal_online_features(recorded_run):
    events, spy = recorded_run
    rows = rows_from_events(events, "decision")
    assert len(rows) == 10 and all(r["ctx_source"] == "decision" for r in rows)
    for r in rows:
        online = spy.observed[r["task_id"]]
        assert isinstance(online, EstimateContext) and r["ctx"] == online
    # non-trivial: the early-binding run actually produced occupancy and recent-activity features
    assert any(r["ctx"].busy_total > 0 for r in rows) and all(r["ctx"].target_busy_frac is not None for r in rows)


def _recording(policy):
    """Wrap select_worker: remember the context the policy logged (decision) and an independent
    ``EstimateContext.from_state`` of the same state (online)."""
    logged, online = {}, {}
    orig = policy.select_worker

    def select(task, state):
        wid = orig(task, state)
        if wid is not None:
            logged[task.task_id] = EstimateContext.from_dict(policy.last_decision["candidates"][wid]["ctx"])
            online[task.task_id] = EstimateContext.from_state(state, wid)
        return wid
    policy.select_worker = select
    return logged, online


@pytest.mark.parametrize("kind", ["random_occupancy", "heft"])
def test_parity_data_collection_and_plan_policies(tmp_path, kind):
    """RandomOccupancyPolicy (campaign) and HEFT (plan) logs: rows built from the run log equal the online context."""
    if kind == "random_occupancy":
        policy = RandomOccupancyPolicy(seed=3, allowed_workers=["P0", "E0"])
    else:
        policy = HeftScheduler(StaticProfileEstimator({("matmul", 96, "P"): 0.01, ("matmul", 96, "E"): 0.02}), "heft")
    logged, online = _recording(policy)
    with WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=False) as pool:
        with EventLogger(kind, output_dir=tmp_path) as log:
            summary = Coordinator(build_independent_dag(10, size=96), pool, policy, log).run(run_timeout=60)
    assert summary.status == "completed"
    rows = rows_from_events(read_events(tmp_path / f"{kind}.jsonl"), "decision")
    assert len(rows) == 10 and all(r["ctx_source"] == "decision" for r in rows)
    for r in rows:
        assert r["ctx"] == logged[r["task_id"]]                      # log round trip is exact
        a, b = r["ctx"], online[r["task_id"]]                        # occupancy equal; recent-activity frac is read at ~the same instant
        assert dataclasses.replace(a, target_busy_frac=None) == dataclasses.replace(b, target_busy_frac=None)
        assert a.target_busy_frac == pytest.approx(b.target_busy_frac, abs=5e-3)


def test_leakage_features_unchanged_when_post_decision_events_removed(recorded_run):
    events, _ = recorded_run
    full = decision_contexts(events)
    assert len(full) == 10
    for i, e in enumerate(events):
        if e["event"] == "task_dispatched":
            assert decision_contexts(events[: i + 1])[e["task_id"]] == full[e["task_id"]]  # nothing later is needed
    # ...and nothing later can change them: drop every completion / shuffle their times
    tampered = [dict(e, t_started=-1.0, t_completed=-0.5) if e["event"] == "task_completed" else e for e in events]
    assert {r["task_id"]: r["ctx"] for r in rows_from_events(tampered, "decision")} == full
    assert decision_contexts([e for e in events if e["event"] != "task_completed"]) == full


def _early_binding_log(a_completes: float):
    """a runs [0, a_completes) on P0; b is bound to E0 at t=1 (P0 busy, busy_P=1 logged) but starts at 12."""
    ctx_b = {"busy_P": 1, "busy_E": 0, "corunning": {"matmul": 1}, "target_busy_frac": 1.0}
    return [
        {"seq": 0, "t": 0.0, "event": "run_started", "run_id": "r", "scheduler": "s", "metadata": {},
         "tasks": {t: {"workload": "matmul", "size": 8, "seed": i} for i, t in enumerate("ab")}},
        {"seq": 1, "t": 0.1, "event": "task_dispatched", "task_id": "a", "worker_id": "P0", "pool": "P",
         "decision": {"candidates": {"P0": {"ctx": {"busy_P": 0, "busy_E": 0, "corunning": {}, "target_busy_frac": 0.0}}}}},
        {"seq": 2, "t": 1.0, "event": "task_dispatched", "task_id": "b", "worker_id": "E0", "pool": "E",
         "decision": {"candidates": {"E0": {"ctx": ctx_b}}}},
        {"seq": 3, "t": a_completes, "event": "task_completed", "task_id": "a", "worker_id": "P0", "pool": "P",
         "t_started": 0.1, "t_completed": a_completes, "wall_time_seconds": 1.0},
        {"seq": 4, "t": 13.0, "event": "task_completed", "task_id": "b", "worker_id": "E0", "pool": "E",
         "t_started": 12.0, "t_completed": 13.0, "wall_time_seconds": 1.0},
        {"seq": 5, "t": 14.0, "event": "run_finished", "status": "completed"},
    ]


def test_start_time_reconstruction_leaks_but_decision_context_does_not():
    early, late = _early_binding_log(5.0), _early_binding_log(20.0)  # only a's FUTURE completion differs
    dec = lambda ev: {r["task_id"]: r["ctx"] for r in rows_from_events(ev, "decision")}
    assert dec(early) == dec(late) and dec(early)["b"].busy_P == 1
    start = lambda ev: {r["task_id"]: r["ctx"] for r in rows_from_events(ev, "start")}
    assert start(early)["b"].busy_P == 0 and start(late)["b"].busy_P == 1   # legacy features depend on the future
    auto = {r["task_id"]: r["ctx_source"] for r in rows_from_events(early, "auto")}
    assert auto == {"a": "decision", "b": "decision"}


def test_decision_mode_drops_rows_without_logged_context():
    ev = _early_binding_log(5.0)
    del ev[2]["decision"]  # b has no logged context
    assert [r["task_id"] for r in rows_from_events(ev, "decision")] == ["a"]
    assert {r["task_id"]: r["ctx_source"] for r in rows_from_events(ev, "auto")} == {"a": "decision", "b": "start"}
    with pytest.raises(ValueError):
        rows_from_events(ev, "bogus")


def test_calibration_only_from_profiles_that_predate_the_session(tmp_path):
    for stamp, v in (("20261003T120000", 1.0), ("20261003T150000", 2.0)):
        (tmp_path / f"{stamp}_profile.json").write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": [
            {"workload": "matmul", "size": 8, "pool": "P", "median_s": v}]}))
    cal = CalibrationProfiles(tmp_path)
    assert cal.lookup("20261003T130000", "matmul", 8, "P") == (1.0, "20261003T120000_profile.json")
    assert cal.lookup("20261003T160000", "matmul", 8, "P")[0] == 2.0
    assert cal.lookup("20261003T110000", "matmul", 8, "P") == (None, None)   # no later-profile fallback
    assert CalibrationProfiles(tmp_path, allow_later_fallback=True).lookup("20261003T110000", "matmul", 8, "P")[0] == 1.0
    assert latest_profile_path(tmp_path, before="20261003T130000").name.startswith("20261003T120000")
    with pytest.raises(FileNotFoundError):
        latest_profile_path(tmp_path, before="20261003T110000")


def test_build_dataset_counts_rows_dropped_for_missing_decision_context(tmp_path):
    root = tmp_path / "data" / "events" / "phase2_20261003T115816"
    root.mkdir(parents=True)
    ev = _early_binding_log(5.0)
    ev[0].update(metadata={"experiment_id": "phase2_20261003T115816", "trace": "inst1"}, scheduler_config={})
    del ev[2]["decision"]
    (root / "r.jsonl").write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    (tmp_path / "data" / "profiles").mkdir()
    out = build_dataset(tmp_path / "data" / "events", tmp_path / "data" / "profiles", tmp_path / "data" / "datasets",
                        context_source="decision")
    m = json.loads((out / "manifest.json").read_text())
    assert m["n_task_rows"] == 1 and m["n_rows_dropped_no_decision_ctx"] == 1
    assert m["rows_per_ctx_source"] == {"decision": 1} and m["instances"] == ["inst1"]
    assert set(m["outputs"]) == {"tasks.csv", "candidates.csv", "splits.json"}
    assert m["calibration_policy"].startswith("only profiles")


def test_eft_estimates_queued_tasks_under_their_own_decision_context():
    """D4: a task already placed is costed under the context of ITS decision, not the new task's."""
    dag = DAG({t: Task(t, "w", 1) for t in ("x", "y", "z")})

    def run(legacy):
        state = RuntimeState(dag, {"W0": "A", "W1": "A"})
        p = EarliestFinishTimeScheduler(SpyEstimator(), "p", legacy_wait_context=legacy)
        p.on_run_start(dag, state)
        assert p.select_worker(dag.tasks["x"], state) == "W0"       # empty machine: x costs 0.01
        now = state.now()
        state.mark_submitted("W0", "x", now)
        state.mark_submitted("W1", "y", now)                       # now the machine looks busier
        p.select_worker(dag.tasks["z"], state)
        return p.last_decision["candidates"]["W0"]

    own, old = run(False), run(True)
    assert own["ctx"]["busy_P"] == 0 and own["ctx"]["busy_E"] == 0 and "busy_other" in own["ctx"]  # pool 'A'
    assert own["wait"] == pytest.approx(0.01, abs=5e-3)          # x under its own (empty) context: 0.01 s
    assert old["wait"] == pytest.approx(0.02, abs=5e-3)          # legacy: x re-costed under z's context (1 busy)
    assert old["wait"] > own["wait"]


def test_eft_logs_context_for_every_candidate_and_only_eligible_workers():
    dag = DAG({"t": Task("t", "w", 1, eligible_pools=("B",))})
    state = RuntimeState(dag, {"a0": "A", "b0": "B", "b1": "B"})

    class Plain(SpyEstimator):
        uses_context = False

    p = EarliestFinishTimeScheduler(Plain(), "plain")
    p.on_run_start(dag, state)
    assert p.select_worker(dag.tasks["t"], state) in ("b0", "b1")
    d = p.last_decision
    assert set(d["candidates"]) == {"b0", "b1"} and d["ctx_version"] == 2
    assert all("ctx" in c for c in d["candidates"].values())    # logged although the estimator ignores context
    off = EarliestFinishTimeScheduler(Plain(), "off", log_context=False)
    off.on_run_start(dag, state)
    off.select_worker(dag.tasks["t"], state)
    assert all("ctx" not in c for c in off.last_decision["candidates"].values())
