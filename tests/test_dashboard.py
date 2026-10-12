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
        page = urllib.request.urlopen(base + "/").read()
        from caosched.dashboard.server import TOKEN
        assert TOKEN.encode() in page and b"__CAO_TOKEN__" not in page  # token injected into the served page only
        assert TOKEN.encode() not in urllib.request.urlopen(base + "/app.js").read()

        def post(**extra):
            hdr = {"Content-Type": "application/json", **extra}
            req = urllib.request.Request(base + "/api/live/start", data=b'{"policy":"X","k":3}', headers=hdr, method="POST")
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req)
            return e.value.code
        ok = {"Origin": base, "X-CAO-Token": TOKEN}
        assert post(**ok) == 400                                              # authorised; bad policy rejected by the handler
        assert post() == 403                                                  # no token, no Origin
        assert post(Origin=base) == 403                                       # Origin only
        assert post(**{"X-CAO-Token": TOKEN}) == 403                          # token only (no Origin)
        assert post(Origin=base, **{"X-CAO-Token": "wrong"}) == 403           # wrong token
        assert post(Origin=base, **{"X-CAO-Token": "é" * 32}) == 403          # non-ASCII token: 403, not a server error
        assert post(Origin="http://evil.example", **{"X-CAO-Token": TOKEN}) == 403  # cross-origin
        assert post(Host="evil.example", **ok) == 403                         # DNS-rebinding style Host
        for host, path in (("evil.example", "/"), ("evil.example", "/api/sessions")):  # GET also host-checked
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(urllib.request.Request(base + path, headers={"Host": host}))
            assert e.value.code == 403
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
    try:  # independent probe: a direct torch call, not the code path the node itself uses
        import torch
        probe = bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - CPU-only machine
        probe = False
    caps = r0["capabilities"]
    assert caps["cuda"] is probe                             # the remote node reports itself honestly
    assert (caps["cuda_device"] is not None) is caps["cuda"]  # a device name iff CUDA is reported


# ---------------------------------------------------------- Montage / GPU (hand-written fixture, no real Montage) ---

def _extcmd_run(sess, name, policy, pools, makespan_s):
    """A tiny extcmd run: two mProject tasks feed one mAdd, written the way the Coordinator logs it."""
    import hashlib
    d = sess / "runs" / name
    d.mkdir(parents=True)
    spec = lambda tr: {"workload": "extcmd", "size": 1, "seed": 0, "params": {"argv": [tr + ".exe"], "transformation": tr}}  # noqa: E731
    ev = [{"event": "run_started", "t": 100.0, "run_id": name, "scheduler": policy, "scheduler_config": {}, "metadata": {},
           "n_tasks": 3, "edges": [["ID1", "ID3"], ["ID2", "ID3"]],
           "tasks": {"ID1": spec("mProject"), "ID2": spec("mProject"), "ID3": {**spec("mAdd"), "eligible_pools": ["P"]}},
           "software": {}, "memory_available_bytes": 2**33},
          {"event": "worker_ready", "t": 100.0, "worker_id": "P0", "pool": "P", "actual_affinity": [0], "affinity_ok": True},
          {"event": "worker_ready", "t": 100.0, "worker_id": "E0", "pool": "E", "actual_affinity": [2], "affinity_ok": True}]
    for i, (tid, pool) in enumerate(zip(("ID1", "ID2"), pools)):
        w = pool + "0"
        ev += [{"event": "task_ready", "t": 100.0, "task_id": tid},
               {"event": "task_dispatched", "t": 100.5 + i, "task_id": tid, "worker_id": w, "pool": pool,
                "queue_wait_seconds": 0.5 + i},
               {"event": "task_completed", "t": 101.5 + i, "task_id": tid, "worker_id": w, "pool": pool, "t_started": 100.6 + i,
                "t_completed": 101.4 + i, "wall_time_seconds": 0.8, "output_bytes": 4, "io_s": 0.01, "exit_status": 0,
                "outputs": {tid + ".fits": {"bytes": 4, "sha256": "ab" * 32}}}]
    ev += [{"event": "task_ready", "t": 103.0, "task_id": "ID3"},
           {"event": "task_dispatched", "t": 103.0, "task_id": "ID3", "worker_id": "P0", "pool": "P", "queue_wait_seconds": 0.0},
           {"event": "task_completed", "t": 104.0, "task_id": "ID3", "worker_id": "P0", "pool": "P", "t_started": 103.1,
            "t_completed": 103.9, "wall_time_seconds": 0.8, "output_bytes": 4, "io_s": 0.0, "exit_status": 0, "outputs": {}},
           {"event": "run_finished", "t": 104.0, "status": "completed", "makespan_seconds": makespan_s,
            "tasks_per_pool": {"P": 2 if "E" in pools else 3, "E": pools.count("E")}}]
    log = d / f"{name}.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in ev) + "\n", encoding="utf-8")
    man = {"run_id": f"S1__{name}", "session_id": "S1", "block": 0, "instance": "inst1", "policy": policy, "seed": 1, "warmup": False,
           "condition": {"name": policy, "policy": policy, "estimator": None, "workload": {}}, "evidence_label": "plan",
           "status": "ok", "error": None,
           "verification": {"passed": True, "output_hashes": {"1-mosaic.fits": "ab" * 32}},
           "event_log": {"path": log.name, "sha256": hashlib.sha256(log.read_bytes()).hexdigest(), "bytes": log.stat().st_size},
           "extra": {"makespan_seconds": makespan_s, "n_tasks": 3, "output_verdict": {"1-mosaic.fits": "identical"}}}
    (d / "run_manifest.json").write_text(json.dumps(man), encoding="utf-8")
    return man["run_id"]


def test_montage_run_is_read_from_manifest_and_extcmd_log(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "EXTRA_ROOTS", [tmp_path])
    rid = _extcmd_run(tmp_path / "S1", "b0000_00_B1", "B1_round_robin", "PE", 4.0)
    rid2 = _extcmd_run(tmp_path / "S1", "b0000_01_EFT", "EFT_E1", "PP", 3.5)
    runs = {r["id"]: r for r in data.montage_runs()}
    assert runs[rid]["kind"] == "montage" and runs[rid]["instance"] == runs[rid2]["instance"] == "inst1"
    assert runs[rid]["makespan_ms"] == pytest.approx(4000) and runs[rid2]["output_ok"] is True
    d = data.montage_run(rid)
    v = d["view"]
    assert v["extcmd"] and v["scheduler"] == "B1_round_robin" and v["finished"]["makespan_ms"] == pytest.approx(4000)
    by = {t["id"]: t for t in v["tasks"]}
    assert by["ID1"]["stage"] == "mProject" and by["ID3"]["stage"] == "mAdd" and by["ID3"]["eligible"] == ["P"]
    assert by["ID2"]["queue_wait_ms"] == pytest.approx(1500) and by["ID2"]["pool"] == "E"
    assert by["ID1"]["outputs"]["ID1.fits"]["sha256"] == "ab" * 32
    assert v["critical_path"][-1] == "ID3"
    assert d["verification"] == {"passed": True, "output_hashes": {"1-mosaic.fits": "ab" * 32},
                                 "verdict": {"1-mosaic.fits": "identical"}, "log_sha256_ok": True}
    assert [(s["stage"], s["level"], s["n"]) for s in d["stages"]] == [("mProject", 0, 2), ("mAdd", 1, 1)]
    assert d["edges"] == [{"from": "mProject", "to": "mAdd", "n": 2}]
    assert d["stages"][0]["pools"] == {"P": 1, "E": 1}
    with pytest.raises(data.NotFound):
        data.montage_run("S1__../../x")


def test_montage_run_flags_a_modified_event_log(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "EXTRA_ROOTS", [tmp_path])
    rid = _extcmd_run(tmp_path / "S1", "b0000_00_B1", "B1_round_robin", "PE", 4.0)
    log = tmp_path / "S1" / "runs" / "b0000_00_B1" / "b0000_00_B1.jsonl"
    log.write_text(log.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert data.montage_run(rid)["verification"]["log_sha256_ok"] is False


def test_gpu_spike_rows_come_from_the_json(tmp_path, monkeypatch):
    spike = tmp_path / "stage" / "gpu" / "gpu_spike.json"
    spike.parent.mkdir(parents=True)
    spike.write_text(json.dumps({"env": {"gpu": "X"}, "rows": [{
        "stage": "img_edges", "params": "{}", "side": 128, "reps": 3, "cpu_median_s": 0.002, "gpu_median_s": 0.001,
        "speedup": 2.0, "equivalent": True, "max_abs": 0.0, "verdict": "PASS"}]}), encoding="utf-8")
    monkeypatch.setattr(data, "RESULTS", tmp_path)
    monkeypatch.setattr(data, "ROOT", tmp_path)
    g = data.gpu_spike()
    assert g["rows"][0]["cpu_ms"] == pytest.approx(2.0) and g["rows"][0]["gpu_ms"] == pytest.approx(1.0)
    assert g["rows"][0]["verdict"] == "PASS" and g["env"] == {"gpu": "X"}
    monkeypatch.setattr(data, "RESULTS", tmp_path / "none")
    with pytest.raises(data.NotFound):
        data.gpu_spike()


def test_montage_endpoints(tmp_path, monkeypatch):
    from caosched.dashboard.server import Handler
    monkeypatch.setattr(data, "EXTRA_ROOTS", [tmp_path])
    rid = _extcmd_run(tmp_path / "S1", "b0000_00_B1", "B1_round_robin", "PE", 4.0)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert [r["id"] for r in json.loads(urllib.request.urlopen(base + "/api/montage/runs").read())
                if r["id"] == rid] == [rid]
        d = json.loads(urllib.request.urlopen(base + f"/api/montage/run?id={rid}").read())
        assert d["view"]["n_tasks"] == 3
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/api/montage/run?id=nope")
        assert e.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as e:  # Host check still applies to the new endpoints
            urllib.request.urlopen(urllib.request.Request(base + "/api/montage/runs", headers={"Host": "evil.example"}))
        assert e.value.code == 403
    finally:
        httpd.shutdown()
