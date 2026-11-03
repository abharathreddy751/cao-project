"""Revival: coverage, oracle-gate, pilot and confirmatory designs for the dynamic-contention mixed-DAG workload. Files created exclusively.

  python scripts/revival_design.py cover   <out_dir> <profile.json> <name> <n_blocks> <seed>
  python scripts/revival_design.py gate    <out_dir> <profile.json> <name> <n_blocks> <seed> <param_model> <blind_model> <oracle_rows> <calibration>
  python scripts/revival_design.py pilot   <out_dir> <profile.json> <name> <n_blocks> <seed> <param_model> <blind_model> <oracle_rows> <calibration>
  python scripts/revival_design.py confirm <out_dir> <profile.json> <name> <n_blocks> <seed> <param_model> <blind_model> - <calibration>

Workload: the TEST classes of the two-factor study (48 chains of 256 px x 2 repeats, 12 of 256 px x 300, 12 of 1024 px x 3) as a mixed DAG
with 6 groups of 12 chains and a two-level fan-in (``revival.workload.build_dyn``). CPU pools only (6 P + 7 E workers); the CUDA worker
is not used (the GPU path is a separate, labelled study). Contention (``revival.contention``): two consecutive 1 s phases starting 0.2 s
after the run starts; in each phase 3 of the 6 P cores (disjoint between phases) are shared with 2 spinning processes (measured slowdown
of a long task about 2.7x). An instance is a chain order AND a contention schedule; the gate, pilot and confirmatory instances use
disjoint seeds, none of them used for the model's training sessions. The SAME schedule is started for every policy of an instance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TEST = [[48, 256, 2], [12, 256, 300], [12, 1024, 3]]
CONT = {"n_hot": 3, "burners": 2, "t0": 0.2, "phase_s": 1.0, "n_phases": 2}
INSTANCES = {
    "gate": {"g1": (71, 101), "g2": (72, 102)},
    "pilot": {"p1": (81, 111), "p2": (82, 112)},
    "confirm": {"c1": (91, 121), "c2": (92, 122), "c3": (93, 123), "c4": (94, 124)},
}


def main(kind, out_dir, profile, name, n_blocks, seed, param_model=None, blind_model=None, oracle_rows=None, calibration=None) -> None:
    inst = INSTANCES["gate" if kind == "cover" else kind]
    spec = {n: {"order_seed": o, "contention": None if kind == "cover" else {"seed": c, **CONT}} for n, (o, c) in inst.items()}
    base = {"dyn": {"classes": TEST, "groups": 6, "seed": 0}, "instances_spec": spec, "profile": str(Path(profile).resolve())}
    ab = lambda p: str(Path(p).resolve())  # noqa: E731

    def cond(cname, policy, **kw):
        return {"name": cname, "policy": policy, "estimator": None, "workload": {"kind": "revival_dyn"}, "kwargs": {**base, **kw}}

    if kind == "cover":
        conds, reference = [cond("B0_P_only", "B0_P_only"), cond("B0_E_only", "B0_E_only")], "B0_P_only"
    else:
        pm, bm, cal = ab(param_model), ab(blind_model), ab(calibration)
        conds = [cond("B4", "B4"), cond("B4_param_first", "B4", binding="param_first"), cond("B4_cost_first", "B4", binding="cost_first"),
                 cond("B4_largest_first", "B4", binding="largest_first"), cond("B0_P_only", "B0_P_only"),
                 cond("PRED_RANK_GREEDY", "EFT_E1", binding="pred_rank_greedy", param_model=pm)]
        if kind in ("pilot", "confirm"):
            conds += [cond("RSA_TASK_ONLY", "EFT_E1", binding="rsa_task_only", param_model=pm, calibration=cal),
                      cond("RSA_STATE_ONLY", "EFT_E1", binding="rsa_state_only", blind_model=bm, calibration=cal),
                      cond("RSA_COMBINED", "EFT_E1", binding="rsa_combined", param_model=pm, calibration=cal)]
        if kind in ("gate", "pilot"):
            conds += [cond("ORACLE_STATE", "EFT_E1", binding="oracle_state", oracle_rows=ab(oracle_rows), calibration=cal)]
        if kind == "pilot":
            conds += [cond("HEFT_param_model", "EFT_E1", binding="param_model_heft", param_model=pm),
                      cond("EFT_param_model_rank", "EFT_E1", binding="param_model_rank", param_model=pm)]
        reference = "B4"
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks), "instances": list(inst),
              "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True, "reference": reference, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    print(name, [c["name"] for c in conds], n_blocks, "blocks")


if __name__ == "__main__":
    main(*sys.argv[1:])
