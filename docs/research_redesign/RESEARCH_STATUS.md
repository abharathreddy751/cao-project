# Research status

Date: 2026-10-14. State: **Stages 1-4 executed on this machine and the confirmatory sessions run and analysed (408 runs, all verified, 0 failed gate checks); the first-round Stage 4 sessions are the PILOT. Result: a confirmed null (section "Confirmatory sessions report" below; details in `FINAL_REPORT.md`). Open items: six, listed at the end of that section.** Older sections below are history (2026-10-11 and 2026-10-12) unless marked.

## Verified current state

| Item | Verified how | Result |
|---|---|---|
| Git | `git status`, `git log` | Branch `main`, HEAD `7651eca` ("Stage 0: SHA-256 manifest..."); previous commit `c23a96e` |
| Uncommitted work | `git status` | Modified: `src/caosched/estimators/__init__.py`, `src/caosched/estimators/learned.py`, `tests/test_estimators.py`. Untracked: `PROGRESS.md`. This task did not stage or change them |
| E4 profile-mismatch fix | `PROGRESS.md`; earlier diff review | Implemented, reported as 56 focused tests passing on the earlier machine, **not committed**, tests not re-run here |
| Machine | PowerShell queries, 2026-10-11 | i5-13500HX, 15.7 GB RAM, NVIDIA RTX 3050 6 GB Laptop GPU, driver 581.83 |
| Historical machine | `data/environment/env_20261002T223753.json` | i5-1235U, 8.25 GB, 2P+8E, Intel UHD. All recorded experiments come from it |
| Toolchain on this machine | PowerShell | No WSL; no `nvcc`, `gcc` or `gfortran` on PATH; `python` is the Windows Store stub; `.venv` points to a deleted `C:\Program Files\Python311` |
| Audit report | `Test-Path` | `D:\cao_records` and `D:\cao_backups` do not exist on this machine; the audit text was not available |
| Survey workbook | file search | `C:\Users\Venkatesh\Downloads\AI_Heterogeneous_Computing_Literature_Survey.xlsx` found and read (12 papers, patent, platforms). `Copy of literature survey.xlsx` in the same folder is a different survey (medical-image models on edge devices) and was not used |

## Completed work and evidence (earlier machine)

Phases 0–6B, the dataset (rebuilt 145,378 task rows), the 68-task image pipeline, the dashboard and the Stage 0 backup/manifest are documented in `PROJECT_STATUS.md`, `PROGRESS.md` and `manifests/stage0_20261010/`. They are historical, machine-specific evidence and are not modified.

## Findings reused from the earlier audit

D1 CUDA flag applies to every task of a stage type; D2 E4 base-profile mismatch (fix uncommitted); D3 eligibility honoured by B4/EFT only; D4 features not decision-time safe (46,229 early-binding rows); D7 hard-coded P/E/R. These come from `PROGRESS.md` and the 2026-10-11 code read, not from the missing audit file.

## New this session (documentation research only)

- Base-patent claims read as a paraphrase: no machine learning, prediction, offloading or named hardware in the claims (see PROJECT_SPEC section 7).
- Literature positioning checked against primary sources where accessible (PROJECT_SPEC section 6).
- Montage workflow, toolkit, WfCommons, WfInstances and Rodinia pages inspected; no GPU path found in Montage (WORKLOAD_AND_DATA_PROVENANCE).
- Owner decision: **this machine first, Raspberry Pi 5 later.**

## Unverified claims (do not rely on them)

Update 2026-10-14: the items closed since this list was written are named in "Closed gaps" of the confirmatory report below; the items that remain open are the five items there (also `FINAL_REPORT.md` section 14.3). Entries below that name a closed item are kept as history.

- Patent legal status beyond the catalogue entry (claim wording is now read verbatim, SOURCES_VERBATIM.md section 1; closed 2026-10-13).
- PEFT equation numbers as printed in the IEEE article (PEFT was read via the author's thesis chapter, thesis numbering; HEFT/CPOP originals and PEFT definitions are closed, SOURCES_VERBATIM.md sections 2-4); TabM and CatBoost venue details beyond arXiv.
- Song et al. 2023, Wang et al. 2022, DDDQN-TS, Gong 2023, Nieto 2024, Liu 2024/2025 beyond abstracts; the IEEE versions of LACHESIS and Cao 2024; the journal version of SATA-DRL.
- Montage input data size, source host, build on Windows, generator version requirements, task count the generator really produces.
- Whether the earlier P/E speed ratios hold on the i5-13500HX; the 13500HX core layout.
- WfCommons Montage recipe, WfBench GPU support, Rodinia build on this machine.
- That an RTX 3050 gives a worthwhile speed-up for any stage after host-device copies.
- Workbook statements: "26.7% makespan reduction over seven baselines" (source says "at most", versus the second-best method, in large batch mode), and the Project_Summary's ML-recommends-a-resource idea as part of the patent (not in the claims).

## Decisions still requiring approval

1. Primary contribution: the prediction-sophistication study; exclusion of GNN+PPO, GRU/TCN, temporal Transformer and GNN predictors from the minimum project.
2. How Montage runs here: WSL2, Cygwin/MSYS2, container or native build (contradicts the earlier "no WSL/Docker" rule).
3. GPU design: Montage CPU workflow plus a separate CPU/GPU DAG (default: image-pipeline stages with PyTorch-CUDA variants); installing CUDA-enabled PyTorch.
4. Treat all i5-1235U data as historical and machine-specific.
5. Provide or locate: patent PDF, paywalled papers, `D:\cao_records` audit, `D:\cao_backups`.
6. Commit the E4 fix (separate commit) before Stage 1 starts.
7. Patent: we make no freedom-to-operate claim; seek advice if the work is to be commercialised.
8. Confirm that the Raspberry Pi 5 remains a post-completion extension.

## Execution-start log (2026-10-11, same day)

| Item | Result |
|---|---|
| Write access | At first the project tree was admin-only (only `docs/` writable); `src`, `tests`, `data`, `.git`, `.venv` could not be written. The owner changed the ACL; re-probe shows `src`, `tests`, `data\results`, `.git`, `.venv` writable [real] |
| Branch | `redesign/montage` created from `main` (HEAD `7651eca`); no commits on it yet; uncommitted E4 files carried over unchanged |
| E4 diff review | `git diff src/` read line by line: `learned.py` (record `base_profile` on save, refuse model without usable profile, `BaseProfileMismatchError` on differing measurements, moved-file name check) and `__init__.py` (E4 no longer rebased onto session profile). No defect found by reading. Tests **not yet re-run** (no Python on this machine) |
| Python 3.11 | `winget install Python.Python.3.11 --scope user` started 14:17; the installer log ends at "Launching elevated engine process", i.e. it waits for a UAC/elevation prompt. Not installed. Needs the owner to approve the prompt, or an alternative route |
| Owner instruction | Documentation-only redesign is completed and reviewed **before** any implementation stage starts. No stage has started. E4 commit waits for a working Python to run the four focused test files |

## Stage 1 report (2026-10-12) - PASS

| Gate | Result | Evidence |
|---|---|---|
| 3 of 3 runs complete | PASS: 3 sequential runs, 59 tasks each, status ok, 1459.4 / 1467.1 / 1469.3 s (pinned to P-core LP 2) | `data/results/stage1_20261011/valid/seq{1,2,3}/run.json` |
| Outputs equal | PASS: `1-mosaic.fits`, `1-mosaic_area.fits`, `1-mosaic.png` byte-identical in all 3 runs; FITS max abs difference 0.0 | `valid/stage1_gate.json` |
| WCS sanity | PASS: NAXIS 3960x3960, CRVAL/CDELT/CRPIX/CTYPE equal the requested header, finite fraction 0.9666 | same |
| DAG extracted with no manual edits | PASS: 59 jobs, 147 edges from `jobDependencies` = 147 from file relations, 0 disagreements | same |
| Per-task times for every task | PASS (all 59 timed in each run); mProject median 160.6 s, other tasks 0.1-4.2 s | same |
| GPU pair equivalent with speed-up > 1 (copies included) | PASS for `img_edges` and `img_features` from 512 px (bit-exact, 3.05-13.96x at 512-2048 px on the idle re-run); `img_denoise` bit-exact at every radius tested (0.7, 1.3, 2.0, 2.5, 4.0) but speed-up only 1.03-1.09x at 1024-2048 px and below 1 at 512 px, so it is not used as GPU evidence below 1024 px / iterations 1 and is marginal above | `gpu/spike_20261012T092018/gpu_spike.json` (rerun with the committed script, tolerances fixed in the script, script sha256 recorded) ; first run `gpu/gpu_spike.json` kept as history |
| Docs consistent, reviewed | Provenance, spec, build, literature docs updated; literature gaps listed (patent verbatim claims, HEFT/PEFT originals not reachable) | `LITERATURE_UPDATE.md`, `MONTAGE_WINDOWS_BUILD.md` |

Route used: native Windows build (route 1), no WSL/container/admin. Deviations and failures (kept, excluded): first run with the wrong mDiffFit variant; runs A-C and rep1-3 (PATH, then runner misreading a tolerated message; rep1-3 partly concurrent); an unpinned set killed after mProject ran ~2x slower; debug resume runs `debug_resume1..3` (label debug, found mImgtbl option-order and mViewer stack bugs, patched). The machine was not idle during timing (WSL VM, browser, editor; power plan Balanced). Timings in these runs are indicative; the E1 profile is measured separately.

Quality gates for code (2026-10-12): full suite 364 passed, 1 skipped, then 366 passed, 1 skipped after the mypy pass; mypy on `src/caosched`: 0 errors (6 targeted `# type: ignore[code]` with reasons, see the subagent report in this session); `data/results/stage1_20261011/tests/`.

Not claimed by Stage 1: any scheduling result, any model result, any speed-up of Montage on GPU (none exists).

## Stage 2 report (2026-10-12) - PASS (software and measurement gates); fallback not needed

| Gate | Result | Evidence |
|---|---|---|
| Montage DAG runs under every policy, output equal to the Stage 1 reference | PASS: 14 policies (B0 P-only, B0 E-only, B1 round-robin, B2 static-P, B3 shortest queue, B4 greedy eligible, B5 criticality, random, EFT E1, EFT E3, EFT E1+rc, HEFT E1, PEFT E1, rank-priority EFT E1) x 3 interleaved seeded blocks = 42 runs, all completed, all outputs byte-identical to `valid/seq1` | `data/results/stage2_20261012/sessions/20261012T101305/`, `stage2_gate.json`, design hash `6f753ecc...7887` |
| Zero ineligible placements, dependencies respected, no worker ran two tasks at once | PASS: 0 / 0 / 0 over 42 logs (checked from raw logs by `scripts/stage2_gate.py`) | `stage2_gate.json` |
| Failure-injection suite | PASS (non-zero exit, hang with process-tree kill, missing output, dead worker, unmapped task, early-binding queue) | `tests/test_extcmd.py`, `tests/test_runtime_hardening.py`, `tests/test_eligibility.py` (full suite 366 passed, 1 skipped, `stage1_20261011/tests/full_suite_after_mypy.txt`) |
| GPU output equals CPU, speed-up reported with copies | PASS (bit-exact for img_edges, img_features, img_denoise; speed-ups in the Stage 1 table); CUDA pool run at tile 64 verified in `tests/test_gpu_adapter.py` | `gpu/spike_20261012T092018/gpu_spike.json` |
| Old tests / 68-task pipeline unchanged | PASS (all 191 pre-existing tests still pass inside the 366) | same suite log |
| Per-pool profile with environment manifest | DONE: mProject median 111.8 s (P-core, n=4) vs 401.1 s (E-core, n=4); other task types seconds | `stage2_20261012/profile_montage/` |

Descriptive makespan means over the 3 blocks (seconds; not a Stage 4 result, no intervals): B0 P-only 270.9, B2 static-P 269.6, EFT E3 273.3, EFT E1 275.5, EFT E1+rc 275.4, EFT E1 rank 274.7, HEFT 274.5, PEFT 275.0, B4 greedy 410.5, B3 410.7, B5 413.4, B1 420.4, random 416.5, B0 E-only 811.8.

Reading, stated plainly: on this instance the predictive and plan-based policies match the trivial "use only the P-cores" baseline, and all of them beat the greedy patent-mapped baseline B4 by about one third, because greedy dispatch puts three of the nine 112-second `mProject` tasks on 401-second E-cores. The strongest non-predictive baseline is therefore B0 P-only, not B4. The hypothesis in PROJECT_SPEC (prediction helps only when speed ratios and contention are large relative to prediction cost) is not tested by this table.

Deviations: (1) the machine was not idle (WSL VM, browser, editor); (2) `cleanup_work` deletes the 2 GB work directory of a run only after its outputs were verified against the reference (hashes and event logs are kept); (3) a smoke session `sessions_smoke` is exploratory and showed the cleanup-before-reverify bug, fixed before the matrix; (4) runs were executed in blocks of 14 policies with 3 blocks.

## Stage 3 report (2026-10-12) - PASS (software, scientific and measurement gates); the result is a null result for sophisticated predictors

| Gate | Result | Evidence |
|---|---|---|
| Parity and leakage tests pass | PASS (full suite 377 passed, 1 skipped; `tests/test_parity_leakage.py`) | `stage3_20261012/full_suite_before_commit.txt` |
| Every candidate has accuracy, latency and memory reported | PASS: E1, E3, E1+rc, Ridge, CatBoost, MLP; median inference latency 1 us (profile lookups), 6 us (Ridge), 22 us (MLP), 478-491 us (CatBoost) | `eval/tuning_loo/metrics.json`, `eval/final_test/metrics.json` |
| At least one instance withheld from fitting and tuning | PASS: d1.5 (157 tasks, size withheld) evaluated once | `eval/final_test/`, freeze `STAGE3_FREEZE.md` |
| Final predictor chosen by the rule fixed before the pilot | PASS: **EFT_E1 selected** (cheapest model whose scheduling outcome is not worse than any more complex model, CI upper bound under the 2% margin, 3 blocks) | `selection/selection_record.json`, `pilot_sessions/` (18 runs, all verified, 0 failing checks) |
| Dataset manifest with hashes and exclusions | PASS | `dataset/20261012T195206/manifest.json`, `SHA256_MANIFEST.tsv` |

Data: 60 runs with logged decision contexts (collection sessions, held-out session, Stage 2 EFT runs), 3648 task rows (2706 fitting, 942 held-out), 1416 completed tasks without a logged context dropped by the builder and counted. 42 collection runs all completed and verified byte-identical to the instance references.

Offline accuracy, mean absolute error in seconds (held-out rows only; label real; no scheduling meaning): leave-one-instance-out over d1.0, d1.1 primary, d1.1 c10.7: E1 3.54, E3 3.53, E1+rc 3.56, Ridge 1.32, CatBoost 2.35, MLP 1.86 (n=2706). Final test d1.5 (n=942): E1 3.26, E3 2.71, E1+rc 2.69, Ridge 1.36, CatBoost 2.32, MLP 2.98 (RMSE 22.2 s, extrapolates badly). Median APE 0.27 to 0.69, dominated by tiny task times (stated limitation).

Scheduling pilot (EFT with each predictor, primary instance, 3 blocks): mean makespans 271.4 (CatBoost), 271.5 (MLP), 271.6 (Ridge), 271.8 (E1), 272.4 (E1+rc), 272.7 s (E3): all within 0.5%. Better prediction accuracy did not change the schedule: every EFT variant placed all nine mProject tasks on the P-cores (the 3.6x speed gap dominates any prediction error; some small tasks went to E-cores). TabM: out by the entry rule (needs >= 20,000 rows; 2,706 available).

Deviations: collection was reduced to 42 runs (v2 designs) after the Stage 2 timing; the d1.5 held-out session was run with the same 3 conditions; machine not idle; first dataset build attempt excluded everything (wrong directory layout), kept as `dataset/20261012T195144`.

## Stage 4 report (2026-10-13; this first round is now the PILOT of the confirmatory sessions below) - PASS for software, measurement and correctness gates; scientific outcome is negative/null (stated, not hidden)

| Gate | Result | Evidence |
|---|---|---|
| All planned blocks complete; excluded runs listed | PASS: main 4/4 blocks (44 runs), scarce-P regime 3/3 (15 runs), GPU workload 12/12 (84 runs); 0 excluded | `stage4_20261012/sessions_main`, `sessions_regimeR`, `gpu/sessions`; `*/exclusions.csv` |
| Correctness on all included runs | PASS: Montage outputs byte-identical to each instance's sequential reference in all 59 runs, 0 dependency violations, 0 worker overlaps, 0 ineligible placements; GPU runs verified within the spike tolerances in all 84 runs | `gate_sessions_main.json`, `gate_sessions_regimeR.json`, run manifests |
| Every number traces to an evidence file; labels | PASS (tables/figures from `scripts/analyze_experiment.py`, all labelled real) | `analysis_main/`, `analysis_regimeR/`, `gpu/analysis*/` |
| CI method equals the protocol | PASS with one stated flaw: 4 blocks cannot reach p < 0.05 under the pre-registered Holm-adjusted sign-flip test (minimum p 0.125); results are interpreted through bootstrap CIs | `EVALUATION_PROTOCOL.md` section 12, `analysis_main/effects.csv` |
| One result reproduced from raw logs, hashes re-run | PASS: summary and effects tables re-derived from raw logs and event-log hashes matched for the main, scarce-P and GPU analyses | `stage4_repro/*.json` |
| Clean-checkout reproduction | PASS: 18 of 18 steps (clone, fresh venv from the lock file, pytest subset, stub experiment, analysis, manifest build/verify, table re-derivation, Montage binary/instance hash check); Montage and timings are not re-run from a clean checkout (data/ is not in Git) | `stage4_repro/repro_clean_checkout_log.json` | Final run at commit `ebc68fb` (`data/results/stage5_repro/repro_clean_checkout_final.json`): 19 of 19 steps, fresh venv from the lock file with the pinned CUDA torch, the whole test suite (390 passed; 3 skipped, the three dashboard tests that read the historical event logs which the Stage 0 record keeps out of Git; all 393 pass on this machine), stub experiment, analysis, manifest build/verify, table re-derivation, and the Montage binaries and four instances hash-checked read-only.
| Dashboard demonstration path | DONE: tab "5 - Montage & GPU" lists the Stage 4 runs and draws policy, placement, DAG by transformation, per-worker timeline, task table, output check and log-hash check (checked in the built-in browser on 2026-10-13) | `dashboard_demo.log` |

Outcomes (descriptive, label real): in all three conditions tested no predictive policy beat the strongest simple baseline. All pools: B0 P-only is 1.3-1.9% faster than every EFT/HEFT/PEFT variant (early versus late binding of the second `mProject` wave, confirmed in the worker timelines of the primary instance) and 54% faster than greedy B4. Scarce fast cores (2 P + 7 E): EFT with E1 equals B4 (-0.01%), P-only is 41% slower, **EFT with CatBoost is 15% slower** (it under-predicts `mProject` on P by 18-25% and queues 7 tasks on 2 workers instead of sending 3 to E-cores). GPU workload: predictive EFT with GPU is 2.0% faster than predictive EFT CPU-only and 3.9% faster than greedy GPU use, not distinguishable from P-only (-0.41%, CI includes 0); absolute gain about 0.15 s because CPU stages dominate.

Limits: see `FINAL_REPORT.md` section on limitations.

## Confirmatory sessions report (2026-10-14) - PASS for software, measurement and correctness gates; the scientific outcome is a confirmed null (stated, not hidden)

Why a second round: the pilot's pre-registered Holm-adjusted sign-flip test could not reach p < 0.05 with 4 blocks (smallest attainable p 0.125), and the pilot GPU session had no written analysis plan. EVALUATION_PROTOCOL section 13 (main, scarce-P, GPU; commit `13d1649`) and section 14 (remote emulation; commit `868eeea`) were committed before the first block of each session (first run 16 s and 12 s after the commit). Evidence directory: `data/results/stage5_20261013/` (`S5`). Results per session and prediction: EVALUATION_PROTOCOL section 15.

| Gate | Result | Evidence |
|---|---|---|
| All planned blocks complete; excluded runs listed | PASS: `stage5_main_confirm` 9 blocks (108 runs), `stage5_regimeR_confirm` 8 (48), `stage5_gpu_confirm` 24 (168), `remote_emulation_confirm` 12 (84, label emulation) = 408 runs; 0 excluded | `S5/sessions_main`, `sessions_regimeR`, `gpu_sessions`, `remote_sessions`; `S5/analysis_*/exclusions.csv` (header only; the post-hoc table lists 24 runs by design) |
| Correctness on all included runs | PASS: 408 of 408 completed and verified, 0 dependency violations, 0 worker overlaps, 0 ineligible placements, `n_failing_checks` 0 | `S5/gate_sessions_main.json`, `gate_sessions_regimeR.json`, `gate_gpu_sessions.json`, `gate_remote.json` |
| Design hash equals the pre-registration | PASS: `9228d7ac...`, `7dac58e3...`, `273a155d...`, `4dab0106...` | EVALUATION_PROTOCOL 13, 14; `S5/analysis_*/analysis.json` |
| Significance method can reach p < 0.05 | PASS: block counts 9, 8, 24, 12 chosen so 2/2^n is below the Holm threshold; the pilot flaw is resolved | `S5/analysis_*/effects.csv` (`p_holm`) |
| Tables re-derived from raw logs, hashes re-checked | PASS: four checks each, `ok` true for main, scarce-P, GPU and remote | `data/results/stage5_repro/repro_analysis_{main,regimeR,gpu,remote}.json` |
| Full test suite | PASS: 392 passed, 1 skipped after the sessions (384 passed, 1 skipped before them) | `S5/full_suite_final.txt`, `S5/full_suite_before_confirmatory.txt` |
| Background load measured | DONE: 1,928 samples every 30 s, median non-experiment CPU 35.1% summed over processes, median machine CPU 23.6%, minimum free RAM 2.09 GB | `S5/load/load_20261013T121952.jsonl` |

Outcomes per pre-stated prediction (label real; remote: emulation; numbers from the `effects.csv` files named in EVALUATION_PROTOCOL 15):

* **P1 supported.** `B0_P_early` (same placements as B0 P-only, early binding) is +1.68% (+1.24 to +2.31), p_holm 0.036: early versus late binding is now a controlled contrast. Post-hoc without the slow window +1.40% (+1.20 to +1.60).
* **P2 supported** for EFT_E1 +1.62%, E3 +1.59%, rank +1.41%, Ridge +1.54%, HEFT +1.54%, PEFT +1.73% (all significant, each in 9 of 9 blocks); direction only for EFT_CatBoost +8.68%, EFT_E1_rc +13.92%, EFT_MLP +12.99% (inflated by the slow window; +1.44%, +1.93%, +2.04% post-hoc); B4 +47.9% (+53.5% post-hoc).
* **P3 supported** (scarce-P): B0 P-only +42.48% (+41.05 to +43.54), EFT_CatBoost +15.65% (+14.84 to +16.12); EFT_E1 -0.13% (-1.10 to +0.88): point estimate inside +-0.5%, equivalence not resolved. EFT_Ridge -0.59% (-1.18 to -0.18), p_holm 0.0325: significant, about 2.4 s of 412 s, below the 2% practical margin, no prediction had been made.
* **P4 supported** (GPU): EFT_E1 with GPU -2.10% (-2.93 to -1.35), p_holm 0.0006 against its CPU-only version; -0.65% (-1.82 to +0.34) against B0 P-only (not distinguishable); about -3.5% against B4 with GPU (computed in FINAL_REPORT 11.1). Makespans about 7 s because CPU stages dominate.
* **D1 supported, D2 not supported, D3 no difference (remote, emulation).** B4 with R is +30.69% (+29.42 to +32.02), p_holm 0.0024 on the WAN link; the transfer-aware EFT placed 0 tasks on R on both links; EFT with R on the LAN +0.14% (-1.10 to +1.19). The emulated remote pool gave no benefit to either policy. Calibrated transfer cost 0.779 ms + 1.617 ns per byte (n = 60).
* **Claims:** (a) prediction beats the best non-predictive baseline in some condition: not supported at the practical margin in all four conditions (the only significant advantage is Ridge over B4 by 0.59% in scarce-P); (b) a simple method matches prediction: supported; (c) predictor sophistication improves scheduling: not supported; (d) offline Ridge generalises to the held-out `d1.5` (MAE 1.36 s against 3.26 s for E1), scheduling effects do not depend on it; (e) significance resolved for P1, P3 (except equivalence of EFT_E1), P4 and D1.

**Slow window (stated plainly).** 14 consecutive runs of the main session, from block 5 run 0 (12:40 UTC on 2026-10-13) to block 6 run 1 (ends about 14:30 UTC), ran slower: about 1.4 times for every policy but B4 in block 5, and about 2.5 times for three runs (EFT_CatBoost in block 5, EFT_E1_rc and EFT_MLP in block 6); the `mProject` kernel on P cores took 296 s to 380 s in the last three against 115 s to 158 s elsewhere; placements of `mProject` did not change. The load monitor shows no heavy non-experiment process in that window; the cause is identified: the Windows System event log (`Kernel-Power` event 105, `data/results/stage5_20261013/windows_power_source_events.json`) records `AcOnline=false` at 18:11:21 local (battery at 100%) and `AcOnline=true` again at 19:59:07 (battery at 9.5%), i.e. the laptop ran on battery for 1 h 48 min; the first slow run started at 18:10:55 and the last ended at about 19:59, so the slow runs coincide with the battery interval; all other sessions ran on AC power according to the same log (AC online from 2026-10-12 08:59:39 to 2026-10-13 18:11:21, and again from 19:59:07; the Stage 1 reference runs of 2026-10-11 20:33-21:57 also fall in an AC interval). The pre-registered exclusion rules do not exclude such runs, so the primary analysis keeps them; the post-hoc sensitivity analysis without blocks 5 and 6 (`S5/analysis_main_posthoc_excl_blocks_5_6`, 7 blocks, cannot be Holm-significant) gives +1.15% to +2.04% for the EFT variants. A measurement limit of this machine, not something to fix by re-running.

**Closed gaps (replace the older "unverified" wording):**

* Patent US 11,561,826 B1 claims read verbatim (all 20; `SOURCES_VERBATIM.md` section 1): 0 occurrences of machine-learning, prediction, estimation, model, offload, GPU, CPU or FPGA vocabulary in any claim.
* HEFT/CPOP original read in full; PEFT read through the author's thesis chapter; both papers' worked examples reproduced exactly by `tests/test_heft_peft_papers.py` (3 tests; makespans 80, 122, 133).
* DSS terms read (non-profit research use free with acknowledgement requested; commercial use needs written permission; no rule on third-party redistribution of the files); acknowledgement text included in `FINAL_REPORT.md` section 15.1.
* Licences of all components read from their files (`LICENCES.md`); components without a licence file are listed there (section 5); the project's own licence is the owner's choice.
* Drift check (late/early MAE ratio learned 1.29 to 1.40 against 1.01 to 1.02 for the references; time-split MAE E1 3.514 s, Ridge 0.8395 s, CatBoost 2.123 s, MLP 1.334 s), learning curve (Ridge flat from 20% to 40% of the runs, CatBoost non-monotone, so the TabM entry condition 2 is not established) and one-step regret table (B4 mean regret 6.85 s per decision in the main set, EFT_E1 0.312 s; scarce-P EFT_CatBoost 2.538 s against EFT_E1 0.134 s; exactly 6 `mProject` decisions differ, regret 57.5 s to 61.7 s; pilot sessions) run: `S5/analysis_extra/`.
* Figures fixed and three diagrams produced (`S5/figures/`); early-binding mechanism tested as a controlled contrast (P1); the Holm flaw resolved by the confirmatory sessions; the GPU session pre-registered before it ran; background load measured.

**Genuinely remaining:**

1. Raspberry Pi 5, real network, foreign clock, ARM: requires hardware that is not available on this machine and is excluded by the project specification as a later extension; no edge claim is made.
2. (closed) The cause of the slow window is identified: the laptop ran on battery from 18:11:21 to 19:59:07 local (Windows `Kernel-Power` event 105, `stage5_20261013/windows_power_source_events.json`).
3. Full texts behind publisher paywalls or bot checks were not accessible and are listed with every attempt in `SOURCES_VERBATIM.md` section 7 (IEEE-typeset PEFT article, LACHESIS, Cao and Song full texts, Liu FGCS full text, Wang accepted manuscript); no claim of the results depends on them.
4. The project has no licence file of its own (the owner's choice).
5. The remote pool is emulated (loopback, no jitter).
6. One machine, patched Windows Montage build.

## Documents in this redesign

[PROJECT_SPEC.md](PROJECT_SPEC.md) · [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) · [FOUR_STAGE_IMPLEMENTATION_PLAN.md](FOUR_STAGE_IMPLEMENTATION_PLAN.md) · [WORKLOAD_AND_DATA_PROVENANCE.md](WORKLOAD_AND_DATA_PROVENANCE.md) · [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md)

Older documents (`PROJECT_STATUS.md`, `docs/PROJECT_BRIEF.md`, `docs/B4_PATENT_MAPPING.md`, `docs/REMOTE_DEVICES.md`) are historical and unchanged. Where they describe the i5-1235U, P/E core numbers, the 68-task pipeline as the application target, or "claims not retrieved" for the patent, this redesign supersedes them once approved.

## Next action

The owner decisions are listed in `FINAL_REPORT.md` section 14.2 (further conditions where prediction might matter, Raspberry Pi 5 go or no-go, licence of the project and data rights, archiving and a stage-level manifest, presentation details). No implementation or experiment is pending.
