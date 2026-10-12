"""Offline feature reconstruction from event logs must match the online
EstimateContext definition."""
import pytest

from caosched.dataset.campaign import RandomOccupancyPolicy
from caosched.dataset.events import rows_from_events
from caosched.core.dag import DAG, build_independent_dag
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task


def _log(tasks, completions, status="completed", history=None, t0=None):
    start = {"event": "run_started", "run_id": "r", "scheduler": "s", "metadata": {"trace": "tr"},
             "tasks": {t: {"workload": w, "size": 8, "seed": i} for i, (t, w) in enumerate(tasks.items())}}
    if history is not None:
        start["worker_history"] = history
    if t0 is not None:
        start["t"] = t0
    ev = [start]
    for tid, wid, pool, t0, t1 in completions:
        ev.append({"event": "task_completed", "task_id": tid, "worker_id": wid, "pool": pool,
                   "t_started": t0, "t_completed": t1, "wall_time_seconds": (t1 - t0) * 0.9})
    ev.append({"event": "run_finished", "status": status})
    return ev


def test_context_reconstructed_at_task_start():
    tasks = {"a": "matmul", "b": "compression", "c": "matmul", "d": "image_filter"}
    rows = {r["task_id"]: r for r in rows_from_events(_log(tasks, [
        ("a", "P0", "P", 0.0, 10.0),
        ("b", "E0", "E", 1.0, 5.0),
        ("c", "E1", "E", 2.0, 3.0),   # starts while a and b run
        ("d", "E1", "E", 5.0, 6.0),   # b ended exactly at 5.0 -> not co-running (half-open interval)
    ]), "start")}  # start-time reconstruction is opt-in (default is the logged decision context)
    assert rows["a"]["ctx"].busy_total == 0
    c = rows["c"]["ctx"]
    assert (c.busy_P, c.busy_E) == (1, 1) and c.corun == {"compression": 1, "matmul": 1}
    d = rows["d"]["ctx"]
    assert (d.busy_P, d.busy_E) == (1, 0) and d.corun == {"matmul": 1}
    assert rows["c"]["kernel_s"] == 0.9 and rows["c"]["trace"] == "tr"


def test_failed_runs_are_excluded():
    assert rows_from_events(_log({"a": "matmul"}, [("a", "P0", "P", 0, 1)], status="failed"), "start") == []
    # the default is the leakage-safe 'decision' mode: a log without a logged decision context yields no rows
    assert rows_from_events(_log({"a": "matmul"}, [("a", "P0", "P", 0, 1)])) == []


def test_campaign_policy_only_uses_allowed_idle_workers():
    dag = build_independent_dag(3)
    s = RuntimeState(dag, {"P0": "P", "E0": "E", "E1": "E"})
    p = RandomOccupancyPolicy(seed=1, allowed_workers=["E0", "E1"])
    p.on_run_start(dag, s)
    picks = {p.select_worker(dag.tasks["t0"], s) for _ in range(50)}
    assert picks == {"E0", "E1"}
    s.mark_submitted("E0", "t0", 0.0)
    s.mark_submitted("E1", "t1", 0.0)
    assert p.select_worker(dag.tasks["t2"], s) is None  # P0 idle but not allowed


def test_campaign_policy_respects_task_eligibility():
    dag = DAG({"t": Task("t", "w", 1, eligible_pools=("E",)), "u": Task("u", "w", 1)})
    s = RuntimeState(dag, {"P0": "P", "E0": "E", "E1": "E"})
    p = RandomOccupancyPolicy(seed=1, allowed_workers=["P0", "E0"])
    p.on_run_start(dag, s)
    assert {p.select_worker(dag.tasks["t"], s) for _ in range(50)} == {"E0"}   # P0 idle + allowed but not eligible
    assert {p.select_worker(dag.tasks["u"], s) for _ in range(50)} == {"P0", "E0"}
    # a task no allowed worker can run is refused up front, not deadlocked mid-run
    with pytest.raises(ValueError, match="cannot be placed"):
        RandomOccupancyPolicy(seed=1, allowed_workers=["P0"]).on_run_start(dag, s)


def test_target_busy_frac_uses_logged_history_else_unknown():
    tasks = {"a": "matmul", "b": "matmul"}
    comps = [("a", "P0", "P", 10.0, 10.25), ("b", "P0", "P", 10.30, 10.4)]
    # with pre-run history: P0 busy [9.80, 9.90]; b's window [9.80, 10.30] holds 0.10 + 0.25 busy
    rows = {r["task_id"]: r for r in rows_from_events(_log(tasks, comps, history={"P0": [[9.80, 9.90]]}, t0=9.95), "start")}
    assert rows["b"]["ctx"].target_busy_frac == pytest.approx(0.70)
    assert rows["a"]["ctx"].target_busy_frac == pytest.approx(0.20)
    # older log without worker_history: window reaches before run start -> unknown, never guessed
    rows = {r["task_id"]: r for r in rows_from_events(_log(tasks, comps, t0=9.95), "start")}
    assert rows["a"]["ctx"].target_busy_frac is None and rows["b"]["ctx"].target_busy_frac is None
    # ...but known when the whole window lies inside the run
    rows = {r["task_id"]: r for r in rows_from_events(_log(tasks, comps, t0=9.0), "start")}
    assert rows["b"]["ctx"].target_busy_frac == pytest.approx(0.5)


def test_campaign_idle_gap_is_enforced_by_retry_after(tmp_path):
    """Real worker process: with min_idle_s, consecutive tasks on the one
    allowed worker are separated by at least that gap, and the coordinator
    waits (retry_after) instead of reporting a deadlock."""
    from caosched.core.coordinator import Coordinator
    from caosched.core.event_log import EventLogger
    from caosched.core.worker_pool import WorkerPool

    gap = 0.03
    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False) as pool:
        dag = build_independent_dag(4, size=16)
        policy = RandomOccupancyPolicy(seed=0, allowed_workers=["E0"], min_idle_s=gap)
        with EventLogger("gap", output_dir=tmp_path) as log:
            summary = Coordinator(dag, pool, policy, log).run(run_timeout=30)
        assert summary.status == "completed"
        spans = sorted((t.t_started, t.t_completed) for t in dag.tasks.values())
        assert all(b0 - a1 >= gap for (_, a1), (b0, _) in zip(spans, spans[1:]))
        assert len(pool.activity["E0"]) == 4  # history persisted on the pool


def test_campaign_policy_resolves_pools_and_concurrency_at_run_start():
    dag = build_independent_dag(3)
    s = RuntimeState(dag, {"P0": "P", "P1": "P", "E0": "E", "E1": "E"})
    p = RandomOccupancyPolicy(seed=1, allowed_pools=["E"])
    p.on_run_start(dag, s)
    assert p.allowed == ["E0", "E1"]
    q = RandomOccupancyPolicy(seed=4, concurrency=(2, 3))                 # default pools: all
    q.on_run_start(dag, s)
    assert 2 <= len(q.allowed) <= 3 and set(q.allowed) <= {"P0", "P1", "E0", "E1"}
    with pytest.raises(ValueError, match="unknown pools"):
        RandomOccupancyPolicy(seed=1, allowed_pools=["R"]).on_run_start(dag, s)
    with pytest.raises(ValueError, match="at least one"):
        RandomOccupancyPolicy(seed=1, allowed_workers=["P0"], allowed_pools=["P"])
