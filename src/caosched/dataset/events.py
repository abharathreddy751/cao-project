"""Event log -> per-task rows with the decision-time occupancy features.

For every completed task in a run, the ``EstimateContext`` at its start is
reconstructed from the log: the other workers whose task interval
[t_started, t_completed) contains this task's t_started (worker-side clock,
which is the shared QPC timebase -- see util/clock.py). This is the same
definition the scheduler sees online via ``EstimateContext.from_state``
(other workers currently executing), up to the ~0.2-0.3 ms IPC lag between
the coordinator's view and the worker's actual start, measured in Phase 1.

``target_busy_frac`` (the task's own worker's busy fraction over the
BUSY_WINDOW_S before its start) uses the worker's in-run intervals plus the
``worker_history`` that ``run_started`` records for runs logged after this
field was added. For older logs it is reconstructed only when the window lies
entirely inside the run; otherwise it is None (unknown) -- never guessed.

Known approximation: the snapshot is taken at task *start*; co-runners that
start or finish during the task are not captured (they are not observable at
decision time either).
"""
from __future__ import annotations

from pathlib import Path

from caosched.core.event_log import read_events
from caosched.estimators.base import BUSY_WINDOW_S, EstimateContext


def _busy_frac(intervals, t: float, window: float) -> float:
    lo = t - window
    return min(1.0, sum(max(0.0, min(b, t) - max(a, lo)) for a, b in intervals) / window)


def rows_from_events(events: list[dict]) -> list[dict]:
    start = next((e for e in events if e["event"] == "run_started"), None)
    if start is None:
        raise ValueError("event log has no run_started record")
    if not any(e["event"] == "run_finished" and e["status"] == "completed" for e in events):
        return []  # incomplete/failed runs are excluded from datasets
    meta = start.get("metadata") or {}
    specs = start["tasks"]
    done = [e for e in events if e["event"] == "task_completed"]
    history = start.get("worker_history")  # None for logs predating the field
    run_t0 = start.get("t")
    rows = []
    for e in done:
        others = [o for o in done if o["worker_id"] != e["worker_id"]
                  and o["t_started"] <= e["t_started"] < o["t_completed"]]
        own = [(o["t_started"], o["t_completed"]) for o in done
               if o["worker_id"] == e["worker_id"] and o["t_completed"] <= e["t_started"]]
        if history is not None:
            frac = _busy_frac([tuple(iv) for iv in history.get(e["worker_id"], [])] + own, e["t_started"], BUSY_WINDOW_S)
        elif run_t0 is not None and e["t_started"] - BUSY_WINDOW_S >= run_t0:
            frac = _busy_frac(own, e["t_started"], BUSY_WINDOW_S)
        else:
            frac = None
        ctx = EstimateContext.build(
            sum(o["pool"] == "P" for o in others), sum(o["pool"] == "E" for o in others),
            [specs[o["task_id"]]["workload"] for o in others], frac)
        s = specs[e["task_id"]]
        rows.append({
            "run_id": start["run_id"], "experiment": meta.get("experiment_id"), "trace": meta.get("trace"),
            "scheduler": start["scheduler"], "task_id": e["task_id"], "workload": s["workload"],
            "size": int(s["size"]), "seed": int(s["seed"]), "worker_id": e["worker_id"], "pool": e["pool"],
            "t_started": e["t_started"], "t_completed": e["t_completed"], "kernel_s": e["wall_time_seconds"],
            "ctx": ctx,
        })
    return rows


def rows_from_dir(directory: Path) -> list[dict]:
    rows = []
    for p in sorted(Path(directory).glob("*.jsonl")):
        rows.extend(rows_from_events(read_events(p)))
    if not rows:
        raise ValueError(f"No completed-run rows in {directory}")
    return rows
