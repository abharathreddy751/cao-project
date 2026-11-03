"""Study 2: train (or RE-train) the generic parameter model from the logs of coverage sessions. One command, no code change per workload or machine.

Every completed application task of every run outside warm-up block 0 is one training point: group = (workload, pool), features = the
numeric task parameters that vary in the training logs (``study2.param_model``), target = ``wall_time_seconds``. The model file records
per group the features, coefficients, row count and training MAE, plus the sessions it was fitted on and a held-out check if
``--holdout`` sessions are given (mean absolute error per group on logs the fit never saw). Never fit on the session it is applied to.
New machine or new pool (for example a Raspberry Pi, pool ``R_PI``): run a coverage session that places every stage on that pool, then run this
command with that session; the model file gains the groups for the new pool, the code is unchanged.

  python scripts/study2_train_param_model.py <out.json> <session_dir> [<session_dir> ...] [--holdout <session_dir> ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from caosched.core.event_log import read_events
from caosched.study2.param_model import ParamModelEstimator, column, fit_group


def points(sessions):
    pts: dict[str, list[tuple[dict, float]]] = {}
    for s in sessions:
        for log in sorted(Path(s).glob("runs/*/*.jsonl")):
            if log.parent.name.startswith("b0000_"):
                continue
            ev = read_events(log)
            specs = next(e for e in ev if e["event"] == "run_started")["tasks"]
            for e in ev:
                if e["event"] == "task_completed":
                    sp = specs[e["task_id"]]
                    pts.setdefault(f'{sp["workload"]}|{e["pool"]}', []).append(({**(sp.get("params") or {}), "size": sp["size"]},
                                                                                e["wall_time_seconds"]))
    return pts


def main(out: str, sessions: list[str], holdout: list[str]) -> int:
    if Path(out).exists():
        sys.exit(f"{out} exists: refusing to overwrite")
    train = points(sessions)
    groups = {k: fit_group([p for p, _ in v], [y for _, y in v]) for k, v in sorted(train.items())}
    report = {}
    if holdout:
        est = ParamModelEstimator(groups)
        for k, v in sorted(points(holdout).items()):
            if k not in groups:
                report[k] = {"n": len(v), "error": "group not in the training logs"}
                continue
            g = groups[k]
            pred = [max(1e-6, float(np.dot(g["coef"], [1.0] + [column(p, f) for f in g["features"]]))) for p, _ in v]
            report[k] = {"n": len(v), "mae_s": float(np.mean([abs(a - y) for a, (_, y) in zip(pred, v)])),
                         "median_ape": float(np.median([abs(a - y) / y for a, (_, y) in zip(pred, v)]))}
    with Path(out).open("x", encoding="utf-8") as fh:
        json.dump({"groups": groups, "sessions": [str(s) for s in sessions], "holdout_sessions": [str(s) for s in holdout],
                   "holdout_report": report, "rule": "ridge least squares per (workload, pool), warm-up block excluded"}, fh, indent=1)
    for k, g in groups.items():
        print(f"{k:22s} n={g['n']:5d} features={g['features']} train_mae={g['mae_s'] * 1e3:8.3f} ms")
    for k, r in report.items():
        print("holdout", k, r)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    hold = a[a.index("--holdout") + 1:] if "--holdout" in a else []
    main(a[0], a[1:a.index("--holdout")] if "--holdout" in a else a[1:], hold)
