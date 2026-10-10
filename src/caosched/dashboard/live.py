"""Live execution of the image-analysis DAG for the dashboard.

Runs the REAL application through the REAL runtime: ``build_image_pipeline``,
``WorkerPool`` (P/E workers + the local remote node behind the ``lan_1g``
link shim), ``Coordinator`` and the unchanged B4 / EFT_E1_rc policies -- the
same construction as ``scripts/run_app_demo.py`` -- and then verifies the
final artifact against the single-process reference.

Differences from the experiment runner, by design:
* output goes to ``data/dashboard_runs/live_<stamp>_<policy>_k<k>/`` -- never
  into the experiment record (``data/events``, ``data/artifacts``, ``data/results``);
* one run, no stage profiling: EFT's E1 estimator uses the stage profile
  measured by the ACCEPTED session of the same workload level (read only).

Executed as a subprocess (``python -m caosched.dashboard.live``) so that
pinning the coordinator to its reserved core and the worker processes never
affect the dashboard server. Progress: the flushed-per-line event log plus
``status.json``.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DASH_RUNS = ROOT / "data" / "dashboard_runs"
LINK_PROFILE = "data/profiles/20261003T152700_profile.json"
REMOTE = {"img_denoise": ["R"], "img_edges": ["R"]}
POLICIES = {"B4": "B4_greedy_eligible_R", "EFT": "EFT_E1_rc_R"}
LEVELS = (1, 4, 16, 64)
NODE_CORE = 11
MIN_START_GIB = 1.0  # the experiment runner's own preflight threshold


def pipeline_kwargs(k: int, size: int = 1024, grid: int = 4) -> dict:
    return dict(width=size, height=size, grid=grid, seed=11, denoise_iterations=k)


def link_config():
    from caosched.remote.link import LinkConfig
    return LinkConfig("lan_1g", latency_s=0.0002, bandwidth_Bps=125e6, per_message_s=0.00005)


def accepted_profile(k: int) -> Path:
    """Stage profile measured by the accepted session for workload level k."""
    from caosched.dashboard.data import accepted_sessions
    sess = next(s for s in accepted_sessions() if s["k"] == k)
    return ROOT / "data" / "profiles" / sess["profile"]


def make_policy(policy: str, k: int):
    from caosched.estimators import RecalibratedEstimator, StaticProfileEstimator
    from caosched.remote.link import TransferModel
    from caosched.schedulers.eft import EarliestFinishTimeScheduler
    from caosched.schedulers.simple import GreedyEligibleScheduler

    if policy == "B4":
        return GreedyEligibleScheduler(priority=["P", "E", "R"], name=POLICIES["B4"])
    prof_path = accepted_profile(k)
    prof = json.loads(prof_path.read_text(encoding="utf-8"))
    e1 = StaticProfileEstimator({(e["workload"], e["size"], e["pool"]): e["median_s"] for e in prof["entries"]},
                                source=str(prof_path))
    cal = json.loads((ROOT / LINK_PROFILE).read_text(encoding="utf-8"))["link_calibration"]
    tm = TransferModel({"R": link_config()}, cal["socket_a_s"], cal["socket_b_s_per_byte"], LINK_PROFILE)
    return EarliestFinishTimeScheduler(RecalibratedEstimator(e1), POLICIES["EFT"], transfer=tm)


def new_session_dir(policy: str, k: int) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    d = DASH_RUNS / f"live_{stamp}_{policy}_k{k}"
    d.mkdir(parents=True, exist_ok=False)
    return d


def read_status(out: Path) -> dict:
    path = out / "status.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_status(out: Path, **fields) -> dict:
    cur = read_status(out)
    cur.update(fields, updated=datetime.datetime.now().isoformat(timespec="seconds"))
    tmp = out / "status.tmp"
    tmp.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    os.replace(tmp, out / "status.json")
    return cur


def execute(out: Path, policy: str, k: int, size: int = 1024, grid: int = 4) -> dict:
    """One live run into ``out``. Returns the final status dict."""
    import psutil

    from caosched.apps import build_image_pipeline, run_reference, verify_output
    from caosched.apps.artifacts import artifact_path
    from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
    from caosched.core.event_log import EventLogger
    from caosched.core.runtime_config import RuntimeConfig
    from caosched.core.worker_pool import RemoteSlot, WorkerPool

    if policy not in POLICIES or k not in LEVELS:
        raise ValueError(f"policy must be one of {list(POLICIES)} and k one of {LEVELS}")
    run_name = f"live_{policy}"
    kw = pipeline_kwargs(k, size, grid)
    avail = psutil.virtual_memory().available / 2**30
    write_status(out, state="starting", policy=POLICIES[policy], k=k, run=run_name, pipeline=kw,
                 available_gib_at_start=round(avail, 3), mode="LIVE (dashboard run, not an experiment record)")
    if avail < MIN_START_GIB:
        return write_status(out, state="refused", message=f"{avail:.2f} GiB available < {MIN_START_GIB} GiB")
    rc = RuntimeConfig.from_topology()
    coord = pin_coordinator_to_reserved_core(rc)
    e_slots = [c for c in rc.e_core_slots if c != NODE_CORE]
    sched = make_policy(policy, k)
    slots = [RemoteSlot(link_config(), node_core=NODE_CORE, proxy_core=rc.coordinator_core)]
    write_status(out, state="starting_workers", coordinator_core=coord, p_slots=list(rc.p_core_slots), e_slots=e_slots,
                 node_core=NODE_CORE, link=link_config().to_dict(),
                 estimator_profile=None if policy == "B4" else str(accepted_profile(k).relative_to(ROOT)))
    with WorkerPool(list(rc.p_core_slots), e_slots, warmup=True, strict_affinity=True, remote_slots=slots) as pool:
        write_status(out, state="running")
        with EventLogger(run_name, output_dir=out / "events") as log:
            summary = Coordinator(build_image_pipeline(**kw, remote_stages=REMOTE), pool, sched, log,
                                  artifact_dir=out / "artifacts" / run_name,
                                  run_metadata={"experiment_id": out.name, "app": "image_pipeline",
                                                "mode": "dashboard_live", **kw}).run(run_timeout=600)
    write_status(out, state="verifying", status=summary.status, makespan_ms=summary.makespan_seconds * 1e3)
    final = artifact_path(out / "artifacts" / run_name, "package").read_bytes()
    v = verify_output(final, run_reference(build_image_pipeline(**kw))["package"])
    return write_status(out, state="done", verification=v, tasks_per_pool=summary.tasks_per_pool,
                        scheduling_ms=summary.scheduling_time_seconds * 1e3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=list(POLICIES), required=True)
    ap.add_argument("--k", type=int, choices=LEVELS, required=True)
    ap.add_argument("--out", required=True, help="an empty directory under data/dashboard_runs")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if not out.is_relative_to(DASH_RUNS.resolve()):
        raise SystemExit("--out must be under data/dashboard_runs")
    try:
        execute(out, a.policy, a.k)
    except Exception as exc:  # noqa: BLE001 - recorded for the dashboard, then re-raised
        write_status(out, state="failed", message=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
