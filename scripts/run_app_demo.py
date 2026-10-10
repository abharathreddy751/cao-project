"""Application demo: the tiled image-analysis pipeline as a real multi-stage
DAG through the scheduler, on local P/E workers plus a remote node.

1. Profile the application's stages on this machine (pipeline runs pinned to
   each pool; kernel medians per (stage, size, pool) from the logs) ->
   data/profiles/<stamp>.appprofile.json (not matched by the benchmark
   '*_profile.json' glob). Link calibration is copied from the Phase 5 profile.
2. Run the pipeline under greedy B4 and under transfer-aware EFT_E1_rc
   (denoise / edges may run remotely); verify every final output against the
   single-process reference; print per-stage placement and timings.
   ``--repeats N``: N paired blocks, B4 and EFT in a seeded random order
   within each block; one row per run in data/results/appdemo_<stamp>_runs.csv
   and the session settings in ..._manifest.json (never overwritten).

``--denoise-iterations k`` sets the workload intensity (the denoise stage
applies its blur k times: compute x k, bytes moved unchanged); k = 1 is the
original application. Each invocation profiles its own stages, so the E1
estimator always matches the intensity being run.

Usage: python scripts/run_app_demo.py [--size 1024] [--grid 4] [--profile-runs 2]
                                      [--denoise-iterations 1] [--repeats 1] [--order-seed 0]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import json
import random
import statistics
from pathlib import Path

import psutil

from caosched.apps import build_image_pipeline, run_reference, verify_output
from caosched.apps.artifacts import artifact_path
from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
from caosched.core.event_log import DEFAULT_OUTPUT_DIR as EVENTS_DIR
from caosched.core.event_log import EventLogger, read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.worker_pool import RemoteSlot, WorkerPool
from caosched.estimators import RecalibratedEstimator, StaticProfileEstimator
from caosched.remote.link import LinkConfig, TransferModel
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.simple import GreedyEligibleScheduler, PoolOnlyScheduler

ROOT = Path(__file__).resolve().parents[1]
REMOTE = {"img_denoise": ["R"], "img_edges": ["R"]}
ALL_STAGES = ("img_source", "img_tile", "img_denoise", "img_edges", "img_features", "img_mosaic",
              "img_aggregate", "img_package")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--grid", type=int, default=4)
    ap.add_argument("--profile-runs", type=int, default=2)
    ap.add_argument("--node-core", type=int, default=11)
    ap.add_argument("--link-profile", default="data/profiles/20261003T152700_profile.json")
    ap.add_argument("--denoise-iterations", type=int, default=1)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--order-seed", type=int, default=0)
    ap.add_argument("--min-run-gib", type=float, default=0.5, help="stop (cleanly) before a run below this")
    args = ap.parse_args()
    avail = psutil.virtual_memory().available / 2**30
    if avail < 1.0:
        raise SystemExit(f"Refusing to start: {avail:.2f} GiB available (< 1.0 GiB)")
    rc = RuntimeConfig.from_topology()
    coord = pin_coordinator_to_reserved_core(rc)
    e_slots = [c for c in rc.e_core_slots if c != args.node_core]
    link = LinkConfig("lan_1g", latency_s=0.0002, bandwidth_Bps=125e6, per_message_s=0.00005)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    events = EVENTS_DIR / f"appdemo_{stamp}"
    art_root = ROOT / "data" / "artifacts" / f"appdemo_{stamp}"
    kw = dict(width=args.size, height=args.size, grid=args.grid, seed=11, denoise_iterations=args.denoise_iterations)
    ref = run_reference(build_image_pipeline(**kw))["package"]
    print(f"appdemo_{stamp}: pipeline {args.size}x{args.size}, grid {args.grid}, "
          f"denoise iterations {args.denoise_iterations}, repeats {args.repeats} "
          f"({len(build_image_pipeline(**kw))} tasks); coordinator core {coord}; P {list(rc.p_core_slots)}, "
          f"E {e_slots}, remote node on LP{args.node_core} behind {link.name}", flush=True)

    def run(pool, dag, policy, name):
        with EventLogger(name, output_dir=events) as log:
            s = Coordinator(dag, pool, policy, log, artifact_dir=art_root / name,
                            run_metadata={"experiment_id": f"appdemo_{stamp}", "app": "image_pipeline", **kw}).run(
                run_timeout=600)
        final = artifact_path(art_root / name, "package").read_bytes()
        return s, read_events(log.path), verify_output(final, ref)

    slots = [RemoteSlot(link, node_core=args.node_core, proxy_core=rc.coordinator_core)]
    with WorkerPool(list(rc.p_core_slots), e_slots, warmup=True, strict_affinity=True, remote_slots=slots) as pool:
        # ---- 1. stage profile (measured) ----
        kernels = collections.defaultdict(list)
        for k in range(args.profile_runs):
            for p in ("P", "E", "R"):
                dag = build_image_pipeline(**kw, remote_stages={st: ["R"] for st in ALL_STAGES})
                s, ev, v = run(pool, dag, PoolOnlyScheduler(p), f"profile_{p}_{k}")
                if v["match"] == "MISMATCH":
                    raise SystemExit(f"profile run on {p} produced a wrong output: {v}")
                for e in ev:
                    if e["event"] == "task_completed":
                        t = ev[0]["tasks"][e["task_id"]]
                        kernels[(t["workload"], t["size"], e["pool"])].append(e["wall_time_seconds"])
        cal = json.loads((ROOT / args.link_profile).read_text(encoding="utf-8"))["link_calibration"]
        prof = {"metric": "kernel_wall_time_seconds", "statistic": "median", "source": f"appdemo_{stamp} profile runs",
                "entries": [{"workload": w, "size": s_, "pool": p, "median_s": statistics.median(v), "n": len(v)}
                            for (w, s_, p), v in sorted(kernels.items())],
                "link_calibration": cal, "link_calibration_source": args.link_profile}
        prof_path = ROOT / "data" / "profiles" / f"{stamp}.appprofile.json"
        prof_path.write_text(json.dumps(prof, indent=1), encoding="utf-8")
        print(f"\nstage profile (measured, {args.profile_runs} runs per pool) -> {prof_path.name}")
        for e in prof["entries"]:
            print(f"  {e['workload']:14s} size {e['size']:>8d} {e['pool']}: {e['median_s'] * 1e3:8.3f} ms (n={e['n']})")

        # ---- 2. the application under two policies ----
        e1 = StaticProfileEstimator({(e["workload"], e["size"], e["pool"]): e["median_s"] for e in prof["entries"]},
                                    source=str(prof_path))
        tm = TransferModel({"R": link}, cal["socket_a_s"], cal["socket_b_s_per_byte"], args.link_profile)
        policies = {"B4_greedy_eligible_R": GreedyEligibleScheduler(priority=["P", "E", "R"],
                                                                    name="B4_greedy_eligible_R"),
                    "EFT_E1_rc_R": EarliestFinishTimeScheduler(RecalibratedEstimator(e1), "EFT_E1_rc_R", transfer=tm)}
        rng = random.Random(args.order_seed)
        rows, stop_reason = [], None
        for rep in range(args.repeats):
            order = list(policies)
            rng.shuffle(order)
            for k, name in enumerate(order):
                avail = psutil.virtual_memory().available / 2**30
                if avail < args.min_run_gib:
                    stop_reason = f"stopped before repeat {rep} run {k}: {avail:.2f} GiB available"
                    break
                run_name = f"demo_{name}" if args.repeats == 1 else f"demo_{name}_r{rep:02d}"
                s, ev, v = run(pool, build_image_pipeline(**kw, remote_stages=REMOTE), policies[name], run_name)
                done = [e for e in ev if e["event"] == "task_completed"]
                per = collections.Counter((ev[0]["tasks"][e["task_id"]]["workload"], e["pool"]) for e in done)
                tr = [e["transfer_s"] for e in done if e.get("transfer_s") is not None]
                rows.append({"repeat": rep, "order_index": k, "policy": name, "status": s.status,
                             "makespan_s": s.makespan_seconds, "scheduling_time_s": s.scheduling_time_seconds,
                             "n_tasks": len(done), "tasks_P": sum(1 for e in done if e["pool"] == "P"),
                             "tasks_E": sum(1 for e in done if e["pool"] == "E"), "tasks_R": len(tr),
                             "transfer_total_s": sum(tr), "output_match": v["match"], "output_sha256": v["sha256"],
                             "available_gib": round(avail, 3),
                             "event_log": f"data/events/appdemo_{stamp}/{run_name}.jsonl"})
                print(f"[r{rep:02d} {name}] {s.status}: makespan {s.makespan_seconds * 1e3:.1f} ms, "
                      f"output {v['match']} ({v['sha256'][:16]}), scheduling {s.scheduling_time_seconds * 1e3:.2f} ms,"
                      f" remote tasks {len(tr)}, transfer {sum(tr) * 1e3:.1f} ms, free {avail:.2f} GiB", flush=True)
                if args.repeats == 1:
                    for st in ALL_STAGES:
                        print(f"  {st:14s} " + "  ".join(f"{p}:{per[(st, p)]}" for p in ("P", "E", "R")
                                                         if per[(st, p)]))
            if stop_reason:
                print(stop_reason)
                break
    res = ROOT / "data" / "results"
    runs_csv, man = res / f"appdemo_{stamp}_runs.csv", res / f"appdemo_{stamp}_manifest.json"
    if runs_csv.exists() or man.exists():
        raise SystemExit("results for this stamp already exist; not overwriting")
    with open(runs_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["repeat"])
        w.writeheader()
        w.writerows(rows)
    man.write_text(json.dumps({"session": f"appdemo_{stamp}", "args": vars(args), "pipeline": kw,
                               "remote_stages": REMOTE, "link": link.to_dict(), "profile": prof_path.name,
                               "policies": list(policies), "runs_completed": len(rows),
                               "stop_reason": stop_reason}, indent=1), encoding="utf-8")
    print(f"\nevents -> {events.relative_to(ROOT)}; runs -> {runs_csv.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
