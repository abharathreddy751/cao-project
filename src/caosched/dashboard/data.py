"""Read-only data layer for the demonstration dashboard.

Everything shown by the dashboard comes from files the project already
writes: event logs (``data/events``), run artifacts (``data/artifacts``),
the accepted-session results of the Phase B analysis
(``data/results/phaseB_appdemo_sweep_20261004``), the hardware status table in
``docs/REMOTE_DEVICES.md``, and live dashboard runs (``data/dashboard_runs``).
Nothing here writes to those locations; no result value is hard-coded.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np

from caosched.core.event_log import read_events

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
EVENTS = DATA / "events"
RESULTS = DATA / "results"
EXPERIMENTS = DATA / "experiments"
EXTRA_ROOTS: list[Path] = []  # extra experiment output dirs (python -m caosched.dashboard --events-dir ...)
DASH_RUNS = DATA / "dashboard_runs"
PHASE_B_SUMMARY = RESULTS / "phaseB_appdemo_sweep_20261004" / "supplementary_summary.json"
REMOTE_DOC = ROOT / "docs" / "REMOTE_DEVICES.md"
B4, EFT = "B4_greedy_eligible_R", "EFT_E1_rc_R"
STAGE_ORDER = ("img_source", "img_tile", "img_denoise", "img_edges", "img_features", "img_mosaic",
               "img_aggregate", "img_package")
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


class NotFound(Exception):
    pass


def safe_name(name: str) -> str:
    """Reject anything that is not a plain file/dir name (no separators, no '..')."""
    if not isinstance(name, str) or not _NAME.match(name) or name in (".", ".."):
        raise NotFound(f"invalid name: {name!r}")
    return name


def _inside(path: Path, base: Path) -> Path:
    p = path.resolve()
    if not p.is_relative_to(base.resolve()):
        raise NotFound("path outside the allowed data directory")
    return p


# ---------------------------------------------------------------- sessions ---

def accepted_sessions() -> list[dict]:
    """The four accepted workload-intensity sessions, as recorded by the
    verified Phase B analysis, with each session's demo runs from runs.csv."""
    summary = json.loads(PHASE_B_SUMMARY.read_text(encoding="utf-8"))
    out = []
    for k, session in sorted(summary["accepted_sessions"].items(), key=lambda kv: int(kv[0])):
        rows = list(csv.DictReader(open(RESULTS / f"{session}_runs.csv", encoding="utf-8")))
        manifest = json.loads((RESULTS / f"{session}_manifest.json").read_text(encoding="utf-8"))
        out.append({
            "k": int(k), "session": session, "link": manifest["link"]["name"],
            "node_core": manifest["args"]["node_core"], "remote_stages": manifest["remote_stages"],
            "profile": manifest["profile"],
            "runs": [{"run": Path(r["event_log"]).stem, "policy": r["policy"], "repeat": int(r["repeat"]),
                      "order_index": int(r["order_index"]), "makespan_ms": float(r["makespan_s"]) * 1e3,
                      "tasks_R": int(r["tasks_R"]), "output_match": r["output_match"],
                      "output_sha256": r["output_sha256"]} for r in rows]})
    return out


def session_log(session: str, run: str) -> Path:
    """Event log of an accepted session's run, or of a live dashboard run."""
    session, run = safe_name(session), safe_name(run)
    if session.startswith("live_"):
        base = DASH_RUNS
        path = DASH_RUNS / session / "events" / f"{run}.jsonl"
    else:
        if session not in {s["session"] for s in accepted_sessions()}:
            raise NotFound(f"{session} is not an accepted session")
        base = EVENTS
        path = EVENTS / session / f"{run}.jsonl"
    path = _inside(path, base)
    if not path.exists():
        raise NotFound(f"no event log {session}/{run}")
    return path


# --------------------------------------------------------------- run view ---

def _read_partial(log: Path) -> list[dict]:
    """Events of a log that may still be being written: stop at a partial last line."""
    ev = []
    for line in Path(log).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ev.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return ev


def run_view(log: Path) -> dict:
    """Everything the workflow screen needs about one run, straight from its
    event log. Works on a log that is still being written (live run)."""
    ev = _read_partial(log)
    if not ev or ev[0]["event"] != "run_started":
        return {"started": False}
    start = ev[0]
    t0 = start["t"]

    def rel(t):  # ms since run start
        return None if t is None else (t - t0) * 1e3

    # extcmd tasks (real Montage): the stage is the transformation name, e.g. "mProject"
    tasks = {tid: {"id": tid, "stage": (spec.get("params") or {}).get("transformation", spec["workload"])
                   if spec["workload"] == "extcmd" else spec["workload"], "deps": [], "eligible": spec.get("eligible_pools"),
                   "state": "pending"} for tid, spec in start["tasks"].items()}
    for a, b in start.get("edges") or []:
        tasks[b]["deps"].append(a)
    workers, finished = [], None
    for e in ev:
        kind, tid = e["event"], e.get("task_id")
        if kind == "worker_ready":
            workers.append({"id": e["worker_id"], "pool": e["pool"], "lp": (e.get("actual_affinity") or [None])[0],
                            "affinity_ok": e.get("affinity_ok"), "capabilities": e.get("capabilities")})
        elif kind == "task_ready":
            tasks[tid].update(state="ready", t_ready=rel(e["t"]))
        elif kind == "task_dispatched":
            t = tasks[tid]
            t.update(state="dispatched", t_dispatched=rel(e["t"]), worker=e["worker_id"], pool=e["pool"],
                     queue_wait_ms=None if e.get("queue_wait_seconds") is None else e["queue_wait_seconds"] * 1e3,
                     decision_us=None if e.get("decision_time_s") is None else e["decision_time_s"] * 1e6)
            dec = e.get("decision")
            if dec and dec.get("candidates"):
                t["candidates"] = [{"worker": w, "wait_ms": c["wait"] * 1e3, "transfer_ms": (c.get("transfer") or 0) * 1e3,
                                    "exec_ms": c["exec"] * 1e3, "finish_ms": c["finish"] * 1e3}
                                   for w, c in sorted(dec["candidates"].items(), key=lambda kv: kv[1]["finish"])]
        elif kind == "task_submitted":
            tasks[tid].update(state="running", t_submitted=rel(e["t"]))
        elif kind == "task_completed":
            tasks[tid].update(state="completed", t_started=rel(e["t_started"]), t_completed=rel(e["t_completed"]),
                              t_done_event=rel(e["t"]), kernel_ms=e["wall_time_seconds"] * 1e3,
                              io_ms=None if e.get("io_s") is None else e["io_s"] * 1e3,
                              transfer_ms=None if e.get("transfer_s") is None else e["transfer_s"] * 1e3,
                              payload_bytes=e.get("payload_bytes"), output_bytes=e.get("output_bytes"),
                              outputs=e.get("outputs"), exit_status=e.get("exit_status"))
        elif kind == "task_failed":
            tasks[tid].update(state="failed", error=e.get("error"))
        elif kind == "run_finished":
            finished = e
    critical = []
    if finished and all(t["state"] == "completed" for t in tasks.values()):
        # observed binding chain: from the last task, repeatedly step to the latest-finishing dependency
        cur = max(tasks.values(), key=lambda t: t["t_completed"])["id"]
        while cur:
            critical.append(cur)
            deps = tasks[cur]["deps"]
            cur = max(deps, key=lambda d: tasks[d]["t_completed"]) if deps else None
        critical.reverse()
    meta = start.get("metadata") or {}
    sc = start.get("scheduler_config") or {}
    est = sc.get("estimator") if isinstance(sc.get("estimator"), dict) else None
    mem = start.get("memory_available_bytes")
    return {
        "started": True, "run_id": start["run_id"], "scheduler": start["scheduler"],
        "estimator": est and est.get("name"), "estimator_source": est and (est.get("base") or {}).get("source"),
        "binds_only_idle": sc.get("binds_only_idle"), "metadata": meta,
        "link": ((sc.get("transfer") or {}).get("links") or {}).get("R"),
        "memory_available_gib": None if mem is None else mem / 2**30,
        "software": start.get("software"), "n_tasks": start["n_tasks"],
        "workers": workers, "tasks": sorted(tasks.values(), key=lambda t: (STAGE_ORDER.index(t["stage"]) if t["stage"] in STAGE_ORDER
                                                       else len(STAGE_ORDER), _idx(t["id"]), t["id"])),
        "extcmd": any(sp["workload"] == "extcmd" for sp in start["tasks"].values()),
        "critical_path": critical,
        "finished": None if finished is None else {
            "status": finished["status"], "makespan_ms": (finished.get("makespan_seconds") or 0) * 1e3,
            "tasks_per_pool": finished.get("tasks_per_pool"),
            "total_kernel_ms": finished.get("total_wall_time_seconds", 0) * 1e3,
            "scheduling_ms": finished.get("scheduling_time_seconds", 0) * 1e3},
        "now_ms": rel(ev[-1]["t"]), "artifact_dir": start.get("artifact_dir"),
    }


def _idx(tid: str) -> int:
    tail = tid.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else -1


# --------------------------------------------------------------- artifacts ---

def artifact_png(log: Path, which: str, max_side: int = 512) -> bytes:
    """PNG of a run's real artifact: ``source`` (input scene) or ``mosaic``
    (edge map unpacked from the final package)."""
    from PIL import Image

    from caosched.apps.image_pipeline import unpack_package

    ev = _read_partial(log)
    if not ev or ev[0]["event"] != "run_started":
        raise NotFound("run has no artifacts yet")
    art = _inside(Path(ev[0]["artifact_dir"]), DATA)
    if which == "source":
        p = art / "source.bin"
        if not p.exists():
            raise NotFound("source artifact not written yet")
        img = Image.fromarray(np.load(io.BytesIO(p.read_bytes()), allow_pickle=False))
    elif which == "mosaic":
        p = art / "package.bin"
        if not p.exists():
            raise NotFound("final package not written yet")
        mosaic, _ = unpack_package(p.read_bytes())
        # display only: thin edges on black vanish when downscaled, so stretch
        # contrast to the 99.5th percentile (the artifact itself is not modified)
        hi = float(np.percentile(mosaic, 99.5)) or 1.0
        img = Image.fromarray(np.clip(mosaic.astype(np.float32) * (255.0 / hi), 0, 255).astype(np.uint8))
    else:
        raise NotFound(f"unknown artifact {which!r}")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# -------------------------------------------------------------- comparison ---

def comparison() -> dict:
    """B4 vs EFT_E1_rc per workload level, from the verified Phase B summary."""
    summary = json.loads(PHASE_B_SUMMARY.read_text(encoding="utf-8"))

    def m(d):
        return {"mean": d["mean"], "sd": d.get("sd"), "ci": d.get("ci95"), "n": d["n"]}

    levels = []
    for s in summary["sessions"]:
        pol, pair, tvc = s["policies"], s["paired_eft_minus_b4"], s["transfer_vs_compute"]
        levels.append({
            "k": s["k"], "session": s["session"], "verification": s["verification"],
            "policy": {p: {"makespan_ms": m(pol[p]["makespan_ms"]), "decision_us": m(pol[p]["decision_latency_us"]),
                           "scheduling_ms": m(pol[p]["scheduling_per_run_ms"]),
                           "tasks_per_run": {q: pol[p]["tasks_per_pool_per_run"][q]["mean"] for q in "PER"},
                           "remote_total": pol[p]["remote_tasks_total"],
                           "placement": pol[p]["placement_total"]} for p in (B4, EFT)},
            "diff_ms": m(pair["makespan_ms"]), "pairs_eft_slower": pair["makespan_ms"]["n_pairs_eft_higher"],
            "pct": {"mean": pair["makespan_pct_t"]["effect_pct"], "ci": pair["makespan_pct_t"]["ci95_pct"],
                    "method": pair["makespan_pct_t"]["method"],
                    "boot_ci": [pair["makespan_pct_bootstrap"]["ci_lo_pct"], pair["makespan_pct_bootstrap"]["ci_hi_pct"]]},
            "stages": {st: {"kernel_ms": {q: tvc[st][f"{q}_kernel_ms"].get("mean") for q in "PER"},
                            "io_ms": {q: tvc[st][f"{q}_io_ms"].get("mean") for q in "PER"},
                            "transfer_ms": m(tvc[st]["R_transfer_ms"]) if tvc[st]["R_transfer_ms"].get("n") else None,
                            "remote_minus_E_ms": m(tvc[st]["remote_path_minus_E_local_ms"])
                            if tvc[st]["remote_path_minus_E_local_ms"].get("n") else None,
                            "kernel_over_transfer": tvc[st]["E_kernel_over_R_transfer"]} for st in tvc}})
    return {"source": str(PHASE_B_SUMMARY.relative_to(ROOT)), "methods": summary["methods"],
            "excluded": summary["excluded_sessions_not_used"], "levels": levels}


# ---------------------------------------------------------------- hardware ---

def hardware_status() -> dict:
    """The status table of docs/REMOTE_DEVICES.md, parsed at request time."""
    text = REMOTE_DOC.read_text(encoding="utf-8")
    heading = next((ln[3:].strip() for ln in text.splitlines() if ln.startswith("## Status")), None)
    rows, in_table = [], False
    for ln in text.splitlines():
        if ln.startswith("| item"):
            in_table = True
            continue
        if in_table:
            if not ln.startswith("|"):
                break
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if set(cells[0]) <= set("-: "):
                continue
            rows.append(dict(zip(("item", "implemented", "executed", "verified", "notes"), cells)))
    return {"source": str(REMOTE_DOC.relative_to(ROOT)), "heading": heading, "rows": rows}


# ------------------------------------------------------------------ system ---

def system_snapshot() -> dict:
    import psutil

    from caosched.core.runtime_config import RuntimeConfig

    try:
        rc = RuntimeConfig.from_topology().to_dict()
        topo_error = None
    except Exception as exc:  # noqa: BLE001 - shown on the dashboard, not hidden
        rc, topo_error = None, str(exc)
    vm = psutil.virtual_memory()
    return {"topology": rc, "topology_error": topo_error,
            "cpu_percent": psutil.cpu_percent(percpu=True, interval=None),
            "logical_processors": psutil.cpu_count(logical=True), "physical_cores": psutil.cpu_count(logical=False),
            "memory_total_gib": vm.total / 2**30, "memory_available_gib": vm.available / 2**30}


def live_runs() -> list[dict]:
    """Live dashboard runs on disk (newest first), with their recorded status."""
    out = []
    if DASH_RUNS.exists():
        for d in sorted(DASH_RUNS.glob("live_*"), reverse=True):
            st = d / "status.json"
            info = json.loads(st.read_text(encoding="utf-8")) if st.exists() else {"state": "unknown"}
            info["session"] = d.name
            out.append(info)
    return out


# ------------------------------------------------- Montage / GPU workload ---

def _manifest_paths() -> list[tuple[Path, Path]]:
    """(scan root, run_manifest.json) for the experiment runner's output (``<session>/runs/<run>/``) and any
    ``results/*manifest.json`` of the same shape; other manifests are skipped by ``_run_entry``."""
    found = [(EXPERIMENTS, p) for p in sorted(EXPERIMENTS.glob("*/runs/*/run_manifest.json"))]
    found += [(RESULTS, p) for p in sorted(RESULTS.glob("*/runs/*/run_manifest.json")) + sorted(RESULTS.glob("*manifest.json"))]
    for root in EXTRA_ROOTS:
        found += [(root, p) for pat in ("*/runs/*/run_manifest.json", "runs/*/run_manifest.json") for p in sorted(root.glob(pat))]
    return found


def _run_entry(m: dict) -> dict | None:
    if not isinstance(m, dict) or "condition" not in m or "run_id" not in m:
        return None
    c, ex, ver = m["condition"], m.get("extra") or {}, m.get("verification") or {}
    mk = ex.get("makespan_seconds")
    return {"id": m["run_id"], "session": m.get("session_id"), "instance": m.get("instance"), "condition": c.get("name"),
            "policy": m.get("policy"), "estimator": c.get("estimator"), "block": m.get("block"), "seed": m.get("seed"),
            "kind": (c.get("workload") or {}).get("kind") or "montage",  # shortcut: no kind recorded -> assume Montage
            "warmup": m.get("warmup"), "status": m.get("status"), "evidence_label": m.get("evidence_label"),
            "makespan_ms": None if mk is None else mk * 1e3, "n_tasks": ex.get("n_tasks"),
            "output_ok": ver.get("passed"), "has_log": bool(m.get("event_log"))}


def _load_runs() -> dict[str, tuple[dict, Path, Path]]:
    out: dict[str, tuple[dict, Path, Path]] = {}
    for root, p in _manifest_paths():
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _run_entry(m):
            out.setdefault(m["run_id"], (m, p, root))
    return out


def montage_runs() -> list[dict]:
    """Experiment runs found on disk (Montage and GPU), from their run manifests."""
    return [e for m, _, _ in _load_runs().values() if (e := _run_entry(m))]


def _stage_summary(v: dict) -> dict:
    """Per-transformation totals and the transformation-level DAG (level = longest path from a root)."""
    by = {t["id"]: t for t in v["tasks"]}
    lvl: dict[str, int] = {}

    def level(i):  # shortcut: recursion depth = DAG depth; fine for workflows of ~10 levels
        if i not in lvl:
            lvl[i] = 1 + max((level(d) for d in by[i]["deps"]), default=-1)
        return lvl[i]
    agg: dict[str, dict] = {}
    edges: dict[tuple[str, str], int] = {}
    for t in v["tasks"]:
        a = agg.setdefault(t["stage"], {"stage": t["stage"], "level": level(t["id"]), "n": 0, "kernel_ms": 0.0,
                                        "queue_wait_ms": 0.0, "pools": {}})
        a["level"] = min(a["level"], level(t["id"]))
        a["n"] += 1
        a["kernel_ms"] += t.get("kernel_ms") or 0.0
        a["queue_wait_ms"] += t.get("queue_wait_ms") or 0.0
        if t.get("pool"):
            a["pools"][t["pool"]] = a["pools"].get(t["pool"], 0) + 1
        for d in t["deps"]:
            k = (by[d]["stage"], t["stage"])
            edges[k] = edges.get(k, 0) + 1
    return {"stages": sorted(agg.values(), key=lambda a: (a["level"], a["stage"])),
            "edges": [{"from": a, "to": b, "n": n} for (a, b), n in sorted(edges.items())]}


def montage_run(run_id: str) -> dict:
    """One experiment run: manifest summary + run view from its event log + output-hash verdicts."""
    found = _load_runs().get(run_id)
    if not found:
        raise NotFound(f"no run {run_id!r}")
    m, mp, root = found
    el = m.get("event_log")
    if not el:
        raise NotFound(f"run {run_id!r} has no event log (status {m.get('status')}: {m.get('error')})")
    log = _inside(mp.parent / el["path"], root)
    if not log.is_file():
        raise NotFound(f"event log of {run_id!r} is missing")
    v = run_view(log)
    ver, ex = m.get("verification") or {}, m.get("extra") or {}
    return {"run": _run_entry(m), "view": v, "error": m.get("error"),
            "verification": {"passed": ver.get("passed"), "output_hashes": ver.get("output_hashes"),
                             "verdict": ex.get("output_verdict"),
                             "log_sha256_ok": hashlib.sha256(log.read_bytes()).hexdigest() == el.get("sha256")},
            **(_stage_summary(v) if v["started"] else {"stages": [], "edges": []})}


def gpu_spike() -> dict:
    """Per-stage CPU-vs-CUDA timing and equivalence verdicts of the newest gpu_spike.json under data/results."""
    cands = sorted({*RESULTS.glob("*/gpu/gpu_spike.json"), *RESULTS.glob("*/gpu/*/gpu_spike.json")},
                   key=lambda p: p.stat().st_mtime)
    if not cands:
        raise NotFound("no gpu_spike.json under data/results")
    d = json.loads(cands[-1].read_text(encoding="utf-8"))

    def ms(r, k):
        return None if r.get(k) is None else r[k] * 1e3
    return {"source": str(cands[-1].relative_to(ROOT)), "env": d.get("env"),
            "rows": [{"stage": r["stage"], "params": r.get("params"), "side": r.get("side"), "reps": r.get("reps"),
                      "cpu_ms": ms(r, "cpu_median_s"), "gpu_ms": ms(r, "gpu_median_s"), "speedup": r.get("speedup"),
                      "equivalent": r.get("equivalent"), "max_abs": r.get("max_abs"), "verdict": r.get("verdict")}
                     for r in d["rows"]]}
