"""Analyze application-demo sessions (one session per workload-intensity level),
from their event logs, artifact files and runs.csv only.

Per session: per-stage kernel time on P / E / R, remote transfer time, total
task service time (dispatch -> completion event), scheduler decision time,
placements, B4 vs EFT_E1_rc paired makespan effect (bootstrap 95% CI over
repeats), EFT's logged remote-vs-local predicted finish gap, and verification
(final output vs the single-process reference; for every remote task: logged
payload bytes == on-disk input + output artifact sizes, output bit-identical to
the reference result of that task).

Usage: python scripts/analyze_app_demo.py appdemo_<stamp> [appdemo_<stamp> ...] --out <name>
Writes data/results/<name>_analysis.json (never overwrites).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import statistics
from pathlib import Path

from caosched.analysis.stats import paired_effect
from caosched.apps import build_image_pipeline, run_reference, verify_output
from caosched.core.event_log import read_events

ROOT = Path(__file__).resolve().parents[1]
B4, EFT = "B4_greedy_eligible_R", "EFT_E1_rc_R"
FOCUS = ("img_denoise", "img_edges")  # the remote-eligible stages


def med(xs):
    return statistics.median(xs) if xs else None


def ms(x):
    return None if x is None else round(x * 1e3, 3)


def analyze_session(session: str) -> dict:
    man = json.loads((ROOT / "data" / "results" / f"{session}_manifest.json").read_text(encoding="utf-8"))
    kw = {k: man["pipeline"][k] for k in ("width", "height", "grid", "seed", "denoise_iterations")}
    dag = build_image_pipeline(**kw)
    ref = run_reference(dag)
    kernel = collections.defaultdict(list)       # (stage, pool) -> kernel s
    transfer = collections.defaultdict(list)     # stage -> transfer s (remote)
    service = collections.defaultdict(list)      # (stage, pool) -> dispatch->completion s
    decision = collections.defaultdict(list)     # policy -> decision s
    place = {B4: collections.Counter(), EFT: collections.Counter()}
    gaps, n_remote, n_remote_ok, outputs, logs = [], 0, 0, collections.Counter(), 0
    for log in sorted((ROOT / "data" / "events" / session).glob("*.jsonl")):
        logs += 1
        ev = read_events(log)
        start = ev[0]
        policy = start["scheduler"]
        run_dir = Path(start["artifact_dir"])
        outputs[verify_output((run_dir / "package.bin").read_bytes(), ref["package"])["match"]] += 1
        t_disp = {}
        for e in ev:
            if e["event"] == "task_dispatched":
                t_disp[e["task_id"]] = e["t"]
                if e.get("decision_time_s") is not None:
                    decision[policy].append(e["decision_time_s"])
                c = (e.get("decision") or {}).get("candidates") or {}
                if policy == EFT and "R0" in c:
                    gaps.append(c["R0"]["finish"] - min(v["finish"] for k, v in c.items() if k != "R0"))
            elif e["event"] == "task_completed":
                st = start["tasks"][e["task_id"]]["workload"]
                kernel[(st, e["pool"])].append(e["wall_time_seconds"])
                service[(st, e["pool"])].append(e["t"] - t_disp[e["task_id"]])
                if policy in place:
                    place[policy][(st, e["pool"])] += 1
                if e["pool"].startswith("R"):
                    transfer[st].append(e["transfer_s"])
                    n_remote += 1
                    t = dag.tasks[e["task_id"]]
                    in_sz = sum((run_dir / f"{d}.bin").stat().st_size for d in t.dependencies)
                    out_p = run_dir / f"{e['task_id']}.bin"
                    n_remote_ok += (e["payload_bytes"] == in_sz + out_p.stat().st_size
                                    and e["output_bytes"] == out_p.stat().st_size
                                    and out_p.read_bytes() == ref[e["task_id"]])
    rows = list(csv.DictReader(open(ROOT / "data" / "results" / f"{session}_runs.csv", encoding="utf-8")))
    blocks = collections.defaultdict(dict)
    for r in rows:
        blocks[int(r["repeat"])][r["policy"]] = {"makespan_s": float(r["makespan_s"])}
    per_policy = {}
    for pol in (B4, EFT):
        rs = [r for r in rows if r["policy"] == pol]
        mk = [float(r["makespan_s"]) for r in rs]
        per_policy[pol] = {
            "runs": len(rs), "completed": sum(r["status"] == "completed" for r in rs),
            "makespan_median_ms": ms(med(mk)), "makespan_mean_ms": ms(statistics.mean(mk)) if mk else None,
            "makespan_min_ms": ms(min(mk)) if mk else None, "makespan_max_ms": ms(max(mk)) if mk else None,
            "scheduling_time_median_ms": ms(med([float(r["scheduling_time_s"]) for r in rs])),
            "decision_time_median_us": round(med(decision[pol]) * 1e6, 2) if decision[pol] else None,
            "remote_tasks_total": sum(int(r["tasks_R"]) for r in rs),
            "runs_with_remote": sum(int(r["tasks_R"]) > 0 for r in rs),
            "placement_total": {f"{s}@{p}": n for (s, p), n in sorted(place[pol].items())}}
    stages = {}
    for st in FOCUS:
        loc = {p: med(kernel[(st, p)]) for p in ("P", "E", "R")}
        tr = med(transfer[st])
        rsvc = med(service[(st, "R")])
        stages[st] = {"kernel_ms": {p: ms(v) for p, v in loc.items()},
                      "n_kernel": {p: len(kernel[(st, p)]) for p in ("P", "E", "R")},
                      "transfer_median_ms": ms(tr), "n_transfer": len(transfer[st]),
                      "service_median_ms": {p: ms(med(service[(st, p)])) for p in ("P", "E", "R")},
                      # >1: a remote task costs more end to end than computing it locally
                      "remote_service_over_local_kernel": {
                          p: round(rsvc / loc[p], 3) if rsvc and loc[p] else None for p in ("P", "E")},
                      "kernel_over_transfer": {p: round(loc[p] / tr, 3) if tr and loc[p] else None
                                               for p in ("P", "E", "R")}}
    eff = paired_effect(dict(blocks), EFT, B4, "makespan_s")
    return {"session": session, "denoise_iterations": kw["denoise_iterations"], "pipeline": kw,
            "event_logs": logs, "final_outputs": dict(outputs),
            "remote_tasks_checked": n_remote, "remote_tasks_verified": n_remote_ok,
            "stages": stages, "policies": per_policy, "eft_vs_b4_makespan": eff,
            "eft_remote_gap_ms": {"n": len(gaps), "min": ms(min(gaps)) if gaps else None,
                                  "median": ms(med(gaps)), "n_remote_predicted_better": sum(g < 0 for g in gaps)},
            "stop_reason": man.get("stop_reason")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = ROOT / "data" / "results" / f"{args.out}_analysis.json"
    if out.exists():
        raise SystemExit(f"{out} exists; not overwriting")
    res = [analyze_session(s) for s in args.sessions]
    out.write_text(json.dumps({"sessions": res}, indent=1), encoding="utf-8")
    for r in res:
        print(f"\n== {r['session']}: denoise iterations {r['denoise_iterations']}; logs {r['event_logs']}; "
              f"final outputs {r['final_outputs']}; remote tasks verified {r['remote_tasks_verified']}/"
              f"{r['remote_tasks_checked']}; stop: {r['stop_reason']}")
        for st, d in r["stages"].items():
            print(f"  {st:12s} kernel P/E/R {d['kernel_ms']['P']}/{d['kernel_ms']['E']}/{d['kernel_ms']['R']} ms; "
                  f"transfer {d['transfer_median_ms']} ms (n={d['n_transfer']}); service P/E/R "
                  f"{d['service_median_ms']['P']}/{d['service_median_ms']['E']}/{d['service_median_ms']['R']} ms; "
                  f"kernel/transfer E {d['kernel_over_transfer']['E']}")
        for pol, d in r["policies"].items():
            print(f"  {pol:22s} {d['completed']}/{d['runs']} runs; makespan median {d['makespan_median_ms']} ms "
                  f"[{d['makespan_min_ms']}, {d['makespan_max_ms']}]; decision median {d['decision_time_median_us']} us; "
                  f"scheduling/run {d['scheduling_time_median_ms']} ms; remote tasks {d['remote_tasks_total']} "
                  f"in {d['runs_with_remote']} runs")
        e = r["eft_vs_b4_makespan"]
        if e:
            print(f"  EFT vs B4 makespan {e['effect_pct']:+.1f}% [{e['ci_lo_pct']:+.1f}, {e['ci_hi_pct']:+.1f}] "
                  f"(n={e['n_blocks']} paired repeats, CI excludes 0: {e['ci_excludes_zero']})")
        print(f"  EFT predicted remote-minus-best-local finish: {r['eft_remote_gap_ms']}")
    print(f"\n-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
