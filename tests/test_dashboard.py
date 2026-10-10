"""Dashboard tests: replay reads genuine saved logs/artifacts, nothing is
hard-coded, unsafe paths are rejected, and the live path runs the real
runtime with the same configuration as the accepted experiment sessions."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import psutil
import pytest

from caosched.dashboard import data, live

SUMMARY = json.loads(data.PHASE_B_SUMMARY.read_text(encoding="utf-8"))
K16 = SUMMARY["accepted_sessions"]["16"]


def _runs_csv(session):
    return list(csv.DictReader(open(data.RESULTS / f"{session}_runs.csv", encoding="utf-8")))


def test_accepted_sessions_come_from_the_verified_summary():
    s = data.accepted_sessions()
    assert {x["k"]: x["session"] for x in s} == {int(k): v for k, v in SUMMARY["accepted_sessions"].items()}
    assert all(len(x["runs"]) == 20 for x in s)


def test_run_view_matches_the_saved_log_and_runs_csv():
    row = next(r for r in _runs_csv(K16) if r["policy"] == data.EFT)
    run = row["event_log"].rsplit("/", 1)[-1][:-len(".jsonl")]
    v = data.run_view(data.session_log(K16, run))
    assert v["scheduler"] == data.EFT and len(v["tasks"]) == 68
    assert all(t["state"] == "completed" for t in v["tasks"])
    assert v["finished"]["makespan_ms"] == pytest.approx(float(row["makespan_s"]) * 1e3)
    assert sum(t["pool"] == "R" for t in v["tasks"]) == int(row["tasks_R"])
    cp = v["critical_path"]
    by = {t["id"]: t for t in v["tasks"]}
    assert cp[0] == "source" and cp[-1] == "package"
    assert all(a in by[b]["deps"] for a, b in zip(cp, cp[1:]))
    assert any(t.get("candidates") for t in v["tasks"])  # EFT decisions are exposed


def test_run_view_handles_a_log_still_being_written(tmp_path):
    src = data.session_log(K16, "demo_B4_greedy_eligible_R_r00")
    lines = src.read_text(encoding="utf-8").splitlines()
    partial = tmp_path / "partial.jsonl"
    partial.write_text("\n".join(lines[:60]) + "\n" + lines[60][:25], encoding="utf-8")  # cut mid-line
    v = data.run_view(partial)
    assert v["started"] and v["finished"] is None and v["critical_path"] == []
    assert any(t["state"] != "completed" for t in v["tasks"])


@pytest.mark.parametrize("session,run", [("../events", "x"), ("a/b", "x"), (K16, "..\\x"),
                                         ("appdemo_20261003T212905", "demo_B4_greedy_eligible_R_r00")])
def test_unsafe_or_unaccepted_paths_are_rejected(session, run):
    with pytest.raises(data.NotFound):
        data.session_log(session, run)


def test_artifacts_are_real_pngs():
    log = data.session_log(K16, "demo_B4_greedy_eligible_R_r00")
    for which in ("source", "mosaic"):
        assert data.artifact_png(log, which)[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(data.NotFound):
        data.artifact_png(log, "other")


def test_comparison_values_equal_the_saved_summary():
    c = data.comparison()
    for lvl, s in zip(c["levels"], SUMMARY["sessions"]):
        assert lvl["k"] == s["k"]
        assert lvl["pct"]["mean"] == s["paired_eft_minus_b4"]["makespan_pct_t"]["effect_pct"]
        assert lvl["policy"][data.B4]["makespan_ms"]["mean"] == s["policies"][data.B4]["makespan_ms"]["mean"]
        assert lvl["stages"]["img_denoise"]["kernel_over_transfer"] == \
            s["transfer_vs_compute"]["img_denoise"]["E_kernel_over_R_transfer"]


def test_hardware_status_is_parsed_from_the_doc():
    hw = data.hardware_status()
    gpu = next(r for r in hw["rows"] if "GPU stage" in r["item"])
    assert "no" in gpu["executed"].lower() and "NOT VERIFIED" in gpu["verified"]


def test_live_configuration_matches_the_accepted_sessions():
    man = json.loads((data.RESULTS / f"{K16}_manifest.json").read_text(encoding="utf-8"))
    assert live.pipeline_kwargs(16) == man["pipeline"]
    assert live.link_config().to_dict() == man["link"]
    assert live.REMOTE == man["remote_stages"]
    assert live.NODE_CORE == man["args"]["node_core"]
    assert live.LINK_PROFILE == man["args"]["link_profile"]
    assert sorted(live.POLICIES.values()) == sorted(man["policies"])
    assert live.make_policy("B4", 16).name == data.B4
    eft = live.make_policy("EFT", 16)
    assert eft.name == data.EFT
    assert live.accepted_profile(16).name == man["profile"]


def test_server_endpoints():
    from caosched.dashboard.server import Handler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert b"<html" in urllib.request.urlopen(base + "/").read()
        assert len(json.loads(urllib.request.urlopen(base + "/api/sessions").read())) == 4
        for path, code in (("/api/run?session=..%2Fx&run=y", 404), ("/nope", 404)):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + path)
            assert e.value.code == code
        req = urllib.request.Request(base + "/api/live/start", data=b'{"policy":"X","k":3}',
                                     headers={"Content-Type": "application/json"}, method="POST")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        assert e.value.code == 400
    finally:
        httpd.shutdown()


def test_live_execution_uses_the_real_runtime(tmp_path):
    """End-to-end: one real B4 run (k=1) in a subprocess (it pins its coordinator core)."""
    if psutil.virtual_memory().available / 2**30 < 1.5:
        pytest.skip("less than 1.5 GiB free: not starting 10 worker processes")
    code = ("import sys; from pathlib import Path; from caosched.dashboard.live import execute; "
            "execute(Path(sys.argv[1]), 'B4', 1)")
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=True, timeout=300)
    st = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert st["state"] == "done" and st["status"] == "completed"
    assert st["verification"]["match"] == "exact"
    k1 = _runs_csv(SUMMARY["accepted_sessions"]["1"])
    assert st["verification"]["sha256"] == k1[0]["output_sha256"]  # same output as the accepted k=1 session
    v = data.run_view(tmp_path / "events" / "live_B4.jsonl")
    assert v["scheduler"] == data.B4 and v["metadata"]["mode"] == "dashboard_live"
    assert sum(t["state"] == "completed" for t in v["tasks"]) == 68
    r0 = next(w for w in v["workers"] if w["pool"] == "R")
    assert r0["capabilities"]["cuda"] is False  # the remote node reports itself honestly
