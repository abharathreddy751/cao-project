"""Write a Study 2 design file and adapter config (exclusive create; see EVALUATION_PROTOCOL_study2.md).

  python scripts/study2_design.py <out_dir> <gpu_spike.json> <profile.json> <name> <n_blocks> <seed> [--reference COND] [--e2e terms.json] [--only A,B,C] [--min-free-ram GB] [--late]

Workload: 64 independent chains, 512 px images, denoise x8 (stage speeds: study2_gate.json). The set of stages allowed on the
GPU is read from the recorded CPU-vs-CUDA spike at side 512 (a row must be PASS). Conditions (all policies exist unchanged):
  B0_P_only                 static: every task on the P cores only
  STATIC_G_edges_features   static type-to-pool map chosen from the profile before any run: sources, denoise, aggregate on P;
                            edges and features on the CUDA worker
  STATIC_GPU_first          static type-to-pool map: every GPU-capable stage (denoise, edges, features) on the CUDA worker
  B3_gpu, B4_gpu, B4_cpu    non-predictive dynamic rules (shortest queue; greedy eligible with priority G, P, E / P, E)
  EFT_E1_gpu, EFT_E1_cpu    predictive earliest finish time with the solo profile (E1), with and without the CUDA pool
  EFT_E1_rc_gpu             EFT with online recalibration; HEFT_E1_gpu: static plan (HEFT) on the same profile
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from caosched.experiment.gpu_adapter import gpu_stage_table_from_spike

TILE, K, ITER = 512, 64, 8


def conditions(table: dict, profile: str) -> list[dict]:
    base = {"k": K, "tile": TILE, "seed": 0, "denoise_iterations": ITER, "profile": profile, "gpu_stage_table": table}

    def cond(name, policy, gpu, **kw):
        k = {**base, **kw}
        if not gpu:
            k["no_gpu"] = True
        return {"name": name, "policy": policy, "estimator": None, "workload": {"kind": "study2_batch"}, "kwargs": k}

    def static(mapping):
        return {"policy_cfg": {"B2_static_mapping": {"mapping": {"img_source": "P", "img_aggregate": "P", **mapping}}}}

    best = static({"img_denoise": "P", "img_edges": "G", "img_features": "G"})
    first = static({"img_denoise": "G", "img_edges": "G", "img_features": "G"})
    b4g = {"policy_cfg": {"B4_greedy_eligible": {"priority": ["G", "P", "E"]}}}
    return [cond("B0_P_only", "B0_P_only", False), cond("STATIC_G_edges_features", "B2", True, **best),
            cond("STATIC_GPU_first", "B2", True, **first), cond("B3_gpu", "B3", True), cond("B4_gpu", "B4", True, **b4g),
            cond("B4_cpu", "B4", False), cond("EFT_E1_gpu", "EFT_E1", True), cond("EFT_E1_cpu", "EFT_E1", False),
            cond("EFT_E1_rc_gpu", "EFT_E1_rc", True), cond("HEFT_E1_gpu", "HEFT_E1", True)]


def main(out_dir, spike, profile, name, n_blocks, seed, reference="STATIC_G_edges_features", e2e=None, only=None,
         min_free_ram_gb=1.2, late=False) -> None:
    table = gpu_stage_table_from_spike(spike, TILE, denoise_iterations=ITER)
    conds = conditions(table, str(Path(profile).resolve()))
    if e2e:  # end-to-end EFT ablation (terms measured in an EARLIER session, scripts/study2_e2e_terms.py)
        base = next(c for c in conds if c["name"] == "EFT_E1_gpu")["kwargs"]
        conds += [{"name": "EFT_E1_e2e_gpu", "policy": "EFT_E1", "estimator": None, "workload": {"kind": "study2_batch"},
                   "kwargs": {**base, "e2e_terms": str(Path(e2e).resolve())}},
                  {"name": "EFT_E1_rc_e2e_gpu", "policy": "EFT_E1_rc", "estimator": None, "workload": {"kind": "study2_batch"},
                   "kwargs": {**base, "e2e_terms": str(Path(e2e).resolve())}}]
    if late:  # late-binding EFT (study2/policies.py): same estimators, the task is held until its predicted-best worker is free
        extra = []
        for c in conds:
            if c["policy"].startswith("EFT_") and c["kwargs"].get("gpu_stage_table") and not c["kwargs"].get("no_gpu"):
                nm = c["name"].replace("_gpu", "_late_gpu") if "e2e" not in c["name"] else c["name"].replace("_e2e_gpu", "_late_e2e_gpu")
                extra.append({**c, "name": nm, "kwargs": {**c["kwargs"], "binding": "late"}})
                nc = c["name"].replace("_gpu", "_noctx_gpu") if "e2e" not in c["name"] else c["name"].replace("_e2e_gpu", "_e2e_noctx_gpu")
                extra.append({**c, "name": nc, "kwargs": {**c["kwargs"], "binding": "early_noctx"}})  # early binding, no context logging
            elif c["policy"].startswith("EFT_") and c["kwargs"].get("no_gpu") and "e2e" not in c["name"]:
                extra.append({**c, "name": c["name"].replace("_cpu", "_noctx_cpu"), "kwargs": {**c["kwargs"], "binding": "early_noctx"}})
        conds += extra
    if only:
        conds = [c for c in conds if c["name"] in only]
        if len(conds) != len(only):
            sys.exit(f"unknown condition in {only}")
    design = {"name": name, "evidence_label": "real", "seed": int(seed), "n_blocks": int(n_blocks), "instances": [None],
              "warmup_blocks": 1, "min_free_ram_gb": float(min_free_ram_gb), "reference": reference, "gpu_stage_table": table,
              "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"design_{name}.json").open("x") as f:
        json.dump(design, f, indent=1)
    with (out / "adapter_config_study2.json").open("x") as f:
        json.dump({"timeout_s": 120, "run_timeout_s": 120}, f)
    print(table, len(conds), "conditions x", n_blocks, "blocks")


if __name__ == "__main__":
    a = sys.argv[1:]

    def opt(flag, default=None):
        return a[a.index(flag) + 1] if flag in a else default

    main(a[0], a[1], a[2], a[3], a[4], a[5], opt("--reference", "STATIC_G_edges_features"), opt("--e2e"),
         opt("--only").split(",") if opt("--only") else None, opt("--min-free-ram", 1.2), "--late" in a)
