"""E3: moving historical execution-time estimate.

Per (workload, size, pool) key, the estimate is the mean of the last
``window`` observed kernel times *in the current run*. Before a key has any
observation, the estimate falls back to a ``prior`` estimator (by default
E1's static profile) -- documented cold-start behaviour, so B7 starts out
identical to B6 and diverges only as real observations (which include
co-running interference, unlike the solo-measured profile) accumulate.
"""
from __future__ import annotations

import collections

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator, estimate_key


class MovingHistoryEstimator(ExecutionTimeEstimator):
    name = "E3_moving_history"

    def __init__(self, prior: ExecutionTimeEstimator, window: int = 8):
        if window < 1:
            raise ValueError("window must be >= 1")
        self.prior = prior
        self.window = window
        self._hist: dict[tuple, collections.deque] = {}

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        h = self._hist.get(estimate_key(task.est_workload, task.est_size, pool))
        if h:
            return sum(h) / len(h)
        return self.prior.estimate(task, pool, ctx)

    def observe(self, task, pool: str, kernel_seconds: float, ctx: EstimateContext | None = None) -> None:
        if kernel_seconds is None or kernel_seconds <= 0:
            return
        key = estimate_key(task.est_workload, task.est_size, pool)
        self._hist.setdefault(key, collections.deque(maxlen=self.window)).append(kernel_seconds)

    def n_observations(self, task, pool: str) -> int:
        return len(self._hist.get(estimate_key(task.est_workload, task.est_size, pool), ()))

    def reset(self) -> None:
        self._hist.clear()
        self.prior.reset()

    def describe(self) -> dict:
        return {"name": self.name, "window": self.window, "prior": self.prior.describe()}
