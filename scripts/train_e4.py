"""Phase 3: train E4 (interference ridge) on a randomized campaign.

Split by run in collection (time) order -- never by random row: the first
``train_fraction`` of campaign runs train the model, the rest are held out
for evaluation (recorded in the model file).

Usage:
    python scripts/train_e4.py [--config config/phase3.yaml] [--campaign DIR] [--profile PATH] [--context-source decision|start|auto]
"""
from __future__ import annotations

import argparse
import datetime
from pathlib import Path

import yaml

from caosched.core.event_log import DEFAULT_OUTPUT_DIR as EVENTS_DIR
from caosched.dataset.events import rows_from_dir
from caosched.estimators import InterferenceRidgeEstimator, StaticProfileEstimator, latest_profile_path
from caosched.estimators.learned import FEATURE_SETS, MODEL_DIR


def latest_dir(prefix: str) -> Path:
    c = sorted(p for p in EVENTS_DIR.glob(f"{prefix}_*") if p.is_dir())
    if not c:
        raise SystemExit(f"No {prefix}_* directory in {EVENTS_DIR}")
    return c[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase3.yaml")
    ap.add_argument("--campaign", default=None)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--feature-set", default=None, choices=sorted(FEATURE_SETS))
    ap.add_argument("--context-source", default="decision", choices=("decision", "auto", "start"),
                    help="decision (default): logged decision context only. Historical campaigns without one need "
                         "'start' explicitly (post-decision reconstruction, leaky for early binding).")
    args = ap.parse_args()
    if args.context_source != "decision":
        print(f"WARNING: --context-source {args.context_source}: features are reconstructed from the task START "
              f"(post-decision data, not what the scheduler knew at placement); use only for historical logs.")
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["estimators"]["E4"]
    campaign = Path(args.campaign) if args.campaign else latest_dir("campaign")
    profile = Path(args.profile) if args.profile else latest_profile_path()

    rows = rows_from_dir(campaign, args.context_source)
    run_ids = sorted({r["run_id"] for r in rows})
    n_train = int(len(run_ids) * cfg["train_fraction"])
    train_ids, holdout_ids = run_ids[:n_train], run_ids[n_train:]
    train = [r for r in rows if r["run_id"] in set(train_ids)]

    base = StaticProfileEstimator.from_file(profile)
    fset = args.feature_set or cfg.get("feature_set", "occupancy+history")
    model = InterferenceRidgeEstimator.fit(train, base, cfg["ridge_lambda"], cfg["min_rows"], meta={
        "campaign_dir": str(campaign), "profile": str(profile), "split": "by run, collection order", "context_source": args.context_source,
        "train_runs": train_ids, "holdout_runs": holdout_ids, "n_train_rows": len(train), "feature_set": fset,
    }, features=FEATURE_SETS[fset])
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    out = MODEL_DIR / f"e4_{stamp}_{fset.replace('+', '_')}.json"
    model.save(out)

    print(f"E4 trained on {len(train)} rows from {len(train_ids)} runs ({campaign.name}); "
          f"{len(holdout_ids)} runs held out -> {out.name}")
    print(f"feature set {fset}; impute {model.meta['impute']}")
    print(f"{'group':22s} {'n':>5s} {'rmse(log)':>9s}  " + " ".join(f"{f[:16]:>16s}" for f in model.features))
    for key, info in model.meta["groups"].items():
        w = model.weights[tuple(key.split("|"))]
        tag = " (fallback E1)" if info["fallback_to_E1"] else ""
        rm = f"{info['train_rmse_log']:9.3f}" if "train_rmse_log" in info else f"{'-':>9s}"
        print(f"{key:22s} {info['n']:5d} {rm}  " + " ".join(f"{x:16.4f}" for x in w) + tag)


if __name__ == "__main__":
    main()
