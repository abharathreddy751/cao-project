"""E5: replay oracle -- OFFLINE / REPLAY ANALYSIS ONLY.

A true oracle would know the exact kernel time a task *will* take on every
candidate pool under the occupancy it *will* meet. That counterfactual is
not observable. E5 is the closest defensible stand-in: the kernel time the
*same task* (same trace task id, input seed, workload, size) actually took
on that pool in other logged runs of the same trace (median over runs).

* ``exclude_run(run_id)`` drops one run's own observations, so evaluating
  E5 on run R never uses R's measurements (leave-run-out).
* Missing (task, pool) -> KeyError: E5 never guesses.
* It must never be used by an online policy as if it were available; the
  oracle policy O (Phase 4/7) is a replay-analysis reference point.
"""
from __future__ import annotations

import statistics

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator


def _key(task, pool: str) -> tuple:
    return (task.task_id, int(task.seed), task.workload, int(task.size), pool)


class ReplayOracleEstimator(ExecutionTimeEstimator):
    name = "E5_replay_oracle"

    def __init__(self, observations: dict[tuple, list[tuple[str, float]]]):
        self.obs = observations
        self._excluded: str | None = None

    @classmethod
    def from_rows(cls, rows: list[dict]) -> "ReplayOracleEstimator":
        """``rows``: dicts with run_id, task_id, seed, workload, size, pool, kernel_s."""
        obs: dict[tuple, list[tuple[str, float]]] = {}
        for r in rows:
            k = (r["task_id"], int(r["seed"]), r["workload"], int(r["size"]), r["pool"])
            obs.setdefault(k, []).append((r["run_id"], r["kernel_s"]))
        return cls(obs)

    def add(self, run_id: str, task_id: str, seed: int, workload: str, size: int, pool: str,
            kernel_s: float) -> None:
        """Append one observation (memory-lean incremental construction;
        equivalent to from_rows over the same rows)."""
        self.obs.setdefault((task_id, int(seed), workload, int(size), pool), []).append((run_id, kernel_s))

    def exclude_run(self, run_id: str | None) -> None:
        self._excluded = run_id

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        vals = [v for rid, v in self.obs.get(_key(task, pool), ()) if rid != self._excluded]
        if not vals:
            raise KeyError(f"E5 has no observation of {_key(task, pool)} outside run {self._excluded!r}")
        return statistics.median(vals)

    def describe(self) -> dict:
        return {"name": self.name, "n_keys": len(self.obs), "excluded_run": self._excluded,
                "note": "offline/replay analysis only"}
