"""Single high-resolution clock for all runtime lifecycle timestamps.

Why not ``time.time()``: on CPython 3.11 / Windows it is backed by
``GetSystemTimeAsFileTime`` (nominal resolution 15.6 ms; observed steps of
~0.5-1 ms on the project machine). Phase 1 validation caught this directly:
cross-process intervals came out quantized to exactly 0 or ~1 ms, and some
tasks' recorded ``t_completed - t_started`` was *shorter* than the
``perf_counter``-timed kernel inside it. ``time.monotonic()`` is no better
(``GetTickCount64``, 15.6 ms).

``time.perf_counter()`` on Windows is ``QueryPerformanceCounter`` (100 ns
resolution) and returns the raw system-wide counter with no per-process
offset, so values taken in the coordinator and in worker processes are
directly comparable. Verified empirically on the project machine (a child
process's reading always fell inside the parent's before/after bracket) and
pinned by ``tests/test_clock.py`` so a platform where this does not hold fails
loudly instead of producing silently wrong intervals.

``now()`` values are seconds on an arbitrary epoch (system uptime on Windows).
Use ``anchor()`` once per run to map them to wall-clock time.
"""
from __future__ import annotations

import time

now = time.perf_counter


def anchor() -> dict:
    """A paired (epoch, perf) reading for converting ``now()`` values to
    wall-clock: epoch ~= epoch_anchor + (t - perf_anchor). The epoch side
    inherits ``time.time()``'s coarse resolution; intervals do not."""
    return {"epoch_anchor": time.time(), "perf_anchor": now()}
