"""Machine/environment characterization record for Phase 0.

Produces a single JSON record capturing everything needed to interpret later
benchmark results and reproduce them on this or another machine: CPU topology
(from :mod:`caosched.phase0.topology`), RAM, OS version, Python version, CPU
affinity support, and the planned worker-pool core assignment.
"""
from __future__ import annotations

import datetime
import json
import os
import platform
import sys
from pathlib import Path

import psutil

from caosched.phase0 import topology as topo

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data" / "environment"


def _detect_os_info() -> dict:
    try:
        edition = platform.win32_edition()
    except Exception:  # noqa: BLE001
        edition = None
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "win32_edition": edition,
    }


def _detect_python_info() -> dict:
    return {
        "version": sys.version,
        "version_info": list(sys.version_info),
        "executable": sys.executable,
        "implementation": platform.python_implementation(),
    }


def _test_affinity_support(topology: topo.TopologyResult) -> dict:
    """Actually set and read back CPU affinity for this process rather than
    assuming it works -- the benchmark harness depends on affinity pinning,
    so Phase 0 verifies it directly and records exactly what succeeded.
    """
    result: dict = {"supported": False, "error": None, "tested_cpu": None, "readback": None}
    if not topology.available or not topology.processors:
        result["error"] = "no topology available to pick a test CPU"
        return result
    test_cpu = topology.processors[0].logical_processor_index
    proc = psutil.Process()
    try:
        original = proc.cpu_affinity()
        proc.cpu_affinity([test_cpu])
        readback = proc.cpu_affinity()
        proc.cpu_affinity(original)
        result["supported"] = readback == [test_cpu]
        result["tested_cpu"] = test_cpu
        result["readback"] = readback
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def planned_worker_pool_config(topology: topo.TopologyResult, max_p_slots: int | None = 2) -> dict:
    """Map the project's initial worker configuration (2 P-core slots, 7
    E-core slots, 1 E-core reserved for coordinator/OS) onto the *actually
    discovered* logical processors -- never assumed indices.
    """
    if not topology.available:
        return {"available": False, "error": "topology unavailable; cannot assign worker pool cores"}

    e_cores = list(topology.e_core_logical_processors)

    # One P-core worker slot per *physical* P-core (not per SMT thread),
    # since the brief specifies 2 P-core worker slots for 2 physical P-cores.
    p_core_physical: list[int] = []
    seen_core_indices: set[int] = set()
    for lp in sorted(topology.p_core_logical_processors):
        core_idx = next(p.core_index for p in topology.processors if p.logical_processor_index == lp)
        if core_idx not in seen_core_indices:
            seen_core_indices.add(core_idx)
            p_core_physical.append(lp)

    coordinator_core = e_cores[0] if e_cores else None
    remaining_e_cores = e_cores[1:] if e_cores else []

    return {
        "available": True,
        "p_core_worker_slots": p_core_physical[:max_p_slots],
        "e_core_worker_slots": remaining_e_cores,
        "coordinator_reserved_core": coordinator_core,
        "note": (
            "P-core slots use one logical processor per physical P-core (not "
            "both SMT threads); E-core slots use all remaining E-core logical "
            "processors after reserving one for the coordinator/OS."
        ),
    }


def build_environment_record() -> dict:
    topology = topo.discover_topology()
    wmi_summary = topo.get_wmi_processor_summary()
    affinity = _test_affinity_support(topology)
    worker_pool = planned_worker_pool_config(topology)

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "topology": topo.topology_to_dict(topology),
        "wmi_cross_check": wmi_summary,
        "ram_bytes_total": psutil.virtual_memory().total,
        "os": _detect_os_info(),
        "python": _detect_python_info(),
        "cpu_affinity_support": affinity,
        "planned_worker_pool_config": worker_pool,
        "cpu_count_cross_check": {
            "os_cpu_count": os.cpu_count(),
            "topology_raw_logical_processor_count": topology.raw_logical_processor_count,
            "wmi_number_of_logical_processors": wmi_summary.get("number_of_logical_processors"),
            "consistent": (
                topology.available
                and bool(wmi_summary.get("available"))
                and os.cpu_count() == topology.raw_logical_processor_count == wmi_summary.get("number_of_logical_processors")
            ),
        },
    }


def write_environment_record(output_dir: Path | None = None) -> Path:
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    record = build_environment_record()
    timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    output_path = output_dir / f"env_{timestamp}.json"
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = write_environment_record()
    print(f"Wrote environment record to {path}")
