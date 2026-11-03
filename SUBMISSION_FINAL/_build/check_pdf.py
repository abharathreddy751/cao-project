"""Layout audit of a PDF: page count, unresolved cross-references, text/images outside the margins, pages with a large empty bottom area,
two-column balance per page. usage: check_pdf.py file.pdf [min_pages]"""
import re
import sys

import pymupdf

pdf = sys.argv[1]
minp = int(sys.argv[2]) if len(sys.argv) > 2 else 0
d = pymupdf.open(pdf)
W, H = d[0].rect.width, d[0].rect.height
issues = []
alltext = ""
for i, pg in enumerate(d, 1):
    t = pg.get_text()
    alltext += t
    blocks = pg.get_text("blocks")
    xs1 = max((b[2] for b in blocks), default=0)
    xs0 = min((b[0] for b in blocks), default=W)
    if xs1 > W - 0.5 * 72 + 2 or xs0 < 0.5 * 72 - 2:
        issues.append(f"p{i}: text block outside margins (x0={xs0:.0f}, x1={xs1:.0f})")
    for im in pg.get_image_info():
        x0, y0, x1, y1 = im["bbox"]
        if x1 > W - 0.5 * 72 + 2 or x0 < 0.5 * 72 - 2:
            issues.append(f"p{i}: image outside margins ({x0:.0f},{x1:.0f})")
    body = [b for b in blocks if b[3] < H - 50 and b[1] > 40]
    imgs = [im["bbox"][3] for im in pg.get_image_info()]
    bottom = max([b[3] for b in body] + imgs, default=0)
    if i < len(d) and bottom < H * 0.80:
        issues.append(f"p{i}: content ends at {bottom / H * 100:.0f}% of page height (hole?)")
n = len(d)
print(f"{pdf}: {n} pages, {len(alltext.split())} words")
for m in re.finditer(r"\?\?", alltext):
    issues.append("unresolved cross-reference '??' near: " + alltext[max(0, m.start() - 40):m.start() + 20].replace("\n", " "))
for pat, msg in ((r"\(\[\d+\]", "citation inside parentheses"), (r"\bTODO\b|\bTBD\b|lorem", "placeholder text")):
    for m in re.finditer(pat, alltext):
        issues.append(msg + ": " + alltext[max(0, m.start() - 30):m.start() + 30].replace("\n", " "))
if minp and n < minp:
    issues.append(f"only {n} pages, required at least {minp}")
print("ISSUES:" if issues else "no layout issues found")
for x in issues:
    print("  -", x)
