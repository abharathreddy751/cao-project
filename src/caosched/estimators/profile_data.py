"""Loading the raw static-profile measurements (the CSV behind a
``*_profile.json``) for estimators that fit their own model to them (E0, E2).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


def load_profile_rows(profile_path, include_warmup: bool = False) -> list[dict]:
    """Rows of the raw CSV referenced by a profile JSON's ``source_csv``,
    typed (size int, kernel_s float), warmups excluded by default."""
    profile_path = Path(profile_path)
    meta = json.loads(profile_path.read_text(encoding="utf-8"))
    raw = profile_path.parent / meta["source_csv"]
    rows = []
    with raw.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            warm = r["is_warmup"] == "True"
            if warm and not include_warmup:
                continue
            rows.append({"workload": r["workload"], "size": int(r["size"]), "pool": r["pool"],
                         "worker_id": r["worker_id"], "kernel_s": float(r["kernel_s"]), "is_warmup": warm})
    if not rows:
        raise ValueError(f"No profile rows in {raw}")
    return rows
