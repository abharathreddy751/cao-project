"""Study 2: build the replay-oracle table (E5 rows) from the event logs of EARLIER sessions and report its coverage.

One row per completed task of every run outside warm-up block 0: {run_id, task_id, seed, workload, size, pool, kernel_s}
(kernel_s = ``wall_time_seconds`` of ``task_completed``). The table is never built from the session it is later applied to
(protocol section 14 names the sessions). Coverage: every (task, eligible pool) of the study 2 batch DAG, with and without G,
must have at least one logged run, else the oracle would raise KeyError mid-run; the script exits 1 and lists what is missing.

  python scripts/study2_oracle_rows.py <out.json> <session_dir> [<session_dir> ...]
  python scripts/study2_oracle_rows.py <out.json> --mix <small_n,small_side,big_n,big_side> --orders <seed,seed> <session_dir> ...
    (heavy-tailed batch, protocol section 17: coverage is checked on the CPU-only DAG of every order seed)
  python scripts/study2_oracle_rows.py <out.json> --iters <small_n,small_iters,big_n,big_iters> --orders <seed,seed> <session_dir> ...
    (hidden-cost batch, protocol section 18)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from caosched.core.event_log import read_events
from caosched.study2.workload import build_batch, build_iters, build_mixed


def main(out: str, sessions: list[str], mix: list[int] | None = None, orders: list[int] | None = None,
         iters: list[int] | None = None) -> int:
    if Path(out).exists():
        sys.exit(f"{out} exists: refusing to overwrite")
    rows = []
    for s in sessions:
        for log in sorted(Path(s).glob("runs/*/*.jsonl")):
            if log.parent.name.startswith("b0000_"):
                continue
            ev = read_events(log)
            specs = next(e for e in ev if e["event"] == "run_started")["tasks"]
            for e in ev:
                if e["event"] == "task_completed":
                    sp = specs[e["task_id"]]
                    rows.append({"run_id": f"{log.parent.name}", "task_id": e["task_id"], "seed": sp["seed"],
                                 "workload": sp["workload"], "size": sp["size"], "pool": e["pool"],
                                 "kernel_s": e["wall_time_seconds"]})
    have = {(r["task_id"], int(r["seed"]), r["workload"], int(r["size"]), r["pool"]) for r in rows}
    missing = []
    dags = ([build_iters([iters[0], iters[1]], [iters[2], iters[3]], order_seed=o) for o in orders or [0]] if iters else
            [build_mixed([mix[0], mix[1]], [mix[2], mix[3]], order_seed=o) for o in orders or [0]] if mix
            else [build_batch(gpu_stages=gpu) for gpu in (("img_denoise", "img_edges", "img_features"), ())])
    for dag in dags:
        for t in dag.tasks.values():
            for p in t.eligible_pools:
                if (t.task_id, int(t.seed), t.est_workload, int(t.est_size), p) not in have:
                    missing.append((t.task_id, p))
    print(f"{len(rows)} rows from {len(sessions)} sessions; missing (task, pool) pairs: {len(set(missing))}")
    if missing:
        print(sorted(set(missing))[:20])
        return 1
    with Path(out).open("x", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    mix = [int(x) for x in a[a.index("--mix") + 1].split(",")] if "--mix" in a else None
    orders = [int(x) for x in a[a.index("--orders") + 1].split(",")] if "--orders" in a else None
    iters = [int(x) for x in a[a.index("--iters") + 1].split(",")] if "--iters" in a else None
    flags = ("--mix", "--orders", "--iters")
    rest = [x for i, x in enumerate(a[1:], 1) if x not in flags and (i < 2 or a[i - 1] not in flags)]
    sys.exit(main(a[0], rest, mix, orders, iters))
