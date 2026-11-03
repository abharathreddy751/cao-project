"""Single-column report builder (python-docx): title page, TOC field, numbered chapters, tables, figures, references.
Reuses IEEEDoc's inline markup and citation handling; export via Word COM (ieee_docx.export_pdf)."""
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from ieee_docx2 import FONT, _fmt, _run, add_inline
from refs import REFS


class Report:
    def __init__(self, body_pt=11):
        self.d = Document()
        self.body_pt = body_pt
        self.ch = 0
        self.sec = 0
        self.fig_no = 0
        self.tab_no = 0
        self.cite_order = []
        s = self.d.sections[0]
        s.page_width, s.page_height = Inches(8.5), Inches(11)
        s.left_margin = s.right_margin = Inches(1.0)
        s.top_margin = s.bottom_margin = Inches(1.0)
        st = self.d.styles["Normal"]
        st.font.name = FONT
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        st.font.size = Pt(body_pt)
        for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
            h = self.d.styles[name]
            h.font.name = FONT
            h.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
            h.element.rPr.rFonts.set(qn("w:ascii"), FONT)
            h.element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
            h.font.size = Pt(size)
            h.font.bold = True
            h.font.color.rgb = None
        self._footer(s)

    def _footer(self, section):
        p = section.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run()
        for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
            if tag:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = txt
            r._r.append(el)
        r.font.size = Pt(9)
        r.font.name = FONT

    def _c(self, text):
        def rep(m):
            nums = []
            for k in m.group(1).split(","):
                k = k.strip()
                if k not in REFS:
                    raise KeyError(f"unknown reference key {k!r}")
                if k not in self.cite_order:
                    self.cite_order.append(k)
                nums.append(self.cite_order.index(k) + 1)
            return ", ".join(f"[{n}]" for n in nums)
        return re.sub(r"\{\{([a-z0-9_, ]+)\}\}", rep, text)

    # ---- front matter -----------------------------------------------------
    def center(self, text, size=12, bold=False, italic=False, before=0, after=6):
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, before, after)
        add_inline(p, text, size, base_bold=bold, base_italic=italic)

    def page_break(self):
        self.d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def toc(self):
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.LEFT, 0, 0)
        r = p.add_run()
        for tag, txt in (("begin", None), (None, 'TOC \\o "1-2" \\h \\z \\u'), ("separate", None), ("end", None)):
            if tag:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = txt
            r._r.append(el)

    # ---- body -------------------------------------------------------------
    def chapter(self, title, new_page=False):
        if new_page and self.ch:
            self.page_break()
        self.ch += 1
        self.sec = 0
        self.d.add_heading(f"{self.ch}. {title}", level=1)

    def chapter_plain(self, title):
        self.page_break()
        self.d.add_heading(title, level=1)

    def section(self, title):
        self.sec += 1
        self.d.add_heading(f"{self.ch}.{self.sec} {title}", level=2)

    def sub(self, title):
        self.d.add_heading(title, level=3)

    def para(self, text):
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 6, line=1.15)
        add_inline(p, self._c(text), self.body_pt)

    def bullets(self, items, size=None):
        for t in items:
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 3, first=-0.2, left=0.35, line=1.1)
            _run(p, "•  ", size or self.body_pt)
            add_inline(p, self._c(t), size or self.body_pt)

    def numbered(self, items):
        for i, t in enumerate(items, 1):
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 3, first=-0.28, left=0.4, line=1.1)
            _run(p, f"{i}. ", self.body_pt)
            add_inline(p, self._c(t), self.body_pt)

    def code(self, text):
        for line in text.strip("\n").split("\n"):
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.LEFT, 0, 0, left=0.3)
            _run(p, line, self.body_pt - 1, mono=True)
        self.d.add_paragraph().paragraph_format.space_after = Pt(2)

    def figure(self, path, caption, width_in=5.4):
        self.fig_no += 1
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 4, 0, keep_next=True)
        p.add_run().add_picture(str(path), width=Inches(width_in))
        c = self.d.add_paragraph()
        _fmt(c, WD_ALIGN_PARAGRAPH.CENTER, 2, 8)
        _run(c, f"Figure {self.fig_no}. ", 10, bold=True)
        add_inline(c, self._c(caption), 10)

    def table(self, caption, header, rows, widths_in, size=9):
        self.tab_no += 1
        cp = self.d.add_paragraph()
        _fmt(cp, WD_ALIGN_PARAGRAPH.CENTER, 6, 3, keep_next=True)
        _run(cp, f"Table {self.tab_no}. ", 10, bold=True)
        add_inline(cp, self._c(caption), 10)
        t = self.d.add_table(rows=1 + len(rows), cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for ri, row in enumerate([header] + rows):
            for ci, val in enumerate(row):
                cell = t.cell(ri, ci)
                cell.width = Inches(widths_in[ci])
                cell.text = ""
                p = cell.paragraphs[0]
                _fmt(p, WD_ALIGN_PARAGRAPH.LEFT, 0, 0, line=1.0)
                add_inline(p, self._c(str(val)), size, base_bold=(ri == 0))
                tcPr = cell._tc.get_or_add_tcPr()
                mar = OxmlElement("w:tcMar")
                for side in ("top", "bottom", "left", "right"):
                    m = OxmlElement(f"w:{side}")
                    m.set(qn("w:w"), "40" if side in ("top", "bottom") else "70")
                    m.set(qn("w:type"), "dxa")
                    mar.append(m)
                tcPr.append(mar)
                if ri == 0:
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:fill"), "E7E6E6")
                    tcPr.append(shd)
        trPr = t.rows[0]._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        th.set(qn("w:val"), "true")
        trPr.append(th)
        self.d.add_paragraph().paragraph_format.space_after = Pt(4)

    def references(self):
        self.chapter_plain("References")
        for i, k in enumerate(self.cite_order, 1):
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 3, first=-0.35, left=0.35)
            _run(p, f"[{i}] ", 10)
            add_inline(p, REFS[k], 10)

    def save(self, path):
        self.d.save(str(path))
