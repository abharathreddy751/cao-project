"""Ready queue: tasks whose dependencies are all satisfied, awaiting dispatch.

Only the single-threaded coordinator touches this, so no locking. The default
ordering is FIFO by ready time. Phase 2 policies that need a different
ordering (e.g. critical-path or shortest-predicted-first) subclass and
override ``ordered()`` -- the coordinator only iterates ``ordered()`` and calls
``remove()``, so ordering is swappable without touching the coordinator.
"""
from __future__ import annotations

from caosched.util import clock


class ReadyQueue:
    def __init__(self) -> None:
        # dict preserves insertion order -> FIFO with O(1) membership/removal.
        self._enqueued_at: dict[str, float] = {}

    def push(self, task_id: str, t: float | None = None) -> None:
        if task_id in self._enqueued_at:
            raise ValueError(f"Task {task_id!r} is already in the ready queue")
        self._enqueued_at[task_id] = clock.now() if t is None else t

    def remove(self, task_id: str) -> float:
        """Remove and return the time ``task_id`` was enqueued."""
        try:
            return self._enqueued_at.pop(task_id)
        except KeyError:
            raise KeyError(f"Task {task_id!r} is not in the ready queue") from None

    def ordered(self) -> list[str]:
        """Snapshot of queued task ids in dispatch-priority order (FIFO here)."""
        return list(self._enqueued_at)

    def enqueued_at(self, task_id: str) -> float:
        return self._enqueued_at[task_id]

    def __contains__(self, task_id: object) -> bool:
        return task_id in self._enqueued_at

    def __len__(self) -> int:
        return len(self._enqueued_at)

    def __bool__(self) -> bool:
        return bool(self._enqueued_at)
