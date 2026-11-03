"""Phase 1 validation: run each DAG pattern through the real coordinator and
worker pool, pinned to this machine's actual P/E core assignment (from Phase
0's topology discovery), and report real wall-clock results.

Every run writes a fresh, timestamped event log under data/events/ (existing
logs are never overwritten).

Usage:
    python scripts/run_dag.py [--size N] [--workload matmul|image_filter|compression]
"""
from __future__ import annotations

import argparse
import datetime

from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
from caosched.core.dag import build_chain_dag, build_fork_join_dag, build_independent_dag, build_mixed_dag
from caosched.core.event_log import EventLogger
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.scheduler_base import FirstIdleScheduler
from caosched.core.worker_pool import WorkerPool


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--workload", default="matmul")
    args = ap.parse_args()

    config = RuntimeConfig.from_topology()
    print(f"Runtime config (from Phase 0 topology): {config.to_dict()}")
    print(f"Coordinator pinned to core: {pin_coordinator_to_reserved_core(config)}")

    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    dags = {
        "independent": build_independent_dag(9, workload=args.workload, size=args.size),
        "chain": build_chain_dag(5, workload=args.workload, size=args.size),
        "fork_join": build_fork_join_dag(width=8, workload=args.workload, size=args.size),
        "mixed": build_mixed_dag(workload=args.workload, size=args.size),
    }

    with WorkerPool.from_config(config, warmup=True, strict_affinity=True) as pool:
        for info in pool.ready_infos():
            print(f"  worker {info.worker_id} pid={info.pid} pool={pool.pool_of(info.worker_id)} "
                  f"affinity requested={list(info.requested_affinity)} actual={list(info.actual_affinity)} "
                  f"warmup={info.warmup_seconds:.3f}s")
        for name, dag in dags.items():
            with EventLogger(run_id=f"phase1_{stamp}_{name}") as logger:
                summary = Coordinator(dag, pool, FirstIdleScheduler(), logger).run(run_timeout=300)
            print(f"[{name}] {summary.status} -- {summary.n_completed}/{summary.n_tasks} tasks, "
                  f"makespan {summary.makespan_seconds * 1e3:.2f} ms, "
                  f"sum(kernel) {summary.total_wall_time_seconds * 1e3:.2f} ms, "
                  f"per-pool {summary.tasks_per_pool}, events -> {logger.path.name}")


if __name__ == "__main__":
    main()
