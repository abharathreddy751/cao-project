"""Task abstraction for the DAG runtime.

A ``Task`` carries exactly what a worker needs to execute it -- a workload name
and size understood by :mod:`caosched.phase0.benchmarks.workloads` -- plus its
dependency list and a full set of lifecycle timestamps. Every timestamp field
is filled in by the coordinator/worker pipeline as the task actually moves
through the system; nothing here is estimated or backfilled.

``TaskResult`` is the single message type a worker sends back to the
coordinator; ``TaskMessage`` is the single message type sent the other way.
Both are plain frozen dataclasses so they pickle cleanly across the
``spawn``-context process boundary.
"""
from __future__ import annotations

import dataclasses
import enum

from caosched.util import clock


class TaskState(enum.Enum):
    PENDING = "pending"        # unmet dependencies
    READY = "ready"            # all dependencies satisfied, not yet dispatched
    DISPATCHED = "dispatched"  # bound to a worker (in its local queue or executing)
    DONE = "done"
    FAILED = "failed"


# Legal lifecycle transitions. Anything else is a coordinator bug and is
# rejected loudly rather than silently corrupting the recorded timeline.
_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.PENDING: frozenset({TaskState.READY}),
    TaskState.READY: frozenset({TaskState.DISPATCHED}),
    TaskState.DISPATCHED: frozenset({TaskState.DONE, TaskState.FAILED}),
    TaskState.DONE: frozenset(),
    TaskState.FAILED: frozenset(),
}


class InvalidTransition(RuntimeError):
    pass


@dataclasses.dataclass
class Task:
    task_id: str
    workload: str  # key into caosched.phase0.benchmarks.workloads.WORKLOADS
    size: int
    seed: int = 0
    dependencies: tuple[str, ...] = ()
    state: TaskState = TaskState.PENDING
    # Application stages only (None for benchmark kernels): stage parameters;
    # inputs are the output artifacts of ``dependencies`` in that order.
    params: dict | None = None
    # Pools this task may run on (None = any). Enforced by the coordinator.
    eligible_pools: tuple[str, ...] | None = None
    # Coordinator-side limit: a task still running this long after submission
    # (+ the coordinator's grace) is killed with its worker. extcmd tasks also
    # pass it to the worker, which kills the process tree itself.
    timeout_s: float | None = None
    memory_bytes: int | None = None  # request; checked against PoolSpec.memory_limit_bytes
    # File sizes (extcmd tasks): sum of declared inputs, refreshed by the
    # coordinator when the task becomes ready; output size set on completion.
    input_bytes: int | None = None
    output_bytes: int | None = None

    # Lifecycle timestamps in caosched.util.clock.now() seconds (QPC; shared
    # across coordinator and worker processes). None until that transition.
    t_created: float = dataclasses.field(default_factory=clock.now)
    t_ready: float | None = None
    t_dispatched: float | None = None   # bound to a worker by the scheduler
    t_submitted: float | None = None    # actually sent to the worker process
    t_started: float | None = None
    t_completed: float | None = None

    assigned_worker: str | None = None
    assigned_pool: str | None = None
    wall_time_seconds: float | None = None
    error: str | None = None
    # Remote pools only (Phase 5): measured link time, both directions.
    transfer_s: float | None = None

    def __post_init__(self) -> None:
        self.dependencies = tuple(self.dependencies)
        if self.eligible_pools is not None:
            self.eligible_pools = tuple(self.eligible_pools)
        if not self.task_id:
            raise ValueError("task_id must be non-empty")
        if self.size <= 0:
            raise ValueError(f"Task {self.task_id!r}: size must be positive, got {self.size}")
        if self.task_id in self.dependencies:
            raise ValueError(f"Task {self.task_id!r} depends on itself")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError(f"Task {self.task_id!r} lists a dependency more than once")

    def transition(self, new_state: TaskState) -> None:
        if new_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransition(f"Task {self.task_id!r}: illegal transition {self.state.name} -> {new_state.name}")
        self.state = new_state

    # Estimator identity. An extcmd task is told apart by its transformation (profile key size 1); its model
    # size feature is the declared input bytes known at ready time (>= 1 so log() is defined). Every
    # estimator, scheduler and dataset row uses these, never workload/size, so online == offline features.
    @property
    def est_workload(self) -> str:
        if self.workload != "extcmd":
            return self.workload
        assert self.params is not None  # an extcmd task always carries its params
        return self.params["transformation"]

    @property
    def est_size(self) -> int:
        return 1 if self.workload == "extcmd" else self.size

    @property
    def est_bytes(self) -> int:
        return max(1, self.input_bytes or 1) if self.workload == "extcmd" else self.size

    @property
    def queue_wait_seconds(self) -> float | None:
        """Time spent ready-but-undispatched (scheduler/ready-queue delay)."""
        if self.t_ready is None or self.t_dispatched is None:
            return None
        return self.t_dispatched - self.t_ready

    @property
    def local_queue_wait_seconds(self) -> float | None:
        """Time bound to a worker but waiting in its local queue (0 for
        late-binding policies, which only ever bind to idle workers)."""
        if self.t_dispatched is None or self.t_submitted is None:
            return None
        return self.t_submitted - self.t_dispatched

    @property
    def response_time_seconds(self) -> float | None:
        """Ready -> completed. Coordinator- and worker-side stamps share the
        clock.now() timebase, so this is a valid cross-process interval."""
        if self.t_ready is None or self.t_completed is None:
            return None
        return self.t_completed - self.t_ready


@dataclasses.dataclass(frozen=True)
class TaskMessage:
    """Coordinator -> worker. ``params`` set => application stage: read
    ``input_refs`` (artifact paths, dependency order), write ``output_ref``."""
    task_id: str
    workload: str
    size: int
    seed: int
    params: dict | None = None
    input_refs: tuple[str, ...] = ()
    output_ref: str | None = None


@dataclasses.dataclass(frozen=True)
class TaskResult:
    """Worker -> coordinator. The transfer fields are set only by remote
    proxies (Phase 5): measured round-trip link time excluding the node-side
    span, the upstream part of it, and the payload bytes moved."""
    task_id: str
    worker_id: str
    wall_time_seconds: float | None
    error: str | None
    t_started: float
    t_completed: float
    transfer_s: float | None = None
    transfer_up_s: float | None = None
    payload_bytes: int | None = None
    output_bytes: int | None = None   # application stages: size of the output artifact; extcmd: sum of declared outputs
    io_s: float | None = None         # application stages: artifact read/decode + encode/write time
    # extcmd tasks only: process exit status, whether the timeout killed it, and
    # {declared output path: {"bytes": n, "sha256": hex}}.
    exit_status: int | None = None
    timed_out: bool = False
    outputs: dict | None = None
