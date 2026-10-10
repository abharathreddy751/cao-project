"""Phase 0 benchmark harness: warmups, repeated measurements, and the
concurrent-load scenarios needed for the Phase 0 gate decision.

Implements:
  K1 -- single-task execution time, P-core vs E-core, no concurrent load.
  K2 -- P-core task execution time under an increasing number of concurrently
        loaded E-cores.
  K5 -- P-core task execution time alone vs. with its SMT sibling also busy
        (only runs if this machine's topology actually has an SMT pair on a
        P-core; otherwise honestly reports nothing rather than fabricating).

Every row written is a real measurement produced by running these processes on
this machine -- nothing here is a manually typed or estimated number.
"""
from __future__ import annotations

import csv
import datetime
import multiprocessing as mp
import time
from pathlib import Path

from caosched.phase0 import topology as topo
from caosched.phase0.benchmarks import worker

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "benchmarks"

CSV_FIELDS = [
    "run_id",
    "timestamp_utc",
    "scenario",
    "workload",
    "size",
    "seed",
    "affinity",
    "pool",
    "load_workload",
    "load_affinity",
    "num_load_procs",
    "warmup",
    "repeat_index",
    "wall_time_seconds",
    "rss_bytes",
    "error",
]


def _spawn_ctx():
    return mp.get_context("spawn")


def _measure_once(workload_name: str, size: int, seed: int, affinity) -> dict:
    ctx = _spawn_ctx()
    result_queue = ctx.Queue()
    proc = ctx.Process(target=worker.measure_one, args=(workload_name, size, seed, affinity, result_queue))
    proc.start()
    try:
        result = result_queue.get(timeout=120)
    finally:
        proc.join(timeout=30)
        if proc.is_alive():
            proc.terminate()
    return result


def _row(run_id, scenario, workload, size, seed, affinity, pool, warmup, repeat_index, result,
         load_workload=None, load_affinity=None, num_load_procs=0) -> dict:
    return {
        "run_id": run_id,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scenario": scenario,
        "workload": workload,
        "size": size,
        "seed": seed,
        "affinity": ",".join(str(c) for c in affinity) if affinity else "",
        "pool": pool,
        "load_workload": load_workload or "",
        "load_affinity": ",".join(str(c) for c in load_affinity) if load_affinity else "",
        "num_load_procs": num_load_procs,
        "warmup": warmup,
        "repeat_index": repeat_index,
        "wall_time_seconds": result.get("wall_time_seconds"),
        "rss_bytes": result.get("rss_bytes"),
        "error": result.get("error") or "",
    }


def run_k1_pool_comparison(topology: topo.TopologyResult, workload_name: str, sizes: list[int],
                            repeats: int, warmups: int, run_id: str) -> list[dict]:
    """K1: single-task execution time on P-core vs E-core, no concurrent load."""
    rows: list[dict] = []
    pools = {
        "P": list(topology.p_core_logical_processors[:1]),
        "E": list(topology.e_core_logical_processors[:1]),
    }
    for pool_name, affinity in pools.items():
        if not affinity:
            continue
        for size in sizes:
            for i in range(warmups):
                _measure_once(workload_name, size, seed=9000 + i, affinity=affinity)
            for i in range(repeats):
                res = _measure_once(workload_name, size, seed=i, affinity=affinity)
                rows.append(_row(run_id, "K1", workload_name, size, i, affinity, pool_name, False, i, res))
    return rows


def run_k2_load_interference(topology: topo.TopologyResult, workload_name: str, size: int,
                              repeats: int, warmups: int, run_id: str, load_workload_name: str,
                              num_load_procs_options: list[int], load_duration_seconds: float = 30.0) -> list[dict]:
    """K2: P-core task execution time under an increasing number of concurrently loaded E-cores."""
    rows: list[dict] = []
    target_affinity = list(topology.p_core_logical_processors[:1])
    e_cores = list(topology.e_core_logical_processors)
    if not target_affinity or not e_cores:
        return rows

    for num_load in num_load_procs_options:
        load_cores = e_cores[:num_load]
        ctx = _spawn_ctx()
        stop_event = ctx.Event()
        load_procs = []
        for core in load_cores:
            p = ctx.Process(target=worker.generate_load,
                             args=(load_workload_name, size, [core], load_duration_seconds, stop_event))
            p.start()
            load_procs.append(p)
        if load_procs:
            time.sleep(0.3)  # let background load ramp up before measuring
        try:
            for i in range(warmups):
                _measure_once(workload_name, size, seed=9000 + i, affinity=target_affinity)
            for i in range(repeats):
                res = _measure_once(workload_name, size, seed=i, affinity=target_affinity)
                rows.append(_row(run_id, "K2", workload_name, size, i, target_affinity, "P", False, i, res,
                                  load_workload=load_workload_name if load_cores else None,
                                  load_affinity=load_cores, num_load_procs=num_load))
        finally:
            stop_event.set()
            for p in load_procs:
                p.join(timeout=10)
                if p.is_alive():
                    p.terminate()
    return rows


def run_k5_smt_sibling_interference(topology: topo.TopologyResult, workload_name: str, size: int,
                                     repeats: int, warmups: int, run_id: str,
                                     load_duration_seconds: float = 30.0) -> list[dict]:
    """K5: P-core task execution time alone vs. with its SMT sibling also busy.

    Returns an empty list (honestly) if this machine's topology has no P-core
    SMT pair to test -- never fabricates a result for an untestable condition.
    """
    rows: list[dict] = []
    sibling_group = None
    for group in topology.core_groups.values():
        if len(group) == 2 and group[0] in topology.p_core_logical_processors:
            sibling_group = group
            break
    if not sibling_group:
        return rows

    target, sibling = sibling_group
    for condition, load_affinity in (("alone", None), ("sibling_busy", [sibling])):
        ctx = _spawn_ctx()
        stop_event = ctx.Event()
        load_proc = None
        if load_affinity:
            load_proc = ctx.Process(target=worker.generate_load,
                                     args=(workload_name, size, load_affinity, load_duration_seconds, stop_event))
            load_proc.start()
            time.sleep(0.3)
        try:
            for i in range(warmups):
                _measure_once(workload_name, size, seed=9000 + i, affinity=[target])
            for i in range(repeats):
                res = _measure_once(workload_name, size, seed=i, affinity=[target])
                rows.append(_row(run_id, "K5", workload_name, size, i, [target], "P", False, i, res,
                                  load_workload=workload_name if load_affinity else None,
                                  load_affinity=load_affinity,
                                  num_load_procs=1 if load_affinity else 0))
        finally:
            if load_proc:
                stop_event.set()
                load_proc.join(timeout=10)
                if load_proc.is_alive():
                    load_proc.terminate()
    return rows


def write_rows(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
