"""Offline schedule-aware oracle for the revival oracle gate (an upper-bound REFERENCE, never a deployable scheduler).

``ScheduleOracleRankGreedy`` is the revival policy with perfect knowledge of the two things a deployable policy has to estimate:

* the isolated cost of every task on every pool (an E5 replay estimator over logged isolated runs: ``study2.policies.CachedOracle``);
* the contention schedule itself (which core is shared with how many spinners in which window) and the measured slowdown per spinner
  count, from which it computes the exact wall time a task would need on a given worker starting now.

It obeys the SAME constraints as the deployable policies: eligibility, late binding to an idle worker, rank ordering, no deliberate
waiting. Any headroom it shows over the best simple rule is therefore attributable to information, not to a looser rule.
"""
from __future__ import annotations

from caosched.core.task import Task
from caosched.revival.contention import ContentionSchedule
from caosched.revival.cost import CostBreakdown
from caosched.revival.policy import ResourceStateAwareRankGreedy


class ScheduleOracleRankGreedy(ResourceStateAwareRankGreedy):
    def __init__(self, estimator, name: str, *, schedule: ContentionSchedule | None, core_of: dict[str, int],
                 slowdown: dict[int, float], min_affected_s: float = 0.03, **kw):
        kw.setdefault("cost_gate", False)
        super().__init__(estimator, name, live_state=False, **kw)
        self.schedule, self.core_of, self.slowdown, self.min_affected_s = schedule, core_of, slowdown, min_affected_s
        self.t0: float | None = None  # clock.now() instant the contention schedule's time 0 corresponds to (set by the adapter)

    def cost_of(self, task: Task, wid: str, state, snap) -> CostBreakdown:
        pool = state.pool_of(wid)
        base = self._base_time(task, pool)
        core = self.core_of.get(wid)
        if self.schedule is None or self.t0 is None or core is None:
            return CostBreakdown(base)
        dur = self.schedule.duration_for(core, snap.t - self.t0, base, self.slowdown, self.min_affected_s)
        return CostBreakdown(base, dur - base)

    def _total(self, task: Task, wid: str, state, snap) -> float:
        return self.cost_of(task, wid, state, snap).total_s

    def describe(self) -> dict:
        return {**super().describe(), "oracle": "isolated task times (E5) + contention schedule; offline upper bound, not deployable"}
