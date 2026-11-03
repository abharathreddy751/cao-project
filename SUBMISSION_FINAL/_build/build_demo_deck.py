from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

FIG = r"D:\cao project\publications\figures"
OUT = r"D:\cao project\publications\04_Project_Demo_Existing_vs_Proposed.pptx"
NAVY, GREY, ACC = RGBColor(0x1F, 0x2A, 0x44), RGBColor(0x55, 0x5B, 0x66), RGBColor(0x1F, 0x6F, 0xB2)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
blank = prs.slide_layouts[6]


def tb(slide, x, y, w, h, text, size=18, bold=False, color=NAVY, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    lines = text if isinstance(text, list) else [text]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = ln
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, color, "Calibri"
        p.space_after = Pt(6)
    return box


def slide(title, notes=""):
    s = prs.slides.add_slide(blank)
    tb(s, 0.6, 0.35, 12.1, 0.9, title, 30, True)
    line = s.shapes.add_shape(1, Inches(0.6), Inches(1.2), Inches(12.1), Inches(0.04))
    line.fill.solid(); line.fill.fore_color.rgb = ACC; line.line.fill.background()
    s.notes_slide.notes_text_frame.text = notes
    return s


def bullets(s, items, x=0.6, y=1.5, w=12.1, h=5.5, size=20):
    tb(s, x, y, w, h, ["\u2022  " + i for i in items], size, color=GREY)


def table(s, header, rows, x, y, w, colw, size=14):
    t = s.shapes.add_table(len(rows) + 1, len(header), Inches(x), Inches(y), Inches(w), Inches(0.4 * (len(rows) + 1))).table
    for ci, wd in enumerate(colw):
        t.columns[ci].width = Inches(wd)
    for ri, row in enumerate([header] + rows):
        for ci, v in enumerate(row):
            c = t.cell(ri, ci)
            c.text = v
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(size); r.font.name = "Calibri"; r.font.bold = ri == 0
                    r.font.color.rgb = RGBColor(255, 255, 255) if ri == 0 else NAVY
            c.fill.solid(); c.fill.fore_color.rgb = NAVY if ri == 0 else (RGBColor(0xF2, 0xF4, 0xF7) if ri % 2 else RGBColor(255, 255, 255))


s = prs.slides.add_slide(blank)
tb(s, 0.8, 2.2, 11.7, 1.6, "Prediction-Aware Task Scheduling on Heterogeneous Hardware", 40, True)
tb(s, 0.8, 3.9, 11.7, 0.8, "Project demonstration: existing implementation versus proposed implementation", 22, False, ACC)
tb(s, 0.8, 5.2, 11.7, 1.2, ["Lakshay S (26MAI0064), Arkkadu Bharath Reddy (26MAI0058)", "Computer Architecture and Organization", "Measured on one laptop; remote offloading emulated; Raspberry Pi not yet tested"], 16, False, GREY)
s.notes_slide.notes_text_frame.text = "Say at the start: all numbers are measured on this laptop; anything remote is emulation; the Raspberry Pi is not tested yet."

s = slide("What problem are we solving?", "A workflow is a graph of tasks. A scheduler decides where and in what order.")
bullets(s, ["A workflow is a graph of tasks with data dependencies (e.g. 64 image chains, or the Montage astronomy mosaic).",
            "The machine is heterogeneous: 6 P cores, 8 E cores (2.8 to 3.6x slower for these tasks), an RTX 3050 GPU, optionally a remote node.",
            "A scheduler decides the order of ready tasks and the worker for each. Blind choices waste the fast hardware.",
            "Measured cost of blind placement: 5% to 37% more time than a rule that merely knew which chains were heavy.",
            "Research question: how much prediction of task time is enough, once the cost of prediction itself is counted?"])

s = slide("Existing implementation: the base idea (B4)", "B4 is a comparison baseline mapped from US 11,561,826 B1, not a copy of the patent.")
bullets(s, ["Base patent US 11,561,826 B1 (Xilinx): task graph, kernel objects tied to compute circuits, per-kernel queues, in-degree gating.",
            "Mapped in our runtime as B4: a task goes to the first idle worker it is eligible for (P before E). No estimate of execution time.",
            "Strength: keeps every worker busy, costs about 7 ms of decision time per run.",
            "Weakness: chooses order by arrival and worker almost never (93.6% of dispatches had only one eligible idle worker); blind to task cost.",
            "Result: 37% slower than a cost-aware rule with 4 to 8 heavy chains; 47.9% slower than static P-only on Montage."])

s = slide("Proposed implementation", "Idle-only placement means a task never waits behind a busy worker.")
bullets(s, ["Order the ready tasks by predicted upward rank (predicted time + longest predicted path to the exit): heavy work first.",
            "Bind a task only to an idle eligible worker (work-conserving); choose the one with the smallest predicted time.",
            "ParamModel: per (stage, pool) ridge regression learned from execution logs on the parameters that vary; names no stage or parameter; refuses unseen stage/pool.",
            "New pool layout? Refit with one command (shown for 2 P + 7 E).",
            "Evaluated against B4, informed hand rule, HEFT, PEFT with paired statistics and overhead accounting."])

s = slide("Existing versus proposed at a glance")
table(s, ["Aspect", "Existing (B4)", "Proposed"],
      [["Order of ready tasks", "first come, first served", "predicted upward rank"],
       ["Worker choice", "first idle eligible (P before E)", "idle eligible with least predicted time"],
       ["Cost knowledge", "none", "learned from logs, one-command refit"],
       ["Decision time per run", "7 ms (coordinator 0.20 s)", "15 ms (coordinator 0.10 s)"],
       ["Hidden cost, 16 heavy", "reference", "-19.3% (6P+7E), -20.5% (2P+7E)"],
       ["Nothing hidden", "reference", "+0.45% (equivalent within 2%)"],
       ["Versus informed rule / HEFT", "-", "level / level"]],
      0.6, 1.6, 12.1, [3.2, 4.2, 4.7], 16)

s = slide("Architecture of the framework")
s.shapes.add_picture(FIG + r"\fig_architecture.png", Inches(2.4), Inches(1.4), height=Inches(5.8))

s = slide("Headline result: 20 unseen chain orders")
s.shapes.add_picture(FIG + r"\fig_per_order.png", Inches(0.8), Inches(1.5), width=Inches(11.6))
tb(s, 0.8, 6.6, 11.7, 0.6, "Proposed dispatcher vs B4 (blue) and vs hand rule (green). Faster than B4 in all 12 and all 8 orders; exploratory, one workload family.", 14, False, GREY)

s = slide("When does it help? Cost ratio and number of heavy chains")
s.shapes.add_picture(FIG + r"\fig_dose_heavy.png", Inches(1.0), Inches(1.5), width=Inches(11.2))
tb(s, 0.8, 6.5, 11.7, 0.7, "About 1% to 3% up to a 20x cost ratio, about 20% at 60x; about 27% with 4 or 8 heavy chains of 64, 4% with 40.", 16, False, GREY)

s = slide("Where it does not help (reported honestly)")
bullets(s, ["Montage (59 tasks): every task prefers P cores; no policy beats static P-only; B4 is 47.9% slower; EFT/HEFT +1.5%.",
            "Uniform batch: equivalent to B4 (+0.45%, within 2%).",
            "Two-factor batch: +0.95% [-0.9, +2.8], gain not supported.",
            "Informed hand rule: same gain as the learned dispatcher (+0.66%, +0.27%); HEFT with the same model also level (+1.10% [-0.5, +2.8]); PEFT only -2.6%.",
            "Remote worker (emulated): accurate predictions (0.1457 s vs 0.1464 s) but no gain; EFT +3.78% slower with it.",
            "Workflow-level CPU/GPU gain: not established. Raspberry Pi: not tested."])

s = slide("Overhead: what does the scheduler cost?")
s.shapes.add_picture(FIG + r"\fig_overhead.png", Inches(1.2), Inches(1.4), height=Inches(4.4))
bullets(s, ["Two metrics: per-dispatch decision time (7 ms B4, 15 ms proposed) and coordinator scheduling time (0.197 s, 0.100 s).",
            "Gap explained: an idle CUDA worker defeats the dispatch loop's early exit; fixing it changes the gain by 0.8 points only."],
        y=5.7, h=1.7, size=16)

s = slide("Demo mode 1: front end", "Start the dashboard, open the last tab, pick a B4 run and a proposed run of the same chain order.")
tb(s, 0.6, 1.5, 6.0, 0.6, "Command (project root):", 18, True)
tb(s, 0.6, 2.1, 6.0, 0.8, ".\\.venv\\Scripts\\python.exe -m caosched.dashboard --port 8765 --open", 14, False, ACC)
bullets(s, ["Open the last tab: experiment runs side by side.", "Pick a B4 run and a proposed run of the same chain order.",
            "Read: makespan (3858.9 ms vs 3097.0 ms), placement per pool, scheduling time, output-hash check."], x=0.6, y=3.1, w=6.0, size=16)
s.shapes.add_picture(FIG + r"\dashboard_compare.jpg", Inches(6.9), Inches(1.5), width=Inches(5.9))

s = slide("Demo mode 2: terminal")
bullets(s, ["Tests: .\\.venv\\Scripts\\python.exe -m pytest tests -q   (488 pass, about 4 min).",
            "Reproduce a table from raw logs: scripts\\reproduce_subset.py on data\\results\\overnight_20261027\\phase3\\analysis_ref_B4 (about 1 min).",
            "Evidence to point at: phase3\\per_order_summary.csv, effects.csv, fig_effect_vs_baseline.png, session_verification.json.",
            "Source files: src\\caosched\\core\\ (coordinator), schedulers\\, study2\\ (proposed dispatcher), estimators\\, experiment\\, analysis\\, remote\\.",
            "If PowerShell blocks Activate.ps1: do not change the policy; call .venv\\Scripts\\python.exe directly."], size=18)

s = slide("Evidence and integrity")
bullets(s, ["Every run's output verified against a CPU reference; event-log and design hashes match the manifests.",
            "Analyses re-derived from raw logs (reproduce_subset exit 0 for every analysis).",
            "50 registered claims tied to stored tables by a test; 488 tests pass.",
            "Failures kept as evidence: node served one client only (24 runs failed), first reproduction before manifests existed.",
            "Sessions with different code or label are never pooled; overnight sessions are exploratory."])

s = slide("Next steps and publication")
bullets(s, ["Measure a Raspberry Pi 5 over a wired link (runbook ready, command chain rehearsed over loopback, labelled emulation).",
            "Second workload family; apply and test the dispatch-loop fix; repeat on a clean committed tree.",
            "Venue: CCGrid 2027 (abstract 24 Nov, paper 1 Dec 2026; re-check on the call page); journal after the Pi results.",
            "IPR: file the disclosure before any public release; professional prior-art search first (IBM grant discloses learned rank-ordered dispatch)."])

prs.save(OUT)
print("saved", len(prs.slides._sldIdLst), "slides")
