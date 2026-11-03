"""Revival engineering check on the UNIFORM batch (no hidden cost, no contention), with the real CUDA worker: do the revival policies do no harm?

  python scripts/revival_uniform_design.py <out_dir> <gpu_spike.json> <profile.json> <param_model.json> <calibration.json> <name> <n_blocks> <seed>

Same workload, pools (6 P, 7 E, one CUDA worker) and stage table as the Study 2 no-harm check (``study2_uniform_design.py``). Conditions:
B0_P_only (static), B4_gpu (reference), PRED_RANK_GREEDY_gpu (existing policy), RSA_TASK_ONLY_gpu, RSA_STATE_ONLY_gpu, RSA_COMBINED_gpu.
Nothing varies in this batch's task parameters, so the size-only baseline profile of RSA_STATE_ONLY is the same per-stage table as the
parameter model (``param_model_uniform.json``, fitted on EARLIER uniform-batch logs). Created exclusively.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(out_dir, spike, profile, model, calibration, name, n_blocks, seed) -> None:
    from caosched.experiment.gpu_adapter import gpu_stage_table_from_spike

    spec = importlib.util.spec_from_file_location("study2_design", ROOT / "scripts" / "study2_design.py")
    assert spec is not None and spec.loader is not None
    sd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sd)
    table = gpu_stage_table_from_spike(spike, sd.TILE, denoise_iterations=sd.ITER)
    base = {c["name"]: c for c in sd.conditions(table, str(Path(profile).resolve()))}
    gpu_kw = base["EFT_E1_gpu"]["kwargs"]
    pm, cal = str(Path(model).resolve()), str(Path(calibration).resolve())

    def cond(cname, kw):
        return {"name": cname, "policy": "EFT_E1", "estimator": None, "workload": {"kind": "study2_batch"}, "kwargs": {**gpu_kw, **kw}}

    conds = [base["B0_P_only"], base["B4_gpu"], cond("PRED_RANK_GREEDY_gpu", {"binding": "pred_rank_greedy", "param_model": pm}),
             cond("RSA_TASK_ONLY_gpu", {"binding": "rsa_task_only", "param_model": pm, "calibration": cal}),
             cond("RSA_STATE_ONLY_gpu", {"binding": "rsa_state_only", "blind_model": pm, "calibration": cal}),
             cond("RSA_COMBINED_gpu", {"binding": "rsa_combined", "param_model": pm, "calibration": cal})]
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks), "instances": [None],
              "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True, "reference": "B4_gpu",
              "gpu_stage_table": table, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    print(name, [c["name"] for c in conds], n_blocks, "blocks")


if __name__ == "__main__":
    main(*sys.argv[1:])
