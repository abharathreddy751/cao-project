"""Stage 3 learned predictors: CatBoost and MLP, same shape as E4.

Both predict the LOG CORRECTION of the E1 base profile from decision-time
features, exactly like the E4 ridge:

    t_hat = E1(workload, size, pool) * exp( f(x) ),   |f| clamped to log 10
    y     = log(observed kernel / E1)                  (the training target)

so the base-profile binding rules of ``learned.py`` apply unchanged (the model
records ``base_profile`` and ``load`` refuses another one,
``BaseProfileMismatchError``). Target = per-task, per-device kernel time only
(AD-8); setup, transfer and queue wait are never in the target.

Features x (``encode``; one model for all workloads and pools, categories and
pool names are taken from the training data, an unseen category encodes as all
zeros): log E1 base time, log size, one-hot workload, one-hot pool, busy
workers per pool at the decision (``EstimateContext.busy_by_pool``, so any pool
incl. the remote one), co-running count per workload, target_busy_frac
(unknown -> training mean). Allowed-feature policy: EVALUATION_PROTOCOL
section 3; rows must come from decision-time contexts (dataset ``context_source``).
An unseen workload, or a pool with no training row as the executing pool, raises
``ValueError`` in ``encode`` (never a silent all-zero encoding); the training-row
count per pool is stored in the spec (``n_rows_by_pool``) and reported by the evaluation.

Known limitation (counterfactual pools): labels exist only for EXECUTED placements, while
EFT queries every eligible pool, so the fit is on the chosen pool only by design. A pool
that was never executed has no label and raises; for a rarely executed pool the model
leans on the E1 base profile and the log-correction form (the correction is ~0 without
evidence), and data collection with ``RandomOccupancyPolicy`` / random placement exists so
that every pool is executed under varied occupancy.

* ``CatBoostEstimator``: gradient-boosted trees, hyper-parameters passed in
  (nothing is hard-coded here), single thread, fixed ``random_seed``.
* ``MlpEstimator``: small ReLU MLP trained with torch (CPU, ``manual_seed``,
  single thread, seeded shuffling); the weights are exported to plain arrays
  and INFERENCE RUNS IN NUMPY (CPU, no torch import, no pickle): same maths,
  and the per-call cost of a tiny network is below torch's call overhead.

Files: one JSON per model (CatBoost model embedded as base64 of its .cbm).
Not implemented by decision: TabM (entry rule not met until a pilot).
"""
from __future__ import annotations

import base64
import json
import math
import os
import tempfile
from pathlib import Path

import numpy as np

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator
from caosched.estimators.learned import MAX_LOG_CORRECTION, resolve_base_profile
from caosched.estimators.profile import StaticProfileEstimator

SCHEMA_VERSION = 1


def make_spec(rows: list[dict]) -> dict:
    """Feature layout from the training rows (dicts with workload, pool, ctx)."""
    known = [r["ctx"].target_busy_frac for r in rows if r["ctx"].target_busy_frac is not None]
    n_pool: dict[str, int] = {}
    for r in rows:
        n_pool[r["pool"]] = n_pool.get(r["pool"], 0) + 1
    return {"workloads": sorted({r["workload"] for r in rows}),
            "pools": sorted({r["pool"] for r in rows} | {p for r in rows for p in r["ctx"].busy_by_pool}),
            "n_rows_by_pool": dict(sorted(n_pool.items())),  # executing-pool rows; a busy-only pool has none
            "impute_frac": float(np.mean(known)) if known else 1.0}


def feature_names(spec: dict) -> list[str]:
    return (["log_base", "log_size"] + [f"wl_{w}" for w in spec["workloads"]] + [f"pool_{p}" for p in spec["pools"]]
            + [f"busy_{p}" for p in spec["pools"]] + [f"corun_{w}" for w in spec["workloads"]] + ["target_busy_frac"])


def encode(spec: dict, workload: str, size: int, pool: str, base_s: float, ctx: EstimateContext | None) -> np.ndarray:
    """``workload`` = est_workload, ``size`` = est_bytes (the size feature; the base profile is keyed on est_size)."""
    if workload not in spec["workloads"] or pool not in spec.get("n_rows_by_pool", dict.fromkeys(spec["pools"], 1)):
        raise ValueError(f"no training rows for workload {workload!r} / pool {pool!r} (trained on workloads "
                         f"{spec['workloads']}, executing pools {sorted(spec.get('n_rows_by_pool', spec['pools']))}); "
                         f"refusing to encode it as all zeros")
    ctx = ctx or EstimateContext()
    busy, corun, frac = ctx.busy_by_pool, ctx.corun, ctx.target_busy_frac
    return np.array([math.log(base_s), math.log(size)]
                    + [float(workload == w) for w in spec["workloads"]] + [float(pool == p) for p in spec["pools"]]
                    + [float(busy.get(p, 0)) for p in spec["pools"]] + [float(corun.get(w, 0)) for w in spec["workloads"]]
                    + [spec["impute_frac"] if frac is None else frac])


def training_matrix(rows: list[dict], base: StaticProfileEstimator, spec: dict) -> tuple[np.ndarray, np.ndarray]:
    # Fit site (both models): one row per EXECUTED placement, so only the chosen pool has a label.
    # Counterfactual pools (queried by EFT, never run) have no label -- documented limitation, see the
    # module docstring; mitigated by the E1 base + log-correction form and by random-placement data collection.
    X, y = [], []
    for r in rows:
        b = base.lookup(r["workload"], r["size"], r["pool"])
        X.append(encode(spec, r["workload"], r.get("bytes", r["size"]), r["pool"], b, r["ctx"]))
        y.append(math.log(r["kernel_s"] / b))
    if not X:
        raise ValueError("no training rows")
    return np.stack(X), np.array(y)


# --- predictors (features -> log correction) ------------------------------------

class _CatBoostPredictor:
    def __init__(self, model):
        self.model = model

    def predict_one(self, x: np.ndarray) -> float:
        return float(self.model.predict(x.reshape(1, -1))[0])

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(X), dtype=float)

    def to_dict(self) -> dict:
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "m.cbm")
            self.model.save_model(f)
            return {"cbm_base64": base64.b64encode(Path(f).read_bytes()).decode("ascii")}

    @classmethod
    def from_dict(cls, d: dict) -> "_CatBoostPredictor":
        from catboost import CatBoostRegressor
        m = CatBoostRegressor()
        m.load_model(blob=base64.b64decode(d["cbm_base64"]))
        return cls(m)


class _MlpPredictor:
    def __init__(self, layers: list[tuple[np.ndarray, np.ndarray]], mean: np.ndarray, std: np.ndarray):
        self.layers, self.mean, self.std = layers, np.asarray(mean), np.asarray(std)

    def predict(self, X: np.ndarray) -> np.ndarray:
        h = (np.atleast_2d(X) - self.mean) / self.std
        for i, (W, b) in enumerate(self.layers):
            h = h @ W.T + b
            if i < len(self.layers) - 1:
                h = np.maximum(h, 0.0)
        return h[:, 0]

    def predict_one(self, x: np.ndarray) -> float:
        return float(self.predict(x)[0])

    def to_dict(self) -> dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist(),
                "layers": [{"W": W.tolist(), "b": b.tolist()} for W, b in self.layers]}

    @classmethod
    def from_dict(cls, d: dict) -> "_MlpPredictor":
        return cls([(np.array(l["W"]), np.array(l["b"])) for l in d["layers"]], np.array(d["mean"]), np.array(d["std"]))


# --- estimators -----------------------------------------------------------------

class TabularCorrectionEstimator(ExecutionTimeEstimator):
    uses_context = True
    kind = "abstract"

    def __init__(self, base: StaticProfileEstimator, spec: dict, predictor, params: dict, meta: dict | None = None):
        self.base, self.spec, self.predictor = base, spec, predictor
        self.params, self.meta = params, meta or {}

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        base = self.base.lookup(task.est_workload, task.est_size, pool)
        x = encode(self.spec, task.est_workload, task.est_bytes, pool, base, ctx)
        return base * math.exp(float(np.clip(self.predictor.predict_one(x), -MAX_LOG_CORRECTION, MAX_LOG_CORRECTION)))

    def estimate_many(self, rows: list[dict]) -> np.ndarray:
        """Batch prediction for evaluation (rows: workload, size, [bytes], pool, ctx; rows are est_* already)."""
        b = np.array([self.base.lookup(r["workload"], r["size"], r["pool"]) for r in rows])
        X = np.stack([encode(self.spec, r["workload"], r.get("bytes", r["size"]), r["pool"], bi, r["ctx"])
                      for r, bi in zip(rows, b)])
        return b * np.exp(np.clip(self.predictor.predict(X), -MAX_LOG_CORRECTION, MAX_LOG_CORRECTION))

    def save(self, path: Path) -> None:
        if not self.base.source:
            raise ValueError("cannot save a model whose base profile has no source file: "
                             "load() could never verify which profile it belongs to")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({
            "schema_version": SCHEMA_VERSION, "estimator": self.name, "kind": self.kind,
            "base_profile": self.base.source, "spec": self.spec, "params": self.params, "meta": self.meta,
            "model": self.predictor.to_dict()}), encoding="utf-8")

    def describe(self) -> dict:
        return {"name": self.name, "base": self.base.describe(), "params": self.params,
                "features": feature_names(self.spec), "model_path": self.meta.get("model_path")}


class CatBoostEstimator(TabularCorrectionEstimator):
    name = "CatBoost_log_correction"
    kind = "catboost"

    @classmethod
    def fit(cls, rows: list[dict], base: StaticProfileEstimator, params: dict, seed: int,
            meta: dict | None = None) -> "CatBoostEstimator":
        from catboost import CatBoostRegressor
        clash = {"random_seed", "random_state", "thread_count", "nthread", "num_threads", "verbose", "allow_writing_files"} & set(params)
        if clash:
            raise ValueError(f"CatBoost params must not set {sorted(clash)}: fit() fixes them for reproducibility "
                             f"(seed = the config seed, single thread, silent, no files)")
        spec = make_spec(rows)
        X, y = training_matrix(rows, base, spec)
        m = CatBoostRegressor(**params, random_seed=seed, thread_count=1, verbose=0, allow_writing_files=False)
        m.fit(X, y)
        return cls(base, spec, _CatBoostPredictor(m), {**params, "random_seed": seed},
                   {**(meta or {}), "n_train_rows": len(rows)})


class MlpEstimator(TabularCorrectionEstimator):
    name = "MLP_log_correction"
    kind = "mlp"

    @classmethod
    def fit(cls, rows: list[dict], base: StaticProfileEstimator, params: dict, seed: int,
            meta: dict | None = None) -> "MlpEstimator":
        """params: hidden (list of widths), epochs, lr, weight_decay, batch_size."""
        import torch
        spec = make_spec(rows)
        X, y = training_matrix(rows, base, spec)
        mean, std = X.mean(0), X.std(0)
        std[std < 1e-8] = 1.0
        torch.manual_seed(seed)
        torch.set_num_threads(1)
        widths = [X.shape[1], *params["hidden"], 1]
        layers = []
        for a, b in zip(widths, widths[1:]):
            layers += [torch.nn.Linear(a, b), torch.nn.ReLU()]
        net = torch.nn.Sequential(*layers[:-1])
        opt = torch.optim.Adam(net.parameters(), lr=params["lr"], weight_decay=params["weight_decay"])
        Xt = torch.tensor((X - mean) / std, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
        g = torch.Generator().manual_seed(seed)
        for _ in range(params["epochs"]):
            perm = torch.randperm(len(Xt), generator=g)
            for i in range(0, len(Xt), params["batch_size"]):
                idx = perm[i:i + params["batch_size"]]
                opt.zero_grad()
                torch.nn.functional.mse_loss(net(Xt[idx]), yt[idx]).backward()
                opt.step()
        lin = [m for m in net if isinstance(m, torch.nn.Linear)]
        pred = _MlpPredictor([(l.weight.detach().double().numpy(), l.bias.detach().double().numpy()) for l in lin],
                             mean, std)
        return cls(base, spec, pred, {**params, "random_seed": seed}, {**(meta or {}), "n_train_rows": len(rows)})


_KINDS: dict[str, tuple[type[TabularCorrectionEstimator], type[_CatBoostPredictor] | type[_MlpPredictor]]] = {"catboost": (CatBoostEstimator, _CatBoostPredictor), "mlp": (MlpEstimator, _MlpPredictor)}


def load_tabular(path: Path, base: StaticProfileEstimator | None = None) -> TabularCorrectionEstimator:
    """Load a saved CatBoost/MLP model bound to its recorded base profile (rules: learned.py)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("kind") not in _KINDS:
        raise ValueError(f"{path}: unknown model kind {d.get('kind')!r}")
    base = resolve_base_profile(path, d.get("base_profile"), base)
    cls, pred = _KINDS[d["kind"]]
    return cls(base, d["spec"], pred.from_dict(d["model"]), d["params"],
               {**d["meta"], "model_path": str(path), "base_profile_recorded": d["base_profile"]})
