import glob, re
keys = ["confidence interval", "p-value|p < 0|p<0", "standard deviation|std", "significan", "repetition|repeated|runs", "HEFT", "PEFT", "random", "round-robin|round robin|FIFO|first-come|greedy"]
for f in sorted(glob.glob("papers/*.txt")):
    if "US11561826" in f: continue
    t = open(f, encoding="utf-8").read()
    print(f[7:38].ljust(32), " ".join(f"{k.split('|')[0][:9]}={len(re.findall(k, t, re.I))}" for k in keys))
