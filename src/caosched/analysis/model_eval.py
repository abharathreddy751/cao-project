"""Offline predictor evaluation (EVALUATION_PROTOCOL sections 4-6) and the model-selection rule.

Everything here is computed on HELD-OUT rows of a split (``dataset.splits``):
accuracy (MAE, RMSE, relative error, median/mean APE, signed bias, calibration by
decile), per-call inference latency distribution, peak memory, model size and
training time. Prediction quality and scheduling value are separate questions:
``select_model`` consumes scheduling results produced elsewhere.

Thresholds and hyper-parameters are never defined here; they arrive in the
config dict of ``evaluate`` (see scripts/evaluate_models.py).
"""
from __future__ import annotations

import csv
import json
import time
import tracemalloc
from collections import Counter
from pathlib import Path

import numpy as np
import psutil

from caosched.dataset.splits import folds
from caosched.estimators import (
    CatBoostEstimator, InterferenceRidgeEstimator, MlpEstimator, MovingHistoryEstimator, RecalibratedEstimator,
    StaticProfileEstimator, TaskSpec,
)
from caosched.estimators.base import EstimateContext
from caosched.estimators.learned import FEATURE_SETS


# --- metrics ---------------------------------------------------------------------

MAPE_NOTE = ("MAPE is dominated by rows with very small observed times (division by y); report median_ape as the "
             "headline relative error. mape_above_floor (config mape_floor_s) restricts MAPE to y >= the floor.")


def accuracy_metrics(y_true, y_pred, mape_floor_s: float | None = None) -> dict:
    """Seconds-scale errors; APE needs y_true > 0 (kernel times are). bias = mean(pred - true).
    Headline relative error = ``median_ape``; ``mape`` is unstable for tiny times (see ``mape_note``)."""
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    if y.size == 0 or (y <= 0).any():
        raise ValueError("accuracy_metrics needs a non-empty array of positive observed times")
    err = p - y
    ape = np.abs(err) / y
    out = {"n": int(y.size), "mean_observed_s": float(y.mean()), "mae_s": float(np.abs(err).mean()),
           "rmse_s": float(np.sqrt((err ** 2).mean())), "relative_mae": float(np.abs(err).mean() / y.mean()),
           "median_ape": float(np.median(ape)), "mape": float(ape.mean()), "mape_note": MAPE_NOTE,
           "bias_s": float(err.mean()), "relative_bias": float(err.mean() / y.mean())}
    if mape_floor_s is not None:
        big = y >= mape_floor_s
        out.update(mape_floor_s=float(mape_floor_s), n_above_floor=int(big.sum()),
                   mape_above_floor=float(ape[big].mean()) if big.any() else None)
    return out


def calibration_deciles(y_true, y_pred, bins: int = 10) -> list[dict]:
    """Observed versus predicted mean per equal-count bin of the prediction (fewer bins if few rows)."""
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    order = np.argsort(p, kind="stable")
    return [{"bin": i, "n": int(len(ix)), "mean_predicted_s": float(p[ix].mean()), "mean_observed_s": float(y[ix].mean())}
            for i, ix in enumerate(np.array_split(order, min(bins, len(order)))) if len(ix)]


def breakdown(rows: list[dict], preds: np.ndarray, key, mape_floor_s: float | None = None) -> dict:
    out = {}
    for k in sorted({key(r) for r in rows}):
        ix = [i for i, r in enumerate(rows) if key(r) == k]
        out[k] = accuracy_metrics([rows[i]["kernel_s"] for i in ix], preds[ix], mape_floor_s)
    return out


def latency_distribution(call, n_calls: int, warmup: int = 5) -> dict:
    """Per-call latency of ``call(i)`` in microseconds (distribution, not only the mean)."""
    for i in range(warmup):
        call(i)
    t = np.empty(n_calls)
    for i in range(n_calls):
        t0 = time.perf_counter_ns()
        call(i)
        t[i] = (time.perf_counter_ns() - t0) / 1e3
    return {"n_calls": n_calls, "mean_us": float(t.mean()), "p50_us": float(np.percentile(t, 50)),
            "p90_us": float(np.percentile(t, 90)), "p99_us": float(np.percentile(t, 99)), "max_us": float(t.max())}


def measured(fn, memory: bool = True):
    """(result, {"seconds", "tracemalloc_peak_bytes", "rss_delta_bytes"}). ``seconds`` and the RSS delta come
    from an UNTRACED call (tracemalloc slows allocation-heavy code); with ``memory`` a SECOND, traced call of
    ``fn`` (result discarded; costs a second run) gives the peak, else it is None. tracemalloc sees Python/numpy
    allocations only (not CatBoost's native memory); the RSS delta sees both but is coarse -- report both."""
    proc = psutil.Process()
    rss0 = proc.memory_info().rss
    t0 = time.perf_counter()
    res = fn()
    seconds = time.perf_counter() - t0
    rss = int(proc.memory_info().rss - rss0)
    peak = None
    if memory:
        tracemalloc.start()
        try:
            fn()
            peak = int(tracemalloc.get_traced_memory()[1])
        finally:
            tracemalloc.stop()
    return res, {"seconds": seconds, "tracemalloc_peak_bytes": peak, "rss_delta_bytes": rss}


def replay_online(estimator, rows: list[dict]) -> np.ndarray:
    """Predictions of an ONLINE estimator (E3, '+rc') for the rows of ONE run: each task is
    predicted at its decision time using only completions observed before it (a decision at the
    same instant as a completion does not see it); ``reset`` first, like the scheduler."""
    estimator.reset()
    events = sorted([(r["t_dispatched_rel"], 1, i) for i, r in enumerate(rows)]
                    + [(r["t_completed_rel"], 2, i) for i, r in enumerate(rows)])
    out = np.zeros(len(rows))
    for _, kind, i in events:
        r = rows[i]
        spec = TaskSpec(r["task_id"], r["workload"], r["size"])
        if kind == 1:
            out[i] = estimator.estimate(spec, r["pool"], r["ctx"])
        else:
            estimator.observe(spec, r["pool"], r["kernel_s"], r["ctx"])
    return out


# --- model selection --------------------------------------------------------------

def select_model(models: list[dict], pairs: list[dict], margin: float) -> dict:
    """Rule fixed before the pilot: choose the cheapest model whose scheduling outcome is not worse
    than that of any more complex model, within the confidence interval.

    ``models``: [{"name", "complexity"}] (lower = cheaper). ``pairs``: one entry per (simple, complex)
    pair with ``diff_lo``, ``diff_hi``, ``diff_mean`` = bootstrap CI of outcome(simple) - outcome(complex),
    outcome lower = better (e.g. makespan). The simple model is NOT worse only if the interval's UPPER bound
    is within the margin (``diff_hi <= margin``: at most ``margin`` worse even at the CI's pessimistic end);
    an interval that straddles ``margin`` cannot exclude "worse", so the more complex model is preferred.
    The most complex model is selected when no cheaper one qualifies. Missing pairs raise: absence of
    evidence is not "not worse"."""
    ordered = sorted(models, key=lambda m: (m["complexity"], m["name"]))
    by_pair = {(p["simple"], p["complex"]): p for p in pairs}
    checks, selected = [], None
    for i, m in enumerate(ordered):
        rows = []
        for c in ordered[i + 1:]:
            if (m["name"], c["name"]) not in by_pair:
                raise KeyError(f"no scheduling comparison for ({m['name']!r} vs more complex {c['name']!r})")
            p = by_pair[(m["name"], c["name"])]
            rows.append({"complex": c["name"], "diff_mean": p["diff_mean"], "diff_lo": p["diff_lo"],
                         "diff_hi": p["diff_hi"], "not_worse": p["diff_hi"] <= margin})
        ok = all(r["not_worse"] for r in rows)
        checks.append({"model": m["name"], "complexity": m["complexity"], "qualifies": ok, "against": rows})
        if ok and selected is None:
            selected = m["name"]
    return {"rule": "cheapest model not worse (CI upper bound diff_hi <= margin) than every more complex model",
            "margin": margin, "selected": selected, "checks": checks}


# --- dataset loading and evaluation -------------------------------------------------

def load_rows(dataset_dir: Path, require_decision_context: bool) -> tuple[list[dict], dict]:
    """tasks.csv -> row dicts with a typed ``ctx``. Returns (rows, {"dropped": n}). With
    ``require_decision_context`` rows whose features were not logged at the decision are dropped."""
    rows, dropped = [], 0
    with (Path(dataset_dir) / "tasks.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if require_decision_context and r["ctx_source"] != "decision":
                dropped += 1
                continue
            rows.append({**r, "size": int(r["size"]), "bytes": int(r.get("est_bytes") or r["size"]), "kernel_s": float(r["kernel_s"]),
                         "t_dispatched_rel": float(r["t_dispatched_rel"]), "t_completed_rel": float(r["t_completed_rel"]),
                         "ctx": EstimateContext.from_dict(json.loads(r["ctx_json"]))})
    return rows, {"dropped": dropped}


def _fit_models(train, base, cfg, seed) -> dict:
    """name -> (estimator, fit measurement). Only the models configured are fitted. The fit is timed
    untraced; the tracemalloc peak needs a second fit and is taken only if ``cfg["measure_memory"]``."""
    out = {}
    mem = bool(cfg.get("measure_memory", False))
    if "ridge" in cfg:
        c = cfg["ridge"]
        out["Ridge"] = measured(lambda: InterferenceRidgeEstimator.fit(
            train, base, c["ridge_lambda"], c["min_rows"], features=FEATURE_SETS[c["feature_set"]]), mem)
    if "catboost" in cfg:
        out["CatBoost"] = measured(lambda: CatBoostEstimator.fit(train, base, cfg["catboost"], seed), mem)
    if "mlp" in cfg:
        out["MLP"] = measured(lambda: MlpEstimator.fit(train, base, cfg["mlp"], seed), mem)
    return out


def _predict(name: str, est, test: list[dict], base) -> np.ndarray:
    if name in ("E1", "Ridge", "CatBoost", "MLP"):  # stateless at inference
        if hasattr(est, "estimate_many"):
            return est.estimate_many(test)
        return np.array([est.estimate(TaskSpec(r["task_id"], r["workload"], r["size"]), r["pool"], r["ctx"]) for r in test])
    out = np.zeros(len(test))  # online references: replay run by run
    for run in sorted({r["source_log"] for r in test}):
        ix = [i for i, r in enumerate(test) if r["source_log"] == run]
        out[ix] = replay_online(est, [test[i] for i in ix])
    return out


def evaluate(rows: list[dict], base: StaticProfileEstimator, cfg: dict, out_dir: Path) -> dict:
    """Fit every configured model on each fold's train side and score its held-out side. Writes
    ``predictions_<model>.csv`` and ``metrics.json`` to ``out_dir``; returns the metrics dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = cfg["seed"]
    floor = cfg.get("mape_floor_s")
    fold_list = folds(rows, cfg["split"])
    preds: dict[str, list] = {}          # model -> [(fold, row, prediction)]
    cost: dict[str, dict] = {}           # model -> {fold: train time / memory / size info of that fold's fit}
    last_fit, last_test = {}, []
    for fold, train, test in fold_list:
        fitted = _fit_models(train, base, cfg, seed)
        for e, _ in fitted.values():
            e.meta["fitted_on_fold"] = fold
        by_pool = dict(sorted(Counter(r["pool"] for r in train).items()))
        rc = cfg["rc"]
        online = {"E1": base, "E3": MovingHistoryEstimator(base, cfg["e3_window"]),
                  "E1+rc": RecalibratedEstimator(base, rc["alpha"], rc["min_obs"], tuple(rc["clamp"]))}
        models = {**online, **{n: e for n, (e, _) in fitted.items()}}
        for name, est in models.items():
            p = _predict(name, est, test, base)
            preds.setdefault(name, []).extend((fold, r, float(x)) for r, x in zip(test, p))
        for n, (e, m) in fitted.items():
            cost.setdefault(n, {})[fold] = {
                "train_seconds": m["seconds"], "train_tracemalloc_peak_bytes": m["tracemalloc_peak_bytes"],
                "train_rss_delta_bytes": m["rss_delta_bytes"], "n_train_rows": len(train), "n_train_rows_by_pool": by_pool}
        last_fit, last_test = models, test
    last_fold = fold_list[-1][0]
    metrics = {"split": cfg["split"], "folds": [f for f, _, _ in fold_list], "seed": seed,
               "base_profile": base.source, "mape_floor_s": floor, "models": {}}
    for name, items in preds.items():
        held = [r for _, r, _ in items]
        p = np.array([x for _, _, x in items])
        est = last_fit[name]
        spec = lambda r: (TaskSpec(r["task_id"], r["workload"], r["size"]), r["pool"], r["ctx"])
        n_calls = cfg["latency"]["n_calls"]
        lat = latency_distribution(lambda i: est.estimate(*spec(last_test[i % len(last_test)])), n_calls)
        _, mem = measured(lambda: [est.estimate(*spec(r)) for r in last_test])
        m = {"headline_relative_error": "median_ape",
             "overall": accuracy_metrics([r["kernel_s"] for r in held], p, floor),
             "per_fold": {f: accuracy_metrics([r["kernel_s"] for g, r, _ in items if g == f],
                                              [x for g, _, x in items if g == f], floor) for f in metrics["folds"]},
             "by_workload": breakdown(held, p, lambda r: r["workload"], floor),
             "by_pool": breakdown(held, p, lambda r: r["pool"], floor),
             "calibration_deciles": calibration_deciles([r["kernel_s"] for r in held], p),
             "inference_latency": lat, "inference_measured_on_fold": last_fold,
             "inference_peak_memory_over_test_set": {k: v for k, v in mem.items() if k != "seconds"}}
        if name in cost:  # fitted model: per-fold training cost, plus the persisted LAST-fold model
            pf = cost[name]
            secs = [v["train_seconds"] for v in pf.values()]
            peaks = [v["train_tracemalloc_peak_bytes"] for v in pf.values() if v["train_tracemalloc_peak_bytes"] is not None]
            m.update(train_per_fold=pf, train_seconds=float(np.mean(secs)),
                     train_tracemalloc_peak_bytes=max(peaks) if peaks else None,
                     train_rss_delta_bytes=max(v["train_rss_delta_bytes"] for v in pf.values()),
                     n_train_rows=int(round(np.mean([v["n_train_rows"] for v in pf.values()]))),
                     train_aggregate="seconds and rows: mean over folds; memory: max over folds")
            path = out_dir / f"model_{name}.json"
            est.save(path)  # a FOLD model (not refit on all rows); labelled in meta["fitted_on_fold"] and here
            m["model_size_bytes"] = path.stat().st_size
            m["saved_model"] = {"path": str(path), "fitted_on_fold": last_fold,
                                "n_train_rows": pf[last_fold]["n_train_rows"],
                                "note": "fold model: trained on that fold's train side only, not refit on all training rows"}
        metrics["models"][name] = m
        with (out_dir / f"predictions_{name.replace('+', '_')}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["fold", "model", "source_log", "task_id", "session_id", "instance", "workload", "size", "pool",
                        "kernel_s", "predicted_s", "e1_base_s"])
            for f, r, x in items:
                w.writerow([f, name, r["source_log"], r["task_id"], r["session_id"], r["instance"], r["workload"],
                            r["size"], r["pool"], r["kernel_s"], x, base.lookup(r["workload"], r["size"], r["pool"])])
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    return metrics
