"""Study 2 oracle bound (protocol section 14): write (a) the coverage design that fills gaps of the oracle table and (b) the oracle design.

  python scripts/study2_oracle_design.py cover  <out_dir> <gpu_spike.json> <profile.json> <name> <n_blocks> <seed>
  python scripts/study2_oracle_design.py oracle <out_dir> <gpu_spike.json> <profile.json> <name> <n_blocks> <seed> <e2e_terms.json> <oracle_rows.json>

cover:  one condition, ``random_gpu`` (random idle eligible worker, GPU allowed), so every (task, pool) pair is logged at least once.
        Its logs are oracle input only, never an evaluation session.
oracle: O_EFT_E5_gpu, O_EFT_E5_e2e_gpu, O_EFT_E5_cpu (EFT with the replay oracle, no context logging) next to B4_gpu,
        EFT_E1_noctx_gpu and B0_P_only; reference B4_gpu. Files are created exclusively.
Conditions of the stage 5-style design are reused from ``scripts/study2_design.py`` (same workload, same stage table).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from caosched.experiment.gpu_adapter import gpu_stage_table_from_spike

ROOT = Path(__file__).resolve().parents[1]


def main(kind, out_dir, spike, profile, name, n_blocks, seed, e2e=None, rows=None) -> None:
    spec = importlib.util.spec_from_file_location("study2_design", ROOT / "scripts" / "study2_design.py")
    sd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sd)
    table = gpu_stage_table_from_spike(spike, sd.TILE, denoise_iterations=sd.ITER)
    prof = str(Path(profile).resolve())
    base = {c["name"]: c for c in sd.conditions(table, prof)}
    gpu_kw = base["EFT_E1_gpu"]["kwargs"]

    def cond(cname, policy, kw):
        return {"name": cname, "policy": policy, "estimator": None, "workload": {"kind": "study2_batch"}, "kwargs": kw}

    if kind == "cover":
        conds = [cond("random_gpu", "random", dict(gpu_kw))]
        reference = "random_gpu"
    else:
        terms, tab = str(Path(e2e).resolve()), str(Path(rows).resolve())
        conds = [cond("O_EFT_E5_gpu", "EFT_E1", {**gpu_kw, "binding": "oracle", "oracle_rows": tab}),
                 cond("O_EFT_E5_e2e_gpu", "EFT_E1", {**gpu_kw, "binding": "oracle", "oracle_rows": tab, "e2e_terms": terms}),
                 cond("O_EFT_E5_cpu", "EFT_E1", {**base["B4_cpu"]["kwargs"], "binding": "oracle", "oracle_rows": tab}),
                 base["B4_gpu"],
                 cond("EFT_E1_noctx_gpu", "EFT_E1", {**gpu_kw, "binding": "early_noctx"}),
                 base["B0_P_only"]]
        reference = "B4_gpu"
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks), "instances": [None],
              "warmup_blocks": 1, "min_free_ram_gb": 0.8, "reference": reference, "gpu_stage_table": table, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    print(name, [c["name"] for c in conds], n_blocks, "blocks")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a)
