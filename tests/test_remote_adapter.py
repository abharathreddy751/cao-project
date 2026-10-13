"""Emulated-remote adapter, calibration script and design generator, at tile 64 (a few seconds per test; real node process)."""
import importlib.util
import json
from pathlib import Path

import pytest

from caosched.apps.image_pipeline import build_image_pipeline
from caosched.core.runtime_config import RuntimeConfig
from caosched.experiment.design import Condition, load_design, plan_blocks
from caosched.experiment.remote_adapter import DEFAULT_REMOTE_STAGES, RemoteAdapter, link_from_kwargs

ROOT = Path(__file__).resolve().parents[1]
LINK = {"name": "t", "latency_ms": 0.1, "bandwidth_mbps": 1000.0, "per_message_ms": 0.0, "jitter_ms": 0.0}


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _profile(path, tile, grid, p_s=1.0, e_s=1.0, r_s=1e-6):
    """Synthetic E1 profile (NOT a measurement): every (stage, size) of the pipeline on P, E, R; R only where remote-eligible."""
    dag = build_image_pipeline(tile * grid, tile * grid, grid, 0)
    keys = {(t.workload, t.size) for t in dag.tasks.values()}
    ent = [{"workload": w, "size": s, "pool": p, "median_s": v} for w, s in sorted(keys) for p, v in (("P", p_s), ("E", e_s))]
    ent += [{"workload": w, "size": s, "pool": "R", "median_s": r_s} for w, s in sorted(keys) if w in DEFAULT_REMOTE_STAGES]
    path.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": ent,
                                "link_calibration": {"socket_a_s": 0.0001, "socket_b_s_per_byte": 1e-9}}))
    return path


def _small_config():
    base = RuntimeConfig.from_topology(max_p_slots=1)  # 1 P + 1 E + the node on the last E core
    return RuntimeConfig(base.p_core_slots, base.e_core_slots[-2:], base.coordinator_core), base.e_core_slots[-1]


def test_link_kwargs_conversion_and_jitter_refused():
    link = link_from_kwargs({"name": "x", "latency_ms": 30.0, "bandwidth_mbps": 20.0, "per_message_ms": 0.1})
    assert (link.latency_s, link.bandwidth_Bps, link.per_message_s) == (0.03, 2.5e6, 0.0001)
    assert link_from_kwargs(None).shim_delay(10**9) == 0.0
    with pytest.raises(ValueError, match="jitter"):
        link_from_kwargs({"jitter_ms": 1.0})


def test_remote_run_places_on_R_verifies_and_stamps_emulation(tmp_path):
    prof = _profile(tmp_path / "p.json", 64, 2)
    cfg, node = _small_config()
    ad = RemoteAdapter(cfg, node_core=node, run_timeout_s=120)
    try:
        def run(name, policy, remote):
            kw = {"tile": 64, "n_images": 4, "profile": str(prof), "remote": remote, "link": LINK}
            wd = tmp_path / "exp" / "runs" / name
            wd.mkdir(parents=True)
            return ad.run_one(Condition(name, policy, kwargs=kw), wd, 1)

        rec = run("eft_remote", "EFT_E1", True)  # R is modelled faster than P/E: EFT must use it, so a remote path is exercised
        assert rec.status == "ok" and rec.output_ok is True, rec.error
        assert rec.extra["evidence_label"] == "emulation" and rec.extra["link_kwargs"] == LINK
        assert rec.extra["link"]["latency_s"] == pytest.approx(1e-4) and rec.extra["transfer_model"]["calibration_source"] == str(prof)
        remote = rec.extra["remote_tasks"]
        assert remote and all(t.split("_")[0] in {"denoise", "edges", "features"} for t in remote)
        assert rec.extra["tasks_per_pool"]["R"] == len(remote)
        assert rec.output_hashes["package"] and rec.extra["output_verdict"]["match"] in ("exact", "numeric")

        # same pool reused (link switched), control: R ineligible
        ctl = run("eft_ctl", "EFT_E1", False)
        assert ctl.status == "ok" and ctl.output_ok is True and ctl.extra["remote_tasks"] == []
        assert ctl.extra["evidence_label"] == "emulation" and not ctl.extra["link_active"]

        b4 = run("b4_remote", "B4_greedy_eligible", True)  # whether B4 reaches R depends on timing; only correctness is asserted
        assert b4.status == "ok" and b4.output_ok is True and b4.extra["policy"] == "B4_greedy_eligible_R"
    finally:
        ad.close()


def test_design_loads_plans_and_holm_numbers(tmp_path):
    prof = tmp_path / "p.json"
    ent = [{"workload": s, "size": 512 * 512, "pool": p, "median_s": 0.05} for s in DEFAULT_REMOTE_STAGES for p in "PER"]
    prof.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": ent,
                                "link_calibration": {"socket_a_s": 0.0001, "socket_b_s_per_byte": 1e-9}}))
    _script("make_remote_design").main(str(tmp_path / "d"), str(prof))
    d = load_design(tmp_path / "d" / "design_remote.json")
    assert d.evidence_label == "emulation" and d.reference == "EFT_E1_no_remote" and d.n_blocks == 12
    assert [c.name for c in d.conditions][:3] == ["B0_P_only", "B4_no_remote", "EFT_E1_no_remote"] and len(d.conditions) == 7
    plan = plan_blocks(d)
    assert len(plan) == 12 and all(len(b["runs"]) == 7 for b in plan)
    ap = d.analysis_plan
    assert ap["holm_smallest_threshold"] == pytest.approx(0.05 / 6) and ap["min_attainable_p_at_n_blocks"] == pytest.approx(2 / 4096)
    assert ap["smallest_n_blocks_with_min_p_below_threshold"] == 8
    rem = [c for c in d.conditions if c.kwargs["remote"]]
    assert {c.kwargs["link"]["name"] for c in rem} == {"fast_lan", "slow_wan"} and all(c.kwargs["link"]["jitter_ms"] == 0 for c in rem)
    with pytest.raises(FileExistsError):  # exclusive create
        _script("make_remote_design").main(str(tmp_path / "d"), str(prof))
    for c in d.conditions:  # every condition's policy/kwargs are acceptable to the adapter before any run
        link_from_kwargs(c.kwargs.get("link"))


def test_calibrate_link_writes_profile_with_R_rows_and_fit(tmp_path):
    base = _profile(tmp_path / "base.json", 32, 2)
    b = json.loads(base.read_text())
    b["entries"] = [e for e in b["entries"] if e["pool"] != "R"]  # a P/E-only base, as profile_gpu_workload.py writes
    base.write_text(json.dumps(b))
    out = tmp_path / "cal" / "prof.json"
    out.parent.mkdir()
    assert _script("calibrate_link").main(["--base-profile", str(base), "--out", str(out), "--tile", "32", "--n-images", "4",
                                           "--calib-tiles", "16", "32", "--reps", "1", "--warmup", "0", "--max-p-slots", "1"]) == 0
    p = json.loads(out.read_text())
    assert {(e["workload"], e["size"]) for e in p["entries"] if e["pool"] == "R"} == {(s, t * t) for s in DEFAULT_REMOTE_STAGES for t in (16, 32)}
    assert p["link_calibration"]["n"] == 6 and p["link_calibration"]["shim"].startswith("zero")
    assert out.with_name("prof_raw.csv").is_file() and "emulation" in p["calibration_label"]
