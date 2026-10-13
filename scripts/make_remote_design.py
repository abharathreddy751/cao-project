"""Write the pre-registerable design of the EMULATED remote-pool experiment (label 'emulation'). Exclusive create.

  python scripts/make_remote_design.py <out_dir> <calibrated_profile.json> [n_blocks]

Workload: the image pipeline at tile 512, 16 branches (2048 x 2048 source, 68 tasks); remote-eligible stages: denoise, edges,
features (the stages whose input/output sizes the payload model knows). Why tile 512: transfer must be a visible share of a task
or placement cannot be transfer-aware in any testable way. For these O(pixels) stages bytes moved and compute both grow with the
pixel count, so the transfer/compute ratio is set mainly by the link, not the tile; a larger tile than the 64-256 of the unit tests
keeps the shim's fixed per-message cost and the scheduler's per-decision cost small relative to a task (intended, to be confirmed
by ``profile_check``), and 16 branches give a DAG wide enough for the 2 P + 6 E pool to be scarce. These are design reasons, not measurements: whether transfer matters is shown by
``profile_check`` (written into the design from the calibrated profile: modelled round-trip transfer / R kernel time per stage
and link) and later by the measured transfer share in the analysis.

Conditions (one pool for all: 2 P + 6 E + R, R on the last E core of the topology; 'no remote' = R ineligible, so the node core is idle):
  B0_P_only, B4_no_remote, EFT_E1_no_remote (reference), and, for each of two emulated link settings,
  B4_remote_<link> (priority P, E, R) and EFT_E1_remote_<link> (E1 + FileTransferModel with the profile's link calibration).
The two links are EMULATED LABELS (numbers given to the shim), not measurements of any real network.
"""
import json
import sys
from pathlib import Path

from caosched.apps.stages import stage_payload_bytes
from caosched.experiment.remote_adapter import link_from_kwargs

TILE, N_IMAGES = 512, 16
STAGES = ("img_denoise", "img_edges", "img_features")
# one-way delay per message (the shim applies it to every message, each direction); Mbit/s = bandwidth
LINKS = {"fast_lan": {"name": "fast_lan", "latency_ms": 0.2, "bandwidth_mbps": 1000.0, "per_message_ms": 0.05, "jitter_ms": 0.0},
         "slow_wan": {"name": "slow_wan", "latency_ms": 30.0, "bandwidth_mbps": 20.0, "per_message_ms": 0.1, "jitter_ms": 0.0}}


def check_profile(path: Path) -> dict:
    p = json.loads(path.read_text(encoding="utf-8"))
    have = {(e["workload"], e["size"], e["pool"]) for e in p["entries"]}
    need = {(s, TILE * TILE, q) for s in STAGES for q in ("P", "E", "R")}
    if need - have:
        raise SystemExit(f"{path}: missing profile rows {sorted(need - have)} (run scripts/calibrate_link.py)")
    cal = p.get("link_calibration")
    if not cal:
        raise SystemExit(f"{path}: no link_calibration (run scripts/calibrate_link.py)")
    kern = {e["workload"]: e["median_s"] for e in p["entries"] if e["pool"] == "R" and e["size"] == TILE * TILE}
    out = {}
    for lname, l in LINKS.items():  # same formula as FileTransferModel.estimate
        link = link_from_kwargs(l)
        for s in STAGES:
            up, down = stage_payload_bytes(s, TILE * TILE)
            tr = link.shim_delay(up) + link.shim_delay(down) + cal["socket_a_s"] + cal["socket_b_s_per_byte"] * (up + down)
            out[f"{lname}/{s}"] = {"modelled_transfer_s": tr, "R_kernel_s": kern[s], "transfer_over_kernel": tr / kern[s]}
    return out


def main(out_dir: str, profile: str, n_blocks: int = 12, name: str = "remote_emulation_confirm", seed: int = 20261104) -> None:
    profile_path = Path(profile).resolve()
    profile_check = check_profile(profile_path)
    base = {"tile": TILE, "n_images": N_IMAGES, "seed": 0, "denoise_iterations": 1, "profile": str(profile_path),
            "remote_stages": list(STAGES)}

    def cond(cname, policy, link=None):
        k = {**base, "remote": link is not None, **({"link": LINKS[link]} if link else {})}
        return {"name": cname, "policy": policy, "estimator": None, "workload": {"kind": "remote_image"}, "kwargs": k}

    conds = [cond("B0_P_only", "B0_P_only"), cond("B4_no_remote", "B4_greedy_eligible"), cond("EFT_E1_no_remote", "EFT_E1")]
    for link in LINKS:
        conds += [cond(f"B4_remote_{link}", "B4_greedy_eligible", link), cond(f"EFT_E1_remote_{link}", "EFT_E1", link)]
    reference = "EFT_E1_no_remote"
    m = len(conds) - 1  # confirmatory family: every other condition vs the reference (analysis/stats_paired.py)
    thr = 0.05 / m
    n_min = next(n for n in range(1, 64) if 2 / 2 ** n < thr)
    plan = {"family": f"{m} makespan contrasts vs {reference}, Holm-adjusted sign-flip p (analysis/stats_paired.py)",
            "holm_smallest_threshold": thr, "min_attainable_p_at_n_blocks": 2 / 2 ** n_blocks,
            "smallest_n_blocks_with_min_p_below_threshold": n_min,
            "blocks_that_may_be_lost_to_exclusion": n_blocks - n_min,
            "pre_stated_directions": [
                "D1 (mechanism): on slow_wan, B4_remote is slower than B4_no_remote (exploratory contrast, --reference B4_no_remote).",
                "D2 (mechanism): EFT_E1_remote places fewer tasks on R on slow_wan than on fast_lan (descriptive, tasks_per_pool).",
                "D3: no direction is predicted for EFT_E1_remote_fast_lan vs EFT_E1_no_remote (one extra worker behind a link).",
                "Wording per prediction: supported / not supported / not resolved by this design. No other claim is confirmatory."],
            "profile_check": profile_check, "links_note": "emulated labels given to the loopback shim, not measurements of a real network; no jitter"}
    design = {"name": name, "evidence_label": "emulation", "seed": seed, "n_blocks": n_blocks, "instances": [None],
              "warmup_blocks": 0, "min_free_ram_gb": 2.5, "reference": reference, "run_timeout_s": 900, "links": LINKS,
              "analysis_plan": plan, "conditions": conds}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "design_remote.json").open("x") as f:
        json.dump(design, f, indent=1)
    with (out / "adapter_config_remote.json").open("x") as f:
        json.dump({"timeout_s": 300, "run_timeout_s": 900, "max_p_slots": 2}, f)
    print(f"{len(conds)} conditions x {n_blocks} blocks; Holm threshold {thr:.5f}, min p {2 / 2 ** n_blocks:.6f}, n_min {n_min}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
