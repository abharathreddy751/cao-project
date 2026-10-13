"""Pure decision-logic tests for B0-B7 against a real RuntimeState (no
processes). The coordinator integration path is in test_coordinator.py."""
import json

import pytest

from caosched.core.dag import DAG, build_independent_dag, build_mixed_dag
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task
from caosched.estimators import MovingHistoryEstimator, StaticProfileEstimator
from caosched.estimators.base import TaskSpec
from caosched.schedulers import ALL_POLICIES, policy_factories
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.simple import (
    CriticalityScheduler, GreedyEligibleScheduler, PoolOnlyScheduler, RoundRobinScheduler,
    ShortestQueueScheduler, StaticMappingScheduler,
)

WORKERS = {"P0": "P", "P1": "P", "E0": "E", "E1": "E", "E2": "E"}


def _state(dag):
    return RuntimeState(dag, WORKERS)


def _occupy(state, wid, tid, t=0.0):
    state.mark_submitted(wid, tid, t)


def _mixed_workload_dag():
    return DAG({
        "m": Task("m", "matmul", 64), "i": Task("i", "image_filter", 64), "c": Task("c", "compression", 1024),
    })


def test_b0_uses_only_its_pool_and_waits_when_pool_busy():
    dag = build_independent_dag(3)
    s = _state(dag)
    p = PoolOnlyScheduler("E")
    p.on_run_start(dag, s)
    assert p.select_worker(dag.tasks["t0"], s) == "E0"
    for w in ("E0", "E1", "E2"):
        _occupy(s, w, "t0")
    assert p.select_worker(dag.tasks["t1"], s) is None  # P idle, but never used


def test_b1_cycles_over_all_workers_including_busy():
    dag = build_independent_dag(7)
    s = _state(dag)
    p = RoundRobinScheduler()
    p.on_run_start(dag, s)
    _occupy(s, "P0", "t0")
    assert [p.select_worker(dag.tasks[f"t{i}"], s) for i in range(7)] == ["P0", "P1", "E0", "E1", "E2", "P0", "P1"]
    assert not p.binds_only_idle


def test_b2_respects_mapping_and_rejects_unmapped_workloads():
    dag = _mixed_workload_dag()
    s = _state(dag)
    p = StaticMappingScheduler({"matmul": "P", "image_filter": "E", "compression": "E"})
    p.on_run_start(dag, s)
    assert p.select_worker(dag.tasks["m"], s) == "P0"
    assert p.select_worker(dag.tasks["i"], s) == "E0"
    with pytest.raises(ValueError, match="compression"):
        StaticMappingScheduler({"matmul": "P", "image_filter": "E"}).on_run_start(dag, s)


def test_b3_picks_least_loaded_with_p_first_tiebreak():
    dag = build_independent_dag(5)
    s = _state(dag)
    p = ShortestQueueScheduler()
    assert p.select_worker(dag.tasks["t4"], s) == "P0"
    for w in WORKERS:
        _occupy(s, w, "t0")
    s.bind("t1", "P0")  # P0 now has load 2, every other worker load 1
    assert p.select_worker(dag.tasks["t4"], s) == "P1"


def test_b4_greedy_priority_and_eligibility():
    dag = _mixed_workload_dag()
    s = _state(dag)
    p = GreedyEligibleScheduler(eligibility={"compression": ["E"]}, priority=["P", "E"])
    p.on_run_start(dag, s)
    assert p.select_worker(dag.tasks["m"], s) == "P0"
    assert p.select_worker(dag.tasks["c"], s) == "E0"  # P not eligible
    _occupy(s, "P0", "m")
    _occupy(s, "P1", "i")
    assert p.select_worker(dag.tasks["m"], s) == "E0"  # greedy fallback to next eligible pool
    with pytest.raises(ValueError):
        GreedyEligibleScheduler(eligibility={"matmul": ["R"]}).on_run_start(dag, s)


def test_b5_identifies_critical_path_and_orders_by_bottom_level():
    dag = build_mixed_dag()  # a-b-{c1,c2}-d-f is the longest path; e is off it
    s = _state(dag)
    p = CriticalityScheduler()
    p.on_run_start(dag, s)
    assert p.critical == {"a", "b", "c1", "c2", "d", "f"}
    assert p.bottom_level["a"] == 5 and p.bottom_level["e"] == 2  # e -> f
    assert p.order_ready(["e", "a"], s) == ["a", "e"]


def test_b5_keeps_p_free_for_waiting_critical_task():
    dag = build_mixed_dag()
    s = _state(dag)
    p = CriticalityScheduler()
    p.on_run_start(dag, s)
    for w in ("E0", "E1", "E2"):
        _occupy(s, w, "x")
    p.order_ready(["e"], s)  # only a non-critical task waiting -> it may use P
    assert p.select_worker(dag.tasks["e"], s) == "P0"
    p.order_ready(["e", "a"], s)  # critical task "a" also waiting -> "e" must not take P
    assert p.select_worker(dag.tasks["e"], s) is None
    assert p.select_worker(dag.tasks["a"], s) == "P0"


def _profile(p_time=0.010, e_time=0.020):
    return StaticProfileEstimator({("matmul", 64, "P"): p_time, ("matmul", 64, "E"): e_time})


def test_eft_prefers_fast_idle_pool_and_logs_all_candidates():
    dag = build_independent_dag(3, size=64)
    s = _state(dag)
    p = EarliestFinishTimeScheduler(_profile(), "B6_eft_static")
    p.on_run_start(dag, s)
    assert p.select_worker(dag.tasks["t0"], s) == "P0"
    d = p.last_decision
    assert set(d["candidates"]) == set(WORKERS) and d["chosen"] == "P0"
    assert d["candidates"]["E0"]["finish"] == pytest.approx(0.020)


def test_eft_queues_behind_busy_p_only_when_that_finishes_earlier():
    dag = build_independent_dag(4, size=64)
    s = _state(dag)
    p = EarliestFinishTimeScheduler(_profile(p_time=0.010, e_time=0.100), "B6")
    p.on_run_start(dag, s)
    now = s.now()
    _occupy(s, "P0", "t0", now)
    _occupy(s, "P1", "t1", now)
    # P busy (~10 ms left) + 10 ms exec = ~20 ms  <  100 ms on an idle E worker
    assert s.pool_of(p.select_worker(dag.tasks["t2"], s)) == "P"
    p2 = EarliestFinishTimeScheduler(_profile(p_time=0.010, e_time=0.012), "B6")
    p2.on_run_start(dag, s)
    assert s.pool_of(p2.select_worker(dag.tasks["t2"], s)) == "E"


def test_eft_rejects_unprofiled_task_before_run():
    dag = build_independent_dag(1, size=999)
    with pytest.raises(KeyError):
        EarliestFinishTimeScheduler(_profile(), "B6").on_run_start(dag, _state(dag))


def test_history_estimator_overrides_prior_and_resets():
    h = MovingHistoryEstimator(_profile(), window=2)
    t = TaskSpec("t", "matmul", 64)
    assert h.estimate(t, "E") == 0.020
    for v in (0.030, 0.050, 0.070):
        h.observe(t, "E", v)
    assert h.estimate(t, "E") == pytest.approx(0.060)  # window keeps the last 2
    assert h.estimate(t, "P") == 0.010  # unobserved key still on the prior
    h.reset()
    assert h.estimate(t, "E") == 0.020


def test_b7_learns_from_completions():
    dag = build_independent_dag(1, size=64)
    s = _state(dag)
    p = EarliestFinishTimeScheduler(MovingHistoryEstimator(_profile(), 4), "B7")
    p.on_run_start(dag, s)
    t = dag.tasks["t0"]
    t.assigned_pool, t.wall_time_seconds = "P", 0.5  # P observed slow (e.g. under interference)
    p.on_task_completed(t)
    assert s.pool_of(p.select_worker(t, s)) == "E"


def test_profile_file_roundtrip_and_metric_check(tmp_path):
    good = {"metric": "kernel_wall_time_seconds",
            "entries": [{"workload": "matmul", "size": 64, "pool": "P", "median_s": 0.01}]}
    (tmp_path / "a_profile.json").write_text(json.dumps(good))
    assert StaticProfileEstimator.from_file(tmp_path / "a_profile.json").lookup("matmul", 64, "P") == 0.01
    (tmp_path / "b_profile.json").write_text(json.dumps({**good, "metric": "prepare_plus_kernel"}))
    with pytest.raises(ValueError, match="kernel_wall_time_seconds"):
        StaticProfileEstimator.from_file(tmp_path / "b_profile.json")


def test_registry_builds_every_policy_fresh(tmp_path):
    prof = {"metric": "kernel_wall_time_seconds",
            "entries": [{"workload": "matmul", "size": 64, "pool": p, "median_s": 0.01} for p in "PE"]}
    path = tmp_path / "x_profile.json"
    path.write_text(json.dumps(prof))
    f = policy_factories({"B2_static_mapping": {"mapping": {"matmul": "P"}}}, path)
    assert tuple(f) == ALL_POLICIES
    for name, make in f.items():
        a, b = make(), make()
        assert a is not b and a.name == name



def test_pool_only_early_binds_to_the_least_loaded_worker_of_its_pool():
    from caosched.core.dag import build_independent_dag
    from caosched.core.runtime_state import RuntimeState
    from caosched.schedulers.simple import PoolOnlyEarlyScheduler
    dag = build_independent_dag(3)
    state = RuntimeState(dag, {"P0": "P", "P1": "P", "E0": "E"})
    pol = PoolOnlyEarlyScheduler("P")
    pol.on_run_start(dag, state)
    assert pol.binds_only_idle is False and pol.name == "B0_P_early"
    first = pol.select_worker(dag.tasks["t0"], state)
    state.bind("t0", first)
    state.mark_submitted(first, "t0", 0.0)
    second = pol.select_worker(dag.tasks["t1"], state)
    assert {first, second} == {"P0", "P1"}                       # spreads over the pool, never E0
    state.bind("t1", second)
    state.mark_submitted(second, "t1", 0.0)
    assert pol.select_worker(dag.tasks["t2"], state) in {"P0", "P1"}   # busy workers accept queued tasks (early binding)
