"""Run a generated Pegasus workflow YAML under one scheduling policy and verify it.

    adapter (workflow YAML -> extcmd DAG) -> clean work directory -> stage raw
    inputs -> run under --policy -> record SHA-256 + size of every final output
    -> compare with --reference-hashes (a JSON {lfn: sha256}); with --write-reference
    the hashes of this run are saved there instead (the first, trusted run).

The run manifest (data/results/<run_id>_manifest.json) records policy, status,
per-task status counts, the adapter report (edge agreement, unresolved inputs),
the runtime configuration and the output hashes. A failed run still writes it.

Usage:
    python scripts/run_workflow.py WORKFLOW.yml --work-dir D:/work/m17 --bin-dir D:/Montage/bin \
        --input-dir D:/montage_inputs --policy B4_greedy_eligible [--reference-hashes ref.json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
from caosched.core.event_log import EventLogger, read_events
from caosched.core.extcmd import prepare_workdir
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.worker_pool import WorkerPool
from caosched.schedulers import policy_factories
from caosched.schedulers.simple import RandomScheduler
from caosched.util.provenance import software_info
from caosched.workflow.adapter import load_workflow, stage_raw_inputs

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow")
    ap.add_argument("--work-dir", required=True, help="created fresh (an earlier caosched work dir is wiped first)")
    ap.add_argument("--bin-dir", help="directory holding the executables (default: PATH)")
    ap.add_argument("--input-dir", action="append", default=[], help="where raw inputs are found by name (repeatable)")
    ap.add_argument("--policy", default="B4_greedy_eligible")
    ap.add_argument("--seed", type=int, default=0, help="seed for the random policy")
    ap.add_argument("--timeout-s", type=float, default=600.0, help="per-task timeout")
    ap.add_argument("--run-timeout", type=float, default=None)
    ap.add_argument("--run-id")
    ap.add_argument("--reference-hashes")
    ap.add_argument("--write-reference", action="store_true")
    ap.add_argument("--out-dir", default=str(DATA), help="events/ and results/ go below this (default: data/)")
    args = ap.parse_args()
    if args.write_reference and not args.reference_hashes:
        ap.error("--write-reference needs --reference-hashes FILE")

    run_id = args.run_id or f"wf_{args.policy}_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    error = rc = wf = log_path = ref = None
    try:  # everything that can fail is inside: the manifest below is written either way
        rc = RuntimeConfig.from_topology()
        cpu = [n for n, s in rc.pools.items() if s.kind == "cpu"]
        # B6/B7 (EFT) need a static profile and are not offered here.
        factories = policy_factories({"B2_static_mapping": {"mapping": {"extcmd": "P" if "P" in cpu else cpu[0]}}}, None)
        factories = {n: f for n, f in factories.items() if not n.startswith(("B6", "B7"))}
        factories["random"] = lambda: RandomScheduler(args.seed)
        if args.policy not in factories:
            raise ValueError(f"unknown --policy {args.policy!r}; choose from {sorted(factories)}")
        if args.reference_hashes and not args.write_reference:
            ref = json.loads(Path(args.reference_hashes).read_text(encoding="utf-8"))
        wf = load_workflow(args.workflow, args.work_dir, bin_dir=args.bin_dir, timeout_s=args.timeout_s)
        print(f"{len(wf.dag)} jobs, {wf.report['n_edges']} edges, {wf.report['n_raw_inputs']} raw inputs; "
              f"edge disagreement: only-in-YAML {len(wf.report['edges_only_in_jobDependencies'])}, "
              f"only-in-files {len(wf.report['edges_only_in_files'])}")
        prepare_workdir(args.work_dir)
        stage_raw_inputs(wf, args.input_dir)
        print(f"coordinator pinned to core {pin_coordinator_to_reserved_core(rc)}; pools {rc.to_dict()['pools']}")
        with WorkerPool.from_config(rc, warmup=False, strict_affinity=True) as pool, \
                EventLogger(run_id, output_dir=Path(args.out_dir) / "events") as log:
            log_path = log.path
            Coordinator(wf.dag, pool, factories[args.policy](), log).run(run_timeout=args.run_timeout)
    except Exception as exc:  # noqa: BLE001 - the manifest records every failure
        error = f"{type(exc).__name__}: {exc}"
    finally:
        events = read_events(log_path) if log_path else []
        finished = events[-1] if events and events[-1]["event"] == "run_finished" else {}
        final = wf.final_outputs if wf else []
        outputs = {lfn: e["outputs"][lfn] for e in events if e["event"] == "task_completed"
                   for lfn in e.get("outputs", {}) if lfn in final}

        verification = None
        if ref is not None:
            bad = {l: {"reference": h, "run": outputs.get(l, {}).get("sha256")} for l, h in ref.items()
                   if outputs.get(l, {}).get("sha256") != h}
            verification = {"reference": args.reference_hashes, "n_files": len(ref), "mismatches": bad, "match": not bad}

        manifest = {
            "run_id": run_id, "workflow": str(Path(args.workflow).resolve()), "policy": args.policy,
            "status": finished.get("status", "failed"), "failure_reason": finished.get("failure_reason"), "error": error,
            "n_tasks": len(wf.dag) if wf else None, "makespan_seconds": finished.get("makespan_seconds"),
            "task_status_counts": {s: list((finished.get("task_status") or {}).values()).count(s)
                                   for s in sorted(set((finished.get("task_status") or {}).values()))},
            "adapter_report": wf.report if wf else None, "final_outputs": outputs, "verification": verification,
            "runtime_config": rc.to_dict() if rc else None, "software": software_info(),
            "event_log": str(log_path) if log_path else None,
        }
        out = Path(args.out_dir) / "results" / f"{run_id}_manifest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
        print(f"{manifest['status']}" + (f" ({manifest['failure_reason']}: {error})" if error else "")
              + f"; tasks {manifest['task_status_counts']}; verification {verification and verification['match']}; -> {out}")
    if args.write_reference and error is None:  # the first, trusted run
        Path(args.reference_hashes).write_text(json.dumps({l: o["sha256"] for l, o in outputs.items()}, indent=1))
    return 0 if manifest["status"] == "completed" and (verification is None or verification["match"]) else 1


if __name__ == "__main__":
    sys.exit(main())
