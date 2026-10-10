"""Execution-time estimator interface (the "Execution-Time Estimator" box).

An estimator predicts the **kernel-only** execution time of a task on a
pool: the quantity recorded as ``wall_time_seconds`` (the timed ``run()``
of the workload, excluding ``prepare()`` input generation and all runtime
overhead). Project decision, 2026-10-03; every estimator, profile, history
observation and the oracle use it.

Interface::

    estimate(task, pool, ctx=None) -> seconds
    observe(task, pool, kernel_seconds, ctx=None)
    reset()
    describe() -> dict

``task`` is anything with ``task_id``, ``workload``, ``size``, ``seed``
(a ``core.task.Task`` or a ``TaskSpec``). ``ctx`` is an ``EstimateContext``:
the occupancy snapshot the scheduler can see *at decision time*, excluding
the candidate worker itself. Estimators that do not use occupancy (E0-E3)
ignore it; E4 requires it; E5 uses task identity. Swapping estimators never
touches a scheduler (ARCHITECTURE.md modularity principle).

The same ``EstimateContext`` definition is reconstructed offline from event
logs (``caosched.dataset.events``) so that E4 is trained on exactly the
features it is later queried with.
"""
from __future__ import annotations

import abc
import dataclasses

WORKLOADS = ("compression", "image_filter", "matmul")
BUSY_WINDOW_S = 0.5  # window for the candidate worker's recent busy fraction


@dataclasses.dataclass(frozen=True)
class TaskSpec:
    """Minimal task identity for offline use (event-log rows)."""
    task_id: str
    workload: str
    size: int
    seed: int = 0


@dataclasses.dataclass(frozen=True)
class EstimateContext:
    """Occupancy snapshot, excluding the candidate worker.

    busy_P / busy_E: other workers currently executing a task, per pool.
    corunning: workload type -> number of those executing tasks of that type.
    target_busy_frac: fraction of the last BUSY_WINDOW_S seconds the
        *candidate* worker itself was busy (1.0 if it is busy or has queued
        work, since the task would then start on a warm core). Captures the
        measured P-core "idle -> slow, then ramps up" effect. None = unknown
        (e.g. reconstructed from older logs without worker history).
    """
    busy_P: int = 0
    busy_E: int = 0
    corunning: tuple[tuple[str, int], ...] = ()  # sorted (workload, count) pairs; hashable
    target_busy_frac: float | None = None

    @property
    def corun(self) -> dict[str, int]:
        return dict(self.corunning)

    @property
    def busy_total(self) -> int:
        return self.busy_P + self.busy_E

    @classmethod
    def build(cls, busy_P: int, busy_E: int, workloads: list[str],
              target_busy_frac: float | None = None) -> "EstimateContext":
        counts: dict[str, int] = {}
        for w in workloads:
            counts[w] = counts.get(w, 0) + 1
        return cls(busy_P, busy_E, tuple(sorted(counts.items())), target_busy_frac)

    @classmethod
    def from_state(cls, state, exclude_worker: str | None) -> "EstimateContext":
        busy = {"P": 0, "E": 0}
        types = []
        for wid, w in state.workers.items():
            if wid == exclude_worker or not w.busy:
                continue
            busy[w.pool] = busy.get(w.pool, 0) + 1
            types.append(state.dag.tasks[w.current_task].workload)
        frac = None
        if exclude_worker is not None:
            cand = state.workers[exclude_worker]
            frac = 1.0 if not cand.idle else state.busy_fraction(exclude_worker, state.now(), BUSY_WINDOW_S)
        return cls.build(busy["P"], busy["E"], types, frac)

    def to_dict(self) -> dict:
        return {"busy_P": self.busy_P, "busy_E": self.busy_E, "corunning": self.corun,
                "target_busy_frac": self.target_busy_frac}


def estimate_key(workload: str, size: int, pool: str) -> tuple[str, int, str]:
    return (workload, int(size), pool)


class ExecutionTimeEstimator(abc.ABC):
    name: str = "abstract"
    uses_context: bool = False  # True -> EFT builds a per-candidate EstimateContext

    @abc.abstractmethod
    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        """Predicted kernel-only seconds for ``task`` on ``pool``."""
        raise NotImplementedError

    def observe(self, task, pool: str, kernel_seconds: float, ctx: EstimateContext | None = None) -> None:
        """Feed back one observed kernel time. Default: ignore (static)."""

    def reset(self) -> None:
        """Forget per-run learned state (called at the start of each run so
        repeated runs are independent). Trained/static parameters persist."""

    def describe(self) -> dict:
        return {"name": self.name}
