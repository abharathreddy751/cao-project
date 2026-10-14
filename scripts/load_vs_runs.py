"""Correlate slow runs of a session with the background-load monitor log [real]. Prints, for runs whose makespan exceeds a factor
of their condition's median, their UTC start time and the load samples (machine CPU, non-experiment CPU, top other processes,
free RAM) in the run's time window. Also summarises the whole load log.

  python scripts/load_vs_runs.py <session_dir> <load.jsonl> [--factor 1.2]
"""
import argparse
import collections
import datetime
import json
import statistics
from pathlib import Path


def utc(e):
    return datetime.datetime.fromtimestamp(e, datetime.timezone.utc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("load")
    ap.add_argument("--factor", type=float, default=1.2)
    a = ap.parse_args()
    runs, by_cond = [], collections.defaultdict(list)
    for f in Path(a.session).glob("runs/*/*.jsonl"):
        ev = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
        fin = [e for e in ev if e["event"] == "run_finished"]
        if not fin:
            continue
        cond = f.parent.name.split("_", 2)[2]
        runs.append((ev[0]["timestamp"], f.parent.name, cond, fin[-1]["makespan_seconds"]))
        by_cond[cond].append(fin[-1]["makespan_seconds"])
    med = {c: statistics.median(v) for c, v in by_cond.items()}
    load = [json.loads(line) for line in Path(a.load).read_text(encoding="utf-8").splitlines() if line.strip()]
    for x in load:
        x["ts"] = datetime.datetime.fromisoformat(x["t"])
    print(f"{len(load)} load samples; non-experiment CPU % (sum over processes): median "
          f"{statistics.median(x['other_cpu_pct_sum'] for x in load):.1f}, max {max(x['other_cpu_pct_sum'] for x in load):.1f}; "
          f"machine CPU % median {statistics.median(x['cpu_total_pct'] for x in load):.1f}; min free RAM "
          f"{min(x['avail_gb'] for x in load):.2f} GB")
    for t, name, cond, ms in sorted(runs):
        if ms > a.factor * med[cond]:
            t1 = utc(t + ms)
            w = [x for x in load if utc(t) <= x["ts"] <= t1]
            print(f"SLOW {name} makespan {ms:.0f}s (condition median {med[cond]:.0f}s) start {utc(t):%m-%d %H:%M:%S} "
                  f"samples {len(w)} max-other-CPU {max((x['other_cpu_pct_sum'] for x in w), default=0):.0f}% "
                  f"min-free-RAM {min((x['avail_gb'] for x in w), default=0):.2f} GB "
                  f"top {collections.Counter(n for x in w for n, c in x['top_other'][:2]).most_common(3)}")


if __name__ == "__main__":
    main()
