"""End-to-end integration tests: real multiprocessing worker pool, real
coordinator loop, real task execution (small matmul sizes to keep tests fast).
Not mocked -- these exercise actual process spawning and queue-based
dispatch/completion on whatever machine runs the test suite.
"""
from caosched.core.coordinator import Coordinator
from caosched.core.dag import build_chain_dag, build_fork_join_dag, build_independent_dag
from caosched.core.event_log import EventLogger
from caosched.core.scheduler_base import FirstIdleScheduler
from caosched.core.task import TaskState
from caosched.core.worker_pool import WorkerPool


def _run_dag(dag, tmp_path):
    # Two workers on arbitrary cores (0 and 1) -- correctness of the
    # coordinator/dispatch loop does not depend on these being real P/E
    # assignments, only on there being at least 2 logical processors, which
    # every machine running this suite has.
    pool = WorkerPool(p_core_slots=[], e_core_slots=[0, 1])
    logger = EventLogger(run_id="test", output_dir=tmp_path)
    coordinator = Coordinator(dag, pool, FirstIdleScheduler(), logger)
    try:
        coordinator.run(poll_timeout=10.0)
    finally:
        pool.shutdown()
        logger.close()
    return dag


def test_independent_dag_all_tasks_complete(tmp_path):
    dag = build_independent_dag(4, workload="matmul", size=16)
    _run_dag(dag, tmp_path)
    assert all(t.state == TaskState.DONE for t in dag.tasks.values())
    assert all(t.t_completed is not None for t in dag.tasks.values())
    assert all(t.wall_time_seconds is not None for t in dag.tasks.values())


def test_chain_dag_completes_in_dependency_order(tmp_path):
    dag = build_chain_dag(3, workload="matmul", size=16)
    _run_dag(dag, tmp_path)
    assert all(t.state == TaskState.DONE for t in dag.tasks.values())
    assert dag.tasks["t0"].t_completed <= dag.tasks["t1"].t_started
    assert dag.tasks["t1"].t_completed <= dag.tasks["t2"].t_started


def test_fork_join_dag_join_waits_for_both_branches(tmp_path):
    dag = build_fork_join_dag(width=2, workload="matmul", size=16)
    _run_dag(dag, tmp_path)
    assert dag.tasks["join"].state == TaskState.DONE
    assert dag.tasks["join"].t_started >= dag.tasks["branch0"].t_completed
    assert dag.tasks["join"].t_started >= dag.tasks["branch1"].t_completed


def test_event_log_contains_lifecycle_events_for_every_task(tmp_path):
    import json

    dag = build_independent_dag(3, workload="matmul", size=16)
    pool = WorkerPool(p_core_slots=[], e_core_slots=[0, 1])
    logger = EventLogger(run_id="test_events", output_dir=tmp_path)
    coordinator = Coordinator(dag, pool, FirstIdleScheduler(), logger)
    try:
        coordinator.run(poll_timeout=10.0)
    finally:
        pool.shutdown()
        logger.close()

    events = [json.loads(line) for line in logger.path.read_text(encoding="utf-8").splitlines()]
    event_types_per_task = {}
    for e in events:
        if "task_id" in e:  # run-level events (run_started, worker_ready, ...) have none
            event_types_per_task.setdefault(e["task_id"], []).append(e["event"])
    for tid in dag.tasks:
        assert event_types_per_task[tid] == ["task_ready", "task_dispatched", "task_submitted", "task_completed"]


# --- Phase 1 hardening: dispatch contract, failure modes, event-log fidelity ---

import pytest  # noqa: E402

from caosched.core.coordinator import DeadlockError, RunTimeoutError, TaskFailedError  # noqa: E402
from caosched.core.dag import DAG, build_mixed_dag  # noqa: E402
from caosched.core.event_log import read_events  # noqa: E402
from caosched.core.scheduler_base import SchedulerContractError, SchedulerPolicy  # noqa: E402
from caosched.core.task import Task  # noqa: E402
from caosched.core.worker_pool import WorkerPoolError  # noqa: E402


@pytest.fixture(scope="module")
def pe_pool():
    """One 'P' worker on LP0 and two 'E' workers on LP1/LP2 -- labels only;
    real P/E assignment is exercised by scripts/run_dag.py on real topology."""
    pool = WorkerPool(p_core_slots=[0], e_core_slots=[1, 2])
    yield pool
    pool.shutdown()


def _coord(dag, pool, sched, tmp_path, name="run"):
    return Coordinator(dag, pool, sched, EventLogger(run_id=name, output_dir=tmp_path))


class OnlyPool(SchedulerPolicy):
    name = "test_only_pool"

    def __init__(self, pool):
        self.pool, self.seen = pool, []

    def select_worker(self, task, state):
        c = state.idle_workers(self.pool)
        return c[0] if c else None

    def on_task_completed(self, task):
        self.seen.append(task.task_id)


def test_scheduler_choice_is_honoured_and_feedback_hook_called(pe_pool, tmp_path):
    dag = build_mixed_dag(size=16)
    sched = OnlyPool("P")
    c = _coord(dag, pe_pool, sched, tmp_path)
    summary = c.run(run_timeout=60)
    c.logger.close()
    assert summary.status == "completed" and summary.n_completed == 7
    assert summary.tasks_per_pool == {"P": 7}
    assert all(t.assigned_worker == "P0" for t in dag.tasks.values())
    assert sorted(sched.seen) == sorted(dag.tasks)


def test_event_log_is_complete_ordered_and_reconstructs_the_schedule(pe_pool, tmp_path):
    dag = build_mixed_dag(size=16)
    c = _coord(dag, pe_pool, FirstIdleScheduler(), tmp_path)
    c.run(run_timeout=60)
    c.logger.close()
    ev = read_events(c.logger.path)
    assert [e["seq"] for e in ev] == list(range(len(ev)))
    assert ev[0]["event"] == "run_started" and ev[-1]["event"] == "run_finished"
    assert ev[-1]["status"] == "completed"
    assert {e["worker_id"] for e in ev if e["event"] == "worker_ready"} == {"P0", "E0", "E1"}
    assert all(e["affinity_ok"] for e in ev if e["event"] == "worker_ready")
    # Edges in run_started match the DAG, and dispatch order respects them.
    assert sorted(map(tuple, ev[0]["edges"])) == sorted((d, t) for t, k in dag.tasks.items() for d in k.dependencies)
    disp = {e["task_id"]: e for e in ev if e["event"] == "task_dispatched"}
    done = {e["task_id"]: e for e in ev if e["event"] == "task_completed"}
    for tid, task in dag.tasks.items():
        assert disp[tid]["worker_id"] == done[tid]["worker_id"] == task.assigned_worker
        for dep in task.dependencies:
            assert done[dep]["seq"] < disp[tid]["seq"]
            assert done[dep]["t_completed"] <= done[tid]["t_started"]


def test_failing_task_fails_fast_and_is_logged(pe_pool, tmp_path):
    dag = DAG({"ok": Task("ok", "matmul", 16), "bad": Task("bad", "no_such_workload", 16, dependencies=("ok",))})
    c = _coord(dag, pe_pool, FirstIdleScheduler(), tmp_path)
    with pytest.raises(TaskFailedError, match="bad"):
        c.run(run_timeout=60)
    c.logger.close()
    ev = read_events(c.logger.path)
    assert any(e["event"] == "task_failed" and e["task_id"] == "bad" for e in ev)
    assert ev[-1]["event"] == "run_finished" and ev[-1]["status"] == "failed" and ev[-1]["n_completed"] == 1
    assert dag.tasks["bad"].state == TaskState.FAILED


def test_scheduler_returning_non_idle_worker_violates_contract(pe_pool, tmp_path):
    class Rogue(SchedulerPolicy):
        name = "rogue"

        def select_worker(self, task, state):
            return "E99"

    c = _coord(build_independent_dag(1, size=16), pe_pool, Rogue(), tmp_path)
    with pytest.raises(SchedulerContractError):
        c.run(run_timeout=10)
    c.logger.close()


def test_scheduler_that_never_dispatches_is_a_detected_deadlock(pe_pool, tmp_path):
    class Never(SchedulerPolicy):
        name = "never"

        def select_worker(self, task, state):
            return None

    c = _coord(build_independent_dag(2, size=16), pe_pool, Never(), tmp_path)
    with pytest.raises(DeadlockError):
        c.run(run_timeout=10)
    c.logger.close()


def test_dag_cannot_be_run_twice(pe_pool, tmp_path):
    dag = build_chain_dag(2, size=16)
    c = _coord(dag, pe_pool, FirstIdleScheduler(), tmp_path, "a")
    c.run(run_timeout=60)
    c.logger.close()
    with pytest.raises(RuntimeError, match="already"):
        _coord(dag, pe_pool, FirstIdleScheduler(), tmp_path, "b").run()


def test_worker_death_mid_task_is_detected_not_hung(tmp_path):
    pool = WorkerPool(p_core_slots=[], e_core_slots=[0])
    try:
        big = build_independent_dag(1, workload="matmul", size=1500)  # long enough to kill mid-run

        class KillAfterDispatch(FirstIdleScheduler):
            def select_worker(self, task, state):
                wid = super().select_worker(task, state)
                pool.workers[wid].process.kill()
                return wid

        c = _coord(big, pool, KillAfterDispatch(), tmp_path)
        with pytest.raises(WorkerPoolError, match="died"):
            c.run(poll_timeout=0.2, run_timeout=30)
        c.logger.close()
    finally:
        pool.shutdown()


def test_run_timeout_is_enforced(tmp_path):
    pool = WorkerPool(p_core_slots=[], e_core_slots=[0])
    try:
        c = _coord(build_independent_dag(1, workload="matmul", size=2500), pool, FirstIdleScheduler(), tmp_path)
        with pytest.raises(RunTimeoutError):
            c.run(poll_timeout=0.01, run_timeout=0.02)
        c.logger.close()
    finally:
        pool.shutdown()


def test_event_logger_refuses_to_clobber_existing_log(tmp_path):
    EventLogger("dup", output_dir=tmp_path).close()
    with pytest.raises(FileExistsError):
        EventLogger("dup", output_dir=tmp_path)
    EventLogger("dup", output_dir=tmp_path, overwrite=True).close()


def test_lifecycle_intervals_are_causally_consistent_at_high_resolution(pe_pool, tmp_path):
    """Regression for the Phase 1 clock finding: with time.time() on
    CPython 3.11/Windows (~1 ms steps), worker-side t_completed - t_started was
    sometimes *shorter* than the perf_counter-timed kernel inside it."""
    dag = build_fork_join_dag(width=4, workload="matmul", size=64)
    c = _coord(dag, pe_pool, FirstIdleScheduler(), tmp_path)
    c.run(run_timeout=60)
    c.logger.close()
    for t in dag.tasks.values():
        assert t.t_created <= t.t_ready <= t.t_dispatched <= t.t_submitted <= t.t_started <= t.t_completed
        assert t.t_completed - t.t_started >= t.wall_time_seconds
    ev = read_events(c.logger.path)
    assert [e["t"] for e in ev] == sorted(e["t"] for e in ev)
    assert {"epoch_anchor", "perf_anchor"} <= set(ev[0])


# --- Phase 2: every baseline through the real coordinator + worker processes ---

import json  # noqa: E402

from caosched.schedulers import ALL_POLICIES, policy_factories  # noqa: E402


@pytest.mark.parametrize("policy_name", ALL_POLICIES)
def test_every_baseline_policy_runs_a_real_dag_correctly(policy_name, pe_pool, tmp_path):
    prof = {"metric": "kernel_wall_time_seconds",
            "entries": [{"workload": "matmul", "size": 32, "pool": "P", "median_s": 0.0001},
                        {"workload": "matmul", "size": 32, "pool": "E", "median_s": 0.0002}]}
    path = tmp_path / "t_profile.json"
    path.write_text(json.dumps(prof))
    policy = policy_factories({"B2_static_mapping": {"mapping": {"matmul": "E"}}}, path)[policy_name]()

    tasks = {**build_mixed_dag(size=32).tasks}
    for i in range(6):  # extra independent tasks so early-binding policies build local queues
        tasks[f"x{i}"] = Task(f"x{i}", "matmul", 32, seed=100 + i)
    dag = DAG(tasks)
    c = _coord(dag, pe_pool, policy, tmp_path, policy_name)
    summary = c.run(run_timeout=120)
    c.logger.close()

    assert summary.status == "completed" and summary.n_completed == len(dag)
    for tid, t in dag.tasks.items():
        for dep in t.dependencies:
            assert dag.tasks[dep].t_completed <= t.t_started
        assert t.t_dispatched <= t.t_submitted <= t.t_started
    by_worker = {}
    for t in dag.tasks.values():
        by_worker.setdefault(t.assigned_worker, []).append((t.t_started, t.t_completed))
    for spans in by_worker.values():  # a worker never runs two tasks at once
        spans.sort()
        assert all(a_end <= b_start for (_, a_end), (b_start, _) in zip(spans, spans[1:]))
    if policy_name == "B0_P_only":
        assert summary.tasks_per_pool == {"P": len(dag)}
    if policy_name in ("B0_E_only", "B2_static_mapping"):
        assert summary.tasks_per_pool == {"E": len(dag)}
    ev = read_events(c.logger.path)
    if policy_name.startswith(("B6", "B7")):
        decisions = [e["decision"] for e in ev if e["event"] == "task_dispatched"]
        assert len(decisions) == len(dag) and all(len(d["candidates"]) == 3 for d in decisions)
    if not policy.binds_only_idle:
        assert any(e["worker_load_before"] > 0 for e in ev if e["event"] == "task_dispatched")
