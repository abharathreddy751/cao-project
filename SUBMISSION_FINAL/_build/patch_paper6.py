p = "build_paper_final.py"
s = open(p, encoding="utf-8").read()


def before(anchor, new):
    global s
    assert anchor in s, anchor[:70]
    s = s.replace(anchor, new + anchor, 1)


# expectations stated before the data (protocol) versus outcome
before('    # ------------------------------------------------------------------ V\n',
       '    d.nextlabel = "expect"\n'
       '    d.table("Expectations written in the protocol before the evaluation data, and what the data showed",\n'
       '            ["Id", "Expected before the data", "Outcome", "Held?"],\n'
       '            [["C1", "faster (earlier sessions: about 19%)", "faster, \\u221217.8%", "yes"], ["C2", "equivalent", "equivalent, +0.6%", "yes"],\n'
       '             ["C3", "inconclusive or equivalent", "faster, \\u22125.2%", "**no**"], ["C4", "inconclusive or equivalent", "faster, \\u22125.2%", "**no**"],\n'
       '             ["C5", "none stated", "faster, \\u221212.2%", "\\u2013"], ["C6", "none stated", "faster, \\u22128.5%", "\\u2013"],\n'
       '             ["C7", "faster or equivalent", "equivalent, \\u22120.0%", "yes"], ["C8", "none stated", "faster, \\u221221.2%", "\\u2013"],\n'
       '             ["C9", "small gain", "faster, \\u22122.6%", "yes"], ["C10", "small", "inconclusive, +1.6%", "yes"]],\n'
       '            [0.3, 1.4, 1.2, 0.4], size=6.5)\n')

# appendix: PRED against the hand rule
before('    d.h1_plain("Appendix C. Placement of tasks (primary workload)")\n',
       '    d.h1_plain("Appendix B2. PRED against the hand rule B4_param_first")\n'
       '    d.nextlabel = "pf"\n'
       '    d.table("PRED against B4_param_first on the primary workload, end-to-end makespan (%, negative = PRED faster; exploratory, 24 blocks)",\n'
       '            ["Hardware set", "Effect [95% CI]"], [[lab, fd.eff(fd.pf_effect(c))] for c, lab in (("cpu", "CPU only"), ("gpu", "strict GPU set"), ("ext", "extended GPU set"))],\n'
       '            [1.2, 1.6], size=7)\n')
open(p, "w", encoding="utf-8").write(s)
print("ok")
