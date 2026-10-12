"""Synthetic adapter for tests / dry runs. Never real evidence: label forced to 'plan'.

Makespan = base[instance] * effect[condition] * lognormal(noise) -- the instance
factor is shared by all conditions of a block (so pairing cancels it).
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from caosched.experiment.design import RunRecord


class StubAdapter:
    evidence_label_override = "plan"

    def __init__(self, base=10.0, effects=None, noise=0.02, fail=(), bad_output=()):
        self.base, self.effects, self.noise = base, effects or {}, noise
        self.fail, self.bad_output = set(fail), set(bad_output)

    def run_one(self, condition, workdir: Path, seed: int) -> RunRecord:
        if condition.name in self.fail:
            raise RuntimeError("stub failure")
        rng = random.Random(seed)
        base = self.base[condition.instance] if isinstance(self.base, dict) else self.base
        ms = base * self.effects.get(condition.name, 1.0) * rng.lognormvariate(0, self.noise)
        rows = [{"seq": 0, "event": "run_started", "n_tasks": 4, "memory_available_bytes": 8 << 30},
                {"seq": 1, "event": "worker_ready", "worker_id": "P0", "pool": "P"}]
        for i in range(4):
            rows.append({"seq": 2 + 2 * i, "event": "task_dispatched", "task_id": f"t{i}",
                         "queue_wait_seconds": 0.01, "decision_time_s": 0.001})
            rows.append({"seq": 3 + 2 * i, "event": "task_completed", "task_id": f"t{i}",
                         "wall_time_seconds": ms / 4, "t_started": 0.0, "t_completed": ms / 4})
        rows.append({"seq": 99, "event": "run_finished", "status": "completed", "n_tasks": 4, "n_completed": 4,
                     "makespan_seconds": ms})
        name = f"{condition.name}.jsonl"
        with (workdir / name).open("x", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in rows))
        return RunRecord(event_log=name, input_hashes={"stub_in": hashlib.sha256(b"in").hexdigest()},
                         output_hashes={"stub_out": hashlib.sha256(b"out").hexdigest()})

    def verify(self, condition, workdir, record):
        return condition.name not in self.bad_output, dict(record.output_hashes)
