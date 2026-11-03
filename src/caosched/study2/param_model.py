"""Study 2: a generic learned runtime model that reads the task's own parameters (protocol section 21).

For every (workload, pool) group: kernel seconds = a + sum_i b_i * x_i by ridge least squares, where x are the NUMERIC entries of
``task.params`` plus ``size`` (the task's size in pixels) that actually vary in the training logs (``seed``, ``width``, ``height`` are
never features), and, when two or more features vary, all their pairwise PRODUCTS (cost often scales as size x repeats; a purely
additive plane cannot represent that). Which features exist is decided from the data, not typed in: a stage whose inputs never vary
(source, edges, features, aggregate in the hidden-cost workload) gets the group mean, a stage with one varying input gets a line, with two
a plane plus their product. Columns are standardised before the solve (sizes are about 1e6, repeat counts about 1e2, their product
about 1e8), the coefficients are returned in raw units. Nothing in the model names a stage or a parameter, so a new workload or a new
pool (a Raspberry Pi) is retrained by one command (``scripts/study2_train_param_model.py``) from the logs of a coverage session; no
code change. Model files written before ``size`` and products existed (features without ``*`` and without ``size``) load and predict
exactly as before.

Decision-time safe (parameters are known when the task is ready); no silent fallback: an unseen (workload, pool) raises ``KeyError``.
Inference is a dot product of a few numbers (microseconds), so the model adds no scheduling cost.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator

IGNORED_PARAMS = frozenset({"seed", "width", "height", "device", "timeout_s"})
MIN_SECONDS = 1e-6


def base_names(param_rows: list[dict]) -> list[str]:
    """Numeric inputs (``size`` included, IGNORED_PARAMS excluded) that take at least two distinct values in ``param_rows``."""
    seen: dict[str, set] = {}
    for p in param_rows:
        for k, v in (p or {}).items():
            if k not in IGNORED_PARAMS and isinstance(v, (int, float)) and not isinstance(v, bool):
                seen.setdefault(k, set()).add(float(v))
    return sorted(k for k, vals in seen.items() if len(vals) >= 2)


def feature_names(param_rows: list[dict]) -> list[str]:
    """Base inputs plus all pairwise products ``a*b`` (only when two or more inputs vary)."""
    base = base_names(param_rows)
    return base + [f"{a}*{b}" for i, a in enumerate(base) for b in base[i + 1:]]


def column(p: dict, name: str) -> float:
    if "*" in name:
        a, b = name.split("*")
        return float((p or {}).get(a, 0.0)) * float((p or {}).get(b, 0.0))
    return float((p or {}).get(name, 0.0))


def fit_group(param_rows: list[dict], y: list[float], ridge: float = 1e-9) -> dict:
    names = feature_names(param_rows)
    F = np.array([[column(p, k) for k in names] for p in param_rows]).reshape(len(param_rows), len(names))
    mean, scale = F.mean(axis=0), F.std(axis=0)
    scale[scale == 0] = 1.0
    Z = np.hstack([np.ones((len(y), 1)), (F - mean) / scale])
    # ridge as extra rows: sqrt(ridge * n) on every non-intercept column; solved by lstsq (no normal equations, no squared conditioning)
    pen = np.hstack([np.zeros((len(names), 1)), np.sqrt(ridge * len(y)) * np.eye(len(names))])
    zc, *_ = np.linalg.lstsq(np.vstack([Z, pen]), np.concatenate([np.array(y, float), np.zeros(len(names))]), rcond=None)
    b = zc[1:] / scale                                     # back to raw units: y = a + sum b_i x_i
    a = zc[0] - float(np.dot(b, mean))
    coef = np.concatenate([[a], b])
    resid = np.hstack([np.ones((len(y), 1)), F]) @ coef - np.array(y)
    return {"features": names, "coef": [float(c) for c in coef], "n": len(y), "mae_s": float(np.mean(np.abs(resid)))}


def fit_group_log_power(param_rows: list[dict], y: list[float]) -> dict:
    """Power-law form (revival): log(time) = a + sum b_i log(x_i) over the inputs that vary (``base_names``); the prediction is
    exp(...). Fixes the large relative error of the additive form on the cheapest tasks (cost ranging over two orders of magnitude).
    Stored with ``"form": "log_power"``; a group without ``form`` is the additive model above, so old model files load unchanged."""
    names = base_names(param_rows)
    X = np.array([[math.log(max(column(p, n), 1.0)) for n in names] for p in param_rows]).reshape(len(param_rows), len(names))
    Z = np.hstack([np.ones((len(y), 1)), X])
    coef, *_ = np.linalg.lstsq(Z, np.log(np.maximum(np.array(y, float), MIN_SECONDS)), rcond=None)
    pred = np.exp(Z @ coef)
    return {"form": "log_power", "features": names, "coef": [float(c) for c in coef], "n": len(y),
            "mae_s": float(np.mean(np.abs(pred - np.array(y))))}


def predict_group(g: dict, p: dict) -> float:
    if g.get("form") == "log_power":
        return max(MIN_SECONDS, math.exp(g["coef"][0] + sum(c * math.log(max(column(p, k), 1.0)) for c, k in zip(g["coef"][1:], g["features"]))))
    return max(MIN_SECONDS, float(np.dot(g["coef"], [1.0] + [column(p, k) for k in g["features"]])))


class ParamModelEstimator(ExecutionTimeEstimator):
    name = "ParamModel"

    def __init__(self, groups: dict[str, dict], source: str | None = None):
        self.groups, self.source = groups, source

    @classmethod
    def load(cls, path: Path) -> "ParamModelEstimator":
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["groups"], str(path))

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        g = self.groups.get(f"{task.est_workload}|{pool}")
        if g is None:
            raise KeyError(f"ParamModel has no group for ({task.est_workload!r}, pool {pool!r}); retrain with a coverage session "
                           f"that ran this stage on this pool")
        return predict_group(g, {**(task.params or {}), "size": task.size})

    def describe(self) -> dict:
        return {"name": self.name, "source": self.source, "n_groups": len(self.groups),
                "features": {k: v["features"] for k, v in sorted(self.groups.items()) if v["features"]}}
