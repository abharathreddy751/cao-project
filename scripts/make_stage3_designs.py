"""Write the Stage 3 data-collection designs (docs/research_redesign/STAGE3_COLLECTION_PLAN.md): one design file and one
adapter config per Montage instance, because blocks cycle instances and each instance needs its own block count.
Every file is created exclusively ("x"): re-running never overwrites a design that may already have been used.

  python scripts/make_stage3_designs.py [--out data/results/stage3_20261012/designs]

Conditions per block: EFT_E1 (reference, a scheduling policy) and RandomOccupancy under four seeds/occupancy settings
(data collection). Reference output hashes: data/results/stage3_20261012/refs/<instance>/run.json and .../work
(paths only; the files need not exist when the design is written).
The numbers here are proposals fixed before collection; changing one afterwards creates a new design (new hash).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE3 = ROOT / "data" / "results" / "stage3_20261012"
PROFILE = ROOT / "data" / "results" / "stage2_20261012" / "profile_montage" / "20261012T092355_profile.json"
PRIMARY = "d1.1_dss2b_c56.7_24.0"
STAGE1_REF = ROOT / "data" / "results" / "stage1_20261011" / "valid" / "seq1"
FINAL = ["1-mosaic.fits", "1-mosaic_area.fits", "1-mosaic.png"]

# instance -> (n_tasks, n_blocks, design seed, run_timeout_s); timeouts: d1.1 as Stage 2, d1.0 lower, d1.5 scaled
# (re-check d1.5 against the sequential reference total_wall_s before launch)
INSTANCES = {
    "d1.0_dss2b_c56.7_24.0": (19, 4, 20261013, 1800),
    "d1.1_dss2b_c56.7_24.0": (59, 4, 20261014, 2400),
    "d1.1_dss2b_c10.7_41.3": (59, 4, 20261015, 2400),
    "d1.5_dss2b_c56.7_24.0": (157, 2, 20261016, 7200),
}
# name -> RandomOccupancy kwargs (seed is fixed per condition; allowed_pools omitted = all pools)
RANDOM_OCCUPANCY = {
    "RandomOccupancy_s1": {"seed": 3101, "min_idle_s": 0.0},
    "RandomOccupancy_s3": {"seed": 3103, "min_idle_s": 1.0, "concurrency": [4, 13]},
}


def design_for(instance: str, n_blocks: int, seed: int, timeout: int, with_reference: bool = True) -> dict:
    ref = STAGE1_REF if instance == PRIMARY else STAGE3 / "refs" / instance  # the primary's reference is the Stage 1 run
    common = {"reference_hashes": str(ref / "run.json"), "reference_dir": str(ref / "work"), "fits_atol": None,
              "final_outputs": FINAL}

    def cond(name, policy, **kw):
        return {"name": name, "policy": policy, "estimator": None, "workload": {"kind": "montage", "instance": instance},
                "kwargs": {**common, **kw}}

    conds = [cond("EFT_E1", "EFT_E1", profile=str(PROFILE))] if with_reference else []
    conds += [cond(n, "RandomOccupancy", **kw) for n, kw in RANDOM_OCCUPANCY.items()]
    return {"name": f"stage3_collect_{instance}", "evidence_label": "real", "seed": seed, "n_blocks": n_blocks,
            "instances": [instance], "warmup_blocks": 0, "min_free_ram_gb": 2.5, "reference": "EFT_E1" if with_reference else None,
            "run_timeout_s": timeout, "conditions": conds}


def main(out_dir: str, with_reference: bool = True, only: tuple = ()) -> None:  # v2 (2026-10-12): fewer blocks/conditions after the Stage 2 timing showed ~7 min per random run
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for inst, (n_tasks, n_blocks, seed, timeout) in INSTANCES.items():
        if only and inst not in only:
            continue
        design = design_for(inst, n_blocks, seed, timeout, with_reference)
        path = out / f"design_{inst}.json"
        text = json.dumps(design, indent=1)
        with path.open("xb") as f:  # bytes: the design's sha256 (runner, manifests) is of exactly these bytes
            f.write(text.encode())
        with (out / f"adapter_config_{inst}.json").open("x", encoding="utf-8") as f:  # like stage2_20261012/adapter_config.json
            json.dump({"timeout_s": 1800, "run_timeout_s": timeout, "cleanup_work": True}, f)
        n_runs = n_blocks * len(design["conditions"])
        print(f"{path.name}: {n_tasks} tasks, {n_blocks} blocks x {len(design['conditions'])} conditions = {n_runs} runs, "
              f"sha256 {hashlib.sha256(text.encode()).hexdigest()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(STAGE3 / "designs_v2"))
    ap.add_argument("--no-reference", action="store_true", help="v3: RandomOccupancy conditions only (EFT_E1 rows already exist from Stage 2)")
    ap.add_argument("--only", nargs="*", default=[], help="instances to write")
    a = ap.parse_args()
    main(a.out, not a.no_reference, tuple(a.only))
