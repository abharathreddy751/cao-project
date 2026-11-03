"""Final study: write the oracle-cost files named by the ``heft_oracle`` conditions of an evaluation design (for ``HEFT_ORACLE_REF``).

  python scripts/final_oracle_rows.py <design.json> <calibration_session_dir> [<session_dir> ...]

Cost of a (stage, image size, denoise iterations, pool) class = the MEDIAN measured ``wall_time_seconds`` of that class over every completed
task of the given CALIBRATION sessions (warm-up block excluded; never an evaluation session). Rows are then written for every task of the
design's DAG (every chain order of the design, resource configuration of the condition) and every pool the task is eligible for, in the
row format ``CachedOracle`` reads. This is an oracle-INFORMED reference (best fixed per-class costs, no per-run noise), not a deployable
predictor. A class with no observation is a hard error (the oracle never guesses); the files are created exclusively.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from caosched.core.event_log import read_events
from caosched.experiment.design import load_design
from caosched.final.adapter import FinalAdapter


def class_key(workload: str, size: int, params: dict | None, pool: str) -> tuple:
    return (workload, int(size), (params or {}).get("iterations"), pool)


def class_medians(sessions) -> dict[tuple, float]:
    obs: dict[tuple, list[float]] = {}
    for s in sessions:
        for log in sorted(Path(s).glob("runs/*/*.jsonl")):
            if log.parent.name.startswith("b0000_"):
                continue
            ev = read_events(log)
            specs = next(e for e in ev if e["event"] == "run_started")["tasks"]
            for e in ev:
                if e["event"] == "task_completed":
                    sp = specs[e["task_id"]]
                    obs.setdefault(class_key(sp["workload"], sp["size"], sp.get("params"), e["pool"]), []).append(e["wall_time_seconds"])
    return {k: statistics.median(v) for k, v in obs.items()}


def dag_for(adapter: FinalAdapter, kw: dict):
    on = {s for s, v in (kw.get("gpu_stage_table") or {}).items() if v}
    gpu = bool(on) and not kw.get("no_gpu")
    return adapter.build_dag(kw, on if gpu else ())[0]


def main(design_path: str, sessions: list[str]) -> int:
    design = load_design(design_path)
    med = class_medians(sessions)
    adapter = FinalAdapter()
    missing: set = set()
    written = []
    for cond in design.conditions:
        kw = cond.kwargs
        if kw.get("binding") != "heft_oracle":
            continue
        out = Path(kw["oracle_rows"])
        if out.exists():
            sys.exit(f"{out} exists: refusing to overwrite")
        rows = []
        for inst in design.instances:
            k2 = {**kw, **({"order_seed": kw["order_seeds"][inst]} if inst is not None and kw.get("order_seeds") else {})}
            dag = dag_for(adapter, k2)
            for t in dag.tasks.values():
                for p in t.eligible_pools:
                    key = class_key(t.workload, t.size, t.params, p)
                    if key not in med:
                        missing.add(key)
                        continue
                    rows.append({"run_id": "class_median", "task_id": t.task_id, "seed": int(t.seed), "workload": t.workload,
                                 "size": int(t.size), "pool": p, "kernel_s": med[key]})
        if not missing:
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("x", encoding="utf-8") as fh:
                json.dump(rows, fh)
            written.append((str(out), len(rows)))
    if missing:
        print("classes with no calibration observation:", sorted(missing, key=str)[:20])
        return 1
    for p, n in written:
        print("wrote", p, n, "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
