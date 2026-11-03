"""Study 2 policy: earliest finish time with LATE binding.

Why (EVALUATION_PROTOCOL_study2.md amendment A4): in pilots 2 and 3 every EFT variant, with kernel-only or end-to-end estimates,
trailed the non-predictive greedy rule B4 (late binding: a task goes to an idle worker, never to a queue) by 2% to 4%. Stage 5
already isolated the cost of early binding on Montage (``B0_P_early``, +1.7%). ``LateEftScheduler`` keeps the prediction but moves
the commitment to the moment a worker is free:

  for a ready task, compute F(t, w) = wait(w) + transfer + exec for EVERY eligible worker, exactly as ``EarliestFinishTimeScheduler``
  (same estimator, same decision-time context, same logging); if the argmin worker is idle, bind to it now; if it is busy, HOLD the
  task in the global ready queue (return None). The coordinator runs another dispatch pass on every completion, so a held task is
  placed as soon as its predicted-best worker frees up or another worker becomes the predicted-best.

So a task waits for a busy fast worker only when the model says that finishes it earlier than starting now on an idle slow one.
Nothing in the coordinator, the base EFT or the estimators is changed; ``binds_only_idle = True`` makes the coordinator enforce
that no task is ever queued behind a busy worker.
"""
from __future__ import annotations

import statistics

from caosched.core.task import Task
from caosched.estimators.oracle import ReplayOracleEstimator, _key
from caosched.core.scheduler_base import eligible_workers
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.rank_eft import RankEftScheduler
from caosched.schedulers.simple import GreedyEligibleScheduler


class EftNoContext(EarliestFinishTimeScheduler):
    """The unchanged EFT, with the decision-context logging switched off (``log_context=False``; the base default is on).

    Decisions are identical for estimators that do not read the context (E1, E1+rc, E1 end-to-end): the context only fed the dataset
    builder of stage 3. It costs scheduling time that grows with the workers' activity history (``RuntimeState.busy_fraction`` walks up
    to 256 intervals per worker for each of the 14 candidates), and a LATE policy re-evaluates every held task on every dispatch pass:
    pilot 4 measured 32 s of scheduling time in a 1.8 s workload (amendment A5). Study 2 has no learned model, so nothing needs it."""

    def __init__(self, estimator, name: str, e2e=None, transfer=None, allowed_pools: list[str] | None = None,
                 log_context: bool = False, legacy_wait_context: bool = False):
        super().__init__(estimator, name, e2e, transfer, allowed_pools, log_context, legacy_wait_context)


class LateEftScheduler(EftNoContext):
    binds_only_idle = True

    def select_worker(self, task: Task, state) -> str | None:
        best = super().select_worker(task, state)
        if best is not None and state.is_idle(best):
            return best
        self._decision_ctx.pop(task.task_id, None)  # held: no decision was taken, nothing for ``observe`` to wait for
        self.last_decision = None
        return None

    def describe(self) -> dict:
        return {**super().describe(), "binding": "late (hold for a busy predicted-best worker)"}


class CachedOracle(ReplayOracleEstimator):
    """``ReplayOracleEstimator`` with the per-key medians computed once. Same numbers, constant-time lookup: the original takes a
    median over every logged observation (about 250 per key) on every call, which cost 1.3 s of scheduling time in a 1.8 s run
    (oracle session 1, amendment A7). ``exclude_run`` is not supported (study 2 never uses it)."""

    @classmethod
    def from_rows(cls, rows: list[dict]) -> "CachedOracle":
        return cls(ReplayOracleEstimator.from_rows(rows).obs)

    def __init__(self, observations):
        super().__init__(observations)
        self._median = {k: statistics.median(v for _, v in vals) for k, vals in observations.items()}

    def estimate(self, task, pool: str, ctx=None) -> float:
        try:
            return self._median[_key(task, pool)]
        except KeyError:
            raise KeyError(f"E5 has no observation of {_key(task, pool)}") from None


class RankEftNoContext(RankEftScheduler):
    """``RankEftScheduler`` (EFT with the ready queue ordered by upward rank) without decision-context logging (see ``EftNoContext``)."""

    def __init__(self, estimator, name: str, e2e=None, transfer=None, allowed_pools: list[str] | None = None,
                 log_context: bool = False, legacy_wait_context: bool = False):
        super().__init__(estimator, name, e2e, transfer, allowed_pools, log_context, legacy_wait_context)


class LargestFirstGreedy(GreedyEligibleScheduler):
    """B4 (first idle eligible worker, priority order) with the ready queue ordered by task size, largest first.

    NON-predictive: the size (pixels) is known when a task is ready; no time model. This is the simple size heuristic a prediction
    scheduler has to beat on a heavy-tailed workload (protocol section 17). Stable sort: FIFO among equal sizes."""

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        return sorted(ready_ids, key=lambda t: -state.dag.tasks[t].size)


class PredictedRankGreedy(RankEftNoContext):
    """Predicted ORDER, work-conserving PLACEMENT (protocol sections 21 and 22).

    The ready queue is ordered by upward rank (HEFT's rank_u from the estimator's predicted times: longest remaining chain first), as
    ``RankEftScheduler`` does. Placement is LATE: a task is bound only to an IDLE eligible worker, the one with the smallest predicted
    time, so no worker idles while a ready task exists and no task waits in a local queue (the two losses measured before: early
    binding, B0_P_early +1.7% in stage 5, and starvation, pilot 5).

    ``hold_min_s`` (None = never hold): a task is HELD (``None``) when the predicted finish on the best BUSY worker (its predicted
    remaining time plus the task's time there) beats the best idle worker's time by more than ``hold_min_s`` seconds: a bounded version
    of EFT's wait-for-the-fast-worker decision, never for a gain below the measured per-task I/O and message cost.

    Cost (amendment A11): the first version re-estimated the remaining time of every busy worker for every held task on every dispatch
    pass and spent 46% of a run deciding (the cost guard flagged all 15 runs). Now the predicted free time of each POOL's soonest-free
    busy worker is computed ONCE per pass in ``order_ready`` (the coordinator calls it before every pass), so each
    ``select_worker`` is a few dictionary lookups. Approximation, stated: workers bound during the same pass are not added to that cache."""

    binds_only_idle = True

    def __init__(self, estimator, name: str, hold_min_s: float | None = None, **kw):
        super().__init__(estimator, name, **kw)
        self.hold_min_s = hold_min_s
        self._free_in: dict[str, float] = {}

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        if self.hold_min_s is not None:  # soonest predicted free time per pool, once per dispatch pass
            now = state.now()
            free_in: dict[str, float] = {}
            for w in state.workers.values():
                if w.busy:
                    t = self._wait(w, state, now, None)
                    if t < free_in.get(w.pool, float("inf")):
                        free_in[w.pool] = t
            self._free_in = free_in
        return super().order_ready(ready_ids, state)

    def select_worker(self, task: Task, state) -> str | None:
        idle = eligible_workers(task, state, idle_only=True)
        if not idle:
            return None
        t_idle, best = min((self._exec(task, state.pool_of(w), None), w) for w in idle)
        if self.hold_min_s is not None and t_idle > self.hold_min_s:  # a task cheaper than the margin cannot gain more than it
            pools = {state.pool_of(w) for w in eligible_workers(task, state)}
            t_busy = min((self._free_in[p] + self._exec(task, p, None) for p in pools if p in self._free_in), default=None)
            if t_busy is not None and t_idle - t_busy > self.hold_min_s:
                return None
        self.last_decision = {"policy": self.name, "chosen": best, "predicted_s": t_idle, "model": "kernel"}
        return best

    def describe(self) -> dict:
        return {**super().describe(), "binding": "late, predicted rank order", "hold_min_s": self.hold_min_s}
