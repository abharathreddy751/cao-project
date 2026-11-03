"""Minimal IEEE two-column DOCX builder (python-docx) + Word COM export to PDF with page count.

Layout follows the IEEE conference template: US Letter, Times New Roman 10 pt body, 2 columns (0.25 in gap), title block across both
columns, section headings in small caps with Roman numerals, italic sub-headings, 8 pt captions, 8 pt references.
Inline markup in text: **bold**, *italic*, `mono`, ^{sup}, _{sub}.
"""
import copy
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

FONT = "Times New Roman"
def _roman(n):
    out = ""
    for v, r in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += r
            n -= v
    return out


ROMAN = [_roman(i) for i in range(1, 41)]
TOKEN = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`|\^\{.+?\}|_\{.+?\})")


def _set_cols(section, num, space_in=0.25):
    sect = section._sectPr
    for c in sect.findall(qn("w:cols")):
        sect.remove(c)
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), str(int(space_in * 1440)))
    sect.append(cols)


def _run(p, text, size, bold=False, italic=False, mono=False, caps=False, sup=False, sub=False, color=None):
    r = p.add_run(text)
    r.font.name = "Consolas" if mono else FONT
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas" if mono else FONT)
    r.font.size = Pt(size - 1 if mono else size)
    r.bold, r.italic = bold, italic
    r.font.small_caps = caps
    r.font.superscript, r.font.subscript = sup, sub
    if color:
        r.font.color.rgb = RGBColor(*color)
    return r


def add_inline(p, text, size, base_bold=False, base_italic=False):
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            _run(p, part[2:-2], size, bold=True, italic=base_italic)
        elif part.startswith("`") and part.endswith("`"):
            _run(p, part[1:-1], size, mono=True, bold=base_bold)
        elif part.startswith("^{"):
            _run(p, part[2:-1], size, sup=True)
        elif part.startswith("_{"):
            _run(p, part[2:-1], size, sub=True)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            _run(p, part[1:-1], size, italic=True, bold=base_bold)
        else:
            _run(p, part, size, bold=base_bold, italic=base_italic)


def _fmt(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, before=0, after=0, first=None, left=None, keep_next=False, line=None):
    pf = p.paragraph_format
    p.alignment = align
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    if first is not None:
        pf.first_line_indent = Inches(first)
    if left is not None:
        pf.left_indent = Inches(left)
    pf.keep_with_next = keep_next
    if line:
        pf.line_spacing = line
    pf.widow_control = True


class IEEEDoc:
    def __init__(self, title, authors, affil_lines, abstract, keywords, body_pt=10, anonymous=False):
        self.d = Document()
        self.body_pt = body_pt
        self.sec_no = 0
        self.sub_no = 0
        self.fig_no = 0
        self.tab_no = 0
        from refs import REFS
        self.refs_db, self.cite_order = REFS, []
        import __main__, json, os
        self._lab_path = Path(__file__).with_name('_labels_' + Path(getattr(__main__, '__file__', 'x')).stem + '.json')
        self.labels = {}
        try:
            self.prev_labels = json.loads(self._lab_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.prev_labels = {}
        s = self.d.sections[0]
        s.page_width, s.page_height = Inches(8.5), Inches(11)
        s.left_margin = s.right_margin = Inches(0.625)
        s.top_margin, s.bottom_margin = Inches(0.75), Inches(0.9)
        st = self.d.styles["Normal"]
        st.font.name = FONT
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        st.font.size = Pt(body_pt)
        # title block (one column)
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 0, 6)
        _run(p, title, 22 if len(title) < 70 else 18, bold=False)
        if anonymous:
            authors, affil_lines = ["Anonymous Authors"], ["Affiliation withheld for double-blind review"]
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 2, 0)
        _run(p, ", ".join(authors), 11)
        for line in affil_lines:
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 0, 0)
            _run(p, line, 9, italic=True)
        s2 = self.d.add_section(WD_SECTION.CONTINUOUS)
        _set_cols(s2, 2)
        s2.left_margin = s2.right_margin = Inches(0.625)
        # abstract
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 6, 0, line=1.0)
        _run(p, "Abstract", body_pt - 1, bold=True, italic=True)
        _run(p, "—", body_pt - 1, bold=True, italic=True)
        add_inline(p, self._c(abstract), body_pt - 1, base_bold=True)
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 4, 4)
        _run(p, "Index Terms", body_pt - 1, bold=True, italic=True)
        _run(p, "—", body_pt - 1, bold=True, italic=True)
        add_inline(p, keywords, body_pt - 1, base_italic=True)
        self._add_page_number(self.d.sections[0])
        s2.footer.is_linked_to_previous = True
        st_el = self.d.settings.element
        for tag, val in (("w:autoHyphenation", "true"), ("w:hyphenationZone", "283"), ("w:doNotHyphenateCaps", "false")):
            el = OxmlElement(tag)
            el.set(qn("w:val"), val)
            st_el.append(el)

    def _c(self, text):
        def rep(m):
            nums = []
            for k in m.group(1).split(","):
                k = k.strip()
                if k not in self.refs_db:
                    raise KeyError(f"unknown reference key {k!r}")
                if k not in self.cite_order:
                    self.cite_order.append(k)
                nums.append(self.cite_order.index(k) + 1)
            return ", ".join(f"[{n}]" for n in nums)
        out = re.sub(r"\{\{([a-z0-9_, ]+)\}\}", rep, text)
        out = re.sub(r"\((\[\d+\](?:, \[\d+\])*)\)", lambda m: m.group(1), out)
        return re.sub(r"@(fig|tab|sec):([a-z0-9_]+)", lambda m: {'fig': 'Fig. ', 'tab': 'Table ', 'sec': 'Section '}[m.group(1)] + self.prev_labels.get(m.group(1) + ':' + m.group(2), '??'), out)  # IEEE: [1], [2], not ([1], [2])

    def _add_page_number(self, section):
        f = section.footer
        f.is_linked_to_previous = False
        p = f.paragraphs[0]
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
        r.font.size = Pt(8)
        r.font.name = FONT

    # ---- text blocks ------------------------------------------------------
    def h1(self, text, label=None):
        label = label or getattr(self, 'nextlabel', None)
        self.nextlabel = None
        self.sec_no += 1
        if label:
            self.labels['sec:' + label] = ROMAN[self.sec_no - 1]
        self.sub_no = 0
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 8, 3, keep_next=True)
        _run(p, f"{ROMAN[self.sec_no - 1]}. ", self.body_pt, caps=True)
        _run(p, text.upper() if False else text, self.body_pt, caps=True)

    def h1_plain(self, text):  # un-numbered (e.g. References, Acknowledgment)
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 8, 3, keep_next=True)
        _run(p, text, self.body_pt, caps=True)

    def h2(self, text, label=None):
        label = label or getattr(self, 'nextlabel', None)
        self.nextlabel = None
        self.sub_no += 1
        if label:
            self.labels['sec:' + label] = f'{ROMAN[self.sec_no - 1]}-{chr(64 + self.sub_no)}'
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.LEFT, 4, 2, keep_next=True)
        _run(p, f"{chr(64 + self.sub_no)}. ", self.body_pt, italic=True)
        _run(p, text, self.body_pt, italic=True)

    def para(self, text, indent=True):
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 3, first=0.17 if indent else 0)
        add_inline(p, self._c(text), self.body_pt)

    def bullets(self, items, size=None):
        for t in items:
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 1, first=-0.14, left=0.17)
            _run(p, "•  ", size or self.body_pt)
            add_inline(p, self._c(t), size or self.body_pt)

    def numbered(self, items):
        for i, t in enumerate(items, 1):
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 1, first=-0.2, left=0.22)
            _run(p, f"{i}) ", self.body_pt)
            add_inline(p, self._c(t), self.body_pt)

    def equation(self, text, number):
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 2, 2)
        add_inline(p, text, self.body_pt)
        _run(p, f"     ({number})", self.body_pt)

    # ---- floats -----------------------------------------------------------
    def _to_one_col(self):
        return None  # layout fix: no spanning floats

    def _to_two_col(self):
        return None

    def figure(self, path, caption, width_in=3.4, span=False, label=None):
        label = label or getattr(self, 'nextlabel', None)
        self.nextlabel = None
        width_in = min(width_in, 3.45)
        self.fig_no += 1
        if label:
            self.labels['fig:' + label] = str(self.fig_no)
        if span:
            self._to_one_col()
        p = self.d.add_paragraph()
        _fmt(p, WD_ALIGN_PARAGRAPH.CENTER, 4, 0, keep_next=True)
        p.add_run().add_picture(str(path), width=Inches(width_in))
        c = self.d.add_paragraph()
        _fmt(c, WD_ALIGN_PARAGRAPH.JUSTIFY if len(caption) > 90 else WD_ALIGN_PARAGRAPH.CENTER, 1, 6)
        _run(c, f"Fig. {self.fig_no}. ", 8)
        add_inline(c, self._c(caption), 8)
        if span:
            self._to_two_col()

    def table(self, caption, header, rows, widths_in, span=False, size=7.5, bold_first_col=False, keep=None, label=None):
        label = label or getattr(self, 'nextlabel', None)
        self.nextlabel = None
        keep = (len(rows) <= 9) if keep is None else keep
        self.tab_no += 1
        if label:
            self.labels['tab:' + label] = ROMAN[self.tab_no - 1]
        if span:
            self._to_one_col()
        cp = self.d.add_paragraph()
        _fmt(cp, WD_ALIGN_PARAGRAPH.CENTER, 4, 2, keep_next=True)
        _run(cp, f"TABLE {ROMAN[self.tab_no - 1]}", 8, caps=True)
        cp2 = self.d.add_paragraph()
        _fmt(cp2, WD_ALIGN_PARAGRAPH.CENTER, 0, 3, keep_next=True)
        _run(cp2, caption, 8, caps=True)
        tot = float(sum(widths_in))
        widths_in = [w * 3.42 / tot for w in widths_in]  # always exactly the column width
        t = self.d.add_table(rows=1 + len(rows), cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        lay = OxmlElement("w:tblLayout")
        lay.set(qn("w:type"), "fixed")
        t._tbl.tblPr.append(lay)
        for ri, row in enumerate([header] + rows):
            for ci, val in enumerate(row):
                cell = t.cell(ri, ci)
                cell.width = Inches(widths_in[ci])
                cell.text = ""
                p = cell.paragraphs[0]
                _fmt(p, WD_ALIGN_PARAGRAPH.LEFT, 0, 0, line=1.0, keep_next=(keep and ri < len(rows)))
                txt = self._c(str(val))
                if ri == 0 and re.fullmatch(r"\[\d+\]", txt):
                    txt = txt[1:-1]  # narrow header columns: bare reference number
                add_inline(p, txt, size, base_bold=(ri == 0 or (bold_first_col and ci == 0)))
                tcPr = cell._tc.get_or_add_tcPr()
                mar = OxmlElement("w:tcMar")
                for side in ("top", "bottom", "left", "right"):
                    m = OxmlElement(f"w:{side}")
                    m.set(qn("w:w"), "30" if side in ("top", "bottom") else "50")
                    m.set(qn("w:type"), "dxa")
                    mar.append(m)
                tcPr.append(mar)
                if ri == 0:
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:fill"), "E7E6E6")
                    tcPr.append(shd)
        # repeat header row
        trPr = t.rows[0]._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        th.set(qn("w:val"), "true")
        trPr.append(th)
        for row in t.rows:
            cs = OxmlElement("w:cantSplit")
            cs.set(qn("w:val"), "true")
            row._tr.get_or_add_trPr().append(cs)
        sp = self.d.add_paragraph()
        sp.paragraph_format.space_after = Pt(0)
        sp.paragraph_format.line_spacing = Pt(5)
        for r_ in sp.runs:
            r_.font.size = Pt(2)
        if span:
            self._to_two_col()

    def references(self, size=8):
        self.h1_plain("References")
        for i, k in enumerate(self.cite_order, 1):
            r = self.refs_db[k]
            p = self.d.add_paragraph()
            _fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 1, first=-0.28, left=0.28)
            _run(p, f"[{i}] ", size)
            add_inline(p, r, size)

    def save(self, path):
        import json
        self._lab_path.write_text(json.dumps(self.labels), encoding='utf-8')
        s = self.d.add_section(WD_SECTION.CONTINUOUS)
        _set_cols(s, 1)
        self.d.save(str(path))


def export_pdf(docx_path, pdf_path):
    """Open in Word (COM), export PDF, return (pages, words)."""
    import os
    if os.environ.get('CAO_NOPDF'):
        return 0, 0
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    w = win32com.client.DispatchEx("Word.Application")
    w.Visible = False
    w.DisplayAlerts = 0
    try:
        doc = w.Documents.Open(str(Path(docx_path).resolve()))
        doc.Repaginate()
        try:
            doc.Fields.Update()
            for toc in doc.TablesOfContents:
                toc.Update()
        except Exception:
            pass
        doc.Repaginate()
        doc.ExportAsFixedFormat(str(Path(pdf_path).resolve()), 17)
        pages, words = doc.ComputeStatistics(2), doc.ComputeStatistics(0)
        doc.Save() if False else None
        doc.Close(False)
    finally:
        w.Quit()
    return int(pages), int(words)
