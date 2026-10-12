"""Stage 1 GPU spike: CPU reference vs PyTorch-CUDA for selected image-pipeline stages.

Rule (ARCHITECTURE_DECISIONS AD-6): a stage is GPU evidence only with a CPU reference,
a numeric-equivalence check inside a tolerance stated BEFORE the run, and a measured
speed-up that INCLUDES host-device copies; otherwise it is DROPPED, not forced.

Timing: CPU = the unmodified CPU stage compute (numpy/Pillow, single thread, as a worker
runs it); CUDA = apps/cuda_stages function incl. H2D + kernels + D2H, between
torch.cuda.synchronize() calls. Warm-up runs are discarded; median + spread over REPS runs.

Tolerances (output dtype / why), fixed before the recorded run:
  img_denoise  uint8, GPU re-implements Pillow's 3+3 extended box blur in int64 fixed point -> must be
               bit-exact (max |d| = 0). Anything else fails the stage.
  img_edges    uint8, float32 with the CPU stage's op sequence; CUDA vs numpy float32 may still differ by one
               rounding step that flips a truncating cast -> max |d| <= 1 level and <= 0.1 % of pixels differ.
  img_features float64 (histogram + moments), same formulas; reduction-order rounding only -> max rel err <= 1e-9.
Development note: a first conv2d-based edges/denoise draft missed these (TF32 in cuDNN; `x / 3.0` lowered to
x * (1/3) on CUDA; true Gaussian vs Pillow's box approximation), so they were rewritten before this run.
Outputs are created exclusively (never overwritten) in a new timestamped subdirectory of --out.
CPU stage: thread pool pinned to one thread (OMP/BLAS env vars set before numpy is imported, torch.set_num_threads(1));
the settings and the 1-minute CPU load are recorded in the JSON env block.
Usage: python scripts/gpu_spike.py [--reps 15] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from caosched.util.threadpin import _THREAD_ENV_VARS, pin_single_thread  # noqa: E402

pin_single_thread()  # before numpy/torch are imported, or the BLAS/OpenMP pools are already sized

import numpy as np  # noqa: E402
import psutil  # noqa: E402

from caosched.apps.cuda_stages import CUDA_STAGES, cuda_available  # noqa: E402
from caosched.apps.stages import STAGES  # noqa: E402

SIDES = (128, 256, 512, 1024, 2048)  # tile side in pixels; the shipped pipeline uses 256 (1024x1024, grid 4)
WARMUP = 3
TOL = {  # max_abs: max |difference| (dtype units); frac: max fraction of differing elements; rel: max relative error
    "img_edges": {"max_abs": 1, "frac": 1e-3},
    "img_features": {"rel": 1e-9},
    "img_denoise": {"max_abs": 0, "frac": 0.0},
}
CASES = [  # (stage, params)
    ("img_denoise", {"radius": 2.0, "iterations": 1}),
    ("img_denoise", {"radius": 2.0, "iterations": 8}),
    *[("img_denoise", {"radius": r, "iterations": 1}) for r in (0.7, 1.3, 2.5, 4.0)],  # radius sweep
    ("img_edges", {}),
    ("img_features", {}),
]


psutil.getloadavg()  # on Windows this starts psutil's load sampler; the value is only meaningful later


def env_info(torch) -> dict:
    free, total = torch.cuda.mem_get_info()
    drv = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    import PIL
    return {"date": datetime.datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(),
            "platform": platform.platform(), "cpu": platform.processor(), "numpy": np.__version__,
            "pillow": PIL.__version__, "torch": torch.__version__, "torch_cuda": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(), "gpu": torch.cuda.get_device_name(0), "driver": drv,
            "gpu_mem_free_MiB": free // 2**20, "gpu_mem_total_MiB": total // 2**20,
            "warmup": WARMUP, "tolerances": TOL,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "thread_env": {k: os.environ.get(k) for k in _THREAD_ENV_VARS},
            "torch_num_threads": torch.get_num_threads(), "numpy_blas": _blas_threads(),
            "cpu_load_1min": psutil.getloadavg()[0], "cpu_percent_1s": psutil.cpu_percent(interval=1.0),
            "logical_cpus": psutil.cpu_count()}


def _blas_threads():
    try:
        from threadpoolctl import threadpool_info
        return [{k: i.get(k) for k in ("internal_api", "num_threads")} for i in threadpool_info()]
    except ImportError:
        return "threadpoolctl not installed"


def timed(fn, reps, sync=None):
    ts = []
    for _ in range(WARMUP):
        fn()
    for _ in range(reps):
        if sync:
            sync()
        t0 = time.perf_counter()
        fn()
        if sync:
            sync()
        ts.append(time.perf_counter() - t0)
    q = statistics.quantiles(ts, n=4)
    return {"median_s": statistics.median(ts), "min_s": min(ts), "max_s": max(ts), "q1_s": q[0], "q3_s": q[2]}


def compare(stage, cpu, gpu) -> dict:
    tol = TOL[stage]
    if cpu.shape != gpu.shape or cpu.dtype != gpu.dtype:
        return {"equivalent": False, "note": f"shape/dtype mismatch {cpu.shape} {cpu.dtype} vs {gpu.shape} {gpu.dtype}"}
    d = np.abs(cpu.astype(np.float64) - gpu.astype(np.float64))
    m = {"max_abs": float(d.max()), "mean_abs": float(d.mean()), "frac_diff": float((d > 0).mean()),
         "max_rel": float((d / np.maximum(np.abs(cpu.astype(np.float64)), 1e-300)).max())}
    ok = (m["max_rel"] <= tol["rel"]) if "rel" in tol else (m["max_abs"] <= tol["max_abs"] and m["frac_diff"] <= tol["frac"])
    return {"equivalent": bool(ok), **m}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=15)
    ap.add_argument("--out", default=str(ROOT / "data" / "results" / "stage1_20261011" / "gpu"))
    ap.add_argument("--sides", type=int, nargs="*", default=list(SIDES))
    a = ap.parse_args()
    if a.reps < 10:
        sys.exit("--reps must be >= 10")
    if not cuda_available():
        sys.exit("CUDA unavailable: no GPU evidence can be produced")
    import torch
    sync = torch.cuda.synchronize
    torch.set_num_threads(1)  # explicit, in addition to the env vars
    out = Path(a.out) / ("spike_" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
    out.mkdir(parents=True, exist_ok=False)  # never reuse / overwrite a recorded directory
    env = env_info(torch)
    rows = []
    for side in a.sides:
        scene = STAGES["img_source"].compute([], {"height": side, "width": side, "seed": 0})
        edges_in = STAGES["img_edges"].compute([scene], {})
        for stage, params in CASES:
            x = [edges_in] if stage == "img_features" else [scene]
            cpu_fn, gpu_fn = STAGES[stage].compute, CUDA_STAGES[stage]
            cpu_out, gpu_out = cpu_fn(x, params), gpu_fn(x, params)
            eq = compare(stage, np.asarray(cpu_out), np.asarray(gpu_out))
            tc = timed(lambda: cpu_fn(x, params), a.reps)
            tg = timed(lambda: gpu_fn(x, params), a.reps, sync)
            su = tc["median_s"] / tg["median_s"]
            row = {"stage": stage, "params": json.dumps(params), "side": side, "pixels": side * side, "reps": a.reps,
                   **{f"cpu_{k}": v for k, v in tc.items()}, **{f"gpu_{k}": v for k, v in tg.items()},
                   "speedup": su, **eq, "verdict": "PASS" if eq["equivalent"] and su > 1 else "DROPPED"}
            rows.append(row)
            print(f"{stage:13s} {params!s:34s} {side:5d}px cpu {tc['median_s']*1e3:9.3f} ms  gpu {tg['median_s']*1e3:8.3f} ms  "
                  f"x{su:6.2f}  eq={eq['equivalent']} maxabs={eq.get('max_abs')}  {row['verdict']}", flush=True)
            torch.cuda.empty_cache()
    env["cpu_load_1min_end"] = psutil.getloadavg()[0]
    with open(out / "gpu_spike.json", "x", encoding="utf-8") as f:
        json.dump({"env": env, "rows": rows}, f, indent=1)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(out / "gpu_spike.csv", "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print("wrote", out)


if __name__ == "__main__":
    main()
