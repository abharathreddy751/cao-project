"""Write the pre-registered GPU-workload design (tile 1024, 16 branches, image pipeline with CUDA variants): CPU-only versus
CUDA-enabled placements under non-predictive and predictive policies, interleaved seeded blocks. Exclusive create.
The set of stages allowed on the GPU is read from the recorded CPU-vs-CUDA spike (a stage is allowed only if its row at this tile
was bit/tolerance-equivalent AND faster including host-device copies).

  python scripts/make_gpu_design.py <out_dir> <spike_dir> <gpu_profile.json> [n_blocks]
"""
import json
import sys
from pathlib import Path

from caosched.experiment.gpu_adapter import gpu_stage_table_from_spike


def main(out_dir: str, spike_dir: str, profile: str, n_blocks: int = 12, name: str = "stage4_gpu_workload",
         seed: int = 20261040, reference: str = "B0_P_only", fname: str = "design_gpu.json") -> None:
    table = gpu_stage_table_from_spike(Path(spike_dir) / "gpu_spike.json", 1024)
    base = {"tile": 1024, "n_images": 16, "seed": 0, "denoise_iterations": 1, "profile": str(Path(profile).resolve())}

    def cond(name, policy, gpu, **kw):
        k = {**base, **kw}
        k["gpu_stage_table"] = table
        if not gpu:
            k["no_gpu"] = True
        return {"name": name, "policy": policy, "estimator": None, "workload": {"kind": "gpu_image"}, "kwargs": k}

    b4g = {"policy_cfg": {"B4_greedy_eligible": {"priority": ["G", "P", "E"]}}}
    conds = [cond("B0_P_only", "B0_P_only", False), cond("B4_cpu", "B4_greedy_eligible", False),
             cond("B4_gpu", "B4_greedy_eligible", True, **b4g), cond("random_gpu", "random", True),
             cond("EFT_E1_cpu", "EFT_E1", False), cond("EFT_E1_gpu", "EFT_E1", True), cond("HEFT_E1_gpu", "HEFT_E1", True)]
    design = {"name": name, "evidence_label": "real", "seed": seed, "n_blocks": n_blocks,
              "instances": [None], "warmup_blocks": 0, "min_free_ram_gb": 2.5, "reference": reference,
              "run_timeout_s": 900, "gpu_stage_table": table, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / fname).open("x") as f:
        json.dump(design, f, indent=1)
    with (out / "adapter_config_gpu.json").open("x") as f:
        json.dump({"timeout_s": 300, "run_timeout_s": 900}, f)
    print(table, len(conds), "conditions x", n_blocks, "blocks")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 12)
