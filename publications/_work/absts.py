import sys, re, glob
for f in sorted(glob.glob("papers/*.txt")):
    if "US11561826" in f: continue
    t = open(f, encoding="utf-8").read()
    i = max(t.lower().find("abstract"), 0)
    print("===", f[7:45])
    print(re.sub(r"\s+", " ", t[i:i + 2100]))
