"""Phase 4: online recalibration, EFT feedback context, EFT/oracle registries,
and one-step hindsight regret."""
import json

import pytest

from caosched.analysis.decisions import decision_rows
from caosched.core.dag import build_independent_dag
from caosched.core.runtime_state import RuntimeState
from caosched.estimators import (
    EstimateContext, ExecutionTimeEstimator, RecalibratedEstimator, ReplayOracleEstimator,
    StaticProfileEstimator, TaskSpec, build_estimator,
)
from caosched.schedulers import eft_factories, eft_policy_name, oracle_factory
from caosched.schedulers.eft import EarliestFinishTimeScheduler

T = TaskSpec("t", "matmul", 64)


def _e1(p=0.010, e=0.020):
    return StaticProfileEstimator({("matmul", 64, "P"): p, ("matmul", 64, "E"): e})


def test_recalibration_converges_per_pool_and_resets():
    rc = RecalibratedEstimator(_e1(), alpha=0.5)
    assert rc.estimate(T, "P") == pytest.approx(0.010)  # no observations yet -> factor 1
    for _ in range(20):
        rc.observe(T, "P", 0.013)
    assert rc.factor("P") == pytest.approx(1.3, rel=1e-6)
    assert rc.estimate(T, "P") == pytest.approx(0.013)
    assert rc.estimate(T, "E") == pytest.approx(0.020)  # other pool untouched
    rc.reset()
    assert rc.factor("P") == 1.0 and rc.calibration() == {}


def test_recalibration_min_obs_and_clamp():
    rc = RecalibratedEstimator(_e1(), alpha=1.0, min_obs=2, clamp=(0.5, 2.0))
    rc.observe(T, "P", 0.050)
    assert rc.factor("P") == 1.0          # below min_obs
    rc.observe(T, "P", 0.050)
    assert rc.factor("P") == 2.0          # 5x clamped to 2x
    assert rc.calibration()["P"]["n"] == 2


def test_rc_registry_rules(tmp_path):
    prof = tmp_path / "x_profile.json"
    prof.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "source_csv": "none.csv",
                                "entries": [{"workload": "matmul", "size": 64, "pool": p, "median_s": 0.01} for p in "PE"]}))
    est = build_estimator("E1+rc", prof, {"rc": {"alpha": 0.3}})
    assert isinstance(est, RecalibratedEstimator) and est.alpha == 0.3 and est.name == "E1_static_profile+rc"
    with pytest.raises(ValueError, match="adaptive"):
        build_estimator("E3+rc", prof)
    f = eft_factories(["E1", "E1+rc", "E3"], prof)
    assert list(f) == ["EFT_E1", "EFT_E1_rc", "EFT_E3"] and eft_policy_name("E4+rc") == "EFT_E4_rc"
    a, b = f["EFT_E1_rc"](), f["EFT_E1_rc"]()
    assert a is not b and a.estimator is not b.estimator


class _Spy(ExecutionTimeEstimator):
    name = "spy"
    uses_context = True

    def __init__(self):
        self.seen = []

    def estimate(self, task, pool, ctx=None):
        return 0.01

    def observe(self, task, pool, kernel_seconds, ctx=None):
        self.seen.append((task.task_id, pool, kernel_seconds, ctx))


def test_eft_feeds_back_the_decision_time_context():
    dag = build_independent_dag(2, size=64)
    s = RuntimeState(dag, {"P0": "P", "E0": "E"})
    spy = _Spy()
    p = EarliestFinishTimeScheduler(spy, "EFT_spy")
    p.on_run_start(dag, s)
    s.mark_submitted("E0", "t1", s.now())       # E0 busy when t0 is decided
    assert p.select_worker(dag.tasks["t0"], s) == "P0"
    t0 = dag.tasks["t0"]
    t0.assigned_pool, t0.wall_time_seconds = "P", 0.02
    p.on_task_completed(t0)
    (tid, pool, k, ctx), = spy.seen
    assert (tid, pool, k) == ("t0", "P", 0.02)
    assert isinstance(ctx, EstimateContext) and ctx.busy_E == 1 and ctx.busy_P == 0


def test_oracle_factory_builds_fresh_e5_policy():
    rows = [{"run_id": "r", "task_id": "t0", "seed": 0, "workload": "matmul", "size": 64, "pool": p, "kernel_s": 0.01}
            for p in "PE"]
    make = oracle_factory(rows)
    a, b = make(), make()
    assert a is not b and a.name == "O_eft_E5" and isinstance(a.estimator, ReplayOracleEstimator)


def _events(dispatches, completions):
    """dispatches: (seq, t, task, worker, pool[, decision]); completions: (seq, task, t_started, t_completed, kernel)."""
    ev = [{"seq": 0, "event": "run_started", "run_id": "R", "scheduler": "pol",
           "tasks": {x: {"workload": "matmul", "size": 64, "seed": 0} for x in ("a", "b", "c")}},
          {"seq": 1, "event": "worker_ready", "worker_id": "P0", "pool": "P"},
          {"seq": 2, "event": "worker_ready", "worker_id": "E0", "pool": "E"}]
    for d in dispatches:
        e = {"seq": d[0], "t": d[1], "event": "task_dispatched", "task_id": d[2], "worker_id": d[3], "pool": d[4]}
        if len(d) > 5:
            e["decision"] = d[5]
        ev.append(e)
    for c in completions:
        ev.append({"seq": c[0], "event": "task_completed", "task_id": c[1], "worker_id": None,
                   "t_started": c[2], "t_completed": c[3], "wall_time_seconds": c[4]})
    return sorted(ev, key=lambda e: e["seq"])


def _oracle(p_exec, e_exec):
    rows = [{"run_id": "other", "task_id": x, "seed": 0, "workload": "matmul", "size": 64, "pool": pool, "kernel_s": v}
            for x in ("a", "b", "c") for pool, v in (("P", p_exec), ("E", e_exec))]
    o = ReplayOracleEstimator.from_rows(rows)
    o.exclude_run("R")
    return o


def test_regret_zero_when_idle_slow_worker_beats_busy_fast_one():
    # a occupies P0 until t=5; b decided at t=1: P0 -> (5-1)+1 = 5, E0 -> 0+3 = 3 -> E0 is best
    ev = _events([(3, 0.0, "a", "P0", "P"), (4, 1.0, "b", "E0", "E")],
                 [(9, "a", 0.0, 5.0, 4.0), (10, "b", 1.0, 4.0, 3.0)])
    rows = {r["task_id"]: r for r in decision_rows(ev, _oracle(1.0, 3.0))}
    b = rows["b"]
    assert b["hind_best_worker"] == "E0" and b["regret_s"] == 0.0 and b["optimal"]
    assert b["hind_chosen_finish"] == pytest.approx(3.0)


def test_regret_positive_when_queueing_behind_busy_worker_was_worse():
    # b queued on busy P0 (free at 5) at t=1 although E0 idle: F(P0)=4+1=5, F(E0)=3 -> regret 2
    dec = {"chosen": "P0", "candidates": {"P0": {"wait": 0.5, "exec": 1.0, "finish": 1.5},
                                          "E0": {"wait": 0.0, "exec": 3.0, "finish": 3.0}}}
    ev = _events([(3, 0.0, "a", "P0", "P"), (4, 1.0, "b", "P0", "P", dec)],
                 [(9, "a", 0.0, 5.0, 4.0), (10, "b", 5.0, 6.0, 1.0)])
    b = {r["task_id"]: r for r in decision_rows(ev, _oracle(1.0, 3.0))}["b"]
    assert b["regret_s"] == pytest.approx(2.0) and not b["optimal"]
    assert b["regret_rel"] == pytest.approx(2.0 / 3.0)
    assert b["pred_finish"] == 1.5 and b["pred_margin"] == pytest.approx(1.5)  # predicted wait was too optimistic


def test_completed_tasks_no_longer_block_and_missing_oracle_pool_is_dropped():
    # a completed (seq 4) before c's decision (seq 5): P0 is free again
    ev = _events([(3, 0.0, "a", "P0", "P"), (5, 2.0, "c", "P0", "P")],
                 [(4, "a", 0.0, 1.0, 1.0), (9, "c", 2.0, 3.0, 1.0)])
    rows = {r["task_id"]: r for r in decision_rows(ev, _oracle(1.0, 3.0))}
    assert rows["c"]["regret_s"] == 0.0
    only_p = ReplayOracleEstimator.from_rows([{"run_id": "o", "task_id": "c", "seed": 0, "workload": "matmul",
                                               "size": 64, "pool": "P", "kernel_s": 1.0}])
    c = {r["task_id"]: r for r in decision_rows(ev, only_p)}["c"]
    assert c["n_candidates"] == 1 and c["n_workers"] == 2


def test_eft_rc_runs_end_to_end_with_real_workers(tmp_path):
    from caosched.core.coordinator import Coordinator
    from caosched.core.event_log import EventLogger, read_events
    from caosched.core.worker_pool import WorkerPool

    dag = build_independent_dag(8, size=64)
    pol = EarliestFinishTimeScheduler(RecalibratedEstimator(_e1(0.0001, 0.0002)), "EFT_E1_rc")
    with WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=True) as pool:
        with EventLogger("rc", output_dir=tmp_path) as log:
            assert Coordinator(dag, pool, pol, log).run(run_timeout=60).status == "completed"
    cal = [e["decision"]["calibration"] for e in read_events(log.path) if e["event"] == "task_dispatched"]
    assert cal[0] == {}                                         # first decision: nothing observed yet
    assert sum(v["n"] for v in pol.estimator.calibration().values()) == 8


def test_waiting_is_bind_delay_and_ready_regret_not_placement_regret():
    """Late binding: b became ready at t=0 while P0 was busy until 5 and E0 idle;
    the policy waited and bound b to P0 at t=5. At t=5 P0 (exec 1) beats E0
    (exec 3): placement optimal. The 5 s of waiting shows up as bind delay and
    as ready-time regret (finish 6 from ready vs 3 on E0 immediately)."""
    ev = _events([(3, 0.0, "a", "P0", "P"), (6, 5.0, "b", "P0", "P")],
                 [(5, "a", 0.0, 5.0, 4.0), (9, "b", 5.0, 6.0, 1.0)])
    ev.append({"seq": 4, "t": 0.0, "event": "task_ready", "task_id": "b"})
    ev.sort(key=lambda e: e["seq"])
    b = {r["task_id"]: r for r in decision_rows(ev, _oracle(1.0, 3.0))}["b"]
    assert b["bind_delay_s"] == 5.0
    assert b["regret_s"] == 0.0 and b["optimal"] and b["hind_best_worker"] == "P0"
    assert b["regret_ready_s"] == pytest.approx(3.0)
