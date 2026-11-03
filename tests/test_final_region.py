"""Verified-GPU-region eligibility (improvement D) and the final-study analysis switches (primary metric, condition filter)."""
import json

import pytest

from _exp_helpers import ENV, make_design
from caosched.analysis import stats_paired
from caosched.analysis.stats_paired import analyze
from caosched.experiment.runner import run_session
from caosched.experiment.stub import StubAdapter
from caosched.final.gpu_region import GpuRegion
from caosched.study2.workload import build_iters


def _row(stage, side, params, verdict):
    return {"stage": stage, "side": side, "params": json.dumps(params), "verdict": verdict}


def _record(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text(json.dumps({"env": {}, "rows": rows}))
    return p


def test_region_keeps_cuda_only_for_pass_rows(tmp_path):
    rec = _record(tmp_path, "r.json", [
        _row("img_edges", 64, {}, "PASS"),
        _row("img_denoise", 64, {"radius": 2.0, "iterations": 120}, "PASS"),
        _row("img_denoise", 64, {"radius": 2.0, "iterations": 2}, "DROPPED"),
        _row("img_features", 128, {}, "PASS")])                     # a different tile: must not count for side 64
    region = GpuRegion.load([rec])
    dag = build_iters([3, 2], [1, 120], side=64, gpu_stages={"img_denoise", "img_edges", "img_features"})
    assert sum("G" in t.eligible_pools for t in dag.tasks.values()) == 4 * 3          # denoise, edges, features of 4 chains
    lost = region.narrow(dag)
    for t in dag.tasks.values():
        want = (t.workload == "img_edges") or (t.workload == "img_denoise" and t.params["iterations"] == 120)
        assert ("G" in t.eligible_pools) == want, t.task_id
        assert {"P", "E"} <= set(t.eligible_pools)
    assert lost == 3 + 4 and "G" not in dag.tasks["features_0"].eligible_pools      # 3 light denoise + 4 features lose the CUDA pool


def test_a_dropped_row_in_any_record_wins_and_unknown_cases_are_not_eligible(tmp_path):
    a = _record(tmp_path, "a.json", [_row("img_edges", 64, {}, "PASS"), _row("img_features", 64, {}, "PASS")])
    b = _record(tmp_path, "b.json", [_row("img_features", 64, {}, "DROPPED")])
    region = GpuRegion.load([a, b])
    assert region.eligible("img_edges", 64, {}) and not region.eligible("img_features", 64, {})
    assert not region.eligible("img_edges", 65, {}) and not region.eligible("img_source", 64, {"width": 64})
    assert region.describe()["n_pass_rows"] == 1 and len(region.signature) == 16


def test_the_recorded_spike_gives_the_expected_region_at_512():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "data/results"
    orig = root / "stage1_20261011/gpu/gpu_spike.json"
    if not orig.is_file():
        pytest.skip("recorded spike not present")
    region = GpuRegion.load([orig])
    assert region.eligible("img_edges", 512, {}) and region.eligible("img_features", 512, {})
    assert region.eligible("img_denoise", 512, {"radius": 2.0, "iterations": 8})
    assert not region.eligible("img_denoise", 512, {"radius": 2.0, "iterations": 2})     # never recorded: not eligible
    assert not region.eligible("img_denoise", 512, {"radius": 2.0, "iterations": 1})     # recorded and DROPPED
    assert not region.eligible("img_edges", 128, {})                                      # DROPPED at 128 px


def _session(tmp_path, sid, effects, conds=("A", "B", "C")):
    d = make_design(tmp_path, n_blocks=12, warmup=1, name=f"{sid}.json", conds=conds)
    run_session(d, tmp_path / "out", StubAdapter(base={"i1": 8.0, "i2": 10.0, "i3": 14.0}, effects=effects, noise=0.03),
                session_id=sid, free_fn=lambda: 16.0, env=ENV)
    return tmp_path / "out" / sid


def test_only_conditions_restricts_the_analysis(tmp_path):
    sd = _session(tmp_path, "S", {"B": 0.9, "C": 1.2})
    res = analyze([sd], seed=1, only_conditions=["A", "B"])
    assert {e["cond"] for e in res["tables"]["effects"]} == {"B"} and res["meta"]["only_conditions"] == ["A", "B"]
    assert {r["condition"] for r in res["tables"]["summary"]} == {"A", "B"}
    assert {e["cond"] for e in analyze([sd], seed=1)["tables"]["effects"]} == {"B", "C"}      # default unchanged


def test_primary_metric_switch_uses_the_end_to_end_makespan(tmp_path, monkeypatch):
    sd = _session(tmp_path, "S", {"B": 0.9}, conds=("A", "B"))
    orig = stats_paired.run_metrics

    def with_e2e(events):                 # every run pays a fixed 5 s of set-up that the old convention does not see
        m = orig(events)
        m["makespan_e2e_s"] = None if m["makespan_s"] is None else m["makespan_s"] + 5.0
        return m

    monkeypatch.setattr(stats_paired, "run_metrics", with_e2e)
    old = analyze([sd], seed=1)
    new = analyze([sd], seed=1, primary_metric="makespan_e2e_s")
    e_old = next(e for e in old["tables"]["effects"] if e["metric"] == "makespan_s" and e["variant"] == "primary")
    e_new = next(e for e in new["tables"]["effects"] if e["metric"] == "makespan_e2e_s" and e["variant"] == "primary")
    assert e_new["tier"] == "confirmatory" and new["meta"]["primary_metric"] == "makespan_e2e_s" and "primary_metric" not in old["meta"]
    assert e_new["effect_pct"] > e_old["effect_pct"]          # a fixed set-up cost counted: B's relative advantage shrinks (less negative)
    with pytest.raises(ValueError):
        analyze([sd], primary_metric="bogus")
