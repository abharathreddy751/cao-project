"""Revival calibration (measured, no assumed values): how much does a spinning process on the SAME logical core slow a worker down, and
what does it cost to sample per-core utilisation? Writes <out>.json (created exclusively).

  python scripts/revival_calibrate.py <out.json> [--core 0] [--reps 5]

Slowdown: the kernel of ``img_denoise`` (256 px, 60 iterations) and ``img_edges`` (512 px) is timed in this process pinned to ``--core`` with
0, 1 and 2 burners on the core (``revival.contention``). Sampling cost: wall time of ``psutil.cpu_percent(percpu=True)``.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import psutil

from caosched.apps.stages import STAGES
from caosched.revival.contention import ContentionRunner, ContentionSchedule, Window
from caosched.util import clock


def kernel_time(stage: str, side: int, params: dict, reps: int) -> float:
    st = STAGES[stage]
    if stage == "img_source":
        inputs = []
    else:
        src = STAGES["img_source"].compute([], {"width": side, "height": side, "seed": 1})
        inputs = [src] if stage == "img_denoise" else [STAGES["img_denoise"].compute([src], {"radius": 2.0, "iterations": 2})]
    ts = []
    for _ in range(reps):
        t = clock.now()
        st.compute(inputs, params)
        ts.append(clock.now() - t)
    return statistics.median(ts)


def main(out: str, core: int = 0, reps: int = 5) -> int:
    psutil.Process().cpu_affinity([core])
    cases = {"img_denoise_256_x60": ("img_denoise", 256, {"radius": 2.0, "iterations": 60}),
             "img_edges_512": ("img_edges", 512, {})}
    res: dict = {"core": core, "reps": reps, "slowdown": {}, "kernel_s": {}}
    runner = ContentionRunner([core], 2)
    try:
        for k in (0, 1, 2):
            for name, (stage, side, params) in cases.items():
                if k:
                    t0 = runner.start(ContentionSchedule("cal", (Window(core, 0.0, 600.0, k),)))
                    time.sleep(0.2)
                tt = kernel_time(stage, side, params, reps)
                if k:
                    runner.stop()
                res["kernel_s"].setdefault(name, {})[str(k)] = tt
        for name, d in res["kernel_s"].items():
            res["slowdown"][name] = {k: d[k] / d["0"] for k in d}
        psutil.cpu_percent(percpu=True)
        ts = []
        for _ in range(200):
            t = clock.now()
            psutil.cpu_percent(percpu=True)
            ts.append(clock.now() - t)
        res["cpu_percent_percpu_call_s"] = {"median": statistics.median(ts), "p95": sorted(ts)[int(0.95 * len(ts))]}
        t0 = runner.start(ContentionSchedule("cal2", (Window(core, 0.0, 5.0, 1),)))
        time.sleep(0.3)
        psutil.cpu_percent(percpu=True)
        time.sleep(0.1)
        a = psutil.cpu_percent(percpu=True)
        runner.stop()
        time.sleep(0.2)
        psutil.cpu_percent(percpu=True)
        time.sleep(0.1)
        b = psutil.cpu_percent(percpu=True)
        res["core_util_pct_100ms"] = {"with_burner": a[core], "without_burner": b[core]}
    finally:
        runner.close()
    with Path(out).open("x", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({"slowdown": res["slowdown"], "sample_cost": res["cpu_percent_percpu_call_s"], "util": res["core_util_pct_100ms"]}, indent=1))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[0], int(a[a.index("--core") + 1]) if "--core" in a else 0, int(a[a.index("--reps") + 1]) if "--reps" in a else 5))
