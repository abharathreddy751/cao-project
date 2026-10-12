"""Session runner: memory preflight, environment manifest, interleaved blocks, per-run manifests.

Layout (nothing is ever overwritten; every directory/file is created exclusively)::

    <out>/<session_id>/design.<ext>  design.sha256  environment.json  preflight.jsonl  session.json
    <out>/<session_id>/runs/bNNNN_PP_<cond>/<event log>  run_manifest.json

Failed / timed-out / unverified runs are kept and flagged; exclusion happens only in the analysis, by the
rule in the design file. A preflight failure (free RAM below ``min_free_ram_gb``) aborts the session
cleanly: ``session.json`` records status 'aborted' and the reason.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

from caosched.experiment.design import RunRecord, load_design, plan_blocks
from caosched.experiment.manifest import sha256_file
from caosched.util.provenance import software_info

_PKGS = ("numpy", "pandas", "psutil", "matplotlib", "scipy", "PyYAML", "torch", "catboost", "scikit-learn")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jhash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def free_ram_gb() -> float:
    import psutil
    return psutil.virtual_memory().available / 2**30


def _cmd(*args) -> str | None:
    """stdout of the command ('' if it printed nothing); None if it could not run or exited non-zero."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
    except Exception:  # noqa: BLE001 - best effort
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _git_info() -> dict:
    """Commit + dirty flag; 'unavailable' (never commit null / dirty False) when git cannot answer."""
    commit, status = _cmd("git", "rev-parse", "HEAD"), _cmd("git", "status", "--porcelain")
    if not commit or status is None:
        return {"commit": "unavailable", "dirty": "unavailable"}
    return {"commit": commit, "dirty": bool(status)}


def environment_manifest() -> dict:
    """Machine + software record; ``machine_id`` (hardware/OS) and ``environment_hash`` (also python/packages)."""
    try:
        from caosched.phase0.env_record import build_environment_record
        base = build_environment_record()
    except Exception as exc:  # noqa: BLE001
        base = {"error": f"{type(exc).__name__}: {exc}"}
    gpu = (_cmd("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader") or None) if shutil.which("nvidia-smi") else None
    pkgs = {}
    for p in _PKGS:
        try:
            pkgs[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            pass
    machine = {"cpu": (base.get("wmi_cross_check") or {}).get("name"), "topology": base.get("topology"),
               "ram_bytes_total": base.get("ram_bytes_total"), "os": base.get("os"), "gpu": gpu}
    env = {"generated_at_utc": _now(), "base": base, "gpu": gpu, "packages": pkgs,
           "git": _git_info(),
           "software": software_info(), "machine": machine, "machine_id": _jhash(machine)}
    env["environment_hash"] = _jhash({"machine": machine, "python": (base.get("python") or {}).get("version"), "pkgs": pkgs})
    return env


def _preflight(sdir: Path, where: str, threshold: float, free_fn) -> bool:
    free = free_fn()
    ok = free >= threshold
    with (sdir / "preflight.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": _now(), "where": where, "free_gb": free, "threshold_gb": threshold, "ok": ok}) + "\n")
    return ok


def _child(q, adapter, cond, workdir, seed) -> None:
    q.put(("started", None))
    try:
        q.put(("ok", adapter.run_one(cond, workdir, seed)))
    except Exception as exc:  # noqa: BLE001 - re-raised in the parent, which records a failed run
        q.put(("err", f"{type(exc).__name__}: {exc}"))


def _kill_tree(p) -> None:
    import psutil
    try:
        root = psutil.Process(p.pid)
        procs = root.children(recursive=True) + [root]
    except psutil.NoSuchProcess:
        return
    for x in procs:
        try:
            x.kill()
        except psutil.NoSuchProcess:
            pass


def _run_isolated(adapter, cond, workdir, seed, timeout: float) -> RunRecord:
    """``adapter.run_one`` in a spawned child process; killed (with its children) after ``timeout`` seconds,
    counted from the moment the child starts running the adapter (spawn/import time excluded)."""
    import multiprocessing
    import queue
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_child, args=(q, adapter, cond, workdir, seed))
    p.start()
    deadline = None
    try:
        while True:
            try:
                kind, val = q.get(timeout=0.2)
            except queue.Empty:
                if deadline is not None and time.monotonic() > deadline:
                    return RunRecord(status="timeout", error=f"exceeded run_timeout_s={timeout}")
                if p.is_alive():
                    continue
                try:  # exited: take a result that was queued just before it exited
                    kind, val = q.get(timeout=1)
                except queue.Empty:
                    raise RuntimeError(f"run process exited (code {p.exitcode}) without a result") from None
            if kind == "started":
                deadline = time.monotonic() + timeout
            elif kind == "err":
                raise RuntimeError(val)
            else:
                return val
    finally:
        if p.is_alive():
            _kill_tree(p)
        p.join(10)


def run_session(design_path, out_root, adapter, *, session_id: str | None = None, free_fn=free_ram_gb,
                env: dict | None = None) -> dict:
    """Run the whole design; returns the final session.json dict. Refuses an existing session dir.

    ``session.json`` is always written: 'complete', 'aborted' (preflight) or 'crashed' (any exception /
    interrupt escaped the runner; the exception still propagates). The analysis only accepts 'complete'
    sessions with every block done.

    Optional design field ``run_timeout_s`` (positive number): each ``run_one`` then runs in a spawned child
    process that is killed (with its children) on expiry and recorded as status 'timeout'. Limits: the
    adapter must be picklable and is used in the child, so state it mutates in ``run_one`` is not visible to
    the parent; child start-up (imports) is not counted against the timeout; ``verify`` runs in the parent
    and is not time-limited. Without the field there is NO timeout (a hung run blocks the session): an
    in-process thread cannot be stopped safely and would keep consuming CPU during later timed runs."""
    design = load_design(design_path)
    timeout = design.raw.get("run_timeout_s")
    if timeout is not None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("run_timeout_s must be a positive number")
        import pickle
        pickle.dumps(adapter)  # fail before creating the session, not on every run
    session_id = session_id or datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    sdir = Path(out_root) / session_id
    sdir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(design.path, sdir / f"design{design.path.suffix}")
    (sdir / "design.sha256").write_text(design.sha256 + "\n")
    env = env or environment_manifest()
    (sdir / "environment.json").write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
    label = getattr(adapter, "evidence_label_override", None) or design.evidence_label
    verify = getattr(adapter, "verify", None)
    session = {"session_id": session_id, "design_name": design.name, "design_sha256": design.sha256,
               "evidence_label": label, "machine_id": env["machine_id"], "environment_hash": env["environment_hash"],
               "started_utc": _now(), "status": "running", "reason": None, "n_blocks": design.n_blocks,
               "blocks_completed": 0}
    thr = design.min_free_ram_gb

    def finish(status, reason=None):
        session.update(status=status, reason=reason, finished_utc=_now())
        (sdir / "session.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
        return session

    try:
        if not _preflight(sdir, "session_start", thr, free_fn):
            return finish("aborted", f"free RAM below {thr} GB at session start")
        (sdir / "runs").mkdir()
        for blk in plan_blocks(design):
            if not _preflight(sdir, f"block_{blk['block']}", thr, free_fn):
                return finish("aborted", f"free RAM below {thr} GB before block {blk['block']}")
            for pos, (cond, seed) in enumerate(blk["runs"]):
                name = f"b{blk['block']:04d}_{pos:02d}_{cond.name}"
                workdir = sdir / "runs" / name
                workdir.mkdir()  # exist_ok=False: never reuse a run dir
                t0, wall0 = _now(), time.perf_counter()
                try:
                    rec = (adapter.run_one(cond, workdir, seed) if timeout is None
                           else _run_isolated(adapter, cond, workdir, seed, timeout))
                except Exception as exc:  # noqa: BLE001 - failures are data
                    rec = RunRecord(status="failed", error=f"{type(exc).__name__}: {exc}")
                if rec.status == "ok" and (rec.event_log is None or not (workdir / rec.event_log).is_file()):
                    rec.status, rec.error = "failed", rec.error or "no event log produced"
                ok, hashes = rec.output_ok, dict(rec.output_hashes)
                if rec.status != "ok":
                    ok = False  # a failed / timed-out run never counts as verified
                elif verify is not None:
                    try:
                        ok, hashes = verify(cond, workdir, rec)
                    except Exception as exc:  # noqa: BLE001
                        ok, rec.error = False, f"verify raised {type(exc).__name__}: {exc}"
                log = None
                if rec.event_log and (workdir / rec.event_log).is_file():
                    lp = workdir / rec.event_log
                    log = {"path": rec.event_log, "sha256": sha256_file(lp), "bytes": lp.stat().st_size}
                    os.chmod(lp, 0o444)
                manifest = {
                    "run_id": f"{session_id}__{name}", "session_id": session_id, "block": blk["block"], "position": pos,
                    "instance": blk["instance"], "warmup": blk["warmup"], "seed": seed, "policy": cond.policy,
                    "condition": dataclasses.asdict(cond), "evidence_label": label, "machine_id": env["machine_id"],
                    "environment_hash": env["environment_hash"],
                    "code": {"git_commit": env["git"]["commit"], "git_dirty": env["git"]["dirty"],
                             "git_available": env["git"]["commit"] != "unavailable",
                             "src_sha256": env["software"]["src_sha256"]},
                    "design": {"name": design.name, "sha256": design.sha256, "reference": design.raw.get("reference"),
                               "warmup_blocks": design.warmup_blocks, "run_timeout_s": timeout},
                    "input_hashes": rec.input_hashes, "status": rec.status, "error": rec.error,
                    "verification": {"passed": ok, "output_hashes": hashes}, "event_log": log, "extra": rec.extra,
                    "started_utc": t0, "wall_s": time.perf_counter() - wall0,
                }
                with (workdir / "run_manifest.json").open("x", encoding="utf-8") as fh:
                    json.dump(manifest, fh, indent=2, default=str)
            session["blocks_completed"] += 1
        return finish("complete")
    finally:
        if session["status"] == "running":  # an exception / interrupt escaped: leave an honest record
            escaped = sys.exc_info()[1]
            finish("crashed", f"{type(escaped).__name__}: {escaped}" if escaped else "ended without a final status")
