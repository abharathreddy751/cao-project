"""Study 2 adapter: ONE batch DAG (``study2.workload.build_batch``) on pools P, E and optionally a CUDA pool 'G'.

Subclass of ``GpuAdapter`` (pool handling, picklability, reference cache are inherited, not copied); ``run_one`` and
``_verify`` are re-stated here because the stage 5 versions hard-code the 68-task pipeline (task ids ``source`` and
``package``). Policies come from the unchanged ``montage_adapter.build_policy`` (B0, B2 static map, B3, B4, EFT, HEFT ...).

Condition kwargs: ``k`` (chains, default 64), ``tile`` (image side, default 512), ``seed``, ``denoise_iterations`` (default 8),
``gpu_stage_table`` ({stage: bool}; absent = no stage on G), ``no_gpu`` (true: CPU pools only, same DAG), ``profile`` /
``model_path`` / ``est_cfg`` / ``policy_cfg`` (as montage), ``keep_artifacts``.
Verification: an all-CPU run must reproduce the sequential reference's final bytes exactly; a run with CUDA tasks is checked
per CUDA task (the CPU stage is re-run on that task's own input artifacts and compared with the tolerances of
``scripts/gpu_spike.py``). The final aggregate is not compared when stages ran on CUDA (its input differs by design).
``factory()`` reads constructor settings from the JSON file named by CAO_STUDY2_ADAPTER_CONFIG, if set.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from caosched.apps.artifacts import artifact_path, read_artifacts
from caosched.apps.cuda_stages import CUDA_STAGES, cuda_available
from caosched.apps.image_pipeline import run_reference
from caosched.apps.stages import STAGES, decode_arrays
from caosched.core.coordinator import Coordinator, RunTimeoutError, TaskTimeoutError, pin_coordinator_to_reserved_core
from caosched.core.event_log import EventLogger
from caosched.experiment.design import Condition, RunRecord
from caosched.experiment.gpu_adapter import GpuAdapter, _spike
from caosched.experiment.montage_adapter import build_policy
from caosched.study2.workload import GPU_POOL, build_batch, build_classes, build_iters, build_mixed


def build_study2_policy(cond: Condition, seed: int):
    """``build_policy`` of the stage 2-5 code, plus two EFT variants. ``kwargs['binding'] == 'late'``: ``LateEftScheduler`` (policies.py). End-to-end ablation: a condition with ``kwargs['e2e_terms']`` (a file
    written by ``scripts/study2_e2e_terms.py``) gets ``EFT_<spec>_e2e`` = kernel estimate + measured setup (task I/O) + measured IPC
    overhead per pool (``estimators/e2e.py``, unchanged). ``montage_adapter.build_policy`` never passes ``e2e_terms``."""
    kw = cond.kwargs
    if kw.get("binding") == "oracle":  # replay oracle (E5) on the unchanged EFT: a ceiling, never a real rule (protocol section 14)
        from caosched.estimators.e2e import EndToEndTerms
        from caosched.study2.policies import CachedOracle, EftNoContext, RankEftNoContext

        terms = EndToEndTerms.load(Path(kw["e2e_terms"])) if kw.get("e2e_terms") else None
        est = CachedOracle.from_rows(json.loads(Path(kw["oracle_rows"]).read_text(encoding="utf-8")))
        cls = RankEftNoContext if kw.get("rank") else EftNoContext
        return cls(est, "O_EFT_E5" + ("_rank" if kw.get("rank") else "") + ("_e2e" if terms else ""), e2e=terms)
    if kw.get("binding") in ("param_model_eft", "param_model_rank", "param_model_heft", "param_model_peft", "pred_rank_greedy",
                             "pred_rank_hold"):  # learned generic model (param_model.py) behind each candidate policy
        from caosched.schedulers.heft import HeftScheduler
        from caosched.schedulers.peft import PeftScheduler
        from caosched.study2.param_model import ParamModelEstimator
        from caosched.study2.policies import EftNoContext, PredictedRankGreedy, RankEftNoContext

        pm = ParamModelEstimator.load(Path(kw["param_model"]))
        b = kw["binding"]
        if b == "param_model_heft":
            return HeftScheduler(pm, "HEFT_param_model")
        if b == "param_model_peft":
            return PeftScheduler(pm, "PEFT_param_model")
        if b == "param_model_eft":
            return EftNoContext(pm, "EFT_param_model_noctx")
        if b == "param_model_rank":
            return RankEftNoContext(pm, "EFT_param_model_rank_noctx")
        return PredictedRankGreedy(pm, "PRED_RANK_GREEDY" if b == "pred_rank_greedy" else "PRED_RANK_HOLD",
                                   hold_min_s=None if b == "pred_rank_greedy" else float(kw.get("hold_min_s", 0.010)))
    if kw.get("binding") == "cost_first":  # hand-written product formula (model.py)
        from caosched.study2.model import CostFirstGreedy

        return CostFirstGreedy(None, kw.get("priority") or ["P", "E"], name="B4_cost_first")
    if kw.get("binding") == "param_first":  # informed non-predictive heuristic (model.py)
        from caosched.study2.model import ParamFirstGreedy

        return ParamFirstGreedy(None, kw.get("priority") or ["P", "E"], name="B4_param_first")
    if kw.get("binding") in ("iter_model", "iter_model_rank"):  # learned predictor that sees the iterations parameter
        from caosched.study2.model import IterModelEstimator
        from caosched.study2.policies import EftNoContext, RankEftNoContext

        iest = IterModelEstimator.load(Path(kw["iter_model"]), Path(kw["profile"]))
        if kw["binding"] == "iter_model_rank":
            return RankEftNoContext(iest, "EFT_iter_model_rank_noctx")
        return EftNoContext(iest, "EFT_iter_model_noctx")
    if kw.get("binding") == "largest_first":  # non-predictive size-ordered greedy (policies.py)
        from caosched.study2.policies import LargestFirstGreedy

        return LargestFirstGreedy(None, kw.get("priority") or ["P", "E"], name="B4_largest_first")
    late = kw.get("binding") == "late"
    if not kw.get("e2e_terms") and kw.get("binding") in (None, "early"):
        return build_policy(cond, seed)
    from caosched.estimators.e2e import EndToEndTerms
    from caosched.experiment.montage_adapter import estimator_spec
    from caosched.schedulers import eft_factories
    from caosched.study2.policies import EftNoContext, LateEftScheduler, RankEftNoContext

    if not cond.policy.startswith("EFT_"):
        raise ValueError(f"{cond.name}: e2e_terms / binding apply to EFT_* policies only, got {cond.policy!r}")
    if kw.get("binding") not in (None, "early", "early_noctx", "rank_noctx", "late"):
        raise ValueError(f"{cond.name}: binding must be 'early', 'early_noctx', 'rank_noctx' or 'late', got {kw['binding']!r}")
    e2e = bool(kw.get("e2e_terms"))
    extra: dict[str, Any] = ({"scheduler_cls": LateEftScheduler, "name_suffix": "_late"} if late
                             else {"scheduler_cls": EftNoContext, "name_suffix": "_noctx"} if kw.get("binding") == "early_noctx"
                             else {"scheduler_cls": RankEftNoContext, "name_suffix": "_rank_noctx"} if kw.get("binding") == "rank_noctx"
                             else {})
    (make,) = eft_factories([estimator_spec(cond.policy, cond.estimator) + ("@e2e" if e2e else "")], Path(kw["profile"]),
                            est_cfg=kw.get("est_cfg"), e2e_terms=EndToEndTerms.load(Path(kw["e2e_terms"])) if e2e else None,
                            **extra).values()
    return make()


class Study2Adapter(GpuAdapter):
    def __init__(self, *args, max_p_slots: int | None = None, **kw):
        """``max_p_slots``: how many P-core workers (None = one per physical P core; 2 = the scarce-fast-core configuration of
        stage 5). A different resource configuration is a different "machine" for the learned model: retrain it with
        ``scripts/study2_retrain.py``, no code change."""
        super().__init__(*args, **kw)
        self.max_p_slots = max_p_slots

    # Pools are the same for EVERY condition of a session (as in remote_adapter): the stage 5 GpuAdapter rebuilds the whole
    # worker pool whenever a condition switches between "with G" and "no_gpu", which leaves cold workers (imports, first CUDA
    # call) in the next, short run. Pilot 1 of study 2 showed bimodal makespans for that reason (protocol amendment A1).
    # A "no GPU" condition only makes G ineligible (build_dag), the idle CUDA worker stays in the pool.
    def _config(self, gpu: bool):
        if self.runtime_config is None and self.max_p_slots is not None:
            from caosched.core.runtime_config import RuntimeConfig
            self.runtime_config = RuntimeConfig.from_topology(max_p_slots=self.max_p_slots)
        return super()._config(cuda_available())

    def _get_pool(self, gpu: bool):
        return super()._get_pool(cuda_available())

    def build_dag(self, kw: dict, gpu_stages=()):
        if kw.get("classes"):  # two-factor batch: [[count, side, iterations], ...], chain order from kw["order_seed"]
            ckey: tuple = ("classes", tuple(map(tuple, kw["classes"])), int(kw.get("seed", 0)), int(kw.get("order_seed", 0)))
            return build_classes(kw["classes"], ckey[2], 2.0, gpu_stages, GPU_POOL, ckey[3]), ckey
        if kw.get("iters"):  # hidden-cost batch: {"small": [count, iterations], "big": [count, iterations]}, one image size kw["tile"]
            m = kw["iters"]
            ikey: tuple = ("iters", *m["small"], *m["big"], int(kw.get("tile", 512)), int(kw.get("seed", 0)), int(kw.get("order_seed", 0)))
            return build_iters(m["small"], m["big"], ikey[-3], ikey[-2], 2.0, gpu_stages, GPU_POOL, ikey[-1]), ikey
        if kw.get("mix"):  # heavy-tailed batch: {"small": [count, side], "big": [count, side]}, chain order from kw["order_seed"]
            m = kw["mix"]
            key: tuple = ("mix", *m["small"], *m["big"], int(kw.get("seed", 0)), int(kw.get("denoise_iterations", 8)),
                          int(kw.get("order_seed", 0)))
            return build_mixed(m["small"], m["big"], key[-3], 2.0, key[-2], gpu_stages, GPU_POOL, key[-1]), key
        key = (int(kw.get("k", 64)), int(kw.get("tile", 512)), int(kw.get("seed", 0)), int(kw.get("denoise_iterations", 8)))
        return build_batch(key[0], key[1], key[2], 2.0, key[3], gpu_stages, GPU_POOL), key

    def _build_policy(self, condition: Condition, kw: dict, seed: int):
        """Policy of one run; a subclass (``revival.adapter``) extends the set of bindings without touching this module."""
        return build_study2_policy(dataclasses.replace(condition, kwargs={k: v for k, v in kw.items() if k != "seed"}), seed)

    def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord:
        workdir, kw = Path(workdir), condition.kwargs
        if condition.instance is not None and kw.get("order_seeds"):  # instance name -> order of the chains (heavy-tailed batch)
            kw = {**kw, "order_seed": kw["order_seeds"][condition.instance]}
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
        policy = self._build_policy(condition, kw, seed)
        run_id, log_name = workdir.name, f"{workdir.name}.jsonl"
        meta = {"experiment_id": workdir.parent.parent.name, "workflow_instance": condition.instance,
                "condition": condition.name, "policy": condition.policy, "estimator": condition.estimator, "seed": seed}
        extra = {"n_tasks": len(dag), "policy": policy.name, "workload_key": [str(x) for x in key],
                 "denoise_iterations": int(kw.get("denoise_iterations", 8)),
                 "gpu_pool": gpu, "gpu_stages": sorted(on) if gpu else [],
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
                         init_s=summary.init_seconds, policy_setup_s=summary.policy_setup_seconds,  # amendment F1 (additive)
                         end_to_end_makespan_seconds=summary.end_to_end_makespan_seconds,
                         n_completed=summary.n_completed, tasks_per_pool=summary.tasks_per_pool,
                         task_placement={t.task_id: [t.assigned_pool, t.assigned_worker] for t in dag.tasks.values()},
                         cuda_tasks=sorted(t.task_id for t in dag.tasks.values() if kinds.get(t.assigned_pool) == "cuda"))
        if summary is not None and summary.makespan_seconds:
            frac = summary.scheduling_time_seconds / summary.makespan_seconds
            extra["scheduling_fraction"] = frac
            limit = float(kw.get("max_scheduling_fraction", 0.25))
            if status == "ok" and frac > limit:  # a run dominated by the policy's own computing measures the implementation, not the policy
                status = "failed"
                error = f"scheduling time {summary.scheduling_time_seconds:.3f}s is {frac:.0%} of the makespan (limit {limit:.0%})"
        rec = RunRecord(status=status, event_log=log_name if (workdir / log_name).is_file() else None, error=error,
                        input_hashes={"reference_aggregate": hashlib.sha256(ref["aggregate"]).hexdigest()}, extra=extra)
        if status == "ok":
            try:
                rec.output_ok, rec.output_hashes = self._verify(dag, art, ref, extra)
            except Exception as exc:  # noqa: BLE001 - keep the run, unverified
                rec.output_ok, rec.error = False, f"verify raised {type(exc).__name__}: {exc}"
        if not kw.get("keep_artifacts"):
            shutil.rmtree(art, ignore_errors=True)
        return rec

    def _verify(self, dag, art: Path, ref: dict, extra: dict) -> tuple[bool, dict]:
        final = artifact_path(art, "aggregate").read_bytes()
        digest, cuda = hashlib.sha256(final).hexdigest(), extra["cuda_tasks"]
        if not cuda:
            ok = digest == hashlib.sha256(ref["aggregate"]).hexdigest()
            extra["output_verdict"] = {"match": "exact" if ok else "MISMATCH", "sha256": digest}
            return ok, {"aggregate": digest}
        spike, checks = _spike(), {}
        for tid in cuda:  # re-run the CPU stage on the CUDA task's own input artifacts
            t = dag.tasks[tid]
            objs = STAGES[t.workload].decode(read_artifacts([artifact_path(art, d) for d in t.dependencies]))
            got = decode_arrays(read_artifacts([artifact_path(art, tid)]))[0]
            checks[tid] = spike.compare(t.workload, np.asarray(STAGES[t.workload].compute(objs, t.params)), got)
        extra["output_verdict"] = checks
        return all(c["equivalent"] for c in checks.values()), {"aggregate": digest}


def factory() -> Study2Adapter:
    path = os.environ.get("CAO_STUDY2_ADAPTER_CONFIG")
    return Study2Adapter(**(json.loads(Path(path).read_text(encoding="utf-8")) if path else {}))
