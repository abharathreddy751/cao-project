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


# --- overnight sprint: external node (host/port) support -------------------------------------------------------------------

def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_external_node(core):
    """A node started like a Pi would be: its own process, listening on a fixed loopback port (not spawned by the pool)."""
    import socket
    import subprocess
    import sys
    import time
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "caosched.remote.node", "--host", "127.0.0.1", "--port", str(port),
                             "--affinity", str(core), "--persistent"])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return proc, port
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("external node did not start")


def test_external_loopback_node_runs_verifies_and_is_labelled_emulation(tmp_path):
    prof = _profile(tmp_path / "p.json", 64, 2)
    cfg, node = _small_config()
    proc, port = _start_external_node(node)
    ad = RemoteAdapter(cfg, remote_host="127.0.0.1", remote_port=port, run_timeout_s=120)
    try:
        wd = tmp_path / "exp" / "runs" / "ext"
        wd.mkdir(parents=True)
        kw = {"tile": 64, "n_images": 4, "profile": str(prof), "remote": True, "link": {"name": "real"}}
        rec = ad.run_one(Condition("ext", "EFT_E1", kwargs=kw), wd, 1)
        assert rec.status == "ok" and rec.output_ok is True, rec.error
        assert rec.extra["tasks_per_pool"].get("R", 0) > 0                      # R is modelled fastest: EFT must use the external node
        assert rec.extra["node_core"] is None and rec.extra["pools"]["R"] == []  # no local core was given to a spawned node
        assert rec.extra["evidence_label"] == "emulation" and ad.evidence_label_override == "emulation"  # loopback is never 'real'
        assert rec.extra["remote_host"] == "127.0.0.1" and rec.extra["remote_port"] == port
        ad.close()  # pool closed (bye): a persistent node must accept the next pool, as a Pi node must between isolated runs
        wd2 = tmp_path / "exp" / "runs" / "ext2"
        wd2.mkdir(parents=True)
        rec2 = ad.run_one(Condition("ext2", "EFT_E1", kwargs=kw), wd2, 2)
        assert rec2.status == "ok" and rec2.output_ok is True, rec2.error
        assert rec2.extra["tasks_per_pool"].get("R", 0) > 0
    finally:
        ad.close()
        proc.kill()
        proc.wait(10)


def test_external_non_loopback_host_is_real_and_refuses_a_delay_shim():
    ad = RemoteAdapter(remote_host="192.0.2.10", remote_port=5555)  # TEST-NET-1 address: nothing connects, the error comes first
    assert ad.evidence_label_override == "real"
    with pytest.raises(ValueError, match="shim"):
        ad.run_one(Condition("x", "B4", kwargs={"remote": True, "link": {"name": "s", "latency_ms": 5.0}}), Path("."), 1)
    with pytest.raises(ValueError, match="together"):
        RemoteAdapter(remote_host="192.0.2.10")


def test_calibrate_link_carries_the_denoise_iterations_to_the_measured_task():
    cl = _script("calibrate_link")
    from types import SimpleNamespace
    seen = []

    class FakePool:
        def submit(self, wid, msg):
            seen.append((msg.workload, dict(msg.params)))

        def poll_result(self, timeout):
            return SimpleNamespace(wall_time_seconds=0.001, transfer_s=0.0001, payload_bytes=10, error=None)

    class Writer:
        def writerow(self, row):
            pass

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cl.measure(FakePool(), [32], 2, 1, 0, Path(tmp), ("img_denoise",), Writer(), iterations=7)
    assert seen and all(w == "img_denoise" and p["iterations"] == 7 for w, p in seen)


def test_make_pi_design_writes_design_and_adapter_config(tmp_path):
    mk = _script("make_pi_design")
    prof = _profile(tmp_path / "p.json", 512, 4, p_s=0.01, e_s=0.03, r_s=0.05)
    out = tmp_path / "designs"
    assert mk.main([str(out), str(prof), "--host", "192.0.2.10", "--port", "5555", "--n-blocks", "4", "--denoise-iterations", "30"]) == 0
    d = json.loads((out / "design_pi.json").read_text())
    assert d["evidence_label"] == "real" and d["warmup_blocks"] == 1 and d["reference"] == "EFT_E1_no_remote"
    names = [c["name"] for c in d["conditions"]]
    assert names == ["B0_P_only", "B4_no_remote", "EFT_E1_no_remote", "B4_remote", "EFT_E1_remote"]
    rem = [c for c in d["conditions"] if c["kwargs"]["remote"]]
    assert all(c["kwargs"]["link"] == {"name": "real"} and c["kwargs"]["denoise_iterations"] == 30 for c in rem)
    cfg = json.loads((out / "adapter_config_pi.json").read_text())
    assert cfg["remote_host"] == "192.0.2.10" and cfg["remote_port"] == 5555
    ad = RemoteAdapter(**cfg)  # the config is accepted by the adapter and a non-loopback host means 'real'
    assert ad.evidence_label_override == "real"
    assert load_design(out / "design_pi.json").n_blocks == 4
    with pytest.raises(FileExistsError):
        mk.main([str(out), str(prof), "--host", "192.0.2.10", "--port", "5555"])  # exclusive create: never overwrites a design
