"""Stage 2-4 adapter: run ONE tiled image-pipeline instance (CPU pools P/E, optionally a CUDA pool 'G') under ONE condition.

Plug-in contract: ``caosched.experiment.design`` (same as ``montage_adapter``; the policy / estimator factory logic is
imported from there, not duplicated). No GPU speed-up is claimed by this code: it only runs a condition and checks the
output. Whether a stage may use the GPU is decided OUTSIDE, by ``kwargs['gpu_stage_table']``.

Per ``run_one``: ``build_image_pipeline`` (grid g with n_images = g*g tile branches, image side = tile * g) -> pools from
``RuntimeConfig`` (+ 'G' of kind 'cuda' iff some table stage is True, ``no_gpu`` is not set and CUDA is available) ->
policy from the condition -> Coordinator (artifacts under ``<workdir>/artifacts``, removed after verification) ->
output check against the CPU reference (``run_reference``) with the tolerances of ``scripts/gpu_spike.py`` (``TOL``,
``compare`` are imported from there): CUDA-executed tasks are re-run on the CPU from their own input artifacts and
compared per stage; the final package is compared with the reference (bit-exact / numeric for an all-CPU run; mosaic
within the edges tolerance, descriptor within the features tolerance unless edges ran on CUDA, otherwise).

Condition kwargs: ``tile`` (side in pixels, default 256), ``n_images`` (perfect square, default 16), ``seed`` (application
seed, default 0), ``denoise_iterations`` (default 1), ``gpu_stage_table`` ({stage: bool}; absent = no stage on G),
``no_gpu`` (true: CPU pools only, same DAG), ``profile`` / ``model_path`` / ``est_cfg`` / ``policy_cfg`` (as montage),
``timeout_s`` / ``run_timeout_s``, ``keep_artifacts``.
Host-device copy time is not measured separately: it is inside the CUDA stage's own kernel time.
``factory()`` reads constructor settings from the JSON file named by CAO_GPU_ADAPTER_CONFIG, if set.
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import importlib.util
import json
import math
import os
import shutil
from pathlib import Path

import numpy as np

from caosched.apps.artifacts import artifact_path, read_artifacts
from caosched.apps.cuda_stages import CUDA_STAGES, cuda_available
from caosched.apps.image_pipeline import build_image_pipeline, run_reference, unpack_package, verify_output
from caosched.apps.stages import STAGES, decode_arrays
from caosched.core.coordinator import Coordinator, RunTimeoutError, TaskTimeoutError, pin_coordinator_to_reserved_core
from caosched.core.event_log import EventLogger
from caosched.core.runtime_config import PoolSpec, RuntimeConfig
from caosched.core.worker_pool import WorkerPool
from caosched.experiment.design import Condition, RunRecord
from caosched.experiment.montage_adapter import build_policy

ROOT = Path(__file__).resolve().parents[3]
GPU_POOL = "G"


@functools.cache
def _spike():
    """scripts/gpu_spike.py as a module: the single source of the tolerances (TOL) and of ``compare``."""
    spec = importlib.util.spec_from_file_location("gpu_spike", ROOT / "scripts" / "gpu_spike.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gpu_stage_table_from_spike(path, tile: int, denoise_iterations: int = 1, radius: float = 2.0) -> dict[str, bool]:
    """{stage: bool} for the CUDA-capable stages: True only for a row of ``gpu_spike.json`` at tile side ``tile``
    (and, for denoise, these params) with verdict PASS (equivalent AND speed-up > 1). A stage with no such row is False."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["rows"]
    want = {"img_denoise": {"radius": radius, "iterations": denoise_iterations}, "img_edges": {}, "img_features": {}}
    return {s: any(r["stage"] == s and r["side"] == tile and json.loads(r["params"]) == p and r["verdict"] == "PASS"
                   for r in rows) for s, p in want.items()}


class GpuAdapter:
    def __init__(self, runtime_config: RuntimeConfig | None = None, timeout_s: float = 600.0,
                 run_timeout_s: float | None = None):
        self.runtime_config = runtime_config  # CPU pools; 'G' is added per condition
        self.timeout_s, self.run_timeout_s = timeout_s, run_timeout_s
        self._pool: WorkerPool | None = None
        self._pool_gpu = False
        self._ref: dict = {}

    def __getstate__(self):  # picklable for the runner's isolated mode
        return {**self.__dict__, "_pool": None, "_ref": {}}

    def _config(self, gpu: bool) -> RuntimeConfig:
        if self.runtime_config is None:
            self.runtime_config = RuntimeConfig.from_topology(max_p_slots=None)
        base = self.runtime_config
        return dataclasses.replace(base, pools={**(base.pools or {}), GPU_POOL: PoolSpec((0,), "cuda")}) if gpu else base

    def _get_pool(self, gpu: bool) -> WorkerPool:
        if self._pool is not None and (self._pool_gpu != gpu or self._pool.dead_workers()
                                       or self._pool.idle_workers() != self._pool.worker_ids()):
            self.close()
        if self._pool is None:
            self._pool = WorkerPool.from_config(self._config(gpu), warmup=False, strict_affinity=True)
            self._pool_gpu = gpu
        return self._pool

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown()

    # --- one run ---------------------------------------------------------------

    def build_dag(self, kw: dict, gpu_stages=()):
        """(dag, key): ``gpu_stages`` additionally get pool 'G' in their eligible pools; every other task stays P/E only."""
        tile, n = int(kw.get("tile", 256)), int(kw.get("n_images", 16))
        grid = math.isqrt(n)
        if grid * grid != n:
            raise ValueError(f"n_images must be a perfect square (build_image_pipeline makes grid*grid branches), got {n}")
        key = (tile, grid, int(kw.get("seed", 0)), int(kw.get("denoise_iterations", 1)))
        dag = build_image_pipeline(tile * grid, tile * grid, grid, key[2], denoise_iterations=key[3],
                                   remote_stages={s: [GPU_POOL] for s in gpu_stages})
        return dag, key

    def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord:
        workdir, kw = Path(workdir), condition.kwargs
        on = {s for s, v in (kw.get("gpu_stage_table") or {}).items() if v}
        if on - set(CUDA_STAGES):
            raise ValueError(f"gpu_stage_table names stages without a CUDA variant: {sorted(on - set(CUDA_STAGES))}")
        gpu = bool(on) and not kw.get("no_gpu")
        if gpu and not cuda_available():
            raise RuntimeError(f"{condition.name}: gpu_stage_table asks for CUDA stages {sorted(on)} but CUDA is unavailable")
        dag, key = self.build_dag(kw, on if gpu else ())
        if key not in self._ref:
            self._ref[key] = run_reference(dag)
        ref, art = self._ref[key], workdir / "artifacts"
        # kwargs['seed'] is the application seed here; montage's build_policy would read it as the random policy's seed
        policy = build_policy(dataclasses.replace(condition, kwargs={k: v for k, v in kw.items() if k != "seed"}), seed)
        run_id, log_name = workdir.name, f"{workdir.name}.jsonl"
        meta = {"experiment_id": workdir.parent.parent.name, "workflow_instance": condition.instance,
                "condition": condition.name, "policy": condition.policy, "estimator": condition.estimator, "seed": seed}
        extra = {"n_tasks": len(dag), "policy": policy.name, "tile": key[0], "grid": key[1], "n_images": key[1] ** 2,
                 "denoise_iterations": key[3], "gpu_pool": gpu, "gpu_stages": sorted(on) if gpu else [],
                 "h2d_d2h_copy_time": "not measured (inside the CUDA stage kernel time)"}
        status, error, summary = "ok", None, None
        try:
            pool = self._get_pool(gpu)
            cfg = self._config(gpu)
            pin_coordinator_to_reserved_core(cfg)
            with EventLogger(run_id, output_dir=workdir) as log:
                summary = Coordinator(dag, pool, policy, log, run_metadata=meta, artifact_dir=art).run(run_timeout=self.run_timeout_s)
        except Exception as exc:  # noqa: BLE001 - a failed run is data; the runner flags and keeps it
            status = "timeout" if isinstance(exc, (TaskTimeoutError, RunTimeoutError)) else "failed"
            error = f"{type(exc).__name__}: {exc}"
            self.close()
        if summary is not None:
            kinds = {p: s.kind for p, s in (self._config(gpu).pools or {}).items()}
            extra.update(decision_time_total_s=summary.scheduling_time_seconds, makespan_seconds=summary.makespan_seconds,
                         n_completed=summary.n_completed, tasks_per_pool=summary.tasks_per_pool,
                         task_placement={t.task_id: [t.assigned_pool, t.assigned_worker] for t in dag.tasks.values()},
                         cuda_tasks=sorted(t.task_id for t in dag.tasks.values() if kinds.get(t.assigned_pool) == "cuda"))
        rec = RunRecord(status=status, event_log=log_name if (workdir / log_name).is_file() else None, error=error,
                        input_hashes={"source": hashlib.sha256(ref["source"]).hexdigest()}, extra=extra)
        if status == "ok":
            try:
                rec.output_ok, rec.output_hashes = self._verify(dag, art, ref, extra)
            except Exception as exc:  # noqa: BLE001 - keep the run, unverified
                rec.output_ok, rec.error = False, f"verify raised {type(exc).__name__}: {exc}"
        if not kw.get("keep_artifacts"):
            shutil.rmtree(art, ignore_errors=True)
        return rec

    def _verify(self, dag, art: Path, ref: dict, extra: dict) -> tuple[bool, dict]:
        final = artifact_path(art, "package").read_bytes()
        cuda = extra["cuda_tasks"]
        if not cuda:
            v = verify_output(final, ref["package"])
            extra["output_verdict"] = v
            return v["match"] != "MISMATCH", {"package": v["sha256"]}
        spike, checks = _spike(), {}
        for tid in cuda:  # re-run the CPU stage on the CUDA task's own input artifacts
            t = dag.tasks[tid]
            objs = STAGES[t.workload].decode(read_artifacts([artifact_path(art, d) for d in t.dependencies]))
            got = decode_arrays(read_artifacts([artifact_path(art, tid)]))[0]
            checks[tid] = spike.compare(t.workload, np.asarray(STAGES[t.workload].compute(objs, t.params)), got)
        (mosaic, desc), (rmosaic, rdesc) = unpack_package(final), unpack_package(ref["package"])
        checks["final_mosaic"] = spike.compare("img_edges", rmosaic, mosaic)
        if not any(dag.tasks[t].workload == "img_edges" for t in cuda):  # else the descriptor input differs by design
            checks["final_descriptor"] = spike.compare("img_features", rdesc, desc)
        extra["output_verdict"] = checks
        return all(c["equivalent"] for c in checks.values()), {"package": hashlib.sha256(final).hexdigest()}


def factory() -> GpuAdapter:
    path = os.environ.get("CAO_GPU_ADAPTER_CONFIG")
    return GpuAdapter(**(json.loads(Path(path).read_text(encoding="utf-8")) if path else {}))
