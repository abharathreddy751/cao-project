"""Software provenance recorded with every run (from Phase 6B on).

``software_info()`` = package version + SHA-256 over the sorted contents of
every ``*.py`` file under ``src/caosched`` at process start (there is no VCS
in this repository, so the source hash is the reproducibility handle).
"""
from __future__ import annotations

import functools
import hashlib
from pathlib import Path

PACKAGE_VERSION = "0.1.0"
_SRC = Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def software_info() -> dict:
    h = hashlib.sha256()
    for p in sorted(_SRC.rglob("*.py")):
        h.update(p.relative_to(_SRC).as_posix().encode())
        h.update(p.read_bytes())
    digest = h.hexdigest()
    return {"version": f"{PACKAGE_VERSION}+{digest[:12]}", "src_sha256": digest}


def memory_available_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.virtual_memory().available)
    except Exception:  # noqa: BLE001 - provenance is best-effort
        return None
