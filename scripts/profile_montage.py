"""Stage 3: solo kernel-time profile of the real Montage tasks, per transformation and pool.

Re-executes the commands of a COMPLETED sequential reference run (``run.json`` + its ``work/`` directory, written by
scripts/montage_sequential.py), one at a time, with this process pinned (psutil cpu_affinity, inherited by the child)
to ONE logical processor of each pool in turn (first slot of the pool: one P slot, one E slot). Per execution a fresh
scratch directory under ``<out>/scratch`` gets copies of only that task's declared inputs from the reference work
directory (which is only read); outputs land in the scratch directory, which is removed afterwards. Timed:
the command only (copy-in and clean-up excluded). Refuses to start, and stops, if free RAM < ``--min-free-ram-gb``.

Outputs under --out (created exclusively, nothing is overwritten):
  <stamp>_profile.json       StaticProfileEstimator.from_file format (metric kernel_wall_time_seconds, entries
                             {workload: <transformation>, size: 1, pool, median_s}) + ``linear_fit``:
                             "<transformation>|<pool>" -> {a, b, n, r2} for time ~ a + b * input_bytes
  <stamp>_raw.csv            every measurement (failed ones too; only ok ones enter the profile)
  <stamp>_environment.json   caosched.experiment.runner.environment_manifest()

  python scripts/profile_montage.py --run-dir data/results/stage1_20261011/seq_runB --out data/profiles/montage_20261011 \
      [--reps 2] [--max-per-transformation N] [--mproject-max 2] [--min-free-ram-gb 2]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from caosched.core.extcmd import _make_writable_and_retry

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["order", "task_id", "transformation", "pool", "logical_processor", "rep", "input_bytes", "output_bytes",
          "wall_s", "exit", "ok", "free_ram_gb", "tail"]


def free_ram_gb() -> float:
    import psutil
    return psutil.virtual_memory().available / 2**30


def load_tasks(run_dir: Path) -> tuple[list[dict], Path]:
    """Tasks of the reference run that succeeded and whose inputs still exist, with their input size."""
    work = run_dir / "work"
    tasks, skipped = [], []
    for t in json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["tasks"]:
        files = [work / f for f in t["inputs"]]
        if not t.get("ok") or not all(f.is_file() for f in files):
            skipped.append(t["id"])
            continue
        tasks.append({**t, "input_bytes": sum(f.stat().st_size for f in files)})
    if skipped:
        print(f"skipping {len(skipped)} task(s) that failed or lack inputs in the reference work dir: {skipped[:8]}")
    return tasks, work


def pick(tasks: list[dict], k: int | None) -> list[dict]:
    """At most k tasks spread evenly over the input sizes (smallest and largest included)."""
    tasks = sorted(tasks, key=lambda t: (t["input_bytes"], t["id"]))
    if k is None or k >= len(tasks):
        return tasks
    if k == 1:
        return [tasks[len(tasks) // 2]]
    return [tasks[i] for i in sorted({round(j * (len(tasks) - 1) / (k - 1)) for j in range(k)})]


def run_command(argv: list[str], cwd: Path, env: dict, timeout_s: float) -> tuple[float, int, str]:
    t0 = time.perf_counter()
    try:
        r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s)
        rc, tail = r.returncode, (r.stdout + r.stderr).strip()[-400:]
    except (subprocess.TimeoutExpired, OSError) as exc:
        rc, tail = -1, f"{type(exc).__name__}: {exc}"
    return time.perf_counter() - t0, rc, tail


def linear_fit(points: list[tuple[float, float]]) -> dict:
    x, y = np.array([p[0] for p in points]), np.array([p[1] for p in points])
    if len(set(x)) < 2:  # one input size: no slope to fit
        return {"a": float(np.median(y)), "b": 0.0, "n": len(y), "r2": None}
    b, a = np.polyfit(x, y, 1)
    ss = float(((y - y.mean()) ** 2).sum())
    return {"a": float(a), "b": float(b), "n": len(y),
            "r2": None if ss == 0 else 1 - float(((y - (a + b * x)) ** 2).sum()) / ss}


def profile(run_dir: Path, out: Path, pools: dict[str, int], bin_dir: Path, reps: int = 2, max_per: int | None = None,
            mproject_max: int | None = 2, min_free_gb: float = 2.0, timeout_s: float = 3600.0, free_fn=free_ram_gb) -> dict:
    """``pools``: pool name -> the logical processor to pin to. Returns the profile dict that was written."""
    import psutil

    if free_fn() < min_free_gb:
        raise SystemExit(f"refusing to start: free RAM {free_fn():.2f} GB < {min_free_gb} GB")
    tasks, ref_work = load_tasks(Path(run_dir))
    by_tr: dict[str, list[dict]] = {}
    for t in tasks:
        by_tr.setdefault(t["name"], []).append(t)
    chosen = []
    for name, ts in sorted(by_tr.items()):
        caps = [k for k in (max_per, mproject_max if name == "mProject" else None) if k is not None]
        chosen += pick(ts, min(caps, default=None))
    from caosched.experiment.runner import environment_manifest
    out.mkdir(parents=True)  # exclusive: never write into an existing profile directory
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    (out / f"{stamp}_environment.json").write_text(json.dumps(environment_manifest(), indent=2, default=str), encoding="utf-8")
    scratch = out / "scratch"
    scratch.mkdir()
    env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}
    proc = psutil.Process()
    original = proc.cpu_affinity()
    meas: dict[tuple[str, str], list[dict]] = {}
    order = 0
    try:
        with (out / f"{stamp}_raw.csv").open("x", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            for t in chosen:
                for pool, slot in pools.items():
                    proc.cpu_affinity([slot])
                    if proc.cpu_affinity() != [slot]:
                        raise RuntimeError(f"affinity readback mismatch for logical processor {slot}")
                    for rep in range(reps):
                        free = free_fn()
                        if free < min_free_gb:
                            raise SystemExit(f"stopping: free RAM {free:.2f} GB < {min_free_gb} GB (raw CSV kept, no profile written)")
                        d = scratch / f"{order:05d}"
                        d.mkdir()  # created here, so removed here
                        try:
                            for f in t["inputs"]:
                                shutil.copy2(ref_work / f, d / f)
                            wall, rc, tail = run_command([str(bin_dir / t["argv"][0]), *t["argv"][1:]], d, env, timeout_s)
                            made = [d / o["lfn"] for o in t["outputs"]]
                            ok = rc == 0 and 'stat="ERROR"' not in tail and all(p.is_file() for p in made)
                            out_bytes = sum(p.stat().st_size for p in made if p.is_file())
                        finally:
                            shutil.rmtree(d, onerror=_make_writable_and_retry)
                        row = {"order": order, "task_id": t["id"], "transformation": t["name"], "pool": pool,
                               "logical_processor": slot, "rep": rep, "input_bytes": t["input_bytes"],
                               "output_bytes": out_bytes, "wall_s": wall, "exit": rc, "ok": ok, "free_ram_gb": free,
                               "tail": "" if ok else tail}
                        w.writerow(row)
                        fh.flush()
                        if ok:
                            meas.setdefault((t["name"], pool), []).append(row)
                        order += 1
    finally:
        proc.cpu_affinity(original)
        if scratch.is_dir() and not any(scratch.iterdir()):
            scratch.rmdir()
    entries, fits = [], {}
    for (name, pool), rows in sorted(meas.items()):
        ks = [r["wall_s"] for r in rows]
        entries.append({"workload": name, "size": 1, "pool": pool, "n": len(ks), "median_s": statistics.median(ks),
                        "mean_s": statistics.fmean(ks), "min_s": min(ks), "max_s": max(ks),
                        "stdev_s": statistics.stdev(ks) if len(ks) > 1 else 0.0,
                        "n_tasks": len({r["task_id"] for r in rows})})
        fits[f"{name}|{pool}"] = linear_fit([(r["input_bytes"], r["wall_s"]) for r in rows])
    run_json = Path(run_dir) / "run.json"
    prof = {"schema_version": 1, "metric": "kernel_wall_time_seconds", "statistic": "median",
            "conditions": "solo (one task in flight), process pinned to one logical processor of the pool, scratch work dir",
            "generated_at": stamp, "source_csv": f"{stamp}_raw.csv", "source_run": str(run_json),
            "source_run_sha256": hashlib.sha256(run_json.read_bytes()).hexdigest(), "pools": pools, "reps": reps,
            "n_tasks_profiled": len(chosen), "entries": entries,
            "linear_fit": {"model": "wall_s = a + b * input_bytes (np.polyfit over the ok measurements)", "fits": fits}}
    (out / f"{stamp}_profile.json").write_text(json.dumps(prof, indent=1), encoding="utf-8")
    return prof


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True, help="completed sequential run (run.json + work/)")
    ap.add_argument("--out", required=True, help="new directory (must not exist)")
    ap.add_argument("--bin-dir", default=str(ROOT / "data" / "montage" / "bin_win64"))
    ap.add_argument("--reps", type=int, default=2, help="executions per task and pool")
    ap.add_argument("--max-per-transformation", type=int, default=None, help="default: all tasks")
    ap.add_argument("--mproject-max", type=int, default=2, help="cap for mProject (slow); 0 = no extra cap")
    ap.add_argument("--min-free-ram-gb", type=float, default=2.0)
    ap.add_argument("--timeout-s", type=float, default=3600.0)
    a = ap.parse_args(argv)
    from caosched.core.runtime_config import RuntimeConfig
    rc = RuntimeConfig.from_topology(max_p_slots=None)
    pools = {n: s.slots[0] for n, s in rc.pools.items() if s.kind == "cpu" and s.slots}
    print(f"pools -> pinned logical processor: {pools}")
    prof = profile(Path(a.run_dir), Path(a.out), pools, Path(a.bin_dir), a.reps, a.max_per_transformation,
                   a.mproject_max or None, a.min_free_ram_gb, a.timeout_s)
    for e in prof["entries"]:
        print(f"{e['workload']:12s} {e['pool']}  median {e['median_s']:9.3f} s  (n={e['n']}, tasks={e['n_tasks']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
