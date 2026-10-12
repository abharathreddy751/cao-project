"""Coordinator: the runtime's main loop.

Wires together the DAG, ready queue, runtime state store, worker pool,
scheduler policy, and event logger:

  seed ready queue
  -> dispatch pass: policy orders the ready queue and binds tasks to workers
     (idle worker: submitted at once; busy worker: appended to its local queue)
  -> wait for a completion -> submit that worker's next local task (if any)
  -> update DAG -> enqueue newly-ready tasks -> repeat

Every state transition is timestamped on the ``Task`` object (via
``Task.transition``, which rejects illegal transitions) and written to the
event log as it happens.

The coordinator never decides *which* worker a task goes to -- that is
entirely the injected ``SchedulerPolicy``'s job -- but it *enforces* the
policy's binding contract (see scheduler_base.py). Failure modes are explicit
and fail fast rather than hang:
  * a task raises / exits non-zero / lacks a declared output -> ``TaskFailedError``
  * a task outlives its ``timeout_s`` (+ grace); its worker is killed -> ``TaskTimeoutError``
  * a worker process dies                -> ``WorkerDiedError`` (a ``WorkerPoolError``)
  * the run exceeds ``run_timeout``      -> ``RunTimeoutError``
  * nothing executing but DAG unfinished -> ``DeadlockError``
  * a task has no eligible worker        -> ``EligibilityError``, before anything runs
Dead workers, task timeouts and the run timeout are checked on every loop
iteration, not only when idle. There is no automatic retry (AD-3). Once the run
has started, every failure above logs a ``run_error`` and a ``run_finished``
event; ``run_finished`` carries ``failure_reason`` and ``task_status``, the
terminal status of EVERY task: done | failed | timeout | worker_died | aborted
(started, unfinished at the end) | not_run (never started, e.g. dependents of a
failed task). The up-front checks in ``run`` (``Cannot run: ...`` RuntimeError,
``EligibilityError``) raise before anything is logged, and leave the DAG untouched.
``run`` narrows ``Task.eligible_pools`` for the duration of the run only and
restores the declared values afterwards, so one DAG can be tried against
different pools.
"""
from __future__ import annotations

import collections
import dataclasses
import time

from caosched.core.dag import DAG
from caosched.core.eligibility import resolve_eligibility
from caosched.core.event_log import EventLogger
from caosched.core.extcmd import EXTCMD, declared_input_bytes
from caosched.core.ready_queue import ReadyQueue
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.runtime_state import RuntimeState
from caosched.core.scheduler_base import SchedulerContractError, SchedulerPolicy
from caosched.core.task import TaskMessage, TaskResult, TaskState
from caosched.core.worker_pool import WorkerPool, WorkerPoolError
from caosched.util import clock
from caosched.util.provenance import memory_available_bytes, software_info


class TaskFailedError(RuntimeError):
    pass


class TaskTimeoutError(TaskFailedError):
    pass


class WorkerDiedError(WorkerPoolError):
    pass


class DeadlockError(RuntimeError):
    pass


class RunTimeoutError(RuntimeError):
    pass


_FAILURE_REASONS = ((TaskTimeoutError, "task_timeout"), (TaskFailedError, "task_failed"),
                    (WorkerDiedError, "worker_died"), (RunTimeoutError, "run_timeout"),
                    (DeadlockError, "deadlock"), (SchedulerContractError, "scheduler_contract"),
                    (WorkerPoolError, "worker_error"))


def pin_coordinator_to_reserved_core(config: RuntimeConfig | None = None) -> int | None:
    """Pin this (coordinator) process to the E-core Phase 0 reserved for it.
    Returns the core actually pinned to (verified by readback), or None if
    unavailable -- best-effort: the coordinator runs correctly unpinned, just
    without the preferred isolation from worker cores.
    """
    import psutil

    try:
        config = config or RuntimeConfig.from_topology()
    except Exception:  # noqa: BLE001 - topology unavailable -> run unpinned
        return None
    core = config.coordinator_core
    if core is None:
        return None
    try:
        proc = psutil.Process()
        proc.cpu_affinity([core])
        if proc.cpu_affinity() != [core]:
            return None
    except Exception:  # noqa: BLE001
        return None
    return core


@dataclasses.dataclass(frozen=True)
class RunSummary:
    status: str
    n_tasks: int
    n_completed: int
    makespan_seconds: float | None  # first dispatch -> last completion
    tasks_per_pool: dict[str, int]
    total_wall_time_seconds: float  # sum of timed compute kernels
    mean_response_time_seconds: float | None  # ready -> completed, over DONE tasks
    scheduling_time_seconds: float = 0.0  # time spent inside the policy (order_ready + select_worker)
    failure_reason: str | None = None  # None when completed (see _FAILURE_REASONS; else the exception type)
    task_status: dict | None = None    # task_id -> done | failed | timeout | worker_died | aborted | not_run


class Coordinator:
    def __init__(
        self,
        dag: DAG,
        worker_pool: WorkerPool,
        scheduler: SchedulerPolicy,
        logger: EventLogger,
        ready_queue: ReadyQueue | None = None,
        run_metadata: dict | None = None,
        artifact_dir=None,
        timeout_grace: float = 10.0,
    ):
        self.dag = dag
        self.worker_pool = worker_pool
        self.scheduler = scheduler
        self.logger = logger
        self.ready_queue = ready_queue if ready_queue is not None else ReadyQueue()
        self.run_metadata = run_metadata or {}
        self.artifact_dir = None
        self.timeout_grace = timeout_grace  # slack after Task.timeout_s for the worker's own enforcement
        self._failed_as: dict[str, str] = {}  # task_id -> "timeout" | "worker_died" (else "failed")
        if any(t.params is not None and t.workload != EXTCMD for t in dag.tasks.values()):  # application workflow: real artifacts
            from pathlib import Path

            from caosched.apps.artifacts import DEFAULT_ROOT
            self.artifact_dir = Path(artifact_dir) if artifact_dir else DEFAULT_ROOT / logger.run_id
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.state = RuntimeState(dag, {wid: worker_pool.pool_of(wid) for wid in worker_pool.worker_ids()},
                                  history=worker_pool.activity)
        self._sched_time = 0.0

    # --- main loop -----------------------------------------------------

    def run(self, poll_timeout: float = 1.0, run_timeout: float | None = None) -> RunSummary:
        if not self.worker_pool.workers:
            raise RuntimeError("Cannot run: worker pool has zero workers")
        if any(t.state != TaskState.PENDING for t in self.dag.tasks.values()):
            raise RuntimeError("Cannot run: DAG has already been (partially) executed")
        if self.worker_pool.dead_workers():
            raise RuntimeError(f"Cannot run: worker(s) dead (e.g. killed after a timeout in an earlier run): "
                               f"{self.worker_pool.dead_workers()}")
        if self.worker_pool.idle_workers() != self.worker_pool.worker_ids():
            raise RuntimeError("Cannot run: worker pool has tasks in flight from a previous run")

        declared = {tid: t.eligible_pools for tid, t in self.dag.tasks.items()}
        resolve_eligibility(self.dag, self.worker_pool.pool_specs)  # EligibilityError before anything is logged
        self._log_run_started()
        deadline = None if run_timeout is None else time.monotonic() + run_timeout
        status, reason = "failed", None
        try:
            self.scheduler.on_run_start(self.dag, self.state)
            for tid in self.dag.initial_ready_tasks():
                self._mark_ready(tid)

            while not self.dag.is_complete():
                self._dispatch_ready_tasks()
                wake = self.scheduler.retry_after(self.state) if self.ready_queue else None
                if not self.state.any_executing():
                    if wake is not None:
                        self._check_health(deadline, run_timeout)  # the run timeout also bounds deliberate idling
                        time.sleep(max(0.0, min(wake, poll_timeout)))
                        continue
                    raise DeadlockError(
                        f"Nothing executing but DAG incomplete ({self.dag.num_completed}/{len(self.dag)} done, "
                        f"{len(self.ready_queue)} ready, scheduler {self.scheduler.name!r} bound none)"
                    )
                timeout = poll_timeout if wake is None else max(0.0, min(poll_timeout, wake))
                result = self.worker_pool.poll_result(timeout=timeout)
                if result is not None:
                    self._handle_completion(result)
                if not self.dag.is_complete():
                    self._check_health(deadline, run_timeout)
            status = "completed"
        except BaseException as exc:
            reason = next((r for cls, r in _FAILURE_REASONS if isinstance(exc, cls)), type(exc).__name__)
            self.logger.log("run_error", error_type=type(exc).__name__, error=str(exc), failure_reason=reason)
            raise
        finally:
            for tid, pools in declared.items():  # the narrowing was for this run only
                self.dag.tasks[tid].eligible_pools = pools
            summary = self._summary(status, reason)
            self.logger.log("run_finished", **dataclasses.asdict(summary))
        return summary

    def _check_health(self, deadline: float | None, run_timeout: float | None) -> None:
        """Every loop iteration: dead workers, per-task timeouts, run timeout."""
        dead = {w: self.state.workers[w].current_task for w in self.worker_pool.dead_workers()
                if self.state.workers[w].load}
        if dead:
            for tid in filter(None, dead.values()):
                self._fail_in_flight(tid, "worker_died", "worker process died")
            raise WorkerDiedError(f"Worker(s) died with tasks in flight: {dead}")
        now = clock.now()
        for wid, w in self.state.workers.items():
            task = self.dag.tasks[w.current_task] if w.current_task is not None else None
            if task is not None and task.timeout_s is not None and w.current_submitted_at is not None \
                    and now - w.current_submitted_at > task.timeout_s + self.timeout_grace:
                self.worker_pool.kill_worker(wid)
                self._fail_in_flight(task.task_id, "timeout", f"no result {task.timeout_s}s after submission; worker killed")
                raise TaskTimeoutError(f"Task {task.task_id!r} on {wid!r} exceeded its {task.timeout_s}s timeout "
                                       f"(+{self.timeout_grace}s grace); worker killed")
        if deadline is not None and time.monotonic() > deadline:
            raise RunTimeoutError(f"Run exceeded {run_timeout}s")

    def _fail_in_flight(self, task_id: str, kind: str, error: str) -> None:
        task = self.dag.tasks[task_id]
        task.transition(TaskState.FAILED)
        task.error = error
        self._failed_as[task_id] = kind
        self.logger.log("task_failed", task_id=task_id, worker_id=task.assigned_worker, pool=task.assigned_pool,
                        failure=kind, error=error)

    # --- state transitions ---------------------------------------------

    def _mark_ready(self, task_id: str) -> None:
        task = self.dag.tasks[task_id]
        task.transition(TaskState.READY)
        task.t_ready = clock.now()
        if task.workload == EXTCMD:  # producers have finished: all declared inputs exist now
            assert task.params is not None
            task.input_bytes = declared_input_bytes(task.params)
        self.ready_queue.push(task_id, task.t_ready)
        self.logger.log("task_ready", task_id=task_id)

    def _dispatch_ready_tasks(self) -> None:
        ready = self.ready_queue.ordered()
        t_o = clock.now()
        ordered = self.scheduler.order_ready(list(ready), self.state)
        self._sched_time += clock.now() - t_o
        if not set(ordered) <= set(ready) or len(set(ordered)) != len(ordered):
            raise SchedulerContractError(f"{self.scheduler.name!r}.order_ready returned ids not in the ready queue")
        late = self.scheduler.binds_only_idle
        for task_id in ordered:
            if late and not self.state.idle_workers():
                return
            task = self.dag.tasks[task_id]
            self.scheduler.last_decision = None
            t_s = clock.now()
            worker_id = self.scheduler.select_worker(task, self.state)
            dt = clock.now() - t_s
            self._sched_time += dt
            if worker_id is None:
                continue
            if worker_id not in self.state.workers:
                raise SchedulerContractError(f"{self.scheduler.name!r} chose unknown worker {worker_id!r}")
            if task.eligible_pools is not None and self.state.pool_of(worker_id) not in task.eligible_pools:
                raise SchedulerContractError(
                    f"{self.scheduler.name!r} chose {worker_id!r} (pool {self.state.pool_of(worker_id)}) for "
                    f"{task_id!r}, which is only eligible for {task.eligible_pools}")
            if late and not self.state.is_idle(worker_id):
                raise SchedulerContractError(
                    f"Late-binding scheduler {self.scheduler.name!r} chose non-idle worker {worker_id!r} "
                    f"for {task_id!r} (idle: {self.state.idle_workers()})"
                )
            self._bind(task_id, worker_id, self.scheduler.last_decision, dt)

    def _bind(self, task_id: str, worker_id: str, decision: dict | None, decision_time: float | None = None) -> None:
        task = self.dag.tasks[task_id]
        self.ready_queue.remove(task_id)
        task.transition(TaskState.DISPATCHED)
        task.t_dispatched = clock.now()
        task.assigned_worker = worker_id
        task.assigned_pool = self.state.pool_of(worker_id)
        submit_now = self.state.bind(task_id, worker_id)
        fields: dict = dict(
            task_id=task_id, worker_id=worker_id, pool=task.assigned_pool,
            queue_wait_seconds=task.queue_wait_seconds,
            worker_load_before=self.state.workers[worker_id].load - (0 if submit_now else 1),
            decision_time_s=decision_time,
        )
        if decision is not None:
            fields["decision"] = decision
        self.logger.log("task_dispatched", **fields)
        if submit_now:
            self._submit(task_id, worker_id)

    def _submit(self, task_id: str, worker_id: str) -> None:
        task = self.dag.tasks[task_id]
        task.t_submitted = clock.now()
        self.state.mark_submitted(worker_id, task_id, task.t_submitted)
        if task.workload == EXTCMD:
            assert task.params is not None
            msg = TaskMessage(task_id, task.workload, task.size, task.seed,
                              params={**task.params, "timeout_s": task.timeout_s})
        elif task.params is not None:
            from caosched.apps.artifacts import artifact_path
            assert self.artifact_dir is not None  # set in __init__ for any application workflow
            params = dict(task.params)
            kind = self.worker_pool.workers[worker_id].kind
            if kind == "cpu":  # the device variant follows the chosen pool, never a flag baked into the task (AD-6)
                params.pop("device", None)
            elif kind == "cuda":
                params["device"] = "cuda"
            msg = TaskMessage(task_id, task.workload, task.size, task.seed, params=params,
                              input_refs=tuple(str(artifact_path(self.artifact_dir, d)) for d in task.dependencies),
                              output_ref=str(artifact_path(self.artifact_dir, task_id)))
        else:
            msg = TaskMessage(task_id, task.workload, task.size, task.seed)
        self.worker_pool.submit(worker_id, msg)
        self.logger.log("task_submitted", task_id=task_id, worker_id=worker_id,
                        local_queue_wait_seconds=task.local_queue_wait_seconds)

    def _handle_completion(self, result: TaskResult) -> None:
        task_id = result.task_id
        task = self.dag.tasks.get(task_id)
        if task is None or task.assigned_worker != result.worker_id or task.state != TaskState.DISPATCHED:
            raise WorkerPoolError(f"Unexpected completion of {task_id!r} from {result.worker_id!r}")
        task.t_started = result.t_started
        task.t_completed = result.t_completed
        task.wall_time_seconds = result.wall_time_seconds
        task.error = result.error
        task.transfer_s = result.transfer_s
        task.output_bytes = result.output_bytes
        next_local = self.state.finish(result.worker_id, task_id)
        self.state.record_activity(result.worker_id, result.t_started, result.t_completed)

        if result.error:
            task.transition(TaskState.FAILED)
            if result.timed_out:
                self._failed_as[task_id] = "timeout"
            self.logger.log(
                "task_failed", task_id=task_id, worker_id=result.worker_id, pool=task.assigned_pool,
                t_started=result.t_started, t_completed=result.t_completed, error=result.error,
                failure=self._failed_as.get(task_id, "failed"), exit_status=result.exit_status,
            )
            exc_type = TaskTimeoutError if result.timed_out else TaskFailedError  # worker-side timeout: same outcome as ours
            raise exc_type(f"Task {task_id!r} failed on worker {result.worker_id!r}:\n{result.error}")

        if next_local is not None:
            self._submit(next_local, result.worker_id)
        task.transition(TaskState.DONE)
        extra: dict = {}
        if result.transfer_s is not None:  # remote pool (Phase 5)
            extra = {"transfer_s": result.transfer_s, "transfer_up_s": result.transfer_up_s,
                     "payload_bytes": result.payload_bytes}
        if result.output_bytes is not None:  # application stage / extcmd
            extra.update(output_bytes=result.output_bytes, io_s=result.io_s)
        if result.outputs is not None:  # extcmd: per-file size + SHA-256, and the input size seen at ready time
            extra.update(exit_status=result.exit_status, outputs=result.outputs, input_bytes=task.input_bytes)
        self.logger.log(
            "task_completed", task_id=task_id, worker_id=result.worker_id, pool=task.assigned_pool,
            wall_time_seconds=result.wall_time_seconds, t_started=result.t_started,
            t_completed=result.t_completed, response_time_seconds=task.response_time_seconds, **extra,
        )
        self.scheduler.on_task_completed(task)
        for newly_ready_id in self.dag.mark_completed(task_id):
            self._mark_ready(newly_ready_id)

    # --- logging helpers -----------------------------------------------

    def _log_run_started(self) -> None:
        self.logger.log(
            "run_started", run_id=self.logger.run_id, scheduler=self.scheduler.name,
            scheduler_config=self.scheduler.describe(), metadata=self.run_metadata,
            n_tasks=len(self.dag), critical_path_length=self.dag.critical_path_length(),
            edges=[[d, tid] for tid, t in self.dag.tasks.items() for d in t.dependencies],
            tasks={tid: {"workload": t.workload, "size": t.size, "seed": t.seed,
                         **({"params": t.params} if t.params is not None else {}),
                         **({"timeout_s": t.timeout_s} if t.timeout_s is not None else {}),
                         **({"eligible_pools": list(t.eligible_pools)} if t.eligible_pools is not None else {})}
                   for tid, t in self.dag.tasks.items()},
            artifact_dir=str(self.artifact_dir) if self.artifact_dir else None,
            worker_history=self._recent_history(),
            software=software_info(), memory_available_bytes=memory_available_bytes(),
            **clock.anchor(),
        )
        for info in self.worker_pool.ready_infos():
            self.logger.log(
                "worker_ready", worker_id=info.worker_id, pool=self.worker_pool.pool_of(info.worker_id),
                pid=info.pid, requested_affinity=list(info.requested_affinity),
                actual_affinity=None if info.actual_affinity is None else list(info.actual_affinity),
                affinity_ok=info.affinity_ok, affinity_error=info.affinity_error,
                warmup_seconds=info.warmup_seconds, warmup_error=info.warmup_error,
                capabilities=info.capabilities,
            )

    def _recent_history(self, horizon: float = 2.0) -> dict:
        """Busy intervals of each worker in the last ``horizon`` seconds
        before this run (from earlier runs on the same pool), so features
        depending on recent activity can be reconstructed exactly offline."""
        now = clock.now()
        return {wid: [[t0, t1] for t0, t1 in w.history if t1 >= now - horizon]
                for wid, w in self.state.workers.items()}

    def _task_status(self, t) -> str:
        if t.state == TaskState.DONE:
            return "done"
        if t.state == TaskState.FAILED:
            return self._failed_as.get(t.task_id, "failed")
        return "aborted" if t.state == TaskState.DISPATCHED and t.t_submitted is not None else "not_run"

    def _summary(self, status: str, reason: str | None = None) -> RunSummary:
        tasks = list(self.dag.tasks.values())
        done = [t for t in tasks if t.state == TaskState.DONE]
        dispatched = [t.t_dispatched for t in tasks if t.t_dispatched is not None]
        completed = [t.t_completed for t in done if t.t_completed is not None]
        makespan = (max(completed) - min(dispatched)) if (dispatched and completed) else None
        responses = [r for r in (t.response_time_seconds for t in done) if r is not None]
        return RunSummary(
            status=status,
            n_tasks=len(tasks),
            n_completed=self.dag.num_completed,
            makespan_seconds=makespan,
            tasks_per_pool=dict(collections.Counter(t.assigned_pool for t in done if t.assigned_pool is not None)),
            total_wall_time_seconds=sum(t.wall_time_seconds or 0.0 for t in done),
            mean_response_time_seconds=(sum(responses) / len(responses)) if responses else None,
            scheduling_time_seconds=self._sched_time,
            failure_reason=reason,
            task_status={t.task_id: self._task_status(t) for t in tasks},
        )
