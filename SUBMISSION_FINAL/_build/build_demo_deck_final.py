"""Project demo deck (existing implementation versus proposed work), updated to the final static-vs-dynamic benchmark. Numbers: CAO_FINAL_EXPERIMENT_REPORT.md / stored analysis files."""
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

FIG = r"D:\cao project\publications\figures"
FF = r"D:\cao project\SUBMISSION_FINAL\_fig"
OUT = r"D:\cao project\SUBMISSION_FINAL\_draft\04_Project_Demo_Existing_vs_Proposed.pptx"
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


M = "\u2212"
s = prs.slides.add_slide(blank)
tb(s, 0.8, 2.0, 11.7, 1.8, "Static Plan or Dynamic Dispatch? Task Scheduling on a Hybrid CPU/GPU Machine", 38, True)
tb(s, 0.8, 4.0, 11.7, 0.8, "Project demonstration: existing implementation versus proposed work", 22, False, ACC)
tb(s, 0.8, 5.2, 11.7, 1.4, ["Lakshay S (26MAI0064), Arkkadu Bharath Reddy (26MAI0058)", "Computer Architecture and Organization | Guide: Dr. Yokesh Babu S, Associate Professor Grade 1",
                            "Measured on one laptop (RTX 3050 + P/E cores); remote worker emulated; Raspberry Pi not tested"], 16, False, GREY)
s.notes_slide.notes_text_frame.text = "Say at the start: all numbers are measured on this laptop; anything remote is emulation; the Raspberry Pi is not tested."

s = slide("What problem are we solving?", "A workflow is a graph of tasks. A scheduler decides where and in what order.")
bullets(s, ["A workflow is a graph of tasks with data dependencies (here 64 image chains, 257 tasks; earlier also the Montage mosaic).",
            "The machine is heterogeneous: 6 P cores, 7 E cores (2.8 to 3.6x slower for these tasks) and one CUDA GPU worker (RTX 3050).",
            "A static scheduler (HEFT, PEFT) plans everything before the run; a dynamic scheduler decides while running.",
            "Research question: with ONE cost model on both sides, is dynamic faster than static once planning and start-up time are counted, and when?",
            "Blind placement alone costs 17% to 40% more time than a cost-aware dynamic policy when task cost varies."])

s = slide("Existing implementation: the base idea (B4)", "B4 is a comparison baseline mapped from US 11,561,826 B1, not a copy of the patent.")
bullets(s, ["Base patent US 11,561,826 B1 (Xilinx): task graph, kernel objects tied to compute circuits, per-kernel queues, in-degree gating.",
            "Mapped in our runtime as B4: a task goes to the first idle worker it is eligible for (P before E). No estimate of execution time.",
            "Strength: keeps every worker busy, about 7 ms of decision time per run.",
            "Weakness: order is first come first served and the worker is almost never chosen (93.6% of dispatches had one eligible idle worker); blind to task cost.",
            "On the GPU configurations blind B4 sends about a third of its tasks to the GPU and is slower for it (+1.6%, inconclusive)."])

s = slide("Proposed work", "Idle-only placement means a task never waits behind a busy worker.")
bullets(s, ["Dynamic: order ready tasks by predicted upward rank; bind only to an IDLE eligible worker with the least predicted time (PRED_RANK_GREEDY); an end-to-end variant adds set-up and IPC terms.",
            "Static: HEFT, PEFT and HEFT_E2E plans from the SAME ridge model, computed before the run; an oracle plan as a reference only.",
            "GPU eligibility per task from recorded speed-up measurements (strict and extended sets); no configuration is GPU-only.",
            "End-to-end makespan: start of the run to the last completion, so planning and start-up are counted.",
            "Protocol frozen before the evaluation; ten pre-stated contrasts with Holm correction; six workloads."])

s = slide("Existing versus proposed at a glance")
table(s, ["Aspect", "Existing (B4)", "Proposed"],
      [["Order of ready tasks", "first come, first served", "predicted upward rank"],
       ["Worker choice", "first idle eligible (P before E)", "idle eligible, least predicted time; GPU only for verified stages"],
       ["Cost knowledge", "none", "ridge model from logs, one-command refit"],
       ["Primary workload, CPU", "reference", M + "17.8% [" + M + "18.8, " + M + "16.7] vs B4; " + M + "5.2% vs static HEFT"],
       ["Primary workload, strict GPU", "reference", M + "21.2% vs B4; " + M + "12.2% vs static HEFT"],
       ["No spread in task cost", "reference", "+0.0% (equivalent within 2%)"],
       ["Versus a rule that knows the parameter", "-", "within 1% in every configuration"]],
      0.6, 1.6, 12.1, [3.3, 3.0, 5.8], 15)

s = slide("Architecture of the final framework")
s.shapes.add_picture(FF + r"\fig_final_architecture.png", Inches(3.0), Inches(1.4), height=Inches(5.8))

s = slide("Headline result: primary workload, all policies", "Lower is better. Dynamic cost-aware policies beat blind B4 and the static HEFT plan.")
s.shapes.add_picture(FF + r"\fig_final_makespan.png", Inches(2.6), Inches(1.4), height=Inches(5.1))
tb(s, 0.8, 6.55, 11.7, 0.6, "End-to-end makespan, geometric mean over 24 blocks, 95% intervals. B4 param-first is a hand rule that knows the cost parameter.", 14, False, GREY)

s = slide("Ten pre-stated contrasts (Holm-adjusted)")
s.shapes.add_picture(FF + r"\fig_final_forest.png", Inches(2.4), Inches(1.4), height=Inches(5.2))
tb(s, 0.8, 6.65, 11.7, 0.6, "C3/C4 were predicted inconclusive; the dynamic policy was 5% faster, so that prediction was wrong (reported).", 14, False, GREY)

s = slide("When does it help? Six workloads")
s.shapes.add_picture(FF + r"\fig_final_workloads.png", Inches(2.0), Inches(1.4), height=Inches(4.9))
tb(s, 0.8, 6.4, 11.7, 0.8, "About 40% over B4 with 4 heavy chains; 3% to 8% with 40 heavy or a cost ratio of 20; nothing on the uniform workload.", 16, False, GREY)

s = slide("The GPU: where it helps and where it does not")
s.shapes.add_picture(FF + r"\fig_final_placement.png", Inches(0.8), Inches(1.5), height=Inches(3.9))
bullets(s, ["PRED: strict set 2.6% faster than CPU only, extended set 7.5%; blind B4: 1.6% slower with the strict set.",
            "GPU cost model error is 23% to 31% (CPU: 4% to 11%): the weakest part; limits GPU placement and may inflate the dynamic-vs-static gap.",
            "One CUDA worker; the GPU takes about 15% to 20% of the 257 tasks under the model-based policies."], x=7.0, y=1.6, w=5.9, size=16)

s = slide("Where it does not help (reported honestly)")
bullets(s, ["A hand rule that knows the cost parameter is within 1% of the dynamic dispatcher in every configuration.",
            "No spread in task cost (uniform, light workloads): policies tie; with ratio 7.5 and the strict GPU set PRED is +1.1% slower than B4.",
            "End-to-end cost terms change nothing (equivalent within 2%); a hybrid B4/PRED selector would gain at most 1.1%: not built.",
            "An earlier session found HEFT level with the dispatcher (+1.10%); the final session finds PRED 5% faster; the difference was not isolated.",
            "Remote worker: emulation only, no benefit; no Raspberry Pi or real-network result. Montage: no gain."])

s = slide("Demo: front end (dashboard v3)", "Start the dashboard, open screens 1, 3, 6; run one live block on screen 6.")
tb(s, 0.6, 1.5, 12.0, 0.6, "Command (project root):", 18, True)
tb(s, 0.6, 2.1, 12.0, 1.4, ".\\.venv\\Scripts\\python.exe -m caosched.dashboard_v3 --port 8770 --events-dir data\\results\\final_20261101\\eval\\sessions --open", 14, False, ACC)
bullets(s, ["Screen 1: GPU CONNECTED with live load, memory, temperature and power; Raspberry Pi card: NOT CONNECTED.",
            "Screen 3: final results with hover details (makespan, forest plot, six workloads, task placement).",
            "Screen 6: run one live block of the final benchmark with any policy on CPU or CPU+GPU (about 1 to 2 minutes; needs 2.4 GB free RAM).",
            "The original dashboard and v2 stay unchanged (ports 8765 and 8766)."], x=0.6, y=3.7, w=12.0, size=17)

s = slide("Demo: terminal")
bullets(s, ["Tests: .\\.venv\\Scripts\\python.exe -m pytest tests -q   (520 of 521 pass; the one failure is a RAM-gate test that refuses to start below 2 GB free).",
            "Final report: CAO_FINAL_EXPERIMENT_REPORT.md, generated from data\\results\\final_20261101\\eval\\analysis_*; flat table RESULTS_TABLE_FINAL.csv.",
            "Source: src\\caosched\\final\\ (static baselines, E2E dispatcher, GPU region), core\\, study2\\, estimators\\, experiment\\, analysis\\.",
            "If PowerShell blocks Activate.ps1: do not change the policy; call .venv\\Scripts\\python.exe directly."], size=18)

s = slide("Evidence and integrity")
bullets(s, ["Every included run's output verified against a CPU reference; event-log and design hashes match the manifests.",
            "Protocol and design hashes logged before the first evaluation session; calibration, hold-out and evaluation data are separate.",
            "RAM gate (2.4 GB start, 0.8 GB per block) and mains power enforced before every block; thresholds never lowered; aborted attempts kept, never pooled.",
            "Earlier results untouched: RESULTS_TABLE.csv unchanged; new table is RESULTS_TABLE_FINAL.csv; backups of every edited file.",
            "Limits: one machine, one workload family, one CUDA worker, emulated remote."])

s = slide("Next steps and publication")
bullets(s, ["A GPU cost model with lower error; an experiment that separates model error from decision timing; a second workload family.",
            "Remote worker with the final policies, then a Raspberry Pi 5 over a wired link (runbook ready, loopback rehearsal only).",
            "Venue: CCGrid 2027 (abstract 24 Nov, paper 1 Dec 2026, 10 pages) or a Q1 journal (FGCS, IEEE TPDS) with the extended version.",
            "IPR: file the disclosure before any public release; professional prior-art search first (an IBM grant discloses learned rank-ordered dispatch)."])

prs.save(OUT)
print("saved", len(prs.slides._sldIdLst), "slides")
