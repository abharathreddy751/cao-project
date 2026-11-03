"""Seeded, serialisable workload traces.

A *trace* is a DAG specification (tasks: id, workload, size, input seed,
dependencies) stored as JSON. It is generated once from a config entry +
seed, saved under data/traces/, and then replayed -- ``dag_from_trace``
builds a fresh ``DAG`` each time -- under every scheduling policy. This is
what makes cross-policy comparisons like-for-like (brief: "the same workload
trace can be replayed under different policies").

Generators (all deterministic in ``seed``):
  layered      random layered DAG: ``n_layers`` layers of
               ``width_min..width_max`` tasks; each non-root task depends on
               1..``max_parents`` distinct tasks of the previous layer.
  independent  ``n_tasks`` tasks, no edges.
  fork_join    root -> ``width`` branches -> join, repeated ``stages`` times
               (each stage's join is the next stage's root).
Workload type per task is drawn from ``workload_mix`` (weights) and size
uniformly from ``sizes[workload]``.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from caosched.core.dag import DAG
from caosched.core.task import Task

TRACE_DIR = Path(__file__).resolve().parents[3] / "data" / "traces"
SCHEMA_VERSION = 1


def _pick_task(rng: random.Random, mix: dict[str, float], sizes: dict[str, list[int]]) -> tuple[str, int]:
    names = sorted(mix)
    workload = rng.choices(names, weights=[mix[n] for n in names])[0]
    return workload, rng.choice(list(sizes[workload]))


def generate_trace(spec: dict) -> dict:
    """``spec``: one entry of the config's ``traces:`` list (must include
    ``name``, ``generator``, ``seed``, ``workload_mix``, ``sizes``)."""
    rng = random.Random(spec["seed"])
    mix, sizes = spec["workload_mix"], spec["sizes"]
    missing = sorted(set(mix) - set(sizes))
    if missing:
        raise ValueError(f"trace {spec['name']!r}: no sizes for workloads {missing}")
    tasks: list[dict] = []

    def add(tid: str, deps: list[str]) -> None:
        wl, size = _pick_task(rng, mix, sizes)
        tasks.append({"id": tid, "workload": wl, "size": size, "seed": rng.randrange(2**31), "deps": deps})

    gen = spec["generator"]
    if gen == "layered":
        prev: list[str] = []
        for layer in range(spec["n_layers"]):
            width = rng.randint(spec["width_min"], spec["width_max"])
            cur = []
            for j in range(width):
                tid = f"L{layer}_{j}"
                deps = sorted(rng.sample(prev, rng.randint(1, min(spec["max_parents"], len(prev))))) if prev else []
                add(tid, deps)
                cur.append(tid)
            prev = cur
    elif gen == "independent":
        for i in range(spec["n_tasks"]):
            add(f"t{i}", [])
    elif gen == "fork_join":
        root = "s0_root"
        add(root, [])
        for s in range(spec["stages"]):
            branches = [f"s{s}_b{i}" for i in range(spec["width"])]
            for b in branches:
                add(b, [root])
            root = f"s{s}_join"
            add(root, branches)
    else:
        raise ValueError(f"Unknown trace generator {gen!r}")

    return {"schema_version": SCHEMA_VERSION, "name": spec["name"], "seed": spec["seed"],
            "generator": {k: v for k, v in spec.items() if k not in ("name", "seed")}, "tasks": tasks}


def dag_from_trace(trace: dict) -> DAG:
    if trace.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported trace schema_version {trace.get('schema_version')!r}")
    return DAG({t["id"]: Task(task_id=t["id"], workload=t["workload"], size=int(t["size"]), seed=int(t["seed"]),
                              dependencies=tuple(t["deps"])) for t in trace["tasks"]})


def trace_path(spec: dict, directory: Path = TRACE_DIR) -> Path:
    return Path(directory) / f"{spec['name']}_seed{spec['seed']}.json"


def load_or_create_trace(spec: dict, directory: Path = TRACE_DIR) -> tuple[dict, Path]:
    """Load the saved trace for (name, seed); create and save it if absent.
    If a saved trace exists but no longer matches what ``spec`` generates
    (config edited), refuse rather than silently replaying a stale trace."""
    path = trace_path(spec, directory)
    fresh = generate_trace(spec)
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved != fresh:
            raise ValueError(f"{path} does not match its config spec; rename the trace or bump its seed")
        return saved, path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fresh, indent=1), encoding="utf-8")
    return fresh, path
