"""DAG representation and dependency tracking.

``DAG`` owns the task dict, the reverse (dependency -> dependents) index, and
a per-task count of still-unsatisfied dependencies. It knows nothing about
workers, scheduling, or execution -- those are the coordinator's job. This
separation is what lets the same DAG be replayed under different
scheduler/estimator combinations (the project's core experimental
requirement) without this module changing at all.

Validation happens at construction time (unknown dependencies, key/id
mismatch, cycles) so that a malformed graph fails immediately with a precise
message, rather than surfacing later as an opaque coordinator "deadlock".

The four pattern builders below (independent, chain, fork-join, mixed) cover
the DAG shapes the project brief calls out for the initial workload set.
"""
from __future__ import annotations

import collections

from caosched.core.task import Task


class CycleError(ValueError):
    pass


class DAG:
    def __init__(self, tasks: dict[str, Task]):
        if not tasks:
            raise ValueError("DAG must contain at least one task")
        self.tasks = tasks
        self._dependents: dict[str, list[str]] = {tid: [] for tid in tasks}
        for tid, task in tasks.items():
            if task.task_id != tid:
                raise ValueError(f"DAG key {tid!r} does not match task.task_id {task.task_id!r}")
            for dep in task.dependencies:
                if dep not in tasks:
                    raise ValueError(f"Task {tid!r} depends on unknown task {dep!r}")
                self._dependents[dep].append(tid)
        # Number of not-yet-completed dependencies per task; a task becomes
        # ready exactly when this hits zero (O(1) per edge, no rescans).
        self._remaining: dict[str, int] = {tid: len(t.dependencies) for tid, t in tasks.items()}
        self._completed: set[str] = set()
        self._topo_order = self._compute_topological_order()

    def _compute_topological_order(self) -> list[str]:
        """Kahn's algorithm; raises CycleError naming the tasks on/behind a cycle."""
        indegree = {tid: len(t.dependencies) for tid, t in self.tasks.items()}
        frontier = collections.deque(tid for tid, d in indegree.items() if d == 0)
        order: list[str] = []
        while frontier:
            tid = frontier.popleft()
            order.append(tid)
            for child in self._dependents[tid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    frontier.append(child)
        if len(order) != len(self.tasks):
            stuck = sorted(tid for tid, d in indegree.items() if d > 0)
            raise CycleError(f"DAG contains a cycle involving tasks: {stuck}")
        return order

    def topological_order(self) -> list[str]:
        return list(self._topo_order)

    def dependents(self, task_id: str) -> list[str]:
        return list(self._dependents[task_id])

    def initial_ready_tasks(self) -> list[str]:
        """Task ids with no dependencies -- ready before anything else runs."""
        return [tid for tid, t in self.tasks.items() if not t.dependencies]

    def mark_completed(self, task_id: str) -> list[str]:
        """Record ``task_id`` as completed and return the ids of dependents
        that just became ready (all of *their* dependencies are now satisfied).
        """
        if task_id not in self.tasks:
            raise KeyError(f"Unknown task {task_id!r}")
        if task_id in self._completed:
            raise ValueError(f"Task {task_id!r} already marked completed")
        if self._remaining[task_id] != 0:
            raise ValueError(f"Task {task_id!r} completed before its dependencies were satisfied")
        self._completed.add(task_id)
        newly_ready = []
        for dependent_id in self._dependents[task_id]:
            self._remaining[dependent_id] -= 1
            if self._remaining[dependent_id] == 0:
                newly_ready.append(dependent_id)
        return newly_ready

    def is_completed(self, task_id: str) -> bool:
        return task_id in self._completed

    def is_complete(self) -> bool:
        return len(self._completed) == len(self.tasks)

    @property
    def num_completed(self) -> int:
        return len(self._completed)

    def critical_path_length(self) -> int:
        """Longest dependency chain, in task count (unweighted -- weighted
        variants need an execution-time estimator, which is Phase 3's job)."""
        depth: dict[str, int] = {}
        for tid in self._topo_order:
            depth[tid] = 1 + max((depth[d] for d in self.tasks[tid].dependencies), default=0)
        return max(depth.values())

    def __len__(self) -> int:
        return len(self.tasks)


def _task(task_id: str, workload: str, size: int, seed: int, deps: tuple[str, ...] = ()) -> Task:
    return Task(task_id=task_id, workload=workload, size=size, seed=seed, dependencies=deps)


def build_independent_dag(n: int, workload: str = "matmul", size: int = 64, seed: int = 0) -> DAG:
    """n tasks, no dependencies between any of them."""
    tasks = {f"t{i}": _task(f"t{i}", workload, size, seed + i) for i in range(n)}
    return DAG(tasks)


def build_chain_dag(n: int, workload: str = "matmul", size: int = 64, seed: int = 0) -> DAG:
    """t0 -> t1 -> ... -> t(n-1), strictly sequential."""
    tasks: dict[str, Task] = {}
    prev = None
    for i in range(n):
        tid = f"t{i}"
        deps = (prev,) if prev else ()
        tasks[tid] = _task(tid, workload, size, seed + i, deps)
        prev = tid
    return DAG(tasks)


def build_fork_join_dag(width: int, workload: str = "matmul", size: int = 64, seed: int = 0) -> DAG:
    """root -> {branch0..branch(width-1)} -> join."""
    tasks: dict[str, Task] = {"root": _task("root", workload, size, seed)}
    for i in range(width):
        tid = f"branch{i}"
        tasks[tid] = _task(tid, workload, size, seed + i + 1, deps=("root",))
    join_deps = tuple(f"branch{i}" for i in range(width))
    tasks["join"] = _task("join", workload, size, seed + width + 1, deps=join_deps)
    return DAG(tasks)


def build_mixed_dag(workload: str = "matmul", size: int = 64, seed: int = 0) -> DAG:
    """A small fixed DAG combining a chain, a fork-join, and an independent
    branch that joins back in at the end -- exercises the runtime against a
    non-trivial dependency structure beyond the three pure patterns above.
    """
    tasks: dict[str, Task] = {
        "a": _task("a", workload, size, seed),
        "b": _task("b", workload, size, seed + 1, deps=("a",)),
        "c1": _task("c1", workload, size, seed + 2, deps=("b",)),
        "c2": _task("c2", workload, size, seed + 3, deps=("b",)),
        "d": _task("d", workload, size, seed + 4, deps=("c1", "c2")),
        "e": _task("e", workload, size, seed + 5),  # independent branch
        "f": _task("f", workload, size, seed + 6, deps=("d", "e")),
    }
    return DAG(tasks)
