"""Online recalibration wrapper ("+rc") for offline-fitted estimators.

Phase 3 found that estimators fitted offline (E1, E2, E4) carry a
session-level bias of up to ~30% on P-cores (P-core performance drifts
between sessions). Project decision (2026-10-03): correct it *online*
rather than by re-profiling.

    estimate = base.estimate(task, pool, ctx) * factor[pool]
    factor[pool] = exp(EWMA of log(actual_kernel / base_prediction))

The ratio for each completed task is taken against the base prediction
made with the *decision-time* context the task was actually scheduled under
(EFT passes it to ``observe``), so the correction learns the real
prediction error, not a re-evaluation with hindsight context.

* Scope: per run -- ``reset()`` (called by EFT at run start) clears the
  factors, so runs stay independent and replayable. Early decisions in a
  run are therefore uncorrected until ``min_obs`` completions per pool.
* One factor per pool (P, E): drift was found to be pool-level (P drifts,
  E is stable), and pooling across workloads lets the factor converge after
  a handful of completions instead of per-(workload, pool) dozens.
* The factor is clamped to [clamp_lo, clamp_hi] so a few outliers cannot
  run away.
* Do not wrap E3: it is already adaptive (its predictions change as it
  observes, so a ratio against it would be self-referential).
"""
from __future__ import annotations

import math

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator


class RecalibratedEstimator(ExecutionTimeEstimator):
    def __init__(self, base: ExecutionTimeEstimator, alpha: float = 0.2, min_obs: int = 1,
                 clamp: tuple[float, float] = (0.5, 3.0)):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self.base = base
        self.alpha = alpha
        self.min_obs = min_obs
        self.clamp = clamp
        self.name = f"{base.name}+rc"
        self.uses_context = base.uses_context
        self._log_factor: dict[str, float] = {}
        self._n: dict[str, int] = {}

    def factor(self, pool: str) -> float:
        if self._n.get(pool, 0) < self.min_obs:
            return 1.0
        lo, hi = self.clamp
        return min(hi, max(lo, math.exp(self._log_factor[pool])))

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        return self.base.estimate(task, pool, ctx) * self.factor(pool)

    def observe(self, task, pool: str, kernel_seconds: float, ctx: EstimateContext | None = None) -> None:
        if kernel_seconds is None or kernel_seconds <= 0:
            return
        self.base.observe(task, pool, kernel_seconds, ctx)
        r = math.log(kernel_seconds / self.base.estimate(task, pool, ctx))
        if pool in self._log_factor:
            self._log_factor[pool] += self.alpha * (r - self._log_factor[pool])
        else:
            self._log_factor[pool] = r
        self._n[pool] = self._n.get(pool, 0) + 1

    def calibration(self) -> dict:
        return {p: {"factor": self.factor(p), "n": self._n.get(p, 0)} for p in sorted(self._n)}

    def reset(self) -> None:
        self._log_factor.clear()
        self._n.clear()
        self.base.reset()

    def describe(self) -> dict:
        return {"name": self.name, "base": self.base.describe(), "alpha": self.alpha,
                "min_obs": self.min_obs, "clamp": list(self.clamp), "scope": "per run"}
