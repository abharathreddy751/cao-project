"""E0: constant execution profile per (task type, resource pool).

One number per (workload, pool): the median of every non-warmup solo
measurement of that workload on that pool in the static-profile raw CSV,
pooled over all profiled sizes. Deliberately ignores task size -- it is the
"knows only what kind of task and which core type" rung of the ladder.
"""
from __future__ import annotations

import statistics

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator
from caosched.estimators.profile_data import load_profile_rows


class ConstantProfileEstimator(ExecutionTimeEstimator):
    name = "E0_constant"

    def __init__(self, table: dict[tuple[str, str], float], source: str | None = None):
        if not table:
            raise ValueError("Empty E0 table")
        self.table = dict(table)
        self.source = source

    @classmethod
    def fit(cls, rows: list[dict], source: str | None = None) -> "ConstantProfileEstimator":
        groups: dict[tuple[str, str], list[float]] = {}
        for r in rows:
            groups.setdefault((r["workload"], r["pool"]), []).append(r["kernel_s"])
        return cls({k: statistics.median(v) for k, v in groups.items()}, source)

    @classmethod
    def from_profile(cls, profile_path) -> "ConstantProfileEstimator":
        return cls.fit(load_profile_rows(profile_path), source=str(profile_path))

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        key = (task.est_workload, pool)
        if key not in self.table:
            raise KeyError(f"E0 has no entry for {key}")
        return self.table[key]

    def describe(self) -> dict:
        return {"name": self.name, "source": self.source,
                "table_s": {f"{w}|{p}": v for (w, p), v in sorted(self.table.items())}}
