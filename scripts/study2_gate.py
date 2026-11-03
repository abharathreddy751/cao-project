"""Study 2 go/no-go gate (EVALUATION_PROTOCOL_study2.md section 2): read a measured profile, print the per-stage ratios and write
the verdict to a NEW file (exclusive create). No value is typed in; every ratio is median(slow) / median(fast) from the profile.

  PASS needs BOTH:
    (a) at least one stage whose CUDA variant is >= 3x faster than a P core (the GPU is worth queueing for), and
    (b) at least one stage that is NOT clearly faster on the GPU (|P / G - 1| <= 0.15): the single CUDA worker is then a
        contended resource and the best worker depends on queue state, which is what a predictor can use.
  Also reported (not part of the verdict): E / P slow-down per stage, and the share of the profile's P-core work that the E
  cores could take (capacity argument for early use of the slow cores).

  python scripts/study2_gate.py <profile.json> <out_gate.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(profile: str, out: str) -> int:
    entries = json.loads(Path(profile).read_text(encoding="utf-8"))["entries"]
    med: dict[str, dict[str, float]] = {}
    for e in entries:
        med.setdefault(e["workload"], {})[e["pool"]] = e["median_s"]
    rows = {}
    for stage, m in sorted(med.items()):
        rows[stage] = {"P_s": m.get("P"), "E_s": m.get("E"), "G_s": m.get("G"),
                       "E_over_P": m["E"] / m["P"] if "E" in m and "P" in m else None,
                       "P_over_G": m["P"] / m["G"] if "G" in m and "P" in m else None}
    gpu = {s: r["P_over_G"] for s, r in rows.items() if r["P_over_G"] is not None}
    strong = sorted(s for s, v in gpu.items() if v >= 3.0)
    indifferent = sorted(s for s, v in gpu.items() if abs(v - 1.0) <= 0.15)
    verdict = "PASS" if strong and indifferent else "FAIL"
    result = {"profile": str(profile), "verdict": verdict, "rule": {"strong_gpu_min_speedup": 3.0, "indifferent_band": 0.15},
              "stages_gpu_at_least_3x": strong, "stages_gpu_indifferent": indifferent, "per_stage": rows}
    with Path(out).open("x", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    for s, r in rows.items():
        fmt = lambda v: "   -  " if v is None else f"{v:6.2f}"  # noqa: E731
        print(f"{s:14s} E/P {fmt(r['E_over_P'])}   P/G {fmt(r['P_over_G'])}")
    print(f"verdict {verdict}: gpu>=3x {strong}, indifferent {indifferent}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
