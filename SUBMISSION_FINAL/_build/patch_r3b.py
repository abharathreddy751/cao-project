"""Cross-references of Review 3 by label (numbers resolved in a second build pass)."""
import re
p = "build_review3.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


def label_before(call_start, key):
    """insert d.nextlabel before the first line that contains call_start"""
    global s
    i = s.index(call_start)
    k = s.rfind("\n", 0, i) + 1
    s = s[:k] + f'd.nextlabel = "{key}"\n' + s[k:]


label_before('d.table("Primary workload h16_l120', "prim")
label_before('d.figure(FF + r"\\fig_final_makespan.png"', "mk")
label_before('d.table("Confirmatory contrasts (Holm', "conf")
label_before('d.figure(FF + r"\\fig_final_forest.png"', "forest")
label_before('d.figure(FF + r"\\fig_final_workloads.png"', "wl")
label_before('d.figure(FF + r"\\fig_final_placement.png"', "place")
label_before('d.figure(FF + r"\\fig_final_model_error.png"', "err")
label_before('d.table("Unseen chain orders (exploratory)', "unseen")
label_before('d.figure(FIG + r"\\fig_per_order.png"', "perorder")
label_before('d.figure(FIG + r"\\fig_dose_heavy.png"', "dose")
label_before('d.figure(FIG + r"\\fig_remote.png"', "remote")
label_before('d.figure(FIG + r"\\dashboard_compare.jpg"', "dash")
label_before('d.h2("Scheduling overhead")', "ovh")

rep("Table V gives the end-to-end makespan", "@tab:prim gives the end-to-end makespan")
rep("Fig. 3 adds the 95% intervals", "@fig:mk adds the 95% intervals")
rep("The ten confirmatory contrasts are in Table VI and Fig. 4.", "The ten confirmatory contrasts are in @tab:conf and @fig:forest.")
rep("(Fig. 5, exploratory outside the primary session)", "(@fig:wl, exploratory outside the primary session)")
rep("of the 257 tasks (Fig. 6). One CUDA worker", "of the 257 tasks (@fig:place). One CUDA worker")
rep("GPU stages with 23% to 31% (Fig. 7).", "GPU stages with 23% to 31% (@fig:err).")
rep("never used before (Table V, Fig. 3).", "never used before (@tab:unseen, @fig:perorder).")
rep("become the majority (Fig. 4), consistent", "become the majority (@fig:dose), consistent")
rep("than without it (Fig. 6). Prediction accuracy", "than without it (@fig:remote). Prediction accuracy")
rep("Section IV-D shows why the two differ.", "Section @sec:ovh shows why the two differ.")
rep("side by side (Fig. 2).", "side by side (@fig:dash).")
# the umbrella heading is dropped; the earlier-study headings say what they are
rep('d.h2("Earlier study: Montage and hidden-cost workloads")\nd.h2("Montage: a valid null result")', 'd.h2("Earlier study: Montage, a valid null result")')
rep('d.h2("Hidden-cost workload")', 'd.h2("Earlier study: hidden-cost workload")')
# table widths
rep("[0.75, 0.55, 1.0, 0.5, 0.45, 0.85], span=True, size=6.5)", "[0.62, 0.45, 0.95, 0.5, 0.55, 0.85], span=True, size=6.5)")
open(p, "w", encoding="utf-8").write(s)
print("r3b ok")
