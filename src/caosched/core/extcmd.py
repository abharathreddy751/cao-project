"""External-command task (AD-1..AD-3): run a program in a work directory.

A task with ``workload == "extcmd"`` carries ``params``:
  argv        list of str, run without a shell
  cwd         work directory (inputs/outputs below are relative to it)
  inputs      declared input paths; all must exist before the start
  outputs     declared output paths; all must exist after a zero exit
  env         extra environment variables (or None)
  stdout      optional path the program's stdout is written to
  transformation  name used by estimators/reports (e.g. "mProject")
The worker enforces ``Task.timeout_s`` by killing the whole process tree, then
checks the exit status and the declared outputs, and records each output's
size and SHA-256. ``run_extcmd`` never raises: every failure is an outcome.
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from caosched.core.task import Task

EXTCMD = "extcmd"
WORKDIR_MARKER = ".caosched_workdir"


def kill_tree(pid: int) -> None:
    """Kill ``pid`` and all its descendants; never raises. The parent is
    suspended first so it cannot fork while we work, descendants are
    re-enumerated until none new appear (bounded), and the parent dies last so
    it cannot orphan them. Any ``psutil.Error`` on one process (already gone,
    access denied) is skipped, not propagated.
    shortcut: a grandchild already re-parented before the kill is missed; a
    Windows Job Object would close that, upgrade if a tool double-forks."""
    import psutil

    def kill(p) -> None:
        try:
            p.kill()
        except psutil.Error:
            pass

    try:
        root = psutil.Process(pid)
    except psutil.Error:
        return
    try:
        root.suspend()
    except psutil.Error:
        pass
    victims = {pid: root}
    for _ in range(10):
        try:
            fresh = [c for c in root.children(recursive=True) if c.pid not in victims]
        except psutil.Error:
            break
        if not fresh:
            break
        for c in fresh:
            victims[c.pid] = c
            kill(c)
    kill(root)
    psutil.wait_procs(list(victims.values()), timeout=5)


@dataclasses.dataclass
class ExtCmdOutcome:
    wall_time: float | None = None  # process start -> exit (the task's "kernel" time)
    error: str | None = None
    exit_status: int | None = None
    timed_out: bool = False
    outputs: dict | None = None     # {path: {"bytes": n, "sha256": hex}}, only when successful
    io_s: float | None = None       # time spent hashing outputs


def _path(cwd: Path, p: str) -> Path:
    return Path(p) if Path(p).is_absolute() else cwd / p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def declared_input_bytes(params: dict) -> int:
    cwd = Path(params["cwd"])
    return sum(p.stat().st_size for p in (_path(cwd, i) for i in params.get("inputs", ())) if p.is_file())


def run_extcmd(params: dict) -> ExtCmdOutcome:
    """``params["timeout_s"]`` (added by the coordinator from ``Task.timeout_s``) bounds the run."""
    cwd = Path(params["cwd"])
    timeout_s = params.get("timeout_s")
    argv = params.get("argv")
    if not argv or not all(isinstance(a, str) for a in argv):
        return ExtCmdOutcome(error=f"argv must be a non-empty list of str, got {argv!r}")
    missing = [i for i in params.get("inputs", ()) if not _path(cwd, i).is_file()]
    if missing:
        return ExtCmdOutcome(error=f"missing declared input(s): {missing}")
    env = {**os.environ, **{k: str(v) for k, v in (params.get("env") or {}).items()}}
    stdout_path = params.get("stdout")
    with tempfile.TemporaryFile() as err, \
            (_path(cwd, stdout_path).open("wb") if stdout_path else open(os.devnull, "wb")) as out:
        t0 = time.perf_counter()
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        except OSError as exc:
            return ExtCmdOutcome(error=f"cannot start {argv[0]!r} in {str(cwd)!r}: {exc}")
        timed_out = False
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_tree(proc.pid)
            try:
                proc.wait(timeout=10)  # a root that could not be killed must not hang the worker; reported as timeout anyway
            except subprocess.TimeoutExpired:
                pass
        wall = time.perf_counter() - t0
        err.seek(0)
        tail = err.read()[-2000:].decode(errors="replace").strip()
    rc = proc.returncode
    if timed_out:
        return ExtCmdOutcome(wall, f"timeout after {timeout_s}s (process tree killed); stderr: {tail}", rc, True)
    if rc != 0:
        return ExtCmdOutcome(wall, f"exit status {rc}; stderr: {tail}", rc)
    absent = [o for o in params.get("outputs", ()) if not _path(cwd, o).is_file()]
    if absent:
        return ExtCmdOutcome(wall, f"exit status 0 but declared output(s) missing: {absent}", rc)
    t1 = time.perf_counter()
    outputs = {o: {"bytes": _path(cwd, o).stat().st_size, "sha256": _sha256(_path(cwd, o))}
               for o in params.get("outputs", ())}
    return ExtCmdOutcome(wall, None, rc, False, outputs, time.perf_counter() - t1)


def make_extcmd_task(task_id: str, argv, cwd, inputs=(), outputs=(), dependencies=(), timeout_s: float = 600.0,
                     env: dict | None = None, stdout: str | None = None, name: str | None = None,
                     eligible_pools=None, seed: int = 0) -> Task:
    """An extcmd Task. ``timeout_s`` must be a positive number: no task may hang a run forever (AD-3)."""
    if timeout_s is None or timeout_s <= 0:
        raise ValueError(f"extcmd task {task_id!r}: timeout_s must be > 0 (AD-3), got {timeout_s!r}")
    argv =[str(a) for a in argv]
    params = {"argv": argv, "cwd": str(cwd), "inputs": list(inputs), "outputs": list(outputs),
              "env": dict(env) if env else None, "stdout": stdout,
              "transformation": name or Path(argv[0]).stem}
    task = Task(task_id, EXTCMD, 1, seed, tuple(dependencies), params=params, eligible_pools=eligible_pools,
                timeout_s=timeout_s)
    task.input_bytes = declared_input_bytes(params)  # raw inputs only; the coordinator refreshes it at ready time
    return task


def _make_writable_and_retry(func, path, exc_info) -> None:
    """``shutil.rmtree`` error hook: a read-only file (common for tool outputs on Windows) blocks deletion;
    make it writable and retry once, else fail with a clear message."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError as exc:
        raise OSError(f"cannot delete {path} while cleaning the work directory: {exc}") from exc


def prepare_workdir(path) -> Path:
    """A fresh, empty work directory for a (re)run (AD-3). An existing non-empty
    directory is deleted only if an earlier call created it (marker file), so a
    wrong path can never wipe user data."""
    path = Path(path).resolve()
    if path.exists():
        if any(path.iterdir()) and not (path / WORKDIR_MARKER).exists():
            raise ValueError(f"{path} exists, is not empty and is not a caosched work directory; refusing to delete")
        shutil.rmtree(path, onerror=_make_writable_and_retry)
    path.mkdir(parents=True)
    (path / WORKDIR_MARKER).write_text("created by caosched.core.extcmd.prepare_workdir\n")
    return path
