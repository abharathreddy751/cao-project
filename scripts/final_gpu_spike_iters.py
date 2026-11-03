"""Final study: extend the recorded GPU spike to the denoise iteration counts of the hidden-cost workload (tile 512).

The recorded spike (data/results/stage1_20261011/gpu/gpu_spike.json) has img_denoise at tile 512 only for iterations 1 (DROPPED) and 8
(PASS); the hidden-cost workload uses 2 and 120 (and the dose-response levels 6, 15, 40). By the project rule (AD-6) a stage is GPU
evidence only with a CPU reference, an equivalence check inside a tolerance fixed BEFORE the run, and a measured speed-up that includes
the host-device copies. This script applies exactly that rule, with the original ``compare``, ``timed``, tolerances and verdict
(imported from scripts/gpu_spike.py, not copied), to the additional iteration counts, and writes a NEW record. It does not touch the
original record. A row with verdict PASS may then be used for GPU eligibility in the "extended" benchmark family; the strict family
uses only the original record.

  python scripts/final_gpu_spike_iters.py --out data/results/final_20261101/gpu_spike_iters [--reps 15]
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_spec = importlib.util.spec_from_file_location("gpu_spike", ROOT / "scripts" / "gpu_spike.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

SIDE = 512
ITERATIONS = (2, 6, 15, 40, 120)
RADIUS = 2.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=15)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.reps < 10:
        sys.exit("--reps must be >= 10")
    if not sp.cuda_available():
        sys.exit("CUDA unavailable: no GPU evidence can be produced")
    import torch
    sync = torch.cuda.synchronize
    torch.set_num_threads(1)
    out = Path(a.out) / ("spike_" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
    out.mkdir(parents=True, exist_ok=False)
    env = sp.env_info(torch)
    env["extends"] = "data/results/stage1_20261011/gpu/gpu_spike.json (same compare/timed/tolerances, imported from scripts/gpu_spike.py)"
    scene = sp.STAGES["img_source"].compute([], {"height": SIDE, "width": SIDE, "seed": 0})
    rows = []
    for it in ITERATIONS:
        params = {"radius": RADIUS, "iterations": it}
        x = [scene]
        cpu_fn, gpu_fn = sp.STAGES["img_denoise"].compute, sp.CUDA_STAGES["img_denoise"]
        import numpy as np
        eq = sp.compare("img_denoise", np.asarray(cpu_fn(x, params)), np.asarray(gpu_fn(x, params)))
        tc = sp.timed(lambda: cpu_fn(x, params), a.reps)
        tg = sp.timed(lambda: gpu_fn(x, params), a.reps, sync)
        su = tc["median_s"] / tg["median_s"]
        row = {"stage": "img_denoise", "params": json.dumps(params), "side": SIDE, "pixels": SIDE * SIDE, "reps": a.reps,
               **{f"cpu_{k}": v for k, v in tc.items()}, **{f"gpu_{k}": v for k, v in tg.items()}, "speedup": su, **eq,
               "verdict": "PASS" if eq["equivalent"] and su > 1 else "DROPPED"}
        rows.append(row)
        print(f"img_denoise {params!s:34s} {SIDE}px cpu {tc['median_s']*1e3:9.3f} ms  gpu {tg['median_s']*1e3:8.3f} ms  "
              f"x{su:6.2f}  eq={eq['equivalent']} maxabs={eq.get('max_abs')}  {row['verdict']}", flush=True)
        torch.cuda.empty_cache()
    with open(out / "gpu_spike.json", "x", encoding="utf-8") as f:
        json.dump({"env": env, "rows": rows}, f, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
