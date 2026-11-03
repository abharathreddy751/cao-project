"""Figures for the publications, all from stored evidence files (no typed results). Output: publications/figures/*.png (300 dpi)."""
import csv, glob, json, os, shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = r"D:\cao project"
R = os.path.join(ROOT, "data", "results")
OV = os.path.join(R, "overnight_20261027")
FIG = os.path.join(ROOT, "publications", "figures")
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 8, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False})
COL = {"B4": "#8c8c8c", "B4_param_first": "#4c9f70", "B0_P_only": "#c9a227", "PRED_RANK_GREEDY": "#1f5fa8", "HEFT": "#8e5ea2", "PEFT": "#d1495b"}


def effects(d, ref_cond=None):
    out = {}
    for r in csv.DictReader(open(os.path.join(d, "effects.csv"), encoding="utf-8")):
        if r["variant"] == "primary" and r["metric"] == "makespan_s" and r["effect_pct"]:
            out[r["cond"]] = (float(r["effect_pct"]), float(r["ci_lo_pct"]), float(r["ci_hi_pct"]), int(r["n_blocks"]))
    return out


def pooled(d):
    return {r["condition"]: (float(r["geo_mean_s"]), float(r["ci_lo_s"]), float(r["ci_hi_s"]))
            for r in csv.DictReader(open(os.path.join(d, "summary.csv"), encoding="utf-8")) if r["scope"] == "pooled_log_scale" and r["geo_mean_s"]}


def save(name):
    plt.savefig(os.path.join(FIG, name), dpi=300, bbox_inches="tight")
    plt.close()


# 1. mean makespan, 6P+7E and 2P+7E, unseen orders
fig, ax = plt.subplots(1, 2, figsize=(3.45, 1.9), sharey=False)
for a, (ph, title) in zip(ax, (("phase3", "6P+7E, 12 new orders"), ("phase3b", "2P+7E, 8 new orders"))):
    pl = pooled(os.path.join(OV, ph, "analysis_ref_B4"))
    names = ["B4", "B4_param_first", "PRED_RANK_GREEDY", "B0_P_only"]
    lab = ["B4", "hand\nrule", "PRED", "P-only"]
    for i, n in enumerate(names):
        g, lo, hi = pl[n]
        a.bar(i, g, color=COL[n], width=0.7)
        a.errorbar(i, g, yerr=[[g - lo], [hi - g]], color="k", lw=0.7, capsize=1.5)
        a.text(i, hi + 0.05 * max(v[0] for v in pl.values()), f"{g:.2f}", ha="center", fontsize=6)
    a.set_xticks(range(4)); a.set_xticklabels(lab, fontsize=6.5)
    a.set_title(title, fontsize=7); a.set_ylabel("makespan (s)" if a is ax[0] else "")
fig.tight_layout()
save("fig_makespan_policies.png")

# 2. per-order effects
fig, ax = plt.subplots(1, 2, figsize=(3.45, 2.0))
for a, (ph, title) in zip(ax, (("phase3", "6P+7E (12 orders)"), ("phase3b", "2P+7E (8 orders)"))):
    rows = [r for r in csv.DictReader(open(os.path.join(OV, ph, "per_order_summary.csv"), encoding="utf-8")) if r["order"].startswith("order_")]
    y = list(range(len(rows)))
    a.barh([i + 0.18 for i in y], [float(r["PRED_minus_B4_pct"]) for r in rows], height=0.34, color=COL["PRED_RANK_GREEDY"], label="PRED vs B4")
    a.barh([i - 0.18 for i in y], [float(r["PRED_minus_hand_pct"]) for r in rows], height=0.34, color=COL["B4_param_first"], label="PRED vs hand rule")
    a.axvline(0, color="k", lw=0.6)
    a.set_yticks(y); a.set_yticklabels([r["order"].replace("order_", "") for r in rows], fontsize=5.5)
    a.set_xlabel("change in makespan (%)", fontsize=7); a.set_title(title, fontsize=7); a.invert_yaxis()
ax[0].legend(fontsize=5.5, loc="lower left", frameon=False)
fig.tight_layout()
save("fig_per_order.png")

# 3. dose-response and heavy-count
fig, ax = plt.subplots(1, 2, figsize=(3.45, 2.0))
dose = [("6", "phase3c/analysis_h006_ref_B4"), ("15", "phase3c/analysis_h015_ref_B4"), ("40", "phase3c/analysis_h040_ref_B4"), ("120", "phase3c/analysis_h120_ref_B4")]
dose2 = [("15", "phase3e/analysis_dose2_h015_ref_B4"), ("40", "phase3e/analysis_dose2_h040_ref_B4")]
xs = {"6": 3, "15": 7.5, "40": 20, "120": 60}
for lab, d in dose:
    e = effects(os.path.join(OV, d))["PRED_RANK_GREEDY"]
    ax[0].errorbar(xs[lab] * 0.93, e[0], yerr=[[e[0] - e[1]], [e[2] - e[0]]], fmt="o", color=COL["PRED_RANK_GREEDY"], ms=3, capsize=1.5, lw=0.8)
for lab, d in dose2:
    e = effects(os.path.join(OV, d))["PRED_RANK_GREEDY"]
    ax[0].errorbar(xs[lab] * 1.08, e[0], yerr=[[e[0] - e[1]], [e[2] - e[0]]], fmt="s", color="#5aa0e0", ms=3, capsize=1.5, lw=0.8)
ax[0].axhline(0, color="k", lw=0.6); ax[0].set_xscale("log"); ax[0].set_xticks([3, 7.5, 20, 60]); ax[0].set_xticklabels(["3", "7.5", "20", "60"]); ax[0].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
ax[0].set_xlabel("heavy : light cost ratio", fontsize=7); ax[0].set_ylabel("PRED vs B4 (%)", fontsize=7)
ax[0].plot([], [], "o", color=COL["PRED_RANK_GREEDY"], ms=3, label="4 orders"); ax[0].plot([], [], "s", color="#5aa0e0", ms=3, label="8 more orders")
ax[0].legend(fontsize=5.5, frameon=False, loc="lower left", bbox_to_anchor=(0.0, 0.12))
hc = [(4, "phase3g/analysis_heavy04_ref_B4"), (8, "phase3g/analysis_heavy08_ref_B4"), (16, "phase3/analysis_ref_B4"), (40, "phase3g/analysis_heavy40_ref_B4")]
for h, d in hc:
    e = effects(os.path.join(OV, d))["PRED_RANK_GREEDY"]
    ax[1].errorbar(h, e[0], yerr=[[e[0] - e[1]], [e[2] - e[0]]], fmt="o", color=COL["PRED_RANK_GREEDY"], ms=3, capsize=1.5, lw=0.8)
    h2 = effects(os.path.join(OV, d))["B4_param_first"]
    ax[1].plot(h, h2[0], "x", color=COL["B4_param_first"], ms=4)
ax[1].axhline(0, color="k", lw=0.6); ax[1].set_xlabel("heavy chains (of 64)", fontsize=7); ax[1].set_xticks([4, 8, 16, 40])
ax[1].plot([], [], "x", color=COL["B4_param_first"], ms=4, label="hand rule"); ax[1].legend(fontsize=5.5, frameon=False, loc="lower right")
fig.tight_layout()
save("fig_dose_heavy.png")

# 4. overhead
v = json.load(open(os.path.join(OV, "phase3d", "session_verification.json")))["mean_per_run_s"]
fig, ax = plt.subplots(figsize=(3.45, 1.9))
names = ["B4", "B4_fix", "B4_param_first", "B4_param_first_fix", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_fix"]
lab = ["B4", "B4\nfixed", "hand", "hand\nfixed", "PRED", "PRED\nfixed"]
k1 = "extra.decision_time_total_s (coordinator summary)"
k2 = "sum decision_time_s over task_dispatched events"
x = range(len(names))
ax.bar([i - 0.2 for i in x], [v[n][k1] * 1000 for n in names], 0.4, color="#c0504d", label="coordinator scheduling time")
ax.bar([i + 0.2 for i in x], [v[n][k2] * 1000 for n in names], 0.4, color="#4f81bd", label="per-dispatch decision time")
ax.set_xticks(list(x)); ax.set_xticklabels(lab, fontsize=6); ax.set_ylabel("ms per run", fontsize=7); ax.legend(fontsize=6, frameon=False)
fig.tight_layout()
save("fig_overhead.png")

# 5. remote emulation (level 30) vs registered level 1
fig, ax = plt.subplots(1, 2, figsize=(3.45, 1.9), sharey=True)
for a, (d, title) in zip(ax, ((os.path.join(R, "stage5_20261013", "analysis_remote"), "level 1 (registered)"), (os.path.join(OV, "phase4", "e3_analysis_ref_EFT_no_remote"), "level 30 (overnight)"))):
    e = effects(d)
    conds = [c for c in e if "remote" in c and "no_remote" not in c]
    for i, c in enumerate(conds):
        a.errorbar(i, e[c][0], yerr=[[e[c][0] - e[c][1]], [e[c][2] - e[c][0]]], fmt="o", ms=3, capsize=1.5, color="#1f5fa8" if "EFT" in c else "#8c8c8c", lw=0.8)
    a.axhline(0, color="k", lw=0.6)
    a.set_xticks(range(len(conds))); a.set_xticklabels([c.replace("_remote", "").replace("_", "\n") for c in conds], fontsize=5)
    a.set_title(title, fontsize=7)
ax[0].set_ylabel("vs EFT, no remote (%)", fontsize=7)
fig.tight_layout()
save("fig_remote.png")

# 6. heterogeneity: P/E kernel time and GPU speed-up
prof = sorted(glob.glob(os.path.join(ROOT, "data", "profiles", "overnight_remote_t512_it30", "*_profile.json")))[0]
ent = json.load(open(prof))["entries"]
fig, ax = plt.subplots(1, 2, figsize=(3.45, 1.9))
st = ["img_denoise", "img_edges", "img_features"]
for i, s in enumerate(st):
    p = next(e["median_s"] for e in ent if e["workload"] == s and e["pool"] == "P") * 1000
    e_ = next(e["median_s"] for e in ent if e["workload"] == s and e["pool"] == "E") * 1000
    ax[0].bar(i - 0.2, p, 0.4, color="#1f5fa8", label="P core" if i == 0 else None)
    ax[0].bar(i + 0.2, e_, 0.4, color="#c0504d", label="E core" if i == 0 else None)
ax[0].set_yscale("log"); ax[0].set_xticks(range(3)); ax[0].set_xticklabels(["denoise\n(x30)", "edges", "features"], fontsize=6); ax[0].set_ylabel("ms (512 px task)", fontsize=7); ax[0].legend(fontsize=6, frameon=False)
sp = json.load(open(os.path.join(R, "stage1_20261011", "gpu", "gpu_spike.json")))["rows"]
for stage, mk in (("img_edges", "o"), ("img_features", "s"), ("img_denoise", "^")):
    pts = sorted((r["side"], r["speedup"]) for r in sp if r["stage"] == stage and (stage != "img_denoise" or "8" in r["params"]))
    ax[1].plot([p[0] for p in pts], [p[1] for p in pts], marker=mk, ms=3, lw=0.8, label=stage.replace("img_", ""))
ax[1].axhline(1, color="k", lw=0.6, ls=":"); ax[1].set_xscale("log", base=2); ax[1].set_yscale("log"); ax[1].set_xlabel("tile side (px)", fontsize=7); ax[1].set_ylabel("GPU speed-up (x)", fontsize=7); ax[1].legend(fontsize=5.5, frameon=False)
fig.tight_layout()
save("fig_heterogeneity.png")

# 7. architecture
fig, ax = plt.subplots(figsize=(3.45, 3.0))
ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 10)


def box(x, y, w, h, text, fc="#dce6f2", fs=6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.12", fc=fc, ec="#333", lw=0.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)


def arr(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=6, lw=0.6, color="#333"))


box(0.2, 8.3, 3.0, 1.4, "Workflow / DAG\n(YAML, generator,\nimage chains)", "#fde9d9")
box(3.7, 8.3, 2.6, 1.4, "DAG manager\nready queue", "#dce6f2")
box(6.8, 8.3, 3.0, 1.4, "Scheduler policy\nB0-B5, EFT, HEFT,\nPEFT, PRED", "#e2efda")
box(6.8, 6.3, 3.0, 1.4, "Estimator\nstatic / history /\nlearned (ParamModel)", "#e2efda")
box(0.2, 6.3, 6.1, 1.4, "Coordinator (reserved core)\ndispatch loop, eligibility, timeouts,\nevent log, output verification", "#dce6f2")
box(0.2, 3.9, 1.9, 1.5, "P-core\nworkers\n(pinned)", "#c6d9f0", 5.5)
box(2.3, 3.9, 1.9, 1.5, "E-core\nworkers\n(pinned)", "#c6d9f0", 5.5)
box(4.4, 3.9, 1.9, 1.5, "CUDA\nworker\n(GPU)", "#c6d9f0", 5.5)
box(6.5, 3.9, 3.3, 1.5, "Remote worker\nproxy + node (loopback\nshim, or real link / Pi)", "#fff2cc", 5.2)
box(0.2, 1.6, 4.5, 1.5, "Event logs + run manifests\n(hashes, code version,\nenvironment)", "#ededed")
box(5.0, 1.6, 4.8, 1.5, "Analysis: paired log-ratio bootstrap,\nHolm, claims registry,\ndashboard", "#ededed")
box(0.2, 0.1, 9.6, 1.0, "Experiment runner: interleaved seeded blocks,\nRAM / power preflight, exclusion rules", "#f2f2f2")
arr(3.2, 9.0, 3.7, 9.0); arr(6.3, 9.0, 6.8, 9.0); arr(8.3, 8.3, 8.3, 7.7); arr(6.8, 7.0, 6.3, 7.0); arr(3.2, 6.3, 1.2, 5.4); arr(3.2, 6.3, 3.2, 5.4)
arr(3.2, 6.3, 5.3, 5.4); arr(5.0, 6.3, 8.0, 5.4); arr(3.2, 3.9, 2.4, 3.1); arr(6.5, 3.9, 7.4, 3.1)
save("fig_architecture.png")

# 8. survey: reported gains vs evaluation type (values from the papers' abstracts) and this work
fig, ax = plt.subplots(figsize=(3.45, 2.1))
items = [("LACHESIS [LACHESIS22]\n(simulation)", 26.7, "#8c8c8c"), ("Tan 2025\n(simulation)", 11.09, "#8c8c8c"), ("Meta-RL offload\n(simulation)", 21.0, "#8c8c8c"),
         ("DAG-DQN IoV\n(simulation)", 16.0, "#8c8c8c"), ("This work, 8 heavy\n(real, 4 orders)", 26.76, "#1f5fa8"), ("This work, 16 heavy\n(real, 12 orders)", 19.32, "#1f5fa8"),
         ("This work, 40 heavy\n(real, 4 orders)", 3.81, "#1f5fa8")]
ax.barh(range(len(items)), [i[1] for i in items], color=[i[2] for i in items])
ax.set_yticks(range(len(items))); ax.set_yticklabels([i[0].replace(" [LACHESIS22]", "") for i in items], fontsize=5.5); ax.invert_yaxis()
ax.set_xlabel("best reported makespan / delay reduction (%)", fontsize=7)
for i, it in enumerate(items):
    ax.text(it[1] + 0.4, i, f"{it[1]:g}", va="center", fontsize=6)
fig.tight_layout()
save("fig_reported_gains.png")

# 9. dashboard screenshot
src = glob.glob(r"C:\Users\Venkatesh\.claude\projects\D--cao-project\3d58deff-1b3c-4c56-8ffe-342c70bc7781\tool-results\mcp-Claude_Browser-blob-1793040527213-*.jpg")
if src:
    shutil.copy(src[0], os.path.join(FIG, "dashboard_compare.jpg"))
print(sorted(os.listdir(FIG)))
