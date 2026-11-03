"""Final study analysis of ONE complete session (docs/final/PROTOCOL_final.md, sections 8 and 9). Reads raw run directories only.

  python scripts/final_analyze.py --session <session_dir> --out <out_dir> [--confirmatory]

Conditions are named ``<policy>_<cfg>`` with cfg in cpu / gpu / ext. Writes:
  policy_table.csv    per condition: n, geometric-mean end-to-end makespan with CI, old-convention makespan, init / policy set-up /
                      scheduling time, queue wait, tasks on CPU and on GPU, GPU busy fraction, CPU utilisation, planned-vs-actual
                      makespan for static plans, output-correct runs
  contrasts.csv       every condition vs the static baseline HEFT_param_model_<cfg> and vs B4_<cfg> of its own configuration, and each
                      policy's gpu / ext configuration vs its cpu configuration; metric makespan_e2e_s and makespan_s; classification
                      per the protocol (EXPLORATORY: unadjusted, CI-based)
  confirmatory.csv    with --confirmatory (primary session only): the ten pre-registered contrasts C1..C10 with Holm-adjusted p
  exclusions.csv      every excluded run and why
  summary.md          the policy table in readable form
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import zlib
from pathlib import Path

from caosched.analysis import stats_paired as sp
from caosched.analysis.stats import holm_adjust, mean_ci, paired_effect
from caosched.core.event_log import read_events

MARGIN = 2.0  # percent; declared in the protocol
PRIMARY, OLD = "makespan_e2e_s", "makespan_s"
CONFIRMATORY = [  # (id, condition, reference) -- protocol section 9
    ("C1", "PRED_RANK_GREEDY_cpu", "B4_cpu"), ("C2", "PRED_RANK_GREEDY_E2E_cpu", "PRED_RANK_GREEDY_cpu"),
    ("C3", "PRED_RANK_GREEDY_cpu", "HEFT_param_model_cpu"), ("C4", "PRED_RANK_GREEDY_E2E_cpu", "HEFT_E2E_cpu"),
    ("C5", "PRED_RANK_GREEDY_gpu", "HEFT_param_model_gpu"), ("C6", "PRED_RANK_GREEDY_E2E_gpu", "HEFT_E2E_gpu"),
    ("C7", "PRED_RANK_GREEDY_E2E_gpu", "PRED_RANK_GREEDY_gpu"), ("C8", "PRED_RANK_GREEDY_gpu", "B4_gpu"),
    ("C9", "PRED_RANK_GREEDY_gpu", "PRED_RANK_GREEDY_cpu"), ("C10", "B4_gpu", "B4_cpu"),
]


def classify(e: dict | None, p_adj: float | None = None) -> str:
    """Protocol rule. ``p_adj`` given -> confirmatory (needs Holm p < 0.05); else descriptive by the CI alone (labelled exploratory)."""
    if e is None:
        return "not enough blocks"
    lo, hi = e["ci_lo_pct"], e["ci_hi_pct"]
    sig = (p_adj < 0.05) if p_adj is not None else True
    if hi < 0 and sig:
        return "faster"
    if lo > 0 and sig:
        return "slower"
    if lo >= -MARGIN and hi <= MARGIN:
        return "equivalent (CI inside +-2%)"
    return "inconclusive"


def _seed(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode()) % 2**31


def log_metrics(run: dict) -> dict:
    """Per-run quantities that need the raw log: tasks per pool class, busy time per pool, planned makespan."""
    lp = Path(run["run_dir"]) / run["manifest"]["event_log"]["path"]
    ev = read_events(lp)
    workers = {e["worker_id"]: e["pool"] for e in ev if e["event"] == "worker_ready"}
    n_pool: dict[str, int] = {}
    for p in workers.values():
        n_pool[p] = n_pool.get(p, 0) + 1
    busy: dict[str, float] = {}
    tasks: dict[str, int] = {}
    for e in ev:
        if e["event"] == "task_completed":
            busy[e["pool"]] = busy.get(e["pool"], 0.0) + (e["t_completed"] - e["t_started"])
            tasks[e["pool"]] = tasks.get(e["pool"], 0) + 1
    ms = run["metrics"].get(OLD)
    cpu_pools = [p for p in n_pool if p in ("P", "E")]
    out = {"tasks_cpu": sum(tasks.get(p, 0) for p in cpu_pools), "tasks_gpu": tasks.get("G", 0),
           "gpu_busy_frac": (busy.get("G", 0.0) / ms) if ms else None,
           "cpu_util": (sum(busy.get(p, 0.0) for p in cpu_pools) / (sum(n_pool[p] for p in cpu_pools) * ms)) if ms and cpu_pools else None}
    sp_ = (run["manifest"].get("extra") or {}).get("static_plan")
    out["planned_makespan_s"] = sp_["planned_makespan_s"] if sp_ else None
    out["plan_over_actual"] = (sp_["planned_makespan_s"] / ms) if sp_ and ms else None
    out["executed_elsewhere"] = sp_["n_executed_elsewhere"] if sp_ else None
    return out


def _gm(vals: list[float], strata: list[str], seed: int) -> dict:
    ci = mean_ci([math.log(v) for v in vals], strata, seed=seed)
    return {"geo_mean_s": math.exp(ci["mean"]), "ci_lo_s": math.exp(ci["ci_lo"]), "ci_hi_s": math.exp(ci["ci_hi"])} if ci else {}


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--confirmatory", action="store_true")
    ap.add_argument("--min-free-gb-sensitivity", type=float, default=1.2)
    a = ap.parse_args(argv)
    runs = sp.load_runs([a.session])
    meta = sp.check_poolable(runs)
    for r in runs:
        r["excluded"] = sp.exclusion_reason(r, PRIMARY)
        if r["metrics"].get(PRIMARY) is not None and r["excluded"] is None:
            r["metrics"].update(log_metrics(r))
    inc = [r for r in runs if not r["excluded"]]
    conds = sorted({r["manifest"]["condition"]["name"] for r in inc})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    with (out / "exclusions.csv").open("x", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["run_id", "condition", "block", "reason"])
        for r in runs:
            if r["excluded"]:
                m = r["manifest"]
                w.writerow([m["run_id"], m["condition"]["name"], m["block"], r["excluded"]])

    rows = []
    for c in conds:
        rs = [r for r in inc if r["manifest"]["condition"]["name"] == c]
        strata = [r["manifest"]["instance"] or "" for r in rs]
        m = [r["metrics"] for r in rs]
        row = {"condition": c, "n": len(rs), **{f"e2e_{k}": v for k, v in _gm([x[PRIMARY] for x in m], strata, _seed("e2e", c)).items()},
               "old_geo_mean_s": math.exp(statistics.fmean(math.log(x[OLD]) for x in m)),
               "init_s": _mean(x["init_s"] for x in m), "policy_setup_s": _mean(x["policy_setup_s"] for x in m),
               "sched_total_s": _mean(x["sched_overhead_total_s"] for x in m), "queue_wait_mean_s": _mean(x["queue_wait_mean_s"] for x in m),
               "tasks_cpu": _mean(x["tasks_cpu"] for x in m), "tasks_gpu": _mean(x["tasks_gpu"] for x in m),
               "gpu_busy_frac": _mean(x["gpu_busy_frac"] for x in m), "cpu_util": _mean(x["cpu_util"] for x in m),
               "plan_over_actual": _mean(x["plan_over_actual"] for x in m), "executed_elsewhere_mean": _mean(x["executed_elsewhere"] for x in m),
               "output_ok": sum(1 for r in rs if r["manifest"]["verification"]["passed"]) , "n_excluded": sum(
                   1 for r in runs if r["excluded"] and r["manifest"]["condition"]["name"] == c and not r["manifest"]["warmup"])}
        rows.append(row)
    _csv(out / "policy_table.csv", rows)

    blocks = sp._blocks(inc)
    pairs = []
    for c in conds:
        cfg = c.rsplit("_", 1)[1]
        pol = c.rsplit("_", 1)[0]
        for ref in (f"HEFT_param_model_{cfg}", f"B4_{cfg}"):
            if ref in conds and ref != c:
                pairs.append((c, ref, "within configuration"))
        if cfg != "cpu" and f"{pol}_cpu" in conds:
            pairs.append((c, f"{pol}_cpu", "configuration effect"))
        if cfg == "ext" and f"{pol}_gpu" in conds:
            pairs.append((c, f"{pol}_gpu", "extended vs strict GPU set"))
    crow = []
    for c, ref, kind in dict.fromkeys(pairs):
        for metric in (PRIMARY, OLD):
            e = paired_effect(blocks, c, ref, metric, seed=_seed("x", c, ref, metric))
            crow.append({"cond": c, "ref": ref, "kind": kind, "metric": metric, "tier": "exploratory (unadjusted)",
                         "n_blocks": e["n_blocks"] if e else 0, **({k: e[k] for k in ("effect_pct", "ci_lo_pct", "ci_hi_pct", "p_perm")} if e else {}),
                         "classification": classify(e)})
    _csv(out / "contrasts.csv", crow)

    if a.confirmatory:
        res = []
        for cid, c, ref in CONFIRMATORY:
            e = paired_effect(blocks, c, ref, PRIMARY, seed=_seed("conf", cid))
            res.append({"id": cid, "cond": c, "ref": ref, "metric": PRIMARY, "n_blocks": e["n_blocks"] if e else 0,
                        **({k: e[k] for k in ("effect_pct", "ci_lo_pct", "ci_hi_pct", "p_perm")} if e else {})})
        ok = [r for r in res if "p_perm" in r]
        for r, p in zip(ok, holm_adjust([r["p_perm"] for r in ok])):
            r["p_holm"] = p
        for r in res:
            r["classification"] = classify(r if "ci_lo_pct" in r else None, r.get("p_holm"))
        _csv(out / "confirmatory.csv", res)

    # sensitivity: runs that started with little free RAM
    low = []
    for r in inc:
        try:
            first = json.loads((Path(r["run_dir"]) / r["manifest"]["event_log"]["path"]).open(encoding="utf-8").readline())
            if first.get("memory_available_bytes", 1e18) < a.min_free_gb_sensitivity * 2**30:
                low.append(r["manifest"]["run_id"])
        except (OSError, ValueError):
            pass
    (out / "meta.json").write_text(json.dumps({**meta, "session": str(a.session), "primary_metric": PRIMARY, "margin_pct": MARGIN,
                                               "n_runs": len(runs), "n_included": len(inc), "runs_started_with_low_free_ram": len(low),
                                               "low_ram_threshold_gb": a.min_free_gb_sensitivity}, indent=1), encoding="utf-8")
    with (out / "summary.md").open("x", encoding="utf-8") as fh:
        fh.write("| condition | n | e2e makespan s [95% CI] | setup s | sched s | tasks CPU/GPU | GPU busy | out ok |\n|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            busy = "" if r["gpu_busy_frac"] is None else format(r["gpu_busy_frac"], ".2f")   # no nested f-string: Python 3.11 here
            fh.write(f"| {r['condition']} | {r['n']} | {r['e2e_geo_mean_s']:.3f} [{r['e2e_ci_lo_s']:.3f}, {r['e2e_ci_hi_s']:.3f}] | "
                     f"{(r['policy_setup_s'] or 0):.4f} | {(r['sched_total_s'] or 0):.4f} | {(r['tasks_cpu'] or 0):.0f}/{(r['tasks_gpu'] or 0):.0f} | "
                     f"{busy} | {r['output_ok']}/{r['n']} |\n")
    print(f"wrote {out}; {len(inc)} of {len(runs)} runs included; {len(low)} started with < {a.min_free_gb_sensitivity} GB free RAM")
    return 0


def _csv(path: Path, rows: list[dict]) -> None:
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, cols, restval="")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
