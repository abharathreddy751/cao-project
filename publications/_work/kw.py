import glob, re
keys = ["testbed", "Jetson", "Raspberry", "github", "inference time|inference latency|decision latency|decision time|decision-making time", "overhead", "Montage", "CloudSim|simulat", "TPC-H", "Alibaba", "Google"]
for f in sorted(glob.glob("papers/*.txt")):
    if "US11561826" in f: continue
    t = open(f, encoding="utf-8").read()
    print(f[7:42].ljust(36), " ".join(f"{k.split('|')[0][:8]}={len(re.findall(k, t, re.I))}" for k in keys))
