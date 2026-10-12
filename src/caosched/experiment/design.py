"""Pre-registered experiment design and the adapter plug-in point.

Design file (JSON, or YAML if the suffix is .yaml/.yml)::

    {"name": "montage_main", "evidence_label": "real", "seed": 20261011,
     "n_blocks": 12, "instances": ["m31_a", "m31_b"],       # optional
     "warmup_blocks": 1,                  # the ONLY warm-up exclusion rule
     "min_free_ram_gb": 3.0, "reference": "B4",             # strongest baseline (from the pilot)
     "conditions": [{"name": "B4", "policy": "B4_greedy_eligible_R", "estimator": null,
                     "workload": {"kind": "montage", "degrees": 0.5}, "kwargs": {}}, ...]}

Block plan: block b uses one instance (instances cycle in a seed-shuffled
order, reshuffled each cycle) and runs EVERY condition exactly once in a
seeded random order. Everything derives from ``seed`` via SHA-256, so the plan
is reproducible and independent of Python's hash randomisation.

PLUG-IN POINT (real Montage / GPU workload): implement ::

    class MyAdapter:
        def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord:
            # build DAG + scheduler from condition.policy/estimator/kwargs/workload/instance,
            # run the Coordinator with EventLogger(run_id, workdir) (mode "x": never overwrites),
            # return RunRecord(event_log="<run_id>.jsonl", input_hashes={...}, output_hashes={...}, output_ok=...)
        def verify(self, condition, workdir, record) -> tuple[bool, dict]:   # optional
            # compare final output to the reference; return (passed, {name: sha256})

and pass it to ``runner.run_session``. Exceptions from run_one are caught and recorded as a
failed run (kept, flagged, excluded from the primary analysis).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

LABELS = ("real", "replay", "emulation", "simulation", "plan")


@dataclass(frozen=True)
class Condition:
    name: str
    policy: str
    estimator: str | None = None
    workload: dict = field(default_factory=dict)
    kwargs: dict = field(default_factory=dict)
    instance: str | None = None  # filled in per block by the planner


@dataclass
class RunRecord:
    status: str = "ok"  # ok | failed | timeout
    event_log: str | None = None  # path relative to workdir
    error: str | None = None
    input_hashes: dict = field(default_factory=dict)
    output_hashes: dict = field(default_factory=dict)
    output_ok: bool | None = None  # None = not verified (treated as a failure)
    extra: dict = field(default_factory=dict)


class Adapter(Protocol):
    def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord: ...


@dataclass
class Design:
    raw: dict
    sha256: str
    path: Path

    def __getattr__(self, k):  # raw["x"] as .x for the validated fields
        try:
            return self.__dict__["raw"][k]
        except KeyError:
            raise AttributeError(k) from None

    @property
    def conditions(self) -> list[Condition]:
        keys = ("name", "policy", "estimator", "workload", "kwargs")
        return [Condition(**{k: c[k] for k in keys if k in c}) for c in self.raw["conditions"]]


def load_design(path) -> Design:
    path = Path(path)
    data = path.read_bytes()
    if path.suffix in (".yaml", ".yml"):
        import yaml
        raw = yaml.safe_load(data)
    else:
        raw = json.loads(data)
    names = [c["name"] for c in raw.get("conditions", [])]
    if not names or len(set(names)) != len(names):
        raise ValueError("design needs >=1 conditions with unique names")
    if raw.get("evidence_label") not in LABELS:
        raise ValueError(f"evidence_label must be one of {LABELS}")
    for k in ("name", "seed", "n_blocks", "min_free_ram_gb"):
        if k not in raw:
            raise ValueError(f"design is missing {k!r}")
    raw.setdefault("warmup_blocks", 0)
    raw.setdefault("instances", [None])
    if raw["n_blocks"] < 1 or raw["warmup_blocks"] >= raw["n_blocks"]:
        raise ValueError("need n_blocks >= 1 and warmup_blocks < n_blocks")
    if raw.get("reference") not in (None, *names):
        raise ValueError("reference must be a condition name")
    return Design(raw, hashlib.sha256(data).hexdigest(), path)


def _rng(*parts) -> random.Random:
    return random.Random(int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16], 16))


def plan_blocks(design: Design) -> list[dict]:
    """[{block, instance, warmup, runs: [(Condition, run_seed), ...]}, ...] -- deterministic in design.seed."""
    seed, insts, conds = design.seed, design.instances, design.conditions
    out = []
    for b in range(design.n_blocks):
        perm = list(insts)
        _rng(seed, "inst", b // len(insts)).shuffle(perm)
        inst = perm[b % len(insts)]
        order = list(conds)
        _rng(seed, "cond", b).shuffle(order)
        out.append({"block": b, "instance": inst, "warmup": b < design.warmup_blocks,
                    "runs": [(dataclasses.replace(c, instance=inst), _rng(seed, "run", b, c.name).getrandbits(31))
                             for c in order]})
    return out
