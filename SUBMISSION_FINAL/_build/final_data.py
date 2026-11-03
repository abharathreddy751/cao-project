"""Reads the stored result files of the final study so that tables in the documents are generated, not typed.
Sources: RESULTS_TABLE_FINAL.csv, data/results/final_20261101/eval/analysis_<workload>/{confirmatory,contrasts}.csv"""
import csv
from pathlib import Path

ROOT = Path(r"D:\cao project")
EV = ROOT / "data" / "results" / "final_20261101" / "eval"
WL = ["h16_l120", "uniform", "h04_l120", "h40_l120", "h16_l40", "h16_l15"]
MINUS = "\u2212"


def _rows(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


RT = _rows(ROOT / "RESULTS_TABLE_FINAL.csv")
CONF = _rows(EV / "analysis_h16_l120" / "confirmatory.csv")
_CON = {w: _rows(EV / f"analysis_{w}" / "contrasts.csv") for w in WL}


def num(x, d=1, plus=False):
    v = float(x)
    s = f"{abs(v):.{d}f}"
    if round(v, d) == 0:
        return s if not plus else "+" + s if v > 0 else s
    return (MINUS if v < 0 else ("+" if plus else "")) + s


def eff(t, d=1):
    """(effect, lo, hi) -> '\u221217.8 [\u221218.8, \u221216.7]' (signs shown for the interval as in the report)"""
    e, lo, hi = t
    return f"{num(e, d, True)} [{num(lo, d, True)}, {num(hi, d, True)}]"


def session_row(w, c, p):
    for r in RT:
        if r["workload"] == w and r["config"] == c and r["policy"] == p and r["kind"] in ("confirmatory-session", "exploratory"):
            return r
    raise KeyError((w, c, p))


def makespan(w, c, p, d=3, ci=False):
    r = session_row(w, c, p)
    s = f"{float(r['e2e_geo_mean_s']):.{d}f}"
    return s + (f" [{float(r['e2e_ci_lo_s']):.{d}f}, {float(r['e2e_ci_hi_s']):.{d}f}]" if ci else "")


def contrast(w, cond, ref, metric="makespan_e2e_s"):
    for r in _CON[w]:
        if r["cond"] == cond and r["ref"] == ref and r["metric"] == metric:
            return float(r["effect_pct"]), float(r["ci_lo_pct"]), float(r["ci_hi_pct"])
    raise KeyError((w, cond, ref))


CONF_LABEL = {"C1": "PRED vs B4 (CPU)", "C2": "PRED-E2E vs PRED (CPU)", "C3": "PRED vs HEFT (CPU)", "C4": "PRED-E2E vs HEFT-E2E (CPU)",
              "C5": "PRED vs HEFT (strict GPU)", "C6": "PRED-E2E vs HEFT-E2E (strict GPU)", "C7": "PRED-E2E vs PRED (strict GPU)",
              "C8": "PRED vs B4 (strict GPU)", "C9": "PRED, strict GPU vs CPU", "C10": "B4, strict GPU vs CPU"}


def confirmatory_rows():
    out = []
    for r in CONF:
        cls = r["classification"].replace(" (CI inside +-2%)", " (within \u00b12%)")
        out.append([r["id"], CONF_LABEL[r["id"]], eff((float(r["effect_pct"]), float(r["ci_lo_pct"]), float(r["ci_hi_pct"]))), f"{float(r['p_holm']):.3f}", cls])
    return out


POLICY_ROWS = [("B4", "B4 (blind, dynamic)"), ("B4_param_first", "B4 param-first (rule, dynamic)"), ("PRED_RANK_GREEDY", "PRED (dynamic)"),
               ("PRED_RANK_GREEDY_E2E", "PRED-E2E (dynamic)"), ("HEFT_param_model", "HEFT (static)"), ("HEFT_E2E", "HEFT-E2E (static)"), ("PEFT_param_model", "PEFT (static)")]


def primary_table_rows():
    return [[label] + [makespan("h16_l120", c, p, 3) for c in ("cpu", "gpu", "ext")] for p, label in POLICY_ROWS]


def workload_effect_rows(cfg):
    """per workload: PRED vs HEFT and PRED vs B4 (exploratory outside the primary session)"""
    rows = []
    for w in WL:
        if w == "uniform" and cfg == "ext":
            continue
        rows.append([w, eff(contrast(w, f"PRED_RANK_GREEDY_{cfg}", f"HEFT_param_model_{cfg}")), eff(contrast(w, f"PRED_RANK_GREEDY_{cfg}", f"B4_{cfg}"))])
    return rows


def pf_effect(cfg):
    """PRED_RANK_GREEDY against B4_param_first, primary workload, end-to-end makespan (exploratory)"""
    for r in _rows(EV / f"exploratory_pf_{cfg}" / "effects.csv"):
        if r["variant"] == "primary" and r["metric"] == "makespan_e2e_s" and r["cond"] == f"PRED_RANK_GREEDY_{cfg}" and r["ref"] == f"B4_param_first_{cfg}" and r["n_blocks"] == "24":
            return float(r["effect_pct"]), float(r["ci_lo_pct"]), float(r["ci_hi_pct"])
    raise KeyError(cfg)


def all_workloads_rows(cfg):
    pols = ["B4", "B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E", "HEFT_param_model", "HEFT_E2E", "PEFT_param_model"]
    rows = []
    for w in WL:
        try:
            rows.append([w] + [makespan(w, cfg, p, 3) for p in pols])
        except KeyError:
            continue
    return rows


def static_rows():
    """static-plan comparisons on the primary workload (within configuration), vs HEFT_param_model"""
    out = []
    for cfg, lab in (("cpu", "CPU only"), ("gpu", "strict GPU"), ("ext", "extended GPU")):
        out.append([lab,
                    eff(contrast("h16_l120", f"HEFT_E2E_{cfg}", f"HEFT_param_model_{cfg}")),
                    eff(contrast("h16_l120", f"PEFT_param_model_{cfg}", f"HEFT_param_model_{cfg}")),
                    eff(contrast("h16_l120", f"HEFT_ORACLE_REF_{cfg}", f"HEFT_param_model_{cfg}"))])
    return out


def gpu_rows():
    out = []
    conf = {r["id"]: (float(r["effect_pct"]), float(r["ci_lo_pct"]), float(r["ci_hi_pct"])) for r in CONF}
    for p, lab, cid in (("PRED_RANK_GREEDY", "PRED (dynamic)", "C9"), ("B4", "B4 (blind)", "C10"), ("HEFT_param_model", "HEFT (static)", None)):
        strict = conf[cid] if cid else contrast("h16_l120", f"{p}_gpu", f"{p}_cpu")  # the confirmatory contrasts C9 and C10 are quoted as stored
        out.append([lab, eff(strict), eff(contrast("h16_l120", f"{p}_ext", f"{p}_cpu")), eff(contrast("h16_l120", f"{p}_ext", f"{p}_gpu"))])
    return out


def placement_rows():
    out = []
    for cfg, lab in (("gpu", "strict"), ("ext", "extended")):
        for p, pl in POLICY_ROWS:
            r = session_row("h16_l120", cfg, p)
            out.append([lab, pl, f"{float(r['tasks_cpu']):.0f} / {float(r['tasks_gpu']):.0f}", f"{float(r['gpu_busy_frac']):.2f}", f"{float(r['cpu_util']):.2f}"])
    return out


def overhead_rows():
    out = []
    for p, pl in POLICY_ROWS:
        r = session_row("h16_l120", "cpu", p)
        out.append([pl, f"{float(r['init_s']) * 1000:.1f}", f"{float(r['policy_setup_s']) * 1000:.1f}", f"{float(r['sched_total_s']) * 1000:.1f}", f"{float(r['queue_wait_mean_s']):.3f}"])
    return out


def timing_rows():
    out = []
    for p, pl in POLICY_ROWS:
        r = session_row("h16_l120", "cpu", p)
        e2e, old = float(r["e2e_geo_mean_s"]), float(r["old_geo_mean_s"])
        out.append([pl, f"{old:.3f}", f"{e2e:.3f}", f"{(e2e - old) * 1000:.1f}"])
    return out


def plan_rows():
    out = []
    for p, pl in (("HEFT_param_model", "HEFT"), ("PEFT_param_model", "PEFT"), ("HEFT_E2E", "HEFT-E2E"), ("HEFT_ORACLE_REF", "HEFT oracle (reference)")):
        row = [pl]
        for cfg in ("cpu", "gpu", "ext"):
            r = None
            for x in RT:
                if x["workload"] == "h16_l120" and x["config"] == cfg and x["policy"].startswith(p) and x["kind"] == "confirmatory-session":
                    r = x
            row.append(f"{float(r['plan_over_actual']):.2f}")
        out.append(row)
    return out


def halfwidths():
    """half-widths (percentage points) of the ten confirmatory intervals"""
    h = [(float(r["ci_hi_pct"]) - float(r["ci_lo_pct"])) / 2 for r in CONF]
    return min(h), max(h)


def effects_vs(ref_kind, cfg):
    """per workload: B4_param_first, PRED, PRED-E2E against static HEFT ('heft') or blind B4 ('b4') within one hardware set"""
    ref = "HEFT_param_model" if ref_kind == "heft" else "B4"
    rows = []
    for w in WL:
        if w == "uniform" and cfg == "ext":
            continue
        rows.append([w] + [eff(contrast(w, f"{p}_{cfg}", f"{ref}_{cfg}")) for p in ("B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E")])
    return rows


def pred_vs_all_rows(cfg):
    """per workload: PRED vs HEFT, vs B4, for the given configuration"""
    return workload_effect_rows(cfg)


if __name__ == "__main__":
    print(primary_table_rows()[:2])
    print(confirmatory_rows()[:2])
    print(workload_effect_rows("cpu")[:2])
