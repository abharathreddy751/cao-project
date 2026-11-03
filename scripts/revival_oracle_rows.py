"""Revival: build the E5 replay-oracle table for the mixed-DAG workload from ISOLATED (no contention) coverage sessions.

One row per completed task of every run outside warm-up block 0, as ``study2_oracle_rows.py``; coverage is checked on the DAG of every
instance the oracle will be applied to (every task x eligible pool needs at least one logged run, else the oracle would raise mid-run).

  python scripts/revival_oracle_rows.py <out.json> <design.json with the gate instances> <session_dir> [<session_dir> ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from caosched.core.event_log import read_events
from caosched.revival.workload import build_dyn


def main(out: str, design: str, sessions: list[str]) -> int:
    if Path(out).exists():
        sys.exit(f"{out} exists: refusing to overwrite")
    d = json.loads(Path(design).read_text(encoding="utf-8"))
    kw = d["conditions"][0]["kwargs"]
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
                    rows.append({"run_id": log.parent.name, "task_id": e["task_id"], "seed": sp["seed"], "workload": sp["workload"],
                                 "size": sp["size"], "pool": e["pool"], "kernel_s": e["wall_time_seconds"]})
    have = {(r["task_id"], int(r["seed"]), r["workload"], int(r["size"]), r["pool"]) for r in rows}
    missing = set()
    for name, spec in kw["instances_spec"].items():
        dag = build_dyn(kw["dyn"]["classes"], kw["dyn"]["groups"], kw["dyn"]["seed"], 2.0, (), "G", spec["order_seed"])
        for t in dag.tasks.values():
            for p in t.eligible_pools or ():
                if (t.task_id, int(t.seed), t.est_workload, int(t.est_size), p) not in have:
                    missing.add((name, t.task_id, p))
    print(f"{len(rows)} rows from {len(sessions)} sessions; missing (instance, task, pool): {len(missing)}")
    if missing:
        print(sorted(missing)[:20])
        return 1
    with Path(out).open("x", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[0], a[1], a[2:]))
