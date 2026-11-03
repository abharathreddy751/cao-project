"""Analyse experiment sessions from raw logs: CSV/JSON tables + figures, each tagged with its evidence label.

  python scripts/analyze_experiment.py --sessions data/experiments/S1 [S2 ...] --out analysis/montage_main \
         [--reference B4] [--seed 0] [--no-figures]

Refuses to pool sessions with different machine id / environment hash / evidence label / design hash / code
version (src_sha256; override with --allow-mixed-code, recorded in analysis.json). Sessions without a
session.json, or not 'complete' with all blocks done, are excluded (reason in exclusions.csv).
"""
from __future__ import annotations

import argparse
import sys

from caosched.analysis.stats_paired import analyze, make_figures, write_tables


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reference")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--posthoc-exclude-blocks", type=int, nargs="*", default=[], help="POST-HOC sensitivity: drop these blocks from the primary analysis (reason recorded in exclusions.csv; never a pre-registered rule)")
    ap.add_argument("--allow-mixed-code", action="store_true", help="pool sessions run with different source versions")
    ap.add_argument("--primary-metric", default="makespan_s", choices=["makespan_s", "makespan_e2e_s"],
                    help="makespan_e2e_s = amendment F1 (planning and policy set-up inside the makespan); default: the old convention")
    ap.add_argument("--only-conditions", nargs="+", help="analyse just these conditions (a session that holds several configurations)")
    a = ap.parse_args(argv)
    res = analyze(a.sessions, a.reference, a.seed, allow_mixed_code=a.allow_mixed_code,
                   posthoc_exclude_blocks=tuple(a.posthoc_exclude_blocks), primary_metric=a.primary_metric,
                   only_conditions=a.only_conditions)
    files = write_tables(res, a.out)
    if not a.no_figures:
        try:
            files += make_figures(res, a.out)
        except ImportError as exc:
            print(f"figures skipped: {exc}")
    print("\n".join(str(f) for f in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
