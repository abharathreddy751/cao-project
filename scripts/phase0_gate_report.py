"""Phase 0: analyze a benchmark CSV (default: most recent) and print/write the
gate verdict.

Usage:
    python scripts/phase0_gate_report.py [path/to/run.csv]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from caosched.phase0.benchmarks.analysis import write_gate_report
from caosched.phase0.benchmarks.harness import DEFAULT_OUTPUT_DIR as CSV_DIR


def _latest_csv() -> Path:
    candidates = sorted(CSV_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise SystemExit(f"No benchmark CSV files found in {CSV_DIR}; run scripts/phase0_benchmark.py first.")
    return candidates[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 gate report")
    parser.add_argument("csv_path", nargs="?", default=None, help="Benchmark CSV to analyze (default: most recent)")
    args = parser.parse_args()

    csv_path = Path(args.csv_path) if args.csv_path else _latest_csv()
    report_path = write_gate_report(csv_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    print(f"Analyzed {csv_path}")
    print(f"Gate report written to {report_path}")
    print()
    print(report["verdict"])


if __name__ == "__main__":
    main()
