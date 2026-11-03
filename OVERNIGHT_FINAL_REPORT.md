# Overnight sprint: final report (started 2026-10-26 22:39; this machine)

Nothing was committed to Git; no existing result, design or document was overwritten (checks: `git status` snapshot `data/results/overnight_20261027/snapshot/git_status.txt`; backups of five of the six edited tracked files in `snapshot/*.orig`; `tests/test_remote.py` only gained one appended test and is recoverable from `git diff`). All new evidence is under `data/results/overnight_20261027/` (log: `ACTIVITY_LOG.md`). Evidence labels: real = this laptop; emulation = loopback remote node behind a delay shim; plan = not run.

## 1. Executive status
- The headline result reproduces and generalises to chain orders never used before, on this machine and this workload family: the learned scheduler `PRED_RANK_GREEDY` has a makespan about 19% to 21% shorter than blind greedy B4 (exploratory sessions: -19.32% on 6P+7E over 12 new orders, -20.45% on 2P+7E over 8 new orders; faster in 20 of 20 orders). It is level with the informed hand rule `B4_param_first` (+0.66% and +0.27%), not better. The gain exists only when the hidden cost ratio is large (about 60x here; at 3x to 20x it is small, 1% to 3%) and it depends on how many chains are heavy (about 27% with 4 or 8 of 64 heavy, about 19% to 20% with 16, about 4% with 40).
- The gain is not a scheduling-overhead artefact: a decision-preserving fix of an inefficiency in the dispatch loop (found and explained; coordinator time 0.197 s to 0.008 s for B4) changes PRED's gain by 0.8 percentage points.
- Remote offloading is **not established**: in emulation the predictive policy gets no benefit from a remote worker even at a compute-heavy level, although its predictions for remote placements are accurate. The Raspberry Pi and real-network claims are untested; a runbook and a rehearsed external-node code path exist.
- Local CPU/GPU: task-level GPU speed-ups are real (up to about 15x for `img_edges` at 1024 px); a workflow-level scheduling benefit from CPU/GPU placement is not established.
- The faculty demo path (dashboard side-by-side B4 vs PRED, stored evidence, optional 6-minute live reproduction) is checked and written down.

## 2. Code changes (all uncommitted; backups in `snapshot/*.orig`)
| file | change | justification (verified before editing) | tests |
|---|---|---|---|
| `src/caosched/experiment/remote_adapter.py` | `RemoteAdapter(remote_host, remote_port)`: connect to an already running node; label `real` only for a non-loopback host, `emulation` for loopback; a delay shim on a real host is refused; extra fields in the run record | the adapter could only spawn the node on this machine (`_get_pool` always built `RemoteSlot(node_core=...)`): a Pi run was impossible | `tests/test_remote_adapter.py`: external loopback node run (verified output, label, tasks on R), non-loopback host label and shim refusal, reconnect of a second pool; 22 tests of `test_remote*.py` passed |
| `src/caosched/remote/node.py` | `--persistent` (`serve(persistent=True)`): keep serving after a client says bye or disconnects | first loopback rehearsal failed: the node exits after one client, the runner builds a new pool per run, runs 2 to 25 died with `Worker(s) died during startup: ['R0']` (kept: `phase4/rehearsal_sessions/rehearsal_loopback`) | `tests/test_remote.py::test_persistent_node_serves_a_second_client_after_bye` |
| `scripts/calibrate_link.py` | `--remote-host/--remote-port` (measure an external node), `--denoise-iterations` (measure R rows at the experiment's level); profile records host, level and label | `measure()` built the pipeline with the default level 1, so R rows for a compute-heavy level were wrong; no way to target a Pi | `test_calibrate_link_carries_the_denoise_iterations_to_the_measured_task` (+ existing calibration test) |
| `scripts/make_pi_design.py` (new) | design + adapter config for the real-device experiment | needed by the runbook | `test_make_pi_design_writes_design_and_adapter_config`; also exercised by the loopback rehearsal |
| `docs/research_redesign/claims.json` | 20 descriptive claims O1 to O20 appended (values read from the analysis files; no existing claim changed, `git diff` shows 0 deletions in this file) | registry convention | `tests/test_claims.py` 51 passed |
No change to the scheduler, estimator, coordinator or the registered designs. A found inefficiency (idle CUDA worker defeats the dispatch loop's early exit) was **not** fixed in the source; the fix is in `phase3d/cao_overnight_adapter.py` for the A/B only.

## 3. Tests and experiments (exit status, failures included)
| item | result | path |
|---|---|---|
| Full test suite before any change | 472 passed, exit 0 (236 s) | `tests/full_suite.txt` |
| Full test suite after code changes (intermediate) | 476 passed | `tests/full_suite_after_changes.txt` |
| Full test suite final | **488 passed**, exit 0 (244 s), run before claims O12 to O20 were added (`tests/test_claims.py` alone: 51 passed afterwards); focused `test_remote*.py` 22 passed | `tests/full_suite_final.txt` |
| Evidence verification of the demo and registered sessions | all runs ok, event-log hashes match, design hash matches; numbers you reported match `effects.csv` | `phase1/session_verification.json`, `PHASE1_FINDINGS.md` |
| Scheduling-overhead discrepancy | explained (two metric definitions + idle CUDA worker), instrumented run | `phase1/diag_run2/diag_sched_time.json` (first attempt `diag_run` FAILED: spawn without a `__main__` guard; kept) |
| Unseen orders 6P+7E (12 orders, 37 blocks) | complete, 148 of 148 runs ok and verified; PRED -19.32% | `phase3/` |
| Unseen orders 2P+7E (8 orders, 25 blocks) | complete, 100 of 100 ok; PRED -20.45% | `phase3b/` |
| Dose-response, 4 levels (4 orders, 13 blocks each) | 4 of 4 complete, 208 runs ok | `phase3c/` |
| Dispatch-loop fix A/B (4 orders, 13 blocks) | complete, 78 of 78 ok | `phase3d/` (smoke session `phase3d/smoke_sessions/smoke1`, not evidence) |
| HEFT/PEFT/rank-EFT vs PRED on 6 unseen orders (25 blocks); dose follow-up L=15 and L=40 with 8 new orders each (25 blocks) | 3 of 3 complete, 150 + 100 + 100 runs ok; first reproduce_subset attempt FAILED (exit 1) because the session manifests did not exist yet (a missing manifest is a failed check; log kept as `repro_*.json`); rerun after the manifests: 6 of 6 exit 0 (`repro2_*.json`) | `phase3e/` |
| Heavy-chain count 4, 8, 40 of 64 (4 new orders, 13 blocks each) | 3 of 3 complete, 156 runs ok, reproduce_subset exit 0 x6 | `phase3g/` |
| Emulated remote pool at denoise level 30 (13 blocks) | complete, 65 of 65 ok; remote did not help | `phase4/e3_sessions/e3_remote_it30` |
| Loopback rehearsal of the Pi runbook chain | attempt 1 FAILED (node exits after one client), attempt 2 (persistent node) 25 of 25 ok, label `emulation` | `phase4/rehearsal_sessions/` |
| Dashboard live check | all APIs 200; side-by-side B4 vs PRED view works | `phase5/dashboard_check.txt`, `dashboard_ui_check.md` |
| Blocked action | an attempt to start a background script with `-ExecutionPolicy Bypass` was refused by the safety classifier; I ran the script by a plain call instead; no policy was changed | `ACTIVITY_LOG.md` |
`reproduce_subset.py` (tables re-derived from the raw logs, event-log and manifest hashes checked) exited 0 for every analysis: phase3 x2, phase3b x2, dose x8, phase3d x2, phase3e x6 (after the manifests existed; see the failed first attempt above).

## 4. Strongest independently verified result and how it was verified
Hidden-cost workload (64 image chains, 16 of them 60x heavier in one parameter), 6P+7E: PRED versus B4 -19.32% [-20.04,-18.59] on 36 paired blocks over 12 chain orders not used before, PRED faster in every order (exploratory, plan and design hash written before the run; `phase3/analysis_ref_B4`, per-order file `phase3/per_order_summary.csv`). Verification: the session's 148 runs all verified against the CPU reference output, event-log hashes match, design hash matches, the analysis re-derived from raw logs (`phase3/repro_analysis_ref_B4.json`, exit 0), and it agrees with the registered sessions (-20.39% and -21.10%) and with the reproduction (-21.79%). Hand rule -19.85%; PRED vs hand rule +0.66% [-0.23,+1.54].
The effect applies only to this workload family, these two core configurations and this machine; it is not a universal 21%.

## 5. Generalisation, CPU/GPU and remote status
- Chain-order generalisation: **supported** for this family (criteria written beforehand: interval below zero and PRED faster in at least 10 of 12 and 7 of 8 orders: met, 12 of 12 and 8 of 8). Workload-family generalisation: **not established**; dose-response (heavy:light cost ratio 3, 7.5, 20, 60): PRED -2.60%, +0.57% (not significant), -6.10%, -19.86%; the non-monotone point at 7.5x did not survive a follow-up with 8 further orders (L=15: -1.31% [-2.56,-0.10]; L=40: -2.89% [-4.34,-1.42], earlier -6.10%): the gain is small (about 1% to 3%) up to about 20x and large only near 60x.
- Dependence on the number of heavy chains (exploratory, 4 new orders each): PRED versus B4 -27.65% [-33.97,-18.73] with 4 of 64 heavy, -26.76% with 8, about -19% to -20% with 16, -3.81% with 40; the hand rule is within about 1.4 points of PRED each time. So the gain is largest with few heavy chains and shrinks as heavy chains become the majority; with 4 or 8 heavy chains static P-only even beats blind B4.
- Versus HEFT and PEFT with the same learned model (6 further unseen orders, exploratory): PRED -18.97%, hand rule -19.27%, HEFT -18.08%, rank-EFT -13.21%, PEFT -2.58% versus B4; HEFT versus PRED +1.10% [-0.53,+2.81] (not distinguishable), PEFT +20.23%, rank-EFT +7.11%. Consistent with an earlier development session on older code (HEFT -17.9%, PEFT -3.9%).
- CPU/GPU: task-level speed-up established; end-to-end scheduling benefit from CPU/GPU placement **not established**; GPU-contention opportunity **not established** (earlier Phase 1); the overnight work did not touch the GPU.
- Remote offloading: emulated at denoise level 30: EFT with the remote worker +3.78% [+2.27,+5.58] versus without it; blind B4 with the remote worker -1.46% versus EFT without it (not significant). Predicted exec 0.1457 s versus measured 0.1464 s and predicted transfer 0.0937 s versus 0.0943 s (44 placements): accurate predictions, no end-to-end gain. Hypothesis not tested: the proxy shares the coordinator core. **Established: transfer-aware placement avoids the harm of blind remote placement (level 1, slow link). Not established: any offloading benefit. Contradicted: that a remote worker at E-core speed helps EFT here.** Real network and Raspberry Pi: untested.

## 6. Features ready for demonstration
Ready: dashboard tab 5 side-by-side comparison of B4 and PRED runs (output hash match, placement, scheduling time); stored evidence and plots; reproduction from raw logs; optional 6-minute live reproduction. Not checked: dashboard tabs 1 to 4 interaction, the "Live execution" button. Not ready: anything involving the Pi or a real network. Details: `FACULTY_DEMO_CHECKLIST.md`, `FACULTY_DEMO_SCRIPT.md`, `FEATURE_VERIFICATION_MATRIX.csv`.

## 7. Limitations that matter
1. The hidden-cost workload is designed; it shows when prediction or knowledge helps, not how common that is.
2. Sessions have different source hashes (`f27b56f3`, `41a8f43b` before the code changes, `ed70c36d` after) and a dirty working tree; they are never pooled in an analysis. The code changes of this sprint do not touch the study 2 code path (they touch `remote_adapter.py` and `node.py`), but the hash differs.
3. The overnight sessions are exploratory (the analysis tool labels the primary family "confirmatory" by default; the plans say exploratory).
4. Coordinator scheduling time is 2% to 5% of makespan for the late-binding policies (open inefficiency; fix proposed, worth 1% to 2% of makespan).
5. The first run after the CPU reference computation of a new order is about 2% slower (11 cases).
6. Remote results are emulation: one local E core behind a loopback socket and a delay shim.
7. HEFT/PEFT implementations follow secondary descriptions; originals not read; literature check bounded (`RESEARCH_CLAIMS_AND_LIMITATIONS.md`, section D).
8. The learned model was fitted at L=2 and 120; levels 6, 15, 40 are interpolation.

## 8. Unresolved defects and decisions for you
- Decide whether to apply the dispatch-loop fix in `src/caosched/core/coordinator.py` (it changes timing for every policy; the A/B shows a 1% to 2% makespan effect).
- Decide whether to commit: the working tree holds about 90 uncommitted paths (git status lines); I committed nothing and did not tidy Git.
- Pi: the plan assumes a wired link and a Pi with Python 3.11; neither is known.

## 9. Paths
Reports (root): `OVERNIGHT_FINAL_REPORT.md`, `RESULTS_TABLE.csv`, `FEATURE_VERIFICATION_MATRIX.csv`, `FACULTY_DEMO_CHECKLIST.md`, `FACULTY_DEMO_SCRIPT.md`, `RASPBERRY_PI_VALIDATION_RUNBOOK.md`, `RESEARCH_CLAIMS_AND_LIMITATIONS.md`, `PAPER_OUTLINE.md`, `EVIDENCE_INDEX.md`, `CAO_HANDOFF_AUDIT.md` (with addendum). Evidence: `data/results/overnight_20261027/` (`phase1` findings and diagnostics, `phase3` and `phase3b` unseen orders, `phase3c` dose-response, `phase3d` dispatch-fix A/B, `phase3e` HEFT/PEFT and dose follow-up, `phase3g` heavy-chain count, `phase4` remote emulation and rehearsal, `phase5` dashboard, `tests`, `snapshot`). Plots: `phase3/analysis_ref_B4/fig_*.png` and the same in every analysis folder. Logs: `ACTIVITY_LOG.md`, `*/run*.stdout.txt`.

## 10. First two hours after the Raspberry Pi arrives
1. Hour 1 (`RASPBERRY_PI_VALIDATION_RUNBOOK.md` steps 1 to 4): record device and OS, connect by cable, check ping and optionally iperf3, create the venv and install numpy, Pillow, psutil, copy `src` and `pyproject.toml`, `pip install -e . --no-deps`, start the node with `--persistent` and a token, check the handshake from the laptop.
2. Hour 1 to 2 (step 5): laptop base profile at `--denoise-iterations 1`, then `calibrate_link.py --remote-host <PI_HOST> --remote-port <PI_PORT>`; read the first real numbers from `pi_profile_raw.csv`: Pi kernel time versus the laptop E core, payload size, transfer time. Repeat for level 30.
3. Then step 8 for level 1 (13 blocks x 5 conditions), with `vcgencmd` temperature and throttling recorded before and after. Decide from the decision rule in step 10; if the Pi kernel time is more than an order of magnitude slower than a laptop E core, record it as the result.
