"""Learning curve of Ridge / CatBoost / MLP (evidence for the TabM entry rule, STAGE3_FREEZE section 2, condition 2).

Fits each model with the FROZEN config (--config, hyper-parameters untouched) on growing fractions of the training
runs and scores it on held-out rows only:
  final_test  train = fraction of the fitting runs (instances d1.0, d1.1, d1.1/c10.7), test = the held-out instance
              of the config's split (d1.5) taken from the full dataset
  tuning_loo  leave-one-instance-out on the fitting dataset: for each instance the train side is a fraction of the
              OTHER instances' runs; MAE is pooled over the three folds (row-weighted)
A fraction is drawn as WHOLE RUNS, stratified by instance (round(f * runs of the instance), at least 1), by a seeded
permutation of the runs (never random rows); subsamples are repeated ``--repeats`` times (100% is one deterministic
fit). The model seed is the config seed. ``still_falling`` states plainly whether the error still falls at 100%.

Usage: python scripts/learning_curve.py --dataset-fit DIR --dataset-all DIR --profile P --config CFG.json --out DIR [--repeats 5]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from caosched.analysis.model_eval import _fit_models, accuracy_metrics, load_rows
from caosched.estimators import StaticProfileEstimator, TaskSpec

FRACTIONS = (0.1, 0.2, 0.4, 0.6, 0.8, 1.0)


def run_subset(rows: list[dict], frac: float, seed: int) -> list[dict]:
    """Whole runs (``source_log``), stratified by instance: round(frac * runs of the instance) runs (>= 1), chosen by a
    seeded shuffle of the sorted run names. Draws for different fractions are independent (not nested)."""
    by_inst: dict[str, set] = defaultdict(set)
    for r in rows:
        by_inst[r["instance"]].add(r["source_log"])
    keep: set = set()
    for inst in sorted(by_inst):
        logs = sorted(by_inst[inst])
        random.Random(f"{seed}/{inst}/{frac}").shuffle(logs)
        keep.update(logs[:max(1, round(frac * len(logs)))])
    return [r for r in rows if r["source_log"] in keep]


def still_falling(mean_80: float, sd_80: float, mean_100: float) -> str:
    """'falling' if the error at 100% is below the 80% mean by more than the subsample sd at 80%; 'rising' if above by
    more than it; else 'flat (within subsample spread)'. A descriptive rule, not a test."""
    d = mean_100 - mean_80
    return "falling" if d < -sd_80 else "rising" if d > sd_80 else "flat (within subsample spread)"


def curve_point(train: list[dict], test: list[dict], cfg: dict, base) -> dict:
    """model -> accuracy of the frozen-config fit on ``train`` over ``test`` (+ n_train_rows)."""
    out = {}
    for name, (est, _) in _fit_models(train, base, {**cfg, "measure_memory": False}, cfg["seed"]).items():
        p = est.estimate_many(test) if hasattr(est, "estimate_many") else np.array(
            [est.estimate(TaskSpec(r["task_id"], r["workload"], r["size"]), r["pool"], r["ctx"]) for r in test])
        out[name] = {**accuracy_metrics([r["kernel_s"] for r in test], p), "n_train_rows": len(train)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-fit", required=True)
    ap.add_argument("--dataset-all", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    base = StaticProfileEstimator.from_file(a.profile)
    fit, _ = load_rows(Path(a.dataset_fit), True)
    allr, _ = load_rows(Path(a.dataset_all), True)
    test_inst = set(cfg["split"]["test"])
    test = [r for r in allr if r["instance"] in test_inst]
    assert not ({r["instance"] for r in fit} & test_inst) and len(fit) + len(test) == len(allr), "fit/test sets overlap or differ"
    instances = sorted({r["instance"] for r in fit})
    e1 = accuracy_metrics([r["kernel_s"] for r in test], [base.lookup(r["workload"], r["size"], r["pool"]) for r in test])
    recs = []  # one record per (eval, fraction, repeat, model, fold)

    def add(ev, frac, rep, fold, train, te):
        for model, m in curve_point(train, te, cfg, base).items():
            recs.append({"eval": ev, "fraction": frac, "repeat": rep, "model": model, "fold": fold, "n_test": m["n"],
                         "n_train_rows": m["n_train_rows"], "abs_err_sum_s": m["mae_s"] * m["n"], "mae_s": m["mae_s"],
                         "rmse_s": m["rmse_s"], "median_ape": m["median_ape"]})

    for frac in FRACTIONS:
        for rep in range(1 if frac == 1.0 else a.repeats):
            add("final_test", frac, rep, "+".join(sorted(test_inst)), run_subset(fit, frac, rep), test)
            for held in instances:
                add("tuning_loo", frac, rep, held, run_subset([r for r in fit if r["instance"] != held], frac, rep),
                    [r for r in fit if r["instance"] == held])
            print(f"fraction {frac} repeat {rep} done", flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "curve_raw.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)
    agg = []  # MAE per (eval, model, fraction, repeat) is row-weighted over the folds of the eval
    for ev in ("final_test", "tuning_loo"):
        for model in sorted({r["model"] for r in recs}):
            for frac in FRACTIONS:
                reps = defaultdict(list)
                for r in recs:
                    if (r["eval"], r["model"], r["fraction"]) == (ev, model, frac):
                        reps[r["repeat"]].append(r)
                mae = [sum(x["abs_err_sum_s"] for x in v) / sum(x["n_test"] for x in v) for v in reps.values()]
                agg.append({"eval": ev, "model": model, "fraction": frac, "n_repeats": len(mae),
                            "n_train_rows_mean": float(np.mean([sum(x["n_train_rows"] for x in v) / len(v) for v in reps.values()])),
                            "mae_s_mean": float(np.mean(mae)), "mae_s_sd": float(np.std(mae, ddof=1)) if len(mae) > 1 else 0.0,
                            "mae_s_min": float(min(mae)), "mae_s_max": float(max(mae))})
    verdict = {}
    for x in agg:
        if x["fraction"] == 0.8:
            y = next(z for z in agg if (z["eval"], z["model"], z["fraction"]) == (x["eval"], x["model"], 1.0))
            verdict[f"{x['eval']}/{x['model']}"] = {
                "mae_80": x["mae_s_mean"], "sd_80": x["mae_s_sd"], "mae_100": y["mae_s_mean"],
                "change_80_to_100_pct": 100 * (y["mae_s_mean"] - x["mae_s_mean"]) / x["mae_s_mean"],
                "still_falling_at_100": still_falling(x["mae_s_mean"], x["mae_s_sd"], y["mae_s_mean"])}
    with (out / "curve.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(agg[0]))
        w.writeheader()
        w.writerows(agg)
    (out / "curve.json").write_text(json.dumps(
        {"evidence": "real", "config": a.config, "fractions": FRACTIONS, "repeats": a.repeats, "e1_mae_final_test_s": e1["mae_s"],
         "subsampling": "whole runs, stratified by instance, seeded; 100% = one fit", "verdict": verdict, "curve": agg}, indent=1),
        encoding="utf-8")
    _plot(agg, e1["mae_s"], out / "learning_curve.png")
    for k, v in verdict.items():
        print(f"{k:24s} MAE@80%={v['mae_80']:.3f}s (sd {v['sd_80']:.3f}) MAE@100%={v['mae_100']:.3f}s "
              f"change={v['change_80_to_100_pct']:+.1f}% -> {v['still_falling_at_100']}")


def _plot(agg, e1_mae, path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, ev, title in zip(axes, ("final_test", "tuning_loo"), ("held-out d1.5 instance (final test rows)", "leave-one-instance-out (tuning folds, pooled)")):
        for model in sorted({x["model"] for x in agg}):
            g = sorted((x for x in agg if x["eval"] == ev and x["model"] == model), key=lambda x: x["fraction"])
            ax.errorbar([100 * x["fraction"] for x in g], [x["mae_s_mean"] for x in g], [x["mae_s_sd"] for x in g], marker="o", capsize=3, label=model)
        if ev == "final_test":
            ax.axhline(e1_mae, ls="--", color="grey", label="E1 (no training)")
        ax.set_xlabel("share of training runs used (%)")
        ax.set_ylabel("held-out MAE (s)")
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8)
    fig.suptitle("Learning curve, kernel-time prediction (evidence: real; mean +/- sd over run subsamples)", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)


if __name__ == "__main__":
    main()
