p = "build_paper_final.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


rep("(@tab:early, @fig:early)", "(@tab:early, @fig:early_f)")
rep("The static plan is not wrong in total (planned and actual makespan differ by 3% to 12%), but", "The static plan is not wrong in total (planned over actual makespan was between 0.88 and 1.03), but")
rep("(about 10 ms more scheduling time than B4)", "(about 9 ms more scheduling time than B4)")
rep("2.8% to 4.8% when 40 are heavy or the cost ratio is 20, and nothing on the uniform workload;",
    "2.8% to 4.8% on the CPU (6.0% to 7.9% with the strict set) when 40 are heavy or the cost ratio is 20, and nothing on the uniform workload;")
rep("On the CPU the dynamic dispatcher beats the static plan by about 5% and with GPU sets by 8% to 12%.",
    "On the CPU the dynamic dispatcher beats the static plan by about 5%, with the strict GPU set by 8% to 12%, and with the extended set by 2% to 3%.")
rep("finishes a workflow 5% to 12% sooner than a static HEFT plan from the same model", "finishes a workflow 2% to 12% sooner than a static HEFT plan from the same model (5% on the CPU, 12% with the strict GPU set)")
# references after the appendices (IEEE order)
rep("    d.references()\n    # ------------------------------------------------------------------ appendix\n", "    # ------------------------------------------------------------------ appendix\n")
rep("    o = OUT + \"\\\\\" + name\n", "    d.references()\n    o = OUT + \"\\\\\" + name\n")
open(p, "w", encoding="utf-8").write(s)
print("paper patched")
