"""Task-level GPU eligibility from recorded GPU-spike verdicts (improvement D of CAO_IMPROVEMENT_PLAN.md).

A task may run on the CUDA pool only if a spike row exists for ITS stage, its image side and ITS parameters with verdict PASS (output
equivalent inside the tolerance fixed before the recording AND speed-up > 1 including the host-device copies; scripts/gpu_spike.py).
Nothing is typed in: the region is whatever the loaded records say, and a task whose (stage, side, params) has no row, or a DROPPED
row, is never given the CUDA pool, however cheap the GPU might look. Records are listed explicitly (the original record and, for
the "extended" family, the one written by scripts/final_gpu_spike_iters.py); the strict family loads only the original.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from caosched.study2.workload import GPU_POOL


class GpuRegion:
    def __init__(self, passed: set[tuple[str, int, str]], sources: list[str], signature: str):
        self.passed, self.sources, self.signature = passed, sources, signature

    @classmethod
    def load(cls, paths) -> "GpuRegion":
        passed: set[tuple[str, int, str]] = set()
        dropped: set[tuple[str, int, str]] = set()
        h = hashlib.sha256()
        for p in map(Path, paths):
            raw = p.read_bytes()
            h.update(raw)
            for r in json.loads(raw)["rows"]:
                k = (r["stage"], int(r["side"]), _canon(json.loads(r["params"])))
                (passed if r["verdict"] == "PASS" else dropped).add(k)
        # a row that was DROPPED in any record is not eligible even if another record passed the same case (conservative)
        return cls(passed - dropped, [str(p) for p in paths], h.hexdigest()[:16])

    def eligible(self, stage: str, side: int, params: dict | None) -> bool:
        return (stage, int(side), _canon(params or {})) in self.passed

    def narrow(self, dag, gpu_pool: str = GPU_POOL) -> int:
        """Remove the CUDA pool from every task whose (stage, side, params) is not a PASS row. Returns how many tasks lost it."""
        n = 0
        for t in dag.tasks.values():
            if t.eligible_pools and gpu_pool in t.eligible_pools:
                side = math.isqrt(int(t.size))
                if side * side != int(t.size) or not self.eligible(t.workload, side, t.params):
                    t.eligible_pools = tuple(p for p in t.eligible_pools if p != gpu_pool)
                    n += 1
        return n

    def describe(self) -> dict:
        return {"sources": self.sources, "signature": self.signature, "n_pass_rows": len(self.passed)}


def _canon(params: dict) -> str:
    return json.dumps({k: params[k] for k in sorted(params)}, sort_keys=True)
