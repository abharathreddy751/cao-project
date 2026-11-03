"""Write the pre-registered Stage 4 Montage designs (EVALUATION_PROTOCOL.md section 12). Exclusive create.

  main     all pools (6 P + 7 E workers), instances d1.1 primary and d1.1 c10.7, 4 interleaved seeded blocks, 11 conditions
  regimeR  scarce fast cores (2 P + 7 E workers), primary instance, 3 blocks, 5 conditions

  python scripts/make_stage4_designs.py <out_dir>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S3 = ROOT / "data/results/stage3_20261012"
PROFILE = ROOT / "data/results/stage2_20261012/profile_montage/20261012T092355_profile.json"
PRIMARY, SECOND = "d1.1_dss2b_c56.7_24.0", "d1.1_dss2b_c10.7_41.3"
REFS = {PRIMARY: ROOT / "data/results/stage1_20261011/valid/seq1", SECOND: S3 / "refs" / SECOND}
FINAL = ["1-mosaic.fits", "1-mosaic_area.fits", "1-mosaic.png"]
MODEL = lambda n: str(S3 / "eval" / "final_test" / f"model_{n}.json")  # noqa: E731 - fitted on all non-test rows (Stage 3)


def cond(name, policy, instances, model=None):
    kw = {"profile": str(PROFILE), "fits_atol": None, "final_outputs": FINAL,
          "reference_hashes": str(REFS[instances[0]] / "run.json"), "reference_dir": str(REFS[instances[0]] / "work"),
          "reference_by_instance": {i: {"reference_hashes": str(REFS[i] / "run.json"), "reference_dir": str(REFS[i] / "work")}
                                    for i in instances}}
    if model:
        kw["model_path"] = MODEL(model)
    return {"name": name, "policy": policy, "estimator": None, "workload": {"kind": "montage"}, "kwargs": kw}


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    inst = [PRIMARY, SECOND]
    main_conds = [cond("B0_P_only", "B0_P_only", inst), cond("B4_greedy_eligible", "B4_greedy_eligible", inst),
                  cond("HEFT_E1", "HEFT_E1", inst), cond("PEFT_E1", "PEFT_E1", inst), cond("EFT_E1", "EFT_E1", inst),
                  cond("EFT_E3", "EFT_E3", inst), cond("EFT_E1_rc", "EFT_E1_rc", inst),
                  cond("EFT_Ridge", "EFT_Ridge", inst, "Ridge"), cond("EFT_CatBoost", "EFT_CatBoost", inst, "CatBoost"),
                  cond("EFT_MLP", "EFT_MLP", inst, "MLP"), cond("EFT_E1_rank", "EFT_E1_rank", inst)]
    designs = {
        "design_main.json": {"name": "stage4_main", "evidence_label": "real", "seed": 20261030, "n_blocks": 4,
                             "instances": inst, "warmup_blocks": 0, "min_free_ram_gb": 2.5, "reference": "B0_P_only",
                             "run_timeout_s": 2400, "conditions": main_conds},
        "design_regimeR.json": {"name": "stage4_regimeR_P2E7", "evidence_label": "real", "seed": 20261031, "n_blocks": 3,
                                "instances": [PRIMARY], "warmup_blocks": 0, "min_free_ram_gb": 2.5,
                                "reference": "B4_greedy_eligible", "run_timeout_s": 2400,
                                "conditions": [cond("B0_P_only", "B0_P_only", [PRIMARY]),
                                               cond("B4_greedy_eligible", "B4_greedy_eligible", [PRIMARY]),
                                               cond("EFT_E1", "EFT_E1", [PRIMARY]), cond("HEFT_E1", "HEFT_E1", [PRIMARY]),
                                               cond("EFT_CatBoost", "EFT_CatBoost", [PRIMARY], "CatBoost")]}}
    for fn, d in designs.items():
        with (out / fn).open("x") as f:
            json.dump(d, f, indent=1)
    with (out / "adapter_config_main.json").open("x") as f:
        json.dump({"timeout_s": 1800, "run_timeout_s": 2400, "cleanup_work": True}, f)
    with (out / "adapter_config_regimeR.json").open("x") as f:
        json.dump({"timeout_s": 1800, "run_timeout_s": 2400, "cleanup_work": True, "max_p_slots": 2}, f)
    print({fn: f"{len(d['conditions'])} conditions x {d['n_blocks']} blocks" for fn, d in designs.items()})


if __name__ == "__main__":
    main(sys.argv[1])
