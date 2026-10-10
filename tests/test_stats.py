"""Phase 6B statistics and runtime additions (decision time, set_link, allowed_pools)."""
import json
import math

import numpy as np
import pytest

from caosched.analysis.stats import bootstrap_mean_ci, min_detectable_effect_pct, paired_effect, paired_log_ratios


def test_bootstrap_ci_covers_mean_and_is_reproducible():
    v = np.random.default_rng(1).normal(0.1, 0.2, 200)
    a = bootstrap_mean_ci(v, seed=3)
    assert a == bootstrap_mean_ci(v, seed=3)
    m, lo, hi = a
    assert lo < m < hi and lo < 0.1 < hi and (hi - lo) == pytest.approx(2 * 1.96 * 0.2 / math.sqrt(200), rel=0.25)


def test_stratified_bootstrap_keeps_strata_sizes():
    v = [0.0] * 50 + [1.0] * 50
    s = ["a"] * 50 + ["b"] * 50
    m, lo, hi = bootstrap_mean_ci(v, s, n_boot=2000)
    assert m == lo == hi == 0.5  # each stratum is constant -> no resampling variance


def test_paired_effect_recovers_known_ratio_and_cancels_block_drift():
    rng = np.random.default_rng(0)
    blocks = {}
    for rep in range(40):
        for trace in ("x", "y", "z"):
            drift = math.exp(rng.normal(0, 0.5))           # large shared block drift
            ref = 1.0 * drift * math.exp(rng.normal(0, 0.03))
            new = 0.90 * drift * math.exp(rng.normal(0, 0.03))
            blocks[(rep, trace)] = {"B4": {"makespan_s": ref}, "EFT": {"makespan_s": new}}
    e = paired_effect(blocks, "EFT", "B4", "makespan_s")
    assert e["n_blocks"] == 120 and e["effect_pct"] == pytest.approx(-10, abs=1.0)
    assert e["ci_hi_pct"] < 0 and e["ci_excludes_zero"]
    r, s = paired_log_ratios(blocks, "EFT", "B4", "makespan_s")
    assert len(r) == 120 and set(s) == {"x", "y", "z"}


def test_paired_effect_needs_blocks_and_skips_missing():
    blocks = {(0, "x"): {"B4": {"m": 1.0}}, (1, "x"): {"B4": {"m": 1.0}, "A": {"m": 0.0}}}
    assert paired_effect(blocks, "A", "B4", "m") is None


def test_min_detectable_effect():
    assert min_detectable_effect_pct(0.29, 120) == pytest.approx((math.exp(1.96 * 0.29 / math.sqrt(120)) - 1) * 100)
    assert min_detectable_effect_pct(0.29, 120) < 6.0


def test_decision_time_and_scheduling_time_are_logged(tmp_path):
    from caosched.core.coordinator import Coordinator
    from caosched.core.dag import build_independent_dag
    from caosched.core.event_log import EventLogger, read_events
    from caosched.core.scheduler_base import FirstIdleScheduler
    from caosched.core.worker_pool import WorkerPool

    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False) as pool:
        with EventLogger("dt", output_dir=tmp_path) as log:
            s = Coordinator(build_independent_dag(3, size=16), pool, FirstIdleScheduler(), log).run(run_timeout=30)
    ev = read_events(log.path)
    dts = [e["decision_time_s"] for e in ev if e["event"] == "task_dispatched"]
    assert len(dts) == 3 and all(d >= 0 for d in dts)
    assert s.scheduling_time_seconds >= sum(dts)
    start = ev[0]
    assert start["software"]["version"].startswith("0.1.0+") and len(start["software"]["src_sha256"]) == 64
    assert start["memory_available_bytes"] > 0


def test_set_link_switches_shim_between_runs():
    from caosched.core.task import TaskMessage
    from caosched.core.worker_pool import RemoteSlot, WorkerPool, WorkerPoolError
    from caosched.remote import LinkConfig

    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False,
                    remote_slots=[RemoteSlot(LinkConfig("fast"), node_core=1)]) as pool:
        pool.submit("R0", TaskMessage("a", "matmul", 16, 0))
        fast = pool.poll_result(30).transfer_s
        pool.set_link("R0", LinkConfig("slow", latency_s=0.03))
        pool.submit("R0", TaskMessage("b", "matmul", 16, 0))
        slow = pool.poll_result(30).transfer_s
        assert slow >= 0.06 > fast
        with pytest.raises(WorkerPoolError):
            pool.set_link("E0", LinkConfig("x"))


def test_eft_allowed_pools_restricts_candidates():
    from caosched.core.dag import build_independent_dag
    from caosched.core.runtime_state import RuntimeState
    from caosched.estimators import StaticProfileEstimator
    from caosched.schedulers.eft import EarliestFinishTimeScheduler

    est = StaticProfileEstimator({("matmul", 64, p): v for p, v in (("P", 0.01), ("E", 0.02))})  # no R entry
    dag = build_independent_dag(1, size=64)
    s = RuntimeState(dag, {"P0": "P", "E0": "E", "R0": "R"})
    pol = EarliestFinishTimeScheduler(est, "local_only", allowed_pools=["P", "E"])
    pol.on_run_start(dag, s)          # would raise KeyError for R if R were considered
    assert pol.select_worker(dag.tasks["t0"], s) == "P0"
    assert set(pol.last_decision["candidates"]) == {"P0", "E0"}
    assert json.loads(json.dumps(pol.describe()))["allowed_pools"] == ["P", "E"]
