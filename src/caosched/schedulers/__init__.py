"""Scheduler policies (B0-B7, the EFT ladder incl. P, oracle O) and registries.

``policy_factories(cfg, profile_path)`` returns name -> zero-arg factory.
A *fresh* policy (and estimator) instance must be built for every run so
that no learned or cursor state leaks between replays of the same trace.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from caosched.core.scheduler_base import SchedulerPolicy
from caosched.estimators import MovingHistoryEstimator, ReplayOracleEstimator, StaticProfileEstimator, build_estimator
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.heft import HeftScheduler
from caosched.schedulers.peft import PeftScheduler
from caosched.schedulers.rank_eft import RankEftScheduler
from caosched.schedulers.simple import (
    CriticalityScheduler,
    GreedyEligibleScheduler,
    PoolOnlyScheduler,
    RoundRobinScheduler,
    ShortestQueueScheduler,
    StaticMappingScheduler,
)

ALL_POLICIES = (
    "B0_P_only", "B0_E_only", "B1_round_robin", "B2_static_mapping", "B3_shortest_queue",
    "B4_greedy_eligible", "B5_criticality", "B6_eft_static", "B7_eft_history",
)


def eft_policy_name(estimator_spec: str) -> str:
    """'E4+rc' -> 'EFT_E4_rc'; 'E4+rc@e2e' -> 'EFT_E4_rc_e2e'.
    EFT_E1 == B6, EFT_E3 == B7, EFT_E4 == P. '@e2e' marks the end-to-end ablation."""
    return "EFT_" + estimator_spec.replace("+", "_").replace("@", "_")


def eft_factories(specs: list[str], profile_path: Path, est_cfg: dict | None = None,
                  model_path: Path | None = None, e2e_terms=None,
                  transfer=None, allowed_pools: list[str] | None = None,
                  name_suffix: str = "", scheduler_cls: Callable[..., SchedulerPolicy] = EarliestFinishTimeScheduler) -> dict[str, Callable[[], SchedulerPolicy]]:
    """EFT with any online estimator spec ('E0'..'E4', 'E4f', optional '+rc',
    optional '@e2e' = end-to-end ablation, which requires ``e2e_terms``);
    a fresh estimator per call (no state crosses runs). ``transfer`` (Phase 5)
    is shared by all returned policies."""
    out: dict[str, Callable[[], SchedulerPolicy]] = {}
    for spec in specs:
        est_spec, _, model = spec.partition("@")
        if model not in ("", "e2e"):
            raise ValueError(f"unknown EFT model suffix in {spec!r}")
        if model == "e2e" and e2e_terms is None:
            raise ValueError(f"{spec!r} needs measured e2e terms")
        build_estimator(est_spec, profile_path, est_cfg, model_path)  # fail fast on a bad spec
        name = eft_policy_name(spec) + name_suffix

        def make(s=est_spec, n=name, m=model) -> SchedulerPolicy:  # defaults bind this iteration's values
            return scheduler_cls(build_estimator(s, profile_path, est_cfg, model_path), n,
                                 e2e=e2e_terms if m == "e2e" else None, transfer=transfer,
                                 allowed_pools=allowed_pools)
        out[name] = make
    return out


def rank_eft_factories(specs: list[str], profile_path: Path, **kw) -> dict[str, Callable[[], SchedulerPolicy]]:
    """The proposed instrument: EFT with upward-rank ready order ('EFT_E1_rc_rank');
    arguments as ``eft_factories`` (transfer model, recalibration via '+rc', ...)."""
    return eft_factories(specs, profile_path, name_suffix="_rank", scheduler_cls=RankEftScheduler, **kw)


def plan_factories(profile_path: Path, est_cfg: dict | None = None, comm=None) -> dict[str, Callable[[], SchedulerPolicy]]:
    """HEFT / PEFT static plan baselines on the E1 profile cost matrix. ``comm(parent, child)``: edge transfer seconds."""
    build_estimator("E1", profile_path, est_cfg)  # fail fast on a bad profile
    return {"HEFT_E1": lambda: HeftScheduler(build_estimator("E1", profile_path, est_cfg), "HEFT_E1", comm),
            "PEFT_E1": lambda: PeftScheduler(build_estimator("E1", profile_path, est_cfg), "PEFT_E1", comm)}


def oracle_factory(rows: list[dict]) -> Callable[[], SchedulerPolicy]:
    """O: EFT with the E5 replay oracle built from already-logged runs of the
    same traces (offline/replay reference only)."""
    def make() -> SchedulerPolicy:
        return EarliestFinishTimeScheduler(ReplayOracleEstimator.from_rows(rows), "O_eft_E5")
    return make


def policy_factories(cfg: dict, profile_path: Path | None) -> dict[str, Callable[[], SchedulerPolicy]]:
    """``cfg`` is the ``policies:`` section of the Phase 2 config."""
    cfg = cfg or {}

    def profile() -> StaticProfileEstimator:
        if profile_path is None:
            raise ValueError("EFT policies need a static profile (run scripts/profile_static.py)")
        return StaticProfileEstimator.from_file(profile_path)

    b4 = cfg.get("B4_greedy_eligible", {})
    window = cfg.get("B7_eft_history", {}).get("window", 8)
    return {
        "B0_P_only": lambda: PoolOnlyScheduler("P"),
        "B0_E_only": lambda: PoolOnlyScheduler("E"),
        "B1_round_robin": RoundRobinScheduler,
        "B2_static_mapping": lambda: StaticMappingScheduler(cfg["B2_static_mapping"]["mapping"]),
        "B3_shortest_queue": ShortestQueueScheduler,
        "B4_greedy_eligible": lambda: GreedyEligibleScheduler(b4.get("eligibility"), b4.get("priority")),
        "B5_criticality": CriticalityScheduler,
        "B6_eft_static": lambda: EarliestFinishTimeScheduler(profile(), "B6_eft_static"),
        "B7_eft_history": lambda: EarliestFinishTimeScheduler(
            MovingHistoryEstimator(profile(), window=window), "B7_eft_history"),
    }
