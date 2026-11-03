"""Final-study adapter: ``Study2Adapter`` plus the new bindings (``pred_rank_greedy_e2e``, ``heft_e2e``, ``heft_oracle``) and, for
static-plan policies, the planned-versus-actual record. Subclassed, not edited: every registered binding falls through to
``build_study2_policy`` unchanged.

Condition kwargs (on top of the Study 2 ones):
  ``binding``     pred_rank_greedy_e2e | heft_e2e | heft_oracle | any Study 2 binding (pred_rank_greedy, param_first, param_model_heft, ...)
  ``param_model`` learned model file (``study2/param_model.py``); ``e2e_terms`` file from ``scripts/study2_e2e_terms.py``
  ``oracle_rows`` JSON rows for ``CachedOracle`` (``scripts/final_oracle_rows.py``)
Extra recorded on every run (beyond the Study 2 fields): for a static plan ``static_plan`` = planned makespan, number of tasks whose
executed worker differs from the planned one (0 for a faithful static schedule), and the policy set-up time.
``factory()`` reads constructor settings from the JSON file named by CAO_FINAL_ADAPTER_CONFIG, if set.
"""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

from caosched.experiment.design import Condition, RunRecord
from caosched.study2.adapter import Study2Adapter, build_study2_policy

FINAL_BINDINGS = ("pred_rank_greedy_e2e", "heft_e2e", "heft_oracle")


def build_final_policy(cond: Condition, seed: int):
    kw = cond.kwargs
    b = kw.get("binding")
    if b not in FINAL_BINDINGS:
        return build_study2_policy(cond, seed)
    from caosched.estimators.e2e import EndToEndTerms
    from caosched.final.policies import HeftE2E, HeftOracleReference, PredictedRankGreedyE2E
    from caosched.study2.param_model import ParamModelEstimator
    from caosched.study2.policies import CachedOracle

    if b == "heft_oracle":
        est = CachedOracle.from_rows(json.loads(Path(kw["oracle_rows"]).read_text(encoding="utf-8")))
        return HeftOracleReference(est, "HEFT_ORACLE_REF")
    terms = EndToEndTerms.load(Path(kw["e2e_terms"]))
    pm = ParamModelEstimator.load(Path(kw["param_model"]))
    if b == "heft_e2e":
        return HeftE2E(pm, "HEFT_E2E", terms)
    return PredictedRankGreedyE2E(pm, "PRED_RANK_GREEDY_E2E", terms)


class FinalAdapter(Study2Adapter):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._policy = None

    def build_dag(self, kw: dict, gpu_stages=()):
        """Study 2 DAG; with ``gpu_region`` (a list of GPU-spike record files) the CUDA pool is then removed from every task whose
        (stage, side, parameters) has no PASS row in those records (``final.gpu_region``). Without it: stage-level eligibility, as registered."""
        dag, key = super().build_dag(kw, gpu_stages)
        paths = kw.get("gpu_region")
        if paths and gpu_stages:
            from caosched.final.gpu_region import GpuRegion

            region = GpuRegion.load(paths)
            region.narrow(dag)
            key = (*key, "region", region.signature)
        return dag, key

    def _build_policy(self, condition: Condition, kw: dict, seed: int):
        self._policy = build_final_policy(dataclasses.replace(condition, kwargs={k: v for k, v in kw.items() if k != "seed"}), seed)
        return self._policy

    def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord:
        self._policy = None
        rec = super().run_one(condition, workdir, seed)
        plan = getattr(self._policy, "plan", None)
        placement = rec.extra.get("task_placement")
        if plan is not None and placement:
            assigned = {t: w for t, w in plan.assign.items()}
            mismatch = sorted(t for t, (_, w) in placement.items() if assigned.get(t) not in (None, w))
            rec.extra["static_plan"] = {"planned_makespan_s": plan.makespan, "n_planned": len(assigned),
                                        "n_executed_elsewhere": len(mismatch), "executed_elsewhere": mismatch[:10],
                                        "policy_setup_s": rec.extra.get("policy_setup_s")}
        return rec


def factory() -> FinalAdapter:
    path = os.environ.get("CAO_FINAL_ADAPTER_CONFIG")
    return FinalAdapter(**(json.loads(Path(path).read_text(encoding="utf-8")) if path else {}))
