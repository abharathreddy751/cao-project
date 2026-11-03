"""Failure semantics (AD-3) and loop hardening: every failure ends the run with
a defined status and an event log that accounts for EVERY task; dead workers and
task timeouts are noticed on every loop iteration, not only when idle."""
import sys

import pytest

from caosched.core.coordinator import (Coordinator, DeadlockError, TaskFailedError, TaskTimeoutError,
                                       WorkerDiedError)
from caosched.core.dag import DAG
from caosched.core.event_log import EventLogger, read_events
from caosched.core.extcmd import make_extcmd_task, prepare_workdir
from caosched.core.scheduler_base import FirstIdleScheduler, SchedulerPolicy
from caosched.core.task import Task
from caosched.core.worker_pool import WorkerPool
from caosched.schedulers.simple import RoundRobinScheduler

PY = sys.executable
TERMINAL = {"done", "failed", "timeout", "worker_died", "aborted", "not_run"}


def _cmd(tid, code, w, deps=(), outputs=(), timeout_s=60):
    return make_extcmd_task(tid, [PY, "-c", code], w, outputs=outputs, dependencies=deps, timeout_s=timeout_s)


def _run(dag, tmp_path, scheduler=None, slots=(0, 1), **run_kw):
    """Run to the end (pass or fail); return (raised exception or None, run_finished event)."""
    pool = WorkerPool(p_core_slots=[], e_core_slots=list(slots), warmup=False)
    err = None
    try:
        with EventLogger("r", output_dir=tmp_path) as log:
            c = Coordinator(dag, pool, scheduler or FirstIdleScheduler(), log, timeout_grace=0.0)
            try:
                c.run(poll_timeout=0.2, **{"run_timeout": 120, **run_kw})
            except Exception as exc:  # noqa: BLE001
                err = exc
    finally:
        pool.shutdown()
    ev = read_events(log.path)
    assert ev[-1]["event"] == "run_finished"
    assert set(ev[-1]["task_status"]) == set(dag.tasks) and set(ev[-1]["task_status"].values()) <= TERMINAL
    return err, ev[-1]


def test_injected_failure_marks_dependents_not_run(tmp_path):
    dag = DAG({"ok": Task("ok", "matmul", 16), "bad": Task("bad", "no_such_workload", 16, dependencies=("ok",)),
               "child": Task("child", "matmul", 16, dependencies=("bad",)), "side": Task("side", "matmul", 16)})
    err, fin = _run(dag, tmp_path, slots=(0,))
    assert isinstance(err, TaskFailedError)
    assert fin["status"] == "failed" and fin["failure_reason"] == "task_failed"
    assert fin["task_status"]["bad"] == "failed" and fin["task_status"]["child"] == "not_run"
    assert fin["task_status"]["ok"] == "done"


def test_missing_output_fails_and_dependents_not_run(tmp_path):
    w = prepare_workdir(tmp_path / "w")
    dag = DAG({"a": _cmd("a", "pass", w, outputs=["x.txt"]), "b": _cmd("b", "pass", w, deps=["a"])})
    err, fin = _run(dag, tmp_path, slots=(0,))
    assert isinstance(err, TaskFailedError) and "missing" in str(err)
    assert fin["task_status"] == {"a": "failed", "b": "not_run"}


def test_hanging_command_is_killed_and_reported_as_timeout(tmp_path):
    w = prepare_workdir(tmp_path / "w")
    dag = DAG({"hang": make_extcmd_task("hang", [PY, "-c", "import time; time.sleep(300)"], w, timeout_s=1.0),
               "after": _cmd("after", "pass", w, deps=["hang"])})
    err, fin = _run(dag, tmp_path, slots=(0,))
    assert isinstance(err, TaskTimeoutError)
    assert fin["failure_reason"] == "task_timeout" and fin["task_status"] == {"hang": "timeout", "after": "not_run"}


def test_coordinator_kills_a_worker_whose_task_ignores_its_timeout(tmp_path):
    # An in-process kernel cannot kill itself: the coordinator must, via the per-task timeout check that runs on every
    # loop iteration (here after "other" completes, then every 0.2 s poll) -- not only when the pool is idle.
    dag = DAG({"slow": Task("slow", "matmul", 3000, timeout_s=0.3), "other": Task("other", "matmul", 16)})
    err, fin = _run(dag, tmp_path)
    assert isinstance(err, TaskTimeoutError) and "worker killed" in str(err)
    assert fin["failure_reason"] == "task_timeout" and fin["task_status"]["slow"] == "timeout"


def test_run_after_a_killed_worker_says_worker_dead_not_tasks_in_flight(tmp_path):
    pool = WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False)
    try:
        with EventLogger("r1", output_dir=tmp_path) as log:
            dag = DAG({"slow": Task("slow", "matmul", 3000, timeout_s=0.3)})
            with pytest.raises(TaskTimeoutError):
                Coordinator(dag, pool, FirstIdleScheduler(), log, timeout_grace=0.0).run(poll_timeout=0.2, run_timeout=120)
        assert pool.workers["E0"].current_task is None and pool.dead_workers() == ["E0"]
        with EventLogger("r2", output_dir=tmp_path) as log2:
            with pytest.raises(RuntimeError, match="worker.*dead"):
                Coordinator(DAG({"a": Task("a", "matmul", 16)}), pool, FirstIdleScheduler(), log2).run()
    finally:
        pool.shutdown()


def test_early_binding_policy_accounts_for_tasks_waiting_in_the_local_queue(tmp_path):
    # B1 binds all three tasks to the single worker at once; "bad" fails while "t1"/"t2" wait in its local queue.
    dag = DAG({"bad": Task("bad", "no_such_workload", 16), "t1": Task("t1", "matmul", 16),
               "t2": Task("t2", "matmul", 16)})
    err, fin = _run(dag, tmp_path, RoundRobinScheduler(), slots=(0,))
    assert isinstance(err, TaskFailedError) and fin["failure_reason"] == "task_failed"
    assert fin["task_status"] == {"bad": "failed", "t1": "not_run", "t2": "not_run"}


def test_deadlock_accounts_for_all_tasks(tmp_path):
    class Never(SchedulerPolicy):
        name = "never"

        def select_worker(self, task, state):
            return None

    err, fin = _run(DAG({"a": Task("a", "matmul", 16), "b": Task("b", "matmul", 16, dependencies=("a",))}),
                    tmp_path, Never(), slots=(0,))
    assert isinstance(err, DeadlockError) and fin["failure_reason"] == "deadlock"
    assert fin["task_status"] == {"a": "not_run", "b": "not_run"}


def test_worker_death_is_noticed_while_results_keep_arriving(tmp_path):
    w = prepare_workdir(tmp_path / "w")
    tasks = {"long": _cmd("long", "import time; time.sleep(120)", w)}
    prev = ()
    for i in range(20):  # ~0.3 s each on the other worker: a result arrives every iteration
        tasks[f"c{i}"] = _cmd(f"c{i}", "import time; time.sleep(0.2)", w, prev)
        prev = (f"c{i}",)
    dag = DAG(tasks)
    pool_ref = {}

    class KillLong(FirstIdleScheduler):
        def select_worker(self, task, state):
            wid = super().select_worker(task, state)
            if task.task_id == "long":
                pool_ref["pool"].workers[wid].process.kill()
            return wid

    pool = WorkerPool(p_core_slots=[], e_core_slots=[0, 1], warmup=False)
    pool_ref["pool"] = pool
    try:
        with EventLogger("r", output_dir=tmp_path) as log:
            with pytest.raises(WorkerDiedError, match="died"):
                Coordinator(dag, pool, KillLong(), log).run(poll_timeout=5.0, run_timeout=120)
    finally:
        pool.shutdown()
    fin = read_events(log.path)[-1]
    assert fin["failure_reason"] == "worker_died" and fin["task_status"]["long"] == "worker_died"
    assert set(fin["task_status"]) == set(tasks)
    assert sum(v == "done" for v in fin["task_status"].values()) < 12  # failed early, not after the chain ended


def test_rerun_starts_from_a_clean_work_directory(tmp_path):
    w = prepare_workdir(tmp_path / "w")
    first = DAG({"a": _cmd("a", "open('stale.txt','w').write('x'); raise SystemExit(1)", w)})
    err, _ = _run(first, tmp_path / "e1", slots=(0,))
    assert isinstance(err, TaskFailedError) and (w / "stale.txt").exists()
    w = prepare_workdir(w)  # the helper a rerun uses
    check = "import os, sys; sys.exit(1 if os.path.exists('stale.txt') else 0)"
    second = DAG({"a": _cmd("a", check, w)})
    err, fin = _run(second, tmp_path / "e2", slots=(0,))
    assert err is None and fin["status"] == "completed" and fin["failure_reason"] is None


def test_dead_worker_check_does_not_fire_for_a_clean_run(tmp_path):
    err, fin = _run(DAG({"a": Task("a", "matmul", 16), "b": Task("b", "matmul", 16, dependencies=("a",))}),
                    tmp_path, slots=(0,))
    assert err is None and fin["task_status"] == {"a": "done", "b": "done"}

