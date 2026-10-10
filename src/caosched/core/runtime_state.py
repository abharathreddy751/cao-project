"""Runtime State Store: the coordinator's view of every worker, exposed
read-only to scheduler policies.

Each worker has at most one task *executing* (``current_task``, already sent
to the worker process) and a FIFO *local queue* of tasks the scheduler has
bound to it but that have not been sent yet. Two binding styles fall out of
this:

* late binding  -- the policy only ever picks idle workers (local queue
  always empty); tasks wait in the global ready queue. B0, B2, B4, B5.
* early binding -- the policy may bind to a busy worker, so the task waits in
  that worker's local queue. Needed for queue-aware policies: B1, B3, and the
  EFT family (B6, B7, P), whose F(t,w) = wait(w) + transfer + exec(t,w) is
  meaningless if every candidate is idle.

Policies must treat this object as read-only; only the coordinator mutates
it (``bind`` / ``mark_submitted`` / ``finish`` / ``record_activity``).

Activity history: each worker also carries its recent busy intervals
(worker-side ``t_started``/``t_completed``, clock.now() timebase). The deque
is owned by the ``WorkerPool`` and shared across runs, so a worker that sat
idle during the previous run is seen as idle -- this matters because a P-core
that has been idle runs measurably slower for a while (Phase 3 diagnostic).
"""
from __future__ import annotations

import collections
import dataclasses

from caosched.core.dag import DAG
from caosched.util import clock


@dataclasses.dataclass
class WorkerView:
    worker_id: str
    pool: str
    current_task: str | None = None
    current_submitted_at: float | None = None
    local_queue: collections.deque = dataclasses.field(default_factory=collections.deque)
    history: collections.deque = dataclasses.field(default_factory=lambda: collections.deque(maxlen=256))

    @property
    def busy(self) -> bool:
        return self.current_task is not None

    @property
    def idle(self) -> bool:
        return not self.busy and not self.local_queue

    @property
    def load(self) -> int:
        """Tasks bound to this worker (executing + locally queued)."""
        return len(self.local_queue) + (1 if self.busy else 0)


class RuntimeState:
    def __init__(self, dag: DAG, worker_pools: dict[str, str], history: dict | None = None):
        """``worker_pools`` maps worker_id -> pool, in a stable order (P
        workers first by convention); that order is the tie-break order.
        ``history`` (optional) maps worker_id -> deque of (t_start, t_end)
        busy intervals, shared with the WorkerPool so it persists across runs."""
        self.dag = dag
        self.workers: dict[str, WorkerView] = {}
        for wid, pool in worker_pools.items():
            w = WorkerView(wid, pool)
            if history is not None:
                w.history = history.setdefault(wid, collections.deque(maxlen=256))
            self.workers[wid] = w

    @staticmethod
    def now() -> float:
        return clock.now()

    # --- read-only queries (for policies) ------------------------------

    def worker_ids(self, pool: str | None = None) -> list[str]:
        return [wid for wid, w in self.workers.items() if pool is None or w.pool == pool]

    def idle_workers(self, pool: str | None = None) -> list[str]:
        return [wid for wid, w in self.workers.items() if w.idle and (pool is None or w.pool == pool)]

    def is_idle(self, worker_id: str) -> bool:
        return self.workers[worker_id].idle

    def pool_of(self, worker_id: str) -> str:
        return self.workers[worker_id].pool

    def pools(self) -> list[str]:
        return list(dict.fromkeys(w.pool for w in self.workers.values()))

    def any_executing(self) -> bool:
        return any(w.busy for w in self.workers.values())

    def busy_fraction(self, worker_id: str, now: float, window: float) -> float:
        """Fraction of [now - window, now] during which the worker was busy
        (completed intervals from its history plus the executing task)."""
        w = self.workers[worker_id]
        lo = now - window
        busy = 0.0
        for t0, t1 in w.history:
            busy += max(0.0, min(t1, now) - max(t0, lo))
        if w.busy and w.current_submitted_at is not None:
            busy += max(0.0, now - max(w.current_submitted_at, lo))
        return min(1.0, busy / window)

    def last_finished(self, worker_id: str) -> float | None:
        h = self.workers[worker_id].history
        return h[-1][1] if h else None

    # --- mutations (coordinator only) ----------------------------------

    def bind(self, task_id: str, worker_id: str) -> bool:
        """Bind ``task_id`` to ``worker_id``. Returns True if the worker is
        idle and the task should be submitted immediately."""
        w = self.workers[worker_id]
        if w.idle:
            return True
        w.local_queue.append(task_id)
        return False

    def mark_submitted(self, worker_id: str, task_id: str, t: float) -> None:
        w = self.workers[worker_id]
        if w.busy:
            raise RuntimeError(f"Worker {worker_id!r} already executing {w.current_task!r}")
        w.current_task, w.current_submitted_at = task_id, t

    def record_activity(self, worker_id: str, t_start: float, t_end: float) -> None:
        self.workers[worker_id].history.append((t_start, t_end))

    def finish(self, worker_id: str, task_id: str) -> str | None:
        """Clear the executing task; return the next locally queued task id
        (to be submitted now), or None."""
        w = self.workers[worker_id]
        if w.current_task != task_id:
            raise RuntimeError(f"Worker {worker_id!r} finished {task_id!r} but was executing {w.current_task!r}")
        w.current_task = w.current_submitted_at = None
        return w.local_queue.popleft() if w.local_queue else None
