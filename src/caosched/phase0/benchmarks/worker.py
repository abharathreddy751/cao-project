"""Subprocess entry points for Phase 0 benchmark measurements.

Each function here is a ``multiprocessing`` (spawn context) process target.
Running as a fresh OS process lets ``caosched.util.threadpin.pin_single_thread``
take effect before numpy is imported in that process, and lets CPU affinity be
set per-process via ``psutil.Process.cpu_affinity()`` before any work starts.

``pin_single_thread()`` is called at module import time (below) rather than
inside each function, because with the ``spawn`` start method a fresh
interpreter re-imports this module before invoking the target function --
so module-level code here always runs first, before any workload's lazy
``import numpy``.
"""
from __future__ import annotations

from caosched.util.threadpin import pin_single_thread

pin_single_thread()

import time
import traceback


def measure_one(workload_name: str, size: int, seed: int, affinity, result_queue) -> None:
    """Run exactly one workload invocation pinned to ``affinity`` (a list of
    logical processor indices, or None/empty to leave affinity unset), and
    push a result dict onto ``result_queue``.
    """
    import psutil

    from caosched.phase0.benchmarks.workloads import WORKLOADS

    result = {
        "workload": workload_name,
        "size": size,
        "seed": seed,
        "affinity": list(affinity) if affinity else None,
        "wall_time_seconds": None,
        "rss_bytes": None,
        "error": None,
    }
    try:
        if affinity:
            psutil.Process().cpu_affinity(list(affinity))
        workload = WORKLOADS[workload_name]
        inputs = workload.prepare(size, seed)
        start = time.perf_counter()
        workload.run(inputs)
        result["wall_time_seconds"] = time.perf_counter() - start
        result["rss_bytes"] = psutil.Process().memory_info().rss
    except Exception:  # noqa: BLE001 - report to parent, never crash silently
        result["error"] = traceback.format_exc()
    result_queue.put(result)


def generate_load(workload_name: str, size: int, affinity, duration_seconds: float, stop_event) -> None:
    """Repeatedly run ``workload_name`` pinned to ``affinity`` until
    ``stop_event`` is set or ``duration_seconds`` elapses, whichever is first.

    Used as background load for the K2/K5 concurrent-load scenarios; this
    process's own timings are not collected -- only its *effect* on a
    simultaneously measured target task (run by ``measure_one`` in another
    process) matters.
    """
    import psutil

    from caosched.phase0.benchmarks.workloads import WORKLOADS

    if affinity:
        psutil.Process().cpu_affinity(list(affinity))
    workload = WORKLOADS[workload_name]
    deadline = time.perf_counter() + duration_seconds
    seed = 0
    while time.perf_counter() < deadline and not stop_event.is_set():
        inputs = workload.prepare(size, seed)
        workload.run(inputs)
        seed += 1
