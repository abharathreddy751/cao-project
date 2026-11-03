"""Study 2 hidden-cost workload (protocol section 18): write the coverage design and the gate design. Files created exclusively.

  python scripts/study2_iters_design.py cover <out_dir> <profile.json> <name> <n_blocks> <seed>
  python scripts/study2_iters_design.py cover2 <out_dir> <profile.json> <name> <n_blocks> <seed>      (random only)
  python scripts/study2_iters_design.py cover_e <out_dir> <profile.json> <name> <n_blocks> <seed>    (B0_E_only)
  python scripts/study2_iters_design.py confirm3 <out_dir> <profile.json> <name> <n_blocks> <seed> <selected_condition> <param_model.json>
  python scripts/study2_iters_design.py dev3 <out_dir> <profile.json> <name> <n_blocks> <seed> - <param_model.json>
  python scripts/study2_iters_design.py dev2 <out_dir> <profile.json> <name> <n_blocks> <seed> - <param_model.json>
  python scripts/study2_iters_design.py confirm2 <out_dir> <profile.json> <name> <n_blocks> <seed> <selected_condition> <param_model.json>
  python scripts/study2_iters_design.py confirm <out_dir> <profile.json> <name> <n_blocks> <seed> - <iter_model.json>
  python scripts/study2_iters_design.py gate  <out_dir> <profile.json> <name> <n_blocks> <seed> <oracle_rows.json> <iter_model.json>

Workload: 64 independent chains at ONE image size (512 px), 48 with denoise x2 and 16 with denoise x120 (60 times the denoise work;
sizes are equal, so a table keyed by size and a size-ordered rule cannot see it). CPU pools only. Two instances = two fixed chain
orders (order_a seed 11, order_b seed 22), alternating by block. ``profile`` is the solo E1 profile of the 512 px batch (denoise x8).
cover: random, B4, B4_param_first, EFT_E1_noctx (logs feed the oracle table and the denoise line only).
gate:  blind rules B0_P_only, B3, B4; informed heuristic B4_param_first; blind predictor EFT_E1_noctx; learned predictors
       EFT_iter_model_noctx, EFT_iter_model_rank_noctx; oracles O_EFT_E5, O_EFT_E5_rank.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ITERS = {"small": [48, 2], "big": [16, 120]}
ORDERS = {"order_a": 11, "order_b": 22}


CONFIRM3_ORDERS = {"order_g": 77, "order_h": 88}  # fresh orders for the 2-P-core configuration (protocol section 26)
CONFIRM2_ORDERS = {"order_e": 55, "order_f": 66}  # chain orders never seen by any earlier session (protocol section 21)
CONFIRM_ORDERS = {"order_c": 33, "order_d": 44}  # chain orders never seen by the coverage or gate sessions (protocol section 19)


def main(kind, out_dir, profile, name, n_blocks, seed, rows=None, model=None) -> None:
    orders = (CONFIRM_ORDERS if kind == "confirm" else CONFIRM2_ORDERS if kind == "confirm2"
              else CONFIRM3_ORDERS if kind == "confirm3" else ORDERS)
    base = {"iters": ITERS, "tile": 512, "seed": 0, "order_seeds": orders, "profile": str(Path(profile).resolve())}

    def cond(cname, policy, **kw):
        return {"name": cname, "policy": policy, "estimator": None, "workload": {"kind": "study2_iters"}, "kwargs": {**base, **kw}}

    if kind == "dev3":  # amendment A11: the efficient hold implementation against the work-conserving greedy, same references
        pm = str(Path(model).resolve())
        conds = [cond("B4", "B4"), cond("B4_param_first", "B4", binding="param_first"),
                 cond("PRED_RANK_GREEDY", "EFT_E1", binding="pred_rank_greedy", param_model=pm),
                 cond("PRED_RANK_HOLD", "EFT_E1", binding="pred_rank_hold", param_model=pm, hold_min_s=0.010)]
        reference = "B4"
    elif kind in ("dev2", "confirm2", "confirm3"):  # <model> = the generic parameter model file (study2/param_model.py)
        pm = str(Path(model).resolve())
        cands = [cond("EFT_param_model_rank_noctx", "EFT_E1", binding="param_model_rank", param_model=pm),
                 cond("HEFT_param_model", "EFT_E1", binding="param_model_heft", param_model=pm),
                 cond("PEFT_param_model", "EFT_E1", binding="param_model_peft", param_model=pm),
                 cond("PRED_RANK_GREEDY", "EFT_E1", binding="pred_rank_greedy", param_model=pm),
                 cond("PRED_RANK_HOLD", "EFT_E1", binding="pred_rank_hold", param_model=pm, hold_min_s=0.010)]
        refs = [cond("B4", "B4"), cond("B4_param_first", "B4", binding="param_first")]
        if kind in ("confirm2", "confirm3"):  # the single selected candidate (name given in <rows>), plus the blind rules
            cands = [c for c in cands if c["name"] == rows]
            refs += [cond("B0_P_only", "B0_P_only"), cond("EFT_E1_noctx", "EFT_E1", binding="early_noctx")]
        conds = refs + cands
        reference = "B4"
    elif kind == "confirm":  # last argument: the denoise-line file (the two arguments before it are unused: "-")
        mod = str(Path(model).resolve())
        conds = [cond("B0_P_only", "B0_P_only"), cond("B4", "B4"), cond("EFT_E1_noctx", "EFT_E1", binding="early_noctx"),
                 cond("B4_param_first", "B4", binding="param_first"),
                 cond("EFT_iter_model_noctx", "EFT_E1", binding="iter_model", iter_model=mod),
                 cond("EFT_iter_model_rank_noctx", "EFT_E1", binding="iter_model_rank", iter_model=mod)]
        reference = "B4"
    elif kind == "cover_e":  # amendment A10: every task on the E pool (B0_E_only), to log every (task, E) pair
        conds = [cond("B0_E_only", "B0_E_only")]
        reference = "B0_E_only"
    elif kind == "cover2":  # extra coverage (amendment A8): random placement only, to log every (task, pool) pair
        conds = [cond("random", "random")]
        reference = "random"
    elif kind == "cover":
        conds = [cond("random", "random"), cond("B4", "B4"), cond("B4_param_first", "B4", binding="param_first"),
                 cond("EFT_E1_noctx", "EFT_E1", binding="early_noctx")]
        reference = "random"
    else:
        tab, mod = str(Path(rows).resolve()), str(Path(model).resolve())
        conds = [cond("B0_P_only", "B0_P_only"), cond("B3", "B3"), cond("B4", "B4"),
                 cond("B4_param_first", "B4", binding="param_first"), cond("EFT_E1_noctx", "EFT_E1", binding="early_noctx"),
                 cond("EFT_iter_model_noctx", "EFT_E1", binding="iter_model", iter_model=mod),
                 cond("EFT_iter_model_rank_noctx", "EFT_E1", binding="iter_model_rank", iter_model=mod),
                 cond("O_EFT_E5", "EFT_E1", binding="oracle", oracle_rows=tab),
                 cond("O_EFT_E5_rank", "EFT_E1", binding="oracle", oracle_rows=tab, rank=True)]
        reference = "B4"
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks),
              "instances": list(orders), "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True, "reference": reference, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    print(name, [c["name"] for c in conds], n_blocks, "blocks")


if __name__ == "__main__":
    main(*sys.argv[1:])
