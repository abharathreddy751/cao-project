"""Figures of the final static-vs-dynamic study. Every plotted number is read from the stored analysis files
(data/results/final_20261101/eval/analysis_*/ and models/train.stdout.txt); nothing is typed in. Output: SUBMISSION_FINAL/_fig/*.png (300 dpi, column width 3.4 in)."""
import csv
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(r"D:\cao project")
FIN = ROOT / "data" / "results" / "final_20261101"
EV = FIN / "eval"
OUT = ROOT / "SUBMISSION_FINAL" / "_fig"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 7.5, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
WL = ["h16_l120", "uniform", "h04_l120", "h40_l120", "h16_l40", "h16_l15"]
COL = {"B4": "#8c8c8c", "B4_param_first": "#4c9f70", "PRED_RANK_GREEDY": "#1f5fa8", "PRED_RANK_GREEDY_E2E": "#6aa6e0",
       "HEFT_param_model": "#8e5ea2", "PEFT_param_model": "#d1495b", "HEFT_E2E": "#c9a0dc"}
SHORT = {"B4": "B4", "B4_param_first": "B4 param-first", "PRED_RANK_GREEDY": "PRED (dynamic)", "PRED_RANK_GREEDY_E2E": "PRED-E2E (dynamic)",
         "HEFT_param_model": "HEFT (static)", "PEFT_param_model": "PEFT (static)", "HEFT_E2E": "HEFT-E2E (static)"}


def rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(x):
    return float(x)


def save(fig, name):
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# ---- 1. makespan by policy and configuration (primary workload) ---------------------------------------------------
pt = {r["condition"]: r for r in rows(EV / "analysis_h16_l120" / "policy_table.csv")}
pols = ["B4", "B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E", "HEFT_param_model", "HEFT_E2E", "PEFT_param_model"]
fig, ax = plt.subplots(figsize=(3.45, 2.5))
w = 0.115
for i, p in enumerate(pols):
    xs, ys, lo, hi = [], [], [], []
    for j, c in enumerate(["cpu", "gpu", "ext"]):
        r = pt[f"{p}_{c}"]
        xs.append(j + (i - 3) * w); ys.append(f(r["e2e_geo_mean_s"]))
        lo.append(f(r["e2e_geo_mean_s"]) - f(r["e2e_ci_lo_s"])); hi.append(f(r["e2e_ci_hi_s"]) - f(r["e2e_geo_mean_s"]))
    ax.bar(xs, ys, w * 0.92, color=COL[p], label=SHORT[p], yerr=[lo, hi], error_kw={"lw": 0.5, "capsize": 0.8})
ax.set_xticks(range(3)); ax.set_xticklabels(["CPU only\n(P+E)", "CPU + GPU\n(strict set)", "CPU + GPU\n(extended set)"])
ax.set_ylim(2.5, 4.4); ax.set_ylabel("end-to-end makespan (s)")
ax.legend(ncol=2, fontsize=5.8, loc="upper center", bbox_to_anchor=(0.5, 1.28), columnspacing=0.8, handlelength=1.1)
save(fig, "fig_final_makespan.png")

# ---- 2. forest plot of the ten confirmatory contrasts ------------------------------------------------------------
cf = rows(EV / "analysis_h16_l120" / "confirmatory.csv")
label = {"C1": "C1 PRED vs B4 (CPU)", "C2": "C2 PRED-E2E vs PRED (CPU)", "C3": "C3 PRED vs HEFT (CPU)", "C4": "C4 PRED-E2E vs HEFT-E2E (CPU)",
         "C5": "C5 PRED vs HEFT (strict GPU)", "C6": "C6 PRED-E2E vs HEFT-E2E (GPU)", "C7": "C7 PRED-E2E vs PRED (GPU)",
         "C8": "C8 PRED vs B4 (strict GPU)", "C9": "C9 PRED: GPU vs CPU", "C10": "C10 B4: GPU vs CPU"}
fig, ax = plt.subplots(figsize=(3.45, 2.7))
ax.axvspan(-2, 2, color="#dddddd", alpha=0.7, lw=0, label="±2% margin")
for k, r in enumerate(cf):
    e, lo, hi = f(r["effect_pct"]), f(r["ci_lo_pct"]), f(r["ci_hi_pct"])
    cls = r["classification"]
    colr = "#1f5fa8" if cls == "faster" else ("#4c9f70" if cls.startswith("equivalent") else "#8c8c8c")
    ax.errorbar(e, -k, xerr=[[e - lo], [hi - e]], fmt="o", ms=3, color=colr, lw=0.9, capsize=1.5)
ax.axvline(0, color="k", lw=0.5)
ax.set_yticks([-k for k in range(len(cf))]); ax.set_yticklabels([label[r["id"]] for r in cf], fontsize=6.3)
ax.set_xlabel("effect on makespan (%, negative = first policy faster)")
save(fig, "fig_final_forest.png")

# ---- 3. effects across workloads: PRED vs HEFT and PRED vs B4 (CPU and strict GPU) ----------------------------------
cross = {}
for w_ in WL:
    for r in rows(EV / "analysis_{}".format(w_) / "policy_table.csv"):
        cross[(w_, r["condition"])] = r


def contrast(w_, cond, ref):
    """paired effect from the per-workload contrasts file (written by final_analyze.py)"""
    for r in rows(EV / f"analysis_{w_}" / "contrasts.csv"):
        if r["cond"] == cond and r["ref"] == ref and r["metric"] == "makespan_e2e_s":
            return f(r["effect_pct"]), f(r["ci_lo_pct"]), f(r["ci_hi_pct"])
    return None


fig, axs = plt.subplots(1, 2, figsize=(3.45, 2.2), sharey=True)
for ax, (ref_name, refs) in zip(axs, [("vs static HEFT", "HEFT_param_model"), ("vs blind B4", "B4")]):
    for k, (cfg, colr, dx) in enumerate([("cpu", "#1f5fa8", -0.13), ("gpu", "#d98a1f", 0.13)]):
        for j, w_ in enumerate(WL):
            r = contrast(w_, f"PRED_RANK_GREEDY_{cfg}", f"{refs}_{cfg}")
            if r:
                ax.errorbar(r[0], -j + dx, xerr=[[r[0] - r[1]], [r[2] - r[0]]], fmt="o", ms=2.6, lw=0.8, capsize=1, color=colr,
                            label=("CPU only" if cfg == "cpu" else "CPU + strict GPU") if j == 0 else None)
    ax.axvline(0, color="k", lw=0.5); ax.axvspan(-2, 2, color="#dddddd", alpha=0.6, lw=0)
    ax.set_title("PRED " + ref_name, fontsize=7); ax.set_xlabel("effect on makespan (%)")
axs[0].set_yticks([-j for j in range(len(WL))]); axs[0].set_yticklabels(WL, fontsize=6.3)
fig.legend(*axs[0].get_legend_handles_labels(), fontsize=6, ncol=2, loc="lower center", bbox_to_anchor=(0.55, -0.24))
save(fig, "fig_final_workloads.png")

# ---- 4. where the tasks ran ----------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.45, 2.1))
names = ["B4", "B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E", "HEFT_param_model", "PEFT_param_model"]
for j, p in enumerate(names):
    r = pt[f"{p}_ext"]
    cpu, gpu = f(r["tasks_cpu"]), f(r["tasks_gpu"])
    ax.bar(j, cpu, color="#9bb7d4"); ax.bar(j, gpu, bottom=cpu, color="#e2a33d")
    ax.text(j, cpu + gpu + 3, f"GPU busy\n{f(r['gpu_busy_frac']):.2f}", ha="center", fontsize=5.6)
ax.set_xticks(range(len(names))); ax.set_xticklabels([SHORT[n].replace(" (", "\n(") for n in names], fontsize=5.6)
ax.set_ylabel("tasks per run (of 257)"); ax.set_ylim(0, 345)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#9bb7d4", label="CPU (P+E)"), Patch(color="#e2a33d", label="GPU (RTX 3050)")], fontsize=6, ncol=2, loc="upper left")
save(fig, "fig_final_placement.png")

# ---- 5. hold-out error of the cost model (never used for fitting) ------------------------------------------------------
hold = []
for ln in open(FIN / "models" / "train.stdout.txt", encoding="utf-8"):
    m = re.match(r"holdout (\S+) (\{.*\})", ln.strip())
    if m:
        d = eval(m.group(2), {"__builtins__": {}}, {"nan": float("nan"), "inf": float("inf")}) if "nan" in m.group(2) else json.loads(m.group(2).replace("'", '"'))
        hold.append((m.group(1), d))
fig, ax = plt.subplots(figsize=(3.45, 2.1))
keys = sorted(hold, key=lambda t: t[0])
vals = []
for name, d in keys:
    v = d.get("median_ape", d.get("median_abs_pct_err", d.get("mdape")))
    vals.append((name, v))
names_, v_ = zip(*vals)
pct = [(x * 100 if x < 2 else x) for x in v_]
colr = ["#e2a33d" if n.endswith("|G") or n.endswith("_G") else ("#1f5fa8" if n.endswith("P") else "#6aa6e0") for n in names_]
ax.barh(range(len(names_)), pct, color=colr)
ax.set_yticks(range(len(names_))); ax.set_yticklabels([n.replace("img_", "").replace("|", " on ") for n in names_], fontsize=5.8)
ax.invert_yaxis(); ax.set_xlabel("median absolute error on hold-out tasks (%)")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#1f5fa8", label="P core"), Patch(color="#6aa6e0", label="E core"), Patch(color="#e2a33d", label="GPU")], fontsize=6, loc="lower right")
save(fig, "fig_final_model_error.png")

# ---- 6. architecture of the final framework (static plan versus dynamic dispatch) ------------------------------------------
fig, ax = plt.subplots(figsize=(3.45, 3.1))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")


def box(x, y, w_, h_, text, fc="#eef3f9", ec="#1f5fa8", fs=5.8):
    ax.add_patch(FancyBboxPatch((x, y), w_, h_, boxstyle="round,pad=0.3,rounding_size=1.5", fc=fc, ec=ec, lw=0.7))
    ax.text(x + w_ / 2, y + h_ / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.25)


def arrow(x1, y1, x2, y2, c="#444444", ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=0.7, color=c, ls=ls, shrinkA=0, shrinkB=0))


box(1, 85, 30, 13, "Workflow DAG\n257 tasks", fc="#f4f4f4", ec="#777777")
box(35, 85, 30, 13, "Cost model\nridge per (stage, pool)", fc="#fdf3e0", ec="#d98a1f")
box(69, 85, 30, 13, "GPU eligibility\nverified spike rows", fc="#fdf3e0", ec="#d98a1f")
box(1, 52, 46, 24, "STATIC\nplan before the run\nHEFT, PEFT, HEFT-E2E\nfixed worker per task", fc="#f3ecf7", ec="#8e5ea2")
box(53, 52, 46, 24, "DYNAMIC\ndecide while running\nB4, B4-param-first,\nPRED, PRED-E2E\nrank order, idle-worker binding", fc="#e8f0fa", ec="#1f5fa8")
box(1, 28, 98, 12, "Coordinator: ready queue, dependency gating, eligibility check, event log", fc="#f4f4f4", ec="#777777")
box(1, 2, 28, 15, "P cores\n6 workers", fc="#dce8f5")
box(36, 2, 28, 15, "E cores\n7 workers", fc="#e6f0e0", ec="#4c9f70")
box(71, 2, 28, 15, "CUDA worker G\nRTX 3050", fc="#fbe9c8", ec="#d98a1f")
for x in (16, 50, 84):
    arrow(x, 85, x, 78 if x != 84 else 78)
ax.plot([16, 84], [81, 81], color="#444444", lw=0.7)
arrow(24, 52, 24, 40); arrow(76, 52, 76, 40)
for x in (15, 50, 85):
    arrow(x, 28, x, 17.5)
ax.text(50, 21.5, "completions fed back to the dynamic policies", fontsize=5.2, color="#b03030", ha="center", style="italic")
save(fig, "fig_final_architecture.png")
