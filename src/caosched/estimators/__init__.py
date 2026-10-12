"""Execution-time estimator ladder E0-E5 (kernel-only time; see base.py).

``build_estimator(name, ...)`` constructs any rung by name so a scheduler
(EFT) can be paired with any estimator without code changes.
"""
from __future__ import annotations

from pathlib import Path

from caosched.estimators.analytic import AnalyticSizeEstimator
from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator, TaskSpec
from caosched.estimators.constant import ConstantProfileEstimator
from caosched.estimators.history import MovingHistoryEstimator
from caosched.estimators.e2e import EndToEndTerms
from caosched.estimators.learned import (
    BaseProfileMismatchError, InterferenceRidgeEstimator, InterferenceRidgeFastEstimator, latest_model_path,
)
from caosched.estimators.oracle import ReplayOracleEstimator
from caosched.estimators.profile import StaticProfileEstimator, latest_profile_path
from caosched.estimators.recalibrated import RecalibratedEstimator
from caosched.estimators.tabular import CatBoostEstimator, MlpEstimator, load_tabular

ONLINE_ESTIMATORS = ("E0", "E1", "E2", "E3", "E4", "CatBoost", "MLP")  # E5 is offline/replay only


def build_estimator(name: str, profile_path: Path, cfg: dict | None = None,
                    model_path: Path | None = None) -> ExecutionTimeEstimator:
    """``name`` is a rung ("E0".."E4"), optionally with "+rc" (online
    recalibration wrapper, settings from cfg["rc"]); E3 cannot be wrapped.

    ``profile_path`` is the session profile used by E0-E3. E4 / E4f do NOT
    use it: a learned model is bound to the profile recorded in its model
    file (``InterferenceRidgeEstimator.load``), so the model is never re-based
    onto the session profile (audit finding D2). The profile E4 actually uses
    is reported by ``describe()["base"]["source"]``."""
    cfg = cfg or {}
    if name.endswith("+rc"):
        base_name = name[:-3]
        if base_name == "E3":
            raise ValueError("E3 is already adaptive; '+rc' is not defined for it")
        rc = cfg.get("rc", {})
        return RecalibratedEstimator(build_estimator(base_name, profile_path, cfg, model_path),
                                     alpha=rc.get("alpha", 0.2), min_obs=rc.get("min_obs", 1),
                                     clamp=tuple(rc.get("clamp", (0.5, 3.0))))
    if name == "E0":
        return ConstantProfileEstimator.from_profile(profile_path)
    if name == "E1":
        return StaticProfileEstimator.from_file(profile_path)
    if name == "E2":
        c = cfg.get("E2", {})
        return AnalyticSizeEstimator.from_profile(profile_path, c.get("exponents"), c.get("fit_exponent", False))
    if name == "E3":
        return MovingHistoryEstimator(StaticProfileEstimator.from_file(profile_path), cfg.get("E3", {}).get("window", 8))
    if name == "E4":
        return InterferenceRidgeEstimator.load(model_path or latest_model_path())  # its own recorded profile
    if name == "E4f":  # same model as E4, cheaper inference (implementation ablation)
        return InterferenceRidgeFastEstimator.from_model(
            InterferenceRidgeEstimator.load(model_path or latest_model_path()))
    if name in ("CatBoost", "MLP"):  # Stage 3 correction models: bound to their own recorded profile, like E4
        if model_path is None:
            raise ValueError(f"{name} needs model_path (a file written by scripts/evaluate_models.py or .save())")
        return load_tabular(model_path)
    raise ValueError(f"Unknown or offline-only estimator {name!r} (E5 needs logged runs: ReplayOracleEstimator)")


__all__ = [
    "AnalyticSizeEstimator", "BaseProfileMismatchError", "CatBoostEstimator", "MlpEstimator", "load_tabular", "ConstantProfileEstimator", "EndToEndTerms", "EstimateContext", "ExecutionTimeEstimator",
    "InterferenceRidgeFastEstimator",
    "InterferenceRidgeEstimator", "MovingHistoryEstimator", "ONLINE_ESTIMATORS", "RecalibratedEstimator",
    "ReplayOracleEstimator",
    "StaticProfileEstimator", "TaskSpec", "build_estimator", "latest_model_path", "latest_profile_path",
]
