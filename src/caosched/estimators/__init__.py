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
from caosched.estimators.learned import InterferenceRidgeEstimator, InterferenceRidgeFastEstimator, latest_model_path
from caosched.estimators.oracle import ReplayOracleEstimator
from caosched.estimators.profile import StaticProfileEstimator, latest_profile_path
from caosched.estimators.recalibrated import RecalibratedEstimator

ONLINE_ESTIMATORS = ("E0", "E1", "E2", "E3", "E4")  # E5 is offline/replay only


def build_estimator(name: str, profile_path: Path, cfg: dict | None = None,
                    model_path: Path | None = None) -> ExecutionTimeEstimator:
    """``name`` is a rung ("E0".."E4"), optionally with "+rc" (online
    recalibration wrapper, settings from cfg["rc"]); E3 cannot be wrapped."""
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
        return InterferenceRidgeEstimator.load(model_path or latest_model_path(),
                                               StaticProfileEstimator.from_file(profile_path))
    if name == "E4f":  # same model as E4, cheaper inference (implementation ablation)
        return InterferenceRidgeFastEstimator.from_model(build_estimator("E4", profile_path, cfg, model_path))
    raise ValueError(f"Unknown or offline-only estimator {name!r} (E5 needs logged runs: ReplayOracleEstimator)")


__all__ = [
    "AnalyticSizeEstimator", "ConstantProfileEstimator", "EndToEndTerms", "EstimateContext", "ExecutionTimeEstimator",
    "InterferenceRidgeFastEstimator",
    "InterferenceRidgeEstimator", "MovingHistoryEstimator", "ONLINE_ESTIMATORS", "RecalibratedEstimator",
    "ReplayOracleEstimator",
    "StaticProfileEstimator", "TaskSpec", "build_estimator", "latest_model_path", "latest_profile_path",
]
