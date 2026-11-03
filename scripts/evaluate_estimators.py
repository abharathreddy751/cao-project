"""Phase 3: offline accuracy evaluation of the estimator ladder E0-E5.

Test sets (split by session / run, never by random row):
  c2_holdout  held-out runs of the campaign E4 was trained on (same session)
  c1          an earlier, independent campaign session (cross-session)
  phase2      the Phase 2 baseline-policy runs (cross-session, DAG-driven occupancy)

Every task row is predicted with the decision-time EstimateContext
reconstructed from its log. E3 is replayed causally per run: a task is
predicted from observations of tasks that *completed before it started*
(prior E1). E5 (replay oracle) is evaluated leave-run-out on phase2 only
(campaign tasks are unique per run, so no other-run observation exists).

Accuracy only -- decision quality (regret) is Phase 4's job.

Outputs: data/results/phase3_<stamp>_predictions.csv (one row per task x
estimator) and phase3_<stamp>_summary.json; tables printed.

Usage:
    python scripts/evaluate_estimators.py --e4 MODEL.json [--e4-ablation MODEL.json]
        [--c1 DIR] [--phase2 DIR] [--config config/phase3.yaml]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import statistics
from pathlib import Path

import yaml

from caosched.dataset.events import rows_from_dir
from caosched.estimators import (
    AnalyticSizeEstimator, ConstantProfileEstimator, InterferenceRidgeEstimator, MovingHistoryEstimator,
    ReplayOracleEstimator, StaticProfileEstimator, TaskSpec,
)
from caosched.estimators.profile_data import load_profile_rows

RESULTS = Path(__file__).resolve().parents[1] / "data" / "results"
FIELDS = ["test_set", "run_id", "task_id", "workload", "size", "pool", "busy_P", "busy_E", "busy_total",
          "target_busy_frac", "estimator", "actual_s", "predicted_s", "ape", "signed_rel_err"]


def spec(r) -> TaskSpec:
    return TaskSpec(r["task_id"], r["workload"], r["size"], r["seed"])


def predict_run(rows, estimators, e3_window, profile_path, e5=None):
    """Yield (row, estimator_name, prediction) for one run's rows."""
    e3 = MovingHistoryEstimator(StaticProfileEstimator.from_file(profile_path), e3_window)
    by_start = sorted(rows, key=lambda r: r["t_started"])
    by_end = sorted(rows, key=lambda r: r["t_completed"])
    j = 0
    if e5 is not None:
        e5.exclude_run(rows[0]["run_id"])
    for r in by_start:
        while j < len(by_end) and by_end[j]["t_completed"] <= r["t_started"]:
            o = by_end[j]
            e3.observe(spec(o), o["pool"], o["kernel_s"])
            j += 1
        t, pool, ctx = spec(r), r["pool"], r["ctx"]
        for name, est in estimators.items():
            yield r, name, est.estimate(t, pool, ctx)
        yield r, "E3_history", e3.estimate(t, pool, ctx)
        if e5 is not None:
            try:
                yield r, "E5_oracle", e5.estimate(t, pool, ctx)
            except KeyError:
                pass  # task never ran on this pool in another run


def metrics(recs) -> dict:
    apes = sorted(x["ape"] for x in recs)
    signed = [x["signed_rel_err"] for x in recs]
    return {"n": len(recs), "median_ape": statistics.median(apes), "mape": statistics.fmean(apes),
            "p90_ape": apes[int(0.9 * (len(apes) - 1))], "median_signed": statistics.median(signed),
            "mae_ms": statistics.fmean(abs(x["predicted_s"] - x["actual_s"]) for x in recs) * 1e3}


def occ_bucket(b: int) -> str:
    return "0" if b == 0 else "1-3" if b <= 3 else "4-6" if b <= 6 else "7-8"


def e2_size_extrapolation(profile_path, exponents) -> list[dict]:
    """Fit E2 on the smallest profiled size of each workload only; predict the
    largest size (solo profile median) -- how well does the analytic
    exponent extrapolate?"""
    rows = load_profile_rows(profile_path)
    out = []
    for wl in sorted({r["workload"] for r in rows}):
        sizes = sorted({r["size"] for r in rows if r["workload"] == wl})
        small, big = sizes[0], sizes[-1]
        e2 = AnalyticSizeEstimator.fit([r for r in rows if r["workload"] == wl and r["size"] == small], exponents)
        for pool in ("P", "E"):
            actual = statistics.median(r["kernel_s"] for r in rows
                                       if r["workload"] == wl and r["size"] == big and r["pool"] == pool)
            pred = e2.estimate(TaskSpec("x", wl, big), pool)
            ratio_meas = actual / statistics.median(r["kernel_s"] for r in rows
                                                    if r["workload"] == wl and r["size"] == small and r["pool"] == pool)
            out.append({"workload": wl, "pool": pool, "fit_size": small, "test_size": big,
                        "predicted_s": pred, "actual_median_s": actual, "rel_err": pred / actual - 1,
                        "measured_scaling": ratio_meas, "analytic_scaling": (big / small) ** exponents[wl]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase3.yaml")
    ap.add_argument("--e4", required=True, help="E4 model (occupancy+history)")
    ap.add_argument("--e4-ablation", default=None, help="E4 model (occupancy only)")
    ap.add_argument("--c1", default=None, help="earlier campaign dir (cross-session test)")
    ap.add_argument("--phase2", default=None, help="phase2 events dir (cross-session test)")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["estimators"]

    e4 = InterferenceRidgeEstimator.load(Path(args.e4))
    profile = Path(e4.base.source)
    ests = {
        "E0_constant": ConstantProfileEstimator.from_profile(profile),
        "E1_profile": StaticProfileEstimator.from_file(profile),
        "E2_analytic": AnalyticSizeEstimator.from_profile(profile, cfg["E2"]["exponents"], cfg["E2"]["fit_exponent"]),
        "E4_occ+hist": e4,
    }
    if args.e4_ablation:
        ests["E4_occ_only"] = InterferenceRidgeEstimator.load(Path(args.e4_ablation))

    holdout = set(e4.meta["holdout_runs"])
    test_sets = {"c2_holdout": [r for r in rows_from_dir(Path(e4.meta["campaign_dir"]), context_source="auto") if r["run_id"] in holdout]}
    if args.c1:
        test_sets["c1"] = rows_from_dir(Path(args.c1), context_source="auto")
    if args.phase2:
        test_sets["phase2"] = rows_from_dir(Path(args.phase2), context_source="auto")

    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    RESULTS.mkdir(parents=True, exist_ok=True)
    pred_path = RESULTS / f"phase3_{stamp}_predictions.csv"
    recs = []
    with pred_path.open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for ts, rows in test_sets.items():
            e5 = ReplayOracleEstimator.from_rows(rows) if ts == "phase2" else None
            runs: dict[str, list] = {}
            for r in rows:
                runs.setdefault(r["run_id"], []).append(r)
            for run_rows in runs.values():
                for r, name, pred in predict_run(run_rows, ests, cfg["E3"]["window"], profile, e5):
                    rec = {"test_set": ts, "run_id": r["run_id"], "task_id": r["task_id"], "workload": r["workload"],
                           "size": r["size"], "pool": r["pool"], "busy_P": r["ctx"].busy_P, "busy_E": r["ctx"].busy_E,
                           "busy_total": r["ctx"].busy_total, "target_busy_frac": r["ctx"].target_busy_frac,
                           "estimator": name, "actual_s": r["kernel_s"], "predicted_s": pred,
                           "ape": abs(pred - r["kernel_s"]) / r["kernel_s"],
                           "signed_rel_err": (pred - r["kernel_s"]) / r["kernel_s"]}
                    w.writerow(rec)
                    recs.append(rec)

    names = list(dict.fromkeys(x["estimator"] for x in recs))
    summary = {"overall": {}, "by_pool": {}, "by_occupancy": {}}
    for ts in test_sets:
        for n in names:
            sel = [x for x in recs if x["test_set"] == ts and x["estimator"] == n]
            if not sel:
                continue
            summary["overall"][f"{ts}|{n}"] = metrics(sel)
            for p in ("P", "E"):
                sp = [x for x in sel if x["pool"] == p]
                if sp:
                    summary["by_pool"][f"{ts}|{n}|{p}"] = metrics(sp)
            for b in ("0", "1-3", "4-6", "7-8"):
                sb = [x for x in sel if occ_bucket(x["busy_total"]) == b]
                if sb:
                    summary["by_occupancy"][f"{ts}|{n}|{b}"] = metrics(sb)
    summary["e2_size_extrapolation"] = e2_size_extrapolation(profile, cfg["E2"]["exponents"])
    (RESULTS / f"phase3_{stamp}_summary.json").write_text(json.dumps({
        "derived_from": pred_path.name, "e4_model": args.e4, "e4_ablation": args.e4_ablation, "profile": str(profile),
        "test_sets": {k: {"n_rows": len(v), "n_runs": len({r["run_id"] for r in v})} for k, v in test_sets.items()},
        **summary}, indent=1), encoding="utf-8")

    print(f"predictions -> {pred_path.name}")
    for ts, rows in test_sets.items():
        print(f"\n[{ts}] {len(rows)} tasks, {len({r['run_id'] for r in rows})} runs")
        print(f"  {'estimator':14s} {'medAPE':>7s} {'MAPE':>7s} {'p90APE':>7s} {'bias':>7s} {'MAE ms':>7s} |"
              f" {'medAPE P':>8s} {'medAPE E':>8s} | medAPE by co-runners 0 / 1-3 / 4-6 / 7-8")
        for n in names:
            m = summary["overall"].get(f"{ts}|{n}")
            if not m:
                continue
            bp = {p: summary["by_pool"].get(f"{ts}|{n}|{p}", {}).get("median_ape") for p in "PE"}
            bo = [summary["by_occupancy"].get(f"{ts}|{n}|{b}", {}).get("median_ape") for b in ("0", "1-3", "4-6", "7-8")]
            fmt = lambda v: f"{v * 100:5.1f}%" if v is not None else "   -  "
            print(f"  {n:14s} {fmt(m['median_ape']):>7s} {fmt(m['mape']):>7s} {fmt(m['p90_ape']):>7s} "
                  f"{m['median_signed'] * 100:+6.1f}% {m['mae_ms']:7.2f} | {fmt(bp['P']):>8s} {fmt(bp['E']):>8s} | "
                  + " / ".join(fmt(v) for v in bo))
    print("\nE2 size extrapolation (fit on smallest profiled size, predict largest; solo profile):")
    for x in summary["e2_size_extrapolation"]:
        print(f"  {x['workload']:12s} {x['pool']} {x['fit_size']}->{x['test_size']}: rel err {x['rel_err'] * 100:+6.1f}%  "
              f"(measured scaling x{x['measured_scaling']:.2f} vs analytic x{x['analytic_scaling']:.2f})")


if __name__ == "__main__":
    main()
