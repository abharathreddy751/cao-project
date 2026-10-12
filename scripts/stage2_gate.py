"""Stage 2 gate check from raw run logs [real]: every run completed, output verified, dependencies respected, no worker ran two
tasks at once, no ineligible placement, plus a per-condition makespan table (descriptive only).

  python scripts/stage2_gate.py <session_dir> <out.json>
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path


def check_run(events: list[dict], manifest: dict) -> dict:
    start = next(e for e in events if e["event"] == "run_started")
    fin = next((e for e in events if e["event"] == "run_finished"), {})
    done = {e["task_id"]: e for e in events if e["event"] == "task_completed"}
    disp = {e["task_id"]: e for e in events if e["event"] == "task_dispatched"}
    elig = {t: spec.get("eligible_pools") for t, spec in (start.get("tasks") or {}).items()}
    dep_viol = [(a, b) for a, b in start.get("edges", []) if a in done and b in done and done[b]["t_started"] < done[a]["t_completed"]]
    by_worker = collections.defaultdict(list)
    for e in done.values():
        by_worker[e["worker_id"]].append((e["t_started"], e["t_completed"], e["task_id"]))
    overlaps = [(w, x[2], y[2]) for w, iv in by_worker.items() for x, y in zip(sorted(iv), sorted(iv)[1:]) if y[0] < x[1]]
    inelig = [t for t, e in disp.items() if elig.get(t) is not None and e["pool"] not in elig[t]]
    return {"completed": fin.get("status") == "completed" and fin.get("n_completed") == start["n_tasks"] == len(done),
            "n_tasks": start["n_tasks"], "dependency_violations": dep_viol, "worker_overlaps": overlaps,
            "ineligible_placements": inelig, "makespan_s": fin.get("makespan_seconds"),
            "output_verified": bool((manifest.get("verification") or {}).get("passed")),
            "tasks_per_pool": fin.get("tasks_per_pool")}


def main(session: str, out: str) -> int:
    runs = {}
    for m in sorted(Path(session).glob("runs/*/run_manifest.json")):
        man = json.loads(m.read_text(encoding="utf-8"))
        log = next(m.parent.glob("*.jsonl"))
        events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        cond = man["condition"]["name"] if isinstance(man.get("condition"), dict) else man.get("condition")
        runs[m.parent.name] = {"condition": cond, **check_run(events, man)}
    bad = {r: v for r, v in runs.items() if not (v["completed"] and v["output_verified"] and not v["dependency_violations"]
                                                 and not v["worker_overlaps"] and not v["ineligible_placements"])}
    table = collections.defaultdict(list)
    for v in runs.values():
        table[v["condition"]].append(v["makespan_s"])
    summary = {c: {"n": len(x), "mean_s": statistics.mean(x), "min_s": min(x), "max_s": max(x)} for c, x in sorted(table.items())}
    res = {"label": "real", "session": session, "n_runs": len(runs), "n_failing_checks": len(bad), "failing": bad,
           "makespan_by_condition": summary, "runs": runs}
    with open(out, "x", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("runs", "failing")}, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
