import json
import time

import pytest

from _exp_helpers import ENV, make_design
from caosched.experiment.manifest import build_manifest, verify_manifest
from caosched.experiment.runner import run_session
from caosched.experiment.stub import StubAdapter


def _run(tmp_path, adapter=None, **kw):
    return run_session(make_design(tmp_path, n_blocks=3, warmup=1, instances=("i1",)), tmp_path / "out",
                       adapter or StubAdapter(), session_id="S", free_fn=kw.pop("free_fn", lambda: 16.0), env=ENV, **kw)


def test_session_layout_manifests_and_readonly_log(tmp_path):
    s = _run(tmp_path)
    assert s["status"] == "complete" and s["blocks_completed"] == 3 and s["evidence_label"] == "plan"
    sd = tmp_path / "out" / "S"
    assert (sd / "design.sha256").read_text().strip() == s["design_sha256"]
    runs = sorted((sd / "runs").iterdir())
    assert len(runs) == 6
    m = json.loads((runs[0] / "run_manifest.json").read_text())
    assert m["warmup"] and m["verification"]["passed"] and m["code"]["src_sha256"] and m["input_hashes"]
    assert m["event_log"]["sha256"] and m["machine_id"] == "M1" and m["seed"] is not None
    with pytest.raises(PermissionError):  # raw log is read-only after the run
        (runs[0] / m["event_log"]["path"]).open("a")


def test_refuses_to_overwrite_session_and_logs(tmp_path):
    _run(tmp_path)
    with pytest.raises(FileExistsError):
        _run(tmp_path)
    run_dir = next((tmp_path / "out" / "S" / "runs").glob("*_A"))
    with pytest.raises(FileExistsError):
        StubAdapter().run_one(_cond(), run_dir, 1)  # log file already there -> 'x' mode refuses


def _cond():
    from caosched.experiment.design import Condition
    return Condition(name="A", policy="p")


def test_failures_kept_and_flagged(tmp_path):
    _run(tmp_path, StubAdapter(fail={"A"}, bad_output={"B"}))
    ms = [json.loads(p.read_text()) for p in (tmp_path / "out" / "S" / "runs").glob("*/run_manifest.json")]
    assert len(ms) == 6
    assert {m["status"] for m in ms if m["condition"]["name"] == "A"} == {"failed"}
    assert {m["verification"]["passed"] for m in ms if m["condition"]["name"] == "B"} == {False}
    assert {m["verification"]["passed"] for m in ms if m["condition"]["name"] == "A"} == {False}  # failed run: never "unknown"/True


def test_crash_leaves_session_json_crashed(tmp_path):
    calls = []

    def free():
        calls.append(1)
        if len(calls) == 3:  # session start ok, block 0 ok, block 1 raises
            raise RuntimeError("boom")
        return 8.0
    with pytest.raises(RuntimeError, match="boom"):
        run_session(make_design(tmp_path, n_blocks=3, name="c.json"), tmp_path / "o", StubAdapter(), session_id="C",
                    free_fn=free, env=ENV)
    s = json.loads((tmp_path / "o" / "C" / "session.json").read_text())
    assert s["status"] == "crashed" and "boom" in s["reason"] and s["blocks_completed"] == 1 and s["n_blocks"] == 3


class _SlowA(StubAdapter):
    def run_one(self, condition, workdir, seed):
        if condition.name == "A":
            time.sleep(120)
        return super().run_one(condition, workdir, seed)


def test_run_timeout_kills_the_run_and_is_recorded(tmp_path):
    d = make_design(tmp_path, n_blocks=1, warmup=0, instances=("i1",), run_timeout_s=2)
    s = run_session(d, tmp_path / "out", _SlowA(), session_id="T", free_fn=lambda: 16.0, env=ENV)
    assert s["status"] == "complete"
    ms = {m["condition"]["name"]: m for m in (json.loads(p.read_text()) for p in (tmp_path / "out" / "T" / "runs").glob("*/run_manifest.json"))}
    assert ms["A"]["status"] == "timeout" and "run_timeout_s" in ms["A"]["error"] and ms["A"]["verification"]["passed"] is False
    assert ms["A"]["event_log"] is None and ms["A"]["design"]["run_timeout_s"] == 2
    assert ms["B"]["status"] == "ok" and ms["B"]["verification"]["passed"] is True  # run in the child, result returned


def test_run_timeout_validation(tmp_path):
    import pickle
    bad = make_design(tmp_path, run_timeout_s=-1)
    with pytest.raises(ValueError, match="run_timeout_s"):
        run_session(bad, tmp_path / "out", StubAdapter(), session_id="V", free_fn=lambda: 16.0, env=ENV)
    unpicklable = StubAdapter()
    unpicklable.hook = lambda: None
    with pytest.raises((pickle.PicklingError, AttributeError, TypeError)):
        run_session(make_design(tmp_path, name="e.json", run_timeout_s=5), tmp_path / "out", unpicklable, session_id="V",
                    free_fn=lambda: 16.0, env=ENV)
    assert not (tmp_path / "out" / "V").exists()  # refused before creating anything


def test_git_unavailable_is_recorded_not_faked(tmp_path, monkeypatch):
    from caosched.experiment import runner
    monkeypatch.setattr(runner, "_cmd", lambda *a: None)
    assert runner._git_info() == {"commit": "unavailable", "dirty": "unavailable"}
    monkeypatch.setattr(runner, "_cmd", lambda *a: "abc" if a[1] == "rev-parse" else "")
    assert runner._git_info() == {"commit": "abc", "dirty": False}
    env = {**ENV, "git": {"commit": "unavailable", "dirty": "unavailable"}}
    run_session(make_design(tmp_path, n_blocks=2, warmup=1, instances=("i1",)), tmp_path / "out", StubAdapter(), session_id="G",
                free_fn=lambda: 16.0, env=env)
    m = json.loads(next((tmp_path / "out" / "G" / "runs").glob("*/run_manifest.json")).read_text())
    assert m["code"]["git_commit"] == "unavailable" and m["code"]["git_available"] is False
    _run(tmp_path)  # ENV carries a real-looking commit
    m = json.loads(next((tmp_path / "out" / "S" / "runs").glob("*/run_manifest.json")).read_text())
    assert m["code"]["git_available"] is True


def test_manifest_refuses_to_overwrite_without_force(tmp_path):
    _run(tmp_path)
    sd = tmp_path / "out" / "S"
    build_manifest(sd)
    with pytest.raises(FileExistsError):
        build_manifest(sd)
    build_manifest(sd, force=True)
    assert verify_manifest(sd)["ok"]


def test_preflight_abort_at_start_and_between_blocks(tmp_path):
    s = _run(tmp_path, free_fn=lambda: 0.79)
    assert s["status"] == "aborted" and "session start" in s["reason"]
    assert not (tmp_path / "out" / "S" / "runs").exists()
    calls = iter([8.0, 8.0, 0.5])  # start ok, block 0 ok, block 1 low
    (tmp_path / "o2").mkdir()
    s = run_session(make_design(tmp_path, n_blocks=3, name="e.json"), tmp_path / "o2", StubAdapter(), session_id="T",
                    free_fn=lambda: next(calls), env=ENV)
    assert s["status"] == "aborted" and s["blocks_completed"] == 1 and "before block 1" in s["reason"]
    assert json.loads((tmp_path / "o2" / "T" / "session.json").read_text())["status"] == "aborted"
    assert len(list((tmp_path / "o2" / "T" / "runs").iterdir())) == 2  # block 0 kept
    assert len((tmp_path / "o2" / "T" / "preflight.jsonl").read_text().splitlines()) == 3


def test_manifest_verify_detects_changed_byte(tmp_path):
    _run(tmp_path)
    sd = tmp_path / "out" / "S"
    mp = build_manifest(sd)
    assert verify_manifest(sd)["ok"]
    log = next(sd.glob("runs/*/*.jsonl"))
    log.chmod(0o666)
    b = bytearray(log.read_bytes())
    b[10] ^= 1
    log.write_bytes(bytes(b))
    r = verify_manifest(sd, mp)
    assert not r["ok"] and r["changed"] == [log.relative_to(sd).as_posix()]
    (sd / "new.txt").write_text("x")
    assert verify_manifest(sd)["extra"] == ["new.txt"]
