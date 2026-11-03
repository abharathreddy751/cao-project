"""Study 2: retrain the learned model for a NEW resource configuration or machine with one command (protocol section 21).

What it does, in order, with no code change: write two coverage designs for the hidden-cost workload (random placement, then every task
on the E pool, so that every (stage, pool) pair is logged), run them with the adapter configuration given (the pools of that machine:
for a Raspberry Pi the adapter config names its remote pool), fit the generic parameter model (``study2/param_model.py``) from the
two sessions and write it next to them. Exits 2 if a session did not complete (for example the design requires mains power and the
laptop is on battery). Nothing is overwritten; every file is created exclusively.

  python scripts/study2_retrain.py <out_dir> <adapter_config.json> <profile.json> [--random-blocks 13] [--e-blocks 7] [--seed 1] [--workload iters|classes]
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(out_dir: str, adapter_config: str, profile: str, random_blocks: int = 13, e_blocks: int = 7, seed: int = 1,
         workload: str = "iters") -> int:
    from caosched.experiment.runner import run_session
    from caosched.study2.adapter import Study2Adapter

    design_mod, train_mod = _load(f"study2_{workload}_design"), _load("study2_train_param_model")  # workload: iters | classes
    out = Path(out_dir)
    (out / "designs").mkdir(parents=True)
    adapter = Study2Adapter(**json.loads(Path(adapter_config).read_text(encoding="utf-8")))
    sessions = []
    try:
        for kind, name, blocks in (("cover2", "retrain_random", random_blocks), ("cover_e", "retrain_e_only", e_blocks)):
            design_mod.main(kind, out / "designs", profile, name, blocks, seed)
            s = run_session(out / "designs" / f"design_{name}.json", out / "sessions", adapter, session_id=name)
            if s["status"] != "complete":
                print(f"session {name} did not complete: {s['status']} ({s['reason']})")
                return 2
            sessions.append(str(out / "sessions" / name))
    finally:
        adapter.close()
    return train_mod.main(str(out / "param_model.json"), sessions, [])


if __name__ == "__main__":
    a = sys.argv[1:]

    def opt(flag, default):
        return int(a[a.index(flag) + 1]) if flag in a else default

    sys.exit(main(a[0], a[1], a[2], opt("--random-blocks", 13), opt("--e-blocks", 7), opt("--seed", 1),
                  a[a.index("--workload") + 1] if "--workload" in a else "iters"))
