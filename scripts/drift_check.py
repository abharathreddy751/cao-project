"""Drift summary for the time-ordered split (EVALUATION_PROTOCOL section 5, STAGE3_FREEZE section 2).

Input: the dataset used and the output dir of scripts/evaluate_models.py run with split policy 'time'
(predictions_<model>.csv hold the held-out rows = the later runs of each session). Within each session the
held-out runs are ordered like the split orders them (``run_order_key``) and cut in an early half and a late
half; per model MAE / median APE / signed bias of both halves are written to drift_summary.csv/.json.
The late/early MAE ratio is a descriptive number, not a test: halves hold 2-3 runs per session.

Usage: python scripts/drift_check.py --dataset DIR --eval DIR --out DIR
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from caosched.dataset.splits import run_order_key


def early_late(rows: list[dict], test_logs: set[str]) -> dict[str, str]:
    """source_log -> 'early' | 'late': held-out runs of each session, in collection order, first half / second half."""
    by_run: dict[str, list] = defaultdict(list)
    for r in rows:
        by_run[r["source_log"]].append(r)
    sessions: dict[str, list] = defaultdict(list)
    for log in test_logs:
        sessions[by_run[log][0]["session_id"]].append(log)
    out = {}
    for logs in sessions.values():
        logs.sort(key=lambda l: run_order_key(by_run[l], l))
        out.update({l: "early" if i < len(logs) / 2 else "late" for i, l in enumerate(logs)})
    return out


def half_metrics(y, p) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    e = p - y
    return {"n": int(y.size), "mean_observed_s": float(y.mean()), "mae_s": float(np.abs(e).mean()),
            "median_ape": float(np.median(np.abs(e) / y)), "bias_s": float(e.mean())}


def summarize(rows: list[dict], preds: dict[str, list[dict]]) -> list[dict]:
    """``preds``: model -> prediction rows (source_log, workload, kernel_s, predicted_s). One output row per
    model x half x subset (all rows / mProject only)."""
    half = early_late(rows, {r["source_log"] for rs in preds.values() for r in rs})
    out = []
    for model, rs in preds.items():
        for subset, keep in (("all", lambda r: True), ("mProject", lambda r: r["workload"] == "mProject")):
            for h in ("early", "late"):
                sel = [r for r in rs if half[r["source_log"]] == h and keep(r)]
                if sel:
                    out.append({"model": model, "subset": subset, "half": h,
                                **half_metrics([r["kernel_s"] for r in sel], [r["predicted_s"] for r in sel])})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--eval", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with (Path(a.dataset) / "tasks.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    preds = {}
    for f in sorted(Path(a.eval).glob("predictions_*.csv")):
        with f.open(encoding="utf-8", newline="") as fh:
            rs = list(csv.DictReader(fh))
        for r in rs:
            r["kernel_s"], r["predicted_s"] = float(r["kernel_s"]), float(r["predicted_s"])
        preds[rs[0]["model"]] = rs
    table = summarize(rows, preds)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "drift_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    ratios = {}
    for m in preds:
        e, l = (next(t for t in table if t["model"] == m and t["subset"] == "all" and t["half"] == h) for h in ("early", "late"))
        ratios[m] = {"mae_early_s": e["mae_s"], "mae_late_s": l["mae_s"], "late_over_early_mae": l["mae_s"] / e["mae_s"],
                     "mean_observed_early_s": e["mean_observed_s"], "mean_observed_late_s": l["mean_observed_s"]}
    (out / "drift_summary.json").write_text(json.dumps({"rows": table, "late_over_early": ratios}, indent=1), encoding="utf-8")
    for m, r in ratios.items():
        print(f"{m:9s} MAE early={r['mae_early_s']:.4g}s late={r['mae_late_s']:.4g}s ratio={r['late_over_early_mae']:.2f} "
              f"(mean observed {r['mean_observed_early_s']:.3g}s -> {r['mean_observed_late_s']:.3g}s)")


if __name__ == "__main__":
    main()
