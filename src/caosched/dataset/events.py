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

Decision context (audit D4 / AD-7). The start-time reconstruction above is
LEAKY for early binding (the task waited in a local queue, so its start-time
occupancy was not known at the decision). Policies therefore log the context
they actually used in the ``task_dispatched`` event
(``decision.candidates[chosen].ctx``); ``decision_contexts`` reads ONLY those
records, never a completion. ``rows_from_events(context_source=...)``:

  "decision"  features from the logged decision context only; tasks without one
              are dropped (DEFAULT; leakage-safe, used for model training/evaluation);
  "start"     the old reconstruction above (historical logs only; post-decision
              data, so opt in explicitly);
  "auto"      "decision" where logged, else "start" (explicit opt-in; each row says
              which via ``ctx_source``).
"""
from __future__ import annotations

from pathlib import Path

from caosched.core.event_log import read_events
from caosched.core.task import Task
from caosched.estimators.base import BUSY_WINDOW_S, EstimateContext


def _busy_frac(intervals, t: float, window: float) -> float:
    lo = t - window
    return min(1.0, sum(max(0.0, min(b, t) - max(a, lo)) for a, b in intervals) / window)


def logged_task(task_id: str, spec: dict, completed: dict | None = None) -> Task:
    """The ``Task`` a logged run_started spec (+ its task_completed record, which carries the extcmd input
    size seen at ready time) describes. Offline rows take ``est_*`` from it, so they cannot drift from
    the ``Task.est_*`` the estimators read online."""
    return Task(task_id, spec["workload"], int(spec["size"]), int(spec["seed"]), params=spec.get("params"),
                input_bytes=(completed or {}).get("input_bytes"))


def decision_contexts(events: list[dict]) -> dict[str, EstimateContext]:
    """task_id -> EstimateContext logged at that task's placement decision.
    Reads only ``task_dispatched`` records: nothing after the decision is used."""
    out = {}
    for e in events:
        if e["event"] != "task_dispatched":
            continue
        c = ((e.get("decision") or {}).get("candidates") or {}).get(e["worker_id"]) or {}
        if "ctx" in c and c["ctx"] is not None:
            out[e["task_id"]] = EstimateContext.from_dict(c["ctx"])
    return out


def rows_from_events(events: list[dict], context_source: str = "decision") -> list[dict]:
    if context_source not in ("auto", "decision", "start"):
        raise ValueError(f"context_source must be auto|decision|start, got {context_source!r}")
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
    logged = {} if context_source == "start" else decision_contexts(events)
    rows = []
    for e in done:
        if e["task_id"] in logged:
            ctx, src = logged[e["task_id"]], "decision"
        elif context_source == "decision":
            continue
        else:
            ctx, src = None, "start"
        if ctx is None:
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
                [logged_task(o["task_id"], specs[o["task_id"]]).est_workload for o in others], frac)
        s = specs[e["task_id"]]
        t = logged_task(e["task_id"], s, e)
        rows.append({
            "run_id": start["run_id"], "experiment": meta.get("experiment_id"), "trace": meta.get("trace"),
            "scheduler": start["scheduler"], "task_id": e["task_id"], "workload": t.est_workload,
            "size": t.est_size, "bytes": t.est_bytes, "is_extcmd": s["workload"] == "extcmd",
            "input_bytes": e.get("input_bytes"), "output_bytes": e.get("output_bytes"),
            "seed": int(s["seed"]), "worker_id": e["worker_id"], "pool": e["pool"],
            "t_started": e["t_started"], "t_completed": e["t_completed"], "kernel_s": e["wall_time_seconds"],
            "ctx": ctx, "ctx_source": src,
        })
    return rows


def rows_from_dir(directory: Path, context_source: str = "decision") -> list[dict]:
    rows = []
    for p in sorted(Path(directory).glob("*.jsonl")):
        rows.extend(rows_from_events(read_events(p), context_source))
    if not rows:
        raise ValueError(f"No completed-run rows in {directory} (context_source={context_source!r}; logs without "
                         f"a logged decision context need an explicit 'start' or 'auto')")
    return rows
