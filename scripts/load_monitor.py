"""Background-load monitor for timed sessions [real]: every INTERVAL seconds append one JSON line with the machine-wide CPU
percent, available RAM and the top processes by CPU that are NOT part of the experiment (name only, no command lines), so the
report can quantify how idle the machine really was. Exclusive create; stop with Ctrl-C / terminate.

  python scripts/load_monitor.py <out.jsonl> [--interval 30] [--exclude python.exe mProject.exe ...]
"""
import argparse
import datetime
import json
import time

import psutil

DEFAULT_EXCLUDE = {"python.exe", "mproject.exe", "mdifffit.exe", "mdiff.exe", "mfitplane.exe", "mbackground.exe",
                   "mbgmodel.exe", "mconcatfit.exe", "mimgtbl.exe", "madd.exe", "mviewer.exe", "bash.exe", "conhost.exe",
                   "system idle process", "system"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--exclude", nargs="*", default=[])
    a = ap.parse_args()
    excl = DEFAULT_EXCLUDE | {e.lower() for e in a.exclude}
    for p in psutil.process_iter():
        p.cpu_percent(None)  # prime the counters
    with open(a.out, "x", encoding="utf-8") as f:
        while True:
            time.sleep(a.interval)
            cpu_total = psutil.cpu_percent(None)
            others = []
            for p in psutil.process_iter(["name"]):
                try:
                    n = (p.info["name"] or "").lower()
                    if n not in excl:
                        others.append((p.cpu_percent(None), n))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            others.sort(reverse=True)
            vm = psutil.virtual_memory()
            f.write(json.dumps({"t": datetime.datetime.now(datetime.timezone.utc).isoformat(), "cpu_total_pct": cpu_total,
                                "avail_gb": round(vm.available / 2**30, 2),
                                "other_cpu_pct_sum": round(sum(c for c, _ in others), 1),
                                "top_other": [(n, round(c, 1)) for c, n in others[:5] if c > 0]}) + "\n")
            f.flush()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
