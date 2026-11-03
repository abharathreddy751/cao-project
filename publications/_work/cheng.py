import pymupdf, re, glob
f = glob.glob(r"C:\Users\Venkatesh\.claude\projects\D--cao-project\3d58deff-1b3c-4c56-8ffe-342c70bc7781\tool-results\webfetch-1793483058259-*.pdf")[0]
t = re.sub(r"\s+", " ", "\n".join(p.get_text() for p in pymupdf.open(f)))
for k in ["10%", "80%", "Google", "40%"]:
    for m in list(re.finditer(re.escape(k), t))[:3]:
        print(k, "|", t[max(0, m.start() - 200):m.end() + 250], "\n")
