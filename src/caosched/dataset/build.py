"""Unified dataset construction from raw event logs (Phase 6A).

Every row is derived from a real logged task execution; nothing is
synthesised. Raw logs are only read. Each output row carries its provenance
(source log path, experiment/session, run id) and the schema is documented in
docs/DATASET.md.

A run is identified by ``source_log`` (unique); ``run_id`` is the logger's
name and repeats across Phase 5 configurations within one session.

Outputs (``build_dataset``):
  tasks.csv       one row per completed task execution
  candidates.csv  one row per EFT candidate evaluated at a binding decision
  splits.json     leakage-safe split definitions (group-level, never random rows)
  manifest.json   sources (+ sha256), row counts, exclusions with reasons
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import re
from pathlib import Path

from caosched.core.event_log import read_events
from caosched.dataset.events import rows_from_events
from caosched.remote.link import payload_bytes

SCHEMA_VERSION = 1
HARDWARE_ID = "Intel Core i5-1235U (2P with SMT + 8E), 12 LP, 8 GB, Windows 11"

TASK_FIELDS = [
    "row_id", "source_log", "source_kind", "experiment_id", "session_id", "scenario", "run_id", "trace", "repeat",
    "order_index", "order_randomized", "randomized_campaign", "policy", "policy_binding", "estimator", "eft_model",
    "task_id", "workload", "size", "seed", "input_bytes", "output_bytes", "origin", "worker_id", "pool",
    "logical_processor", "timestamp_epoch", "t_ready_rel", "t_dispatched_rel", "t_submitted_rel", "t_started_rel",
    "t_completed_rel", "queue_wait_s", "local_queue_wait_s", "dispatch_to_start_s", "kernel_s", "worker_span_s",
    "setup_s", "transfer_s", "response_time_s", "busy_P", "busy_E", "busy_R", "busy_total", "corun_compression",
    "corun_image_filter", "corun_matmul", "target_busy_frac", "calibration_kernel_s", "calibration_profile",
    "predicted_exec_s", "predicted_wait_s", "predicted_transfer_s", "predicted_finish_s", "pred_margin_s",
    "n_candidates", "link_name", "memory_available_bytes", "software_version", "hardware_id",
]
CAND_FIELDS = ["source_log", "run_id", "session_id", "policy", "estimator", "eft_model", "task_id", "decision_seq",
               "candidate_worker", "candidate_pool", "chosen", "pred_wait_s", "pred_transfer_s", "pred_exec_s",
               "pred_setup_s", "pred_overhead_s", "pred_finish_s"]

_STAMP = re.compile(r"(\d{8}T\d{6})")


def classify(path: Path, events_root: Path) -> tuple[str | None, str | None]:
    """(source_kind, exclusion_reason). Exactly one is non-None."""
    rel = path.relative_to(events_root).as_posix()
    top = rel.split("/")[0]
    if "/" not in rel and top.startswith("phase1_"):
        return None, "Phase 1 log: lifecycle timestamps from time.time() (~1 ms quantized) or pipeline check"
    smoke = {"phase2_20261003T115741": "Phase 2 n=1 smoke run (pipeline check)",
             "phase4_20261003T145622": "Phase 4 n=1 smoke run (pipeline check, superseded regret definition)",
             "phase5_20261003T153046": "Phase 5 n=1 smoke run (pipeline check)",
             "phase6b_20261003T160833": "Phase 6B 3-block smoke run (pipeline check, not a result)"}
    if top in smoke:
        return None, smoke[top]
    for kind in ("campaign", "phase2", "phase4", "phase5", "phase6b"):
        if top.startswith(kind + "_"):
            return kind, None
    return None, "unrecognised source directory"


class CalibrationProfiles:
    """E1 solo-profile medians, taken from the latest profile measured at or
    before the session (so a row's calibration value was available when the
    session ran)."""

    def __init__(self, profile_dir: Path):
        self.profiles = []
        for p in sorted(Path(profile_dir).glob("*_profile.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("metric") != "kernel_wall_time_seconds":
                continue
            table = {(e["workload"], int(e["size"]), e["pool"]): e["median_s"] for e in d["entries"]}
            self.profiles.append((_STAMP.search(p.name).group(1), p.name, table))

    def lookup(self, session_stamp: str, workload: str, size: int, pool: str):
        chosen = None
        for stamp, name, table in self.profiles:
            if stamp <= session_stamp:
                chosen = (name, table)
        if chosen is None and self.profiles:
            chosen = (self.profiles[0][1], self.profiles[0][2])
        if chosen is None:
            return None, None
        name, table = chosen
        return table.get((workload, int(size), pool)), name


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_for_log(path: Path, events_root: Path, kind: str, calib: CalibrationProfiles) -> tuple[list[dict], list[dict]]:
    ev = read_events(path)
    base = rows_from_events(ev)  # completed runs only; decision-time context reconstructed
    if not base:
        return [], []
    start = ev[0]
    meta = start.get("metadata") or {}
    exp_id = meta.get("experiment_id") or path.relative_to(events_root).parts[0]
    session_stamp = _STAMP.search(exp_id).group(1)
    scenario = meta.get("config") or meta.get("condition") or ""
    session_id = exp_id  # each experiment is one contiguous session block
    sc = start.get("scheduler_config") or {}
    est = (sc.get("estimator") or {}).get("name") if isinstance(sc.get("estimator"), dict) else None
    link = meta.get("link") or {}
    lp = {e["worker_id"]: (e.get("actual_affinity") or [None])[0] for e in ev if e["event"] == "worker_ready"}
    pools = {e["worker_id"]: e["pool"] for e in ev if e["event"] == "worker_ready"}
    t0, anchor_e, anchor_p = start["t"], start.get("epoch_anchor"), start.get("perf_anchor")
    by = {}
    for e in ev:
        if e["event"] in ("task_ready", "task_dispatched", "task_submitted", "task_completed"):
            by.setdefault(e["task_id"], {})[e["event"]] = e
    software = (start.get("software") or {}).get("version") or "unrecorded (log predates software field)"
    rel_path = path.relative_to(events_root.parent).as_posix()
    tasks, cands = [], []
    for r in base:
        evs = by[r["task_id"]]
        rd, dp, sb, cp = (evs.get(k) for k in ("task_ready", "task_dispatched", "task_submitted", "task_completed"))
        dec = (dp or {}).get("decision")
        ch = dec["candidates"].get(r["worker_id"]) if dec else None
        fins = sorted(c["finish"] for c in dec["candidates"].values()) if dec else []
        up, down = payload_bytes(r["workload"], r["size"])
        cal, cal_name = calib.lookup(session_stamp, r["workload"], r["size"], r["pool"])
        corun = r["ctx"].corun
        busy_r = sum(1 for o in base if o["worker_id"] != r["worker_id"] and pools.get(o["worker_id"]) == "R"
                     and o["t_started"] <= r["t_started"] < o["t_completed"])
        span = r["t_completed"] - r["t_started"]
        tasks.append({
            "source_log": rel_path, "source_kind": kind, "experiment_id": exp_id, "session_id": session_id,
            "scenario": scenario, "run_id": start["run_id"], "trace": r["trace"], "repeat": meta.get("repeat"),
            "order_index": meta.get("order_index"), "order_randomized": kind in ("phase2", "phase4", "phase5", "phase6b"),
            "randomized_campaign": kind == "campaign", "policy": start["scheduler"],
            "policy_binding": "late" if sc.get("binds_only_idle", True) else "early", "estimator": est,
            "eft_model": dec.get("model", "kernel") if dec else None,
            "task_id": r["task_id"], "workload": r["workload"], "size": r["size"], "seed": r["seed"],
            "input_bytes": up, "output_bytes": down, "origin": "coordinator", "worker_id": r["worker_id"],
            "pool": r["pool"], "logical_processor": lp.get(r["worker_id"]),
            "timestamp_epoch": (anchor_e + (r["t_started"] - anchor_p)) if anchor_e is not None else None,
            "t_ready_rel": rd["t"] - t0 if rd else None, "t_dispatched_rel": dp["t"] - t0 if dp else None,
            "t_submitted_rel": sb["t"] - t0 if sb else None, "t_started_rel": r["t_started"] - t0,
            "t_completed_rel": r["t_completed"] - t0,
            "queue_wait_s": (dp["t"] - rd["t"]) if (rd and dp) else None,
            "local_queue_wait_s": (sb["t"] - dp["t"]) if (sb and dp) else None,
            "dispatch_to_start_s": (r["t_started"] - sb["t"]) if sb else None,
            "kernel_s": r["kernel_s"], "worker_span_s": span, "setup_s": span - r["kernel_s"],
            "transfer_s": (cp or {}).get("transfer_s"), "response_time_s": (cp or {}).get("response_time_seconds"),
            "busy_P": r["ctx"].busy_P, "busy_E": r["ctx"].busy_E, "busy_R": busy_r,
            "busy_total": r["ctx"].busy_total + busy_r,
            "corun_compression": corun.get("compression", 0), "corun_image_filter": corun.get("image_filter", 0),
            "corun_matmul": corun.get("matmul", 0), "target_busy_frac": r["ctx"].target_busy_frac,
            "calibration_kernel_s": cal, "calibration_profile": cal_name,
            "predicted_exec_s": ch["exec"] if ch else None, "predicted_wait_s": ch["wait"] if ch else None,
            "predicted_transfer_s": ch["transfer"] if ch else None, "predicted_finish_s": ch["finish"] if ch else None,
            "pred_margin_s": (fins[1] - fins[0]) if len(fins) > 1 else None,
            "n_candidates": len(dec["candidates"]) if dec else None, "link_name": link.get("name"),
            "memory_available_bytes": start.get("memory_available_bytes"), "software_version": software,
            "hardware_id": HARDWARE_ID,
        })
        if dec:
            for wid, c in dec["candidates"].items():
                cands.append({"source_log": rel_path, "run_id": start["run_id"], "session_id": session_id,
                              "policy": start["scheduler"], "estimator": est, "eft_model": dec.get("model", "kernel"),
                              "task_id": r["task_id"], "decision_seq": dp["seq"], "candidate_worker": wid,
                              "candidate_pool": pools.get(wid), "chosen": wid == r["worker_id"],
                              "pred_wait_s": c["wait"], "pred_transfer_s": c.get("transfer"), "pred_exec_s": c["exec"],
                              "pred_setup_s": c.get("setup"), "pred_overhead_s": c.get("overhead"),
                              "pred_finish_s": c["finish"]})
    return tasks, cands


def make_splits(sessions: set, sizes: dict, campaign_runs: dict) -> dict:
    """Group-level, leakage-safe split definitions from streamed aggregates.
    ``campaign_runs``: session -> sorted source_logs. A run never straddles
    train and test in the session/run splits; size and occupancy splits are
    extrapolation axes (row-level by construction) and should be combined
    with the session split to avoid same-run leakage."""
    sessions = sorted(sessions)
    campaign_sessions = [x for x in sessions if x.startswith("campaign_")]
    sched_sessions = [x for x in sessions if x not in campaign_sessions]
    latest = campaign_sessions[-1] if campaign_sessions else None
    camp_runs = sorted(campaign_runs.get(latest, []))
    n_tr = int(len(camp_runs) * 0.7)
    return {
        "schema_version": SCHEMA_VERSION,
        "unit": "source_log (one run); sessions = experiment_id",
        "by_session": {"rule": "train = randomized profiling campaign sessions; test = scheduling-experiment sessions",
                       "train_sessions": campaign_sessions, "test_sessions": sched_sessions},
        "by_run_within_latest_campaign": {"rule": "first 70% of runs (collection order) train, rest test",
                                          "session": latest, "train_runs": camp_runs[:n_tr], "test_runs": camp_runs[n_tr:]},
        "by_size": {"rule": "per workload: smallest profiled size train, largest test (size extrapolation)",
                    "train": {w: min(v) for w, v in sorted(sizes.items())},
                    "test": {w: max(v) for w, v in sorted(sizes.items())}},
        "by_occupancy": {"rule": "busy_total <= 4 train, >= 5 test (occupancy extrapolation)", "threshold": 4},
        "forbidden": "random row-level splits (rows of one run share session state and co-runner context)",
    }


def build_dataset(events_root: Path, profile_dir: Path, out_root: Path) -> Path:
    """Streams: each log's rows are written immediately; only small aggregates
    are kept in memory (the machine has 8 GB and other applications)."""
    calib = CalibrationProfiles(profile_dir)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    out = Path(out_root) / stamp
    out.mkdir(parents=True, exist_ok=False)
    sources, excluded, per_kind = [], [], {}
    sessions, sizes, campaign_runs = set(), {}, {}
    n_tasks = n_cands = 0
    with (out / "tasks.csv").open("x", newline="", encoding="utf-8") as ft, \
            (out / "candidates.csv").open("x", newline="", encoding="utf-8") as fc:
        wt = csv.DictWriter(ft, fieldnames=TASK_FIELDS)
        wc = csv.DictWriter(fc, fieldnames=CAND_FIELDS)
        wt.writeheader()
        wc.writeheader()
        for path in sorted(Path(events_root).rglob("*.jsonl")):
            kind, why = classify(path, Path(events_root))
            rel = path.relative_to(Path(events_root).parent).as_posix()
            if why:
                excluded.append({"source_log": rel, "reason": why})
                continue
            t, c = rows_for_log(path, Path(events_root), kind, calib)
            if not t:
                excluded.append({"source_log": rel, "reason": "run not completed (no run_finished status=completed)"})
                continue
            for row in t:
                row["row_id"] = n_tasks
                n_tasks += 1
                sizes.setdefault(row["workload"], set()).add(int(row["size"]))
            wt.writerows(t)
            wc.writerows(c)
            n_cands += len(c)
            per_kind[kind] = per_kind.get(kind, 0) + len(t)
            sess = t[0]["session_id"]
            sessions.add(sess)
            if sess.startswith("campaign_"):
                campaign_runs.setdefault(sess, []).append(rel)
            sources.append({"source_log": rel, "sha256": _sha256(path), "rows": len(t)})
            del t, c
    (out / "splits.json").write_text(json.dumps(make_splits(sessions, sizes, campaign_runs), indent=1), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({
        "schema_version": SCHEMA_VERSION, "built_at": stamp, "events_root": str(events_root),
        "n_task_rows": n_tasks, "n_candidate_rows": n_cands, "rows_per_source_kind": per_kind,
        "n_runs": len(sources), "sessions": sorted(sessions),
        "calibration_profiles": [n for _, n, _ in calib.profiles],
        "sources": sources, "excluded": excluded,
        "notes": ["All rows derive from logged task executions; no synthetic values.",
                  "Raw logs were read only; sha256 recorded per source.",
                  "memory_available_bytes / software_version are null/'unrecorded' for logs predating those fields."],
    }, indent=1), encoding="utf-8")
    return out


def validate_dataset(out: Path) -> dict:
    """Integrity checks, streaming over tasks.csv; returns a report (raises on hard failures)."""
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    keys: set = set()
    n = remote = preds = frac = 0
    with (out / "tasks.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            k = (r["source_log"], r["task_id"])
            if k in keys:
                raise ValueError("duplicate (source_log, task_id) rows")
            keys.add(k)
            n += 1
            if not r["kernel_s"] or float(r["kernel_s"]) <= 0:
                raise ValueError(f"non-positive kernel time in row {r['row_id']}")
            if float(r["t_started_rel"]) > float(r["t_completed_rel"]):
                raise ValueError(f"t_started after t_completed in row {r['row_id']}")
            remote += r["pool"] == "R"
            preds += bool(r["predicted_exec_s"])
            frac += bool(r["target_busy_frac"])
    if sum(x["rows"] for x in manifest["sources"]) != n:
        raise ValueError("row count does not match per-source counts")
    for x in manifest["sources"]:
        if _sha256(Path(manifest["events_root"]).parent / x["source_log"]) != x["sha256"]:
            raise ValueError(f"raw log changed since build: {x['source_log']}")
    return {"rows": n, "sources": len(manifest["sources"]), "excluded": len(manifest["excluded"]),
            "remote_rows": remote, "rows_with_predictions": preds, "rows_with_busy_frac": frac}
