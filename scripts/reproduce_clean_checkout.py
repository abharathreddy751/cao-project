"""Clean-checkout reproduction test (Stage 4): clone this repo into a NEW empty directory, build a fresh venv from
requirements-lock.txt, run a small pytest subset and the stub-adapter experiment end to end, and write a log.

  python scripts/reproduce_clean_checkout.py --dest D:/tmp/cao_repro [--with-gpu] [--tests tests/test_task.py ...]
         [--montage-subset --data-dir <path of the original data/> [--instance NAME ...]] [--timeout-s 600]

Layout under --dest (must be empty or absent; nothing outside it is written):
  repo/ (git clone --branch <branch> of --source)   venv/   work/ (design, stub session, analysis)
  logs/NN_<step>.txt (full output of each command)   requirements-cpu.txt   repro_log.json (created exclusively)

Steps (each one a subprocess without a shell, with a timeout; a failed step is recorded and its dependants are
recorded as skipped, never dropped): git_clone, required_files_present, clone_is_branch_tip, venv, venv_python_version,
filter_requirements, pip_install_lock, [pip_install_torch_cuda], pip_install_package, import_from_clone, pip_freeze,
pytest_subset, stub_run_experiment, stub_analyze, stub_make_manifest, stub_verify_manifest, stub_reproduce_subset,
[montage_subset_hashes]. Exit code 1 if any step failed or was skipped, 2 on bad arguments.

LIMITS (also written to the log, field 'limits'): only COMMITTED files are cloned; data/ is gitignored (Montage
binaries, instance inputs, raw results), so Montage cannot be re-run in the clone. --montage-subset only HASHES the
original data directory read-only and compares with the SHA-256 lists in the docs and instance.json; nothing is copied.
The stub adapter is synthetic (label 'plan'): it checks the code path, not timings. Standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TESTS = ["tests/test_task.py", "tests/test_stats.py", "tests/test_experiment_design.py",
                 "tests/test_analysis_paired.py"]
# committed files the stub pipeline needs; checked in the clone (untracked files are NOT cloned)
REQUIRED_FILES = ["pyproject.toml", "requirements-lock.txt", "tests/_exp_helpers.py",
                  "scripts/run_experiment.py", "scripts/analyze_experiment.py", "scripts/make_manifest.py",
                  "scripts/reproduce_subset.py", "src/caosched/experiment/design.py", "src/caosched/experiment/stub.py",
                  "src/caosched/experiment/runner.py", "src/caosched/experiment/manifest.py",
                  "src/caosched/analysis/stats_paired.py"]
BIN_MANIFEST_REL = "docs/research_redesign/montage_build/bin_win64_sha256.txt"
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"
TAIL = 2000
DESIGN = {  # tiny pre-registered design for the stub adapter (label forced to 'plan' by the adapter)
    "name": "repro_stub", "evidence_label": "plan", "seed": 20261011, "n_blocks": 8, "warmup_blocks": 1,
    "instances": ["i1", "i2"], "min_free_ram_gb": 0.5, "reference": "A",
    "conditions": [{"name": n, "policy": "pol_" + n} for n in ("A", "B", "C")]}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------- pure helpers
def validate_test_paths(paths: list[str]) -> None:
    """Relative paths inside the clone only (no option injection into pytest, no escape from the clone)."""
    if not paths:
        raise ValueError("--tests needs at least one path")
    for p in paths:
        node = p.split("::", 1)[0]
        if not node or p.startswith("-") or os.path.isabs(node) or ".." in Path(node).parts:
            raise ValueError(f"bad test path {p!r}: must be relative to the repo, no '..', no leading '-'")


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", required=True, help="new empty directory (refused if it has any content)")
    ap.add_argument("--source", default=str(ROOT), help="local repo to clone (default: this checkout)")
    ap.add_argument("--branch", default="redesign/montage")
    ap.add_argument("--tests", nargs="+", default=list(DEFAULT_TESTS), help="pytest targets, relative to the repo")
    ap.add_argument("--with-gpu", action="store_true", help="also install the CUDA torch pinned in the lock file")
    ap.add_argument("--torch-index", default=TORCH_INDEX)
    ap.add_argument("--montage-subset", action="store_true", help="hash-check data/montage (read-only), needs --data-dir")
    ap.add_argument("--data-dir", help="the ORIGINAL data/ directory (never written, never copied)")
    ap.add_argument("--instance", action="append", default=[], help="instance names to hash-check (repeatable)")
    ap.add_argument("--timeout-s", type=float, default=600.0, help="per step")
    ap.add_argument("--install-timeout-s", type=float, default=3600.0, help="per pip step")
    a = ap.parse_args(argv)
    if a.timeout_s <= 0 or a.install_timeout_s <= 0:
        ap.error("timeouts must be > 0")
    if not a.branch or a.branch.startswith("-"):
        ap.error("bad --branch")
    if not (Path(a.source) / ".git").exists():
        ap.error(f"--source {a.source} is not a git checkout")
    if a.montage_subset and not (a.data_dir and Path(a.data_dir).is_dir()):
        ap.error("--montage-subset needs --data-dir pointing at an existing directory")
    if (a.data_dir or a.instance) and not a.montage_subset:
        ap.error("--data-dir/--instance only make sense with --montage-subset")
    for n in a.instance:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", n) or n in (".", ".."):
            ap.error(f"bad --instance name {n!r}")
    try:
        validate_test_paths(a.tests)
    except ValueError as exc:
        ap.error(str(exc))
    return a


def prepare_dest(dest: Path, source: Path, data_dir: Path | None = None) -> Path:
    """Create/accept a NEW empty directory. Raises ValueError otherwise (never deletes or reuses anything)."""
    dest, source = Path(dest).resolve(), Path(source).resolve()
    if dest.exists() and not dest.is_dir():
        raise ValueError(f"--dest {dest} exists and is not a directory")
    if dest.is_dir() and any(dest.iterdir()):
        raise ValueError(f"--dest {dest} is not empty: refusing to reuse it")
    for other, what in ((source, "source repo"), (Path(data_dir).resolve() if data_dir else None, "data dir")):
        if other is not None and (dest == other or other in dest.parents or dest in other.parents):
            raise ValueError(f"--dest {dest} overlaps the {what} {other}")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def write_log(path, obj) -> Path:
    """Exclusive create: an existing log is evidence and is never overwritten (FileExistsError)."""
    path = Path(path)
    with path.open("x", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=str)
        fh.write("\n")
    return path


def write_design(path) -> Path:
    path = Path(path)
    with path.open("x", encoding="utf-8") as fh:
        json.dump(DESIGN, fh, indent=2)
    return path


def filter_requirements(text: str, drop: tuple[str, ...] = ("torch",)) -> tuple[str, list[str]]:
    """(text without the dropped packages, the dropped lines). 'torch' must not match 'torchvision'."""
    keep, dropped = [], []
    for line in text.splitlines():
        name = re.split(r"[=<>!~\[;\s]", line.strip(), maxsplit=1)[0].lower()
        (dropped if name in drop else keep).append(line)
    return "\n".join(keep) + "\n", dropped


def venv_python(venv: Path) -> Path:
    return Path(venv) / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def clean_env() -> dict:
    """Environment for the steps: nothing that could make the clone import this checkout's code."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "CAO_MONTAGE_ADAPTER_CONFIG", "VIRTUAL_ENV")}
    env.update(PYTHONNOUSERSITE="1", PYTHONUTF8="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    return env


def _txt(x) -> str:
    return x.decode("utf-8", "replace") if isinstance(x, bytes) else (x or "")


def run_step(name: str, argv, *, cwd, env=None, timeout_s: float = 600.0, log_path=None) -> dict:
    """Run one command (no shell). Always returns a record; failures are data: exit_code, timed_out, error."""
    rec = {"name": name, "argv": [str(a) for a in argv], "cwd": str(cwd), "started_utc": _now(), "exit_code": None,
           "timed_out": False, "error": None, "timeout_s": timeout_s}
    out = err = ""
    t0 = time.perf_counter()
    try:
        r = subprocess.run(rec["argv"], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout_s, stdin=subprocess.DEVNULL)
        rec["exit_code"], out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as exc:
        rec.update(timed_out=True, error=f"timeout after {timeout_s}s")
        out, err = _txt(exc.stdout), _txt(exc.stderr)
    except OSError as exc:  # missing executable, bad cwd ...
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rec["duration_s"] = round(time.perf_counter() - t0, 3)
    rec["ok"] = rec["exit_code"] == 0
    rec["status"] = "ok" if rec["ok"] else ("timeout" if rec["timed_out"] else "failed")
    rec["stdout_tail"], rec["stderr_tail"] = out[-TAIL:], err[-TAIL:]
    if log_path is not None:
        with Path(log_path).open("x", encoding="utf-8") as fh:
            fh.write(f"$ {' '.join(rec['argv'])}\n# cwd {cwd}\n# exit {rec['exit_code']}\n--- stdout ---\n{out}\n--- stderr ---\n{err}\n")
        rec["log_file"] = Path(log_path).name
    return rec


class Steps:
    """Ordered step records with dependency skipping; ``ok`` is False if any step failed or was skipped."""

    def __init__(self, logs_dir=None):
        self.records: list[dict] = []
        self.logs_dir = Path(logs_dir) if logs_dir else None

    def _failed_deps(self, depends) -> list[str]:
        done = {r["name"]: r["ok"] for r in self.records}
        return [d for d in depends if not done.get(d)]

    def _skip(self, name: str, bad: list[str]) -> dict:
        rec = {"name": name, "status": "skipped", "ok": False, "exit_code": None, "duration_s": 0.0,
               "error": f"skipped: prerequisite step(s) not ok: {bad}"}
        self.records.append(rec)
        return rec

    def run(self, name, argv, *, depends=(), **kw) -> dict:
        bad = self._failed_deps(depends)
        if bad:
            return self._skip(name, bad)
        log = self.logs_dir / f"{len(self.records):02d}_{name}.txt" if self.logs_dir else None
        rec = run_step(name, argv, log_path=log, **kw)
        self.records.append(rec)
        return rec

    def call(self, name, fn, *, depends=()) -> dict:
        """In-process step: ``fn() -> (ok, detail)``; an exception is a failed step, not a crash."""
        bad = self._failed_deps(depends)
        if bad:
            return self._skip(name, bad)
        rec = {"name": name, "started_utc": _now(), "exit_code": 0, "error": None}
        t0 = time.perf_counter()
        try:
            ok, rec["detail"] = fn()
            rec["exit_code"] = 0 if ok else 1
        except Exception as exc:  # noqa: BLE001 - recorded
            ok, rec["exit_code"], rec["error"] = False, 1, f"{type(exc).__name__}: {exc}"
        rec.update(duration_s=round(time.perf_counter() - t0, 3), ok=bool(ok), status="ok" if ok else "failed")
        self.records.append(rec)
        return rec

    @property
    def ok(self) -> bool:
        return bool(self.records) and all(r["ok"] for r in self.records)


def git_out(args, cwd) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


# ---------------------------------------------------------------- montage hash check (read-only)
def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:  # read-only
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_sha256sum(text: str) -> dict[str, str]:
    """'<64 hex> *name' lines (sha256sum format) -> {name: digest}."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition(" ")
        name = name.lstrip(" *")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest) or not name:
            raise ValueError(f"bad manifest line {line!r}")
        out[name] = digest.lower()
    return out


def verify_montage_subset(data_dir, bin_manifest_text: str, instances=()) -> tuple[bool, dict]:
    """Compare data/montage/bin_win64/* with the documented SHA-256 list, and for each instance the generated
    workflow and every raw input with the hashes recorded in its instance.json. Only reads."""
    mont = Path(data_dir) / "montage"
    expected = parse_sha256sum(bin_manifest_text)
    missing, changed = [], []
    for name, digest in expected.items():
        p = mont / "bin_win64" / name
        if not p.is_file():
            missing.append(f"bin_win64/{name}")
        elif sha256_file(p) != digest:
            changed.append(f"bin_win64/{name}")
    n_files = len(expected)
    for inst in instances:
        d = mont / "instances" / inst
        try:
            meta = json.loads((d / "instance.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            missing.append(f"instances/{inst}/instance.json ({type(exc).__name__})")
            continue
        items = [("data/montage-workflow.yml", meta.get("workflow_yml_sha256"), None)]
        items += [(f"inputs/{f['lfn']}", f["sha256"], f["bytes"]) for f in meta.get("inputs", [])]
        for rel, digest, size in items:
            n_files += 1
            p = d / rel
            if not p.is_file():
                missing.append(f"instances/{inst}/{rel}")
            elif (size is not None and p.stat().st_size != size) or sha256_file(p) != digest:
                changed.append(f"instances/{inst}/{rel}")
    detail = {"n_expected": n_files, "n_binaries_in_manifest": len(expected), "instances": list(instances),
              "missing": missing[:50], "changed": changed[:50], "n_missing": len(missing), "n_changed": len(changed),
              "note": "extra files in data/ are not checked; instances not named are not checked"}
    return (not missing and not changed and n_files > 0), detail


# ---------------------------------------------------------------- orchestration
def limits(a, dirty: int | None) -> list[str]:
    out = ["Only COMMITTED files are in the clone; data/ is gitignored (Montage binaries, instance inputs, raw results), "
           "so Montage cannot be re-run in the clone and no Montage timing is reproduced by this check.",
           "The stub adapter is synthetic (evidence label 'plan'): it verifies the experiment/analysis/manifest code path "
           "and determinism of the derived tables, not any performance number.",
           f"Only this pytest subset was run, not the full suite: {a.tests}",
           "GPU/CPU timing numbers are machine-specific and are not reproduced here."]
    if dirty:
        out.append(f"The source checkout has {dirty} uncommitted/untracked entries; they are NOT in the clone, so a failure "
                   "of required_files_present or a test import usually means 'commit it first'.")
    if not a.with_gpu:
        out.append("torch (CUDA) was not installed (no --with-gpu): CUDA tests and the GPU spike are not covered.")
    if a.montage_subset:
        out.append("--montage-subset hashed the ORIGINAL data dir read-only; it checks listed binaries and the named "
                   "instances only, and does not re-download inputs.")
    else:
        out.append("--montage-subset not requested: data/montage hashes were not checked.")
    return out


def run_all(a, source: Path, dest: Path, steps: Steps, log: dict) -> None:
    repo, venv, work = dest / "repo", dest / "venv", dest / "work"
    env, to, ito = clean_env(), a.timeout_s, a.install_timeout_s
    work.mkdir()
    tip = git_out(["rev-parse", "--verify", a.branch], source)
    log["source"]["branch_tip"] = tip

    steps.run("git_clone", ["git", "clone", "--branch", a.branch, "--single-branch", str(source), str(repo)],
              cwd=dest, env=env, timeout_s=to)
    if (repo / ".git").exists():
        log["clone"]["commit"] = git_out(["rev-parse", "HEAD"], repo)
        log["clone"]["branch"] = git_out(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    steps.call("required_files_present", lambda: (lambda m: (not m, {"missing": m}))(
        [f for f in [*REQUIRED_FILES, *(t.split("::", 1)[0] for t in a.tests)] if not (repo / f).is_file()]),
        depends=["git_clone"])
    steps.call("clone_is_branch_tip", lambda: (bool(tip) and tip == log["clone"]["commit"],
                                               {"branch_tip": tip, "clone_head": log["clone"]["commit"]}), depends=["git_clone"])

    steps.run("venv", [sys.executable, "-m", "venv", str(venv)], cwd=dest, env=env, timeout_s=to, depends=["git_clone"])
    py = str(venv_python(venv))
    want = "%d.%d" % sys.version_info[:2]
    steps.run("venv_python_version", [py, "-c", f"import sys; sys.exit(0 if '%d.%d' % sys.version_info[:2] == '{want}' else 1)"],
              cwd=dest, env=env, timeout_s=to, depends=["venv"])

    lock_cpu = dest / "requirements-cpu.txt"

    def _filter():
        text, dropped = filter_requirements((repo / "requirements-lock.txt").read_text(encoding="utf-8"))
        with lock_cpu.open("x", encoding="utf-8") as fh:
            fh.write(text)
        log["torch_lines_dropped_from_lock"] = dropped
        return True, {"dropped": dropped, "written": lock_cpu.name}

    steps.call("filter_requirements", _filter, depends=["git_clone"])
    pip = [py, "-m", "pip", "install", "--no-input"]
    steps.run("pip_install_lock", [*pip, "-r", str(lock_cpu)], cwd=dest, env=env, timeout_s=ito,
              depends=["venv_python_version", "filter_requirements"])
    setup = ["pip_install_lock"]
    if a.with_gpu:
        def _torch_argv():
            return [*pip, *(l.strip() for l in log.get("torch_lines_dropped_from_lock", []) if l.strip()),
                    "--index-url", a.torch_index, "--extra-index-url", "https://pypi.org/simple"]
        steps.run("pip_install_torch_cuda", _torch_argv(), cwd=dest, env=env, timeout_s=ito, depends=["pip_install_lock"])
        setup.append("pip_install_torch_cuda")
    steps.run("pip_install_package", [*pip, "--no-deps", "-e", str(repo)], cwd=dest, env=env, timeout_s=ito, depends=setup)
    steps.run("import_from_clone",
              [py, "-c", "import sys, pathlib, caosched; p = pathlib.Path(caosched.__file__).resolve(); print(p); "
                         "sys.exit(0 if pathlib.Path(sys.argv[1]).resolve() in p.parents else 1)", str(repo)],
              cwd=dest, env=env, timeout_s=to, depends=["pip_install_package"])
    steps.run("pip_freeze", [py, "-m", "pip", "freeze"], cwd=dest, env=env, timeout_s=to, depends=["venv_python_version"])

    steps.run("pytest_subset", [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *a.tests], cwd=repo, env=env,
              timeout_s=to, depends=["import_from_clone"])

    design, sess_root, sid, analysis = work / "design.json", work / "experiments", "repro_stub", work / "analysis"
    sess = sess_root / sid
    steps.call("write_design", lambda: (write_design(design) and True, {"design": design.name}), depends=["git_clone"])
    sc = lambda f: str(repo / "scripts" / f)  # noqa: E731
    steps.run("stub_run_experiment", [py, sc("run_experiment.py"), "--design", str(design), "--out", str(sess_root),
                                      "--adapter", "stub", "--session-id", sid],
              cwd=repo, env=env, timeout_s=to, depends=["import_from_clone", "write_design"])
    steps.run("stub_analyze", [py, sc("analyze_experiment.py"), "--sessions", str(sess), "--out", str(analysis),
                               "--reference", "A", "--seed", "0"],
              cwd=repo, env=env, timeout_s=to, depends=["stub_run_experiment"])
    steps.run("stub_make_manifest", [py, sc("make_manifest.py"), str(sess)], cwd=repo, env=env, timeout_s=to,
              depends=["stub_run_experiment"])
    steps.run("stub_verify_manifest", [py, sc("make_manifest.py"), str(sess), "--verify"], cwd=repo, env=env, timeout_s=to,
              depends=["stub_make_manifest"])
    steps.run("stub_reproduce_subset", [py, sc("reproduce_subset.py"), "--analysis-dir", str(analysis),
                                        "--log", str(work / "reproduction_log.json")],
              cwd=repo, env=env, timeout_s=to, depends=["stub_analyze", "stub_verify_manifest"])

    if a.montage_subset:
        steps.call("montage_subset_hashes", lambda: verify_montage_subset(
            a.data_dir, (repo / BIN_MANIFEST_REL).read_text(encoding="utf-8"), a.instance), depends=["git_clone"])


def main(argv=None) -> int:
    a = parse_args(argv)
    source = Path(a.source).resolve()
    try:
        dest = prepare_dest(Path(a.dest), source, Path(a.data_dir) if a.data_dir else None)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    (dest / "logs").mkdir()
    steps = Steps(dest / "logs")
    dirty = git_out(["status", "--porcelain"], source)
    log = {"schema_version": 1, "started_utc": _now(), "dest": str(dest), "label": "software check (stub adapter, no timings)",
           "python": {"version": platform.python_version(), "implementation": platform.python_implementation(),
                      "platform": platform.platform()},
           "args": {k: v for k, v in vars(a).items()},
           "source": {"path": str(source), "branch": a.branch, "dirty_entries": len(dirty.splitlines()) if dirty is not None else None},
           "clone": {"commit": None, "branch": None}, "limits": limits(a, len(dirty.splitlines()) if dirty else 0),
           "crashed": None}
    try:
        run_all(a, source, dest, steps, log)
    except BaseException as exc:  # the partial log is still written below; the exception propagates
        log["crashed"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        log["finished_utc"] = _now()
        log["steps"] = steps.records
        log["ok"] = steps.ok and log["crashed"] is None
        write_log(dest / "repro_log.json", log)
    for r in steps.records:
        print(f"{r['status']:8s} {r['name']:26s} exit={r['exit_code']} {r['duration_s']}s")
    print(f"{'OK' if log['ok'] else 'FAILED'}: {dest / 'repro_log.json'}")
    return 0 if log["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
