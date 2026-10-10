"""Phase B supplementary analysis of the application workload-intensity sweep.

Complements scripts/analyze_app_demo.py (run unchanged first). Differences:
* uses ONLY the 20 paired demo runs (B4 / EFT_E1_rc) of each accepted session;
  the 6 pool-pinned profile_* runs are reported separately as a reference,
  never mixed into the primary statistics;
* the unit of analysis is the run (task timings are averaged within a run
  first), so tasks of one run are not treated as independent observations;
* means, SD and 95% CIs: per policy a t-interval over the 10 runs; for
  B4 vs EFT_E1_rc a paired t-interval over the 10 per-repeat differences
  (EFT - B4) plus the existing paired log-ratio percentile bootstrap
  (caosched.analysis.stats.paired_effect) as a non-parametric cross-check;
* validates every session against the pre-registered design and stops
  (writes nothing) on any mismatch.

Reads manifests, runs.csv, event logs and the final package artifact only.
Usage: python scripts/analyze_app_sweep.py --out-dir data/results/<new dir>
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import statistics
from pathlib import Path

from caosched.analysis.stats import paired_effect
from caosched.apps import build_image_pipeline, run_reference, verify_output
from caosched.core.event_log import read_events

ROOT = Path(__file__).resolve().parents[1]
B4, EFT = "B4_greedy_eligible_R", "EFT_E1_rc_R"
POOLS = ("P", "E", "R")
FOCUS = ("img_denoise", "img_edges")  # the remote-eligible stages
# the four accepted sessions (PROJECT_STATUS.md, Phase A); nothing else is analysed
ACCEPTED = {1: "appdemo_20261004T185921", 4: "appdemo_20261003T213900",
            16: "appdemo_20261004T185801", 64: "appdemo_20261003T214453"}
DESIGN = {"size": 1024, "grid": 4, "profile_runs": 2, "node_core": 11,
          "link_profile": "data/profiles/20261003T152700_profile.json",
          "repeats": 10, "order_seed": 0, "min_run_gib": 0.5}
# two-sided 95% Student t quantiles (no scipy in the venv)
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
        10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110,
        18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def summ(xs, scale=1e3):
    """n, mean, SD, 95% t-CI, median, min, max (x scale; default s -> ms)."""
    xs = [x * scale for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    out = {"n": len(xs), "mean": statistics.mean(xs), "median": statistics.median(xs),
           "min": min(xs), "max": max(xs), "sd": None, "ci95": None}
    if len(xs) >= 2:
        sd = statistics.stdev(xs)
        h = T975.get(len(xs) - 1, 1.960) * sd / math.sqrt(len(xs))
        out.update(sd=sd, ci95=[out["mean"] - h, out["mean"] + h])
    return {k: (round(v, 4) if isinstance(v, float) else [round(c, 4) for c in v] if isinstance(v, list) else v)
            for k, v in out.items()}


def validate(k: int, session: str):
    res = ROOT / "data" / "results"
    man = json.loads((res / f"{session}_manifest.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(res / f"{session}_runs.csv", encoding="utf-8")))
    errs = []
    a = man["args"]
    errs += [f"arg {key}={a.get(key)!r} != {v!r}" for key, v in DESIGN.items() if a.get(key) != v]
    if a.get("denoise_iterations") != k or man["pipeline"]["denoise_iterations"] != k:
        errs.append("denoise_iterations != k")
    if man["pipeline"].get("seed") != 11 or man["link"]["name"] != "lan_1g":
        errs.append("seed / link differ from design")
    if man["policies"] != [B4, EFT] or man["runs_completed"] != 20 or man["stop_reason"] is not None:
        errs.append("policies / runs_completed / stop_reason")
    pairs = collections.defaultdict(dict)
    for r in rows:
        pairs[int(r["repeat"])][r["policy"]] = r
    if sorted(pairs) != list(range(10)) or any(set(p) != {B4, EFT} for p in pairs.values()):
        errs.append("not 10 complete B4/EFT pairs")
    if any(r["status"] != "completed" or r["output_match"] != "exact" for r in rows):
        errs.append("a run is not completed/exact")
    if errs:
        raise SystemExit(f"{session} (k={k}) does not match the pre-registered design: {errs}")
    return man, rows, pairs


def run_metrics(log: Path, ref: dict) -> dict:
    ev = read_events(log)
    start, fin = ev[0], ev[-1]
    assert start["event"] == "run_started" and fin["event"] == "run_finished", log
    tasks = start["tasks"]
    disp, dec, gaps = {}, [], []
    place = collections.Counter()
    m = collections.defaultdict(list)  # (stage, pool, metric) -> values in this run
    for e in ev:
        if e["event"] == "task_dispatched":
            disp[e["task_id"]] = e["t"]
            if e.get("decision_time_s") is not None:
                dec.append(e["decision_time_s"])
            c = (e.get("decision") or {}).get("candidates") or {}
            if "R0" in c and len(c) > 1:
                gaps.append(c["R0"]["finish"] - min(v["finish"] for w, v in c.items() if w != "R0"))
        elif e["event"] == "task_completed":
            st, pool = tasks[e["task_id"]]["workload"], e["pool"]
            place[(st, pool)] += 1
            m[(st, pool, "kernel")].append(e["wall_time_seconds"])
            m[(st, pool, "service")].append(e["t"] - disp[e["task_id"]])
            m[(st, pool, "io")].append(e.get("io_s"))
            if e.get("transfer_s") is not None:
                m[(st, pool, "transfer")].append(e["transfer_s"])
    package = (Path(start["artifact_dir"]) / "package.bin").read_bytes()
    v = verify_output(package, ref["package"])
    return {"scheduler": start["scheduler"], "status": fin["status"], "makespan_s": fin["makespan_seconds"],
            "n_completed": fin["n_completed"], "n_tasks": fin["n_tasks"], "tasks_per_pool": fin["tasks_per_pool"],
            "total_kernel_s": fin["total_wall_time_seconds"], "scheduling_s": fin["scheduling_time_seconds"],
            "decision_mean_s": statistics.mean(dec) if dec else None, "n_decisions": len(dec),
            "placement": place, "m": m, "gaps": gaps, "output_match": v["match"], "output_sha256": v["sha256"]}


def mean_of(vals):
    vals = [x for x in vals if x is not None]
    return statistics.mean(vals) if vals else None


def analyze(k: int, session: str):
    man, rows, pairs = validate(k, session)
    kw = {key: man["pipeline"][key] for key in ("width", "height", "grid", "seed", "denoise_iterations")}
    ref = run_reference(build_image_pipeline(**kw))
    runs, checks = {}, collections.Counter()
    for r in rows:
        rm = run_metrics(ROOT / r["event_log"], ref)
        checks["event_log_matches_runs_csv"] += (
            rm["scheduler"] == r["policy"] and rm["status"] == "completed"
            and abs(rm["makespan_s"] - float(r["makespan_s"])) < 1e-9
            and rm["n_completed"] == rm["n_tasks"] == int(r["n_tasks"])
            and all(rm["tasks_per_pool"].get(p, 0) == int(r[f"tasks_{p}"]) for p in POOLS))
        checks["final_output_exact_vs_reference"] += rm["output_match"] == "exact"
        checks["final_sha_matches_runs_csv"] += rm["output_sha256"] == r["output_sha256"]
        runs[(int(r["repeat"]), r["policy"])] = (r, rm)
    if any(n != 20 for n in checks.values()):
        raise SystemExit(f"{session}: run-level verification failed: {dict(checks)}")

    # profile runs (pool-pinned, NOT part of the primary analysis): task-level reference only
    prof = collections.defaultdict(list)
    for log in sorted((ROOT / "data" / "events" / session).glob("profile_*.jsonl")):
        pm = run_metrics(log, ref)
        if pm["output_match"] != "exact":
            raise SystemExit(f"{log}: profile output not exact")
        for (st, pool, met), vals in pm["m"].items():
            if st in FOCUS and met in ("kernel", "transfer", "io"):
                prof[f"{st}@{pool}:{met}"] += vals

    per_policy, per_run_rows = {}, []
    for pol in (B4, EFT):
        rr = [runs[(i, pol)][1] for i in range(10)]
        stage = {}
        for st in FOCUS:
            stage[st] = {}
            for pool in POOLS:
                d = {met: summ([mean_of(x["m"].get((st, pool, met), [])) for x in rr])
                     for met in ("kernel", "io", "service") + (("transfer",) if pool == "R" else ())}
                d["tasks_total"] = sum(x["placement"][(st, pool)] for x in rr)
                stage[st][pool] = d
        place = collections.Counter()
        for x in rr:
            place.update(x["placement"])
        per_policy[pol] = {
            "runs": 10, "makespan_ms": summ([x["makespan_s"] for x in rr]),
            "total_kernel_ms": summ([x["total_kernel_s"] for x in rr]),
            "scheduling_per_run_ms": summ([x["scheduling_s"] for x in rr]),
            "decision_latency_us": summ([x["decision_mean_s"] for x in rr], scale=1e6),
            "tasks_per_pool_per_run": {p: summ([x["tasks_per_pool"].get(p, 0) for x in rr], scale=1) for p in POOLS},
            "remote_tasks_total": sum(x["tasks_per_pool"].get("R", 0) for x in rr),
            "runs_with_remote": sum(x["tasks_per_pool"].get("R", 0) > 0 for x in rr),
            "placement_total": {f"{s}@{p}": n for (s, p), n in sorted(place.items())},
            "stages": stage}
        if pol == EFT:
            g = [v for x in rr for v in x["gaps"]]
            per_policy[pol]["predicted_remote_minus_best_local_finish_ms"] = {
                **summ(g), "ci95": None, "n_decisions_remote_predicted_better": sum(v < 0 for v in g),
                "note": "task-level, descriptive only (decisions within a run are not independent)"}
        for i in range(10):
            r, x = runs[(i, pol)]
            row = {"k": k, "session": session, "repeat": i, "order_index": int(r["order_index"]), "policy": pol,
                   "makespan_ms": x["makespan_s"] * 1e3, "total_kernel_ms": x["total_kernel_s"] * 1e3,
                   "scheduling_ms": x["scheduling_s"] * 1e3, "decision_mean_us": x["decision_mean_s"] * 1e6,
                   **{f"tasks_{p}": x["tasks_per_pool"].get(p, 0) for p in POOLS},
                   "transfer_total_ms": sum(v for (s, p, met), vals in x["m"].items() if met == "transfer"
                                            for v in vals) * 1e3,
                   "output_match": x["output_match"]}
            for st in FOCUS:
                for pool in POOLS:
                    km = mean_of(x["m"].get((st, pool, "kernel"), []))
                    row[f"{st}_{pool}_kernel_mean_ms"] = None if km is None else km * 1e3
            per_run_rows.append(row)

    # paired B4 vs EFT_E1_rc: per-repeat differences EFT - B4
    paired, paired_rows = {}, []
    for metric, key, scale in (("makespan_ms", "makespan_s", 1e3), ("total_kernel_ms", "total_kernel_s", 1e3),
                               ("scheduling_per_run_ms", "scheduling_s", 1e3)):
        d = [runs[(i, EFT)][1][key] - runs[(i, B4)][1][key] for i in range(10)]
        paired[metric] = {**summ(d, scale), "n_pairs_eft_higher": sum(x > 0 for x in d)}
    d_r = [runs[(i, EFT)][1]["tasks_per_pool"].get("R", 0) - runs[(i, B4)][1]["tasks_per_pool"].get("R", 0)
           for i in range(10)]
    paired["remote_tasks"] = summ(d_r, scale=1)
    lr = [math.log(runs[(i, EFT)][1]["makespan_s"] / runs[(i, B4)][1]["makespan_s"]) for i in range(10)]
    s = summ(lr, scale=1)
    paired["makespan_pct_t"] = {"n": 10, "effect_pct": (math.exp(s["mean"]) - 1) * 100,
                                "ci95_pct": [(math.exp(c) - 1) * 100 for c in s["ci95"]],
                                "method": "paired t-interval on log(EFT/B4) per repeat, back-transformed"}
    blocks = {i: {p: {"makespan_s": runs[(i, p)][1]["makespan_s"]} for p in (B4, EFT)} for i in range(10)}
    paired["makespan_pct_bootstrap"] = {**paired_effect(blocks, EFT, B4, "makespan_s"),
                                        "method": "percentile bootstrap (10,000, seed 0) over log ratios"}
    for i in range(10):
        a, b = runs[(i, EFT)], runs[(i, B4)]
        paired_rows.append({"k": k, "repeat": i, "first": EFT if int(a[0]["order_index"]) == 0 else B4,
                            "b4_makespan_ms": b[1]["makespan_s"] * 1e3, "eft_makespan_ms": a[1]["makespan_s"] * 1e3,
                            "diff_ms": (a[1]["makespan_s"] - b[1]["makespan_s"]) * 1e3,
                            "b4_remote": b[1]["tasks_per_pool"].get("R", 0),
                            "eft_remote": a[1]["tasks_per_pool"].get("R", 0)})

    # transfer vs computation for img_denoise / img_edges, demo runs of both policies (run-level means)
    allr = [runs[(i, p)][1] for i in range(10) for p in (B4, EFT)]
    tvc = {}
    for st in FOCUS:
        def per_run(pool, met):
            return [mean_of(x["m"].get((st, pool, met), [])) for x in allr]
        tvc[st] = {f"{pool}_{met}_ms": summ(per_run(pool, met))
                   for pool in POOLS for met in ("kernel", "io")}
        tvc[st]["R_transfer_ms"] = summ(per_run("R", "transfer"))
        # remote path overhead per task vs computing locally (same run): (R kernel+io+transfer) - (pool kernel+io)
        for loc in ("P", "E"):
            diffs = []
            for x in allr:
                rk, ri, rt = (mean_of(x["m"].get((st, "R", m_), [])) for m_ in ("kernel", "io", "transfer"))
                lk, li = (mean_of(x["m"].get((st, loc, m_), [])) for m_ in ("kernel", "io"))
                if None not in (rk, ri, rt, lk, li):
                    diffs.append((rk + ri + rt) - (lk + li))
            tvc[st][f"remote_path_minus_{loc}_local_ms"] = {
                **summ(diffs), "unit": "run (runs with both a remote and a local task of this stage)"}
        k_e = tvc[st]["E_kernel_ms"].get("mean")
        t_r = tvc[st]["R_transfer_ms"].get("mean")
        tvc[st]["E_kernel_over_R_transfer"] = round(k_e / t_r, 3) if k_e and t_r else None
    return {"k": k, "session": session, "pipeline": kw, "verification": dict(checks),
            "profile_runs_reference_task_level": {key: summ(v) for key, v in sorted(prof.items())},
            "policies": per_policy, "paired_eft_minus_b4": paired, "transfer_vs_compute": tvc}, \
        per_run_rows, paired_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    out = ROOT / ap.parse_args().out_dir
    targets = [out / n for n in ("supplementary_summary.json", "per_run.csv", "paired.csv")]
    if any(t.exists() for t in targets):
        raise SystemExit("outputs exist; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    res, per_run, paired = [], [], []
    for k, s in ACCEPTED.items():
        r, pr, pp = analyze(k, s)
        res.append(r)
        per_run += pr
        paired += pp
    targets[0].write_text(json.dumps({
        "sessions": res, "accepted_sessions": ACCEPTED,
        "excluded_sessions_not_used": ["appdemo_20261003T211356 (verification only)",
                                       "appdemo_20261003T212905", "appdemo_20261003T223138",
                                       "appdemo_20261003T231850 (interrupted)"],
        "methods": {"unit": "run; task timings averaged within each run first",
                    "per_policy_ci": "Student t 95% over 10 runs",
                    "paired_ci": "paired t 95% over 10 per-repeat differences (EFT - B4); "
                                 "log-ratio percentile bootstrap as cross-check",
                    "cross_k": "descriptive only: each k is a separate session (time, thermal, drift confounded)"}},
        indent=1), encoding="utf-8")
    for path, rows in ((targets[1], per_run), (targets[2], paired)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    def ci(d, f="{:.1f}"):
        return f"{f.format(d['mean'])} ± {f.format(d['sd'])} [{f.format(d['ci95'][0])}, {f.format(d['ci95'][1])}]"
    for r in res:
        print(f"\n== k={r['k']} {r['session']}  verification {r['verification']}")
        for pol, d in r["policies"].items():
            print(f"  {pol:21s} makespan {ci(d['makespan_ms'])} ms; total kernel {ci(d['total_kernel_ms'])} ms; "
                  f"decision {ci(d['decision_latency_us'], '{:.1f}')} us; remote/run "
                  f"{d['tasks_per_pool_per_run']['R']['mean']:.1f} ({d['remote_tasks_total']} total)")
        p = r["paired_eft_minus_b4"]
        print(f"  EFT-B4 makespan {ci(p['makespan_ms'])} ms (EFT higher in {p['makespan_ms']['n_pairs_eft_higher']}/10);"
              f" {p['makespan_pct_t']['effect_pct']:+.1f}% t-CI [{p['makespan_pct_t']['ci95_pct'][0]:+.1f},"
              f" {p['makespan_pct_t']['ci95_pct'][1]:+.1f}] boot [{p['makespan_pct_bootstrap']['ci_lo_pct']:+.1f},"
              f" {p['makespan_pct_bootstrap']['ci_hi_pct']:+.1f}]")
        for st, t in r["transfer_vs_compute"].items():
            g = lambda key: f"{t[key]['mean']:.2f}" if t[key].get('n') else "-"
            print(f"  {st:11s} kernel P/E/R {g('P_kernel_ms')}/{g('E_kernel_ms')}/{g('R_kernel_ms')} ms; io P/E/R "
                  f"{g('P_io_ms')}/{g('E_io_ms')}/{g('R_io_ms')}; transfer R {g('R_transfer_ms')} ms; "
                  f"remote-path minus local E {g('remote_path_minus_E_local_ms')} "
                  f"(n={t['remote_path_minus_E_local_ms']['n']}), minus P {g('remote_path_minus_P_local_ms')} "
                  f"(n={t['remote_path_minus_P_local_ms']['n']})")
    print(f"\n-> {', '.join(str(t.relative_to(ROOT)) for t in targets)}")


if __name__ == "__main__":
    main()
