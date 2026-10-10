"""End-to-end EFT ablation, E4f fast-inference equivalence, EFT transfer hook."""
import json
import math
import random

import numpy as np
import pytest

from caosched.core.dag import build_independent_dag
from caosched.core.runtime_state import RuntimeState
from caosched.estimators import (
    EndToEndTerms, EstimateContext, InterferenceRidgeEstimator, InterferenceRidgeFastEstimator,
    StaticProfileEstimator, TaskSpec,
)
from caosched.estimators.learned import FEATURE_SETS, FEATURES
from caosched.schedulers import eft_factories
from caosched.schedulers.eft import EarliestFinishTimeScheduler


def _e1():
    return StaticProfileEstimator({("matmul", 64, p): v for p, v in (("P", 0.010), ("E", 0.020), ("R", 0.020))})


def _terms():
    return EndToEndTerms({("matmul", 64, "P"): 0.002, ("matmul", 64, "E"): 0.004, ("matmul", 64, "R"): 0.004},
                         {"P": 0.001, "E": 0.001, "R": 0.001})


def test_e2e_terms_roundtrip_and_strictness(tmp_path):
    t = _terms()
    p = tmp_path / "e2e.json"
    t.save(p, {"note": "test"})
    again = EndToEndTerms.load(p)
    assert again.extra(TaskSpec("x", "matmul", 64), "E") == pytest.approx(0.005)
    with pytest.raises(KeyError):
        again.setup("matmul", 999, "E")
    with pytest.raises(KeyError):
        again.overhead("X")


def test_eft_e2e_adds_setup_and_overhead_and_is_labelled():
    dag = build_independent_dag(2, size=64)
    s = RuntimeState(dag, {"P0": "P", "E0": "E"})
    kern = EarliestFinishTimeScheduler(_e1(), "k")
    e2e = EarliestFinishTimeScheduler(_e1(), "e", e2e=_terms())
    for p in (kern, e2e):
        p.on_run_start(dag, s)
        p.select_worker(dag.tasks["t0"], s)
    ck, ce = kern.last_decision["candidates"]["E0"], e2e.last_decision["candidates"]["E0"]
    assert kern.last_decision["model"] == "kernel" and e2e.last_decision["model"] == "e2e"
    assert ck["finish"] == pytest.approx(0.020) and "setup" not in ck
    assert ce["finish"] == pytest.approx(0.020 + 0.004 + 0.001) and ce["exec"] == ck["exec"]  # kernel term unchanged


def test_eft_e2e_wait_of_busy_worker_includes_setup_and_overhead():
    dag = build_independent_dag(2, size=64)
    s = RuntimeState(dag, {"P0": "P"})
    p = EarliestFinishTimeScheduler(_e1(), "e", e2e=_terms())
    p.on_run_start(dag, s)
    s.mark_submitted("P0", "t0", s.now())
    p.select_worker(dag.tasks["t1"], s)
    assert p.last_decision["candidates"]["P0"]["wait"] == pytest.approx(0.010 + 0.002 + 0.001, abs=0.002)


def test_transfer_hook_applies_only_where_estimated():
    class Link:
        def estimate(self, task, pool):
            return 0.050 if pool == "R" else 0.0

        def describe(self):
            return {"name": "test-link"}

    dag = build_independent_dag(1, size=64)
    s = RuntimeState(dag, {"P0": "P", "R0": "R"})
    p = EarliestFinishTimeScheduler(_e1(), "t", transfer=Link())
    p.on_run_start(dag, s)
    assert p.select_worker(dag.tasks["t0"], s) == "P0"
    c = p.last_decision["candidates"]
    assert c["R0"]["transfer"] == 0.050 and c["R0"]["finish"] == pytest.approx(0.070) and c["P0"]["transfer"] == 0.0
    assert p.describe()["transfer"] == {"name": "test-link"}


def test_registry_e2e_suffix(tmp_path):
    prof = tmp_path / "x_profile.json"
    prof.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "source_csv": "none.csv",
                                "entries": [{"workload": "matmul", "size": 64, "pool": p, "median_s": 0.01} for p in "PE"]}))
    f = eft_factories(["E1", "E1+rc@e2e"], prof, e2e_terms=_terms())
    assert list(f) == ["EFT_E1", "EFT_E1_rc_e2e"]
    assert f["EFT_E1"]().e2e is None and f["EFT_E1_rc_e2e"]().e2e is not None
    with pytest.raises(ValueError, match="e2e terms"):
        eft_factories(["E1@e2e"], prof)
    with pytest.raises(ValueError, match="suffix"):
        eft_factories(["E1@bogus"], prof, e2e_terms=_terms())


@pytest.mark.parametrize("fset", ["occupancy", "occupancy+history"])
def test_e4f_matches_e4_exactly(fset):
    rng = np.random.default_rng(3)
    feats = FEATURE_SETS[fset]
    weights = {("matmul", p): rng.normal(0, 0.1, len(feats)) for p in ("P", "E")}
    weights[("matmul", "E")][0] = 3.0  # force the clamp on some inputs
    e4 = InterferenceRidgeEstimator(_e1(), weights, {"impute": {"target_busy_frac": 0.37}}, feats)
    fast = InterferenceRidgeFastEstimator.from_model(e4)
    r = random.Random(0)
    t = TaskSpec("t", "matmul", 64)
    for _ in range(300):
        wl = [r.choice(["matmul", "compression", "image_filter"]) for _ in range(r.randint(0, 8))]
        frac = r.choice([None, r.random()])
        ctx = r.choice([None, EstimateContext.build(r.randint(0, 2), r.randint(0, 7), wl, frac)])
        for pool in ("P", "E", "R"):  # R has no weights -> both fall back to E1
            assert fast.estimate(t, pool, ctx) == pytest.approx(e4.estimate(t, pool, ctx), rel=1e-12)
    assert set(FEATURES) >= set(feats)
    assert not math.isnan(fast.estimate(t, "E"))
