"""Phase 6B: core experiment matrix (interleaved, randomized, repeated).

One worker pool for the whole session (2 P + 6 E + remote node R0 behind the
link shim). A *block* = one (repeat, trace); within a block every condition
(local policies with R unused, and remote-capable policies per link) runs
once, in a fresh seeded random order; the link shim is switched per run
(``WorkerPool.set_link``). Trace order is shuffled per repeat. Paired
analysis within blocks cancels session drift shared by the block.

O (oracle replay) uses an E5 table built only from runs completed earlier in
this session (seed stage + previous runs) -- information that exists at that
time, never the current run.

Analysis (from logs, streamed one log at a time; ``--analyze-only EXP_ID``):
  * paired effects vs the reference and configured contrasts on makespan,
    mean response time and throughput: % with bootstrap 95% CI over blocks
  * scheduling overhead (time inside the policy per decision / per run)
  * offload overhead (measured transfer per offloaded task / per run)
  * prediction error of the chosen worker's exec (and transfer) prediction
  * placement regret (kernel and e2e yardsticks; local-condition runs, E5
    leave-run-out over this session's local runs) and regret vs decision
    margin

Usage:  python scripts/run_phase6b.py [--config config/phase6b.yaml] [--repeats N]
        python scripts/run_phase6b.py --analyze-only phase6b_<stamp>
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import platform
import random
import statistics
import sys
from pathlib import Path

import psutil
import yaml

from caosched.analysis.decisions import decision_rows
from caosched.analysis.stats import mean_ci, min_detectable_effect_pct, paired_effect
from caosched.core.coordinator import Coordinator, pin_coordinator_to_reserved_core
from caosched.core.event_log import DEFAULT_OUTPUT_DIR as EVENTS_DIR
from caosched.core.event_log import EventLogger, read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.trace import dag_from_trace, load_or_create_trace
from caosched.core.worker_pool import RemoteSlot, WorkerPool
from caosched.dataset.events import rows_from_events
from caosched.estimators import EndToEndTerms, ReplayOracleEstimator
from caosched.remote.link import LinkConfig, TransferModel
from caosched.schedulers import eft_factories
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.simple import GreedyEligibleScheduler, PoolOnlyScheduler

RESULTS = Path(__file__).resolve().parents[1] / "data" / "results"
RUN_FIELDS = ["stage", "repeat", "trace", "condition", "policy", "link", "order_index", "status", "n_tasks",
              "makespan_s", "mean_response_s", "throughput_tps", "scheduling_time_s", "n_decisions",
              "mean_decision_time_s", "tasks_P", "tasks_E", "tasks_R", "transfer_total_s", "event_log",
              "coordinator_rss_mib"]  # last column added after phase6b_20261003T162145 (memory diagnostics)
DEC_FIELDS = ["condition", "repeat", "trace", "run_id", "policy", "task_id", "workload", "size", "chosen_pool",
              "actual_kernel_s", "pred_exec", "pred_wait", "pred_finish", "pred_margin", "regret_s", "optimal",
              "regret_e2e_s", "optimal_e2e", "bind_delay_s", "n_candidates"]
LOCAL = ["P", "E"]


def is_remote_condition(name: str) -> bool:
    return "_R@" in name


def load_yaml(p) -> dict:
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


def build_conditions(cfg, profile, est_cfg, e2e, model) -> dict:
    """condition name -> (factory, link or None)."""
    conds = {}
    for n in cfg["local"]["baselines"]:
        if n == "B4_greedy_eligible":
            conds[n] = (lambda: GreedyEligibleScheduler(priority=["P", "E"]), None)
        elif n.startswith("B0_"):
            conds[n] = ((lambda p=n.split("_")[1]: PoolOnlyScheduler(p)), None)
        else:
            raise ValueError(f"unknown local baseline {n}")
    for name, f in eft_factories(cfg["local"]["eft"], profile, est_cfg, model, e2e_terms=e2e,
                                 allowed_pools=LOCAL).items():
        conds[name] = (f, None)
    if cfg["local"].get("oracle"):
        conds["O_eft_E5"] = ("ORACLE", None)
    for lname, l in cfg["remote"]["links"].items():
        link = LinkConfig(lname, **l)
        if cfg["remote"].get("greedy"):
            nm = f"B4_greedy_eligible_R@{lname}"
            conds[nm] = ((lambda nm=nm: GreedyEligibleScheduler(priority=["P", "E", "R"], name=nm)), link)
        tm = TransferModel.with_profile_calibration({"R": link}, profile)
        for name, f in eft_factories(cfg["remote"]["eft"], profile, est_cfg, model, e2e_terms=e2e, transfer=tm,
                                     allowed_pools=["P", "E", "R"], name_suffix=f"_R@{lname}").items():
            conds[name] = (f, link)
    return conds


def run_once(pool, trace, policy, link, meta, events_dir, timeout, writer, fh, oracle) -> dict:
    if link is not None:
        pool.set_link("R0", link)
    run_id = f"{meta['stage']}__{trace['name']}__{policy.name}__r{meta['repeat']}"
    with EventLogger(run_id, output_dir=events_dir) as logger:
        s = Coordinator(dag_from_trace(trace), pool, policy, logger, run_metadata={
            **meta, "trace": trace["name"], "condition": policy.name,
            "link": link.to_dict() if link else None}).run(run_timeout=timeout)
    ev = read_events(logger.path)
    # O's replay table grows only *between* runs (here), so an O run sees exactly the runs completed
    # before it -- same semantics as the original per-run copy, without copying or keeping row dicts.
    specs = ev[0]["tasks"]
    for e in ev:
        if e["event"] == "task_completed" and e["pool"] in LOCAL:
            sp = specs[e["task_id"]]
            oracle.add(ev[0]["run_id"], e["task_id"], sp["seed"], sp["workload"], sp["size"], e["pool"],
                       e["wall_time_seconds"])
    dts = [e["decision_time_s"] for e in ev if e["event"] == "task_dispatched" and e.get("decision_time_s") is not None]
    tr = sum(e.get("transfer_s") or 0.0 for e in ev if e["event"] == "task_completed")
    row = {"stage": meta["stage"], "repeat": meta["repeat"], "trace": trace["name"], "condition": policy.name,
           "policy": policy.name, "link": link.name if link else "", "order_index": meta["order_index"],
           "status": s.status, "n_tasks": s.n_tasks, "makespan_s": s.makespan_seconds,
           "mean_response_s": s.mean_response_time_seconds, "throughput_tps": s.n_tasks / s.makespan_seconds,
           "scheduling_time_s": s.scheduling_time_seconds, "n_decisions": len(dts),
           "mean_decision_time_s": statistics.fmean(dts) if dts else None,
           "tasks_P": s.tasks_per_pool.get("P", 0), "tasks_E": s.tasks_per_pool.get("E", 0),
           "tasks_R": s.tasks_per_pool.get("R", 0), "transfer_total_s": tr,
           "event_log": str(logger.path.relative_to(EVENTS_DIR.parent)),
           "coordinator_rss_mib": psutil.Process().memory_info().rss / 2**20}
    del ev
    writer.writerow(row)
    fh.flush()
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase6b.yaml")
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--analyze-only", default=None, metavar="EXP_ID")
    ap.add_argument("--block-filter", default="full_repeats", choices=["full_repeats", "complete_blocks"])
    ap.add_argument("--tag", default="", help="suffix for analysis outputs (never overwrites)")
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    if args.analyze_only:
        analyze(args.analyze_only, cfg, args.block_filter, args.tag)
        return
    exp = cfg["experiment"]
    repeats = args.repeats or exp["repeats"]
    profile, model = Path(cfg["profile"]), Path(cfg["e4_model"])
    e2e = EndToEndTerms.load(Path(cfg["e2e_terms"]))
    est_cfg = {**load_yaml(cfg["estimator_config"])["estimators"], "rc": cfg["rc"]}
    traces = [load_or_create_trace(spec)[0] for spec in load_yaml(cfg["traces_from"])["traces"]]
    conds = build_conditions(cfg, profile, est_cfg, e2e, model)

    min_gib = exp.get("min_available_gib", 1.0)
    avail = psutil.virtual_memory().available / 2**30
    if avail < min_gib:
        raise SystemExit(f"Refusing to start: {avail:.2f} GiB available < {min_gib} GiB "
                         f"(experiment.min_available_gib); free memory first")
    rc = RuntimeConfig.from_topology()
    coord_core = pin_coordinator_to_reserved_core(rc)
    node = cfg["remote"]["node_core"]
    e_slots = [c for c in rc.e_core_slots if c != node]
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    exp_id = f"phase6b_{stamp}"
    events_dir = EVENTS_DIR / exp_id
    rng = random.Random(exp["order_seed"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{exp_id}_manifest.json").write_text(json.dumps({
        "experiment_id": exp_id, "config_path": args.config, "config": cfg, "conditions": list(conds),
        "repeats": repeats, "n_blocks": repeats * len(traces), "p_slots": list(rc.p_core_slots), "e_slots": e_slots,
        "remote_node_core": node, "coordinator_core": coord_core, "python": sys.version,
        "platform": platform.platform(),
        "design": "single pool; blocks = (repeat, trace); all conditions once per block in seeded random order; "
                  "trace order shuffled per repeat; link shim switched per run"}, indent=1), encoding="utf-8")
    print(f"{exp_id}: {len(conds)} conditions x {repeats} repeats x {len(traces)} traces "
          f"= {len(conds) * repeats * len(traces)} runs (+ seed stage)", flush=True)

    oracle = ReplayOracleEstimator({})  # compact (key -> [(run_id, kernel_s)]) table, grows between runs
    first_link = next(l for _, l in conds.values() if l is not None)
    slots = [RemoteSlot(first_link, node_core=node, proxy_core=cfg["remote"]["proxy_core"])]
    with WorkerPool(list(rc.p_core_slots), e_slots, warmup=True, strict_affinity=True, remote_slots=slots) as pool, \
            (RESULTS / f"{exp_id}_runs.csv").open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RUN_FIELDS)
        w.writeheader()
        seed_pols = cfg["seed_stage"]["policies"]
        for k in range(cfg["seed_stage"]["repeats_per_trace"]):
            for trace in traces:
                for i, n in enumerate(seed_pols):
                    run_once(pool, trace, PoolOnlyScheduler(n.split("_")[1]), None,
                             {"experiment_id": exp_id, "stage": "seed", "repeat": k, "order_index": i},
                             events_dir, exp["run_timeout_s"], w, fh, oracle)
        print("  seed stage done", flush=True)
        for rep in range(repeats):
            order_t = list(traces)
            rng.shuffle(order_t)
            for trace in order_t:
                names = list(conds)
                rng.shuffle(names)
                for idx, name in enumerate(names):
                    factory, link = conds[name]
                    if factory == "ORACLE":
                        pol = EarliestFinishTimeScheduler(ReplayOracleEstimator(oracle.obs),
                                                          "O_eft_E5", allowed_pools=LOCAL)
                    else:
                        pol = factory()
                    run_once(pool, trace, pol, link,
                             {"experiment_id": exp_id, "stage": "block", "repeat": rep, "order_index": idx},
                             events_dir, exp["run_timeout_s"], w, fh, oracle)
            print(f"  repeat {rep + 1}/{repeats} done  (available memory "
                  f"{psutil.virtual_memory().available / 2**30:.2f} GiB)", flush=True)
    analyze(exp_id, cfg)


def _run_log_metrics(ev: list[dict]) -> dict:
    """Prediction error of the chosen worker (exec, transfer) for one run."""
    disp = {e["task_id"]: e for e in ev if e["event"] == "task_dispatched"}
    ap, bi, tq = [], [], []
    for e in ev:
        if e["event"] != "task_completed":
            continue
        dec = disp[e["task_id"]].get("decision")
        if not dec:
            continue
        ch = dec["candidates"][e["worker_id"]]
        ap.append(abs(ch["exec"] - e["wall_time_seconds"]) / e["wall_time_seconds"])
        bi.append((ch["exec"] - e["wall_time_seconds"]) / e["wall_time_seconds"])
        if e.get("transfer_s") and ch.get("transfer"):
            tq.append(e["transfer_s"] / ch["transfer"])
    return {"ape": statistics.median(ap) if ap else None, "bias": statistics.median(bi) if bi else None,
            "transfer_ratio": statistics.median(tq) if tq else None}


def select_blocks(runs: list[dict], conds_expected: int, block_filter: str) -> tuple[list[dict], dict]:
    """Keep only analysable blocks. ``complete_blocks``: every condition ran
    in the block. ``full_repeats``: additionally every trace of the repeat is
    a complete block (balanced design). Returns (kept block runs, exclusion report)."""
    block_runs = [r for r in runs if r["stage"] == "block"]
    per_block: dict = {}
    for r in block_runs:
        per_block.setdefault((r["repeat"], r["trace"]), []).append(r)
    complete = {k for k, v in per_block.items() if len({x["condition"] for x in v}) == conds_expected}
    traces = {k[1] for k in per_block}
    if block_filter == "full_repeats":
        keep = {k for k in complete if all((k[0], t) in complete for t in traces)}
    elif block_filter == "complete_blocks":
        keep = set(complete)
    else:
        raise ValueError(f"unknown block filter {block_filter!r}")
    excluded = [{"repeat": k[0], "trace": k[1], "runs": len(v),
                 "reason": "incomplete block" if k not in complete else "block of a partial repeat (balanced design)"}
                for k, v in sorted(per_block.items()) if k not in keep]
    kept_runs = [r for r in block_runs if (r["repeat"], r["trace"]) in keep]
    full_reps = sorted({k[0] for k in keep if all((k[0], t) in keep for t in traces)}, key=int)
    return kept_runs, {"block_filter": block_filter, "blocks_total": len(per_block), "blocks_complete": len(complete),
                       "blocks_kept": len(keep), "full_repeats_kept": len(full_reps), "excluded_blocks": excluded}


def _oracle_tables(runs: list[dict]) -> tuple[ReplayOracleEstimator, ReplayOracleEstimator]:
    """E5 kernel and span tables from local-condition runs (incl. seed), built
    from compact tuples (memory-lean: the analysis machine had < 1 GiB free)."""
    obs_k: dict = {}
    obs_s: dict = {}
    for r in runs:
        if is_remote_condition(r["condition"]):
            continue
        ev = read_events(EVENTS_DIR.parent / r["event_log"])
        rid = ev[0]["run_id"]
        specs = ev[0]["tasks"]
        for e in ev:
            if e["event"] == "task_completed" and e["pool"] in LOCAL:
                sp = specs[e["task_id"]]
                key = (e["task_id"], int(sp["seed"]), sp["workload"], int(sp["size"]), e["pool"])
                obs_k.setdefault(key, []).append((rid, e["wall_time_seconds"]))
                obs_s.setdefault(key, []).append((rid, e["t_completed"] - e["t_started"]))
        del ev
    return ReplayOracleEstimator(obs_k), ReplayOracleEstimator(obs_s)


def analyze(exp_id: str, cfg: dict, block_filter: str = "full_repeats", tag: str = "") -> dict:
    with (RESULTS / f"{exp_id}_runs.csv").open(encoding="utf-8", newline="") as fh:
        runs = list(csv.DictReader(fh))
    num = ("makespan_s", "mean_response_s", "throughput_tps", "scheduling_time_s", "mean_decision_time_s",
           "transfer_total_s")
    for r in runs:
        for k in num:
            r[k] = float(r[k]) if r[k] not in ("", None) else None
        for k in ("tasks_P", "tasks_E", "tasks_R", "n_decisions", "n_tasks"):
            r[k] = int(r[k])
    manifest = json.loads((RESULTS / f"{exp_id}_manifest.json").read_text(encoding="utf-8"))
    referenced = {Path(r["event_log"]).name for r in runs}
    unreferenced = sorted(p.name for p in (EVENTS_DIR / exp_id).glob("*.jsonl") if p.name not in referenced)
    block_runs, sel = select_blocks(runs, len(manifest["conditions"]), block_filter)
    sel["unreferenced_logs"] = [{"log": n, "reason": "run interrupted (no completed row in runs.csv; no run_finished)"}
                                for n in unreferenced]
    sel["planned_repeats"] = manifest["repeats"]
    blocks: dict = {}
    for r in block_runs:
        blocks.setdefault((r["repeat"], r["trace"]), {})[r["condition"]] = r
    conds = list(dict.fromkeys(r["condition"] for r in block_runs))
    ref = cfg["reference"]
    out = {"experiment_id": exp_id, "n_blocks": len(blocks), "reference": ref, "selection": sel,
           "effects_vs_reference": {}, "contrasts": {}, "per_condition": {}}

    for metric in ("makespan_s", "mean_response_s", "throughput_tps"):
        for c in conds:
            if c != ref:
                e = paired_effect(blocks, c, ref, metric, seed=1)
                if e:
                    out["effects_vs_reference"][f"{c}|{metric}"] = e
        for c, rf in cfg["contrasts"]:
            e = paired_effect(blocks, c, rf, metric, seed=2)
            if e:
                out["contrasts"][f"{c} vs {rf}|{metric}"] = e

    # E5 tables: ALL completed local-condition runs of the session (incl. seed and excluded blocks:
    # they are genuine observations of the same tasks), leave-run-out per analysed run.
    ok, oe = _oracle_tables(runs)

    run_pred, run_reg, margins = {}, {}, {}
    bins = [(0.0, 0.02), (0.02, 0.10), (0.10, 0.30), (0.30, float("inf"))]
    dec_path = RESULTS / f"{exp_id}_decisions{tag}.csv"
    with dec_path.open("x", newline="", encoding="utf-8") as fh:
        wd = csv.DictWriter(fh, fieldnames=DEC_FIELDS, extrasaction="ignore")
        wd.writeheader()
        for r in block_runs:
            ev = read_events(EVENTS_DIR.parent / r["event_log"])
            run_pred[r["event_log"]] = _run_log_metrics(ev)
            if is_remote_condition(r["condition"]):
                continue  # no R oracle coverage -> placement regret only for local-condition runs
            ok.exclude_run(ev[0]["run_id"])
            oe.exclude_run(ev[0]["run_id"])
            ks, ko, es, eo = [], [], [], []
            for d in decision_rows(ev, ok, oe):
                d.update(condition=r["condition"], repeat=r["repeat"], trace=r["trace"])
                wd.writerow(d)
                if d.get("regret_s") is None:
                    continue
                ks.append(d["regret_s"])
                ko.append(1.0 if d["optimal"] else 0.0)
                if d.get("regret_e2e_s") is not None:
                    es.append(d["regret_e2e_s"])
                    eo.append(1.0 if d["optimal_e2e"] else 0.0)
                if d.get("pred_margin") is not None and d.get("pred_finish"):
                    rel = d["pred_margin"] / d["pred_finish"]
                    for lo, hi in bins:
                        if lo <= rel < hi:
                            m = margins.setdefault(f"{lo:.2f}-{hi:.2f}", {"n": 0, "regret": [], "opt": []})
                            m["n"] += 1
                            m["regret"].append(d["regret_s"] * 1e3)
                            m["opt"].append(ko[-1])
            if ks and es:
                run_reg[r["event_log"]] = (statistics.fmean(ks) * 1e3, statistics.fmean(ko) * 100,
                                           statistics.fmean(es) * 1e3, statistics.fmean(eo) * 100)
            del ev

    for c in conds:
        rs = [r for r in block_runs if r["condition"] == c]
        strata = [r["trace"] for r in rs]
        pc = {"n_runs": len(rs),
              "makespan_ms": mean_ci([r["makespan_s"] * 1e3 for r in rs], strata),
              "mean_response_ms": mean_ci([r["mean_response_s"] * 1e3 for r in rs], strata),
              "throughput_tps": mean_ci([r["throughput_tps"] for r in rs], strata),
              "scheduling_time_ms_per_run": mean_ci([r["scheduling_time_s"] * 1e3 for r in rs], strata),
              "decision_time_us": mean_ci([r["mean_decision_time_s"] * 1e6 for r in rs if r["mean_decision_time_s"]],
                                          [r["trace"] for r in rs if r["mean_decision_time_s"]]),
              "tasks_R_per_run": mean_ci([r["tasks_R"] for r in rs], strata)}
        off = [r for r in rs if r["tasks_R"] > 0]
        if off:
            pc["transfer_ms_per_offloaded_task"] = mean_ci([r["transfer_total_s"] * 1e3 / r["tasks_R"] for r in off],
                                                           [r["trace"] for r in off])
            pc["transfer_share_of_makespan"] = mean_ci([r["transfer_total_s"] / r["makespan_s"] for r in rs], strata)
        pr = [(run_pred[r["event_log"]], r["trace"]) for r in rs]
        ape = [(p["ape"], t) for p, t in pr if p["ape"] is not None]
        if ape:
            pc["exec_pred_median_ape"] = mean_ci([a for a, _ in ape], [t for _, t in ape])
            pc["exec_pred_median_signed"] = mean_ci([p["bias"] for p, _ in pr if p["bias"] is not None],
                                                    [t for p, t in pr if p["bias"] is not None])
        trq = [p["transfer_ratio"] for p, _ in pr if p["transfer_ratio"] is not None]
        if trq:
            pc["transfer_measured_over_predicted"] = mean_ci(trq)
        rr = [(run_reg[r["event_log"]], r["trace"]) for r in rs if r["event_log"] in run_reg]
        if rr:
            st_ = [t for _, t in rr]
            pc["regret_kernel_ms"] = mean_ci([v[0] for v, _ in rr], st_)
            pc["optimal_kernel_pct"] = mean_ci([v[1] for v, _ in rr], st_)
            pc["regret_e2e_ms"] = mean_ci([v[2] for v, _ in rr], st_)
            pc["optimal_e2e_pct"] = mean_ci([v[3] for v, _ in rr], st_)
        out["per_condition"][c] = pc

    out["margins_all_eft"] = {k: {"n": v["n"], "regret_ms": mean_ci(v["regret"]),
                                  "optimal_pct": statistics.fmean(v["opt"]) * 100} for k, v in sorted(margins.items())}
    sds = [e["sd_log"] for k, e in out["effects_vs_reference"].items() if k.endswith("|makespan_s")]
    if sds:
        sd = statistics.median(sds)
        out["power_note"] = {"median_paired_sd_log_makespan": sd, "n_blocks": len(blocks),
                             "implied_ci_halfwidth_pct": min_detectable_effect_pct(sd, len(blocks))}
    with (RESULTS / f"{exp_id}_effects{tag}.json").open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=1))
    report(exp_id, out, tag)
    return out


def report(exp_id: str, out: dict, tag: str = "") -> None:
    fmt = (lambda e: f"{e['effect_pct']:+6.1f} [{e['ci_lo_pct']:+6.1f},{e['ci_hi_pct']:+6.1f}]"
           f"{'*' if e['ci_excludes_zero'] else ' '}" if e else f"{'-':>24s}")
    ci = (lambda m, s=1.0, f="{:.1f}": (f.format(m["mean"] * s) + " [" + f.format(m["ci_lo"] * s) + ","
                                        + f.format(m["ci_hi"] * s) + "]") if m else "-")
    sel = out.get("selection", {})
    lines = [f"{exp_id}: {out['n_blocks']} blocks analysed; reference {out['reference']}",
             f"selection: filter={sel.get('block_filter')} planned_repeats={sel.get('planned_repeats')} "
             f"blocks_total={sel.get('blocks_total')} complete={sel.get('blocks_complete')} "
             f"kept={sel.get('blocks_kept')} full_repeats={sel.get('full_repeats_kept')}",
             f"excluded blocks: {sel.get('excluded_blocks')}",
             f"unreferenced logs: {sel.get('unreferenced_logs')}",
             f"power: {out.get('power_note')}", "",
             "Paired effect vs reference, % [95% bootstrap CI]; * = CI excludes 0 (negative = lower):",
             f"  {'condition':34s} {'makespan':>26s} {'mean response':>26s} {'throughput':>26s}"]
    conds = list(out["per_condition"])
    for c in conds:
        if c == out["reference"]:
            continue
        cells = [fmt(out["effects_vs_reference"].get(f"{c}|{m}")) for m in ("makespan_s", "mean_response_s", "throughput_tps")]
        lines.append(f"  {c:34s} " + " ".join(f"{x:>26s}" for x in cells))
    lines += ["", "Contrasts (makespan), % [95% CI]:"]
    for k, e in out["contrasts"].items():
        if k.endswith("|makespan_s"):
            lines.append(f"  {k[:-11]:55s} {fmt(e)}")
    lines += ["", "Per condition (mean [95% CI] over runs):",
              f"  {'condition':34s} {'makespan ms':>22s} {'sched ms/run':>20s} {'decision us':>20s} "
              f"{'exec medAPE %':>18s} {'regret k ms':>18s} {'optimal k %':>18s} {'regret e2e ms':>18s} {'R tasks':>8s}"]
    for c in conds:
        p = out["per_condition"][c]
        lines.append(f"  {c:34s} {ci(p['makespan_ms']):>22s} {ci(p['scheduling_time_ms_per_run'], f='{:.2f}'):>20s} "
                     f"{ci(p['decision_time_us']):>20s} {ci(p.get('exec_pred_median_ape'), 100):>18s} "
                     f"{ci(p.get('regret_kernel_ms'), f='{:.2f}'):>18s} {ci(p.get('optimal_kernel_pct')):>18s} "
                     f"{ci(p.get('regret_e2e_ms'), f='{:.2f}'):>18s} {p['tasks_R_per_run']['mean']:8.2f}")
    lines += ["", "Offload: transfer per offloaded task (ms), share of makespan (%), measured/predicted transfer:"]
    for c in conds:
        p = out["per_condition"][c]
        if "transfer_ms_per_offloaded_task" in p:
            lines.append(f"  {c:34s} {ci(p['transfer_ms_per_offloaded_task'])}  share "
                         f"{ci(p['transfer_share_of_makespan'], 100)}  meas/pred "
                         f"{ci(p.get('transfer_measured_over_predicted'), f='{:.2f}')}")
    lines += ["", "Placement regret vs relative decision margin (all EFT decisions, local runs):"]
    for k, v in sorted(out["margins_all_eft"].items()):
        lines.append(f"  margin {k:12s} n={v['n']:6d}  regret ms {ci(v['regret_ms'], f='{:.2f}')}  "
                     f"optimal {v['optimal_pct']:.1f}%")
    text = "\n".join(lines)
    with (RESULTS / f"{exp_id}_report{tag}.txt").open("x", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
