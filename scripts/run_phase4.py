"""Phase 4: predictive scheduling experiment with decision-regret analysis.

Stage A: for each repeat and trace, every online policy (reference
baselines + EFT with each estimator rung, with/without online
recalibration) runs in a seeded shuffled order on a fresh DAG from the same
saved trace, sharing one warm worker pool.
Stage B: O (EFT with the E5 replay oracle), whose table is built from the
stage-A runs of THIS session (Phase 3: cross-session data is biased).

Then every run is analysed from its event log: per-decision predicted vs
hindsight finish times and one-step regret (caosched.analysis.decisions),
with the E5 table built from all runs of this experiment, leave-run-out.

Outputs (raw first, summaries derived):
  data/events/phase4_<stamp>/*.jsonl
  data/results/phase4_<stamp>_manifest.json
  data/results/phase4_<stamp>_runs.csv
  data/results/phase4_<stamp>_decisions.csv
  data/results/phase4_<stamp>_summary.json

Usage:
    python scripts/run_phase4.py [--config config/phase4.yaml] [--repeats N]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import platform
import random
import statistics
import sys
from pathlib import Path

import yaml

from caosched.analysis.decisions import decision_rows
from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
from caosched.core.event_log import DEFAULT_OUTPUT_DIR as EVENTS_DIR
from caosched.core.event_log import EventLogger, read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.trace import dag_from_trace, load_or_create_trace
from caosched.core.worker_pool import WorkerPool
from caosched.dataset.events import rows_from_dir, rows_from_events
from caosched.estimators import ReplayOracleEstimator, latest_profile_path
from caosched.schedulers import eft_factories, oracle_factory, policy_factories

RESULTS = Path(__file__).resolve().parents[1] / "data" / "results"
RUN_FIELDS = ["stage", "repeat", "trace", "policy", "order_index", "status", "n_tasks", "makespan_s",
              "mean_response_s", "total_kernel_s", "tasks_P", "tasks_E", "event_log"]
DEC_FIELDS = ["stage", "repeat", "trace", "run_id", "policy", "task_id", "workload", "size", "chosen_worker",
              "chosen_pool", "actual_kernel_s", "bind_delay_s", "pred_exec", "pred_wait", "pred_finish", "pred_margin",
              "hind_best_worker", "hind_best_pool", "hind_best_finish", "hind_chosen_finish", "regret_s",
              "regret_rel", "optimal", "regret_ready_s", "n_candidates", "n_workers"]


def load_yaml(path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def run_one(pool, trace, policy, rep, idx, stage, exp_id, events_dir, timeout) -> dict:
    run_id = f"{trace['name']}__{policy.name}__r{rep}"
    with EventLogger(run_id, output_dir=events_dir) as logger:
        s = Coordinator(dag_from_trace(trace), pool, policy, logger,
                        run_metadata={"experiment_id": exp_id, "trace": trace["name"], "repeat": rep,
                                      "order_index": idx, "stage": stage}).run(run_timeout=timeout)
    return {"stage": stage, "repeat": rep, "trace": trace["name"], "policy": policy.name, "order_index": idx,
            "status": s.status, "n_tasks": s.n_tasks, "makespan_s": s.makespan_seconds,
            "mean_response_s": s.mean_response_time_seconds, "total_kernel_s": s.total_wall_time_seconds,
            "tasks_P": s.tasks_per_pool.get("P", 0), "tasks_E": s.tasks_per_pool.get("E", 0),
            "event_log": str(logger.path.relative_to(EVENTS_DIR.parent))}


def summarise(runs: list[dict], decisions: list[dict]) -> dict:
    out = {}
    for trace in dict.fromkeys(r["trace"] for r in runs):
        per = {}
        for pol in dict.fromkeys(r["policy"] for r in runs if r["trace"] == trace):
            ms = [r["makespan_s"] for r in runs if r["trace"] == trace and r["policy"] == pol]
            ds = [d for d in decisions if d["trace"] == trace and d["policy"] == pol and d.get("regret_s") is not None]
            pe = [abs(d["pred_exec"] - d["actual_kernel_s"]) / d["actual_kernel_s"]
                  for d in ds if d.get("pred_exec") is not None and d["actual_kernel_s"]]
            per[pol] = {
                "n_runs": len(ms), "makespan_median_s": statistics.median(ms),
                "makespan_min_s": min(ms), "makespan_max_s": max(ms),
                "tasks_P_median": statistics.median(r["tasks_P"] for r in runs if r["trace"] == trace and r["policy"] == pol),
                "n_decisions": len(ds),
                "regret_mean_ms": statistics.fmean(d["regret_s"] for d in ds) * 1e3 if ds else None,
                "regret_total_ms_per_run": (sum(d["regret_s"] for d in ds) * 1e3 / len(ms)) if ds else None,
                "optimal_frac": statistics.fmean(1.0 if d["optimal"] else 0.0 for d in ds) if ds else None,
                "bind_delay_mean_ms": statistics.fmean(d["bind_delay_s"] for d in ds) * 1e3 if ds else None,
                "regret_ready_mean_ms": statistics.fmean(d["regret_ready_s"] for d in ds) * 1e3 if ds else None,
                "chosen_pred_exec_median_ape": statistics.median(pe) if pe else None,
                "chosen_pred_exec_median_signed": statistics.median(
                    (d["pred_exec"] - d["actual_kernel_s"]) / d["actual_kernel_s"]
                    for d in ds if d.get("pred_exec") is not None and d["actual_kernel_s"]) if pe else None,
            }
        best = min(v["makespan_median_s"] for v in per.values())
        for v in per.values():
            v["makespan_vs_best"] = v["makespan_median_s"] / best
        out[trace] = per
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase4.yaml")
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--analyze-only", default=None, metavar="EXP_ID",
                    help="re-run only the log analysis of an existing experiment (no new runs)")
    args = ap.parse_args()
    if args.analyze_only:
        analyze(args.analyze_only)
        return
    cfg = load_yaml(args.config)
    exp = cfg["experiment"]
    repeats = args.repeats or exp["repeats"]
    est_cfg = {**load_yaml(cfg["estimator_config"])["estimators"], "rc": cfg["rc"]}
    profile = latest_profile_path()
    model = Path(cfg["e4_model"])

    factories = {}
    base = policy_factories(load_yaml(cfg["baseline_policy_config"])["policies"], profile)
    for name in cfg["policies"]["baselines"]:
        factories[name] = base[name]
    factories.update(eft_factories(cfg["policies"]["eft_estimators"], profile, est_cfg, model))
    traces = [load_or_create_trace(spec)[0] for spec in load_yaml(cfg["traces_from"])["traces"]]

    rc = RuntimeConfig.from_topology()
    coord_core = pin_coordinator_to_reserved_core(rc)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    exp_id = f"phase4_{stamp}"
    events_dir = EVENTS_DIR / exp_id
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(exp["order_seed"])
    (RESULTS / f"{exp_id}_manifest.json").write_text(json.dumps({
        "experiment_id": exp_id, "config": cfg, "estimator_config": est_cfg, "profile": str(profile),
        "e4_model": str(model), "policies_stage_A": list(factories), "oracle_stage_B": cfg["policies"]["oracle"],
        "repeats": repeats, "traces": [t["name"] for t in traces], "runtime_config": rc.to_dict(),
        "coordinator_core": coord_core, "python": sys.version, "platform": platform.platform(),
        "regret_definition": "one-step hindsight placement regret at bind time (primary), bind delay, ready-time regret (secondary); E5 leave-run-out (caosched.analysis.decisions)",
    }, indent=1), encoding="utf-8")
    print(f"{exp_id}: {len(traces)} traces x {len(factories)} policies x {repeats} repeats (+ O); profile {profile.name}")

    runs: list[dict] = []
    runs_path = RESULTS / f"{exp_id}_runs.csv"
    with WorkerPool.from_config(rc, warmup=True, strict_affinity=True) as pool, \
            runs_path.open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RUN_FIELDS)
        w.writeheader()
        for rep in range(repeats):
            for trace in traces:
                order = list(factories)
                rng.shuffle(order)
                for idx, name in enumerate(order):
                    row = run_one(pool, trace, factories[name](), rep, idx, "A", exp_id, events_dir, exp["run_timeout_s"])
                    w.writerow(row)
                    fh.flush()
                    runs.append(row)
            print(f"  stage A repeat {rep + 1}/{repeats} done")
        if cfg["policies"]["oracle"]:
            make_o = oracle_factory(rows_from_dir(events_dir, context_source="auto"))
            for rep in range(repeats):
                for trace in traces:
                    row = run_one(pool, trace, make_o(), rep, 0, "B", exp_id, events_dir, exp["run_timeout_s"])
                    w.writerow(row)
                    fh.flush()
                    runs.append(row)
            print("  stage B (oracle) done")

    analyze(exp_id)


def analyze(exp_id: str) -> None:
    """Decision / regret analysis of an experiment, from its logs only.
    Re-running it writes new timestamped derived files; raw data is untouched."""
    events_dir = EVENTS_DIR / exp_id
    runs = []
    with (RESULTS / f"{exp_id}_runs.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            r["makespan_s"] = float(r["makespan_s"])
            r["tasks_P"] = int(r["tasks_P"])
            runs.append(r)
    tag = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    logs = {p: read_events(p) for p in sorted(events_dir.glob("*.jsonl"))}
    all_rows = [r for ev in logs.values() for r in rows_from_events(ev, context_source="auto")]
    oracle = ReplayOracleEstimator.from_rows(all_rows)
    decisions = []
    dec_path = RESULTS / f"{exp_id}_decisions_{tag}.csv"
    with dec_path.open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=DEC_FIELDS, extrasaction="ignore")
        w.writeheader()
        for ev in logs.values():
            meta = ev[0].get("metadata") or {}
            oracle.exclude_run(ev[0]["run_id"])
            for d in decision_rows(ev, oracle):
                d.update(stage=meta.get("stage"), repeat=meta.get("repeat"), trace=meta.get("trace"))
                w.writerow(d)
                decisions.append(d)

    summary = summarise(runs, decisions)
    (RESULTS / f"{exp_id}_summary_{tag}.json").write_text(json.dumps(
        {"experiment_id": exp_id, "derived_from": [f"{exp_id}_runs.csv", dec_path.name], "summary": summary}, indent=1),
        encoding="utf-8")
    for trace, per in summary.items():
        print(f"\n[{trace}] makespan median (ms) [min-max] x best | P tasks | placement regret ms/decision"
              f" | optimal | bind delay ms | ready-regret ms | chosen-exec medAPE (bias)")
        for pol, v in sorted(per.items(), key=lambda kv: kv[1]["makespan_median_s"]):
            ape, sg = v["chosen_pred_exec_median_ape"], v["chosen_pred_exec_median_signed"]
            print(f"  {pol:19s} {v['makespan_median_s'] * 1e3:7.1f} [{v['makespan_min_s'] * 1e3:6.1f}-"
                  f"{v['makespan_max_s'] * 1e3:6.1f}] x{v['makespan_vs_best']:.2f} | P {v['tasks_P_median']:4g} | "
                  f"{v['regret_mean_ms']:6.2f} | {v['optimal_frac'] * 100:5.1f}% | {v['bind_delay_mean_ms']:7.1f} | "
                  f"{v['regret_ready_mean_ms']:7.1f} | "
                  + (f"{ape * 100:5.1f}% ({sg * 100:+.0f}%)" if ape is not None else "  -"))


if __name__ == "__main__":
    main()
