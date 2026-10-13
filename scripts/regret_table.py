"""One-step hindsight placement regret per policy from logged decisions (analysis/decisions.py; read its docstring
for the limits: myopic, kernel-only, the E5 replay oracle is a stand-in for the unobservable counterfactual).

Sets analysed: --main (Stage 4 main session) and --regime (scarce-P regime session). Only runs with manifest status
'ok' and verified output count. The oracle (median kernel time of the same task on a pool in OTHER runs) is built per
workflow instance from every such run under --main, --regime and --oracle-extra (Stage 2 / Stage 3 pilot sessions
add pool-E observations); candidate workers whose pool has no observation are left out of the regret minimum
(``mean_candidates_scored`` vs ``mean_workers``).

Writes to --out: regret_table.csv (per set and policy), regret_decisions.csv (every decision row), regime_mProject_diff.csv
(mProject decisions where CatBoost and E1 chose different pools in the same regime block) and regret_table.md.

Usage: python scripts/regret_table.py --main DIR --regime DIR --oracle-extra DIR [DIR ...] --out DIR
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from caosched.analysis.decisions import decision_rows
from caosched.core.event_log import read_events
from caosched.dataset.events import rows_from_events
from caosched.estimators import ReplayOracleEstimator


def discover(session_dir: Path) -> list[dict]:
    """Verified-ok runs of a session dir: [{"log", "run_id", "instance", "policy", "block"}]."""
    out = []
    for mf in sorted(Path(session_dir).glob("runs/*/run_manifest.json")):
        m = json.loads(mf.read_text(encoding="utf-8"))
        if m["status"] == "ok" and (m.get("verification") or {}).get("passed"):
            out.append({"log": mf.parent / m["event_log"]["path"], "run_id": m["run_id"], "instance": m["instance"],
                        "policy": m["policy"], "block": m["block"]})
    return out


def summarize(rows: list[dict]) -> list[dict]:
    """Per policy: decision counts, mean / total regret (s), share of scored decisions with positive regret, and the
    same for mProject decisions (the dominant task type). Rows without ``regret_s`` (no scored candidate) are not scored."""
    by_pol: dict[str, list] = defaultdict(list)
    for r in rows:
        by_pol[r["policy"]].append(r)
    out = []
    for pol, rs in sorted(by_pol.items()):
        sc = [r for r in rs if r.get("regret_s") is not None]
        mp = [r for r in sc if r["workload"] == "mProject"]
        reg = np.array([r["regret_s"] for r in sc])
        n_runs = len({r["run_id"] for r in rs})
        out.append({"policy": pol, "n_runs": n_runs, "n_decisions": len(rs), "n_scored": len(sc),
                    "mean_candidates_scored": float(np.mean([r["n_candidates"] for r in sc])) if sc else None,
                    "mean_workers": float(np.mean([r["n_workers"] for r in rs])),
                    "candidate_costs_logged_share": sum(r.get("pred_finish") is not None for r in rs) / len(rs),
                    "mean_regret_s": float(reg.mean()) if sc else None, "total_regret_s": float(reg.sum()),
                    "total_regret_per_run_s": float(reg.sum() / n_runs), "share_positive_regret": float((~np.array([r["optimal"] for r in sc])).mean()) if sc else None,
                    "n_mProject": len(mp), "mProject_mean_regret_s": float(np.mean([r["regret_s"] for r in mp])) if mp else None,
                    "mProject_share_positive": float(np.mean([not r["optimal"] for r in mp])) if mp else None})
    return out


def pool_differences(rows: list[dict], a: str, b: str, workload: str = "mProject") -> list[dict]:
    """Decisions of policy ``a`` and ``b`` for the same (block, task_id, workload) whose chosen POOL differs; one dict
    per pair with both sides' pool, regret, predicted and actual kernel time. Rows need ``block``."""
    key = lambda r: (r["block"], r["task_id"])
    ra = {key(r): r for r in rows if r["policy"] == a and r["workload"] == workload}
    rb = {key(r): r for r in rows if r["policy"] == b and r["workload"] == workload}
    out = []
    for k in sorted(set(ra) & set(rb)):
        x, y = ra[k], rb[k]
        if x["chosen_pool"] != y["chosen_pool"]:
            out.append({"block": k[0], "task_id": k[1], **{f"{n}_{f}": r.get(f) for n, r in ((a, x), (b, y))
                        for f in ("chosen_pool", "chosen_worker", "pred_exec", "pred_finish", "actual_kernel_s", "regret_s", "hind_best_pool")}})
    return out


def _f(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--regime", required=True)
    ap.add_argument("--oracle-extra", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sets = {"main": discover(a.main), "regime_R": discover(a.regime)}
    extra = [r for d in a.oracle_extra for r in discover(d)]
    oracles: dict[str, ReplayOracleEstimator] = defaultdict(lambda: ReplayOracleEstimator({}))
    events = {}
    for r in [x for s in sets.values() for x in s] + extra:
        ev = events[r["log"]] = read_events(r["log"])
        for row in rows_from_events(ev, context_source="auto"):
            oracles[r["instance"]].add(row["run_id"], row["task_id"], row["seed"], row["workload"], row["size"], row["pool"], row["kernel_s"])
    all_rows, table = [], []
    for name, runs in sets.items():
        rows = []
        for r in runs:
            oracles[r["instance"]].exclude_run(r["run_id"])
            for d in decision_rows(events[r["log"]], oracles[r["instance"]]):
                rows.append({"set": name, "block": r["block"], "instance": r["instance"], **d})
        table += [{"set": name, **s} for s in summarize(rows)]
        all_rows += rows
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for fn, recs in (("regret_table.csv", table), ("regret_decisions.csv", all_rows)):
        fields = list(dict.fromkeys(k for r in recs for k in r))
        with (out / fn).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(recs)
    diff = pool_differences([r for r in all_rows if r["set"] == "regime_R"], "EFT_CatBoost", "EFT_E1")
    with (out / "regime_mProject_diff.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(diff[0]) if diff else ["none"])
        w.writeheader()
        w.writerows(diff)
    lines = ["# One-step hindsight placement regret (evidence: real; derived from event logs)", "",
             "Regret = (finish of the chosen worker) - (finish of the best worker), both with the E5 replay-oracle kernel time "
             "and the actual worker backlog at binding time (analysis/decisions.py). Myopic, kernel-only; workers whose pool has no "
             "oracle observation are left out of the minimum. B0/B4 log no candidate costs but regret needs none.", ""]
    for name in sets:
        lines += [f"## {name}", "", "| policy | runs | decisions | mean regret s | total regret s | total per run s | share positive | mProject mean s | mProject share positive | costs logged |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {t['policy']} | {t['n_runs']} | {t['n_scored']} | {_f(t['mean_regret_s'])} | {_f(t['total_regret_s'], 1)} | {_f(t['total_regret_per_run_s'], 1)} | "
                  f"{_f(t['share_positive_regret'], 3)} | {_f(t['mProject_mean_regret_s'])} | {_f(t['mProject_share_positive'], 3)} | {t['candidate_costs_logged_share']:.2f} |"
                  for t in table if t["set"] == name] + [""]
    lines += [f"## regime_R: mProject decisions where EFT_CatBoost and EFT_E1 chose different pools ({len(diff)} pairs)", ""]
    if diff:
        lines += ["| block | task | CatBoost pool | E1 pool | CatBoost pred exec s | CatBoost actual s | E1 actual s | CatBoost regret s | E1 regret s | best pool (CatBoost view) |", "|---|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {d['block']} | {d['task_id']} | {d['EFT_CatBoost_chosen_pool']} | {d['EFT_E1_chosen_pool']} | {_f(d['EFT_CatBoost_pred_exec'], 1)} | "
                  f"{_f(d['EFT_CatBoost_actual_kernel_s'], 1)} | {_f(d['EFT_E1_actual_kernel_s'], 1)} | {_f(d['EFT_CatBoost_regret_s'], 1)} | "
                  f"{_f(d['EFT_E1_regret_s'], 1)} | {d['EFT_CatBoost_hind_best_pool']} |" for d in diff]
    (out / "regret_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for t in table:
        print(f"{t['set']:9s} {t['policy']:20s} runs={t['n_runs']:2d} dec={t['n_scored']:4d} mean={_f(t['mean_regret_s'])}s total={_f(t['total_regret_s'], 1)}s "
              f"pos={_f(t['share_positive_regret'], 3)} mProject_mean={_f(t['mProject_mean_regret_s'])}s")
    print(f"regime_R mProject pool differences CatBoost vs E1: {len(diff)}")


if __name__ == "__main__":
    main()
