import pymupdf, glob, os, sys
d = r"C:\Users\Venkatesh\Downloads\base papers"
out = r"D:\cao project\publications\_work\papers"
for f in sorted(glob.glob(d + "/*.pdf")):
    doc = pymupdf.open(f)
    txt = "\n".join(p.get_text() for p in doc)
    name = os.path.basename(f)[:60].replace(" ", "_").replace(".pdf", "")
    open(os.path.join(out, name + ".txt"), "w", encoding="utf-8").write(txt)
    print(name, len(doc), len(txt))
