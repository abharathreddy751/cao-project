import glob, re, sys
def show(pat, kw, n=2, w=230):
    f = glob.glob("papers/" + pat + "*")[0]
    t = re.sub(r"\s+", " ", open(f, encoding="utf-8").read())
    for m in list(re.finditer(kw, t, re.I))[:n]:
        print(f"[{pat[:12]}|{kw}] ...{t[max(0,m.start()-w):m.end()+w]}...\n")
show("Dynamic-Task", "Jetson", 3)
show("2309", "Montage", 2)
show("2103", "inference", 2)
show("s13677-024-00658", "Raspberry", 1)
show("1-s2", "github", 1)
