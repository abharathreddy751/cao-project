"""Write the design + adapter config of the REAL-DEVICE remote experiment (Raspberry Pi or any other host running the node).

  python scripts/make_pi_design.py <out_dir> <calibrated_profile.json> --host <HOST> --port <PORT> [--n-blocks 12]
         [--denoise-iterations 1] [--name NAME] [--seed N]

Same workload and pools as the emulated experiment (``make_remote_design.py``: image pipeline, tile 512, 16 branches, 2 P + all E cores
locally, remote-eligible stages denoise/edges/features) but the remote pool 'R' is a node that ALREADY RUNS on another machine
(``RemoteSlot(host, port)``), the link shim is ZERO and the real network supplies the delay. Unlike the emulated experiment no local
E core is given to the node, so remote conditions add capacity relative to the controls.
Evidence label: 'real' for a non-loopback host; the adapter stamps 'emulation' when the host is a loopback address (a local rehearsal).

Conditions: B0_P_only, B4_no_remote, EFT_E1_no_remote (reference), B4_remote, EFT_E1_remote. ``profile`` must have P, E and R rows at the tile
AND ``link_calibration`` measured through the real link (``scripts/calibrate_link.py --remote-host ...``), produced for the SAME
``--denoise-iterations`` as used here. Nothing is measured here; the design only records what it is given. Exclusive create.
"""
import argparse
import json
import sys
from pathlib import Path

from caosched.apps.stages import stage_payload_bytes

TILE, N_IMAGES = 512, 16
STAGES = ("img_denoise", "img_edges", "img_features")


def profile_check(path: Path, iterations: int) -> dict:
    p = json.loads(path.read_text(encoding="utf-8"))
    have = {(e["workload"], e["size"], e["pool"]) for e in p["entries"]}
    need = {(s, TILE * TILE, q) for s in STAGES for q in ("P", "E", "R")}
    if need - have:
        raise SystemExit(f"{path}: missing profile rows {sorted(need - have)}")
    cal = p.get("link_calibration")
    if not cal:
        raise SystemExit(f"{path}: no link_calibration (run scripts/calibrate_link.py --remote-host ...)")
    kern = {e["workload"]: e["median_s"] for e in p["entries"] if e["pool"] == "R" and e["size"] == TILE * TILE}
    out = {}
    for s in STAGES:
        up, down = stage_payload_bytes(s, TILE * TILE)
        tr = cal["socket_a_s"] + cal["socket_b_s_per_byte"] * (up + down)
        out[s] = {"modelled_transfer_s": tr, "R_kernel_s": kern[s], "transfer_over_R_kernel": tr / kern[s]}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("profile")
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--n-blocks", type=int, default=12)
    ap.add_argument("--denoise-iterations", type=int, default=1)
    ap.add_argument("--name", default="pi_remote_confirm")
    ap.add_argument("--seed", type=int, default=20261201)
    a = ap.parse_args(argv)
    profile_path = Path(a.profile).resolve()
    check = profile_check(profile_path, a.denoise_iterations)
    base = {"tile": TILE, "n_images": N_IMAGES, "seed": 0, "denoise_iterations": a.denoise_iterations, "profile": str(profile_path),
            "remote_stages": list(STAGES)}

    def cond(name, policy, remote=False):
        return {"name": name, "policy": policy, "estimator": None, "workload": {"kind": "remote_image"},
                "kwargs": {**base, "remote": remote, **({"link": {"name": "real"}} if remote else {})}}

    conds = [cond("B0_P_only", "B0_P_only"), cond("B4_no_remote", "B4_greedy_eligible"), cond("EFT_E1_no_remote", "EFT_E1"),
             cond("B4_remote", "B4_greedy_eligible", True), cond("EFT_E1_remote", "EFT_E1", True)]
    design = {"name": a.name, "evidence_label": "real", "seed": a.seed, "n_blocks": a.n_blocks, "instances": [None],
              "warmup_blocks": 1, "min_free_ram_gb": 2.0, "reference": "EFT_E1_no_remote", "run_timeout_s": 900,
              "analysis_plan": {"profile_check": check, "denoise_iterations": a.denoise_iterations,
                                "decision_rule": "remote helps: 95% CI of EFT_E1_remote vs EFT_E1_no_remote entirely below 0 (Holm p < 0.05); "
                                                 "no measurable advantage: interval includes 0; too costly: interval entirely above 0",
                                "note": "no threshold is derived from the data; the profile_check ratios are recorded, not used for exclusion"},
              "conditions": conds}
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "design_pi.json").open("x") as f:
        json.dump(design, f, indent=1)
    with (out / "adapter_config_pi.json").open("x") as f:
        json.dump({"timeout_s": 300, "run_timeout_s": 900, "max_p_slots": 2, "remote_host": a.host, "remote_port": a.port}, f)
    print(f"{len(conds)} conditions x {a.n_blocks} blocks (block 0 = warm-up); host {a.host}:{a.port}; transfer/R-kernel: "
          + ", ".join(f"{s}={v['transfer_over_R_kernel']:.2f}" for s, v in check.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
