"""Write the Stage 2 policy-matrix design (every policy on the frozen Montage instance, 3 interleaved blocks) next to the
profile it uses. Exclusive create. Usage: python scripts/make_stage2_design.py <profile.json> <out_dir>"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = "d1.1_dss2b_c56.7_24.0"


def main(profile: str, out_dir: str) -> None:
    out = Path(out_dir)
    common = {"profile": str(Path(profile).resolve()),
              "reference_hashes": str(ROOT / "data/results/stage1_20261011/valid/seq1/run.json"),
              "reference_dir": str(ROOT / "data/results/stage1_20261011/valid/seq1/work"),
              "fits_atol": None, "final_outputs": ["1-mosaic.fits", "1-mosaic_area.fits", "1-mosaic.png"]}

    def cond(name, policy, **kw):
        return {"name": name, "policy": policy, "estimator": None,
                "workload": {"kind": "montage", "instance": INSTANCE}, "kwargs": {**common, **kw}}

    conds = [cond("B0_P_only", "B0_P_only"), cond("B0_E_only", "B0_E_only"), cond("B1_round_robin", "B1_round_robin"),
             cond("B2_static_P", "B2_static_mapping", policy_cfg={"B2_static_mapping": {"mapping": {"extcmd": "P"}}}),
             cond("B3_shortest_queue", "B3_shortest_queue"), cond("B4_greedy_eligible", "B4_greedy_eligible"),
             cond("B5_criticality", "B5_criticality"), cond("random", "random"), cond("EFT_E1", "EFT_E1"),
             cond("EFT_E3", "EFT_E3"), cond("EFT_E1_rc", "EFT_E1_rc"), cond("HEFT_E1", "HEFT_E1"),
             cond("PEFT_E1", "PEFT_E1"), cond("EFT_E1_rank", "EFT_E1_rank")]
    design = {"name": "stage2_policy_matrix", "evidence_label": "real", "seed": 20261012, "n_blocks": 3,
              "instances": [INSTANCE], "warmup_blocks": 0, "min_free_ram_gb": 2.5, "reference": "B4_greedy_eligible",
              "run_timeout_s": 2400, "conditions": conds}
    with (out / "design_stage2_matrix.json").open("x") as f:
        json.dump(design, f, indent=1)
    with (out / "adapter_config.json").open("x") as f:
        json.dump({"timeout_s": 1800, "run_timeout_s": 2400, "cleanup_work": True}, f)
    print(f"{len(conds)} conditions x {design['n_blocks']} blocks")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
