"""Phase 2: replay the configured workload traces under every baseline policy
(B0-B7) on the real P/E worker pools.

For each repeat and each trace, the policy order is shuffled with a seeded
RNG (recorded), and every policy runs on a *fresh* DAG built from the same
saved trace, with a fresh policy/estimator instance. One warm worker pool is
shared by all runs (worker cold-start is paid once, in the startup
handshake, and recorded).

Outputs (raw first; the summary is derived from the runs CSV afterwards):
  data/results/phase2_<stamp>_manifest.json  config, profile, traces, environment
  data/results/phase2_<stamp>_runs.csv       one row per (repeat, trace, policy) run
  data/events/phase2_<stamp>/*.jsonl         full event log of every run
  data/results/phase2_<stamp>_summary.json   per (trace, policy) statistics

Usage:
    python scripts/run_baselines.py [--config config/phase2.yaml] [--profile PATH]
                                    [--repeats N] [--policies B1_round_robin,B6_eft_static]
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

from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
from caosched.core.event_log import DEFAULT_OUTPUT_DIR as EVENTS_DIR
from caosched.core.event_log import EventLogger
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.trace import dag_from_trace, load_or_create_trace
from caosched.core.worker_pool import WorkerPool
from caosched.estimators.profile import latest_profile_path
from caosched.schedulers import ALL_POLICIES, policy_factories

RESULTS_DIR = Path(__file__).resolve().parents[1] / "data" / "results"
FIELDS = ["repeat", "trace", "policy", "order_index", "status", "n_tasks", "makespan_s", "mean_response_s",
          "total_kernel_s", "tasks_P", "tasks_E", "event_log"]


def summarise(rows: list[dict]) -> dict:
    out: dict = {}
    for trace in dict.fromkeys(r["trace"] for r in rows):
        ok = [r for r in rows if r["trace"] == trace and r["status"] == "completed"]
        per_policy = {}
        for pol in dict.fromkeys(r["policy"] for r in ok):
            ms = [r["makespan_s"] for r in ok if r["policy"] == pol]
            rt = [r["mean_response_s"] for r in ok if r["policy"] == pol]
            per_policy[pol] = {
                "n_runs": len(ms), "makespan_median_s": statistics.median(ms),
                "makespan_min_s": min(ms), "makespan_max_s": max(ms),
                "mean_response_median_s": statistics.median(rt),
                "tasks_P_median": statistics.median(r["tasks_P"] for r in ok if r["policy"] == pol),
            }
        best = min(v["makespan_median_s"] for v in per_policy.values())
        for v in per_policy.values():
            v["makespan_vs_best"] = v["makespan_median_s"] / best
        out[trace] = per_policy
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase2.yaml")
    ap.add_argument("--profile", default=None, help="profile JSON (default: newest in data/profiles)")
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--policies", default=None, help="comma-separated subset of policy names")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    exp = cfg["experiment"]
    repeats = args.repeats or exp["repeats"]
    names = args.policies.split(",") if args.policies else (
        list(ALL_POLICIES) if exp["policies"] == "all" else list(exp["policies"]))
    unknown = sorted(set(names) - set(ALL_POLICIES))
    if unknown:
        raise SystemExit(f"Unknown policies: {unknown}")
    profile_path = Path(args.profile) if args.profile else latest_profile_path()
    factories = policy_factories(cfg["policies"], profile_path)
    traces = [load_or_create_trace(spec) for spec in cfg["traces"]]

    rc = RuntimeConfig.from_topology()
    coord_core = pin_coordinator_to_reserved_core(rc)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    exp_id = f"phase2_{stamp}"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    events_dir = EVENTS_DIR / exp_id
    rng = random.Random(exp["order_seed"])

    manifest = {
        "experiment_id": exp_id, "config_path": args.config, "config": cfg, "policies": names,
        "repeats": repeats, "profile": str(profile_path),
        "traces": {tr["name"]: {"path": str(p), "n_tasks": len(tr["tasks"])} for tr, p in traces},
        "runtime_config": rc.to_dict(), "coordinator_core": coord_core,
        "python": sys.version, "platform": platform.platform(),
        "execution_time_definition": "kernel-only (wall_time_seconds)",
    }
    (RESULTS_DIR / f"{exp_id}_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    runs_path = RESULTS_DIR / f"{exp_id}_runs.csv"
    print(f"{exp_id}: {len(traces)} traces x {len(names)} policies x {repeats} repeats; profile {profile_path.name}")

    rows: list[dict] = []
    with WorkerPool.from_config(rc, warmup=True, strict_affinity=True) as pool, \
            runs_path.open("x", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for rep in range(repeats):
            for trace, _ in traces:
                order = list(names)
                rng.shuffle(order)
                for idx, pol in enumerate(order):
                    run_id = f"{trace['name']}__{pol}__r{rep}"
                    with EventLogger(run_id, output_dir=events_dir) as logger:
                        coord = Coordinator(dag_from_trace(trace), pool, factories[pol](), logger,
                                            run_metadata={"experiment_id": exp_id, "trace": trace["name"],
                                                          "repeat": rep, "order_index": idx})
                        s = coord.run(run_timeout=exp["run_timeout_s"])
                    row = {"repeat": rep, "trace": trace["name"], "policy": pol, "order_index": idx,
                           "status": s.status, "n_tasks": s.n_tasks, "makespan_s": s.makespan_seconds,
                           "mean_response_s": s.mean_response_time_seconds,
                           "total_kernel_s": s.total_wall_time_seconds,
                           "tasks_P": s.tasks_per_pool.get("P", 0), "tasks_E": s.tasks_per_pool.get("E", 0),
                           "event_log": str(logger.path.relative_to(EVENTS_DIR.parent))}
                    writer.writerow(row)
                    fh.flush()
                    rows.append(row)
                print(f"  repeat {rep + 1}/{repeats} trace {trace['name']} done")

    summary = summarise(rows)
    (RESULTS_DIR / f"{exp_id}_summary.json").write_text(
        json.dumps({"experiment_id": exp_id, "derived_from": runs_path.name, "summary": summary}, indent=1),
        encoding="utf-8")
    for trace, per in summary.items():
        print(f"\n[{trace}]  median makespan over {repeats} repeats (ms)  [min-max]  x best  | tasks on P")
        for pol, v in sorted(per.items(), key=lambda kv: kv[1]["makespan_median_s"]):
            print(f"  {pol:20s} {v['makespan_median_s'] * 1e3:9.1f}  [{v['makespan_min_s'] * 1e3:7.1f}-"
                  f"{v['makespan_max_s'] * 1e3:7.1f}]  x{v['makespan_vs_best']:.2f}  | P {v['tasks_P_median']:g}")


if __name__ == "__main__":
    main()
