from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

FIG = r"D:\cao project\publications\figures"
OUT = r"D:o projectSUBMISSION_FINAL_draftOUT = r"D:\cao project\publications\04_Project_Demo_Existing_vs_Proposed.pptx"4_Project_Demo_Existing_vs_Proposed.pptx"
FF = r"D:o projectSUBMISSION_FINAL_fig"
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
