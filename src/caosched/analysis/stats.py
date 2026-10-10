"""Paired-block effect estimates with bootstrap confidence intervals (Phase 6B).

Design assumed: blocks (repeat x trace) in which every condition ran once,
in shuffled order, close together in time. A condition's effect on a
positive metric (makespan, response time, throughput) is the mean over blocks
of log(metric_condition / metric_reference) in the same block -- so drift
shared by the block cancels -- reported as a percentage exp(x) - 1.

CIs: percentile bootstrap over blocks, resampling *within each trace
stratum* (keeps the trace mix fixed), seeded and reproducible. No normality
assumption (Phase 4/5 makespans were heavy-tailed).
"""
from __future__ import annotations

import math

import numpy as np


def bootstrap_mean_ci(values, strata=None, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """(mean, lo, hi) of ``values``; resampling within ``strata`` labels if given."""
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return None
    rng = np.random.default_rng(seed)
    if strata is None:
        idx = rng.integers(0, v.size, size=(n_boot, v.size))
        boots = v[idx].mean(axis=1)
    else:
        s = np.asarray(strata)
        groups = [np.flatnonzero(s == g) for g in dict.fromkeys(s.tolist())]
        total = np.zeros(n_boot)
        for g in groups:
            pick = rng.integers(0, g.size, size=(n_boot, g.size))
            total += v[g][pick].sum(axis=1)
        boots = total / v.size
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return float(v.mean()), float(lo), float(hi)


def paired_log_ratios(blocks: dict, cond: str, ref: str, metric: str):
    """blocks: block_key -> {condition: {metric: value}}. Returns (ratios, strata)
    for blocks where both ran and both values are positive; stratum = block_key[1]
    when keys are (repeat, trace) tuples."""
    out, strata = [], []
    for key, b in blocks.items():
        a, r = b.get(cond, {}).get(metric), b.get(ref, {}).get(metric)
        if a and r and a > 0 and r > 0:
            out.append(math.log(a / r))
            strata.append(key[1] if isinstance(key, tuple) else 0)
    return out, strata


def paired_effect(blocks: dict, cond: str, ref: str, metric: str, seed: int = 0) -> dict | None:
    """Percentage effect of ``cond`` vs ``ref`` with 95% CI (bootstrap over blocks)."""
    ratios, strata = paired_log_ratios(blocks, cond, ref, metric)
    if len(ratios) < 3:
        return None
    m, lo, hi = bootstrap_mean_ci(ratios, strata, seed=seed)
    return {"cond": cond, "ref": ref, "metric": metric, "n_blocks": len(ratios),
            "effect_pct": (math.exp(m) - 1) * 100, "ci_lo_pct": (math.exp(lo) - 1) * 100,
            "ci_hi_pct": (math.exp(hi) - 1) * 100, "sd_log": float(np.std(ratios, ddof=1)),
            "ci_excludes_zero": (lo > 0) or (hi < 0)}


def mean_ci(values, strata=None, seed: int = 0) -> dict | None:
    r = bootstrap_mean_ci(values, strata, seed=seed)
    if r is None:
        return None
    return {"n": len(values), "mean": r[0], "ci_lo": r[1], "ci_hi": r[2]}


def min_detectable_effect_pct(sd_log: float, n_blocks: int) -> float:
    """95% CI half-width (in %) implied by a paired log-ratio SD and block count."""
    return (math.exp(1.96 * sd_log / math.sqrt(n_blocks)) - 1) * 100
