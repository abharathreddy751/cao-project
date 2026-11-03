"""Solo kernel-time profile (E1 input) of the image-pipeline stages on pools P, E and G at one tile size.

One representative task per stage type of ``build_image_pipeline`` (the first of its type; inputs are the real artifacts
of a CPU reference run, so every stage sees realistic data). Timed quantity = the stage's compute only (the same
``compute`` seconds a worker reports as ``wall_time_seconds``); for G this INCLUDES the host-device copies, which sit
inside the CUDA stage functions and are not separated. Warm-up repetitions are discarded.
  P, E: this process pinned (psutil cpu_affinity) to the first logical processor of each CPU pool, one thread.
  G:    a worker of a 'cuda' pool (started after the CPU pass, so no CUDA process runs during CPU timing) executes
        the stage as in a real run; stages without a CUDA variant get no G entry.
This script only measures; whether a stage may use G is decided by gpu_stage_table_from_spike, not here.

Outputs under --out (must not exist; files are created exclusively, nothing is overwritten):
  <stamp>_profile.json      StaticProfileEstimator.from_file format {workload, size, pool, median_s, ...}
  <stamp>_raw.csv           every measurement, failed ones too (only ok ones enter the profile)
  <stamp>_environment.json  caosched.experiment.runner.environment_manifest()

  python scripts/profile_gpu_workload.py --out data/profiles/gpu_workload_t512 --tile 512 [--n-images 16]
         [--denoise-iterations 1] [--reps 5] [--warmup 2] [--no-gpu]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import shutil
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from caosched.util.threadpin import pin_single_thread  # noqa: E402

pin_single_thread()  # before numpy is imported

from caosched.apps.artifacts import artifact_path, read_artifacts, write_artifact  # noqa: E402
from caosched.apps.cuda_stages import CUDA_STAGES, cuda_available  # noqa: E402
from caosched.apps.image_pipeline import build_image_pipeline, run_reference  # noqa: E402
from caosched.apps.stages import run_stage  # noqa: E402
from caosched.core.task import TaskMessage  # noqa: E402

FIELDS = ["task_id", "stage", "size", "pool", "rep", "wall_s", "ok", "error"]


def representatives(dag) -> dict:
    """stage type -> first task of that type."""
    reps: dict = {}
    for t in dag.tasks.values():
        reps.setdefault(t.workload, t)
    return reps


def measure_cpu(reps, ref, pools: dict[str, int], n: int, warmup: int, writer) -> None:
    import psutil

    proc, original = psutil.Process(), psutil.Process().cpu_affinity()
    try:
        for pool, slot in pools.items():
            proc.cpu_affinity([slot])
            if proc.cpu_affinity() != [slot]:
                raise RuntimeError(f"affinity readback mismatch for logical processor {slot}")
            for t in reps.values():
                blobs = [ref[d] for d in t.dependencies]
                for rep in range(warmup + n):
                    try:
                        wall, err = run_stage(t.workload, blobs, t.params)[1], ""
                    except Exception as exc:  # noqa: BLE001 - recorded, not hidden
                        wall, err = None, f"{type(exc).__name__}: {exc}"
                    if rep >= warmup:
                        writer.writerow(dict(task_id=t.task_id, stage=t.workload, size=t.size, pool=pool, rep=rep - warmup,
                                             wall_s=wall, ok=not err, error=err))
    finally:
        proc.cpu_affinity(original)


def measure_cuda(reps, ref, scratch: Path, n: int, warmup: int, writer, timeout_s: float = 600.0) -> None:
    from caosched.core.runtime_config import PoolSpec
    from caosched.core.worker_pool import WorkerPool

    with WorkerPool(pools={"G": PoolSpec((0,), "cuda")}, warmup=False) as pool:
        for t in (t for t in reps.values() if t.workload in CUDA_STAGES):
            for d in t.dependencies:
                write_artifact(artifact_path(scratch, d), ref[d])
            for rep in range(warmup + n):
                msg = TaskMessage(f"{t.task_id}_r{rep}", t.workload, t.size, t.seed, params=dict(t.params),
                                  input_refs=tuple(str(artifact_path(scratch, d)) for d in t.dependencies),
                                  output_ref=str(artifact_path(scratch, f"{t.task_id}_r{rep}")))
                pool.submit("G0", msg)
                res = pool.poll_result(timeout_s)
                if res is None:
                    raise RuntimeError(f"G worker gave no result for {msg.task_id} within {timeout_s}s")
                if rep >= warmup:
                    writer.writerow(dict(task_id=t.task_id, stage=t.workload, size=t.size, pool="G", rep=rep - warmup,
                                         wall_s=res.wall_time_seconds, ok=res.error is None,
                                         error=(res.error or "").strip().splitlines()[-1] if res.error else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="new directory (must not exist)")
    ap.add_argument("--tile", type=int, required=True)
    ap.add_argument("--n-images", type=int, default=16, help="perfect square (grid*grid tile branches)")
    ap.add_argument("--denoise-iterations", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--no-gpu", action="store_true", help="profile P and E only")
    a = ap.parse_args(argv)
    grid = math.isqrt(a.n_images)
    if grid * grid != a.n_images:
        sys.exit("--n-images must be a perfect square")
    gpu = not a.no_gpu
    if gpu and not cuda_available():
        sys.exit("CUDA unavailable: rerun with --no-gpu for a CPU-only profile")
    from caosched.core.runtime_config import RuntimeConfig
    from caosched.experiment.runner import environment_manifest

    cfg = RuntimeConfig.from_topology(max_p_slots=None)
    pools = {n: s.slots[0] for n, s in cfg.pools.items() if s.kind == "cpu" and s.slots}
    dag = build_image_pipeline(a.tile * grid, a.tile * grid, grid, a.seed, denoise_iterations=a.denoise_iterations)
    ref = run_reference(dag)
    reps = representatives(dag)
    out = Path(a.out)
    out.mkdir(parents=True)  # exclusive: never write into an existing profile directory
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    (out / f"{stamp}_environment.json").write_text(json.dumps(environment_manifest(), indent=2, default=str), encoding="utf-8")
    scratch = out / "scratch"
    scratch.mkdir()
    rows: list[dict] = []

    class Tee:  # write every row to the CSV and keep it for the profile
        def __init__(self, w):
            self.w = w

        def writerow(self, row):
            rows.append(row)
            self.w.writerow(row)

    try:
        with (out / f"{stamp}_raw.csv").open("x", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            measure_cpu(reps, ref, pools, a.reps, a.warmup, Tee(w))
            if gpu:
                measure_cuda(reps, ref, scratch, a.reps, a.warmup, Tee(w))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    entries = []
    for (stage, size, pool) in sorted({(r["stage"], r["size"], r["pool"]) for r in rows}):
        ks = [r["wall_s"] for r in rows if (r["stage"], r["size"], r["pool"]) == (stage, size, pool) and r["ok"]]
        if ks:
            entries.append({"workload": stage, "size": size, "pool": pool, "n": len(ks), "median_s": statistics.median(ks),
                            "mean_s": statistics.fmean(ks), "min_s": min(ks), "max_s": max(ks),
                            "stdev_s": statistics.stdev(ks) if len(ks) > 1 else 0.0})
    prof = {"schema_version": 1, "metric": "kernel_wall_time_seconds", "statistic": "median",
            "conditions": "solo; P/E: process pinned to one logical processor of the pool; G: cuda-pool worker, "
                          "kernel time includes host-device copies",
            "generated_at": stamp, "source_csv": f"{stamp}_raw.csv", "tile": a.tile, "n_images": a.n_images,
            "denoise_iterations": a.denoise_iterations, "seed": a.seed, "pools": {**pools, **({"G": 0} if gpu else {})},
            "reps": a.reps, "warmup": a.warmup, "entries": entries}
    (out / f"{stamp}_profile.json").write_text(json.dumps(prof, indent=1), encoding="utf-8")
    for e in entries:
        print(f"{e['workload']:14s} {e['pool']}  median {e['median_s'] * 1e3:10.3f} ms  (n={e['n']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
