"""Pre-execution workload features: pure functions on a hand-built DAG and a constant-cost model."""
import importlib.util
import json
from pathlib import Path

import pytest

from caosched.study2.param_model import ParamModelEstimator
from caosched.study2.workload import build_iters

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("final_workload_features", ROOT / "scripts" / "final_workload_features.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _model():
    # denoise cost = 1 ms per iteration on P (coef on 'iterations'), every other stage 2 ms
    g = {"img_denoise|P": {"features": ["iterations"], "coef": [0.0, 0.001], "n": 3, "mae_s": 0.0}}
    for s in ("img_source", "img_edges", "img_features"):
        g[f"{s}|P"] = {"features": [], "coef": [0.002], "n": 3, "mae_s": 0.0}
    return ParamModelEstimator(g)


def test_chain_costs_and_features_for_a_hidden_cost_batch():
    dag = build_iters([6, 2], [2, 100], side=64, order_seed=3)
    costs = mod.chain_costs(dag, _model())
    assert sorted(costs) == pytest.approx([0.006 + 0.002] * 6 + [0.006 + 0.100] * 2)   # source+edges+features = 6 ms; denoise = iterations ms
    f = mod.features(costs, workers=4)
    assert f["n_chains"] == 8 and f["n_heavy"] == 2 and f["max_over_median"] == pytest.approx(0.106 / 0.008)
    total = 6 * 0.008 + 2 * 0.106
    assert f["heavy_work_share"] == pytest.approx(0.212 / total) and f["tail_ratio"] == pytest.approx(0.106 / (total / 4))
    assert f["cv_chain_cost"] > 1.0


def test_uniform_batch_has_no_spread():
    dag = build_iters([8, 8], [0, 8], side=64)
    f = mod.features(mod.chain_costs(dag, _model()), workers=4)
    assert f["cv_chain_cost"] == pytest.approx(0.0) and f["n_heavy"] == 0 and f["max_over_median"] == pytest.approx(1.0)
