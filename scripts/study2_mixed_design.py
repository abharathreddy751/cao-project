"""Study 2 heavy-tailed workload (protocol section 17): write the coverage design and the gate design. Files created exclusively.

  python scripts/study2_mixed_design.py cover <out_dir> <profile.json> <name> <n_blocks> <seed>
  python scripts/study2_mixed_design.py gate  <out_dir> <profile.json> <name> <n_blocks> <seed> <oracle_rows.json>

Workload: 48 small (256 px) and 16 big (1024 px) independent chains (a big chain is about 27 times the P-core time of a small one,
solo profile), denoise x8, CPU pools only (P, E; the idle CUDA worker stays in the pool and is never eligible). Two instances = two
fixed orders of the chains (``order_a`` seed 11, ``order_b`` seed 22), alternating by block.
cover: random, B4, B4_largest_first, EFT_E1_noctx. Their logs feed the oracle table only.
gate:  non-predictive B0_P_only, B3, B4, B4_largest_first; predictive EFT_E1_noctx, EFT_E1_rank_noctx; oracles O_EFT_E5, O_EFT_E5_rank.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MIX = {"small": [48, 256], "big": [16, 1024]}
ORDERS = {"order_a": 11, "order_b": 22}


def main(kind, out_dir, profile, name, n_blocks, seed, rows=None) -> None:
    base = {"mix": MIX, "denoise_iterations": 8, "seed": 0, "order_seeds": ORDERS, "profile": str(Path(profile).resolve())}

    def cond(cname, policy, **kw):
        return {"name": cname, "policy": policy, "estimator": None, "workload": {"kind": "study2_mixed"}, "kwargs": {**base, **kw}}

    if kind == "cover":
        conds = [cond("random", "random"), cond("B4", "B4"), cond("B4_largest_first", "B4", binding="largest_first"),
                 cond("EFT_E1_noctx", "EFT_E1", binding="early_noctx")]
        reference = "random"
    else:
        tab = str(Path(rows).resolve())
        conds = [cond("B0_P_only", "B0_P_only"), cond("B3", "B3"), cond("B4", "B4"),
                 cond("B4_largest_first", "B4", binding="largest_first"),
                 cond("EFT_E1_noctx", "EFT_E1", binding="early_noctx"),
                 cond("EFT_E1_rank_noctx", "EFT_E1", binding="rank_noctx"),
                 cond("O_EFT_E5", "EFT_E1", binding="oracle", oracle_rows=tab),
                 cond("O_EFT_E5_rank", "EFT_E1", binding="oracle", oracle_rows=tab, rank=True)]
        reference = "B4"
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks),
              "instances": list(ORDERS), "warmup_blocks": 1, "min_free_ram_gb": 0.8, "reference": reference, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    print(name, [c["name"] for c in conds], n_blocks, "blocks")


if __name__ == "__main__":
    main(*sys.argv[1:])
