"""Phase 5: remote offloading through the local link shim, and the
kernel-only vs end-to-end EFT ablation.

Configurations (worker pool rebuilt for each, order randomized):
  local_2P7E       P + all 7 E slots, no remote. Hosts the kernel vs e2e
                   ablation; B0_P_only / B0_E_only give every task oracle
                   coverage on both pools so kernel AND e2e placement regret
                   can be computed for the same decisions.
  local_2P6E       the node's E core left unused -- the local reference for:
  remote_<link>    P + 6 E + R0 (a node on that same core, behind the link).
                   remote vs local_2P6E isolates what the link costs/buys for
                   identical compute.

Policies per configuration: B4 (local pools only), B4_R (greedy with R as
last resort; remote configs), and EFT with each configured spec. EFT's
transfer term = configured link + measured socket cost (profile calibration).

Outputs (raw first): data/events/phase5_<stamp>/<config>/*.jsonl and
data/results/phase5_<stamp>_{manifest.json, runs.csv, transfer.csv,
decisions.csv, summary.json}.

Usage:  python scripts/run_phase5.py [--config config/phase5.yaml] [--repeats N]
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

import yaml

from caosched.analysis.decisions import decision_rows
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
from caosched.schedulers.simple import GreedyEligibleScheduler, PoolOnlyScheduler

RESULTS = Path(__file__).resolve().parents[1] / "data" / "results"
RUN_FIELDS = ["config", "link", "repeat", "trace", "policy", "order_index", "status", "n_tasks", "makespan_s",
              "tasks_P", "tasks_E", "tasks_R", "transfer_total_s", "event_log"]
TRANSFER_FIELDS = ["config", "run_id", "policy", "task_id", "workload", "size", "predicted_transfer_s",
                   "measured_transfer_s"]
DEC_FIELDS = ["config", "repeat", "trace", "run_id", "policy", "task_id", "workload", "size", "chosen_pool",
              "actual_kernel_s", "pred_exec", "pred_finish", "regret_s", "optimal", "regret_e2e_s", "optimal_e2e",
              "bind_delay_s", "n_candidates"]


def load_yaml(p) -> dict:
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


def build_configs(cfg: dict, rc: RuntimeConfig) -> list[dict]:
    node = cfg["remote"]["node_core"]
    e6 = tuple(c for c in rc.e_core_slots if c != node)
    out = [{"name": "local_2P7E", "link": None, "e": rc.e_core_slots, "remote": None},
           {"name": "local_2P6E", "link": None, "e": e6, "remote": None}]
    for lname, l in cfg["links"].items():
        out.append({"name": f"remote_{lname}", "link": LinkConfig(lname, **l), "e": e6, "remote": node})
    return out


def factories_for(conf: dict, cfg: dict, profile: Path, est_cfg: dict, e2e: EndToEndTerms, model: Path) -> dict:
    f = {}
    if conf["name"] == "local_2P7E":
        for n in cfg["policies"]["coverage_baselines"]:
            f[n] = (lambda p=n.split("_")[1]: PoolOnlyScheduler(p))
    for n in cfg["policies"]["local_only_baselines"]:
        f[n] = lambda: GreedyEligibleScheduler(priority=["P", "E"])
    transfer = None
    if conf["link"] is not None:
        if cfg["policies"].get("remote_greedy"):
            f["B4_greedy_eligible_R"] = lambda: GreedyEligibleScheduler(priority=["P", "E", "R"],
                                                                        name="B4_greedy_eligible_R")
        transfer = TransferModel.with_profile_calibration({"R": conf["link"]}, profile)
    f.update(eft_factories(cfg["policies"]["eft"], profile, est_cfg, model, e2e_terms=e2e, transfer=transfer))
    return f


def run_config(conf, cfg, rc, factories, traces, repeats, rng, exp_id, events_root, exp, writer, fh) -> list[dict]:
    slots = []
    if conf["remote"] is not None:
        slots = [RemoteSlot(conf["link"], node_core=conf["remote"], proxy_core=cfg["remote"]["proxy_core"])]
    events_dir = events_root / conf["name"]
    rows = []
    with WorkerPool(list(rc.p_core_slots), list(conf["e"]), warmup=True, strict_affinity=True,
                    remote_slots=slots) as pool:
        for rep in range(repeats):
            for trace in traces:
                order = list(factories)
                rng.shuffle(order)
                for idx, name in enumerate(order):
                    pol = factories[name]()
                    run_id = f"{trace['name']}__{pol.name}__r{rep}"
                    with EventLogger(run_id, output_dir=events_dir) as logger:
                        s = Coordinator(dag_from_trace(trace), pool, pol, logger, run_metadata={
                            "experiment_id": exp_id, "config": conf["name"], "trace": trace["name"],
                            "repeat": rep, "order_index": idx,
                            "link": conf["link"].to_dict() if conf["link"] else None}).run(run_timeout=exp["run_timeout_s"])
                    ev = read_events(logger.path)
                    tr = sum(e.get("transfer_s") or 0.0 for e in ev if e["event"] == "task_completed")
                    row = {"config": conf["name"], "link": conf["link"].name if conf["link"] else "",
                           "repeat": rep, "trace": trace["name"], "policy": pol.name, "order_index": idx,
                           "status": s.status, "n_tasks": s.n_tasks, "makespan_s": s.makespan_seconds,
                           "tasks_P": s.tasks_per_pool.get("P", 0), "tasks_E": s.tasks_per_pool.get("E", 0),
                           "tasks_R": s.tasks_per_pool.get("R", 0), "transfer_total_s": tr,
                           "event_log": str(logger.path.relative_to(EVENTS_DIR.parent))}
                    writer.writerow(row)
                    fh.flush()
                    rows.append(row)
            print(f"  [{conf['name']}] repeat {rep + 1}/{repeats} done")
    return rows


def transfer_rows(config_name: str, ev: list[dict]) -> list[dict]:
    disp = {e["task_id"]: e for e in ev if e["event"] == "task_dispatched"}
    specs = ev[0]["tasks"]
    out = []
    for e in ev:
        if e["event"] == "task_completed" and e.get("transfer_s") is not None:
            d = disp[e["task_id"]].get("decision")
            pred = d["candidates"][e["worker_id"]]["transfer"] if d else None
            out.append({"config": config_name, "run_id": ev[0]["run_id"], "policy": ev[0]["scheduler"],
                        "task_id": e["task_id"], "workload": specs[e["task_id"]]["workload"],
                        "size": specs[e["task_id"]]["size"], "predicted_transfer_s": pred,
                        "measured_transfer_s": e["transfer_s"]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase5.yaml")
    ap.add_argument("--repeats", type=int, default=None)
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    exp = cfg["experiment"]
    repeats = args.repeats or exp["repeats"]
    profile, model = Path(cfg["profile"]), Path(cfg["e4_model"])
    e2e = EndToEndTerms.load(Path(cfg["e2e_terms"]))
    est_cfg = {**load_yaml(cfg["estimator_config"])["estimators"], "rc": cfg["rc"]}
    traces = [load_or_create_trace(spec)[0] for spec in load_yaml(cfg["traces_from"])["traces"]]

    rc = RuntimeConfig.from_topology()
    coord_core = pin_coordinator_to_reserved_core(rc)
    configs = build_configs(cfg, rc)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    exp_id = f"phase5_{stamp}"
    events_root = EVENTS_DIR / exp_id
    rng = random.Random(exp["order_seed"])
    rng.shuffle(configs)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{exp_id}_manifest.json").write_text(json.dumps({
        "experiment_id": exp_id, "config": cfg, "config_order": [c["name"] for c in configs],
        "runtime_config": rc.to_dict(), "coordinator_core": coord_core, "repeats": repeats,
        "python": sys.version, "platform": platform.platform(),
        "notes": "remote node = one E core of this machine behind the link shim; compute speed is the E core's"},
        indent=1), encoding="utf-8")
    print(f"{exp_id}: configs {[c['name'] for c in configs]}, {repeats} repeats")

    runs = []
    with (RESULTS / f"{exp_id}_runs.csv").open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RUN_FIELDS)
        w.writeheader()
        for conf in configs:
            f = factories_for(conf, cfg, profile, est_cfg, e2e, model)
            runs += run_config(conf, cfg, rc, f, traces, repeats, rng, exp_id, events_root, exp, w, fh)

    # ---- analysis (from logs only) ----
    trans, decisions = [], []
    for conf in configs:
        logs = [read_events(p) for p in sorted((events_root / conf["name"]).glob("*.jsonl"))]
        for ev in logs:
            trans += transfer_rows(conf["name"], ev)
        if conf["name"] == "local_2P7E":
            rows = [r for ev in logs for r in rows_from_events(ev)]
            ok = ReplayOracleEstimator.from_rows(rows)
            oe = ReplayOracleEstimator.from_rows([{**r, "kernel_s": r["t_completed"] - r["t_started"]} for r in rows])
            for ev in logs:
                ok.exclude_run(ev[0]["run_id"])
                oe.exclude_run(ev[0]["run_id"])
                meta = ev[0]["metadata"]
                for d in decision_rows(ev, ok, oe):
                    d.update(config=conf["name"], repeat=meta["repeat"], trace=meta["trace"])
                    decisions.append(d)
    for name, fields, data in (("transfer", TRANSFER_FIELDS, trans), ("decisions", DEC_FIELDS, decisions)):
        with (RESULTS / f"{exp_id}_{name}.csv").open("x", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    summary = {"makespan": {}, "transfer": {}, "ablation_local_2P7E": {}}
    for c in dict.fromkeys(r["config"] for r in runs):
        for t in dict.fromkeys(r["trace"] for r in runs):
            for p in dict.fromkeys(r["policy"] for r in runs if r["config"] == c):
                sel = [r for r in runs if r["config"] == c and r["trace"] == t and r["policy"] == p]
                if sel:
                    ms = [r["makespan_s"] for r in sel]
                    summary["makespan"][f"{c}|{t}|{p}"] = {
                        "median_s": statistics.median(ms), "min_s": min(ms), "max_s": max(ms),
                        "tasks_R_median": statistics.median(r["tasks_R"] for r in sel), "n": len(sel)}
    for c in dict.fromkeys(x["config"] for x in trans):
        sel = [x for x in trans if x["config"] == c and x["predicted_transfer_s"]]
        if sel:
            ratios = sorted(x["measured_transfer_s"] / x["predicted_transfer_s"] for x in sel)
            summary["transfer"][c] = {"n": len(sel), "measured_over_predicted_median": statistics.median(ratios),
                                      "p10": ratios[len(ratios) // 10], "p90": ratios[9 * len(ratios) // 10]}
    for p in dict.fromkeys(d["policy"] for d in decisions):
        ds = [d for d in decisions if d["policy"] == p and d.get("regret_s") is not None]
        de = [d for d in ds if d.get("regret_e2e_s") is not None]
        summary["ablation_local_2P7E"][p] = {
            "n": len(ds), "regret_kernel_mean_ms": statistics.fmean(d["regret_s"] for d in ds) * 1e3,
            "optimal_kernel": statistics.fmean(1.0 if d["optimal"] else 0.0 for d in ds),
            "regret_e2e_mean_ms": statistics.fmean(d["regret_e2e_s"] for d in de) * 1e3 if de else None,
            "optimal_e2e": statistics.fmean(1.0 if d["optimal_e2e"] else 0.0 for d in de) if de else None}
    (RESULTS / f"{exp_id}_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    for t in dict.fromkeys(r["trace"] for r in runs):
        print(f"\n[{t}] median makespan ms (tasks on R) by configuration")
        pols = list(dict.fromkeys(r["policy"] for r in runs))
        cols = list(dict.fromkeys(r["config"] for r in runs))
        cols.sort()
        print("  " + f"{'policy':24s}" + "".join(f"{c[:14]:>16s}" for c in cols))
        for p in pols:
            cells = []
            for c in cols:
                m = summary["makespan"].get(f"{c}|{t}|{p}")
                cells.append(f"{m['median_s'] * 1e3:8.1f} ({m['tasks_R_median']:3g})" if m else f"{'-':>15s}")
            print(f"  {p:24s}" + "".join(f"{x:>16s}" for x in cells))
    print("\ntransfer measured/predicted (EFT decisions to R):",
          {c: f"{v['measured_over_predicted_median']:.2f} [{v['p10']:.2f},{v['p90']:.2f}] n={v['n']}"
           for c, v in summary["transfer"].items()})
    print("\nlocal_2P7E ablation: placement regret kernel vs e2e (mean ms / optimal %):")
    for p, v in summary["ablation_local_2P7E"].items():
        print(f"  {p:24s} kernel {v['regret_kernel_mean_ms']:6.2f} / {v['optimal_kernel'] * 100:5.1f}%   "
              + (f"e2e {v['regret_e2e_mean_ms']:6.2f} / {v['optimal_e2e'] * 100:5.1f}%" if v['regret_e2e_mean_ms'] is not None else "e2e -"))


if __name__ == "__main__":
    main()
