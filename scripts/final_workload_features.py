"""Final study, Phase F input: workload features that are known BEFORE execution (DAG plus the trained cost model), per design instance.

  python scripts/final_workload_features.py <param_model.json> <out.csv> <design.json> [<design.json> ...]

For every instance (chain order) of every given design, the CPU-only DAG is built and each chain's predicted cost is the sum of the model's
kernel predictions of its tasks on a P core. Features:
  n_chains, cv_chain_cost (std/mean), max_over_median, n_heavy (chains above 3x the median), heavy_work_share (their share of predicted work),
  tail_ratio = longest chain / (total predicted work / n_cpu_workers): above 1 the longest chain alone outlasts a perfectly balanced
  schedule, so the order in which chains are started matters.
Nothing here reads a result. The file is written (exclusively) BEFORE the evaluation sessions are analysed so that a selector rule can only
use what a runtime policy could know.
"""
from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

from caosched.experiment.design import load_design
from caosched.final.adapter import FinalAdapter
from caosched.study2.param_model import ParamModelEstimator

N_CPU_WORKERS = 13  # 6 P + 7 E, the configuration of the final study


def chain_costs(dag, est, pool: str = "P") -> list[float]:
    chains: dict[str, float] = {}
    for t in dag.tasks.values():
        if t.workload == "img_aggregate":
            continue
        idx = t.task_id.rsplit("_", 1)[1]
        chains[idx] = chains.get(idx, 0.0) + est.estimate(t, pool)
    return list(chains.values())


def features(costs: list[float], workers: int = N_CPU_WORKERS) -> dict:
    med, mean, total = statistics.median(costs), statistics.fmean(costs), sum(costs)
    heavy = [c for c in costs if c > 3 * med]
    return {"n_chains": len(costs), "cv_chain_cost": statistics.pstdev(costs) / mean, "max_over_median": max(costs) / med,
            "n_heavy": len(heavy), "heavy_work_share": sum(heavy) / total, "tail_ratio": max(costs) / (total / workers)}


def main(model: str, out: str, designs: list[str]) -> int:
    est = ParamModelEstimator.load(Path(model))
    adapter = FinalAdapter()
    rows = []
    for dp in designs:
        d = load_design(dp)
        c0 = next(c for c in d.conditions if c.name == "B4_cpu")  # same DAG for every condition of a configuration
        for inst in d.instances:
            kw = {**c0.kwargs, **({"order_seed": c0.kwargs["order_seeds"][inst]} if inst is not None and c0.kwargs.get("order_seeds") else {})}
            dag, _ = adapter.build_dag(kw, ())
            rows.append({"workload": d.name.removeprefix("final_eval_"), "instance": inst or "", **features(chain_costs(dag, est))})
    with Path(out).open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote", out, len(rows), "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
