"""Measure the end-to-end EFT ablation terms (setup and runtime overhead).

setup[workload, size, pool]  = median(worker_span_s - kernel_s), non-warmup
                               rows of the static-profile raw CSV
overhead[pool]               = either (--events) median over completed tasks in
                               the given event logs of (t_started - t_submitted)
                               + (t of task_completed event - t_completed)
                               - transfer_s (remote tasks), or (--overhead-from-profile)
                               median of roundtrip_s - worker_span_s - transfer_s
                               over the profile's non-warmup rows (solo conditions)

Link transfer is excluded from overhead in both modes: EFT models it
separately (transfer term), so it must not be counted twice.

Output: data/models/e2e_terms_<stamp>.json
Usage:  python scripts/derive_e2e_terms.py --profile PROFILE.json (--events DIR [DIR ...] | --overhead-from-profile)
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import statistics
from pathlib import Path

from caosched.core.event_log import read_events
from caosched.estimators.e2e import MODEL_DIR, EndToEndTerms


def setup_from_profile(profile_path: Path) -> dict:
    meta = json.loads(profile_path.read_text(encoding="utf-8"))
    groups: dict[tuple, list[float]] = {}
    with (profile_path.parent / meta["source_csv"]).open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["is_warmup"] == "True":
                continue
            key = (r["workload"], int(r["size"]), r["pool"])
            groups.setdefault(key, []).append(float(r["worker_span_s"]) - float(r["kernel_s"]))
    return {k: statistics.median(v) for k, v in groups.items()}


def overhead_from_events(dirs: list[Path]) -> tuple[dict, dict]:
    per_pool: dict[str, list[float]] = {}
    for d in dirs:
        for p in sorted(Path(d).glob("*.jsonl")):
            ev = read_events(p)
            submitted = {e["task_id"]: e["t"] for e in ev if e["event"] == "task_submitted"}
            for e in ev:
                if e["event"] == "task_completed" and e["task_id"] in submitted:
                    o = (e["t_started"] - submitted[e["task_id"]]) + (e["t"] - e["t_completed"])
                    o -= e.get("transfer_s") or 0.0
                    per_pool.setdefault(e["pool"], []).append(o)
    return ({p: statistics.median(v) for p, v in per_pool.items()},
            {p: {"n": len(v), "p10": sorted(v)[len(v) // 10], "p90": sorted(v)[9 * len(v) // 10]}
             for p, v in per_pool.items()})


def overhead_from_profile(profile_path: Path) -> tuple[dict, dict]:
    meta = json.loads(profile_path.read_text(encoding="utf-8"))
    per_pool: dict[str, list[float]] = {}
    with (profile_path.parent / meta["source_csv"]).open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["is_warmup"] == "True" or not r.get("roundtrip_s"):
                continue
            o = float(r["roundtrip_s"]) - float(r["worker_span_s"]) - float(r.get("transfer_s") or 0.0)
            per_pool.setdefault(r["pool"], []).append(o)
    if not per_pool:
        raise SystemExit(f"{profile_path} has no roundtrip_s column (profile predates Phase 5)")
    return ({p: statistics.median(v) for p, v in per_pool.items()},
            {p: {"n": len(v), "p10": sorted(v)[len(v) // 10], "p90": sorted(v)[9 * len(v) // 10]}
             for p, v in per_pool.items()})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--events", nargs="+")
    src.add_argument("--overhead-from-profile", action="store_true")
    args = ap.parse_args()
    profile = Path(args.profile)
    setup = setup_from_profile(profile)
    if args.overhead_from_profile:
        overhead, spread = overhead_from_profile(profile)
    else:
        overhead, spread = overhead_from_events([Path(d) for d in args.events])
    terms = EndToEndTerms(setup, overhead)
    out = MODEL_DIR / f"e2e_terms_{datetime.datetime.now():%Y%m%dT%H%M%S}.json"
    terms.save(out, {"profile": str(profile), "events": args.events,
                     "overhead_source": "profile (solo)" if args.overhead_from_profile else "event logs",
                     "overhead_spread": spread})
    print(f"-> {out.name}")
    print("setup (prepare) median ms:", {f"{w}|{s}|{p}": round(v * 1e3, 3) for (w, s, p), v in sorted(setup.items())})
    print("overhead median ms:", {p: round(v * 1e3, 3) for p, v in overhead.items()}, "spread:", spread)


if __name__ == "__main__":
    main()
