"""Phase 0 gate analysis: turn raw benchmark CSV rows into a decision about
whether execution-time variation on this hardware justifies building out the
estimator ladder (E0-E4).

The "meaningful difference" threshold is fixed and documented here in advance.
It is never tuned after seeing results to manufacture a particular verdict --
if the data shows weak variation, the report says so.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "reports"

# A relative difference in mean wall-clock time below this threshold is
# considered "not meaningfully different" for the Phase 0 gate decision.
MEANINGFUL_RELATIVE_DIFFERENCE = 0.15


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["error"].isna() | (df["error"] == "")]
    df["wall_time_seconds"] = pd.to_numeric(df["wall_time_seconds"], errors="coerce")
    return df.dropna(subset=["wall_time_seconds"])


def summarize_k1(df: pd.DataFrame) -> list[dict]:
    """P vs E comparison per (workload, size)."""
    k1 = df[df["scenario"] == "K1"]
    out = []
    for (workload, size), group in k1.groupby(["workload", "size"]):
        p = group[group["pool"] == "P"]["wall_time_seconds"]
        e = group[group["pool"] == "E"]["wall_time_seconds"]
        if len(p) == 0 or len(e) == 0:
            continue
        p_mean, e_mean = float(p.mean()), float(e.mean())
        rel_diff = abs(p_mean - e_mean) / max(p_mean, e_mean)
        out.append({
            "workload": workload,
            "size": int(size),  # type: ignore[call-overload]  # pandas groupby keys are typed Hashable
            "p_mean_seconds": p_mean,
            "p_stdev_seconds": float(p.std()) if len(p) > 1 else 0.0,
            "p_n": int(len(p)),
            "e_mean_seconds": e_mean,
            "e_stdev_seconds": float(e.std()) if len(e) > 1 else 0.0,
            "e_n": int(len(e)),
            "relative_difference": rel_diff,
            "meaningful": bool(rel_diff >= MEANINGFUL_RELATIVE_DIFFERENCE),
            "faster_pool": "P" if p_mean < e_mean else "E",
        })
    return out


def summarize_k2(df: pd.DataFrame) -> list[dict]:
    """P-core task time as a function of concurrent E-core load level."""
    k2 = df[df["scenario"] == "K2"]
    out = []
    for (workload, size), group in k2.groupby(["workload", "size"]):
        by_load = group.groupby("num_load_procs")["wall_time_seconds"].agg(["mean", "std", "count"]).sort_index()
        if len(by_load) < 2:
            continue
        baseline = float(by_load["mean"].iloc[0])
        max_loaded = float(by_load["mean"].iloc[-1])
        rel_diff = abs(max_loaded - baseline) / max(baseline, max_loaded)
        out.append({
            "workload": workload,
            "size": int(size),  # type: ignore[call-overload]  # pandas groupby keys are typed Hashable
            "by_num_load_procs": {
                str(int(idx)): {  # type: ignore[call-overload]  # pandas groupby keys are typed Hashable
                    "mean_seconds": float(row["mean"]),
                    "stdev_seconds": float(row["std"]) if pd.notna(row["std"]) else 0.0,
                    "n": int(row["count"]),
                }
                for idx, row in by_load.iterrows()
            },
            "relative_difference_min_to_max_load": rel_diff,
            "meaningful": bool(rel_diff >= MEANINGFUL_RELATIVE_DIFFERENCE),
        })
    return out


def summarize_k5(df: pd.DataFrame) -> list[dict]:
    """P-core SMT sibling interference: alone vs. sibling-busy."""
    k5 = df[df["scenario"] == "K5"]
    out = []
    for (workload, size), group in k5.groupby(["workload", "size"]):
        alone = group[group["num_load_procs"] == 0]["wall_time_seconds"]
        busy = group[group["num_load_procs"] == 1]["wall_time_seconds"]
        if len(alone) == 0 or len(busy) == 0:
            continue
        alone_mean, busy_mean = float(alone.mean()), float(busy.mean())
        rel_diff = abs(busy_mean - alone_mean) / max(alone_mean, busy_mean)
        out.append({
            "workload": workload,
            "size": int(size),  # type: ignore[call-overload]  # pandas groupby keys are typed Hashable
            "alone_mean_seconds": alone_mean,
            "sibling_busy_mean_seconds": busy_mean,
            "relative_difference": rel_diff,
            "meaningful": bool(rel_diff >= MEANINGFUL_RELATIVE_DIFFERENCE),
        })
    return out


def build_gate_report(csv_path: Path) -> dict:
    df = load_csv(csv_path)
    k1 = summarize_k1(df)
    k2 = summarize_k2(df)
    k5 = summarize_k5(df)

    any_meaningful = any(r["meaningful"] for r in k1) or any(r["meaningful"] for r in k2) or any(r["meaningful"] for r in k5)

    if any_meaningful:
        verdict = (
            "Execution time varies meaningfully across P/E pools and/or load levels on "
            "this machine for at least one tested workload/size -- proceeding with "
            "estimator ladder development (E0-E4) is justified by the data."
        )
    else:
        verdict = (
            f"Execution time does NOT vary meaningfully (>= {MEANINGFUL_RELATIVE_DIFFERENCE:.0%} "
            "relative difference) across P/E pools or load levels for any tested "
            "workload/size on this machine. Recorded honestly: later phases should "
            "emphasize scheduling-policy and offload-overhead effects over "
            "execution-time prediction sophistication for this hardware/workload "
            "combination, rather than manufacturing an ML benefit that the data does "
            "not support."
        )

    return {
        "source_csv": str(csv_path),
        "meaningful_relative_difference_threshold": MEANINGFUL_RELATIVE_DIFFERENCE,
        "k1_pool_comparison": k1,
        "k2_load_interference": k2,
        "k5_smt_sibling_interference": k5,
        "any_meaningful_variation_found": any_meaningful,
        "verdict": verdict,
    }


def write_gate_report(csv_path: Path, output_dir: Path | None = None) -> Path:
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_gate_report(csv_path)
    output_path = output_dir / f"{csv_path.stem}_gate.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path
