"""Final study: write the calibration, hold-out and evaluation designs. Files are created exclusively (never overwritten).

  python scripts/final_make_designs.py calibration <out_dir>
  python scripts/final_make_designs.py evaluation  <out_dir> <param_model.json> <e2e_terms.json> <oracle_dir> [workload ...]

Resource configurations (suffix of the condition name):
  _cpu  P+E only: no CUDA stage is GPU-eligible (the idle CUDA worker stays in the pool, as in every registered Study 2 session)
  _gpu  P+E+G, STRICT: GPU eligibility only for stages/parameters that PASS in the ORIGINAL recorded spike
        (hidden-cost workload: img_edges, img_features at 512 px; uniform workload: also img_denoise with 8 iterations)
  _ext  P+E+G, EXTENDED: additionally img_denoise for the iteration counts that PASS in the new record written by
        scripts/final_gpu_spike_iters.py (per task, through final.gpu_region)
Policies per configuration: STATIC  HEFT_param_model, PEFT_param_model, HEFT_E2E, HEFT_ORACLE_REF (reference only)
                            DYNAMIC B4, B4_param_first, PRED_RANK_GREEDY, PRED_RANK_GREEDY_E2E
B4 and B4_param_first use the pool priority G, P, E when G exists (as the registered revival_uniform2 design), else P, E.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = str(ROOT / "data/results/study2_20261024/profile_t512/20261024T001156_profile.json")
SPIKE_ORIG = str(ROOT / "data/results/stage1_20261011/gpu/gpu_spike.json")
STRICT_HIDDEN = {"img_denoise": False, "img_edges": True, "img_features": True}
ALL3 = {"img_denoise": True, "img_edges": True, "img_features": True}
CAL_ORDERS = {"cal_a": 9101, "cal_b": 9102}
HOLD_ORDERS = {"hold_a": 9201, "hold_b": 9202}
EVAL_ORDERS = {"ord_a": 9301, "ord_b": 9302, "ord_c": 9303, "ord_d": 9304}
# workload -> (kind, kwargs); counts are [light, heavy] chains of 64, iterations [light, heavy]
WORKLOADS = {
    "h16_l120": {"iters": {"small": [48, 2], "big": [16, 120]}},
    "h04_l120": {"iters": {"small": [60, 2], "big": [4, 120]}},
    "h40_l120": {"iters": {"small": [24, 2], "big": [40, 120]}},
    "h16_l15": {"iters": {"small": [48, 2], "big": [16, 15]}},
    "h16_l40": {"iters": {"small": [48, 2], "big": [16, 40]}},
    "uniform": {"k": 64, "denoise_iterations": 8},
}
BLOCKS = {"h16_l120": 25}  # the primary workload gets more blocks; every other session 13 (block 0 = warm-up)
DESIGN_SEED = {"h16_l120": 20261101, "h04_l120": 20261102, "h40_l120": 20261103, "h16_l15": 20261104, "h16_l40": 20261105,
               "uniform": 20261106}


def _write(path: Path, d: dict) -> None:
    with path.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(d, indent=1))
    print("wrote", path)


def _base(workload: str, orders: dict | None) -> tuple[dict, dict]:
    w = WORKLOADS[workload]
    kind = {"workload": {"kind": "study2_batch" if "k" in w else "study2_iters"}}
    kw = {"tile": 512, "seed": 0, "profile": PROFILE, **w}
    if orders and "iters" in w:
        kw["order_seeds"] = orders
    return kind, kw


def calibration(out: Path) -> None:
    ext_region = sorted((ROOT / "data/results/final_20261101/gpu_spike_iters").glob("spike_*/gpu_spike.json"))
    assert len(ext_region) == 1, "expected exactly one extended GPU spike record"
    region = [SPIKE_ORIG, str(ext_region[0])]
    out.mkdir(parents=True, exist_ok=True)
    seed0 = 20261110
    for i, (name, orders, nblocks, levels) in enumerate((("cal", CAL_ORDERS, 9, (15, 40, 120)), ("hold", HOLD_ORDERS, 7, (40, 120)))):
        for L in levels:
            wl = {"iters": {"small": [48, 2], "big": [16, L]}}
            kind, kw = {"workload": {"kind": "study2_iters"}}, {"tile": 512, "seed": 0, "profile": PROFILE, **wl, "order_seeds": orders}

            def cond(cname, policy, **extra):
                return {"name": cname, "policy": policy, "estimator": None, **kind, "kwargs": {**kw, **extra}}
            conds = [cond("random_gpu", "random", gpu_stage_table=STRICT_HIDDEN),
                     cond("random_ext", "random", gpu_stage_table=ALL3, gpu_region=region)]
            if name == "cal":
                conds.append(cond("B0_E_only_cpu", "B0_E_only"))
            _write(out / f"design_final_{name}_l{L}.json", {
                "name": f"final_{name}_l{L}", "evidence_label": "real", "seed": seed0 + 10 * i + L % 7, "n_blocks": nblocks,
                "instances": list(orders), "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True,
                "reference": conds[0]["name"], "conditions": conds})
    kind, kw = _base("uniform", None)
    conds = [{"name": "random_gpu", "policy": "random", "estimator": None, **kind, "kwargs": {**kw, "gpu_stage_table": ALL3}},
             {"name": "B0_E_only_cpu", "policy": "B0_E_only", "estimator": None, **kind, "kwargs": dict(kw)}]
    _write(out / "design_final_cal_uniform.json", {
        "name": "final_cal_uniform", "evidence_label": "real", "seed": 20261120, "n_blocks": 9, "instances": [None],
        "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True, "reference": "random_gpu", "conditions": conds})


def evaluation(out: Path, param_model: str, e2e: str, oracle_dir: str, which: list[str]) -> None:
    ext_region = sorted((ROOT / "data/results/final_20261101/gpu_spike_iters").glob("spike_*/gpu_spike.json"))
    region = [SPIKE_ORIG, str(ext_region[0])]
    pm, terms = str(Path(param_model).resolve()), str(Path(e2e).resolve())
    out.mkdir(parents=True, exist_ok=True)
    for workload in which or WORKLOADS:
        kind, kw = _base(workload, EVAL_ORDERS)
        uniform = workload == "uniform"
        cfgs = {"cpu": {}, "gpu": {"gpu_stage_table": ALL3 if uniform else STRICT_HIDDEN}}
        if not uniform:
            cfgs["ext"] = {"gpu_stage_table": ALL3, "gpu_region": region}
        conds = []
        for cfg, extra in cfgs.items():
            prio = {"priority": ["G", "P", "E"]} if cfg != "cpu" else {}
            b4cfg = {"policy_cfg": {"B4_greedy_eligible": {"priority": ["G", "P", "E"]}}} if cfg != "cpu" else {}
            orc = str(Path(oracle_dir).resolve() / f"oracle_rows_{workload}_{cfg}.json")

            def cond(name, policy, **more):
                return {"name": f"{name}_{cfg}", "policy": policy, "estimator": None, **kind,
                        "kwargs": {**kw, **extra, **more}}
            conds += [cond("HEFT_param_model", "EFT_E1", binding="param_model_heft", param_model=pm),
                      cond("PEFT_param_model", "EFT_E1", binding="param_model_peft", param_model=pm),
                      cond("HEFT_E2E", "EFT_E1", binding="heft_e2e", param_model=pm, e2e_terms=terms),
                      cond("HEFT_ORACLE_REF", "EFT_E1", binding="heft_oracle", oracle_rows=orc),
                      cond("B4", "B4", **b4cfg),
                      cond("B4_param_first", "B4", binding="param_first", **prio),
                      cond("PRED_RANK_GREEDY", "EFT_E1", binding="pred_rank_greedy", param_model=pm),
                      cond("PRED_RANK_GREEDY_E2E", "EFT_E1", binding="pred_rank_greedy_e2e", param_model=pm, e2e_terms=terms)]
        _write(out / f"design_final_eval_{workload}.json", {
            "name": f"final_eval_{workload}", "evidence_label": "real", "seed": DESIGN_SEED[workload],
            "n_blocks": BLOCKS.get(workload, 13), "instances": list(EVAL_ORDERS) if "iters" in WORKLOADS[workload] else [None],
            "warmup_blocks": 1, "min_free_ram_gb": 0.8, "require_ac_power": True, "reference": "B4_cpu", "conditions": conds})


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "calibration":
        calibration(Path(a[1]))
    elif a[0] == "evaluation":
        evaluation(Path(a[1]), a[2], a[3], a[4], a[5:])
    else:
        sys.exit(__doc__)
