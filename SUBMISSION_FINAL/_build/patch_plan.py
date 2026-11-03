p = "build_plan.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


def line_with(start):
    """whole source line beginning (after indentation) with `start`"""
    i = s.index(start)
    a = s.rfind("\n", 0, i) + 1
    b = s.index("\n", i)
    return s[a:b]


rep('sys.path.insert(0, r"D:\\cao project\\publications\\_work")', 'sys.path.insert(0, r"D:\\cao project\\SUBMISSION_FINAL\\_build")')
rep("from report_docx import Report\nfrom ieee_docx import export_pdf", "from report_docx1 import Report\nfrom ieee_docx2 import export_pdf")
rep('OUT = r"D:\\cao project\\publications"', 'OUT = r"D:\\cao project\\SUBMISSION_FINAL\\_draft"')
rep("Version of 1 November 2026", "Version of 3 November 2026")

old = line_with('"The anonymous draft `06b` fits the format (7 pages).')
new = ('    "The anonymous Lab-10 draft `06b` has 14 pages; CCGrid allows 10 pages including references, so a 10-page conference cut (drop the appendices, the earlier-study details and the long tables) must be made first. '
       'Weakness the reviewers will raise: one machine, one workload family, a hand rule within 1% of the dispatcher, emulated remote. State these limits in the paper (the draft does).",')
s = s.replace(old, new, 1)

old = line_with('"Lead with the strongest verified result')
new = ('    "Lead with the final benchmark: with one cost model on both sides the dynamic dispatcher beats a static HEFT plan by 5.2% (CPU) and 12.2% (strict GPU set) and blind dispatch by 17.8% and 21.2%; then give the limits (a hand rule within 1%, a tie without cost spread, 23% to 31% GPU model error, an earlier session that found HEFT level).",')
s = s.replace(old, new, 1)

rep('r.para("A journal paper should add:',
    'r.table("Indexing and quartile status of the candidates (checked 3 Nov. 2026 on aggregator pages that quote SCImago; the quartile is category-specific and changes yearly, so confirm on scimagojr.com and Scopus before choosing)",\n'
    '        ["Venue", "Reported quartile (SJR best quartile)", "How certain"],\n'
    '        [["IEEE/ACM CCGrid 2027 (conference)", "conference; IEEE proceedings; Scopus indexing of the 2027 volume not yet verifiable", "dates verified on the call page: abstract 24 Nov. 2026, paper 1 Dec. 2026 (AoE), notification 1 Feb. 2027, camera-ready 16 Mar. 2027; 10 pages including references; double-blind; conference 24 to 27 May 2027, Dallas Fort-Worth"],\n'
    '         ["Future Generation Computer Systems", "Q1 (several computer science categories)", "aggregators agree; SJR value varies by source"],\n'
    '         ["IEEE Trans. Parallel and Distributed Systems", "Q1", "aggregators agree; SJR value varies by source"],\n'
    '         ["Journal of Systems Architecture", "Q1 (Hardware and Architecture; Software)", "one aggregator; confirm"],\n'
    '         ["Journal of Parallel and Distributed Computing", "Q1 (several categories)", "one aggregator; confirm"],\n'
    '         ["Concurrency and Computation: Practice and Experience", "mixed: CiteScore Q1 or Q2 by category, JCR Q3", "no clear SJR quartile found; weakest candidate"]],\n'
    '        [2.0, 2.2, 2.1], size=8.5)\n'
    'r.para("**Recommended order.** (1) CCGrid 2027 with a 10-page cut of the Lab-10 paper if the IPR decision allows public submission; (2) otherwise or afterwards a Q1 journal (Future Generation Computer Systems or IEEE TPDS) with the extended version and real-device results. '
    'A book chapter needs a specific call (none verified).")\n'
    'r.para("A journal paper should add:')

# ---- 08
rep("(about 11,900 lines runtime, 488 automated tests)", "(about 12,600 lines runtime, 521 automated tests)")
rep('r.para("**Status of this draft.** This is a working draft',
    'r.para("**Template note (Lab 9).** The institution\\u2019s IDF-B template was not available in this work; the sections below follow the usual IDF structure (administrative data, field, background, problem, summary, embodiments, prior art, advantages, inventor contributions) so that the text can be moved into the official form.")\n'
    'r.para("**Status of this draft.** This is a working draft')
rep('         ["emulated remote worker, level 30", "EFT +3.78% slower with remote", "no offloading gain"]],',
    '         ["emulated remote worker, level 30", "EFT +3.78% slower with remote", "no offloading gain"],\n'
    '         ["final benchmark, primary workload, CPU (24 blocks, Holm)", "PRED vs B4 \\u221217.8% [\\u221218.8, \\u221216.7]; vs static HEFT \\u22125.2% [\\u22125.9, \\u22124.6]", "confirmatory; end-to-end makespan"],\n'
    '         ["final benchmark, strict GPU set", "PRED vs B4 \\u221221.2% [\\u221222.6, \\u221219.7]; vs static HEFT \\u221212.2% [\\u221213.4, \\u221211.1]", "GPU used only where a speed-up was measured"],\n'
    '         ["final benchmark, PRED vs hand rule B4_param_first", "\\u22120.4% [\\u22120.9, +0.1] (CPU)", "within 1% in every configuration (exploratory)"]],')
rep("Reported gain where hidden cost exists (19% to 28%); no harm where it does not.", "Reported gain where task cost varies (17% to 40% against blind dispatch; 2% to 12% against a static plan from the same model); no harm where it does not.")
open(p, "w", encoding="utf-8").write(s)
print("plan patched")
