"""Revival: state snapshot, cost breakdown, ResourceStateAwareRankGreedy, contention schedule, schedule-aware oracle, mixed-DAG workload."""
import json
import time

import pytest

from caosched.core.dag import DAG
from caosched.core.runtime_state import RuntimeState
from caosched.core.scheduler_base import eligible_workers
from caosched.core.task import Task
from caosched.estimators.profile import StaticProfileEstimator
from caosched.revival.contention import ContentionSchedule, Window
from caosched.revival.oracle import ScheduleOracleRankGreedy
from caosched.revival.policy import ResourceStateAwareRankGreedy
from caosched.revival.state import StateProvider
from caosched.revival.workload import build_dyn
from caosched.study2.policies import PredictedRankGreedy
from caosched.util import clock


def _world(workers, n=6, elig=("P", "E"), **est_times):
    dag = DAG({f"t{i}": Task(f"t{i}", "w", 1, eligible_pools=elig) for i in range(n)})
    state = RuntimeState(dag, workers)
    est = StaticProfileEstimator({("w", 1, "P"): est_times.get("P", 0.010), ("w", 1, "E"): est_times.get("E", 0.030),
                                  ("w", 1, "G"): est_times.get("G", 0.001)})
    return dag, state, est


W4 = {"P0": "P", "P1": "P", "E0": "E", "E1": "E"}


def _busy(state, *ids):
    for i, w in enumerate(ids):
        state.mark_submitted(w, f"t{i}", clock.now())


def test_snapshot_without_any_telemetry_is_safe_and_says_what_is_missing():
    dag, state, est = _world(W4)
    pol = ResourceStateAwareRankGreedy(est, "r", provider=StateProvider())
    pol.on_run_start(dag, state)
    snap = pol.provider.snapshot(state)
    assert set(snap.unavailable) >= {"foreign_load", "host_ram", "gpu_telemetry"} and snap.gpu is None and not snap.slowdown
    assert pol.select_worker(dag.tasks["t0"], state) == "P0"
    assert "unavailable" in snap.to_log()


def test_task_only_ablation_decides_like_predicted_rank_greedy():
    dag, state, est = _world(W4)
    ref = PredictedRankGreedy(est, "ref")
    new = ResourceStateAwareRankGreedy(est, "new", live_state=False, cost_gate=False)
    for p in (ref, new):
        p.on_run_start(dag, state)
    assert new.order_ready(list(dag.tasks), state) == ref.order_ready(list(dag.tasks), state)
    for busy in ((), ("P0",), ("P0", "P1"), ("P0", "P1", "E0"), ("E0", "P1")):
        dag, state, est = _world(W4)
        _busy(state, *busy)
        for p in (ref, new):
            p.on_run_start(dag, state)
        got = new.select_worker(dag.tasks["t5"], state)
        assert got == ref.select_worker(dag.tasks["t5"], state)
        new.order_ready(list(dag.tasks), state)


def test_work_conserving_idle_only_and_eligibility_with_a_gpu_worker():
    workers = {**W4, "G0": "G"}
    dag, state, est = _world(workers)                            # tasks are eligible for P and E only
    pol = ResourceStateAwareRankGreedy(est, "r")
    pol.on_run_start(dag, state)
    for busy in ((), ("P0",), ("P0", "P1", "E0"), ("P0", "P1", "E0", "E1")):
        d2, s2, _ = _world(workers)
        _busy(s2, *busy)
        pol.order_ready(list(d2.tasks), s2)
        got = pol.select_worker(d2.tasks["t5"], s2)
        elig_idle = eligible_workers(d2.tasks["t5"], s2, idle_only=True)
        assert (got in elig_idle and got != "G0") if elig_idle else got is None
        assert got is None or s2.is_idle(got)
    assert got is None                                          # last case: only the GPU worker is idle and the task may not use it
    dag3, s3, est3 = _world(workers, elig=("P", "E", "G"))      # a task that MAY use G is placed there when it is the only idle one
    pol3 = ResourceStateAwareRankGreedy(est3, "r3")
    pol3.on_run_start(dag3, s3)
    _busy(s3, "P0", "P1", "E0", "E1")
    assert pol3.select_worker(dag3.tasks["t5"], s3) == "G0"


def test_residual_signal_steers_away_from_a_slow_worker_and_is_logged():
    dag, state, est = _world(W4, P=0.100, E=0.150)
    prov = StateProvider()
    pol = ResourceStateAwareRankGreedy(est, "r", provider=prov, diagnostics=True)
    pol.on_run_start(dag, state)
    now = clock.now()
    for _ in range(3):
        prov.observe("w", "P1", "P", 0.100, 0.100, now)         # peers run at the prediction
    prov.observe("w", "P0", "P", 0.100, 0.350, now)             # P0 runs 3.5x slower than predicted
    pol.order_ready(list(dag.tasks), state)
    assert pol.select_worker(dag.tasks["t0"], state) == "P1"    # B4 would have taken P0
    d = pol.last_decision
    assert d["b4"] == "P0" and 0.1 <= d["cost"]["compute"] <= 0.2 and d["state"]["slowdown"]["P0"] > 2.0
    assert d["runner_up"][0] in ("P0", "E0") and d["fallback"] is None
    json.dumps(d)


def test_fallbacks_are_logged_with_a_reason():
    dag, state, _ = _world(W4)
    est_missing = StaticProfileEstimator({("w", 1, "P"): 0.01})            # no entry for pool E: the run falls back to B4
    pol = ResourceStateAwareRankGreedy(est_missing, "r")
    pol.on_run_start(dag, state)
    assert pol.select_worker(dag.tasks["t0"], state) == "P0" and pol.last_decision["fallback"] == "no_model_coverage"
    assert pol.order_ready(["t3", "t1"], state) == ["t3", "t1"]
    dag, state, est_flat = _world(W4, P=0.020, E=0.020)                      # no predicted benefit: B4's choice
    pol = ResourceStateAwareRankGreedy(est_flat, "r")
    pol.on_run_start(dag, state)
    assert pol.select_worker(dag.tasks["t0"], state) == "P0" and pol.last_decision["fallback"] == "gain_below_cost"
    dag, state, est = _world(W4)
    pol = ResourceStateAwareRankGreedy(est, "r", decision_budget_s=-1.0, cost_gate=False)
    pol.on_run_start(dag, state)
    for _ in range(40):
        pol.select_worker(dag.tasks["t0"], state)
    assert pol._over_budget and pol.last_decision["fallback"] == "decision_budget" and pol.fallbacks["decision_budget"] >= 9


class _Poison(Task):
    """A task that raises if the policy reads anything only known after the task ran."""

    def __getattribute__(self, name):
        if name in ("wall_time_seconds", "t_started", "t_completed", "t_submitted", "output_bytes", "transfer_s", "error"):
            raise AssertionError(f"decision read {name} of the task being scheduled")
        return super().__getattribute__(name)


def test_decision_never_reads_outcome_fields_of_the_task_being_scheduled():
    tasks = {f"t{i}": _Poison(f"t{i}", "w", 1, eligible_pools=("P", "E")) for i in range(4)}
    dag = DAG(tasks)
    state = RuntimeState(dag, W4)
    est = StaticProfileEstimator({("w", 1, "P"): 0.010, ("w", 1, "E"): 0.030})
    pol = ResourceStateAwareRankGreedy(est, "r")
    pol.on_run_start(dag, state)
    pol.order_ready(list(dag.tasks), state)
    assert pol.select_worker(dag.tasks["t0"], state) in W4
    json.dumps(pol.last_decision)


def test_decision_record_is_versioned_and_complete():
    dag, state, est = _world(W4)
    pol = ResourceStateAwareRankGreedy(est, "r")
    pol.on_run_start(dag, state)
    pol.order_ready(list(dag.tasks), state)
    pol.select_worker(dag.tasks["t0"], state)
    d = json.loads(json.dumps(pol.last_decision))
    assert d["schema"] == "revival/1" and {"chosen", "fallback", "n_idle", "pred_s"} <= set(d)
    assert "state" not in d and "cost" not in d                                   # rich diagnostics are opt-in
    full = ResourceStateAwareRankGreedy(est, "r2", diagnostics=True)
    full.on_run_start(dag, state)
    full.order_ready(list(dag.tasks), state)
    full.select_worker(dag.tasks["t0"], state)
    assert {"policy", "pool", "b4", "benefit", "state", "cost", "runner_up"} <= set(full.last_decision)


def test_hot_path_total_equals_the_component_breakdown():
    dag, state, est = _world(W4, P=0.100, E=0.150)
    prov = StateProvider()
    pol = ResourceStateAwareRankGreedy(est, "r", provider=prov)
    pol.on_run_start(dag, state)
    now = clock.now()
    for _ in range(3):
        prov.observe("w", "P1", "P", 0.100, 0.100, now)
    prov.observe("w", "P0", "P", 0.100, 0.350, now)
    snap = prov.snapshot(state)
    for w in W4:
        assert pol._total(dag.tasks["t0"], w, state, snap) == pytest.approx(pol.cost_of(dag.tasks["t0"], w, state, snap).total_s)


def test_decision_latency_at_the_maximum_pool_size():
    """14 workers (6 P, 7 E, 1 G), full activity history, a live provider with per-core sampling: one pass + one decision per task."""
    tasks = {f"t{i}": Task(f"t{i}", "w", 1, eligible_pools=("P", "E")) for i in range(60)}
    dag = DAG(tasks)
    workers = {**{f"P{i}": "P" for i in range(6)}, **{f"E{i}": "E" for i in range(7)}, "G0": "G"}
    state = RuntimeState(dag, workers)
    now = clock.now()
    for w in state.workers.values():
        for k in range(256):
            w.history.append((now - 5 - k * 0.01, now - 5 - k * 0.01 + 0.005))
    for i in range(6):
        state.mark_submitted(f"P{i}", f"t{i}", now)
    est = StaticProfileEstimator({("w", 1, "P"): 0.05, ("w", 1, "E"): 0.15})
    prov = StateProvider(core_of={w: i for i, w in enumerate(workers)}, cpu_fn=lambda: [30.0] * 20, ram_fn=lambda: 1 << 33)
    pol = ResourceStateAwareRankGreedy(est, "r", provider=prov)
    pol.on_run_start(dag, state)
    t0 = time.perf_counter()
    n = 0
    for rep in range(10):
        pol.order_ready([f"t{i}" for i in range(6, 60)], state)
        for i in range(6, 60):
            pol.select_worker(dag.tasks[f"t{i}"], state)
            n += 1
    per_call = (time.perf_counter() - t0) / n
    assert per_call < 1e-3, f"{per_call * 1e3:.3f} ms per decision (budget 1 ms)"
    assert pol._over_budget is False


def test_contention_schedule_is_deterministic_disjoint_and_exact():
    cores = [0, 2, 4, 6, 8, 10]
    a, b = ContentionSchedule.phases("a", cores, 1), ContentionSchedule.phases("a", cores, 1)
    assert a == b and a != ContentionSchedule.phases("c", cores, 2)
    first = {w.core for w in a.windows if w.start_s == 0.2}
    second = {w.core for w in a.windows if w.start_s == 1.2}
    assert len(first) == len(second) == 3 and not first & second
    assert a.burners_at(next(iter(first)), 0.5) == 2 and a.burners_at(next(iter(first)), 1.5) == 0
    s = ContentionSchedule("x", (Window(0, 0.0, 1.0, 1),))
    tab = {0: 1.0, 1: 2.0}
    assert s.duration_for(0, 0.0, 0.3, tab) == pytest.approx(0.6)
    assert s.duration_for(0, 0.0, 0.8, tab) == pytest.approx(1.3)          # 0.5 s of work in the window, 0.3 s outside
    assert s.duration_for(0, 2.0, 0.8, tab) == pytest.approx(0.8)
    assert s.duration_for(2, 0.0, 0.8, tab) == pytest.approx(0.8)          # another core
    assert s.duration_for(0, 0.0, 0.01, tab) == pytest.approx(0.01)       # shorter than a time slice: not slowed
    with pytest.raises(ValueError):
        ContentionSchedule.phases("z", [0, 2], 1)


def test_oracle_avoids_a_contended_worker_but_stays_work_conserving():
    workers = {"P0": "P", "P1": "P", "E0": "E"}
    dag, state, est = _world(workers, P=0.100, E=0.150)
    sched = ContentionSchedule("s", (Window(0, 0.0, 100.0, 2),))
    pol = ScheduleOracleRankGreedy(est, "o", schedule=sched, core_of={"P0": 0, "P1": 2, "E0": 4}, slowdown={0: 1.0, 1: 1.8, 2: 2.7})
    pol.on_run_start(dag, state)
    pol.t0 = clock.now()
    pol.order_ready(list(dag.tasks), state)
    assert pol.select_worker(dag.tasks["t0"], state) == "P1"
    state.mark_submitted("P1", "t0", clock.now())
    pol.order_ready(list(dag.tasks), state)
    assert pol.select_worker(dag.tasks["t1"], state) == "E0"               # P0 would take 0.27 s, E0 0.15 s
    state.mark_submitted("E0", "t1", clock.now())
    pol.order_ready(list(dag.tasks), state)
    assert pol.select_worker(dag.tasks["t2"], state) == "P0"               # only idle worker: used, never left idle


def test_dyn_workload_is_a_two_level_fan_in_on_p_and_e_only():
    d = build_dyn([[4, 32, 2], [2, 64, 30]], n_groups=3, order_seed=5)
    assert len(d) == 6 * 4 + 3 + 1
    assert d.tasks["aggregate"].dependencies == ("gagg_0", "gagg_1", "gagg_2") and d.tasks["aggregate"].size == 3
    assert sum(d.tasks[f"gagg_{g}"].size for g in range(3)) == 6
    assert all(t.eligible_pools == ("P", "E") for t in d.tasks.values())
    assert d.critical_path_length() == 6
    with pytest.raises(ValueError):
        build_dyn([[2, 32, 2]], n_groups=3)
    with pytest.raises(ValueError):
        build_dyn([[5, 32, 2]], n_groups=2)          # unequal groups: the fan-in stage would get inputs of different lengths


def test_revival_adapter_runs_a_contended_mixed_dag_and_verifies_the_output(tmp_path):
    from caosched.core.runtime_config import RuntimeConfig
    from caosched.experiment.design import Condition
    from caosched.revival.adapter import ReviveAdapter

    stages = ("img_source", "img_denoise", "img_edges", "img_features", "img_aggregate")
    groups = {f"{s}|{p}": {"features": [], "coef": [0.002 if p == "P" else 0.004], "n": 1, "mae_s": 0.0} for s in stages for p in "PE"}
    model = tmp_path / "pm.json"
    model.write_text(json.dumps({"groups": groups}))
    kw = {"dyn": {"classes": [[4, 32, 2], [2, 64, 30]], "groups": 2}, "binding": "rsa_combined", "param_model": str(model),
          "instances_spec": {"i1": {"order_seed": 3, "contention": {"seed": 1, "n_hot": 1, "burners": 1, "t0": 0.05, "phase_s": 0.3,
                                                                    "n_phases": 1}}}}
    a = ReviveAdapter(runtime_config=RuntimeConfig(p_core_slots=(0,), e_core_slots=(1,)), timeout_s=120, run_timeout_s=300)
    try:
        wd = tmp_path / "session" / "runs" / "b0000_00_x"
        wd.mkdir(parents=True)
        rec = a.run_one(Condition("RSA", "EFT_E1", None, {}, kw, instance="i1"), wd, seed=1)
        assert rec.status == "ok" and rec.output_ok is True, rec.error
        assert rec.extra["contention"]["windows"][0]["core"] == 0 and rec.extra["contention_t0"] is not None
        assert rec.extra["revival"]["over_budget"] is False
        from caosched.core.event_log import read_events
        disp = [e for e in read_events(wd / rec.event_log) if e["event"] == "task_dispatched"]
        assert disp and all(e["decision"]["schema"] == "revival/1" for e in disp)
    finally:
        a.close()
