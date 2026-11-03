"""Phase 4 diagnostic: CPU cost of one EFT decision per estimator rung.

EFT evaluates every worker; for each it estimates the executing task's
remaining time, every locally queued task, and the new task (with a
per-candidate EstimateContext for context-using estimators such as E4). The
cost therefore grows with the number of already-bound tasks. This measures
``select_worker`` wall time (clock.now, QPC) in the coordinator process for
a synthetic state of 9 workers (2 P + 7 E) with n tasks already bound
round-robin, no worker processes involved.

Raw output: data/diagnostics/decision_cost_<stamp>.csv
Usage: python scripts/diag_decision_cost.py [--repeats 200]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import statistics
from pathlib import Path

import yaml

from caosched.core.dag import DAG
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task
from caosched.estimators import build_estimator, latest_profile_path
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.util import clock

OUT = Path(__file__).resolve().parents[1] / "data" / "diagnostics"
WORKERS = {"P0": "P", "P1": "P", **{f"E{i}": "E" for i in range(7)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=200)
    ap.add_argument("--config", default="config/phase4.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    est_cfg = {**yaml.safe_load(Path(cfg["estimator_config"]).read_text(encoding="utf-8"))["estimators"], "rc": cfg["rc"]}
    profile, model = latest_profile_path(), Path(cfg["e4_model"])

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"decision_cost_{datetime.datetime.now():%Y%m%dT%H%M%S}.csv"
    rows = []
    for spec in ("E1", "E3", "E4", "E4+rc", "E4f", "E4f+rc"):
        for n_bound in (0, 9, 30, 60):
            tasks = {f"t{i}": Task(f"t{i}", "matmul", 512, seed=i) for i in range(n_bound + 1)}
            dag = DAG(tasks)
            state = RuntimeState(dag, WORKERS)
            wids = list(WORKERS)
            for i in range(n_bound):  # first 9 executing, the rest queued round-robin
                w = wids[i % len(wids)]
                if state.bind(f"t{i}", w):
                    state.mark_submitted(w, f"t{i}", clock.now())
            pol = EarliestFinishTimeScheduler(build_estimator(spec, profile, est_cfg, model), f"EFT_{spec}")
            pol.on_run_start(dag, state)
            new = dag.tasks[f"t{n_bound}"]
            for r in range(args.repeats):
                t0 = clock.now()
                pol.select_worker(new, state)
                rows.append({"estimator": spec, "n_bound": n_bound, "repeat": r, "select_worker_s": clock.now() - t0})
    with path.open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["estimator", "n_bound", "repeat", "select_worker_s"])
        w.writeheader()
        w.writerows(rows)
    print(f"raw -> {path.name}\nmedian select_worker time (ms) by already-bound tasks:")
    print(f"  {'estimator':8s} " + " ".join(f"{n:>8d}" for n in (0, 9, 30, 60)))
    for spec in ("E1", "E3", "E4", "E4+rc", "E4f", "E4f+rc"):
        med = [statistics.median(r["select_worker_s"] for r in rows if r["estimator"] == spec and r["n_bound"] == n)
               for n in (0, 9, 30, 60)]
        print(f"  {spec:8s} " + " ".join(f"{m * 1e3:8.3f}" for m in med))


if __name__ == "__main__":
    main()
