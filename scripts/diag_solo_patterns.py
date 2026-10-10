"""Phase 3 diagnostic: does a task running ALONE take longer when its core
runs tasks back-to-back than when consecutive tasks hop between cores (the
static profile's pattern)? Motivated by the campaign finding that truly solo
P-core tasks ran 1.2-1.4x their profile time while E-core tasks did not.

Conditions (one task in flight machine-wide in all of them), in a randomized
order within each block:
  interleaved      each task on a random worker of all 9 (profile-like)
  b2b_P0 / b2b_E0  every task on the same worker, back to back
  gap_P0           same as b2b_P0 but the coordinator idles `gap_s` between tasks

Raw output: data/diagnostics/solo_patterns_<stamp>.csv (+ _meta.json).
Usage:  python scripts/diag_solo_patterns.py [--blocks 3] [--tasks 20] [--gap 0.05]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import platform
import random
import statistics
import time
from pathlib import Path

import psutil

from caosched.core.coordinator import pin_coordinator_to_reserved_core
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.task import TaskMessage
from caosched.core.worker_pool import WorkerPool
from caosched.estimators import StaticProfileEstimator, latest_profile_path

OUT = Path(__file__).resolve().parents[1] / "data" / "diagnostics"
TASKS = [("matmul", 512), ("image_filter", 512), ("compression", 1048576)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=3)
    ap.add_argument("--tasks", type=int, default=20)
    ap.add_argument("--gap", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()

    rc = RuntimeConfig.from_topology()
    core = pin_coordinator_to_reserved_core(rc)
    prof_path = latest_profile_path()
    e1 = StaticProfileEstimator.from_file(prof_path)
    rng = random.Random(args.seed)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / f"solo_patterns_{stamp}.csv"
    bat = psutil.sensors_battery()
    (OUT / f"solo_patterns_{stamp}_meta.json").write_text(json.dumps({
        "args": vars(args), "profile": str(prof_path), "coordinator_core": core,
        "power_plugged": None if bat is None else bat.power_plugged, "platform": platform.platform(),
    }, indent=1), encoding="utf-8")

    rows = []
    with WorkerPool.from_config(rc, warmup=True, strict_affinity=True) as pool, \
            csv_path.open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["block", "condition", "idx", "workload", "size", "worker_id", "pool",
                                           "kernel_s", "profile_s", "ratio"])
        w.writeheader()
        workers = pool.worker_ids()
        for block in range(args.blocks):
            conds = ["interleaved", "b2b_P0", "b2b_E0", "gap_P0"]
            rng.shuffle(conds)
            for cond in conds:
                for i in range(args.tasks):
                    wl, size = TASKS[i % len(TASKS)]
                    wid = rng.choice(workers) if cond == "interleaved" else cond.split("_")[1]
                    if cond == "gap_P0":
                        time.sleep(args.gap)
                    pool.submit(wid, TaskMessage(f"{block}_{cond}_{i}", wl, size, 7000 + i))
                    res = pool.poll_result(timeout=120)
                    if res is None or res.error:
                        raise SystemExit(f"failed: {res and res.error}")
                    p = pool.pool_of(wid)
                    ps = e1.lookup(wl, size, p)
                    row = {"block": block, "condition": cond, "idx": i, "workload": wl, "size": size,
                           "worker_id": wid, "pool": p, "kernel_s": res.wall_time_seconds, "profile_s": ps,
                           "ratio": res.wall_time_seconds / ps}
                    w.writerow(row)
                    rows.append(row)
                fh.flush()

    print(f"raw -> {csv_path.name}   (power plugged: {None if bat is None else bat.power_plugged})")
    print("kernel / solo-profile ratio, median [p10, p90] (n):")
    for cond in ("interleaved", "b2b_P0", "gap_P0", "b2b_E0"):
        for p in ("P", "E"):
            v = sorted(r["ratio"] for r in rows if r["condition"] == cond and r["pool"] == p)
            if v:
                print(f"  {cond:12s} {p}: {statistics.median(v):.3f} [{v[len(v) // 10]:.3f}, {v[9 * len(v) // 10]:.3f}] (n={len(v)})")


if __name__ == "__main__":
    main()
