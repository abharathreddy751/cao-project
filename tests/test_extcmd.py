"""External-command tasks: argv run without a shell, declared inputs/outputs,
timeout with process-tree kill, size + SHA-256 records. Real subprocesses
(python -c), real worker processes."""
import hashlib
import stat
import subprocess
import sys
import time

import psutil
import pytest

from caosched.core.coordinator import Coordinator, TaskFailedError
from caosched.core.dag import DAG
from caosched.core.event_log import EventLogger, read_events
from caosched.core.extcmd import kill_tree, make_extcmd_task, prepare_workdir, run_extcmd
from caosched.core.scheduler_base import FirstIdleScheduler
from caosched.core.worker_pool import WorkerPool


def _params(tmp_path, code, inputs=(), outputs=(), timeout_s=30, stdout=None):
    return {"argv": [sys.executable, "-c", code], "cwd": str(tmp_path), "inputs": list(inputs),
            "outputs": list(outputs), "timeout_s": timeout_s, "env": None, "stdout": stdout}


def test_success_records_size_and_sha256(tmp_path):
    (tmp_path / "in.txt").write_text("abc")
    o = run_extcmd(_params(tmp_path, "open('out.txt','w').write(open('in.txt').read().upper())",
                           ["in.txt"], ["out.txt"]))
    assert o.error is None and o.exit_status == 0 and not o.timed_out and o.wall_time > 0
    assert o.outputs == {"out.txt": {"bytes": 3, "sha256": hashlib.sha256(b"ABC").hexdigest()}}


def test_nonzero_exit_is_an_error_with_stderr_tail(tmp_path):
    o = run_extcmd(_params(tmp_path, "import sys; sys.stderr.write('boom'); sys.exit(3)"))
    assert o.exit_status == 3 and "exit status 3" in o.error and "boom" in o.error and o.outputs is None


def test_missing_declared_output_fails_even_with_exit_zero(tmp_path):
    o = run_extcmd(_params(tmp_path, "pass", outputs=["nope.txt"]))
    assert o.exit_status == 0 and "missing" in o.error and "nope.txt" in o.error and o.outputs is None


def test_missing_declared_input_fails_before_starting(tmp_path):
    o = run_extcmd(_params(tmp_path, "open('ran','w')", inputs=["absent.txt"]))
    assert "missing declared input" in o.error and not (tmp_path / "ran").exists()


def test_unstartable_program_and_stdout_redirect(tmp_path):
    p = _params(tmp_path, "print('hi')", outputs=["so.txt"], stdout="so.txt")
    assert run_extcmd(p).outputs["so.txt"]["bytes"] > 0
    p["argv"] = ["no_such_program_xyz"]
    assert "cannot start" in run_extcmd(p).error


def test_timeout_kills_the_whole_process_tree(tmp_path):
    code = ("import subprocess, sys, time\n"
            "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
            "open('child.pid', 'w').write(str(c.pid))\n"
            "time.sleep(120)")
    t0 = time.perf_counter()
    o = run_extcmd(_params(tmp_path, code, timeout_s=6))
    assert o.timed_out and "timeout" in o.error and time.perf_counter() - t0 < 30
    pid = int((tmp_path / "child.pid").read_text())
    deadline = time.monotonic() + 5
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not psutil.pid_exists(pid), "grandchild survived the timeout"


def test_kill_tree_never_raises_when_a_process_cannot_be_killed(monkeypatch):
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        def denied(self):
            raise psutil.AccessDenied(self.pid)

        with monkeypatch.context() as m:
            m.setattr(psutil.Process, "kill", denied)
            kill_tree(p.pid)  # must return, not raise
        assert p.poll() is None  # the kill really was denied
        kill_tree(p.pid)
        p.wait(timeout=10)
        kill_tree(p.pid)  # already gone: still no error
    finally:
        if p.poll() is None:
            p.kill()


@pytest.mark.parametrize("bad", [None, 0, -1.0])
def test_make_extcmd_task_requires_a_positive_timeout(tmp_path, bad):
    with pytest.raises(ValueError, match="timeout_s"):
        make_extcmd_task("t", ["prog"], tmp_path, timeout_s=bad)


def test_make_extcmd_task_sizes_and_defaults(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 10)
    t = make_extcmd_task("t", ["prog", "a.bin"], tmp_path, ["a.bin"], ["b.bin"], timeout_s=5)
    assert t.workload == "extcmd" and t.input_bytes == 10 and t.timeout_s == 5
    assert t.params["transformation"] == "prog" and t.size == 1


def test_prepare_workdir_cleans_only_its_own_directories(tmp_path):
    w = prepare_workdir(tmp_path / "w")
    (w / "junk.txt").write_text("old run")
    w2 = prepare_workdir(w)  # rerun: clean directory again
    assert w2 == w and sorted(p.name for p in w.iterdir()) == [".caosched_workdir"]
    ro = w / "ro.txt"  # a read-only tool output must not make the rerun fail
    ro.write_text("x")
    ro.chmod(stat.S_IREAD)
    assert prepare_workdir(w) == w and not ro.exists()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "precious.txt").write_text("keep")
    with pytest.raises(ValueError, match="refusing"):
        prepare_workdir(foreign)
    assert (foreign / "precious.txt").exists()


def test_chain_through_coordinator_logs_hashes_and_input_sizes(tmp_path):
    w = prepare_workdir(tmp_path / "w")
    a = make_extcmd_task("a", [sys.executable, "-c", "open('a.txt','w').write('x'*100)"], w, outputs=["a.txt"])
    b = make_extcmd_task("b", [sys.executable, "-c", "open('b.txt','w').write(open('a.txt').read()*2)"], w,
                         ["a.txt"], ["b.txt"], ["a"])
    dag = DAG({"a": a, "b": b})
    with WorkerPool(p_core_slots=[], e_core_slots=[0, 1], warmup=False) as pool, \
            EventLogger("x", output_dir=tmp_path) as log:
        s = Coordinator(dag, pool, FirstIdleScheduler(), log).run(run_timeout=60)
    assert s.status == "completed" and s.task_status == {"a": "done", "b": "done"}
    done = {e["task_id"]: e for e in read_events(log.path) if e["event"] == "task_completed"}
    assert done["b"]["outputs"]["b.txt"] == {"bytes": 200, "sha256": hashlib.sha256(b"x" * 200).hexdigest()}
    assert done["b"]["input_bytes"] == 100 and b.input_bytes == 100 and b.output_bytes == 200
    assert done["a"]["exit_status"] == 0


def test_nonzero_exit_through_coordinator_fails_the_run_with_a_defined_status(tmp_path):
    w = prepare_workdir(tmp_path / "w")
    bad = make_extcmd_task("bad", [sys.executable, "-c", "raise SystemExit(7)"], w)
    after = make_extcmd_task("after", [sys.executable, "-c", "pass"], w, dependencies=["bad"])
    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False) as pool, \
            EventLogger("x", output_dir=tmp_path) as log:
        c = Coordinator(DAG({"bad": bad, "after": after}), pool, FirstIdleScheduler(), log)
        with pytest.raises(TaskFailedError, match="exit status 7"):
            c.run(run_timeout=60)
    fin = read_events(log.path)[-1]
    assert fin["status"] == "failed" and fin["failure_reason"] == "task_failed"
    assert fin["task_status"] == {"bad": "failed", "after": "not_run"}
