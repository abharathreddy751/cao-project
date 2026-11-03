"""Append available RAM (GB) every N seconds to a CSV until the stop file appears. Read-only monitor: it never signals or kills anything.

  python scripts/final_memory_monitor.py <out.csv> <stop_file> [interval_s=10] [floor_gb=0.8] [start_gb=2.4]

Columns: utc, available_gb, state. state = ok | below_runner_floor (< floor_gb: the runner aborts the session at its next block start)
| below_start_threshold (< start_gb; only informative while a session is running, because the worker pool holds about 1.4 GB).
"""
import datetime
import sys
import time
from pathlib import Path

import psutil

out, stop = Path(sys.argv[1]), Path(sys.argv[2])
interval = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
floor = float(sys.argv[4]) if len(sys.argv) > 4 else 0.8
start = float(sys.argv[5]) if len(sys.argv) > 5 else 2.4
new = not out.exists()
with out.open("a", encoding="utf-8", buffering=1) as fh:
    if new:
        fh.write("utc,available_gb,state\n")
    while not stop.exists():
        a = psutil.virtual_memory().available / 2**30
        state = "below_runner_floor" if a < floor else "below_start_threshold" if a < start else "ok"
        fh.write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat()},{a:.2f},{state}\n")
        time.sleep(interval)
