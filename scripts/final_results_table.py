"""Final study: one flat results table from the per-session analyses written by scripts/final_analyze.py. Written exclusively; the
earlier RESULTS_TABLE.csv is never touched.

  python scripts/final_results_table.py <eval_dir> <out.csv>

<eval_dir>/analysis_<workload>/{policy_table,contrasts}.csv are joined: for every condition, its end-to-end makespan and overheads plus the
paired effect (percent, 95% CI) against the static baseline HEFT_param_model_<cfg> and against B4_<cfg>, on the primary metric
makespan_e2e_s. Confirmatory contrasts (if the session has them) are appended with their Holm-adjusted p.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path


def _read(p: Path) -> list[dict]:
    with p.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(eval_dir: str, out: str) -> int:
    rows = []
    for ad in sorted(Path(eval_dir).glob("analysis_*")):
        wl = ad.name.removeprefix("analysis_")
        if wl == "smoke":   # 2-block sanity run, not a result
            continue
        con = {(c["cond"], c["ref"], c["metric"]): c for c in _read(ad / "contrasts.csv")}
        for r in _read(ad / "policy_table.csv"):
            name = r["condition"]
            pol, cfg = name.rsplit("_", 1)
            row = {"workload": wl, "config": cfg, "policy": pol, "kind": "confirmatory-session" if (ad / "confirmatory.csv").exists() else "exploratory",
                   **{k: r.get(k, "") for k in ("n", "e2e_geo_mean_s", "e2e_ci_lo_s", "e2e_ci_hi_s", "old_geo_mean_s", "init_s", "policy_setup_s",
                                                "sched_total_s", "queue_wait_mean_s", "tasks_cpu", "tasks_gpu", "gpu_busy_frac", "cpu_util",
                                                "plan_over_actual", "output_ok", "n_excluded")}}
            for tag, ref in (("static", f"HEFT_param_model_{cfg}"), ("B4", f"B4_{cfg}")):
                c = con.get((name, ref, "makespan_e2e_s"))
                for k in ("effect_pct", "ci_lo_pct", "ci_hi_pct", "classification"):
                    row[f"vs_{tag}_{k}"] = c.get(k, "") if c else ""
            rows.append(row)
        if (ad / "confirmatory.csv").exists():
            for c in _read(ad / "confirmatory.csv"):
                rows.append({"workload": wl, "config": "confirmatory", "policy": f"{c['id']}: {c['cond']} vs {c['ref']}", "kind": "confirmatory",
                             "n": c.get("n_blocks", ""), "vs_static_effect_pct": c.get("effect_pct", ""), "vs_static_ci_lo_pct": c.get("ci_lo_pct", ""),
                             "vs_static_ci_hi_pct": c.get("ci_hi_pct", ""), "vs_static_classification": c.get("classification", ""),
                             "vs_B4_effect_pct": f"p_holm={c.get('p_holm', '')}"})
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with Path(out).open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, cols, restval="")
        w.writeheader()
        w.writerows(rows)
    print("wrote", out, len(rows), "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
