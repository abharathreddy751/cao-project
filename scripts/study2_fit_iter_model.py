"""Study 2 hidden-cost workload: fit the denoise line (kernel seconds = a + b * iterations, one line per pool) from the logs of EARLIER sessions.

Every completed ``img_denoise`` task of every run outside warm-up block 0 is one point (iterations from the task's ``params``, kernel =
``wall_time_seconds``, pool from the event). Least squares per pool (``numpy.polyfit`` degree 1). Output (exclusive create) is read by
``study2.model.IterModelEstimator``. Never fitted on the session it is later applied to (protocol section 18 names the source).

  python scripts/study2_fit_iter_model.py <out.json> <session_dir> [<session_dir> ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from caosched.core.event_log import read_events


def main(out: str, sessions: list[str]) -> int:
    if Path(out).exists():
        sys.exit(f"{out} exists: refusing to overwrite")
    pts: dict[str, list[tuple[int, float]]] = {}
    for s in sessions:
        for log in sorted(Path(s).glob("runs/*/*.jsonl")):
            if log.parent.name.startswith("b0000_"):
                continue
            ev = read_events(log)
            specs = next(e for e in ev if e["event"] == "run_started")["tasks"]
            for e in ev:
                if e["event"] == "task_completed" and specs[e["task_id"]]["workload"] == "img_denoise":
                    pts.setdefault(e["pool"], []).append((int(specs[e["task_id"]]["params"]["iterations"]), e["wall_time_seconds"]))
    line, info = {}, {}
    for pool, v in sorted(pts.items()):
        x, y = np.array([a for a, _ in v], float), np.array([b for _, b in v])
        if len(set(x)) < 2:
            sys.exit(f"pool {pool}: need at least two distinct iteration counts to fit a line (got {sorted(set(x))})")
        b, a = np.polyfit(x, y, 1)
        line[pool] = [float(a), float(b)]
        info[pool] = {"n": len(v), "iterations": sorted(set(int(i) for i in x)),
                      "mean_abs_error_s": float(np.mean(np.abs(a + b * x - y)))}
    with Path(out).open("x", encoding="utf-8") as fh:
        json.dump({"denoise_line_by_pool": line, "fit": info, "sessions": [str(s) for s in sessions],
                   "rule": "least squares per pool, warm-up block excluded"}, fh, indent=1)
    for pool, (a, b) in line.items():
        print(f"{pool}: kernel = {a * 1e3:.3f} ms + {b * 1e3:.3f} ms * iterations   {info[pool]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
