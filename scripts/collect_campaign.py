"""Phase 3: randomized interference campaign (training data for E4).

Each run: a fresh random independent trace (profiled workloads/sizes), a
random concurrency level c and a random subset of c workers, dispatched by
``RandomOccupancyPolicy``. Everything is logged in the standard event-log
format, so features are later reconstructed by ``caosched.dataset.events``
exactly as for any scheduling run.

Outputs:
  data/events/campaign_<stamp>/run_NNN.jsonl
  data/results/campaign_<stamp>_manifest.json

Usage:
    python scripts/collect_campaign.py [--config config/phase3.yaml] [--runs N]
"""
from __future__ import annotations

import argparse
import datetime
import json
import platform
import random
import sys
from pathlib import Path

import yaml

from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
from caosched.core.event_log import DEFAULT_OUTPUT_DIR as EVENTS_DIR
from caosched.core.event_log import EventLogger
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.trace import dag_from_trace, generate_trace
from caosched.core.worker_pool import WorkerPool
from caosched.dataset.campaign import RandomOccupancyPolicy

RESULTS_DIR = Path(__file__).resolve().parents[1] / "data" / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase3.yaml")
    ap.add_argument("--runs", type=int, default=None)
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["campaign"]
    n_runs = args.runs or cfg["runs"]

    rc = RuntimeConfig.from_topology()
    coord_core = pin_coordinator_to_reserved_core(rc)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    exp_id = f"campaign_{stamp}"
    out_dir = EVENTS_DIR / exp_id
    rng = random.Random(cfg["seed"])
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    runs_meta = []
    with WorkerPool.from_config(rc, warmup=True, strict_affinity=True) as pool:
        workers = pool.worker_ids()
        print(f"{exp_id}: {n_runs} runs x {cfg['tasks_per_run']} tasks; workers {workers}; coordinator core {coord_core}")
        for i in range(n_runs):
            c = rng.randint(cfg["concurrency_min"], min(cfg["concurrency_max"], len(workers)))
            allowed = sorted(rng.sample(workers, c), key=workers.index)
            min_idle = rng.choice(cfg.get("min_idle_choices_s", [0.0]))
            trace = generate_trace({"name": f"{exp_id}_r{i:03d}", "generator": "independent",
                                    "seed": cfg["seed"] * 100_003 + i, "n_tasks": cfg["tasks_per_run"],
                                    "workload_mix": cfg["workload_mix"], "sizes": cfg["sizes"]})
            policy = RandomOccupancyPolicy(seed=rng.randrange(2**31), allowed_workers=allowed, min_idle_s=min_idle)
            meta = {"experiment_id": exp_id, "trace": trace["name"], "run_index": i,
                    "concurrency": c, "allowed_workers": allowed, "min_idle_s": min_idle}
            with EventLogger(f"run_{i:03d}", output_dir=out_dir) as logger:
                s = Coordinator(dag_from_trace(trace), pool, policy, logger, run_metadata=meta).run(
                    run_timeout=cfg["run_timeout_s"])
            runs_meta.append({**meta, "status": s.status, "makespan_s": s.makespan_seconds})
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{n_runs} runs")

    (RESULTS_DIR / f"{exp_id}_manifest.json").write_text(json.dumps({
        "experiment_id": exp_id, "config": cfg, "events_dir": str(out_dir), "runtime_config": rc.to_dict(),
        "coordinator_core": coord_core, "python": sys.version, "platform": platform.platform(), "runs": runs_meta,
    }, indent=1), encoding="utf-8")
    print(f"done -> {out_dir}")


if __name__ == "__main__":
    main()
