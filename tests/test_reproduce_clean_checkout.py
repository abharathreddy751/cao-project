"""Fast unit tests of the pure helpers of scripts/reproduce_clean_checkout.py (no clone, no venv, no network)."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_p = Path(__file__).resolve().parents[1] / "scripts" / "reproduce_clean_checkout.py"
_spec = importlib.util.spec_from_file_location("reproduce_clean_checkout", _p)
rcc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rcc
_spec.loader.exec_module(rcc)

PY = sys.executable


def _repo(tmp_path):
    (tmp_path / "src" / ".git").mkdir(parents=True)
    return tmp_path / "src"


def test_parse_args_validation(tmp_path):
    src = _repo(tmp_path)
    base = ["--source", str(src), "--dest", str(tmp_path / "d")]
    assert rcc.parse_args(base).tests == rcc.DEFAULT_TESTS
    for bad in (["--timeout-s", "0"], ["--install-timeout-s", "-1"], ["--montage-subset"],
                ["--data-dir", str(tmp_path)], ["--tests", "../x.py"], ["--tests", "-k"], ["--tests", str(tmp_path / "t.py")],
                ["--montage-subset", "--data-dir", str(tmp_path), "--instance", "../evil"], ["--branch", "--upload-pack=x"]):
        with pytest.raises(SystemExit) as e:
            rcc.parse_args(base + bad)
        assert e.value.code == 2
    with pytest.raises(SystemExit):  # source that is not a git checkout
        rcc.parse_args(["--source", str(tmp_path), "--dest", str(tmp_path / "d")])
    ok = rcc.parse_args(base + ["--tests", "tests/test_a.py::test_x", "--montage-subset", "--data-dir", str(tmp_path), "--instance", "d1.1_a"])
    assert ok.tests == ["tests/test_a.py::test_x"] and ok.instance == ["d1.1_a"]


def test_prepare_dest_refuses_non_empty_and_overlap(tmp_path):
    src = _repo(tmp_path)
    full = tmp_path / "full"
    full.mkdir()
    (full / "f.txt").write_text("x")
    with pytest.raises(ValueError, match="not empty"):
        rcc.prepare_dest(full, src)
    assert (full / "f.txt").read_text() == "x"  # untouched
    afile = tmp_path / "afile"
    afile.write_text("x")
    with pytest.raises(ValueError, match="not a directory"):
        rcc.prepare_dest(afile, src)
    with pytest.raises(ValueError, match="overlaps"):
        rcc.prepare_dest(src / "inside", src)
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(ValueError, match="overlaps"):
        rcc.prepare_dest(data / "inside", src, data)
    new = rcc.prepare_dest(tmp_path / "new" / "deeper", src)  # absent: created
    assert new.is_dir() and not any(new.iterdir())
    empty = tmp_path / "empty"
    empty.mkdir()
    assert rcc.prepare_dest(empty, src) == empty.resolve()


def test_main_refuses_non_empty_dest_without_doing_anything(tmp_path, capsys):
    src = _repo(tmp_path)
    d = tmp_path / "d"
    d.mkdir()
    (d / "keep").write_text("1")
    assert rcc.main(["--source", str(src), "--dest", str(d)]) == 2
    assert sorted(p.name for p in d.iterdir()) == ["keep"]  # no logs dir, no log, nothing created
    assert "not empty" in capsys.readouterr().err


def test_write_log_is_exclusive(tmp_path):
    p = tmp_path / "repro_log.json"
    rcc.write_log(p, {"ok": True, "steps": []})
    with pytest.raises(FileExistsError):
        rcc.write_log(p, {"ok": False})
    assert json.loads(p.read_text())["ok"] is True
    with pytest.raises(FileExistsError):
        rcc.write_design(p)  # same rule for the design file


def test_design_is_valid_stub_design(tmp_path):
    d = json.loads(rcc.write_design(tmp_path / "d.json").read_text())
    names = [c["name"] for c in d["conditions"]]
    assert len(set(names)) == len(names) >= 3 and d["reference"] in names
    assert d["evidence_label"] == "plan" and 0 <= d["warmup_blocks"] < d["n_blocks"]


def test_run_step_records_failure_exit_code(tmp_path):
    r = rcc.run_step("fails", [PY, "-c", "import sys; print('out'); sys.stderr.write('boom'); sys.exit(3)"],
                     cwd=tmp_path, timeout_s=60, log_path=tmp_path / "fails.txt")
    assert (r["exit_code"], r["ok"], r["status"], r["timed_out"]) == (3, False, "failed", False)
    assert "out" in r["stdout_tail"] and "boom" in r["stderr_tail"] and r["duration_s"] >= 0
    assert "exit 3" in (tmp_path / "fails.txt").read_text()
    with pytest.raises(FileExistsError):  # step logs are exclusive too
        rcc.run_step("fails", [PY, "-c", "pass"], cwd=tmp_path, log_path=tmp_path / "fails.txt")
    ok = rcc.run_step("good", [PY, "-c", "pass"], cwd=tmp_path)
    assert (ok["exit_code"], ok["ok"], ok["status"]) == (0, True, "ok")


def test_run_step_timeout_and_missing_executable(tmp_path):
    t = rcc.run_step("slow", [PY, "-c", "import time; time.sleep(30)"], cwd=tmp_path, timeout_s=0.5)
    assert t["timed_out"] and t["status"] == "timeout" and t["exit_code"] is None and not t["ok"]
    m = rcc.run_step("nope", [str(tmp_path / "no_such_exe")], cwd=tmp_path)
    assert m["exit_code"] is None and not m["ok"] and m["status"] == "failed" and "FileNotFoundError" in m["error"]


def test_steps_skip_dependants_and_fail_overall(tmp_path):
    (tmp_path / "logs").mkdir()
    s = rcc.Steps(tmp_path / "logs")
    s.run("a", [PY, "-c", "import sys; sys.exit(1)"], cwd=tmp_path)
    b = s.run("b", [PY, "-c", "pass"], cwd=tmp_path, depends=["a"])
    c = s.run("c", [PY, "-c", "pass"], cwd=tmp_path)
    assert b["status"] == "skipped" and not b["ok"] and "a" in b["error"]
    assert c["ok"] and [r["name"] for r in s.records] == ["a", "b", "c"]
    assert not s.ok
    e = s.call("boom", lambda: 1 / 0)
    assert e["status"] == "failed" and "ZeroDivisionError" in e["error"]
    only_ok = rcc.Steps()
    only_ok.run("x", [PY, "-c", "pass"], cwd=tmp_path)
    only_ok.call("y", lambda: (True, {"k": 1}))
    assert only_ok.ok and not rcc.Steps().ok  # no steps is not a pass


def test_filter_requirements_drops_torch_only():
    text = "numpy==2.4.6\n# comment\ntorch==2.11.0+cu128\ntorchvision==1\nPyYAML==6.0.3\n"
    out, dropped = rcc.filter_requirements(text)
    assert dropped == ["torch==2.11.0+cu128"]
    assert "torchvision==1" in out and "numpy==2.4.6" in out and "torch==" not in out.replace("torchvision==", "")


def test_montage_subset_hash_check(tmp_path):
    data = tmp_path / "data"
    (data / "montage" / "bin_win64").mkdir(parents=True)
    inst = data / "montage" / "instances" / "i1"
    (inst / "data").mkdir(parents=True)
    (inst / "inputs").mkdir()
    h = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
    (data / "montage" / "bin_win64" / "mAdd.exe").write_bytes(b"add")
    (inst / "data" / "montage-workflow.yml").write_bytes(b"yml")
    (inst / "inputs" / "a.fits").write_bytes(b"fits")
    (inst / "instance.json").write_text(json.dumps({"workflow_yml_sha256": h(b"yml"),
                                                    "inputs": [{"lfn": "a.fits", "bytes": 4, "sha256": h(b"fits")}]}))
    manifest = f"{h(b'add')} *mAdd.exe\n"
    ok, d = rcc.verify_montage_subset(data, manifest, ["i1"])
    assert ok and d["n_expected"] == 3
    (inst / "inputs" / "a.fits").write_bytes(b"FITS")  # same size, other content
    ok, d = rcc.verify_montage_subset(data, manifest, ["i1"])
    assert not ok and d["changed"] == ["instances/i1/inputs/a.fits"]
    ok, d = rcc.verify_montage_subset(data, manifest + f"{h(b'x')} *mGone.exe\n", ["nope"])
    assert not ok and "bin_win64/mGone.exe" in d["missing"] and any("nope" in m for m in d["missing"])
    assert not rcc.verify_montage_subset(data, "", [])[0]  # empty manifest verifies nothing: not a pass
    with pytest.raises(ValueError):
        rcc.parse_sha256sum("not-a-hash *x.exe")
