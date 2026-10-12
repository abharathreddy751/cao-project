"""Write the Stage 3 scheduling-pilot design (model selection): EFT with each predictor of the ladder on the primary
Montage instance, 3 interleaved blocks. Models are the ones fitted by scripts/evaluate_models.py on all non-test rows
(eval/final_test/model_*.json). Exclusive create.

  python scripts/make_stage3_pilot_design.py <out_dir>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S3 = ROOT / "data" / "results" / "stage3_20261012"
INSTANCE = "d1.1_dss2b_c56.7_24.0"
PROFILE = ROOT / "data/results/stage2_20261012/profile_montage/20261012T092355_profile.json"
REF = ROOT / "data/results/stage1_20261011/valid/seq1"


def main(out_dir: str) -> None:
    common = {"profile": str(PROFILE), "reference_hashes": str(REF / "run.json"), "reference_dir": str(REF / "work"),
              "fits_atol": None, "final_outputs": ["1-mosaic.fits", "1-mosaic_area.fits", "1-mosaic.png"]}

    def cond(name, policy, model=None):
        kw = dict(common)
        if model:
            kw["model_path"] = str(S3 / "eval" / "final_test" / f"model_{model}.json")
        return {"name": name, "policy": policy, "estimator": None,
                "workload": {"kind": "montage", "instance": INSTANCE}, "kwargs": kw}

    conds = [cond("EFT_E1", "EFT_E1"), cond("EFT_E3", "EFT_E3"), cond("EFT_E1_rc", "EFT_E1_rc"),
             cond("EFT_Ridge", "EFT_Ridge", "Ridge"), cond("EFT_CatBoost", "EFT_CatBoost", "CatBoost"),
             cond("EFT_MLP", "EFT_MLP", "MLP")]
    design = {"name": "stage3_scheduling_pilot", "evidence_label": "real", "seed": 20261020, "n_blocks": 3,
              "instances": [INSTANCE], "warmup_blocks": 0, "min_free_ram_gb": 2.5, "reference": "EFT_E1",
              "run_timeout_s": 2400, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "design_stage3_pilot.json").open("x") as f:
        json.dump(design, f, indent=1)
    with (out / "adapter_config.json").open("x") as f:
        json.dump({"timeout_s": 1800, "run_timeout_s": 2400, "cleanup_work": True}, f)
    print(f"{len(conds)} conditions x {design['n_blocks']} blocks")


if __name__ == "__main__":
    main(sys.argv[1])
