"""Stage 3 offline predictor evaluation and model-selection record.

Loads a dataset (output of scripts/build_dataset.py: tasks.csv, manifest.json), applies the split
policy, fits Ridge / CatBoost / MLP on each fold's train side, scores them and the references
(E1, E3, E1+rc) on the HELD-OUT side only, and writes to --out:
  metrics.json                accuracy (MAE, RMSE, relative error, median/mean APE, bias, calibration by
                              decile), inference latency distribution, peak memory, model size, training time
  predictions_<model>.csv     one row per held-out task and model
  model_<model>.json          the fitted models (bound to --profile, like E4)
  selection_record.json       only with --scheduling: the 'cheapest model not worse within the CI' rule

No threshold or hyper-parameter is in the code: all come from --config (JSON), e.g.
  {"seed": 0,
   "split": {"policy": "instance", "leave_one_out": true},       # or policy session|size|occupancy|time, see dataset/splits.py
   "require_decision_context": true,              # false is refused unless "allow_non_decision_context": true
   "allow_profile_after_sessions": false,
   "mape_floor_s": null,                          # optional: also report MAPE over observed times >= floor
   "measure_memory": false,                       # true = second (traced) fit per fold for the tracemalloc peak
   "e3_window": 8, "rc": {"alpha": 0.2, "min_obs": 1, "clamp": [0.5, 3.0]},
   "ridge": {"ridge_lambda": 1.0, "min_rows": 30, "feature_set": "occupancy+history"},
   "catboost": {<CatBoostRegressor keyword arguments>},
   "mlp": {"hidden": [16, 16], "epochs": N, "lr": X, "weight_decay": X, "batch_size": N},
   "latency": {"n_calls": N},
   "selection": {"margin": X}}
Sections ridge / catboost / mlp that are absent are skipped. --scheduling is a JSON
{"models": [{"name", "complexity"}], "pairs": [{"simple", "complex", "diff_mean", "diff_lo", "diff_hi"}]}
(paired bootstrap CI of outcome(simple) - outcome(complex), lower = better; produced from scheduling runs).

Usage: python scripts/evaluate_models.py --dataset DIR --profile PATH --config CFG.json --out DIR [--scheduling FILE]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from caosched.analysis.model_eval import evaluate, load_rows, select_model
from caosched.estimators import StaticProfileEstimator

_STAMP = re.compile(r"(\d{8}T\d{6})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--profile", required=True, help="E1 base profile; must predate every session in the dataset")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scheduling", default=None)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out = Path(args.out)
    manifest = json.loads((Path(args.dataset) / "manifest.json").read_text(encoding="utf-8"))
    first = min(_STAMP.search(s).group(1) for s in manifest["sessions"])
    stamp = _STAMP.search(Path(args.profile).name).group(1)
    if stamp > first and not cfg.get("allow_profile_after_sessions", False):
        raise SystemExit(f"profile {Path(args.profile).name} is newer than the earliest session ({first}): "
                         f"calibration must predate the data (AD-7)")
    allow_non_dec = bool(cfg.get("allow_non_decision_context", False))
    if not cfg["require_decision_context"] and not allow_non_dec:
        raise SystemExit("require_decision_context=false refused: rows with start-time reconstructed features leak "
                         "post-decision data (AD-7). Set allow_non_decision_context=true in the config to override "
                         "(recorded in metrics.json and selection_record.json).")
    base = StaticProfileEstimator.from_file(args.profile)
    rows, info = load_rows(Path(args.dataset), cfg["require_decision_context"])
    ctx_counts = dict(sorted(Counter(r["ctx_source"] for r in rows).items()))
    metrics = evaluate(rows, base, cfg, out)
    metrics["rows_per_ctx_source"] = ctx_counts
    if not cfg["require_decision_context"]:
        metrics["WARNING"] = ("NON-DECISION CONTEXT ALLOWED (allow_non_decision_context=true): rows with "
                              f"start-time features were used; rows_per_ctx_source={ctx_counts}")
        print(metrics["WARNING"])
    metrics["dataset"] = {"dir": str(args.dataset), "n_rows_used": len(rows), "n_rows_dropped_not_decision_ctx": info["dropped"],
                          "manifest_outputs": manifest.get("outputs"), "profile": str(args.profile),
                          "rows_per_ctx_source": ctx_counts}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    for name, m in metrics["models"].items():
        o = m["overall"]
        print(f"{name:9s} n={o['n']:6d} MAE={o['mae_s']:.4g}s RMSE={o['rmse_s']:.4g}s medAPE={o['median_ape']:.3f} "
              f"bias={o['bias_s']:+.3g}s p50={m['inference_latency']['p50_us']:.0f}us")
    if args.scheduling:
        sched = json.loads(Path(args.scheduling).read_text(encoding="utf-8"))
        rec = select_model(sched["models"], sched["pairs"], cfg["selection"]["margin"])
        (out / "selection_record.json").write_text(json.dumps(
            {**rec, "scheduling_input": str(args.scheduling), "prediction_metrics": str(out / "metrics.json"),
             "rows_per_ctx_source": ctx_counts, "require_decision_context": cfg["require_decision_context"],
             "allow_non_decision_context": allow_non_dec,
             **({"WARNING": metrics["WARNING"]} if "WARNING" in metrics else {})}, indent=1), encoding="utf-8")
        print("selected:", rec["selected"])


if __name__ == "__main__":
    main()
