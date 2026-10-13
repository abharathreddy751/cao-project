"""Write the pre-registered CONFIRMATORY designs (EVALUATION_PROTOCOL.md section 13), written because section 12's 4-block main
design could not reach p < 0.05 under the Holm-adjusted sign-flip test. Block counts here are chosen so the smallest attainable
sign-flip p-value (2 / 2**n) is below the Holm threshold of the family. Exclusive create.

  main      6 P + 7 E, instances d1.1 primary / c10.7 alternating, 9 blocks, 12 conditions, reference B0_P_only
            family = 11 contrasts vs B0_P_only; Holm threshold 0.05/11 = 0.00455; 2/2**9 = 0.0039 -> n = 9
  regimeR   2 P + 7 E, primary instance, 8 blocks, 6 conditions, reference B4 greedy
            family = 5 contrasts; Holm threshold 0.01; 2/2**8 = 0.0078 -> n = 8
  gpu       tile 1024 image pipeline, 24 blocks, 7 conditions, reference EFT_E1_cpu (does GPU use help predictive placement?)

  python scripts/make_stage5_designs.py <out_dir> <spike_dir> <gpu_profile.json>
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(out_dir: str, spike_dir: str, gpu_profile: str) -> None:
    s4 = _load("make_stage4_designs")
    inst = [s4.PRIMARY, s4.SECOND]
    c = lambda name, policy, model=None, instances=inst: s4.cond(name, policy, instances, model)  # noqa: E731
    main_conds = [c("B0_P_only", "B0_P_only"), c("B0_P_early", "B0_P_early"), c("B4_greedy_eligible", "B4_greedy_eligible"),
                  c("HEFT_E1", "HEFT_E1"), c("PEFT_E1", "PEFT_E1"), c("EFT_E1", "EFT_E1"), c("EFT_E3", "EFT_E3"),
                  c("EFT_E1_rc", "EFT_E1_rc"), c("EFT_Ridge", "EFT_Ridge", "Ridge"), c("EFT_CatBoost", "EFT_CatBoost", "CatBoost"),
                  c("EFT_MLP", "EFT_MLP", "MLP"), c("EFT_E1_rank", "EFT_E1_rank")]
    p = [s4.PRIMARY]
    r_conds = [c("B0_P_only", "B0_P_only", None, p), c("B4_greedy_eligible", "B4_greedy_eligible", None, p),
               c("EFT_E1", "EFT_E1", None, p), c("EFT_Ridge", "EFT_Ridge", "Ridge", p),
               c("EFT_CatBoost", "EFT_CatBoost", "CatBoost", p), c("EFT_MLP", "EFT_MLP", "MLP", p)]
    designs = {
        "design_main_confirm.json": {"name": "stage5_main_confirm", "evidence_label": "real", "seed": 20261101, "n_blocks": 9,
                                     "instances": inst, "warmup_blocks": 0, "min_free_ram_gb": 2.5, "reference": "B0_P_only",
                                     "run_timeout_s": 2400, "conditions": main_conds},
        "design_regimeR_confirm.json": {"name": "stage5_regimeR_confirm", "evidence_label": "real", "seed": 20261102,
                                        "n_blocks": 8, "instances": p, "warmup_blocks": 0, "min_free_ram_gb": 2.5,
                                        "reference": "B4_greedy_eligible", "run_timeout_s": 2400, "conditions": r_conds}}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for fn, d in designs.items():
        with (out / fn).open("x") as f:
            json.dump(d, f, indent=1)
    with (out / "adapter_config_main.json").open("x") as f:
        json.dump({"timeout_s": 1800, "run_timeout_s": 2400, "cleanup_work": True}, f)
    with (out / "adapter_config_regimeR.json").open("x") as f:
        json.dump({"timeout_s": 1800, "run_timeout_s": 2400, "cleanup_work": True, "max_p_slots": 2}, f)
    # GPU: same builder as stage 4, more blocks, reference = predictive CPU-only
    g = _load("make_gpu_design")
    g.main(str(out / "gpu"), spike_dir, gpu_profile, 24, "stage5_gpu_confirm", 20261103, "EFT_E1_cpu", "design_gpu_confirm.json")
    gd = json.loads((out / "gpu" / "design_gpu_confirm.json").read_text())
    print({fn: f"{len(d['conditions'])} conditions x {d['n_blocks']} blocks" for fn, d in designs.items()},
          f"gpu: {len(gd['conditions'])} conditions x {gd['n_blocks']} blocks")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
