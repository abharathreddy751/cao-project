"""End-to-end terms for the EFT *ablation* (project decision 2026-10-03).

The PRIMARY execution-time target stays kernel-only (``wall_time_seconds``);
nothing here changes any estimator. ``EndToEndTerms`` only supplies the two
extra, separately-measured components an end-to-end EFT adds on top of the
kernel estimate:

    exec_e2e(task, pool) = kernel_estimate(task, pool, ctx)
                           + setup(workload, size, pool)   # prepare(): input generation
                           + overhead(pool)                 # runtime per-task overhead

* setup: median of (worker span - kernel time) per (workload, size, pool) in
  the static-profile raw CSV (the worker span covers prepare() + kernel).
* overhead: median per pool of (t_started - t_submitted) + (t_logged - t_completed)
  from event logs: dispatch IPC to the worker + result IPC back to the
  coordinator, as measured in real runs.

Both are measured by ``scripts/derive_e2e_terms.py`` and stored as JSON; no
value is typed by hand. Unknown keys raise KeyError (never guessed).
"""
from __future__ import annotations

import json
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models"


class EndToEndTerms:
    def __init__(self, setup_s: dict[tuple[str, int, str], float], overhead_s: dict[str, float],
                 source: str | None = None):
        self.setup_s = dict(setup_s)
        self.overhead_s = dict(overhead_s)
        self.source = source

    def setup(self, workload: str, size: int, pool: str) -> float:
        key = (workload, int(size), pool)
        if key not in self.setup_s:
            raise KeyError(f"No measured setup time for {key}")
        return self.setup_s[key]

    def overhead(self, pool: str) -> float:
        if pool not in self.overhead_s:
            raise KeyError(f"No measured runtime overhead for pool {pool!r}")
        return self.overhead_s[pool]

    def extra(self, task, pool: str) -> float:
        return self.setup(task.workload, task.size, pool) + self.overhead(pool)

    def to_dict(self) -> dict:
        return {"schema_version": 1,
                "setup_s": {f"{w}|{s}|{p}": v for (w, s, p), v in sorted(self.setup_s.items())},
                "overhead_s": dict(sorted(self.overhead_s.items()))}

    def save(self, path: Path, sources: dict) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({**self.to_dict(), "sources": sources}, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "EndToEndTerms":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        setup = {}
        for k, v in d["setup_s"].items():
            w, s, p = k.split("|")
            setup[(w, int(s), p)] = float(v)
        return cls(setup, {k: float(v) for k, v in d["overhead_s"].items()}, source=str(path))

    def describe(self) -> dict:
        return {"source": self.source, **self.to_dict()}
