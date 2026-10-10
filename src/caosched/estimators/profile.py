"""E1: static profile lookup by (workload, size, pool).

The profile is a JSON file *derived* by ``scripts/profile_static.py`` from a
raw per-measurement CSV of real kernel timings on this machine (taken one
task at a time, i.e. without co-running load). Nothing here is hand-typed.

Lookup is strict: an unprofiled (workload, size, pool) raises ``KeyError``
instead of being guessed -- interpolating across sizes is E2's job (Phase 3).
"""
from __future__ import annotations

import json
from pathlib import Path

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator, estimate_key

PROFILE_DIR = Path(__file__).resolve().parents[3] / "data" / "profiles"


def latest_profile_path(directory: Path = PROFILE_DIR) -> Path:
    candidates = sorted(Path(directory).glob("*_profile.json"))
    if not candidates:
        raise FileNotFoundError(f"No *_profile.json in {directory}; run scripts/profile_static.py first")
    return candidates[-1]


class StaticProfileEstimator(ExecutionTimeEstimator):
    name = "E1_static_profile"

    def __init__(self, table: dict[tuple[str, int, str], float], source: str | None = None):
        if not table:
            raise ValueError("Empty profile table")
        if any(v <= 0 for v in table.values()):
            raise ValueError("Profile contains non-positive execution times")
        self.table = dict(table)
        self.source = source

    @classmethod
    def from_file(cls, path: Path) -> "StaticProfileEstimator":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("metric") != "kernel_wall_time_seconds":
            raise ValueError(f"{path}: profile metric must be kernel_wall_time_seconds, got {data.get('metric')!r}")
        table = {estimate_key(e["workload"], e["size"], e["pool"]): float(e["median_s"]) for e in data["entries"]}
        return cls(table, source=str(path))

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        return self.lookup(task.workload, task.size, pool)

    def lookup(self, workload: str, size: int, pool: str) -> float:
        key = estimate_key(workload, size, pool)
        if key not in self.table:
            raise KeyError(f"No static profile entry for {key}; profiled keys: {sorted(self.table)}")
        return self.table[key]

    def describe(self) -> dict:
        return {"name": self.name, "source": self.source, "n_entries": len(self.table)}
