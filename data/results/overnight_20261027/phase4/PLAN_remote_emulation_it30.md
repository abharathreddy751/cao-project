# Phase 4 plan: emulated remote pool at a compute-heavy level (EXPLORATORY, label emulation; written before the run)

Question: the registered emulated-remote session of 2026-10-13 (denoise level 1) found no benefit of a remote worker for the predictive policy (EFT_E1_remote vs EFT_E1_no_remote: +0.14% on fast_lan, +0.32% on slow_wan; blind B4 on slow_wan +31%) and the design's own profile check shows transfer time about as long as the remote kernel time even on the fast link (ratio 0.59 to 0.83 per stage). Does a compute-heavy level (denoise level 30, which multiplies the denoise compute but not the bytes moved) change that?

This is NOT a real-network or Pi test: the remote worker is a node process pinned to one local E core behind a loopback socket and a delay shim; its capacity is one E core that is taken out of the local E pool in every condition (idle in the controls).

Fixed before running:
- Workload: image pipeline, tile 512, 16 branches (68 tasks), `denoise_iterations` 30 (the level was chosen as the order of magnitude of the heavy chains of the hidden-cost workload; not tuned), remote-eligible stages denoise, edges, features, 2 P + 6 E locally + R.
- Profile: P and E rows from `profile_gpu_workload.py --denoise-iterations 30 --no-gpu`, R rows and the loopback socket calibration from `calibrate_link.py --denoise-iterations 30` (the option added today; before that the R rows could only be measured at level 1).
- Conditions (5): B4_no_remote, EFT_E1_no_remote (reference), B4_remote_fast_lan, EFT_E1_remote_fast_lan, EFT_E1_remote_slow_wan. Links as in the registered design (fast_lan 0.2 ms, 1000 Mbit/s, 0.05 ms per message; slow_wan 30 ms, 20 Mbit/s, 0.1 ms). B0_P_only and B4_remote_slow_wan of the registered design are omitted to save time (B4 on the slow link was already shown harmful); declared, not outcome-based.
- 13 blocks, block 0 is a warm-up (excluded by the design rule), seed 20261029, each run in its own child process with the 900 s timeout (as the registered design), memory preflight 2.0 GB.
- Analysis: `analyze_experiment.py --reference EFT_E1_no_remote` and `--reference B4_no_remote`, Holm over the conditions; report `tasks_per_pool`, `transfer_total_s`, per-dispatch and coordinator scheduling times.
- Decision rule: remote "helps" if the 95% interval of EFT_E1_remote_fast_lan versus EFT_E1_no_remote is entirely below 0; "no measurable advantage" if it includes 0 (equivalence only if inside +-2%); "costs" if entirely above 0. Same rule for the slow link.
- Run once. A failed run stays in the data. If the session aborts for an environment fault (preflight), one retry under a new session id with the same design.
