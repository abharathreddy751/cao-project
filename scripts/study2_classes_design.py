"""Study 2 two-factor hidden-cost workload (protocol section 30): coverage, pilot and confirmatory designs. Files created exclusively.

  python scripts/study2_classes_design.py cover2   <out_dir> <profile.json> <name> <n_blocks> <seed>             (random placement)
  python scripts/study2_classes_design.py cover_e  <out_dir> <profile.json> <name> <n_blocks> <seed>             (every task on E)
  python scripts/study2_classes_design.py pilot    <out_dir> <profile.json> <name> <n_blocks> <seed> - <param_model.json>
  python scripts/study2_classes_design.py confirm  <out_dir> <profile.json> <name> <n_blocks> <seed> - <param_model.json>

Cost of a chain depends on BOTH its image side and its denoise iterations. COVER is a grid of (side, iterations) combinations the model is
trained on (a few chains each; the heaviest combinations have one chain); TEST holds the classes of the evaluation, chosen as combinations
the model never saw (interpolation between grid points): many light chains, 12 chains of a small image with very many repeats and 12 of
a large image with few repeats, so that sorting by size alone or by repeats alone puts a heavy class last. CPU pools only.
Instances = two fixed chain orders: pilot order_a / order_b (seeds 11, 22), confirm order_e / order_f (seeds 55, 66).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

COVER = [[3, 256, 2], [3, 256, 20], [3, 256, 100], [2, 256, 400], [3, 512, 2], [3, 512, 20], [2, 512, 100],
         [3, 1024, 2], [2, 1024, 20], [1, 1024, 100]]
TEST = [[48, 256, 2], [12, 256, 300], [12, 1024, 3]]
PILOT_ORDERS = {"order_a": 11, "order_b": 22}
CONFIRM_ORDERS = {"order_e": 55, "order_f": 66}


def main(kind, out_dir, profile, name, n_blocks, seed, _unused=None, model=None) -> None:
    classes = COVER if kind in ("cover2", "cover_e") else TEST
    orders = CONFIRM_ORDERS if kind == "confirm" else PILOT_ORDERS
    base = {"classes": classes, "seed": 0, "order_seeds": orders, "profile": str(Path(profile).resolve())}

    def cond(cname, policy, **kw):
        return {"name": cname, "policy": policy, "estimator": None, "workload": {"kind": "study2_classes"}, "kwargs": {**base, **kw}}

    if kind == "cover2":
        conds, reference = [cond("random", "random")], "random"
    elif kind == "cover_e":
        conds, reference = [cond("B0_E_only", "B0_E_only")], "B0_E_only"
    else:
        pm = str(Path(model).resolve())
        conds = [cond("B4", "B4"), cond("B4_param_first", "B4", binding="param_first"),
                 cond("B4_largest_first", "B4", binding="largest_first"), cond("B4_cost_first", "B4", binding="cost_first"),
                 cond("B0_P_only", "B0_P_only"),
                 cond("PRED_RANK_GREEDY", "EFT_E1", binding="pred_rank_greedy", param_model=pm)]
        reference = "B4"
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks), "instances": list(orders),
              "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True, "reference": reference, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    print(name, [c["name"] for c in conds], n_blocks, "blocks")


if __name__ == "__main__":
    main(*sys.argv[1:])
