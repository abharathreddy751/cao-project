"""Study 2: merge two solo profiles of ``scripts/study2_profile.py`` (one per image size) into one E1 profile for the heavy-tailed batch.

Entries are unioned by (workload, size, pool). ``img_aggregate`` is taken from the FIRST profile only (its size is the chain
count, which the second, small-count profile run does not share). Output is created exclusively; every number is copied, none typed.

  python scripts/study2_merge_profiles.py <out_profile.json> <profile_a.json> <profile_b.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(out: str, a: str, b: str) -> int:
    pa, pb = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (a, b))
    entries = {(e["workload"], e["size"], e["pool"]): e for e in pa["entries"]}
    for e in pb["entries"]:
        if e["workload"] != "img_aggregate":
            entries[(e["workload"], e["size"], e["pool"])] = e
    merged = {**pa, "entries": [entries[k] for k in sorted(entries)], "merged_from": [str(a), str(b)],
              "sizes_px": sorted({k[1] for k in entries if k[0] != "img_aggregate"})}
    with Path(out).open("x", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=1)
    for (w, s, p), e in sorted(entries.items()):
        print(f"{w:13s} {s:8d} {p}  {e['median_s'] * 1e3:9.3f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
