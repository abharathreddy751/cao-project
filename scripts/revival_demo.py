"""Revival demo: ONE run of the mixed-DAG workload under contention with a chosen revival policy and full diagnostics, then a printed trace of the
decisions in which the live state changed the placement.

  python scripts/revival_demo.py <out_dir> <param_model.json> <blind_model.json> <calibration.json> [--binding rsa_combined] [--order-seed 81] [--contention-seed 111]

Not an experiment: one run, no statistics, labelled 'demo' in its manifest. The trace shows, per decision, the state the policy saw, the cost
components of the chosen worker, B4's choice and the runner-up, and (from the same log) the duration that was measured afterwards.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from caosched.core.event_log import read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.experiment.design import Condition
from caosched.revival.adapter import ReviveAdapter
from caosched.revival.workload import build_dyn  # noqa: F401  (import check)

TEST = [[48, 256, 2], [12, 256, 300], [12, 1024, 3]]


def trace(log: Path, limit: int = 6) -> None:
    """Print the decisions that had a real choice (two or more eligible idle workers), whether the live state changed the placement, and the
    duration measured afterwards for the same task."""
    ev = read_events(log)
    done = {e["task_id"]: e for e in ev if e["event"] == "task_completed"}
    dec = [e for e in ev if e["event"] == "task_dispatched" and e.get("decision", {}).get("n_idle", 1) > 1]
    n_all = sum(1 for e in ev if e["event"] == "task_dispatched")
    changed = [e for e in dec if e["decision"].get("b4") and e["decision"]["chosen"] != e["decision"]["b4"]]
    print(f"{n_all} dispatches; {len(dec)} had a real choice; {len(changed)} of those chose a worker other than B4's")
    for e in (changed + [x for x in dec if x not in changed])[:limit]:
        d = e["decision"]
        print(json.dumps({"task": e["task_id"], "chosen": d["chosen"], "b4": d.get("b4"), "fallback": d["fallback"], "n_idle": d["n_idle"],
                          "cost": d.get("cost"), "runner_up": d.get("runner_up"), "slowdown_seen": d.get("state", {}).get("slowdown"),
                          "decision_time_us": round(e["decision_time_s"] * 1e6, 1),
                          "measured_s": round(done.get(e["task_id"], {}).get("wall_time_seconds", 0), 5)}))


def main(out_dir, param_model, blind_model, calibration, binding="rsa_combined", order_seed=81, contention_seed=111) -> int:
    out = Path(out_dir)
    wd = out / "runs" / "demo_00"
    wd.mkdir(parents=True)
    kw = {"dyn": {"classes": TEST, "groups": 6, "seed": 0}, "binding": binding, "param_model": str(Path(param_model).resolve()),
          "blind_model": str(Path(blind_model).resolve()), "calibration": str(Path(calibration).resolve()), "diagnostics": True,
          "instances_spec": {"demo": {"order_seed": order_seed, "contention": {"seed": contention_seed, "n_hot": 3, "burners": 2, "t0": 0.2,
                                                                                 "phase_s": 1.0, "n_phases": 2}}}}
    a = ReviveAdapter(runtime_config=RuntimeConfig.from_topology(max_p_slots=None), timeout_s=120, run_timeout_s=120)
    try:
        rec = a.run_one(Condition("demo", "EFT_E1", None, {}, kw, instance="demo"), wd, seed=1)
    finally:
        a.close()
    print("status", rec.status, "output_ok", rec.output_ok, "makespan_s", round(rec.extra.get("makespan_seconds", 0), 3),
          "revival", rec.extra.get("revival"))
    assert rec.event_log is not None
    trace(wd / rec.event_log)
    (out / "demo_summary.json").write_text(json.dumps({"label": "demo", "status": rec.status, "extra": rec.extra}, default=str, indent=1),
                                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--trace":  # print the trace of an existing event log
        trace(Path(a[1]))
        sys.exit(0)

    def opt(flag, default, cast=str):
        return cast(a[a.index(flag) + 1]) if flag in a else default

    sys.exit(main(a[0], a[1], a[2], a[3], opt("--binding", "rsa_combined"), opt("--order-seed", 81, int), opt("--contention-seed", 111, int)))
