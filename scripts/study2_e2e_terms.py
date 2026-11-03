"""Study 2: derive the end-to-end terms of the EFT ablation (EFT_*_e2e) from the event logs of ONE earlier session.

For every completed application task of the given session(s), excluding warm-up block 0:
  setup[stage, size, pool] = median( (t_completed - t_started) - wall_time_seconds )     worker span minus the timed kernel,
                             i.e. artifact read/decode + encode/write (the task's I/O), inside the worker
  overhead[pool]           = median( (t_started - t of its task_submitted event) + (t of its task_completed event - t_completed) )
                             coordinator-to-worker and worker-to-coordinator IPC
A (stage, size, pool) with no completed task gets the median of the same stage on the other pools (recorded in ``filled``).
Nothing is typed in. The result must come from a session that is NOT the one it is later applied to (the protocol names the
source). Output file is created exclusively.

  python scripts/study2_e2e_terms.py <out.json> <session_dir> [<session_dir> ...]
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

from caosched.core.event_log import read_events
from caosched.estimators.e2e import EndToEndTerms

POOLS = ("P", "E", "G")


def main(out: str, sessions: list[str]) -> int:
    if Path(out).exists():
        sys.exit(f"{out} exists: refusing to overwrite")
    setup: dict[tuple, list[float]] = {}
    over: dict[str, list[float]] = {}
    n_logs = 0
    for s in sessions:
        for log in sorted(Path(s).glob("runs/*/*.jsonl")):
            if log.parent.name.startswith("b0000_"):  # warm-up block (design rule)
                continue
            n_logs += 1
            ev = read_events(log)
            sizes = {tid: t["size"] for tid, t in next(e for e in ev if e["event"] == "run_started")["tasks"].items()}
            sub = {e["task_id"]: e["t"] for e in ev if e["event"] == "task_submitted"}
            for e in ev:
                if e["event"] != "task_completed" or e["task_id"] not in sub:
                    continue
                tid, pool = e["task_id"], e["pool"]
                stage = tid.rsplit("_", 1)[0] if tid[-1].isdigit() and "_" in tid else tid
                setup.setdefault(("img_" + stage, sizes[tid], pool), []).append(
                    (e["t_completed"] - e["t_started"]) - e["wall_time_seconds"])
                over.setdefault(pool, []).append(max(0.0, e["t_started"] - sub[tid]) + max(0.0, e["t"] - e["t_completed"]))
    med = {k: statistics.median(v) for k, v in setup.items()}
    filled = []
    for (w, size) in sorted({(w, sz) for (w, sz, _p) in med}):
        have = {p: med[(w, size, p)] for p in POOLS if (w, size, p) in med}
        for p in POOLS:
            if p not in have and have and not (p == "G" and w not in ("img_denoise", "img_edges", "img_features")):
                med[(w, size, p)] = statistics.median(have.values())
                filled.append(f"{w}|{size}|{p}")
    terms = EndToEndTerms(med, {p: statistics.median(v) for p, v in over.items()})
    terms.save(Path(out), {"sessions": [str(s) for s in sessions], "n_logs": n_logs, "filled_from_other_pools": filled,
                           "rule": "warm-up block excluded; medians over completed tasks"})
    for (w, size, p), v in sorted(med.items()):
        print(f"{w:14s} {size:8d} {p}  setup {v * 1e3:8.3f} ms")
    for p, v in sorted(terms.overhead_s.items()):
        print(f"overhead {p}: {v * 1e3:.3f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
