"""E4: learned interference-aware estimator.

Multiplicative correction of the solo static profile (E1) by the occupancy
the scheduler can see at decision time:

    t_hat = E1(workload, size, pool) * exp( w[workload, pool] . x(ctx) )
    x(ctx) = [1, busy_P, busy_E, corun_compression, corun_image_filter, corun_matmul,
              target_busy_frac]

where busy_* count *other* workers executing a task, corun_* count those
tasks by workload type, and target_busy_frac is the candidate worker's own
recent busy fraction (``EstimateContext``). The feature set is configurable:
``occupancy`` (first six) is kept as an ablation of ``occupancy+history``
(all seven); target_busy_frac was added after a Phase 3 diagnostic showed
P-cores running up to ~2-3x slower right after idling. An unknown
target_busy_frac (older logs) is imputed with the training mean, which is
stored in the model file. One ridge regression per
(workload, pool) group, fitted on y = log(observed kernel / E1); the
intercept is not penalised. A group with fewer than ``min_rows`` training
rows keeps all-zero weights (i.e. falls back to E1) and is reported as such.

Why this form: it is the smallest learned model that can represent "the same
task gets slower when more / which other tasks co-run", is interpretable
(each weight is a log-slowdown per co-running task), needs only numpy, and
lets the evaluation decide whether anything heavier is warranted (the brief:
do not force an ML model the data does not need). The brief's "calibration
execution time" feature is the E1 solo time the correction multiplies.
Not used (not observable at decision time in this runtime): available
memory, thermal/frequency state.

Training data: the randomized interference campaign (scripts/collect_campaign.py);
features are reconstructed from event logs with the same EstimateContext
definition used online (caosched.dataset.events).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from caosched.estimators.base import WORKLOADS, EstimateContext, ExecutionTimeEstimator
from caosched.estimators.profile import StaticProfileEstimator

FEATURES = ("intercept", "busy_P", "busy_E", *(f"corun_{w}" for w in WORKLOADS), "target_busy_frac")
FEATURE_SETS = {
    "occupancy": FEATURES[:-1],
    "occupancy+history": FEATURES,
}
MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models"
MAX_LOG_CORRECTION = math.log(10.0)  # clamp: never scale E1 by more than 10x either way


def feature_vector(ctx: EstimateContext | None, features=FEATURES, impute: dict | None = None) -> np.ndarray:
    ctx = ctx or EstimateContext()
    c = ctx.corun
    frac = ctx.target_busy_frac
    if frac is None:
        frac = (impute or {}).get("target_busy_frac", 1.0)
    full = {"intercept": 1.0, "busy_P": ctx.busy_P, "busy_E": ctx.busy_E,
            **{f"corun_{w}": c.get(w, 0) for w in WORKLOADS}, "target_busy_frac": frac}
    return np.array([full[f] for f in features], dtype=float)


class InterferenceRidgeEstimator(ExecutionTimeEstimator):
    name = "E4_interference_ridge"
    uses_context = True

    def __init__(self, base: StaticProfileEstimator, weights: dict[tuple[str, str], np.ndarray],
                 meta: dict | None = None, features=FEATURES):
        self.base = base
        self.weights = {k: np.asarray(v, dtype=float) for k, v in weights.items()}
        self.meta = meta or {}
        self.features = tuple(features)
        self.impute = self.meta.get("impute", {})

    # --- training ------------------------------------------------------

    @classmethod
    def fit(cls, rows: list[dict], base: StaticProfileEstimator, ridge_lambda: float = 1.0,
            min_rows: int = 30, meta: dict | None = None,
            features=FEATURES) -> "InterferenceRidgeEstimator":
        """``rows``: dicts with workload, size, pool, kernel_s, ctx (EstimateContext)."""
        features = tuple(features)
        known = [r["ctx"].target_busy_frac for r in rows if r["ctx"].target_busy_frac is not None]
        impute = {"target_busy_frac": float(np.mean(known)) if known else 1.0}
        groups: dict[tuple[str, str], list[dict]] = {}
        for r in rows:
            groups.setdefault((r["workload"], r["pool"]), []).append(r)
        weights, group_info = {}, {}
        penalty = np.eye(len(features)) * ridge_lambda
        penalty[0, 0] = 0.0
        for key, rs in sorted(groups.items()):
            if len(rs) < min_rows:
                weights[key] = np.zeros(len(features))
                group_info[f"{key[0]}|{key[1]}"] = {"n": len(rs), "fallback_to_E1": True}
                continue
            X = np.stack([feature_vector(r["ctx"], features, impute) for r in rs])
            y = np.array([math.log(r["kernel_s"] / base.lookup(r["workload"], r["size"], r["pool"])) for r in rs])
            w = np.linalg.solve(X.T @ X + penalty, X.T @ y)
            resid = y - X @ w
            weights[key] = w
            group_info[f"{key[0]}|{key[1]}"] = {"n": len(rs), "fallback_to_E1": False,
                                                "train_rmse_log": float(np.sqrt(np.mean(resid ** 2)))}
        m = {**(meta or {}), "ridge_lambda": ridge_lambda, "min_rows": min_rows, "groups": group_info,
             "impute": impute, "n_rows_busy_frac_unknown": len(rows) - len(known)}
        return cls(base, weights, m, features)

    # --- inference -----------------------------------------------------

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        base = self.base.lookup(task.workload, task.size, pool)
        w = self.weights.get((task.workload, pool))
        if w is None:
            return base
        corr = float(np.clip(w @ feature_vector(ctx, self.features, self.impute),
                             -MAX_LOG_CORRECTION, MAX_LOG_CORRECTION))
        return base * math.exp(corr)

    # --- persistence ---------------------------------------------------

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({
            "schema_version": 1, "estimator": self.name, "features": list(self.features),
            "base_profile": self.base.source,
            "weights": {f"{w}|{p}": v.tolist() for (w, p), v in sorted(self.weights.items())},
            "meta": self.meta,
        }, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, base: StaticProfileEstimator | None = None) -> "InterferenceRidgeEstimator":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if not d.get("features") or not set(d["features"]) <= set(FEATURES):
            raise ValueError(f"{path}: feature list does not match this code version")
        base = base or StaticProfileEstimator.from_file(d["base_profile"])
        weights = {tuple(k.split("|")): np.array(v) for k, v in d["weights"].items()}
        return cls(base, weights, {**d["meta"], "model_path": str(path)}, d["features"])

    def describe(self) -> dict:
        return {"name": self.name, "base": self.base.describe(), "features": list(self.features),
                "weights": {f"{w}|{p}": [round(x, 5) for x in v] for (w, p), v in sorted(self.weights.items())},
                "model_path": self.meta.get("model_path")}


def latest_model_path(directory: Path = MODEL_DIR) -> Path:
    c = sorted(Path(directory).glob("e4_*.json"))
    if not c:
        raise FileNotFoundError(f"No e4_*.json in {directory}; run scripts/train_e4.py first")
    return c[-1]


class InterferenceRidgeFastEstimator(InterferenceRidgeEstimator):
    """E4f -- IMPLEMENTATION OPTIMIZATION / ABLATION of E4, not a new model.

    Same fitted weights, same features, same clamp, same predictions (checked
    by tests to ~1e-12 relative); only inference is cheaper: the per-group
    weights are pre-split into plain Python floats and the 6-7 term dot
    product is computed without building a dict and a numpy array per call
    (numpy's per-call overhead dominates for vectors this small). Introduced
    because Phase 4 measured E4 decisions at ~10-16x the cost of E1. The
    original ``InterferenceRidgeEstimator`` is kept unchanged for comparison.
    """

    name = "E4f_interference_ridge_fast"

    def __init__(self, base, weights, meta=None, features=FEATURES):
        super().__init__(base, weights, meta, features)
        self._fast = {k: [float(x) for x in v] for k, v in self.weights.items()}
        self._idx = {f: i for i, f in enumerate(self.features)}
        self._impute_frac = float(self.impute.get("target_busy_frac", 1.0))

    @classmethod
    def from_model(cls, model: InterferenceRidgeEstimator) -> "InterferenceRidgeFastEstimator":
        return cls(model.base, model.weights, {**model.meta}, model.features)

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        base = self.base.lookup(task.workload, task.size, pool)
        w = self._fast.get((task.workload, pool))
        if w is None:
            return base
        idx = self._idx
        acc = w[idx["intercept"]]
        if ctx is not None:
            acc += w[idx["busy_P"]] * ctx.busy_P + w[idx["busy_E"]] * ctx.busy_E
            for wl, n in ctx.corunning:
                j = idx.get("corun_" + wl)
                if j is not None:
                    acc += w[j] * n
            frac = ctx.target_busy_frac
        else:
            frac = None
        j = idx.get("target_busy_frac")
        if j is not None:
            acc += w[j] * (self._impute_frac if frac is None else frac)
        acc = min(MAX_LOG_CORRECTION, max(-MAX_LOG_CORRECTION, acc))
        return base * math.exp(acc)
