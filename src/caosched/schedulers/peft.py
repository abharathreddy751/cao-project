"""PEFT: Predict Earliest Finish Time with an Optimistic Cost Table.

STATUS OF THE DEFINITION: written from the standard formulation in secondary
sources (Arabnejad and Barbosa, IEEE TPDS 2014); the original paper has NOT
been read, so tie-breaking and details are unverified. Formulas used:

    OCT(i,p)   = max over successors j of  min over processors q of
                 ( OCT(j,q) + w(j,q) + cbar(i,j) * [q != p] )      (exit task: 0)
    rank_oct(i)= mean over the processors that may run i of OCT(i,p)
    schedule: among READY tasks (all predecessors already placed) take the one
    with the highest rank_oct; place it on the processor minimising
        O_EFT(i,p) = EFT(i,p) + OCT(i,p)
    where EFT uses the same insertion-based slot search as HEFT.

The processor sets are restricted to ``eligible_workers`` (uniform eligibility,
D3): ``q`` ranges over the workers that may run ``j``. Ties: task order is
topological index, processor order is worker order (first wins). Like HEFT it is
a static PLAN method needing a profile cost matrix (estimator E1); see heft.py.
"""
from __future__ import annotations

import statistics

from caosched.schedulers.heft import Plan, Problem, StaticPlanScheduler


def optimistic_cost_table(prob: Problem) -> dict[str, dict[str, float]]:
    oct_: dict[str, dict[str, float]] = {}
    for tid in reversed(prob.dag.topological_order()):
        succ = prob.dag.dependents(tid)
        oct_[tid] = {
            p: max((min(oct_[j][q] + prob.w[j][q] + (prob.edge(tid, j) if q != p else 0.0) for q in prob.elig[j])
                    for j in succ), default=0.0)
            for p in prob.workers}
    return oct_


def peft_plan(dag, state, cost, comm=None) -> Plan:
    prob = Problem(dag, state, cost, comm)
    oct_ = optimistic_cost_table(prob)
    prob.plan.rank = rank = {t: statistics.fmean(oct_[t][p] for p in prob.elig[t]) for t in dag.tasks}
    waiting = {tid: len(t.dependencies) for tid, t in dag.tasks.items()}
    ready = [tid for tid, n in waiting.items() if n == 0]
    while ready:
        tid = min(ready, key=lambda t: (-rank[t], prob.topo_idx[t]))
        ready.remove(tid)
        prob.place(tid, min(prob.elig[tid], key=lambda p: prob.eft(tid, p)[1] + oct_[tid][p]))
        for c in dag.dependents(tid):
            waiting[c] -= 1
            if waiting[c] == 0:
                ready.append(c)
    return prob.plan


class PeftScheduler(StaticPlanScheduler):
    def make_plan(self, dag, state) -> Plan:
        return peft_plan(dag, state, self._cost, self.comm)
