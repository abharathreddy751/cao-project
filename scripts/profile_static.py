"""Phase 2: measure the static execution-time profile used by E1 (B6/B7's
prior) on this machine.

Every (workload, size) is run *solo* (exactly one task in flight
machine-wide) on every worker slot of the real P/E pools, for
warmup_rounds + repeat_rounds rounds, in a seeded random order per round.
Recorded metric is kernel-only time (``wall_time_seconds``).

Outputs (raw first, summary derived from it):
  data/profiles/<stamp>_raw.csv        one row per measurement (incl. warmups)
  data/profiles/<stamp>_profile.json   per (workload, size, pool) statistics

With ``--remote-node-core C`` (Phase 5) a remote slot R0 is added: a node
process on logical processor C (removed from the E slots) reached through the
link shim configured to ZERO delay, so every R row measures the node's
kernel/span plus the *real* socket transfer cost of its payload. The profile
JSON then also carries ``link_calibration``: a least-squares fit
transfer_s = a + b * payload_bytes over the non-warmup R rows (the measured
serialization/transfer overhead of the mechanism itself).

Every row also records ``roundtrip_s`` = coordinator submit -> result
received, so per-task runtime overhead = roundtrip - worker span - transfer.

Usage:
    python scripts/profile_static.py [--config config/phase2.yaml]
        [--remote-node-core 11 --proxy-core 4]
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

from caosched.core.coordinator import pin_coordinator_to_reserved_core
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.task import TaskMessage
from caosched.core.worker_pool import RemoteSlot, WorkerPool
from caosched.estimators.profile import PROFILE_DIR
from caosched.remote.link import LinkConfig
from caosched.util import clock

FIELDS = ["round", "is_warmup", "workload", "size", "seed", "worker_id", "pool", "logical_processor",
          "kernel_s", "worker_span_s", "transfer_s", "payload_bytes", "roundtrip_s"]


def fit_link_calibration(rows: list[dict]) -> dict | None:
    pts = [(r["payload_bytes"], r["transfer_s"]) for r in rows
           if not r["is_warmup"] and r.get("transfer_s") not in (None, "")]
    if len(pts) < 2:
        return None
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    b = sum((x - mx) * (y - my) for x, y in pts) / sxx if sxx > 0 else 0.0
    a = my - b * mx
    resid = sorted(abs(y - (a + b * x)) for x, y in pts)
    return {"socket_a_s": a, "socket_b_s_per_byte": b, "n": len(pts),
            "median_abs_residual_s": resid[len(resid) // 2], "shim": "zero (no emulated delay)"}


def _quantile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summarise(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        if not r["is_warmup"]:
            groups.setdefault((r["workload"], r["size"], r["pool"]), []).append(r)
    out = []
    for (wl, size, pool), rs in sorted(groups.items()):
        ks = [r["kernel_s"] for r in rs]
        per_worker = {}
        for r in rs:
            per_worker.setdefault(r["worker_id"], []).append(r["kernel_s"])
        out.append({
            "workload": wl, "size": size, "pool": pool, "n": len(ks),
            "median_s": statistics.median(ks), "mean_s": statistics.fmean(ks),
            "stdev_s": statistics.stdev(ks) if len(ks) > 1 else 0.0,
            "p10_s": _quantile(ks, 0.10), "p90_s": _quantile(ks, 0.90),
            "min_s": min(ks), "max_s": max(ks),
            "per_worker_median_s": {w: statistics.median(v) for w, v in sorted(per_worker.items())},
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase2.yaml")
    ap.add_argument("--remote-node-core", type=int, default=None)
    ap.add_argument("--proxy-core", type=int, default=None)
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["profile"]

    rc = RuntimeConfig.from_topology()
    remote_slots = []
    if args.remote_node_core is not None:
        if args.remote_node_core not in rc.e_core_slots:
            raise SystemExit(f"--remote-node-core must be one of the E slots {rc.e_core_slots}")
        rc = RuntimeConfig(rc.p_core_slots, tuple(c for c in rc.e_core_slots if c != args.remote_node_core),
                           rc.coordinator_core)
        remote_slots = [RemoteSlot(LinkConfig("zero"), node_core=args.remote_node_core, proxy_core=args.proxy_core)]
    coord_core = pin_coordinator_to_reserved_core(rc)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = PROFILE_DIR / f"{stamp}_raw.csv"
    prof_path = PROFILE_DIR / f"{stamp}_profile.json"

    combos = [(wl, int(s)) for wl, sizes in cfg["workloads"].items() for s in sizes]
    rng = random.Random(cfg["order_seed"])
    n_rounds = cfg["warmup_rounds"] + cfg["repeat_rounds"]
    rows: list[dict] = []

    with WorkerPool.from_config(rc, warmup=True, strict_affinity=True, remote_slots=remote_slots) as pool, \
            raw_path.open("x", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        workers = pool.worker_ids()
        lp = {w.worker_id: (w.affinity[0] if w.affinity else None) for w in pool.workers.values()}
        total = n_rounds * len(combos) * len(workers)
        print(f"Coordinator core {coord_core}; {len(workers)} workers; {total} solo measurements -> {raw_path.name}")
        done = 0
        for rnd in range(n_rounds):
            order = [(wl, s, w) for wl, s in combos for w in workers]
            rng.shuffle(order)
            seed = cfg["input_seed_base"] + rnd
            for wl, size, wid in order:
                t_sub = clock.now()
                pool.submit(wid, TaskMessage(f"r{rnd}_{wl}_{size}_{wid}", wl, size, seed))
                res = pool.poll_result(timeout=300)
                t_back = clock.now()
                if res is None or res.error:
                    raise SystemExit(f"Measurement failed for {wl}/{size} on {wid}: {res and res.error}")
                row = {"round": rnd, "is_warmup": rnd < cfg["warmup_rounds"], "workload": wl, "size": size,
                       "seed": seed, "worker_id": wid, "pool": pool.pool_of(wid), "logical_processor": lp[wid],
                       "kernel_s": res.wall_time_seconds, "worker_span_s": res.t_completed - res.t_started,
                       "transfer_s": res.transfer_s, "payload_bytes": res.payload_bytes,
                       "roundtrip_s": t_back - t_sub}
                writer.writerow(row)
                rows.append(row)
                done += 1
            fh.flush()
            print(f"  round {rnd + 1}/{n_rounds} done ({done}/{total})")

    entries = summarise(rows)
    prof_path.write_text(json.dumps({
        "schema_version": 1,
        "metric": "kernel_wall_time_seconds",
        "statistic": "median",
        "conditions": "solo (one task in flight machine-wide), warm persistent workers",
        "generated_at": stamp,
        "source_csv": raw_path.name,
        "config": cfg,
        "runtime_config": rc.to_dict(),
        "coordinator_core": coord_core,
        "python": sys.version,
        "platform": platform.platform(),
        "remote_node_core": args.remote_node_core,
        "link_calibration": fit_link_calibration(rows),
        "entries": entries,
    }, indent=1), encoding="utf-8")

    print(f"\nProfile -> {prof_path.name}")
    print(f"{'workload':13s} {'size':>8s} {'P median':>10s} {'E median':>10s} {'E/P':>6s}  (ms; n per pool)")
    by = {(e["workload"], e["size"], e["pool"]): e for e in entries}
    for wl, s in combos:
        p, e = by[(wl, s, "P")], by[(wl, s, "E")]
        r = by.get((wl, s, "R"))
        print(f"{wl:13s} {s:>8d} {p['median_s'] * 1e3:10.3f} {e['median_s'] * 1e3:10.3f} "
              f"{e['median_s'] / p['median_s']:6.2f}  (P n={p['n']}, E n={e['n']})"
              + (f"  R {r['median_s'] * 1e3:.3f} ms (n={r['n']})" if r else ""))
    cal = fit_link_calibration(rows)
    if cal:
        print(f"link calibration (shim zero): transfer = {cal['socket_a_s'] * 1e3:.3f} ms + "
              f"{cal['socket_b_s_per_byte'] * 1e9:.3f} ns/byte  (n={cal['n']}, "
              f"median |resid| {cal['median_abs_residual_s'] * 1e3:.3f} ms)")


if __name__ == "__main__":
    main()
