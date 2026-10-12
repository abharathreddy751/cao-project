"""Phase 6A: build and validate the unified dataset from the raw event logs.

Reads data/events/** (never modifies it), writes data/datasets/<stamp>/
{tasks.csv, candidates.csv, splits.json, manifest.json}, then validates it
(including re-hashing every source log). Schema: docs/DATASET.md.

Usage:  python scripts/build_dataset.py [--context-source decision|auto|start] [--allow-later-calibration]
                                        [--train-fraction F] [--events DIR]
  decision (DEFAULT; use for model training/evaluation, AD-7): features only from the context logged at the
  placement decision; rows without one are dropped and counted in manifest.json.
  auto / start (explicit opt-in, historical logs only): start-time reconstruction is post-decision data.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from caosched.dataset.build import build_dataset, validate_dataset

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=str(ROOT / "data" / "events"))
    ap.add_argument("--context-source", default="decision", choices=("decision", "auto", "start"))
    ap.add_argument("--allow-later-calibration", action="store_true", help="historical: use a later profile when none predates the session")
    ap.add_argument("--train-fraction", type=float, default=0.7)
    a = ap.parse_args()
    out = build_dataset(Path(a.events), ROOT / "data" / "profiles", ROOT / "data" / "datasets", a.context_source,
                        a.allow_later_calibration, a.train_fraction)
    report = validate_dataset(out)
    print(f"dataset -> {out.relative_to(ROOT)}")
    print("validation:", report)


if __name__ == "__main__":
    main()
