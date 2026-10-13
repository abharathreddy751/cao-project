"""Baseline policies B0-B5 (no execution-time estimator).

Definitions follow docs/PROJECT_BRIEF.md ("BASELINE POLICIES"). Where the
brief names a policy without fixing its details, the concrete rule chosen is
stated in the class docstring and is the thing that must be cited.

Late binding (``binds_only_idle = True``): B0, B2, B4, B5 only ever bind to
idle workers; tasks wait in the global ready queue.
Early binding: B1, B3 bind immediately and tasks wait in worker-local queues.

Every policy picks only among ``eligible_workers(task, state)`` (AD-5), and a
policy that could never place some task raises a ``ValueError`` in
``on_run_start`` -- before any task runs -- instead of deadlocking.
"""
from __future__ import annotations

import random

from caosched.core.scheduler_base import NoEligibleWorkerError, SchedulerPolicy, eligible_workers
from caosched.core.task import Task


def _require_placeable(name: str, dag, state, allowed_pools) -> None:
    """Raise if some task has no eligible worker in the pools the policy allows for it."""
    for t in dag.tasks.values():
        allowed = allowed_pools(t)
        if not [w for w in eligible_workers(t, state) if state.pool_of(w) in allowed]:
            raise NoEligibleWorkerError(
                f"{name}: task {t.task_id!r} ({t.workload}) has no eligible worker: it is only eligible for "
                f"{t.eligible_pools or 'any pool'} and the policy only uses pools {sorted(allowed)}")


class PoolOnlyScheduler(SchedulerPolicy):
    """B0: every task runs on one pool only (``pool='P'`` -> B0-P, ``'E'``
    -> B0-E); first idle worker of that pool, else wait."""

    def __init__(self, pool: str):
        self.pool = pool
        self.name = f"B0_{pool}_only"

    def on_run_start(self, dag, state) -> None:
        if not state.worker_ids(self.pool):
            raise ValueError(f"{self.name}: no workers in pool {self.pool!r}")
        _require_placeable(self.name, dag, state, lambda t: {self.pool})

    def select_worker(self, task: Task, state) -> str | None:
        idle = [w for w in eligible_workers(task, state, idle_only=True) if state.pool_of(w) == self.pool]
        return idle[0] if idle else None

    def describe(self) -> dict:
        return {**super().describe(), "pool": self.pool}


class PoolOnlyEarlyScheduler(SchedulerPolicy):
    """B0 with EARLY binding: every task goes to the least-loaded worker of one pool (ties: worker order), at the moment it
    becomes ready, and waits in that worker's local queue. Identical placement set to ``PoolOnlyScheduler`` (late binding:
    first idle worker); the only difference is WHEN the worker is chosen. Controlled contrast for the early-versus-late
    binding explanation of the EFT/HEFT/PEFT makespan gap against B0 P-only (docs/research_redesign/FINAL_REPORT.md)."""

    binds_only_idle = False

    def __init__(self, pool: str):
        self.pool = pool
        self.name = f"B0_{pool}_early"

    def on_run_start(self, dag, state) -> None:
        if not state.worker_ids(self.pool):
            raise ValueError(f"{self.name}: no workers in pool {self.pool!r}")
        _require_placeable(self.name, dag, state, lambda t: {self.pool})

    def select_worker(self, task: Task, state) -> str | None:
        ids = [w for w in eligible_workers(task, state) if state.pool_of(w) == self.pool]
        return min(ids, key=lambda w: (state.workers[w].load, ids.index(w))) if ids else None

    def describe(self) -> dict:
        return {**super().describe(), "pool": self.pool}


class RoundRobinScheduler(SchedulerPolicy):
    """B1: classic round robin. Ready tasks (FIFO) are bound to workers in a
    fixed cyclic order (P workers then E workers), regardless of whether the
    worker is busy -- early binding into the worker's local queue. The
    cursor restarts at the first worker each run. Workers the task is not
    eligible for are skipped."""

    name = "B1_round_robin"
    binds_only_idle = False

    def on_run_start(self, dag, state) -> None:
        self._order, self._next = state.worker_ids(), 0
        _require_placeable(self.name, dag, state, lambda t: set(state.pools()))

    def select_worker(self, task: Task, state) -> str | None:
        ok, n = set(eligible_workers(task, state)), len(self._order)
        for k in range(n):
            w = self._order[(self._next + k) % n]
            if w in ok:
                self._next = (self._next + k + 1) % n
                return w
        return None


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
        _require_placeable(self.name, dag, state, lambda t: {self.mapping[t.workload]})

    def select_worker(self, task: Task, state) -> str | None:
        pool = self.mapping[task.workload]
        idle = [w for w in eligible_workers(task, state, idle_only=True) if state.pool_of(w) == pool]
        return idle[0] if idle else None

    def describe(self) -> dict:
        return {**super().describe(), "mapping": self.mapping}


class ShortestQueueScheduler(SchedulerPolicy):
    """B3: bind to the worker with the fewest bound tasks (executing +
    locally queued), ties broken by worker order (P first). Queue *length*
    only -- no notion of task cost or core speed. Early binding."""

    name = "B3_shortest_queue"
    binds_only_idle = False

    def on_run_start(self, dag, state) -> None:
        _require_placeable(self.name, dag, state, lambda t: set(state.pools()))

    def select_worker(self, task: Task, state) -> str | None:
        ids = eligible_workers(task, state)
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
        self.priority = list(priority) if priority else None  # None: decided per run from the pools
        self._priority = self.priority or ["P", "E"]
        if name is not None:  # e.g. a Phase 5 variant whose priority also includes the remote pool
            self.name = name

    def _eligible_pools(self, workload: str) -> list[str]:
        allowed = self.eligibility.get(workload, self._priority)
        return [p for p in self._priority if p in allowed]

    def on_run_start(self, dag, state) -> None:
        # Default priority: P, E when present (so a remote pool is only used if the caller lists it), else
        # the pools in worker order -- any pool names work.
        self._priority = self.priority or [p for p in ("P", "E") if p in state.pools()] or state.pools()
        _require_placeable(self.name, dag, state, lambda t: set(self._eligible_pools(t.workload)))

    def select_worker(self, task: Task, state) -> str | None:
        ok = set(eligible_workers(task, state, idle_only=True))  # per-task eligibility (application DAGs) also applies
        for pool in self._eligible_pools(task.workload):
            idle = [w for w in state.idle_workers(pool) if w in ok]
            if idle:
                return idle[0]
        return None

    def describe(self) -> dict:
        return {**super().describe(), "eligibility": self.eligibility, "priority": self._priority,
                "patent_mapping": self.patent_reference}


class CriticalityScheduler(SchedulerPolicy):
    """B5: simple criticality-aware DAG rule (unweighted -- no estimator).

    * Priority: ready tasks ordered by *bottom level* (number of tasks on the
      longest path from the task to an exit, inclusive), descending; FIFO
      among ties.
    * A task is *critical* if it lies on a longest path of the DAG
      (top_level + bottom_level - 1 == critical path length, in task count).
    * Placement ("fast" = pool "P", "slow" = pool "E" when both exist, else
      the first and second pool in worker order): critical -> idle fast worker,
      else idle slow worker. Non-critical -> idle slow worker; an idle fast
      worker is used only when no critical task is waiting in the ready
      queue. Late binding; only eligible workers are considered.
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
        pools = state.pools()
        if "P" in pools and "E" in pools:
            self.fast, self.slow = "P", "E"
        else:
            self.fast, self.slow = pools[0], pools[1] if len(pools) > 1 else pools[0]
        _require_placeable(self.name, dag, state, lambda t: {self.fast, self.slow})

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        ordered = sorted(ready_ids, key=lambda t: -self.bottom_level[t])  # stable -> FIFO among ties
        self._critical_waiting = {t for t in ordered if t in self.critical}
        return ordered

    def select_worker(self, task: Task, state) -> str | None:
        idle = eligible_workers(task, state, idle_only=True)
        idle_fast = [w for w in idle if state.pool_of(w) == self.fast]
        idle_slow = [w for w in idle if state.pool_of(w) == self.slow]
        if task.task_id in self.critical:
            pick = next(iter(idle_fast or idle_slow), None)
            if pick is not None:
                self._critical_waiting.discard(task.task_id)
            return pick
        if idle_slow:
            return idle_slow[0]
        if idle_fast and not self._critical_waiting:
            return idle_fast[0]
        return None


class RandomScheduler(SchedulerPolicy):
    """Uniformly random idle eligible worker (seeded; the generator restarts
    each run). Late binding. A reference baseline for the Stage 3 comparison."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.name = f"random_s{seed}"

    def on_run_start(self, dag, state) -> None:
        self._rng = random.Random(self.seed)
        _require_placeable(self.name, dag, state, lambda t: set(state.pools()))

    def select_worker(self, task: Task, state) -> str | None:
        idle = eligible_workers(task, state, idle_only=True)
        return self._rng.choice(idle) if idle else None

    def describe(self) -> dict:
        return {**super().describe(), "seed": self.seed}
