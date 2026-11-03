"""Dashboard v3: one LIVE block of the final benchmark on this laptop.

Runs the real experiment machinery (``run_session`` + ``FinalAdapter``) on a one-block, one-condition copy of the registered primary design
(``design_final_eval_h16_l120.json``): the same workload (16 heavy chains of 64, 512 px), the same policy classes, the same GPU-eligibility
rule, the same CUDA worker G. Only the block count (1), the warm-up (none) and the mains-power requirement (off, so a demo on battery still
runs) differ. The output is a normal session under ``data/dashboard_runs_v3/sessions`` (read by the dashboard through its run manifest).
This is a demonstration run, not an experiment record.

  python -m caosched.dashboard_v3.live3 --policy PRED_RANK_GREEDY_E2E --config ext --sid <id>
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DASH3 = ROOT / "data" / "dashboard_runs_v3"
DESIGN = ROOT / "data" / "results" / "final_20261101" / "eval" / "designs" / "design_final_eval_h16_l120.json"
ADAPTER_CFG = ROOT / "data" / "results" / "final_20261101" / "adapter_config_final.json"
POLICIES = ("B4", "B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E", "HEFT_param_model", "PEFT_param_model", "HEFT_E2E", "HEFT_ORACLE_REF")
CONFIGS = ("cpu", "gpu", "ext")
MIN_START_GIB = 2.4  # the project's start gate: the worker pool takes about 1.8 GB and each block needs 0.8 GB left


def new_sid(policy: str, config: str) -> str:
    return f"live3_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}_{policy}_{config}"


def status_path(sid: str) -> Path:
    return DASH3 / "status" / f"{sid}.json"


def read_status(sid: str) -> dict:
    p = status_path(sid)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def write_status(sid: str, **fields) -> dict:
    p = status_path(sid)
    p.parent.mkdir(parents=True, exist_ok=True)
    cur = read_status(sid)
    cur.update(fields, updated=datetime.datetime.now().isoformat(timespec="seconds"))
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return cur


def mains_power() -> bool | None:
    import psutil
    b = psutil.sensors_battery()
    return None if b is None else bool(b.power_plugged)


def execute(sid: str, policy: str, config: str) -> dict:
    import psutil

    if policy not in POLICIES or config not in CONFIGS:
        raise ValueError(f"policy must be one of {POLICIES} and config one of {CONFIGS}")
    avail = psutil.virtual_memory().available / 2**30
    write_status(sid, state="starting", policy=policy, config=config, available_gib_at_start=round(avail, 2), mains_power=mains_power(),
                 mode="LIVE (dashboard demonstration run, not an experiment record)")
    if avail < MIN_START_GIB:
        return write_status(sid, state="refused", message=f"{avail:.2f} GiB free RAM < {MIN_START_GIB} GiB needed (worker pool about 1.8 GB). Close other programs and retry.")
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    name = f"{policy}_{config}"
    cond = next((c for c in design["conditions"] if c["name"] == name), None)
    if cond is None:
        raise ValueError(f"condition {name!r} not in the registered design")
    mini = {**design, "name": f"live3_{name}", "n_blocks": 1, "warmup_blocks": 0, "instances": design["instances"][:1], "conditions": [cond],
            "reference": name, "require_ac_power": False}
    dpath = DASH3 / "designs" / f"{sid}.json"
    dpath.parent.mkdir(parents=True, exist_ok=True)
    dpath.write_text(json.dumps(mini, indent=1), encoding="utf-8")
    os.environ["CAO_FINAL_ADAPTER_CONFIG"] = str(ADAPTER_CFG)
    from caosched.experiment.runner import run_session
    from caosched.final.adapter import factory

    write_status(sid, state="running", condition=name, message="starting the worker pool (P cores, E cores" + (", RTX 3050 CUDA worker" if config != "cpu" else "") + "), then one run, then output verification")
    sess = run_session(dpath, DASH3 / "sessions", factory(), session_id=sid)
    if sess.get("status") != "complete":
        return write_status(sid, state="failed", session_status=sess.get("status"), message=str(sess.get("reason") or "session did not complete"))
    mdir = next((DASH3 / "sessions" / sid / "runs").glob("*/run_manifest.json"), None)
    if mdir is None:
        return write_status(sid, state="failed", message="no run manifest written")
    m = json.loads(mdir.read_text(encoding="utf-8"))
    ex, ver = m.get("extra") or {}, m.get("verification") or {}
    return write_status(sid, state="done", session=sid, run_id=m.get("run_id"), run_status=m.get("status"), output_verified=ver.get("passed"),
                        makespan_s=ex.get("makespan_seconds"), end_to_end_makespan_s=ex.get("end_to_end_makespan_seconds"),
                        n_tasks=ex.get("n_tasks"), cuda_tasks=len(ex.get("cuda_tasks") or []))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--sid", required=True)
    a = ap.parse_args()
    try:
        execute(a.sid, a.policy, a.config)
    except Exception as exc:  # noqa: BLE001 - shown on the page
        write_status(a.sid, state="failed", message=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc()[-1500:])
        sys.exit(1)


if __name__ == "__main__":
    main()
