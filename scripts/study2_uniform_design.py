"""Study 2 "do no harm" check (protocol section 28): the learned policy on the UNIFORM batch (section 12 workload), where nothing is hidden.

  python scripts/study2_uniform_design.py <out_dir> <gpu_spike.json> <profile.json> <param_model.json> <name> <n_blocks> <seed>

Same workload, pools (6 P, 7 E, one CUDA worker) and stage table as the confirmatory session of section 12; conditions B0_P_only (static),
B4_gpu (blind greedy, priority G, P, E; the session reference), EFT_E1_noctx_gpu (the section 13 predictive rule) and PRED_RANK_GREEDY_gpu
(generic parameter model trained from EARLIER uniform-batch logs, predicted-rank order, work-conserving placement). Created exclusively.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(out_dir, spike, profile, model, name, n_blocks, seed) -> None:
    from caosched.experiment.gpu_adapter import gpu_stage_table_from_spike

    spec = importlib.util.spec_from_file_location("study2_design", ROOT / "scripts" / "study2_design.py")
    sd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sd)
    table = gpu_stage_table_from_spike(spike, sd.TILE, denoise_iterations=sd.ITER)
    base = {c["name"]: c for c in sd.conditions(table, str(Path(profile).resolve()))}
    gpu_kw = base["EFT_E1_gpu"]["kwargs"]

    def cond(cname, policy, kw):
        return {"name": cname, "policy": policy, "estimator": None, "workload": {"kind": "study2_batch"}, "kwargs": kw}

    conds = [base["B0_P_only"], base["B4_gpu"],
             cond("EFT_E1_noctx_gpu", "EFT_E1", {**gpu_kw, "binding": "early_noctx"}),
             cond("PRED_RANK_GREEDY_gpu", "EFT_E1", {**gpu_kw, "binding": "pred_rank_greedy",
                                                      "param_model": str(Path(model).resolve())})]
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks), "instances": [None],
              "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True, "reference": "B4_gpu",
              "gpu_stage_table": table, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    print(name, [c["name"] for c in conds], n_blocks, "blocks")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[3], a[4], a[5], a[6])
