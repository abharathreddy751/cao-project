import csv
import json

import pytest

from _exp_helpers import ENV, make_design
from caosched.analysis.stats_paired import PoolingError, analyze, write_tables
from caosched.experiment.manifest import build_manifest
from caosched.experiment.runner import run_session
from caosched.experiment.stub import StubAdapter


def _session(tmp_path, sid, effects, env=ENV, **kw):
    d = make_design(tmp_path, n_blocks=kw.pop("n_blocks", 30), warmup=1, name=f"{sid}.json", **kw)
    run_session(d, tmp_path / "out", StubAdapter(base={"i1": 8.0, "i2": 10.0, "i3": 14.0}, effects=effects, noise=0.03),
                session_id=sid, free_fn=lambda: 16.0, env=env)
    return tmp_path / "out" / sid


def _eff(res, cond="B", metric="makespan_s", variant="primary"):
    return next(e for e in res["tables"]["effects"] if e["cond"] == cond and e["metric"] == metric and e["variant"] == variant)


def test_known_ten_percent_speedup_recovered(tmp_path):
    res = analyze([_session(tmp_path, "S", {"B": 0.9})], seed=1)
    e = _eff(res)
    assert e["n_blocks"] == 29  # warm-up block excluded
    assert -13 < e["effect_pct"] < -7 and e["ci_lo_pct"] < -10 < e["ci_hi_pct"] and e["ci_excludes_zero"]
    assert e["dz"] < 0
    from caosched.analysis.stats import ci_halfwidth_pct, min_detectable_effect_pct
    assert e["mde_pct_80power"] == pytest.approx(min_detectable_effect_pct(e["sd_log"], e["n_blocks"]))
    assert e["ci_halfwidth_pct"] == pytest.approx(ci_halfwidth_pct(e["sd_log"], e["n_blocks"]))
    assert e["mde_pct_80power"] > e["ci_halfwidth_pct"] > 0   # 2.8 sd/sqrt(n) vs 1.96 sd/sqrt(n) on the log scale
    assert e["tier"] == "confirmatory" and 0 < e["p_perm"] <= e["p_holm"] <= 1 and e["significant_holm_05"]
    assert all("p_holm" not in x and x["tier"] == "exploratory" for x in res["tables"]["effects"]
               if (x["variant"], x["metric"]) != ("primary", "makespan_s"))
    summ = res["tables"]["summary"]  # absolute seconds per instance, pooled statement on the log scale only
    assert {r["instance"] for r in summ if r["scope"] == "per_instance" and r["condition"] == "A"} == {"i1", "i2", "i3"}
    assert all("mean_s" in r and "geo_mean_s" not in r for r in summ if r["scope"] == "per_instance")
    assert all("geo_mean_s" in r and "mean_s" not in r for r in summ if r["scope"] == "pooled_log_scale")
    assert res["meta"]["evidence_label"] == "plan"  # stub forces 'plan'


def test_null_case_interval_includes_zero(tmp_path):
    e = _eff(analyze([_session(tmp_path, "S", {})], seed=1))
    assert e["ci_lo_pct"] < 0 < e["ci_hi_pct"] and not e["ci_excludes_zero"]


def test_exclusions_sensitivity_and_crosscheck(tmp_path):
    sd = _session(tmp_path, "S", {"B": 0.9}, n_blocks=12)
    res = analyze([sd])
    # warm-up block (2 runs) is the only exclusion with a healthy stub
    assert [r["reason"] for r in res["tables"]["exclusions"]] == ["warm-up block (design rule)"] * 2
    assert _eff(res, variant="sensitivity_all_runs")["n_blocks"] == 12
    assert res["tables"]["crosscheck"]  # present: either scipy results or a 'skipped' note
    assert res["tables"]["runs"][0]["transfer_total_s"] == "not measured"


def test_failed_and_unverified_runs_flagged_not_dropped(tmp_path):
    d = make_design(tmp_path, n_blocks=8, warmup=0, instances=("i1",))
    run_session(d, tmp_path / "out", StubAdapter(fail={"B"}), session_id="F", free_fn=lambda: 9, env=ENV)
    d2 = make_design(tmp_path, n_blocks=8, warmup=0, instances=("i1",), name="e.json")
    run_session(d2, tmp_path / "out", StubAdapter(bad_output={"B"}), session_id="G", free_fn=lambda: 9, env=ENV)
    f = analyze([tmp_path / "out" / "F"])
    assert {r["reason"][:10] for r in f["tables"]["exclusions"]} == {"run failed"} and len(f["tables"]["exclusions"]) == 8
    assert not [e for e in f["tables"]["effects"] if e["variant"] == "primary" and "effect_pct" in e]
    g = analyze([tmp_path / "out" / "G"])
    assert len(g["tables"]["exclusions"]) == 8 and "verification failed" in g["tables"]["exclusions"][0]["reason"]
    assert _eff(g, variant="sensitivity_all_runs")["n_blocks"] == 8  # sensitivity includes the excluded runs


def test_refuses_to_pool_across_environments_and_labels(tmp_path):
    a = _session(tmp_path, "A", {}, n_blocks=4)
    b = _session(tmp_path, "B", {}, env={**ENV, "machine_id": "M2"}, n_blocks=4)
    with pytest.raises(PoolingError, match=r"machine_id: \['M1', 'M2'\]"):
        analyze([a, b])
    c = _session(tmp_path, "C", {}, env={**ENV, "environment_hash": "E2"}, n_blocks=4)
    with pytest.raises(PoolingError, match="environment_hash"):
        analyze([a, c])
    d = _session(tmp_path, "D", {}, n_blocks=4)  # same machine id and environment hash as A ...
    p = next(d.glob("runs/*/run_manifest.json"))
    m = json.loads(p.read_text())
    m["evidence_label"] = "real"                 # ... but one run carries a forged label (A's runs are 'plan')
    p.write_text(json.dumps(m))
    with pytest.raises(PoolingError, match="evidence_label") as ei:
        analyze([a, d])
    assert "['plan', 'real']" in str(ei.value)


def test_refuses_mixed_code_unless_flagged(tmp_path):
    a = _session(tmp_path, "A", {}, n_blocks=4)
    b = _session(tmp_path, "B", {}, env={**ENV, "software": {"src_sha256": "e" * 64}}, n_blocks=4)
    with pytest.raises(PoolingError, match="src_sha256"):
        analyze([a, b])
    meta = analyze([a, b], allow_mixed_code=True)["meta"]
    assert meta["allow_mixed_code"] is True and meta["code_versions"] == ["e" * 12, "f" * 12]
    assert analyze([a])["meta"]["allow_mixed_code"] is False


def test_incomplete_sessions_are_excluded_with_a_reason(tmp_path):
    a = _session(tmp_path, "A", {}, n_blocks=6)
    n = [0]

    def low_ram_from_third_check():  # start ok, block 0 ok, block 1 refused -> aborted after one block
        n[0] += 1
        return 16.0 if n[0] <= 2 else 0.0
    d = make_design(tmp_path, n_blocks=6, warmup=1, name="A.json")
    assert run_session(d, tmp_path / "out", StubAdapter(), session_id="Z", free_fn=low_ram_from_third_check, env=ENV)["status"] == "aborted"
    z = tmp_path / "out" / "Z"
    reasons = {r["reason"] for r in analyze([a, z])["tables"]["exclusions"] if r["run_id"].startswith("Z__")}
    assert reasons == {"session aborted: free RAM below 2.0 GB before block 1"}
    assert analyze([a, z])["meta"]["n_included_primary"] == analyze([a])["meta"]["n_included_primary"]
    (z / "session.json").unlink()                 # crashed hard enough to leave no session.json
    assert {r["reason"][:20] for r in analyze([a, z])["tables"]["exclusions"] if r["run_id"].startswith("Z__")} == {"session.json missing"}
    sj = json.loads((a / "session.json").read_text())
    sj["blocks_completed"] = 5                    # 'complete' but a block short
    (a / "session.json").write_text(json.dumps(sj))
    ex = analyze([a])["tables"]["exclusions"]
    assert len(ex) == 12 and all(r["reason"] == "session incomplete: 5 of 6 blocks" for r in ex)


def test_same_session_twice_or_copied_is_not_double_counted(tmp_path):
    import shutil
    a = _session(tmp_path, "A", {"B": 0.9}, n_blocks=6)
    assert analyze([a, a])["meta"]["n_runs"] == analyze([a])["meta"]["n_runs"] == 12
    shutil.copytree(a, tmp_path / "copy")
    with pytest.raises(ValueError, match="duplicate run_id"):
        analyze([a, tmp_path / "copy"])


def test_tampered_log_is_excluded(tmp_path):
    sd = _session(tmp_path, "S", {}, n_blocks=4)
    log = next(sd.glob("runs/*/*.jsonl"))
    log.chmod(0o666)
    log.write_text(log.read_text().replace("0.001", "0.002"))
    assert any("hash mismatch" in r["reason"] for r in analyze([sd])["tables"]["exclusions"])


def test_tables_figures_and_reproduction(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    sd = _session(tmp_path, "S", {"B": 0.9}, n_blocks=10)
    build_manifest(sd)
    res = analyze([sd], seed=3)
    out = tmp_path / "an"
    files = write_tables(res, out)
    assert {f.name for f in files} >= {"runs.csv", "effects.csv", "summary.csv", "exclusions.csv", "analysis.json"}
    assert "evidence_label" in next(csv.DictReader((out / "effects.csv").open())).keys()
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, str(root / "scripts" / "reproduce_subset.py"), "--analysis-dir", str(out), "--log", str(tmp_path / "rl.json")]
    assert subprocess.run(cmd, capture_output=True, text=True).returncode == 0
    assert json.loads((tmp_path / "rl.json").read_text())["ok"]
    (out / "summary.csv").write_text((out / "summary.csv").read_text().replace("A,", "A,9", 1))  # corrupt a reported number
    assert subprocess.run(cmd, capture_output=True, text=True).returncode == 1


def test_figures_tagged(tmp_path):
    pytest.importorskip("matplotlib")
    from caosched.analysis.stats_paired import make_figures
    figs = make_figures(analyze([_session(tmp_path, "S", {"B": 0.9}, n_blocks=8)]), tmp_path)
    assert len(figs) == 3 and all(f.stat().st_size > 0 for f in figs)



def test_posthoc_block_exclusion_is_recorded_and_changes_n(tmp_path):
    sdir = _session(tmp_path, "S", {"B": 0.9}, n_blocks=12)
    base = analyze([sdir], seed=1)
    ph = analyze([sdir], seed=1, posthoc_exclude_blocks=(3, 4))
    assert _eff(ph)["n_blocks"] == _eff(base)["n_blocks"] - 2
    assert {r["reason"] for r in ph["tables"]["exclusions"] if r["block"] in (3, 4)} == {"post-hoc block exclusion (declared as such, not pre-registered)"}
