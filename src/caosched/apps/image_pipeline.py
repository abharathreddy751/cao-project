"""Tiled image-analysis application, expressed as a DAG of real stage tasks.

    source -> tile_i -> denoise_i -> edges_i -> features_i      (i = 0 .. g*g-1)
    mosaic   <- edges_0 .. edges_{n-1}       (fan-in, input order = tile order)
    aggregate<- features_0 .. features_{n-1}
    package  <- mosaic, aggregate            (final output artifact)

Task ``size`` = pixels processed by the stage (the estimator key), ``seed``
= the application seed, ``params`` = stage parameters. ``remote_stages``
marks which stage types may run on remote pools; all others are restricted
to the local P/E pools (``eligible_pools``).

``run_reference`` executes the identical stage functions sequentially in one
process; ``verify_output`` compares a scheduled run's final artifact with it.
"""
from __future__ import annotations

import hashlib
import zlib

import numpy as np

from caosched.apps.stages import STAGES, run_stage
from caosched.core.dag import DAG
from caosched.core.task import Task

LOCAL_POOLS = ("P", "E")
STAGE_TYPES = ("img_source", "img_tile", "img_denoise", "img_edges", "img_features", "img_mosaic",
               "img_aggregate", "img_package")


def build_image_pipeline(width: int = 1024, height: int = 1024, grid: int = 4, seed: int = 0,
                         radius: float = 2.0, denoise_iterations: int = 1, remote_stages: dict[str, list[str]] | None = None,
                         device_params: dict[str, dict] | None = None) -> DAG:
    """``remote_stages``: stage type -> extra pools it may use (e.g.
    {"img_denoise": ["R"], "img_edges": ["R"]}). ``device_params``: stage type
    -> params merged into every task of that type (e.g. {"img_edges":
    {"device": "cuda"}} for a GPU pool). ``denoise_iterations``: how many times
    the denoise stage applies its blur (workload-intensity knob; 1 = original)."""
    if width % grid or height % grid:
        raise ValueError("width and height must be divisible by grid")
    remote_stages = remote_stages or {}
    device_params = device_params or {}
    n = grid * grid
    full, tile = width * height, (width // grid) * (height // grid)

    def task(tid, stage, size, params, deps=()):
        pools = tuple(LOCAL_POOLS) + tuple(remote_stages.get(stage, ()))
        return Task(task_id=tid, workload=stage, size=size, seed=seed, dependencies=tuple(deps),
                    params={**params, **device_params.get(stage, {})}, eligible_pools=pools)

    tasks = [task("source", "img_source", full, {"width": width, "height": height, "seed": seed})]
    for i in range(n):
        tasks += [task(f"tile_{i}", "img_tile", tile, {"grid": grid, "index": i}, ["source"]),
                  task(f"denoise_{i}", "img_denoise", tile, {"radius": radius, "iterations": int(denoise_iterations)},
                       [f"tile_{i}"]),
                  task(f"edges_{i}", "img_edges", tile, {}, [f"denoise_{i}"]),
                  task(f"features_{i}", "img_features", tile, {}, [f"edges_{i}"])]
    tasks += [task("mosaic", "img_mosaic", full, {"grid": grid}, [f"edges_{i}" for i in range(n)]),
              task("aggregate", "img_aggregate", n, {}, [f"features_{i}" for i in range(n)]),
              task("package", "img_package", full, {"level": 6}, ["mosaic", "aggregate"])]
    return DAG({t.task_id: t for t in tasks})


def run_reference(dag: DAG) -> dict[str, bytes]:
    """Execute every stage sequentially in this process (same functions)."""
    out: dict[str, bytes] = {}
    for tid in dag.topological_order():
        t = dag.tasks[tid]
        out[tid], _, _ = run_stage(t.workload, [out[d] for d in t.dependencies], t.params or {})
    return out


def unpack_package(blob: bytes) -> tuple[np.ndarray, np.ndarray]:
    raw = zlib.decompress(blob)
    shape = np.frombuffer(raw[:24], dtype=np.int64)
    h, w, d = int(shape[0]), int(shape[1]), int(shape[2])
    mosaic = np.frombuffer(raw[24:24 + h * w], dtype=np.uint8).reshape(h, w)
    desc = np.frombuffer(raw[24 + h * w:], dtype=np.float64)
    if desc.size != d:
        raise ValueError("corrupt package: descriptor length mismatch")
    return mosaic, desc


def verify_output(final_blob: bytes, reference_blob: bytes) -> dict:
    """Bit-exact match, else numeric closeness (a different CPU, e.g. ARM, may
    round float32 differently); reports which."""
    a, b = hashlib.sha256(final_blob).hexdigest(), hashlib.sha256(reference_blob).hexdigest()
    if a == b:
        return {"match": "exact", "sha256": a}
    ma, da = unpack_package(final_blob)
    mb, db = unpack_package(reference_blob)
    same_shape = ma.shape == mb.shape and da.shape == db.shape
    diff = int(np.abs(ma.astype(int) - mb.astype(int)).max()) if same_shape else None
    close = same_shape and diff <= 1 and bool(np.allclose(da, db, rtol=1e-5, atol=1e-6))
    return {"match": "numeric" if close else "MISMATCH", "sha256": a, "reference_sha256": b,
            "max_mosaic_diff": diff}


if set(STAGE_TYPES) != set(STAGES):
    raise RuntimeError("image pipeline stage list out of sync with the stage registry")
