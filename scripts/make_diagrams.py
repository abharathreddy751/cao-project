"""Stage 5 figures: three diagrams (SVG + PNG, matplotlib patches and text only) and, with --analysis, the re-drawn
Stage 4 analysis figures. Writes only into a NEW directory (refuses to overwrite existing files unless --force).

  python scripts/make_diagrams.py [--out data/results/stage5_20261013/figures] [--analysis] [--force]

  montage_dag             Montage DAG by transformation, read from the primary instance's montage-workflow.yml
  system_architecture     coordinator, ready queue, policies, estimator interface, pools, event log, dataset, analysis
  predictor_ladder_flow   baselines, published list schedulers, estimator ladder, instrument, experiment flow
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = ROOT / "data/montage/instances/d1.1_dss2b_c56.7_24.0/data/montage-workflow.yml"
S4 = ROOT / "data/results/stage4_20261012"
# Okabe-Ito, colour-blind-safe; each fill is light so black text stays readable
C = {"blue": "#CFE3F3", "orange": "#FBE3B5", "green": "#BFE6D8", "pink": "#F1D3E3", "grey": "#E6E6E6", "sky": "#D5EEFA",
     "yellow": "#F8F0B0"}


def canvas(w, h, xmax, ymax):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax), ax.set_ylim(0, ymax), ax.axis("off")
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99)
    return fig, ax


def box(ax, x, y, w, h, text, fc="blue", fs=9, bold_first=True, lw=1.1, ls="-", ec="#333333"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=C.get(fc, fc), ec=ec, lw=lw, ls=ls))
    lines = text.split("\n")
    if bold_first and len(lines) > 1:
        ax.text(x + w / 2, y + h - 0.12, lines[0], ha="center", va="top", fontsize=fs, fontweight="bold")
        ax.text(x + w / 2, y + h - 0.12 - 1.7 * fs / 72 * 1.1, "\n".join(lines[1:]), ha="center", va="top", fontsize=fs - 1)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold_first else "normal")


def arrow(ax, p, q, text="", fs=8, ls="-", both=False, color="#222222", off=(0, 0.12), rad=0.0):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="<|-|>" if both else "-|>", lw=1.2, color=color, ls=ls,
                                                    mutation_scale=11, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha="center", va="bottom", fontsize=fs,
                bbox=dict(fc="white", ec="none", pad=0.6))


def polyline(ax, pts, text="", fs=8, ls="-", tpos=None):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1], ys[:-1], color="#222222", lw=1.2, ls=ls)
    ax.plot(xs[-2:], ys[-2:], color="#222222", lw=1.2, ls=ls)
    ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>", lw=1.2, color="#222222", mutation_scale=11, ls=ls))
    if text:
        ax.text(*(tpos or pts[1]), text, fontsize=fs, ha="center", va="bottom", bbox=dict(fc="white", ec="none", pad=0.6))


def save(fig, outdir: Path, name: str, force: bool):
    out = []
    for ext in ("svg", "png"):
        p = outdir / f"{name}.{ext}"
        if p.exists() and not force:
            raise FileExistsError(f"{p} exists (use --force to replace)")
        fig.savefig(p, dpi=150)
        out.append(p)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------------------------------------------- (a)
def montage_dag(outdir, force):
    import yaml
    wf = yaml.safe_load(INSTANCE.read_text(encoding="utf-8"))
    name = {j["id"]: j["name"] for j in wf["jobs"]}
    parents = collections.defaultdict(list)
    edges = collections.Counter()
    for d in wf["jobDependencies"]:
        for ch in d.get("children", []):
            parents[ch].append(d["id"])
            edges[(name[d["id"]], name[ch])] += 1
    level: dict[str, int] = {}

    def lv(i):
        if i not in level:
            level[i] = 0 if not parents[i] else 1 + max(lv(p) for p in parents[i])
        return level[i]
    for i in name:
        lv(i)
    nodes = {}  # transformation -> (level, count)
    for i, n in name.items():
        nodes[n] = (level[i], collections.Counter(name.values())[n])
    assert len({v[0] for v in nodes.values()}) == len(nodes)  # one transformation per level (true for this instance)
    order = sorted(nodes, key=lambda n: nodes[n][0])
    n_edges = sum(edges.values())

    fig, ax = canvas(18, 5.6, 18.4, 5.6)
    bw, bh, gap, y0 = 1.5, 0.95, 0.8, 2.1
    xs = {n: 0.35 + nodes[n][0] * (bw + gap) for n in order}
    for n in order:
        lvl, cnt = nodes[n]
        fc = {"mProject": "orange", "mDiffFit": "blue"}.get(n, "grey")
        box(ax, xs[n], y0, bw, bh, f"{n}\n{cnt} task{'s' if cnt > 1 else ''}", fc=fc, fs=10)
        ax.text(xs[n] + bw / 2, y0 + bh + 0.12, f"level {lvl}", ha="center", fontsize=8, color="#555555")
    cy = y0 + bh / 2
    for (a, b), k in edges.items():
        la, lb = nodes[a][0], nodes[b][0]
        txt = f"{k} edge{'s' if k > 1 else ''}"
        if lb - la == 1:
            arrow(ax, (xs[a] + bw, cy), (xs[b], cy), txt, off=(0, 0.1))
        else:  # level-skipping edges are routed above (towards the join) or below, clear of the boxes
            up = (a, b) != ("mAdd", "mViewer") and (la < 2 or a == "mBgModel")
            ytop = y0 + bh + 0.95 if up else y0 - 0.95
            if (a, b) == ("mBackground", "mAdd"):
                ytop = y0 - 0.95
            elif (a, b) == ("mProject", "mBackground"):
                ytop = y0 + bh + 0.95
            xa, xb = xs[a] + bw * (0.7 if ytop > y0 else 0.3), xs[b] + bw * 0.3
            ya = y0 + bh if ytop > y0 else y0
            polyline(ax, [(xa, ya), (xa, ytop), (xb, ytop), (xb, ya)], txt, tpos=((xa + xb) / 2, ytop + 0.04))
    ax.text(9.2, 5.3, "Montage workflow, primary instance d1.1_dss2b_c56.7_24.0: one node per transformation", ha="center",
            fontsize=12, fontweight="bold")
    ax.text(9.2, 4.95, f"{len(name)} tasks, {n_edges} dependency edges (from jobDependencies in montage-workflow.yml); "
            "evidence: real workflow definition", ha="center", fontsize=9)
    ax.text(0.35, 0.35, "Edge labels count task-to-task dependencies between the two transformations. mProject (orange) is 98.7% of "
            "sequential time (STAGE3_FREEZE); mDiffFit has 2 parents per task.\nmBgModel feeds every mBackground; mBackground "
            "feeds both mImgtbl and mAdd; mViewer writes the final mosaic image.", fontsize=8.5, va="bottom")
    return save(fig, outdir, "montage_dag", force)


# ---------------------------------------------------------------------------------------------------------------- (b)
def system_architecture(outdir, force):
    fig, ax = canvas(16, 11, 16.4, 11)
    box(ax, 0.4, 9.5, 4.6, 1.1, "Workflow adapter\nPegasus YAML -> internal DAG\nexternal-command tasks, declared files", "sky")
    box(ax, 6.0, 9.5, 9.6, 1.1, "Experiment runner\ndesign file + seeded interleaved blocks, one policy per run, "
        "run manifest (hashes, machine, evidence label)", "yellow")
    ax.add_patch(FancyBboxPatch((0.4, 4.3), 15.2, 4.7, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#FAFAFA", ec="#333333", lw=1.4, ls="--"))
    ax.text(15.4, 8.75, "Coordinator (pinned to a reserved core)", fontsize=10.5, fontweight="bold", va="center", ha="right")
    box(ax, 0.8, 6.2, 3.6, 1.9, "DAG manager + ready queue\ndependencies, ready tasks,\ncompletions release children", "blue")
    box(ax, 5.2, 6.2, 5.0, 1.9, "Scheduler policy (swappable)\nB0 P-only/E-only, B1 round robin, B2 static, B3 shortest\n"
        "queue, B4 greedy eligible, B5 criticality, random,\nHEFT, PEFT, EFT, rank-priority EFT (instrument)", "orange", fs=9)
    box(ax, 11.0, 6.2, 4.2, 1.9, "Estimator interface (swappable)\nE0 constant, E1 profile, E3 history, +rc,\n"
        "Ridge, CatBoost, MLP; predicts task time\nper worker pool", "green", fs=9)
    box(ax, 0.8, 4.6, 3.6, 1.2, "Event log (JSONL)\nevery state transition, decision\ncontext, decision time", "grey")
    box(ax, 5.2, 4.6, 5.0, 1.2, "Dispatcher\none eligibility check for every policy;\nplacement chosen at dispatch", "blue")
    box(ax, 11.0, 4.6, 4.2, 1.2, "Runtime state\nidle workers, queue lengths,\nrunning tasks", "blue")
    # pools
    pools = [("P pool\nperformance cores", "orange"), ("E pool\nefficiency cores", "orange"),
             ("G pool (CUDA)\nRTX 3050, GPU workload", "pink"), ("R pool\nremote emulation (loopback)", "grey")]
    for k, (t, fc) in enumerate(pools):
        box(ax, 4.6 + 2.65 * k, 2.5, 2.45, 1.1, t, fc, fs=9)
    ax.text(4.6, 2.3, "Worker pools (affinity-pinned processes)", fontsize=9, fontweight="bold", va="center")
    # bottom row
    box(ax, 0.4, 0.4, 3.9, 1.2, "Analysis\npaired bootstrap, effects, figures", "yellow", fs=9)
    box(ax, 5.4, 0.4, 4.4, 1.2, "Dataset builder\ndecision-time-safe features,\nleave-instance-out splits", "sky", fs=9)
    box(ax, 11.0, 0.4, 4.6, 1.2, "Predictor training\nRidge, CatBoost, MLP; held-out\nevaluation, frozen before Stage 4", "green", fs=9)
    # arrows
    arrow(ax, (2.6, 9.5), (2.6, 8.1), "tasks", off=(0.5, -0.05))
    arrow(ax, (8.0, 9.5), (8.0, 9.0), "", off=(0, 0))
    ax.text(8.2, 9.22, "runs one policy per block", fontsize=8, va="center")
    arrow(ax, (4.4, 7.2), (5.2, 7.2), "ready", off=(0, 0.1))
    arrow(ax, (10.2, 7.15), (11.0, 7.15), "", both=True)
    ax.text(10.6, 7.3, "query", fontsize=8, ha="center", va="bottom", bbox=dict(fc="white", ec="none", pad=0.6))
    arrow(ax, (7.7, 6.2), (7.7, 5.8), "choice", off=(0.55, -0.1))
    arrow(ax, (11.0, 5.2), (10.2, 5.2), "", both=True)
    ax.text(10.6, 5.3, "state", fontsize=8, ha="center", va="bottom", bbox=dict(fc="white", ec="none", pad=0.6))
    arrow(ax, (5.2, 5.2), (4.4, 5.2), "log", off=(0, 0.1))
    ax.plot([7.7, 7.7], [4.6, 4.0], color="#222222", lw=1.2)
    ax.plot([5.8, 14.2], [4.0, 4.0], color="#222222", lw=1.2)
    for k in range(4):
        x = 4.6 + 2.65 * k + 1.2
        arrow(ax, (x, 4.0), (x, 3.6), both=True)
    ax.text(14.4, 4.0, "dispatch / completion", fontsize=8, ha="left", va="center")
    arrow(ax, (1.6, 4.6), (1.6, 1.6), "event logs", off=(0.75, 0.0))
    polyline(ax, [(3.5, 4.6), (3.5, 1.85), (7.6, 1.85), (7.6, 1.6)], "event logs", tpos=(5.2, 1.89))
    arrow(ax, (9.8, 1.0), (11.0, 1.0), "dataset", off=(0, 0.1))
    polyline(ax, [(15.6, 1.0), (16.0, 1.0), (16.0, 7.1), (15.2, 7.1)], "frozen model files", ls="--", tpos=(16.0, 4.0))
    ax.texts[-1].set_rotation(90), ax.texts[-1].set_va("center")
    ax.text(0.4, 10.9, "System architecture (consistent with ARCHITECTURE.md and ARCHITECTURE_DECISIONS.md, Stage 5)", fontsize=11, fontweight="bold",
            va="bottom")
    ax.set_ylim(0, 11.3)
    return save(fig, outdir, "system_architecture", force)


# ---------------------------------------------------------------------------------------------------------------- (c)
def predictor_ladder_flow(outdir, force):
    fig, ax = canvas(16.4, 10.0, 16.4, 9.9)
    ax.text(0.3, 9.6, "Predictor ladder and experiment flow", fontsize=12, fontweight="bold", va="center")
    ax.text(0.3, 9.25, "Policies compared on the same seeded workload blocks (PROJECT_SPEC, EVALUATION_PROTOCOL); ladder order as frozen "
            "before Stage 4", fontsize=9, va="center")
    box(ax, 0.3, 4.2, 2.3, 2.6, "Workload\nMontage DAG\n(59 tasks) +\nGPU image DAG\n(68 tasks)", "sky", fs=9.5)
    lane_x, lane_w = 3.4, 8.2
    lanes = [
        (7.75, "Non-predictive baselines", "grey", ["B0\nP-only", "B1 round\nrobin", "B2\nstatic", "B3 shortest\nqueue", "B4 greedy\neligible",
                                                    "B5\ncriticality", "random"]),
        (6.25, "Published static list schedulers (profile cost matrix)", "green", ["HEFT (E1)", "PEFT (E1)"]),
    ]
    for y, title, fc, items in lanes:
        ax.add_patch(FancyBboxPatch((lane_x, y - 0.1), lane_w, 1.3, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#FAFAFA", ec="#888888", lw=0.8))
        ax.text(lane_x + 0.15, y + 0.98, title, fontsize=9, fontweight="bold", va="center")
        w = (lane_w - 0.3 - 0.1 * (len(items) - 1)) / len(items) if len(items) > 2 else 1.6
        for k, t in enumerate(items):
            box(ax, lane_x + 0.15 + k * (w + 0.1), y + 0.0, w, 0.7, t, fc, fs=8, bold_first=False)
    ay = 3.75  # ladder lane
    ax.add_patch(FancyBboxPatch((lane_x, ay - 0.35), lane_w, 2.55, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#FAFAFA", ec="#0072B2", lw=1.4))
    ax.text(lane_x + 0.15, ay + 1.95, "EFT with a predictor ladder (more prediction, more inference cost)", fontsize=9, fontweight="bold", va="center")
    rungs = [("E0\nconstant", "grey", "no signal"), ("E1\nprofile", "blue", "static table"), ("E3\nhistory", "blue", "moving mean"),
             ("E1 + rc", "blue", "online recalib."), ("Ridge", "orange", "learned"), ("CatBoost", "orange", "learned"), ("MLP", "orange", "learned")]
    w = 1.0
    for k, (t, fc, sub) in enumerate(rungs):
        x = lane_x + 0.15 + k * (w + 0.1)
        box(ax, x, ay + 0.6, w, 0.95, t, fc, fs=8.5, bold_first=False)
        ax.text(x + w / 2, ay + 0.5, sub, fontsize=7, ha="center", va="top", color="#444444")
        if k:
            arrow(ax, (x - 0.1, ay + 1.07), (x, ay + 1.07))
    ax.text(lane_x + 0.15, ay - 0.05, "Cost order of the rungs run in Stage 4: E1 < E3 < E1+rc < Ridge < CatBoost < MLP (inference median 1.2 to 478 us);\n"
            "E0 is the no-information reference rung. TabM not run: pre-registered entry rule not met.", fontsize=7.5, va="center")
    box(ax, lane_x, 2.3, lane_w, 0.85, "Instrument: rank-priority EFT with E1\nupward-rank task priority + predicted, queue-aware earliest finish time",
        "pink", fs=9)
    for y in (8.1, 6.6, 4.9, 2.72):
        arrow(ax, (2.6, 5.5), (lane_x, y))
    box(ax, lane_x, 0.4, lane_w, 1.35, "Stage 3 data for the learned rungs\nevent logs -> dataset builder (decision-time-safe) -> Ridge, CatBoost, MLP; "
        "leave-instance-out tuning,\nheld-out final test evaluated once; selection margin 2.0%", "sky", fs=9)
    polyline(ax, [(11.6, 1.07), (11.95, 1.07), (11.95, 3.4), (11.6, 3.4)], "", ls="--")
    ax.text(12.05, 2.2, "frozen models", fontsize=8, rotation=90, va="center", ha="left")
    # collector: every policy lane feeds the real runs
    for y in (8.1, 6.6, 4.9, 2.72):
        ax.plot([11.6, 12.35], [y, y], color="#222222", lw=1.2)
    ax.plot([12.35, 12.35], [2.72, 8.05], color="#222222", lw=1.2)
    arrow(ax, (12.35, 8.05), (12.7, 8.05))
    steps = [("Real runs on this machine\nseeded interleaved blocks; every policy\nonce per block; 6P+7E, 2P+7E, GPU regimes", "yellow"),
             ("Measured per run\nmakespan, queue wait,\nscheduling time, decision time", "blue"),
             ("Paired analysis\neffect vs reference baseline, 95% CI\n(bootstrap), Holm for the confirmatory family", "green"),
             ("Figures and tables\nevidence label on every figure", "orange")]
    for k, (t, fc) in enumerate(steps):
        y = 7.3 - k * 1.95
        box(ax, 12.7, y, 3.5, 1.5, t, fc, fs=8.5)
        if k:
            arrow(ax, (14.45, y + 1.95), (14.45, y + 1.5))
    ax.text(0.3, 0.2, "Reference baseline: B0 P-only (main, GPU) or B4 greedy (scarce-P regime), fixed in the design file before the runs.",
            fontsize=8, va="center")
    return save(fig, outdir, "predictor_ladder_flow", force)


# ---------------------------------------------------------------------------------------------------------------- analysis
def analysis_figures(outdir, force):
    sys.path.insert(0, str(ROOT / "src"))
    from caosched.analysis.stats_paired import load_result, make_figures
    out = []
    for src, name in (("analysis_main", "analysis_main"), ("analysis_regimeR", "analysis_regimeR"), ("gpu/analysis", "gpu_analysis")):
        d = outdir / name
        if d.exists() and any(d.glob("*.png")) and not force:
            raise FileExistsError(f"{d} has figures (use --force to replace)")
        out += make_figures(load_result(S4 / src), d)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "data/results/stage5_20261013/figures"))
    ap.add_argument("--analysis", action="store_true", help="also re-draw the Stage 4 analysis figures into <out>/<analysis>/")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in (montage_dag, system_architecture, predictor_ladder_flow) + ((analysis_figures,) if a.analysis else ()):
        files += f(outdir, a.force)
    print("\n".join(str(p) for p in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
