"""Phase 6A: build and validate the unified dataset from the raw event logs.

Reads data/events/** (never modifies it), writes data/datasets/<stamp>/
{tasks.csv, candidates.csv, splits.json, manifest.json}, then validates it
(including re-hashing every source log). Schema: docs/DATASET.md.

Usage:  python scripts/build_dataset.py
"""
from __future__ import annotations

from pathlib import Path

from caosched.dataset.build import build_dataset, validate_dataset

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    out = build_dataset(ROOT / "data" / "events", ROOT / "data" / "profiles", ROOT / "data" / "datasets")
    report = validate_dataset(out)
    print(f"dataset -> {out.relative_to(ROOT)}")
    print("validation:", report)


if __name__ == "__main__":
    main()
