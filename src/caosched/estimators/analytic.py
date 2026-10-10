"""E2: analytic size-based model.

    t(workload, size, pool) = a[workload, pool] * size ** b[workload]

``b`` is the workload's asymptotic complexity exponent in the units of its
``size`` parameter, taken from config (defaults: matmul N -> N^3,
image_filter side length -> side^2 i.e. linear in pixels, compression bytes
-> linear). ``a`` is fitted per (workload, pool) on solo profile
measurements as the geometric mean of t / size^b (least squares in log
space). With ``fit_exponent=True`` b is instead fitted per workload by
log-log least squares (needs >= 2 distinct sizes).

Unlike E1, E2 answers for sizes that were never profiled -- that is the
point of the rung, and its size-extrapolation error is measured in Phase 3.
"""
from __future__ import annotations

import math

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator
from caosched.estimators.profile_data import load_profile_rows

DEFAULT_EXPONENTS = {"matmul": 3.0, "image_filter": 2.0, "compression": 1.0}


class AnalyticSizeEstimator(ExecutionTimeEstimator):
    name = "E2_analytic"

    def __init__(self, coef: dict[tuple[str, str], float], exponents: dict[str, float], source: str | None = None,
                 fitted_exponent: bool = False):
        self.coef = dict(coef)
        self.exponents = dict(exponents)
        self.source = source
        self.fitted_exponent = fitted_exponent

    @classmethod
    def fit(cls, rows: list[dict], exponents: dict[str, float] | None = None, fit_exponent: bool = False,
            source: str | None = None) -> "AnalyticSizeEstimator":
        exps = dict(DEFAULT_EXPONENTS if exponents is None else exponents)
        if fit_exponent:
            for wl in {r["workload"] for r in rows}:
                pts = [(math.log(r["size"]), math.log(r["kernel_s"])) for r in rows if r["workload"] == wl]
                if len({x for x, _ in pts}) < 2:
                    raise ValueError(f"E2 fit_exponent needs >= 2 sizes for {wl!r}")
                mx = sum(x for x, _ in pts) / len(pts)
                my = sum(y for _, y in pts) / len(pts)
                exps[wl] = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
        logs: dict[tuple[str, str], list[float]] = {}
        for r in rows:
            b = exps[r["workload"]]
            logs.setdefault((r["workload"], r["pool"]), []).append(math.log(r["kernel_s"]) - b * math.log(r["size"]))
        coef = {k: math.exp(sum(v) / len(v)) for k, v in logs.items()}
        return cls(coef, exps, source, fitted_exponent=fit_exponent)

    @classmethod
    def from_profile(cls, profile_path, exponents=None, fit_exponent=False) -> "AnalyticSizeEstimator":
        return cls.fit(load_profile_rows(profile_path), exponents, fit_exponent, source=str(profile_path))

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        key = (task.workload, pool)
        if key not in self.coef:
            raise KeyError(f"E2 has no coefficient for {key}")
        return self.coef[key] * float(task.size) ** self.exponents[task.workload]

    def describe(self) -> dict:
        return {"name": self.name, "source": self.source, "exponents": self.exponents,
                "fitted_exponent": self.fitted_exponent,
                "coef": {f"{w}|{p}": v for (w, p), v in sorted(self.coef.items())}}
