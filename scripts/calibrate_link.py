"""Calibrate the emulated remote pool on THIS machine and write the E1 profile the remote experiment needs. [not yet run]

Starts the loopback node on one E core behind the link shim set to ZERO delay and runs the remote-eligible image stages through
it, solo, on the real input artifacts of a CPU reference run. Two things are measured:
  * R kernel times (node on an E core of this machine) per (stage, pixels): the 'R' rows of the E1 profile;
  * the socket cost of the mechanism: transfer_s = a + b * payload_bytes, least-squares over the non-warm-up rows (the same
    ``fit_link_calibration`` as ``scripts/profile_static.py``). It is the measured loopback/serialisation cost, NOT a network
    property; the configured link delay is added on top by ``FileTransferModel`` at scheduling time.
The P and E rows are copied from a base profile (``scripts/profile_gpu_workload.py --no-gpu`` at the experiment tile); the
output is a StaticProfileEstimator file (P, E, R rows) with ``link_calibration``. Output files are created exclusively.

  python scripts/profile_gpu_workload.py --out data/profiles/remote_t512 --tile 512 --n-images 16 --no-gpu
  python scripts/calibrate_link.py --base-profile data/profiles/remote_t512/<stamp>_profile.json --out data/profiles/remote_t512/remote_profile.json
         [--tile 512] [--calib-tiles 64 128 256 512] [--reps 5] [--warmup 2] [--max-p-slots 2]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import importlib.util
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from caosched.apps.artifacts import artifact_path, write_artifact  # noqa: E402
from caosched.apps.image_pipeline import build_image_pipeline, run_reference  # noqa: E402
from caosched.core.coordinator import pin_coordinator_to_reserved_core  # noqa: E402
from caosched.core.task import TaskMessage  # noqa: E402
from caosched.core.worker_pool import RemoteSlot, WorkerPool  # noqa: E402
from caosched.experiment.remote_adapter import DEFAULT_REMOTE_STAGES, REMOTE_POOL, RemoteAdapter  # noqa: E402
from caosched.remote.link import LinkConfig  # noqa: E402

FIELDS = ["tile", "task_id", "stage", "size", "rep", "is_warmup", "kernel_s", "transfer_s", "payload_bytes", "ok", "error"]


def _fit():
    spec = importlib.util.spec_from_file_location("profile_static", ROOT / "scripts" / "profile_static.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.fit_link_calibration  # single source of the fit


def measure(pool: WorkerPool, tiles, grid: int, reps: int, warmup: int, scratch: Path, stages, writer, timeout_s=300.0) -> list[dict]:
    rows = []
    for tile in tiles:
        dag = build_image_pipeline(tile * grid, tile * grid, grid, 0)
        ref = run_reference(dag)
        first = {}
        for t in dag.tasks.values():
            first.setdefault(t.workload, t)
        for st in stages:
            t = first[st]
            sub = scratch / f"t{tile}"
            sub.mkdir(parents=True, exist_ok=True)
            for d in t.dependencies:
                write_artifact(artifact_path(sub, d), ref[d])
            for rep in range(warmup + reps):
                msg = TaskMessage(f"{t.task_id}_t{tile}_r{rep}", t.workload, t.size, t.seed, params=dict(t.params),
                                  input_refs=tuple(str(artifact_path(sub, d)) for d in t.dependencies),
                                  output_ref=str(artifact_path(sub, f"{t.task_id}_r{rep}")))
                pool.submit(f"{REMOTE_POOL}0", msg)
                res = pool.poll_result(timeout_s)
                if res is None:
                    raise RuntimeError(f"node gave no result for {msg.task_id} within {timeout_s}s")
                row = dict(tile=tile, task_id=t.task_id, stage=st, size=t.size, rep=rep, is_warmup=rep < warmup,
                           kernel_s=res.wall_time_seconds, transfer_s=res.transfer_s, payload_bytes=res.payload_bytes,
                           ok=res.error is None, error=(res.error or "").strip().splitlines()[-1] if res.error else "")
                writer.writerow(row)
                rows.append(row)
    return rows


def build_profile(base: dict, rows: list[dict], extra: dict) -> dict:
    ok = [r for r in rows if r["ok"] and not r["is_warmup"]]
    if len(ok) < 2 or len(ok) < len([r for r in rows if not r["is_warmup"]]):
        raise RuntimeError("calibration rows failed or too few; see the raw CSV")
    entries = [e for e in base["entries"] if e["pool"] != REMOTE_POOL]
    for (stage, size) in sorted({(r["stage"], r["size"]) for r in ok}):
        ks = [r["kernel_s"] for r in ok if (r["stage"], r["size"]) == (stage, size)]
        entries.append({"workload": stage, "size": size, "pool": REMOTE_POOL, "n": len(ks), "median_s": statistics.median(ks),
                        "mean_s": statistics.fmean(ks), "min_s": min(ks), "max_s": max(ks),
                        "stdev_s": statistics.stdev(ks) if len(ks) > 1 else 0.0})
    return {**{k: v for k, v in base.items() if k != "entries"}, **extra, "entries": entries,
            "link_calibration": _fit()(rows)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-profile", required=True, help="P/E profile at the experiment tile (profile_gpu_workload.py --no-gpu)")
    ap.add_argument("--out", required=True, help="new profile file (must not exist); the raw CSV goes next to it")
    ap.add_argument("--tile", type=int, default=512, help="experiment tile: its stages need P, E and R rows")
    ap.add_argument("--n-images", type=int, default=16, help="experiment branches (the pipeline grid is sqrt of this)")
    ap.add_argument("--calib-tiles", type=int, nargs="+", default=[64, 128, 256, 512], help="tile sides for the payload spread")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--max-p-slots", type=int, default=2)
    ap.add_argument("--node-core", type=int, default=None)
    a = ap.parse_args(argv)
    if a.tile not in a.calib_tiles:
        sys.exit("--calib-tiles must include --tile (its R rows are the experiment's)")
    base = json.loads(Path(a.base_profile).read_text(encoding="utf-8"))
    need = {(s, a.tile * a.tile, p) for s in DEFAULT_REMOTE_STAGES for p in ("P", "E")}
    have = {(e["workload"], e["size"], e["pool"]) for e in base["entries"]}
    if need - have:
        sys.exit(f"base profile lacks P/E rows {sorted(need - have)}")
    out = Path(a.out)
    raw = out.with_name(out.stem + "_raw.csv")
    cfg, node = RemoteAdapter(max_p_slots=a.max_p_slots, node_core=a.node_core)._layout()
    pin_coordinator_to_reserved_core(cfg)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    with tempfile.TemporaryDirectory() as tmp, raw.open("x", newline="", encoding="utf-8") as fh, \
            WorkerPool(warmup=False, strict_affinity=True,
                       remote_slots=[RemoteSlot(LinkConfig("zero"), node_core=node, proxy_core=cfg.coordinator_core)]) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        rows = measure(pool, a.calib_tiles, math.isqrt(a.n_images), a.reps, a.warmup, Path(tmp), DEFAULT_REMOTE_STAGES, w)
    prof = build_profile(base, rows, {"generated_at": stamp, "base_profile": str(a.base_profile), "source_csv_remote": raw.name,
                                      "remote_node_core": node, "calibration_tiles": a.calib_tiles,
                                      "calibration_label": "emulation: loopback socket of this machine with the shim at zero; "
                                                           "not a network measurement"})
    with out.open("x", encoding="utf-8") as f:
        json.dump(prof, f, indent=1)
    cal = prof["link_calibration"]
    print(f"link calibration (shim zero): transfer = {cal['socket_a_s'] * 1e3:.3f} ms + {cal['socket_b_s_per_byte'] * 1e9:.3f} ns/byte "
          f"(n={cal['n']}, median |resid| {cal['median_abs_residual_s'] * 1e3:.3f} ms) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
