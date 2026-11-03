"""HEFT: static list scheduling with upward rank and insertion-based EFT.

STATUS OF THE DEFINITION: written from the standard formulation in secondary
sources (Topcuoglu, Hariri, Wu, IEEE TPDS 2002); the original paper has NOT
been read, so details (tie-breaking, how the average communication cost is
formed, complexity claims) are unverified. Only the well-known formulas are
used:

    wbar(i)    = mean over the processors that may run i of w(i, p)
    rank_u(i)  = wbar(i) + max over successors j of ( cbar(i,j) + rank_u(j) )
                 (exit task: wbar(i))
    tasks are scheduled in decreasing rank_u; each goes to the processor with
    the smallest earliest finish time
        EST(i,p) = earliest idle slot on p (INSERTION: a gap between already
                   planned tasks counts) not before
                   max over predecessors m of AFT(m) + c(m,i)   [c = 0 if m is on p]
        EFT(i,p) = EST(i,p) + w(i,p)

A *processor* is a worker; ``w(i,p)`` is the profile cost of ``i`` on ``p``'s
pool (estimator E1, no contention, which is HEFT's assumption), restricted to
``eligible_workers`` (uniform eligibility, D3). ``comm(parent, child)`` is the
transfer time of the edge when parent and child run on different workers (default
0: local pools share memory/files); the same value is used as cbar in the rank.

``HeftScheduler`` is a PLAN method: the plan is computed once in
``on_run_start`` from the profile and followed at run time (each task goes to
its planned worker, ready tasks are dispatched in planned-start order). An online/
adaptive variant is not claimed. Late arrival of a task relative to its planned
slot is not corrected, so the executed order on a worker can differ from the plan.
"""
from __future__ import annotations

import dataclasses
import statistics

from caosched.core.scheduler_base import SchedulerPolicy, eligible_workers
from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator


@dataclasses.dataclass
class Plan:
    assign: dict[str, str]
    start: dict[str, float]
    finish: dict[str, float]
    order: list[str]          # order in which tasks were placed
    rank: dict[str, float]    # priority (rank_u for HEFT, rank_oct for PEFT)

    @property
    def makespan(self) -> float:
        return max(self.finish.values())


def earliest_slot(busy: list[tuple[float, float]], ready: float, duration: float) -> float:
    """Insertion policy: earliest start >= ``ready`` that fits ``duration`` in a gap of
    ``busy`` (sorted, non-overlapping intervals) or after the last interval."""
    t = ready
    for s, f in busy:
        if t + duration <= s:
            return t
        t = max(t, f)
    return t


class Problem:
    """Cost matrix + incremental plan; shared by HEFT, PEFT and the tests."""

    def __init__(self, dag, state, cost, comm=None) -> None:
        self.dag = dag
        self.comm = comm or (lambda parent, child: 0.0)
        self.workers = state.worker_ids()
        self.elig = {tid: eligible_workers(t, state) for tid, t in dag.tasks.items()}
        for tid, e in self.elig.items():
            if not e:
                raise ValueError(f"no eligible worker for task {tid!r}")
        pool_cost: dict[tuple[str, str], float] = {}
        self.w: dict[str, dict[str, float]] = {}
        for tid, t in dag.tasks.items():
            row = {}
            for wid in self.elig[tid]:
                pool = state.pool_of(wid)
                if (tid, pool) not in pool_cost:
                    pool_cost[(tid, pool)] = float(cost(t, pool))
                row[wid] = pool_cost[(tid, pool)]
            self.w[tid] = row
        self.topo_idx = {tid: i for i, tid in enumerate(dag.topological_order())}
        self.busy: dict[str, list[tuple[float, float]]] = {wid: [] for wid in self.workers}
        self.plan = Plan({}, {}, {}, [], {})

    def edge(self, parent: str, child: str) -> float:
        return self.comm(self.dag.tasks[parent], self.dag.tasks[child])

    def wbar(self, tid: str) -> float:
        return statistics.fmean(self.w[tid].values())

    def eft(self, tid: str, wid: str) -> tuple[float, float]:
        """(EST, EFT) of ``tid`` on ``wid`` given the tasks planned so far."""
        p = self.plan
        ready = max((p.finish[m] + (0.0 if p.assign[m] == wid else self.edge(m, tid))
                     for m in self.dag.tasks[tid].dependencies), default=0.0)
        est = earliest_slot(self.busy[wid], ready, self.w[tid][wid])
        return est, est + self.w[tid][wid]

    def place(self, tid: str, wid: str) -> None:
        est, eft = self.eft(tid, wid)
        p = self.plan
        p.assign[tid], p.start[tid], p.finish[tid] = wid, est, eft
        p.order.append(tid)
        self.busy[wid].append((est, eft))
        self.busy[wid].sort()


def upward_rank(prob: Problem) -> dict[str, float]:
    rank: dict[str, float] = {}
    for tid in reversed(prob.dag.topological_order()):
        rank[tid] = prob.wbar(tid) + max((prob.edge(tid, c) + rank[c] for c in prob.dag.dependents(tid)), default=0.0)
    return rank


def heft_plan(dag, state, cost, comm=None) -> Plan:
    prob = Problem(dag, state, cost, comm)
    prob.plan.rank = rank = upward_rank(prob)
    for tid in sorted(dag.tasks, key=lambda t: (-rank[t], prob.topo_idx[t])):  # ties: topological order
        prob.place(tid, min(prob.elig[tid], key=lambda wid: prob.eft(tid, wid)[1]))  # min() keeps first on ties
    return prob.plan


class StaticPlanScheduler(SchedulerPolicy):
    """Runs a precomputed plan (``make_plan``) with early binding."""

    binds_only_idle = False

    def __init__(self, estimator: ExecutionTimeEstimator, name: str, comm=None):
        self.estimator = estimator
        self.name = name
        self.comm = comm
        self.plan: Plan | None = None

    def make_plan(self, dag, state) -> Plan:
        raise NotImplementedError

    def _cost(self, task, pool: str) -> float:
        return self.estimator.estimate(task, pool, None)  # idle-machine cost: use E1 (a profile)

    def on_run_start(self, dag, state) -> None:
        self.estimator.reset()
        self.plan = self.make_plan(dag, state)

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        plan = self.plan
        assert plan is not None  # set by on_run_start
        return sorted(ready_ids, key=lambda t: (plan.start[t], -plan.rank[t]))

    def select_worker(self, task, state) -> str | None:
        assert self.plan is not None  # set by on_run_start
        wid = self.plan.assign[task.task_id]
        if wid not in eligible_workers(task, state):
            raise ValueError(f"{self.name}: planned worker {wid!r} is not eligible for {task.task_id!r}")
        self.last_decision = {
            "policy": self.name, "chosen": wid, "ctx_version": 2, "model": "plan",
            "planned_start": self.plan.start[task.task_id], "planned_finish": self.plan.finish[task.task_id],
            "plan_makespan": self.plan.makespan,
            # decision-time occupancy for the dataset builder (the plan itself is occupancy-blind)
            "candidates": {wid: {"ctx": EstimateContext.from_state(state, wid).to_dict()}},
        }
        return wid

    def describe(self) -> dict:
        return {**super().describe(), "estimator": self.estimator.describe(), "plan": "static"}


class HeftScheduler(StaticPlanScheduler):
    def make_plan(self, dag, state) -> Plan:
        return heft_plan(dag, state, self._cost, self.comm)
