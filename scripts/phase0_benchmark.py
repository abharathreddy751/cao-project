"""Phase 0: run the benchmark harness (K1, K2, K5) and write raw CSV results.

Usage:
    python scripts/phase0_benchmark.py              # full suite
    python scripts/phase0_benchmark.py --quick       # smaller sizes/repeats, for fast iteration
"""
from __future__ import annotations

import argparse
import datetime
import uuid

from caosched.phase0 import topology as topo
from caosched.phase0.benchmarks import harness


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 benchmark harness")
    parser.add_argument("--quick", action="store_true", help="Use smaller sizes/repeats for fast iteration")
    args = parser.parse_args()

    topology = topo.discover_topology()
    if not topology.available:
        raise SystemExit(f"Topology discovery failed: {topology.error}")

    run_id = f"{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    print(f"run_id={run_id}")
    print(f"P-core logical processors: {topology.p_core_logical_processors}")
    print(f"E-core logical processors: {topology.e_core_logical_processors}")

    if args.quick:
        matmul_sizes = [128, 256]
        other_sizes = {"image_filter": [256], "compression": [262144]}
        repeats, warmups = 5, 2
        k2_load_options = [0, 2, 4]
        k2_size = 192
        k5_size = 192
        load_duration = 15.0
    else:
        matmul_sizes = [128, 256, 512]
        other_sizes = {"image_filter": [256, 512], "compression": [262144, 1048576]}
        repeats, warmups = 10, 3
        k2_load_options = [0, 1, 2, 4, 6]
        k2_size = 256
        k5_size = 256
        load_duration = 30.0

    rows = []
    print("Running K1 (P vs E, no load)...")
    for workload_name in ("matmul", "image_filter", "compression"):
        sizes = matmul_sizes if workload_name == "matmul" else other_sizes[workload_name]
        rows += harness.run_k1_pool_comparison(topology, workload_name, sizes, repeats, warmups, run_id)

    print("Running K2 (P-core task under increasing E-core load)...")
    rows += harness.run_k2_load_interference(
        topology, "matmul", k2_size, repeats, warmups, run_id,
        load_workload_name="matmul", num_load_procs_options=k2_load_options,
        load_duration_seconds=load_duration,
    )

    print("Running K5 (P-core SMT sibling interference, if measurable)...")
    rows += harness.run_k5_smt_sibling_interference(
        topology, "matmul", k5_size, repeats, warmups, run_id,
        load_duration_seconds=load_duration,
    )

    output_path = harness.DEFAULT_OUTPUT_DIR / f"{run_id}.csv"
    harness.write_rows(rows, output_path)
    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
