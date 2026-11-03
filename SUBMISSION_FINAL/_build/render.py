"""Render a PDF to contact sheets (PNG) for visual layout checks. usage: render.py file.pdf outdir [dpi] [per_sheet]"""
import sys, pymupdf
from PIL import Image
pdf, out = sys.argv[1], sys.argv[2]
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 60
per = int(sys.argv[4]) if len(sys.argv) > 4 else 4
import os; os.makedirs(out, exist_ok=True)
d = pymupdf.open(pdf)
ims = []
for p in d:
    pm = p.get_pixmap(dpi=dpi)
    ims.append(Image.frombytes("RGB", (pm.width, pm.height), pm.samples))
w, h = ims[0].size
cols = 2 if per >= 2 else 1
for s in range(0, len(ims), per):
    grp = ims[s:s + per]
    rows = (len(grp) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols + 6 * (cols - 1), h * rows + 6 * (rows - 1)), (120, 120, 120))
    for i, im in enumerate(grp):
        sheet.paste(im, ((i % cols) * (w + 6), (i // cols) * (h + 6)))
    sheet.save(os.path.join(out, f"sheet_{s // per + 1:02d}.png"))
print(len(d), "pages ->", out)
