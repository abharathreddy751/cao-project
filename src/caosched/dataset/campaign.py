"""Randomized interference campaign: a DATA-COLLECTION policy, not a baseline.

Each campaign run draws a random concurrency level c in [c_min, c_max] and a
random subset of c workers (so P/E occupancy mixes vary run to run) and a
minimum idle gap g; a ready task goes to a uniformly random allowed worker
that has been idle for at least g since its last task (``retry_after`` makes
the coordinator wait otherwise). Varying g samples the candidate worker's
recent-activity feature (target_busy_frac), which back-to-back campaigns
cannot. Over many runs of random independent tasks this samples the
(busy_P, busy_E, co-running type, recent activity) space that E4 learns
from -- far more evenly than scheduling-policy runs, which mostly saturate
every worker.
"""
from __future__ import annotations

import random

from caosched.core.scheduler_base import SchedulerPolicy, eligible_workers
from caosched.estimators.base import EstimateContext


class RandomOccupancyPolicy(SchedulerPolicy):
    name = "campaign_random_occupancy"

    def __init__(self, seed: int, allowed_workers: list[str], min_idle_s: float = 0.0):
        if not allowed_workers:
            raise ValueError("need at least one allowed worker")
        self.rng = random.Random(seed)
        self.allowed = list(allowed_workers)
        self.seed = seed
        self.min_idle_s = float(min_idle_s)

    def _remaining_idle(self, state, wid: str) -> float:
        last = state.last_finished(wid)
        return 0.0 if last is None else max(0.0, self.min_idle_s - (state.now() - last))

    def on_run_start(self, dag, state) -> None:
        unknown = set(self.allowed) - set(state.worker_ids())
        if unknown:
            raise ValueError(f"unknown workers {sorted(unknown)}")
        for t in dag.tasks.values():  # fail now, not as a mid-run deadlock
            if not set(eligible_workers(t, state)) & set(self.allowed):
                raise ValueError(f"task {t.task_id!r} (eligible_pools={t.eligible_pools}) cannot be placed on any "
                                 f"allowed worker {self.allowed}")

    def select_worker(self, task, state) -> str | None:
        ok = set(eligible_workers(task, state, idle_only=True))  # per-task eligibility (AD-5)
        idle = [w for w in self.allowed if w in ok and self._remaining_idle(state, w) == 0.0]
        if not idle:
            return None
        pick = self.rng.choice(idle)
        # decision-time context (AD-7): the features the dataset builder uses, never start-time reconstruction
        self.last_decision = {"policy": self.name, "chosen": pick, "ctx_version": 2,
                              "candidates": {pick: {"ctx": EstimateContext.from_state(state, pick).to_dict()}}}
        return pick

    def retry_after(self, state) -> float | None:
        waits = [self._remaining_idle(state, w) for w in self.allowed if state.is_idle(w)]
        waits = [x for x in waits if x > 0.0]
        return min(waits) if waits else None

    def describe(self) -> dict:
        return {**super().describe(), "seed": self.seed, "allowed_workers": self.allowed,
                "min_idle_s": self.min_idle_s}
