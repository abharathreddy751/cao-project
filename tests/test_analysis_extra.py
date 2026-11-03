"""Pure functions of scripts/drift_check.py, learning_curve.py, regret_table.py on small synthetic rows."""
import importlib.util
from pathlib import Path

import pytest


def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


drift, curve, regret = _load("drift_check"), _load("learning_curve"), _load("regret_table")


def test_run_subset_whole_runs_stratified_and_seeded():
    rows = [{"instance": i, "source_log": f"{i}/run{k}", "x": j} for i in "ab" for k in range(10) for j in range(3)]
    s = curve.run_subset(rows, 0.4, 0)
    for i in "ab":  # 4 of 10 runs per instance, every kept run complete (3 rows)
        logs = {r["source_log"] for r in s if r["instance"] == i}
        assert len(logs) == 4 and len([r for r in s if r["instance"] == i]) == 12
    assert s == curve.run_subset(rows, 0.4, 0) and s != curve.run_subset(rows, 0.4, 1)
    assert len({r["source_log"] for r in curve.run_subset(rows, 0.01, 0)}) == 2  # at least one run per instance
    assert len(curve.run_subset(rows, 1.0, 3)) == len(rows)


def test_still_falling_rule():
    assert curve.still_falling(2.0, 0.1, 1.5) == "falling"
    assert curve.still_falling(2.0, 0.1, 1.95).startswith("flat")
    assert curve.still_falling(2.0, 0.1, 2.5) == "rising"


def test_drift_early_late_split_orders_runs_within_session():
    rows = [{"source_log": f"r{i}", "session_id": "s", "order_index": "", "timestamp_epoch": str(100 - i)} for i in range(4)]
    assert drift.early_late(rows, {"r0", "r1", "r2", "r3"}) == {"r3": "early", "r2": "early", "r1": "late", "r0": "late"}
    preds = {"M": [{"source_log": f"r{i}", "workload": "mProject", "kernel_s": 10.0, "predicted_s": 10.0 + (i < 2) * 5.0}
                   for i in range(4)]}
    t = {(x["half"], x["subset"]): x for x in drift.summarize(rows, preds)}
    assert t[("early", "all")]["mae_s"] == 0.0 and t[("late", "all")]["mae_s"] == 5.0 and t[("late", "mProject")]["bias_s"] == 5.0


def _dec(run, pol, task, pool, regret, block=0, wl="mProject", optimal=None, pred=1.0):
    return {"run_id": run, "policy": pol, "task_id": task, "workload": wl, "block": block, "chosen_pool": pool,
            "chosen_worker": pool + "0", "regret_s": regret, "optimal": regret == 0 if optimal is None else optimal,
            "n_candidates": 3, "n_workers": 4, "pred_finish": pred}


def test_regret_summary_and_pool_differences():
    rows = [_dec("r1", "A", "t1", "P", 0.0), _dec("r1", "A", "t2", "P", 2.0), _dec("r1", "A", "t3", "P", 4.0, wl="mAdd"),
            _dec("r2", "A", "t1", "P", 0.0, pred=None), _dec("r3", "B", "t1", "E", 0.0), _dec("r3", "B", "t2", "P", 1.0)]
    s = {x["policy"]: x for x in regret.summarize(rows)}
    a = s["A"]
    assert (a["n_runs"], a["n_decisions"], a["total_regret_s"]) == (2, 4, 6.0) and a["mean_regret_s"] == pytest.approx(1.5)
    assert a["share_positive_regret"] == 0.5 and a["candidate_costs_logged_share"] == 0.75
    assert a["n_mProject"] == 3 and a["mProject_mean_regret_s"] == pytest.approx(2 / 3)
    d = regret.pool_differences(rows, "A", "B")  # t1 differs (P vs E); t2 same pool; t3 is not mProject
    assert len(d) == 1 and d[0]["task_id"] == "t1" and d[0]["A_chosen_pool"] == "P" and d[0]["B_chosen_pool"] == "E"
