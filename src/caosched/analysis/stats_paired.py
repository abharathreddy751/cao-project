"""Stage 4 analysis from raw run directories (event logs + run manifests) only.

Per run (from the raw event log): makespan, task time, queue wait, scheduling/inference overhead
(``decision_time_s`` = scheduler decision incl. estimator inference; not separable in the log), transfer,
utilisation (busy time / workers x makespan, only if worker_ready + t_started/t_completed are logged),
memory available at start; correctness comes from the run manifest. Absent quantities are None = 'not measured'.

Paired within-block log-ratios against the design's reference condition, stratified (by instance) percentile
bootstrap (``analysis.stats``), per-metric seeds, effect size dz = mean/sd of the log-ratio, spread, the 95%
CI half-width and the minimum detectable effect (alpha 0.05, 80% power: ``mde_pct_80power``) for the achieved
block count, a sensitivity pass that includes every run that has a value (excluded runs too, but not runs of
incomplete sessions), and a Friedman/Wilcoxon cross-check only if scipy is importable.
Runs from different machine ids, environment hashes, evidence labels, design hashes or code versions
(``src_sha256``, unless ``allow_mixed_code``) are never pooled. Sessions whose ``session.json`` is missing or
not 'complete' with every block done are excluded, with the reason in the exclusion table.

Summaries are per instance (absolute seconds); pooled statements use the log scale (geometric mean). Multiplicity:
the confirmatory family is the primary variant's makespan contrasts against the reference, Holm-adjusted
(``p_holm``, from sign-flip p-values); every other metric/variant is labelled ``exploratory`` and unadjusted.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import zlib
from pathlib import Path

import numpy as np

from caosched.analysis.stats import ci_halfwidth_pct, holm_adjust, mean_ci, min_detectable_effect_pct, paired_effect
from caosched.experiment.manifest import sha256_file

NOT_MEASURED = "not measured"
METRICS = ("makespan_s", "task_time_total_s", "queue_wait_total_s", "sched_overhead_total_s", "transfer_total_s")


class PoolingError(ValueError):
    pass


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def run_metrics(events: list[dict]) -> dict:
    fin = next((e for e in reversed(events) if e["event"] == "run_finished"), None)
    comp = [e for e in events if e["event"] == "task_completed"]
    disp = [e for e in events if e["event"] == "task_dispatched"]
    subm = [e for e in events if e["event"] == "task_submitted"]
    ok_run = fin is not None and fin.get("status") == "completed"
    ms = fin.get("makespan_seconds") if fin is not None and ok_run else None
    qw = [_sum([e.get("queue_wait_seconds") for e in disp]), _sum([e.get("local_queue_wait_seconds") for e in subm])]
    qtot = _sum(qw)
    dts = [e["decision_time_s"] for e in disp if e.get("decision_time_s") is not None]
    nworkers = sum(1 for e in events if e["event"] == "worker_ready")
    busy = [e["t_completed"] - e["t_started"] for e in comp if e.get("t_started") is not None and e.get("t_completed") is not None]
    start = next((e for e in events if e["event"] == "run_started"), {})
    return {
        "makespan_s": ms, "n_tasks_completed": len(comp),
        "task_time_total_s": _sum([e.get("wall_time_seconds") for e in comp]),
        "task_time_mean_s": statistics.fmean([e["wall_time_seconds"] for e in comp]) if comp else None,
        "queue_wait_total_s": qtot, "queue_wait_mean_s": qtot / len(disp) if qtot is not None and disp else None,
        "sched_overhead_total_s": sum(dts) if dts else None,
        "sched_overhead_per_decision_s": statistics.fmean(dts) if dts else None,
        "transfer_total_s": _sum([e.get("transfer_s") for e in comp]),
        "utilisation": sum(busy) / (nworkers * ms) if ms and nworkers and busy else None,
        "memory_available_start_bytes": start.get("memory_available_bytes"),
    }


def _unique_paths(paths) -> list[Path]:
    seen, out = set(), []
    for p in map(Path, paths):
        if p.resolve() not in seen:  # the same session listed twice must not double its runs
            seen.add(p.resolve())
            out.append(p)
    return out


def _session_problem(sd: Path) -> str | None:
    """Why this session's runs cannot be used as evidence (None if session.json says complete and whole)."""
    try:
        s = json.loads((sd / "session.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "session.json missing or unreadable (crashed or foreign session)"
    if s.get("status") != "complete":
        return f"session {s.get('status')}: {s.get('reason')}"
    if s.get("n_blocks") is None or s.get("blocks_completed") != s["n_blocks"]:
        return f"session incomplete: {s.get('blocks_completed')} of {s.get('n_blocks')} blocks"
    return None


def load_runs(paths) -> list[dict]:
    """Every run under the given session directories: manifest fields + raw-log metrics + log integrity +
    ``session_problem`` (None for runs of complete sessions). Run ids must be unique across the sessions."""
    runs = []
    for sd in _unique_paths(paths):
        problem = _session_problem(sd)
        for mp in sorted(sd.glob("runs/*/run_manifest.json")):
            m = json.loads(mp.read_text(encoding="utf-8"))
            log = m.get("event_log")
            lp = mp.parent / log["path"] if log else None
            log_ok = bool(lp and lp.is_file() and sha256_file(lp) == log["sha256"])
            met = {}
            if lp and lp.is_file():
                met = run_metrics([json.loads(ln) for ln in lp.read_text(encoding="utf-8").splitlines() if ln.strip()])
            runs.append({"manifest": m, "metrics": met, "log_ok": log_ok, "run_dir": mp.parent.as_posix(),
                         "session_problem": problem})
    ids = [r["manifest"]["run_id"] for r in runs]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"duplicate run_id across sessions (same session given twice under another path?): {dup[:5]}")
    return runs


def check_poolable(runs: list[dict], allow_mixed_code: bool = False) -> dict:
    if not runs:
        raise ValueError("no runs found")
    meta = {}
    for key, getter in (("machine_id", lambda m: m["machine_id"]), ("environment_hash", lambda m: m["environment_hash"]),
                        ("evidence_label", lambda m: m["evidence_label"]), ("design_sha256", lambda m: m["design"]["sha256"])):
        vals = sorted({getter(r["manifest"]) for r in runs})
        if len(vals) > 1:
            raise PoolingError(f"refusing to pool runs with different {key}: {vals}")
        meta[key] = vals[0]
    code = sorted({r["manifest"]["code"]["src_sha256"] for r in runs})
    if len(code) > 1 and not allow_mixed_code:
        raise PoolingError(f"refusing to pool runs from different code versions (src_sha256): {[c[:12] for c in code]}; "
                           "pass allow_mixed_code=True (--allow-mixed-code) to override")
    meta["code_versions"] = [c[:12] for c in code]
    meta["allow_mixed_code"] = allow_mixed_code
    return meta


def exclusion_reason(r: dict) -> str | None:
    m = r["manifest"]
    if r.get("session_problem"):
        return r["session_problem"]
    if m["status"] != "ok":
        return f"run {m['status']}: {m.get('error')}"
    if not r["log_ok"]:
        return "event log missing or hash mismatch"
    ok = m["verification"]["passed"]
    if ok is None:
        return "output not verified"
    if not ok:
        return "output verification failed"
    if r["metrics"].get("makespan_s") is None:
        return "run did not complete (no makespan)"
    if m["warmup"]:
        return "warm-up block (design rule)"
    return None


def _seed(base, *parts) -> int:
    return (base + zlib.crc32("|".join(parts).encode())) % 2**31


def _blocks(runs):
    blocks = {}
    for r in runs:
        m = r["manifest"]
        blocks.setdefault((f"{m['session_id']}/b{m['block']}", m["instance"] or ""), {})[m["condition"]["name"]] = r["metrics"]
    return blocks


def _num(v):
    return NOT_MEASURED if v is None else v


def analyze(paths, reference: str | None = None, seed: int = 0, allow_mixed_code: bool = False) -> dict:
    paths = _unique_paths(paths)
    runs = load_runs(paths)
    meta = check_poolable(runs, allow_mixed_code)
    reference = reference or runs[0]["manifest"]["design"]["reference"]
    if not reference:
        raise ValueError("no reference condition: set 'reference' in the design or pass one")
    for r in runs:
        r["excluded"] = exclusion_reason(r)
    conds = sorted({r["manifest"]["condition"]["name"] for r in runs})
    if reference not in conds:
        raise ValueError(f"reference {reference!r} has no runs")
    primary = [r for r in runs if not r["excluded"]]
    sens = [r for r in runs if r["metrics"].get("makespan_s") is not None and not r["session_problem"]]

    run_rows = []
    for r in runs:
        m = r["manifest"]
        run_rows.append({"run_id": m["run_id"], "block": m["block"], "instance": m["instance"] or "",
                         "condition": m["condition"]["name"], "policy": m["policy"], "seed": m["seed"],
                         "status": m["status"], "output_ok": m["verification"]["passed"], "log_ok": r["log_ok"],
                         "included_primary": r["excluded"] is None, "exclusion_reason": r["excluded"] or "",
                         **{k: _num(v) for k, v in r["metrics"].items()}, "evidence_label": meta["evidence_label"]})
    excl_rows = [{"run_id": x["run_id"], "condition": x["condition"], "block": x["block"], "reason": x["exclusion_reason"]}
                 for x in run_rows if x["exclusion_reason"]]

    # Absolute makespans are only comparable within an instance: one row per (condition, instance), plus one
    # pooled row per condition on the log scale (geometric mean, bootstrap stratified by instance).
    summary = []
    for c in conds:
        rs_c = [r for r in primary if r["manifest"]["condition"]["name"] == c]
        scopes = [(inst, [r for r in rs_c if (r["manifest"]["instance"] or "") == inst], "per_instance")
                  for inst in sorted({r["manifest"]["instance"] or "" for r in rs_c})]
        scopes.append(("all", rs_c, "pooled_log_scale"))
        for inst, rs, scope in scopes:
            ms = [r["metrics"]["makespan_s"] for r in rs]
            row = {"condition": c, "instance": inst, "scope": scope, "n": len(ms), "evidence_label": meta["evidence_label"]}
            if ms and scope == "per_instance":
                ci = mean_ci(ms, seed=_seed(seed, "summary", c, inst))
                assert ci is not None  # ms is non-empty
                sd = statistics.stdev(ms) if len(ms) > 1 else None
                row.update(mean_s=ci["mean"], ci_lo_s=ci["ci_lo"], ci_hi_s=ci["ci_hi"], median_s=statistics.median(ms),
                           sd_s=_num(sd), cv=_num(sd / ci["mean"] if sd else None), min_s=min(ms), max_s=max(ms))
            elif ms:
                logs = [math.log(v) for v in ms]
                ci = mean_ci(logs, [r["manifest"]["instance"] or "" for r in rs], seed=_seed(seed, "summary", c, "all"))
                assert ci is not None  # ms is non-empty
                row.update(geo_mean_s=math.exp(ci["mean"]), ci_lo_s=math.exp(ci["ci_lo"]), ci_hi_s=math.exp(ci["ci_hi"]),
                           mean_log_s=ci["mean"], ci_lo_log_s=ci["ci_lo"], ci_hi_log_s=ci["ci_hi"],
                           sd_log_s=_num(statistics.stdev(logs) if len(logs) > 1 else None))
            if ms:  # sums over tasks = task-seconds, not wall time
                for k in ("task_time_total_s", "queue_wait_total_s", "sched_overhead_total_s",
                          "sched_overhead_per_decision_s", "transfer_total_s", "utilisation"):
                    vals = [r["metrics"][k] for r in rs if r["metrics"].get(k) is not None]
                    row[f"{k}_mean"] = statistics.fmean(vals) if vals else NOT_MEASURED
            summary.append(row)

    effects = []
    for variant, rs in (("primary", primary), ("sensitivity_all_runs", sens)):
        blocks = _blocks(rs)
        for metric in METRICS:
            for c in conds:
                if c == reference:
                    continue
                e = paired_effect(blocks, c, reference, metric, seed=_seed(seed, metric, c, variant))
                row = {"variant": variant, "metric": metric, "cond": c, "ref": reference,
                       "tier": "confirmatory" if (variant, metric) == ("primary", "makespan_s") else "exploratory",
                       "evidence_label": meta["evidence_label"]}
                if e is None:
                    row.update(n_blocks=sum(1 for b in blocks.values() if b.get(c, {}).get(metric) and b.get(reference, {}).get(metric)),
                               note="fewer than 3 paired blocks or metric not measured")
                else:
                    sd = e["sd_log"]
                    e.pop("cond"), e.pop("ref"), e.pop("metric")
                    row.update(e, dz=math.log1p(e["effect_pct"] / 100) / sd if sd > 0 else NOT_MEASURED,
                               ci_halfwidth_pct=ci_halfwidth_pct(sd, e["n_blocks"]),
                               mde_pct_80power=min_detectable_effect_pct(sd, e["n_blocks"]))
                effects.append(row)
    fam = [e for e in effects if e["tier"] == "confirmatory" and "p_perm" in e]  # Holm across the confirmatory family
    for e, p in zip(fam, holm_adjust([e["p_perm"] for e in fam])):
        e["p_holm"] = p
        e["significant_holm_05"] = p < 0.05

    return {"meta": {**meta, "reference": reference, "seed": seed, "n_boot": 10000, "paths": [str(p) for p in paths],
                     "n_runs": len(runs), "n_included_primary": len(primary), "n_excluded": len(excl_rows),
                     "not_measured_note": "metrics shown as 'not measured' are absent from the raw logs; "
                                          "sched_overhead includes estimator inference (not separable in the log)",
                     "multiplicity_note": "confirmatory family = primary variant, makespan_s, every condition vs the reference "
                                          "(Holm over sign-flip p-values: p_holm); all other rows are exploratory, unadjusted"},
            "tables": {"runs": run_rows, "exclusions": excl_rows, "summary": summary, "effects": effects,
                       "crosscheck": _crosscheck(_blocks(primary), conds, reference)}}


def _crosscheck(blocks, conds, ref) -> list[dict]:
    try:
        from scipy import stats as ss
    except ImportError:
        return [{"test": "friedman/wilcoxon", "note": "scipy not available; skipped"}]
    full = [b for b in blocks.values() if all(b.get(c, {}).get("makespan_s") for c in conds)]
    out = []
    if len(conds) >= 3 and len(full) >= 3:
        s, p = ss.friedmanchisquare(*[[b[c]["makespan_s"] for b in full] for c in conds])
        out.append({"test": "friedman", "cond": "all", "n_blocks": len(full), "statistic": float(s), "p_value": float(p)})
    for c in conds:
        if c != ref and len(full) >= 6:
            s, p = ss.wilcoxon([b[c]["makespan_s"] for b in full], [b[ref]["makespan_s"] for b in full])
            out.append({"test": "wilcoxon_vs_ref", "cond": c, "n_blocks": len(full), "statistic": float(s), "p_value": float(p),
                        "multiplicity": "unadjusted (cross-check only)"})
    return out or [{"test": "friedman/wilcoxon", "note": "too few complete blocks"}]


def write_tables(result: dict, outdir) -> list[Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows in result["tables"].items():
        p = outdir / f"{name}.csv"
        cols = list(dict.fromkeys(k for r in rows for k in r))
        with p.open("w", newline="", encoding="utf-8") as fh:  # derived files: re-derivable, so replaceable
            w = csv.DictWriter(fh, cols, restval="")
            w.writeheader()
            w.writerows(rows)
        written.append(p)
    pj = outdir / "analysis.json"
    pj.write_text(json.dumps(result["meta"], indent=2), encoding="utf-8")
    return written + [pj]


def make_figures(result: dict, outdir) -> list[Path]:
    """Three figures, each tagged with the evidence label. Needs matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir, tag = Path(outdir), f"evidence: {result['meta']['evidence_label']}"
    summ = [r for r in result["tables"]["summary"] if r.get("scope") == "pooled_log_scale" and "geo_mean_s" in r]
    out = []

    def save(fig, name, title):
        fig.suptitle(title, fontsize=10)
        fig.text(0.01, 0.01, tag, fontsize=8, style="italic")
        p = outdir / name
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        out.append(p)

    names = [r["condition"] for r in summ]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.errorbar(names, [r["geo_mean_s"] for r in summ], yerr=[[r["geo_mean_s"] - r["ci_lo_s"] for r in summ],
                [r["ci_hi_s"] - r["geo_mean_s"] for r in summ]], fmt="o", capsize=4)
    ax.set_ylabel("makespan (s), geometric mean and 95% CI\n(log scale, bootstrap stratified by instance)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    save(fig, "fig_makespan_by_policy.png", "Makespan by policy (pooled over instances, log scale)")

    fig, ax = plt.subplots(figsize=(6, 3.5))
    bottom = np.zeros(len(summ))
    drawn = False
    for k, lab in (("sched_overhead_total_s_mean", "scheduling/inference"), ("queue_wait_total_s_mean", "queue wait"),
                   ("transfer_total_s_mean", "transfer")):
        ok = [i for i, r in enumerate(summ) if isinstance(r.get(k), (int, float))]  # only measured components
        if ok:
            v = np.array([summ[i][k] for i in ok])
            ax.bar([names[i] for i in ok], v, bottom=bottom[ok], label=lab)
            bottom[ok] += v
            drawn = True
    if drawn:
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "no overhead component was measured", ha="center", va="center", transform=ax.transAxes)
    ax.set_ylabel("task-seconds per run (sum over tasks, not wall time)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    save(fig, "fig_overhead_breakdown.png", "Overhead breakdown (measured components only; omitted = not measured)")

    eff = [e for e in result["tables"]["effects"] if e["variant"] == "primary" and e["metric"] == "makespan_s" and "effect_pct" in e]
    fig, ax = plt.subplots(figsize=(6, 0.6 * len(eff) + 1.5))
    ax.errorbar([e["effect_pct"] for e in eff], range(len(eff)),
                xerr=[[e["effect_pct"] - e["ci_lo_pct"] for e in eff], [e["ci_hi_pct"] - e["effect_pct"] for e in eff]],
                fmt="o", capsize=4)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_yticks(range(len(eff)), [e["cond"] for e in eff])
    ax.set_xlabel(f"makespan change vs {result['meta']['reference']} (%), paired, 95% CI")
    save(fig, "fig_effect_vs_baseline.png", "Effect relative to the reference baseline")
    return out
