"""Baseline policies B0-B5 (no execution-time estimator).

Definitions follow docs/PROJECT_BRIEF.md ("BASELINE POLICIES"). Where the
brief names a policy without fixing its details, the concrete rule chosen is
stated in the class docstring and is the thing that must be cited.

Late binding (``binds_only_idle = True``): B0, B2, B4, B5 only ever bind to
idle workers; tasks wait in the global ready queue.
Early binding: B1, B3 bind immediately and tasks wait in worker-local queues.
"""
from __future__ import annotations

import itertools

from caosched.core.scheduler_base import SchedulerPolicy
from caosched.core.task import Task


class PoolOnlyScheduler(SchedulerPolicy):
    """B0: every task runs on one pool only (``pool='P'`` -> B0-P, ``'E'``
    -> B0-E); first idle worker of that pool, else wait."""

    def __init__(self, pool: str):
        self.pool = pool
        self.name = f"B0_{pool}_only"

    def on_run_start(self, dag, state) -> None:
        if not state.worker_ids(self.pool):
            raise ValueError(f"{self.name}: no workers in pool {self.pool!r}")

    def select_worker(self, task: Task, state) -> str | None:
        idle = state.idle_workers(self.pool)
        return idle[0] if idle else None

    def describe(self) -> dict:
        return {**super().describe(), "pool": self.pool}


class RoundRobinScheduler(SchedulerPolicy):
    """B1: classic round robin. Ready tasks (FIFO) are bound to workers in a
    fixed cyclic order (P workers then E workers), regardless of whether the
    worker is busy -- early binding into the worker's local queue. The
    cursor restarts at the first worker each run."""

    name = "B1_round_robin"
    binds_only_idle = False

    def on_run_start(self, dag, state) -> None:
        self._cycle = itertools.cycle(state.worker_ids())

    def select_worker(self, task: Task, state) -> str | None:
        return next(self._cycle)


class StaticMappingScheduler(SchedulerPolicy):
    """B2: fixed workload-type -> pool mapping (from config). A task waits
    for an idle worker of its mapped pool; it never runs elsewhere."""

    name = "B2_static_mapping"

    def __init__(self, mapping: dict[str, str]):
        if not mapping:
            raise ValueError("B2 needs a non-empty workload -> pool mapping")
        self.mapping = dict(mapping)

    def on_run_start(self, dag, state) -> None:
        missing = sorted({t.workload for t in dag.tasks.values()} - set(self.mapping))
        if missing:
            raise ValueError(f"{self.name}: no pool mapped for workload(s) {missing}")
        unknown = sorted(set(self.mapping.values()) - set(state.pools()))
        if unknown:
            raise ValueError(f"{self.name}: mapping targets pools with no workers: {unknown}")

    def select_worker(self, task: Task, state) -> str | None:
        idle = state.idle_workers(self.mapping[task.workload])
        return idle[0] if idle else None

    def describe(self) -> dict:
        return {**super().describe(), "mapping": self.mapping}


class ShortestQueueScheduler(SchedulerPolicy):
    """B3: bind to the worker with the fewest bound tasks (executing +
    locally queued), ties broken by worker order (P first). Queue *length*
    only -- no notion of task cost or core speed. Early binding."""

    name = "B3_shortest_queue"
    binds_only_idle = False

    def select_worker(self, task: Task, state) -> str | None:
        ids = state.worker_ids()
        return min(ids, key=lambda w: (state.workers[w].load, ids.index(w)))


class GreedyEligibleScheduler(SchedulerPolicy):
    """B4: patent-mapped greedy eligible-worker dispatch.

    Rule: each workload type has a set of *eligible* pools (config; default:
    all pools). Ready tasks are considered in FIFO ready order; each goes to
    the first idle eligible worker, scanning pools in a fixed priority order
    (config) and workers in id order. No cost model, no execution-time
    estimate, no lookahead. If no eligible worker is idle, the task waits.

    Patent mapping -- a COMPARISON BASELINE, NOT an implementation of
    US 11,561,826 B1 ("Scheduling processing of machine learning tasks on
    heterogeneous compute circuits", Xilinx, granted 2023-01-24). Only the
    patent's general eligible-worker / heterogeneous dispatch idea is mapped:
      * per-task eligibility: a task node is assigned to "one or more of the
        kernel objects", each kernel type indicating a compute circuit
        -> our workload -> eligible-pools map;
      * availability-driven, eligibility-gated dispatch: "a thread will only
        dequeue a task from the assigned task queue if the node that
        represents that task has assigned the kernel of the kernel object
        being executed by the thread" -> an idle worker receives the oldest
        ready task it is eligible for, with no performance prediction.
    Our additions (not from the patent): the P-before-E pool priority used
    when several eligible workers are idle (the patent does not say which
    free thread takes a task), and one global FIFO ready queue scanned for
    eligibility instead of per-kernel task queues.
    NOT implemented: kernel objects/definitions, FPGA/GPU compute circuits,
    blocking vs non-blocking kernels and wait threads, in-action graphs and
    buffer passing, pipelining of multiple jobs, utilization-triggered
    worker-thread scaling, and any claim-level specifics. Dependency gating
    (enqueue after all parents complete) exists in our runtime for every
    policy and is not B4-specific. See docs/B4_PATENT_MAPPING.md.
    """

    name = "B4_greedy_eligible"
    patent_reference = "US 11,561,826 B1 (eligible-worker dispatch concept only; see docs/B4_PATENT_MAPPING.md)"

    def __init__(self, eligibility: dict[str, list[str]] | None = None, priority: list[str] | None = None,
                 name: str | None = None):
        self.eligibility = {k: list(v) for k, v in (eligibility or {}).items()}
        self.priority = list(priority or ["P", "E"])
        if name is not None:  # e.g. a Phase 5 variant whose priority also includes the remote pool
            self.name = name

    def _eligible_pools(self, workload: str) -> list[str]:
        allowed = self.eligibility.get(workload, self.priority)
        return [p for p in self.priority if p in allowed]

    def on_run_start(self, dag, state) -> None:
        for wl in {t.workload for t in dag.tasks.values()}:
            if not any(state.worker_ids(p) for p in self._eligible_pools(wl)):
                raise ValueError(f"{self.name}: workload {wl!r} has no eligible worker")

    def select_worker(self, task: Task, state) -> str | None:
        pools = self._eligible_pools(task.workload)
        if task.eligible_pools is not None:  # per-task eligibility (application DAGs) also applies
            pools = [p for p in pools if p in task.eligible_pools]
        for pool in pools:
            idle = state.idle_workers(pool)
            if idle:
                return idle[0]
        return None

    def describe(self) -> dict:
        return {**super().describe(), "eligibility": self.eligibility, "priority": self.priority,
                "patent_mapping": self.patent_reference}


class CriticalityScheduler(SchedulerPolicy):
    """B5: simple criticality-aware DAG rule (unweighted -- no estimator).

    * Priority: ready tasks ordered by *bottom level* (number of tasks on the
      longest path from the task to an exit, inclusive), descending; FIFO
      among ties.
    * A task is *critical* if it lies on a longest path of the DAG
      (top_level + bottom_level - 1 == critical path length, in task count).
    * Placement: critical -> idle P worker, else any idle worker.
      Non-critical -> idle E worker; an idle P worker is used only when no
      critical task is waiting in the ready queue. Late binding.
    """

    name = "B5_criticality"

    def on_run_start(self, dag, state) -> None:
        order = dag.topological_order()
        top: dict[str, int] = {}
        for tid in order:
            top[tid] = 1 + max((top[d] for d in dag.tasks[tid].dependencies), default=0)
        bottom: dict[str, int] = {}
        for tid in reversed(order):
            bottom[tid] = 1 + max((bottom[c] for c in dag.dependents(tid)), default=0)
        cp = max(bottom.values())
        self.bottom_level = bottom
        self.critical = frozenset(tid for tid in order if top[tid] + bottom[tid] - 1 == cp)
        self._critical_waiting: set[str] = set()

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        ordered = sorted(ready_ids, key=lambda t: -self.bottom_level[t])  # stable -> FIFO among ties
        self._critical_waiting = {t for t in ordered if t in self.critical}
        return ordered

    def select_worker(self, task: Task, state) -> str | None:
        idle_p, idle_e = state.idle_workers("P"), state.idle_workers("E")
        if task.task_id in self.critical:
            pick = (idle_p or idle_e or [None])[0]
            if pick is not None:
                self._critical_waiting.discard(task.task_id)
            return pick
        if idle_e:
            return idle_e[0]
        if idle_p and not self._critical_waiting:
            return idle_p[0]
        return None
