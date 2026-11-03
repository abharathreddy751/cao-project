"""ResourceStateAwareRankGreedy: predicted-rank ordering, work-conserving placement, end-to-end cost with live resource state.

Unchanged from ``PredictedRankGreedy`` (study2/policies.py, kept as the baseline): the ready queue is ordered by HEFT upward rank
computed once per run from the estimator's idle-machine times; placement is LATE (only to an IDLE eligible worker, never a queue, never
a deliberate wait). What is added:

* cost of a candidate worker = ``CostBreakdown`` (compute x class-aware residual correction, load correction of THAT worker from the
  live state, measured setup/IPC, transfer), instead of the bare kernel estimate;
* a safe fallback to B4 (first idle eligible worker, pool priority) with a logged reason: ``no_model_coverage`` (the estimator has no
  entry for a (stage, pool)), ``gain_below_cost`` (the predicted benefit over B4's choice is smaller than the measured cost of
  deciding), ``decision_budget`` (the policy's own decision latency exceeded its budget: permanent for the run);
* a compact decision record (``last_decision``, schema ``revival/1``): state snapshot, chosen worker, cost components, runner-up,
  fallback reason. The measured duration comes with the ``task_completed`` event of the same task id.

Ablations are constructor switches, not code forks: ``live_state`` False = task-feature-only (decisions equal ``PredictedRankGreedy``
when ``cost_gate`` is False); an estimator without task-parameter knowledge (baseline profile) with ``live_state`` True =
resource-state-only.
"""
from __future__ import annotations

import math

from caosched.core.scheduler_base import eligible_workers
from caosched.core.task import Task
from caosched.revival.cost import CostBreakdown
from caosched.revival.state import StateProvider, StateSnapshot
from caosched.study2.policies import RankEftNoContext
from caosched.util import clock

SCHEMA = "revival/1"


class ResourceStateAwareRankGreedy(RankEftNoContext):
    binds_only_idle = True

    def __init__(self, estimator, name: str, *, provider: StateProvider | None = None, live_state: bool = True, e2e=None, transfer=None,
                 priority: list[str] | None = None, cost_gate: bool = True, min_gain_s: float = 0.0, decision_budget_s: float = 0.002,
                 diagnostics: bool = False, **kw):
        super().__init__(estimator, name, e2e=e2e, transfer=transfer, **kw)
        self.live_state = live_state
        self.provider = provider if provider is not None else StateProvider(use_residual=live_state, use_foreign=live_state)
        self.priority = list(priority) if priority else None
        self.cost_gate, self.min_gain_s, self.decision_budget_s = cost_gate, min_gain_s, decision_budget_s
        self.diagnostics = diagnostics
        self._priority: list[str] = self.priority or ["P", "E"]
        self._reset_run()

    def _reset_run(self) -> None:
        self._snap: StateSnapshot | None = None
        self._base: dict[tuple[str, str], float] = {}
        self._pred: dict[str, float] = {}
        self._no_model = False
        self._over_budget = False
        self._lat = 0.0
        self._n_dec = 0
        self._pass_s = 0.0
        self.fallbacks: dict[str, int] = {}

    # --- run lifecycle ---------------------------------------------------------------------------------------------------

    def on_run_start(self, dag, state) -> None:
        self._reset_run()
        self.provider.reset()
        pools = state.pools()
        self._priority = self.priority or [p for p in ("P", "E") if p in pools] or pools
        try:
            super().on_run_start(dag, state)
        except KeyError:  # the estimator does not cover every (stage, pool): B4 order and placement for the whole run
            self._no_model = True
            self.rank = {}
            self._count("no_model_coverage")

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        t = clock.now()
        self._snap = None  # the state snapshot is taken lazily, once per pass, only if a decision has a real choice
        out = list(ready_ids) if self._no_model else super().order_ready(ready_ids, state)
        self._pass_s = (clock.now() - t) / max(1, len(ready_ids))
        return out

    def _snapshot(self, state) -> StateSnapshot:
        if self._snap is None:
            self._snap = self.provider.snapshot(state)
        return self._snap

    def on_task_completed(self, task: Task) -> None:
        super().on_task_completed(task)
        base = self._pred.pop(task.task_id, None)
        if base is not None and task.wall_time_seconds and task.assigned_worker and task.assigned_pool and task.t_completed:
            self.provider.observe(task.est_workload, task.assigned_worker, task.assigned_pool, base, task.wall_time_seconds,
                                  task.t_completed)

    # --- decision --------------------------------------------------------------------------------------------------------

    def _count(self, reason: str) -> None:
        self.fallbacks[reason] = self.fallbacks.get(reason, 0) + 1

    def _b4(self, idle: list[str], state) -> str:
        for pool in self._priority:
            for w in idle:
                if state.pool_of(w) == pool:
                    return w
        return idle[0]

    def _load_factor(self, wid: str, snap: StateSnapshot, state) -> float:
        """Slowdown of worker ``wid`` the cost model assumes (>= 1). Overridden by the schedule-aware oracle."""
        return snap.slowdown_of(wid) if self.live_state else 1.0

    def _bias(self, task: Task, pool: str, base: float) -> float:
        return self.provider.bias_of(task.est_workload, pool, base) if self.live_state else 1.0

    def _base_time(self, task: Task, pool: str) -> float:
        key = (task.task_id, pool)
        base = self._base.get(key)
        if base is None:
            base = self._base[key] = self._exec(task, pool, None)
        return base

    def _total(self, task: Task, wid: str, state, snap: StateSnapshot) -> float:
        """Predicted end-to-end occupation of ``wid`` by ``task`` in seconds: the hot-path form of ``cost_of(...).total_s``."""
        pool = state.pool_of(wid)
        base = self._base_time(task, pool)
        t = base * self._bias(task, pool, base) if self.live_state else base
        c = self._load_factor(wid, snap, state)
        if c != 1.0:
            t *= c
        if self.e2e is not None:
            try:
                t += self._extra(task, pool)
            except KeyError:
                pass
        if self.transfer is not None:
            t += self._transfer(task, pool)
        return t

    def cost_of(self, task: Task, wid: str, state, snap: StateSnapshot) -> CostBreakdown:
        """The same cost as ``_total``, split into its components (diagnostics, tests, logs)."""
        pool = state.pool_of(wid)
        base = self._base_time(task, pool)
        compute = base * self._bias(task, pool, base)
        load = compute * (self._load_factor(wid, snap, state) - 1.0)
        missing: list[str] = []
        setup = 0.0
        if self.e2e is not None:
            try:
                setup = self._extra(task, pool)
            except KeyError:
                missing.append("setup")
        return CostBreakdown(compute, load, setup, self._transfer(task, pool), tuple(missing))

    def select_worker(self, task: Task, state) -> str | None:
        idle = eligible_workers(task, state, idle_only=True)
        if not idle:
            return None
        t0 = clock.now()
        reason: str | None = None
        pred: float | None = None
        benefit = 0.0
        snap: StateSnapshot | None = None
        totals: dict[str, float] = {}
        b4 = chosen = idle[0] if len(idle) == 1 else self._b4(idle, state)  # one idle worker: the placement is forced
        if self._no_model:
            reason = "no_model_coverage"
        elif self._over_budget:
            reason = "decision_budget"
        elif len(idle) > 1:
            snap = self._snapshot(state)
            try:
                totals = {w: self._total(task, w, state, snap) for w in idle}
            except KeyError:
                reason = "no_model_coverage"
                totals = {}
            if totals:
                best = min(idle, key=totals.__getitem__)  # min keeps the first (pool priority order) on ties
                benefit = totals[b4] - totals[best]
                if self.cost_gate and benefit <= max(self.min_gain_s, self._lat):
                    reason = "gain_below_cost"
                else:
                    chosen = best
                pred = totals[chosen]
        pool = state.pool_of(chosen)
        if not self._no_model:
            try:
                self._pred[task.task_id] = self._base_time(task, pool)
            except KeyError:
                pass
        if reason:
            self._count(reason)
        dt = clock.now() - t0 + self._pass_s
        self._n_dec += 1
        self._lat = dt if self._n_dec == 1 else 0.9 * self._lat + 0.1 * dt
        if self._n_dec >= 30 and self._lat > self.decision_budget_s:
            self._over_budget = True
        d: dict = {"schema": SCHEMA, "chosen": chosen, "fallback": reason, "n_idle": len(idle)}
        if pred is not None:
            d["pred_s"] = round(pred, 6)
        if snap is not None:
            c = snap.slowdown.get(chosen)
            if c is not None:
                d["slowdown"] = round(c, 3)
        if self.diagnostics:  # opt-in: full cost components, B4's choice, the runner-up and the whole snapshot
            snap = self._snapshot(state)
            d.update(policy=self.name, pool=pool, b4=b4, benefit=round(benefit, 6), state=snap.to_log())
            if totals:
                d["cost"] = self.cost_of(task, chosen, state, snap).to_log()
                rest = sorted((totals[w], w) for w in idle if w != chosen)
                if rest:
                    d["runner_up"] = [rest[0][1], round(rest[0][0], 6)]
        self.last_decision = d
        return chosen

    def describe(self) -> dict:
        return {**super().describe(), "schema": SCHEMA, "live_state": self.live_state, "cost_gate": self.cost_gate,
                "decision_budget_s": self.decision_budget_s, "diagnostics": self.diagnostics, "binding": "late, predicted rank order, end-to-end state-aware cost"}


def decision_summary(policy: ResourceStateAwareRankGreedy) -> dict:
    return {"fallbacks": dict(policy.fallbacks), "mean_decision_latency_s": policy._lat,
            "over_budget": policy._over_budget, "no_model": policy._no_model, "finite": math.isfinite(policy._lat)}
