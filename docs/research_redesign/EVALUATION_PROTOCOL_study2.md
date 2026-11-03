# Evaluation protocol, Study 2 (branch `study2/affinity`)

Status: written 2026-10-24 BEFORE the first pilot block. This is a NEW file; `EVALUATION_PROTOCOL.md` and every stage 1-5 file are unchanged (rollback: `git checkout baseline-null-result`). Evidence labels as in `PROJECT_SPEC.md` ([real] = measured on this machine). Written by the assistant under the owner's delegation (the owner asked for a run on full autopilot while asleep).

## 1. Question

Stage 5 found a confirmed null: on Montage and on the 68-task pipeline, prediction-aware EFT did not beat the strongest simple rule, because one serial stage dominates the makespan and every stage prefers the P cores (stage 2 profile: E/P slow-down 2.3 to 3.6 for every Montage transformation). A placement choice can only help when it has room: many independent tasks, three kinds of worker (P, E, one CUDA worker), and stages that disagree about the best worker.

Study 2 question: on a batch of independent image-analysis chains where such room exists, does predicted-finish-time placement (EFT with the solo profile, E1) beat (C1) the strongest STATIC rule and (C2) the strongest non-predictive DYNAMIC rule?

Hypothesis: yes for C1 (a static rule cannot use the E cores and the CUDA worker well at the same time); C2 is open and may well be a null. A null is an accepted, reportable outcome (as in `PROJECT_SPEC.md` section 5).

## 2. Workload and go/no-go gate [real]

`src/caosched/study2/workload.py`: k = 64 independent chains `source -> denoise (x8) -> edges -> features`, 512 px images, one `aggregate` task at the end (existing stage functions, `apps/stages.py`; CUDA variants `apps/cuda_stages.py`). Pools: P (one worker per physical P core), E, and one CUDA worker G (only `img_denoise`, `img_edges`, `img_features` may use G; the stage table is read from the recorded spike at side 512, rows PASS for all three).

Gate (`scripts/study2_gate.py`, rule fixed in the script before the profile was read; result `data/results/study2_20261024/gate.json`, sha256 `ed994365f7ff5d04c412f17693b9006d3b865632fe87a95775211e3c3e980dae`): PASS needs (a) one stage at least 3x faster on G than on a P core and (b) one stage within 15% of P speed on G. Measured solo medians (9 reps, profile `profile_t512/20261024T001156_profile.json`):

| stage | P ms | E ms | G ms | E / P | P / G |
|---|---:|---:|---:|---:|---:|
| img_source | 84.8 | 229.8 | - | 2.71 | - |
| img_denoise | 44.8 | 159.1 | 41.8 | 3.55 | 1.07 |
| img_edges | 5.4 | 18.1 | 0.84 | 3.36 | 6.43 |
| img_features | 2.2 | 6.9 | 0.96 | 3.09 | 2.31 |
| img_aggregate | 0.04 | 0.16 | - | 4.25 | - |

Verdict PASS (edges 6.4x; denoise 1.07x). Stated limits of this room: the GPU can save at most (5.4 - 0.84) + (2.2 - 0.96) = 5.8 ms of the 137 ms P-core time of a chain (4%); the dominant lever is whether the 7 E workers (each 2.7 to 3.6x slower) are used well. Every stage still prefers the P core over the E core, so the "task types disagree" condition holds for the GPU only.

## 3. Conditions (design files in `data/results/study2_20261024/designs/`)

Static rules (fixed type-to-pool map or fixed pool, no queue state; fixed before any run): `B0_P_only`; `STATIC_G_edges_features` (sources, denoise, aggregate on P; edges and features on G; chosen from the profile above); `STATIC_GPU_first` (denoise, edges, features all on G). Non-predictive dynamic rules: `B3_gpu` (shortest queue), `B4_gpu` (greedy eligible, priority G, P, E), `B4_cpu` (priority P, E, no GPU). Predictive: `EFT_E1_gpu`, `EFT_E1_cpu` (same policy, G not eligible), `EFT_E1_rc_gpu` (online recalibration), `HEFT_E1_gpu` (static plan). All policies are the unchanged stage 2-5 implementations (`experiment/montage_adapter.build_policy`); only the workload and adapter (`study2/adapter.py`) are new.

Correctness: an all-CPU run must reproduce the sequential reference's final aggregate byte for byte; runs with CUDA tasks are checked per CUDA task (CPU stage re-run on the same input artifacts, tolerances of `scripts/gpu_spike.py`). A run that fails this is not verified and is excluded from the primary analysis (kept in the raw data).

## 4. Pilot (exploratory; this section is written before it runs)

Design `design_study2_pilot.json` sha256 `fc15a09826144b2ba34ab43ad208025314f7e51aa9b88abebc9ffae36a1e6eb3` (seed 20261201, 8 blocks, 1 warm-up block excluded, 10 conditions in seeded random order per block, adapter config `adapter_config_study2.json` sha256 `15d4c3e9beacf1e1eb04379c15cc9fc7b939201ac4b4499ef225bd5b2a73e1c7`). The pilot is NOT confirmatory. It is used for exactly two things, fixed now: (i) to name the strongest static rule and the strongest non-predictive dynamic rule (smallest mean makespan among the verified pilot runs of each group); (ii) the paired standard deviation of the log makespan, from which the confirmatory block count follows by the rule of `EVALUATION_PROTOCOL.md` section 9 / 12.4 (n = ceil(((1.96 + 0.84) sd_log / ln(1 + m))^2) with m = 2%, then raised so that the smallest attainable sign-flip p, 2/2^n, is below the Holm threshold of the family, as in section 13). The pilot numbers are never pooled with the confirmatory session (different design hash).

## 5. Confirmatory session (pre-registration appended BEFORE its first block)

To be added below as section 5.1 after the pilot analysis and committed before the first confirmatory block. It will fix: reference conditions, block count, family of contrasts and Holm threshold, predictions with direction and size, and outcome wording (supported / not supported / not resolved). If the pilot shows no condition in which an EFT variant is within 2% of or ahead of the strongest static rule, the confirmatory session is still run on the pre-registered contrasts unless the pilot shows the design cannot resolve them (minimum detectable effect above 2%), in which case the result is reported as "not resolved by this design".

## 6. Controls and limits stated in advance

* AC power: the session starter checks that the laptop is on mains power and aborts otherwise (the one slow window of stage 5 coincided with battery operation). Background load is logged every 30 s (`scripts/load_monitor.py`).
* Memory: at the start of this pilot about 2.3 GB of RAM was free (WSL VM, browser, editor running). The design therefore uses `min_free_ram_gb` 1.2 instead of 2.5; the memory preflight records free memory before every block. The workload itself is small (64 chains of 512 px images; artifacts are removed after verification).
* No pooling with stage 5 sessions: the source hash differs (new files under `src/caosched`), `analyze_experiment.py` refuses mixed code.
* Same machine, same session family: conclusions are machine-specific. The DAG shape is synthetic (a batch of independent chains), the stages and kernels are real.
* The sessions run on the same working tree as the commit that contains this file plus uncommitted data files; the runner records the git commit and the dirty flag.

## 7. Rollback

`git tag baseline-null-result` (commit `7dd1847`) is the state before this study. All study 2 files are new: `src/caosched/study2/`, `scripts/study2_*.py`, `tests/test_study2.py`, this file, and `data/results/study2_*`. Reverting means checking out the tag (or deleting those paths); no stage 1-5 file was edited.

## 8. Amendment A1 (2026-10-24, written after pilot 1 and BEFORE pilot 2)

Pilot 1 (session `pilot_sessions/20261024T001349`, design sha256 `fc15a098...`, 80 runs, all verified) is kept as evidence and is a flawed pilot, not a result. Its makespans of GPU conditions were bimodal (about 2.0 to 2.2 s versus 2.5 to 2.9 s for the same policy) and the paired standard deviation of the log makespan was 0.08 to 0.20, a minimum detectable effect of 9% to 23% with 7 blocks. Cause found in the code (not tuned on outcomes): the stage 5 `GpuAdapter` rebuilds the whole worker pool whenever a condition switches between "with G" and "no_gpu", so the run after a rebuild starts with cold workers (imports, first CUDA call), and the run order is random. Fix, new files only: `Study2Adapter` keeps ONE pool with the CUDA worker for every condition (a "no GPU" condition only makes G ineligible), as `remote_adapter` already does. Test: `tests/test_study2.py::test_one_pool_serves_gpu_and_no_gpu_conditions`.

Pilot 2: design `design_study2_pilot2.json` sha256 `16cfdb8f59d6e67e28fd65e2a121e4531daa215433297dc01b805dfdac41bd1b` (same conditions and workload, seed 20261202, 12 blocks, 1 warm-up block). Pilot 1's numbers are not used for any decision in section 4 (reference choice, block count). Pilot 1 is reported as a described failure in the final report.

## 9. Amendment A2 (2026-10-24, written after pilot 2 and BEFORE pilot 3)

Pilot 2 (session `pilot2_sessions/20261024T...`, design sha256 `16cfdb8f...`, 12 blocks, 120 runs, all verified) removed the bimodality: paired sd of the log makespan 0.016 to 0.034 (minimum detectable effect 1.3% to 2.9% with 11 blocks). Descriptive means (s): B0_P_only 2.550, STATIC_G_edges_features 2.951, STATIC_GPU_first 4.425, B3_gpu 2.119, B4_cpu 2.109, B4_gpu 1.876, EFT_E1_cpu 2.008, EFT_E1_gpu 1.908, EFT_E1_rc_gpu 1.905, HEFT_E1_gpu 2.067. Reading: every predictive and dynamic policy beats the static rules by a wide margin (it uses the E cores and the CUDA worker together), the strongest static rule is B0_P_only (the hand-tuned G map is slower, because one CUDA worker serialises 128 tasks that each cost more in I/O than in kernel time), and the strongest non-predictive dynamic rule is B4_gpu, which EFT is NOT ahead of (EFT_E1_gpu +1.7%). The code explains why EFT may be misled: its estimates are kernel-only (G edges 0.84 ms) while the measured worker span of a G task is about 6 ms (3.6 ms task I/O plus 1.9 ms IPC), so EFT over-rates the single CUDA worker (queue length, early binding).

Decision before pilot 3 (stated now): test the end-to-end ablation of the existing code (`EFT_*_e2e`, `estimators/e2e.py`: kernel estimate + measured setup + measured IPC overhead per pool), with terms measured from pilot 2's logs only (`e2e_terms_pilot2.json` sha256 `dc1f33632262ee1dd5b660a0e4849e32848412e0d1485cb4477498b6b270187e`, `scripts/study2_e2e_terms.py`, warm-up block excluded). New in study 2 only: `build_study2_policy` (the stage 5 `build_policy` never passes `e2e_terms`). Pilot 3: design `design_study2_pilot3.json` sha256 `15fd4e9cbe8918d51d1733b854ff1725dc19578ce115781de008876d72b6b333`, 6 conditions (B0_P_only, B4_gpu, EFT_E1_gpu, EFT_E1_rc_gpu, EFT_E1_e2e_gpu, EFT_E1_rc_e2e_gpu), 8 blocks, seed 20261203, 1 warm-up block. Exploratory; it only decides whether the e2e conditions enter the confirmatory design.

Note A2.1 (same day, before any pilot 3 block ran): the pilot 3 file `design_study2_pilot3.json` (sha256 `15fd4e9c...`) was rejected by `load_design` ("reference must be a condition name": its reference STATIC_G_edges_features is not among the six conditions), so no run started. Same conditions, seed 20261203, 8 blocks, reference B0_P_only: `design_study2_pilot3b.json` sha256 `a6efc73bf290018207e8a496b9e7e949883ccd3f8c4fb90bed68f32f6e77da53`.

Note A2.2 (same day, before the next pilot 3 attempt): `design_study2_pilot3b.json` ran one block, then the session ABORTED by its own memory preflight ("free RAM below 1.2 GB before block 1": 1.12 GB free with the pool up; the machine fluctuates between 1.0 and 2.7 GB free because of the WSL VM, browser and editor; the session record `pilot3_sessions/20261024T0054...` is kept, block 0 is a warm-up block, nothing is analysed from it). Pool memory is part of the workload (14 workers, one with a CUDA context), so the threshold for study 2 is lowered from 1.2 to 0.8 GB for all later sessions (`--min-free-ram 0.8`); free memory is still recorded before every block (`preflight.jsonl`) and in the load log. Same conditions, seed 20261203, 8 blocks, reference B0_P_only: `design_study2_pilot3c.json` sha256 `8e47cf02e393d44712a6c1ad9dffb117e38089af7ad2ab0316e5e0efbc11a1e3`.

## 10. Amendment A4 (2026-10-24, after pilot 3c, BEFORE pilot 4)

Pilot 3c (session `pilot3c_sessions/`, design sha256 `8e47cf02...`, 8 blocks, reference B4_gpu, 42 of 48 runs in the primary analysis; the 6 excluded are the warm-up block): mean makespan (s) B0_P_only 2.491, B4_gpu 1.779, EFT_E1_gpu 1.836, EFT_E1_rc_gpu 1.850, EFT_E1_e2e_gpu 1.822, EFT_E1_rc_e2e_gpu 1.821. Paired effect against B4_gpu: EFT_E1_gpu +3.2% (+1.0, +5.5), EFT_E1_rc_gpu +4.0% (+2.2, +6.0), EFT_E1_e2e_gpu +2.4% (+0.0, +4.4), EFT_E1_rc_e2e_gpu +2.3% (+0.9, +3.9); B0_P_only +39.9%. End-to-end estimates help a little but EFT stays behind the non-predictive greedy rule B4_gpu. B4_gpu is a late-binding rule; every EFT variant tested so far binds early (a task is queued behind a busy worker on the model's say-so), and stage 5 isolated the cost of early binding (B0_P_early, +1.7%).

Decision before pilot 4 (stated now): add one new policy, `LateEftScheduler` (`src/caosched/study2/policies.py`, subclass of the unchanged `EarliestFinishTimeScheduler`): the same predicted finish times, but a task is bound only to an IDLE worker; if the predicted-best worker is busy the task is held in the ready queue. Tests: `tests/test_study2.py::test_late_eft_*`. Pilot 4: design `design_study2_pilot4.json` sha256 `7c3c7c6ee3a1c00ab78266c0723bf4f01c2c5d82cd66a6ad99c6a56b95a216fe`, 7 conditions (B0_P_only, B4_gpu, EFT_E1_gpu as in pilot 3, plus EFT_E1_late_gpu, EFT_E1_rc_late_gpu, EFT_E1_late_e2e_gpu, EFT_E1_rc_late_e2e_gpu), 8 blocks, seed 20261204, 1 warm-up block, reference B0_P_only, e2e terms from pilot 2 (unchanged file), memory threshold 0.8 GB. Exploratory; it decides which EFT variants enter the confirmatory design.

## 11. Amendment A5 (2026-10-24, after pilot 4, BEFORE pilot 5)

Pilot 4 (session `pilot4_sessions/`, design sha256 `7c3c7c6e...`, 8 blocks, 56 runs, all verified): B0_P_only 2.441 s, B4_gpu 1.780 s, EFT_E1_gpu (early binding) 1.830 s (+2.8% vs B4_gpu, +0.6 to +4.8). All four late-binding EFT conditions took 10 to 33 s per run and the time grew with the block number. Cause (read from the event logs, not tuned): `run_finished.scheduling_time_seconds` was about 32 s of a 32.7 s makespan, i.e. the time was spent inside `select_worker`. A late policy re-evaluates every held task on every dispatch pass, and each evaluation built the decision context for 14 candidate workers (`log_context`, default on in the unchanged EFT), whose cost grows with the workers' activity history (up to 256 intervals per worker, shared across runs of a session). Micro-benchmark on a synthetic state with an empty history: 81 microseconds per call with the context, 19 without. The per-decision overhead in `runs.csv` did not show it because it only counts decisions that bound a task. The late-binding result of pilot 4 is therefore a measurement of an implementation cost, not of the policy.

Fix, new files only: `EftNoContext` and `LateEftScheduler` default to `log_context=False` (same decisions for E1-type estimators, test `test_no_context_eft_decides_like_eft`). To keep the comparison fair, a no-context EARLY-binding variant is added (`binding: early_noctx`, policy names `..._noctx_...`); the original EFT_E1_gpu (context logging on, as in stage 5) stays in the design as the unchanged reference EFT. Pilot 5: `design_study2_pilot5.json` sha256 `e3151a9898596f2151783203e1211716ef26233dac960ca2ff13ffa47c466cae`, 8 conditions (B0_P_only, B4_gpu, EFT_E1_gpu, EFT_E1_noctx_gpu, EFT_E1_late_gpu, EFT_E1_rc_late_gpu, EFT_E1_late_e2e_gpu, EFT_E1_e2e_noctx_gpu), 8 blocks, seed 20261205, reference B0_P_only. Scheduling time per run (including held decisions) is read from `scheduling_time_seconds` and reported next to every makespan from now on.

## 12. Pre-registration of the confirmatory session (written 2026-10-24 BEFORE its first block)

Evidence used to set the design (exploratory pilots, all on this machine; pilots 1 and 4 are described failures, see sections 8 and 11): pilot 2 (12 blocks), pilot 3c (8), pilot 5 (8). Mean makespans in seconds, pilots 2 / 3c / 5: B0_P_only 2.55 / 2.49 / 2.44; B4_gpu 1.88 / 1.78 / 1.77; EFT_E1_gpu (stage 5 implementation, context logging on) 1.91 / 1.84 / 1.83; EFT_E1_noctx_gpu (pilot 5) 1.77; EFT_E1_e2e_noctx_gpu (pilot 5) 1.76; STATIC_G_edges_features 2.95 (pilot 2). Late-binding EFT (pilot 5): 2.66 to 2.71 s, 50% worse than B4_gpu (held tasks starve idle workers; 0.7 to 1.0 s of scheduling time per run): it is not in the confirmatory design and is reported as a negative result.

**Reference and strongest rules (chosen from the pilots, before the confirmatory data):** strongest STATIC rule = B0_P_only (lowest mean of the static rules in every pilot; STATIC_G_edges_features and HEFT_E1_gpu are slower); strongest NON-PREDICTIVE DYNAMIC rule = B4_gpu (lowest mean of the non-predictive rules in every pilot). Session reference = B4_gpu.

**Session.** Design `data/results/study2_20261024/designs/design_study2_confirm.json` sha256 `619f08781f26e6c4308ee200e25a39ac5b09f01c9052dba9043e3b67d1910f02`; adapter config `adapter_config_study2.json` sha256 `15d4c3e9beacf1e1eb04379c15cc9fc7b939201ac4b4499ef225bd5b2a73e1c7`; e2e terms `e2e_terms_pilot2.json` sha256 `dc1f33632262ee1dd5b660a0e4849e32848412e0d1485cb4477498b6b270187e` (measured from pilot 2 only, never from this session). Seed 20261301, 49 blocks of which block 0 is the warm-up (48 analysed), 9 conditions per block in seeded random order, instance: the one fixed workload (64 chains, 512 px, denoise x8, CUDA stages edges/features/denoise allowed), memory preflight 0.8 GB.

| condition | role |
|---|---|
| B0_P_only | strongest static rule |
| STATIC_G_edges_features | static type-to-pool map (edges and features on G) |
| HEFT_E1_gpu | static plan (HEFT) |
| B3_gpu | non-predictive dynamic (shortest queue) |
| B4_gpu | strongest non-predictive dynamic rule, session reference |
| EFT_E1_gpu | predictive, stage 5 implementation (context logging on) |
| EFT_E1_noctx_gpu | predictive, same decisions, context logging off |
| EFT_E1_e2e_noctx_gpu | predictive with measured I/O and IPC terms, context logging off |
| EFT_E1_noctx_cpu | predictive without the CUDA worker (same pool, G ineligible) |

**Block count.** Paired sd of the log makespan in the pilots for the contrasts of interest: 0.009 to 0.034 (pilot 5: 0.021 to 0.027 for the no-context EFT conditions against B4_gpu). The rule of section 4 (n = ceil(((1.96 + 0.84) sd / ln(1 + m))^2)) with m = 2% and sd = 0.03 gives 18 blocks; 48 are used so that the achieved 80%-power minimum detectable effect is about 1% (it is reported as `mde_pct_80power` in every effects table) and a +-2% equivalence claim can be resolved.

**Analyses (committed now, no others are confirmatory).** `scripts/analyze_experiment.py --seed 0` (stratified percentile bootstrap, 10,000 resamples, exact or sampled sign-flip test with Holm adjustment over the conditions of each analysis) twice on the same session: A with reference B4_gpu (output `analysis_confirm_ref_B4_gpu`), B with reference B0_P_only (output `analysis_confirm_ref_B0_P_only`). Metric: makespan (`run_finished.makespan_seconds`); scheduling time per run (`scheduling_time_seconds`) is reported beside it. Exclusions as in `EVALUATION_PROTOCOL.md` section 12.5 (session not complete, run not ok, log missing or hash mismatch, output not verified, no makespan); excluded runs stay in the raw data and a sensitivity analysis includes them.

**Pre-stated predictions (made from the pilots), outcome wording "supported", "not supported" or "not resolved by this design":**
* P1 (beats the strongest static rule): EFT_E1_noctx_gpu is faster than B0_P_only by 20% to 35%, Holm-significant.
* P2: EFT_E1_noctx_gpu is faster than STATIC_G_edges_features by 30% to 45%, Holm-significant.
* P3 (against the strongest dynamic rule): EFT_E1_noctx_gpu is equivalent to B4_gpu: the whole 95% interval of the paired effect lies inside +-2% (the project's practical margin). No superiority is predicted.
* P4 (the stage 5 implementation's overhead): EFT_E1_gpu is slower than EFT_E1_noctx_gpu by 2% to 5%, Holm-significant.
* P5: EFT_E1_noctx_gpu is faster than EFT_E1_noctx_cpu by 3% to 6% (value of the CUDA worker).
* P6: EFT_E1_e2e_noctx_gpu against B4_gpu: no prediction on the sign (pilot 5: -0.5%, interval -2.0 to +0.9), exploratory.

**What the confirmatory claims mean.** "Prediction-aware placement beats static scheduling on this workload" is supported only if P1 and P2 are both supported. "Prediction beats the strongest non-predictive dynamic rule" is supported only if some predictive condition has a Holm-significant paired effect against B4_gpu with the point estimate at or below -2%; an interval inside +-2% is reported as equivalence (P3); anything else as not resolved. No other comparison is confirmatory.

**Controls and limits (as in section 6).** AC power checked immediately before the first block and the load log running during the session. The workload shape (64 independent chains), the CUDA stage table, the no-context variant and the e2e terms were developed over pilots on this machine and are not independent of it; one machine; the DAG shape is synthetic, the stages are real. The unchanged stage 5 code was not edited (rollback: `baseline-null-result`).

## 13. Results of the confirmatory session (written 2026-10-24, AFTER the session and its analyses; sections 1 to 12 above are unchanged)

Session `confirm_sessions/20261024T013322`: status complete, 49 of 49 blocks, 441 runs, all 441 with status ok, output verified and event-log hash matching; 432 in the primary analysis (the 9 excluded runs are the warm-up block, exclusion table `exclusions.csv`). Design hash matches the pre-registration (`619f0878...`). Evidence manifest `confirm_sessions/20261024T013322/SHA256_MANIFEST.tsv` verified (0 missing, 0 changed, 0 extra); `scripts/reproduce_subset.py` re-derived the summary and effects tables from the raw logs for both pre-registered analyses (`repro_confirm_ref_B4_gpu.json`, `repro_confirm_ref_B0_P_only.json`, `ok` true). Mean makespan (s): B0_P_only 2.454, STATIC_G_edges_features 2.804, HEFT_E1_gpu 1.984, B3_gpu 2.009, B4_gpu 1.773, EFT_E1_gpu 1.824, EFT_E1_noctx_gpu 1.778, EFT_E1_e2e_noctx_gpu 1.775, EFT_E1_noctx_cpu 1.864. Paired effects (percent of the reference makespan, 95% bootstrap interval, 48 blocks; files `analysis_confirm_ref_*/effects.csv`):

| prediction | contrast | effect | interval | p_holm | outcome |
|---|---|---:|---|---:|---|
| P1 | EFT_E1_noctx_gpu vs B0_P_only | -27.56% | -28.21 to -26.92 | 0.0008 | **supported** (predicted 20 to 35%) |
| P2 | EFT_E1_noctx_gpu vs STATIC_G_edges_features | -36.6% (computed: 1.778 / 2.804 on the paired means; reference-EFT table: static +57.70%, 56.11 to 59.26, p_holm 0.0008) | | 0.0008 | **supported** (predicted 30 to 45%) |
| P3 | EFT_E1_noctx_gpu vs B4_gpu | +0.25% | -0.55 to +1.05 | 1.0 | **supported**: interval inside +-2%, i.e. equivalent; no superiority |
| P4 | EFT_E1_gpu vs EFT_E1_noctx_gpu | +2.62% | +1.87 to +3.39 | 0.0008 | **supported** (predicted 2 to 5%) |
| P5 | EFT_E1_noctx_gpu vs EFT_E1_noctx_cpu | -4.64% (cpu is +4.87% slower, 4.18 to 5.59) | | 0.0008 | **supported** (predicted 3 to 6%) |
| P6 | EFT_E1_e2e_noctx_gpu vs B4_gpu | +0.09% | -0.72 to +1.04 | 1.0 | exploratory: no difference |

Other contrasts against B4_gpu: B0_P_only +38.40%, STATIC_G_edges_features +58.09%, B3_gpu +13.31%, HEFT_E1_gpu +11.84%, EFT_E1_gpu +2.88% (+2.26 to +3.50), EFT_E1_noctx_cpu +5.14%. Against EFT_E1_noctx_gpu: HEFT_E1_gpu +11.56%, B3_gpu +13.03%. The 80%-power minimum detectable effect of the contrasts is 0.8% to 1.5%.

**Confirmatory claims (wording fixed in section 12).** (a) "Prediction-aware placement beats static scheduling on this workload": **supported** (P1 and P2 both supported; it is also 10.4% faster than the static HEFT plan, computed from the reference-EFT table). (b) "Prediction beats the strongest non-predictive dynamic rule": **not supported**; the no-context EFT, with kernel-only or end-to-end estimates, is equivalent to B4_gpu within +-1% (P3, P6). The gain over the static rules comes from using all three worker kinds dynamically, which the greedy late-binding rule B4_gpu also does.

Scheduling time per run (median of `run_finished.scheduling_time_seconds`, includes decisions that held or bound a task): B4_gpu 0.015 s, EFT_E1_noctx_gpu 0.056 s, EFT_E1_e2e_noctx_gpu 0.082 s, EFT_E1_gpu (context logging on) 0.233 s, of makespans of 1.8 s. Tasks per pool in a typical run (257 tasks): B4_gpu P 129 / G 45 / E 83; EFT_E1_noctx_gpu P 86 / G 38 / E 133: the predictive rule moves work to the E cores.

**Deviations and limits (stated plainly).**
* The load monitor for this session failed to start (shell error, exit code 127, so no `load/load_confirm_*.jsonl` exists); the machine's background load during the session is therefore not measured. What exists instead: the free-RAM preflight before every block (`preflight.jsonl`), `memory_available_start_bytes` for every run (`runs.csv`), and the Windows System log, which has no AC/battery change event (id 105) in the five hours that include the session (checked read-only afterwards); the laptop reported mains power before launch and afterwards.
* Predictions P4 and P5 involve a reference other than the two pre-registered analyses; they were evaluated with a third analysis (reference EFT_E1_noctx_gpu, same method and seed, `analysis_confirm_ref_EFT_E1_noctx_gpu`), declared here, not listed in section 12.
* After the session two typing-only edits were made (`policies.py` constructor signature, `adapter.py` type annotation) so that `mypy` is clean; behaviour is unchanged (10 study 2 tests pass) but `src_sha256` of the session (`environment.json`) is the hash of the code before those edits.
* One machine; a synthetic DAG shape made of real stages; the design (workload shape, CUDA stage table, no-context variant, e2e terms) was developed over pilots on this machine. The Montage and 68-task pipeline null results of stage 5 are not changed by this study.

## 14. Oracle bound (written 2026-10-24, BEFORE its first block)

**Question.** How much faster can an EFT decision get if it knows the true time of every task? This is a ceiling, not a rule. If the ceiling is close to the current rules, no better prediction or policy can win on this workload; if it is well below them, a better decision rule may win.

**Oracle.** `ReplayOracleEstimator` (E5, `estimators/oracle.py`): for each (task id, seed, workload, size, pool) the median kernel time of the same task in the logs of the four sessions `pilot2_sessions`, `pilot3c_sessions`, `pilot4_sessions`, `pilot5_sessions`. Not used: the confirmatory session (leakage), `pilot1` (cold-pool adapter, amendment A1), `pilot3_sessions` (aborted). Task ids and seeds are fixed by `build_batch`, so the table is exact for every task of this workload. A (task, pool) pair with no logged run fails the run (`KeyError`, no filling); the coverage is checked before the session starts (`scripts/study2_oracle_rows.py`, report printed).

**Conditions.** `O_EFT_E5_gpu` (oracle kernel times, GPU eligible); `O_EFT_E5_e2e_gpu` (oracle kernel times plus the measured task I/O and message terms of `e2e_terms_pilot2.json`, so the oracle sees the same costs as the real EFT); `O_EFT_E5_cpu` (oracle, no GPU); references `B4_gpu` (strongest non-predictive rule), `EFT_E1_noctx_gpu` (strongest predictive rule without the oracle), `B0_P_only`. All oracle variants use the no-context EFT (`EftNoContext`, amendment A5). Warm-up block 0, 12 blocks analysed, seed 20261401, reference `B4_gpu`, memory preflight 0.8 GB, AC power required.

**Primary contrast and decision rule (fixed now).** `O_EFT_E5_e2e_gpu` against `B4_gpu`, paired by block, Holm over the five contrasts against `B4_gpu`.
* **Headroom supported:** the contrast is at or below −5% with p_holm < 0.05. Then the next step is a global-planning rule (rank order, I/O-aware costs), written under its own section, and the ceiling is reported as the target.
* **Headroom not supported:** otherwise (including "not resolved", i.e. an interval that reaches zero or is wider than 5%). Then no further policy tuning on this workload; the study is written up with the oracle result as the finding.
* `O_EFT_E5_gpu` (kernel only) is secondary: it shows how much the I/O terms cost the oracle.

**Descriptive outputs (not confirmatory).** Makespan and scheduling time for every condition; the tasks placed per pool; the oracle against `EFT_E1_noctx_gpu`.

**Limits stated in advance.** The oracle table comes from four sessions on this machine, which drifted between sessions (not measured per session here); a faster oracle than a real rule is expected, since it never guesses wrong; a result of "supported" is a ceiling under EFT's per-task rule, not a claim about all schedulers.

Amendment A6 (2026-10-24, before the oracle session): the coverage check of section 14 FAILED on the four named sessions: 8 of the (task, eligible pool) pairs have no logged run (`aggregate` on E; `source_0` to `source_5` and `source_30` on E: the first tasks of a run always find an idle P worker, and `aggregate` always goes to P). Rule of section 14: no filling. Fix, stated before any oracle run: one coverage session (`design_study2_oracle_cover.json` sha256 `e383f8d3518e3e893f11d66906b3a5a59934ff417766522df8ff1a4858762ae9`, one condition `random_gpu`: random idle eligible worker, G allowed, 11 blocks with block 0 as warm-up, seed 20261402) whose logs are added to the oracle table as a fifth source session. It is an input to the oracle only, never an evaluation session. If a pair is still missing afterwards the oracle session is not run and the finding is reported as "oracle not buildable".

Frozen before the oracle session (2026-10-24): coverage session `oracle_cover_sessions/` complete (11 of 11 blocks); the table `oracle_rows.json` (sha256 `87e613a48cc99e5a169f4805736b366149b5708cae8eaadb292497165fd799ad`, 68,619 rows from five sessions: pilot2, pilot3c, pilot4, pilot5 and the coverage session) has 0 missing (task, pool) pairs. Oracle design `design_study2_oracle.json` sha256 `d973a30d30200553993b1060a0950d07183fe18f7b2ce8976435b2c562bda062`: 6 conditions (O_EFT_E5_gpu, O_EFT_E5_e2e_gpu, O_EFT_E5_cpu, B4_gpu, EFT_E1_noctx_gpu, B0_P_only), 13 blocks of which block 0 is the warm-up (12 analysed), seed 20261401, reference B4_gpu, adapter config unchanged (`15d4c3e9...`), e2e terms `e2e_terms_pilot2.json` (`dc1f3363...`). Decision rule: section 14, unchanged.

## 15. Result of oracle session 1 and amendment A7 (written 2026-10-24, after session 1, BEFORE oracle session 2)

Session `oracle_sessions/` (design `d973a30d...`): complete, 13 of 13 blocks, 78 runs verified; 72 in the primary analysis (6 warm-up runs excluded), analysis `analysis_oracle_ref_B4_gpu`. Mean makespan (s): B0_P_only 2.411, B4_gpu 1.742, EFT_E1_noctx_gpu 1.753, O_EFT_E5_gpu 2.270, O_EFT_E5_e2e_gpu 2.253, O_EFT_E5_cpu 2.469. Against B4_gpu: O_EFT_E5_e2e_gpu **+29.3%** (+27.7 to +30.8, p_holm 0.002), O_EFT_E5_gpu +30.1%, EFT_E1_noctx_gpu +0.58% (-1.24 to +2.71). **By the decision rule of section 14 the outcome of session 1 is "headroom not supported"** (the oracle contrast is not at or below -5%).

**But session 1 does not measure the ceiling.** The oracle was slower than the real rule because of its own computing cost: median scheduling time per run (`run_finished.scheduling_time_seconds`) was 1.28 to 1.34 s for the three oracle conditions against 0.054 s for EFT_E1_noctx_gpu and 0.016 s for B4_gpu, in runs of 1.7 to 2.3 s. Cause: `ReplayOracleEstimator.estimate` takes the median of every logged observation of the key (about 250 values, 68,619 rows) on every call, about 3,600 calls per run. The decisions are not the problem; the lookup is the same kind of implementation cost as the decision-context cost of amendment A5. Session 1 is kept and reported as it is.

**Amendment A7 (decided after seeing session 1; stated as such).** `CachedOracle` (`study2/policies.py`) computes the same per-key medians once and looks them up in constant time (test: identical numbers to `ReplayOracleEstimator`; `tests/test_study2.py`). Oracle session 2: design `design_study2_oracle2.json` sha256 `fd07a12f8816eeb3fa66c51e78fb64eb727a61482f689bef23b5d5dbf845388c`, same six conditions, same table (`87e613a4...`), same terms, same rule as section 14, seed 20261403, 13 blocks (12 analysed). **The decision of section 14 is taken on session 2**, because only it measures decisions rather than lookup cost; session 1 is reported next to it. A scheduling time of the oracle conditions above 0.2 s per run would again invalidate the measurement and is checked first.

## 16. Result of oracle session 2 and the decision (written 2026-10-24, AFTER the session; sections 1 to 15 are unchanged)

Session `oracle2_sessions/` (design `fd07a12f...`): complete, 13 of 13 blocks, 78 runs, all verified; 72 in the primary analysis (warm-up block excluded). Evidence manifest verified (0 missing, 0 changed, 0 extra); `reproduce_subset.py` re-derived summary and effects from the raw logs (`repro_oracle2_ref_B4_gpu.json`, `ok` true). Scheduling time per run is now 0.064 to 0.090 s for the oracle conditions (fixed by the cached lookup, amendment A7), so the measurement is valid. Mean makespan (s): B0_P_only 2.393, B4_gpu 1.773, EFT_E1_noctx_gpu 1.742, O_EFT_E5_gpu 1.733, O_EFT_E5_e2e_gpu 1.741, O_EFT_E5_cpu 1.879.

| contrast against B4_gpu | effect | interval | p_holm |
|---|---:|---|---:|
| O_EFT_E5_e2e_gpu (primary) | -1.74% | -3.84 to +0.08 | 0.29 |
| O_EFT_E5_gpu (secondary) | -2.14% | -4.03 to -0.63 | 0.025 |
| EFT_E1_noctx_gpu | -1.67% | -4.50 to +0.30 | 0.29 |
| O_EFT_E5_cpu | +5.93% | +2.70 to +9.53 | 0.016 |
| B0_P_only | +35.10% | +31.78 to +37.97 | 0.0035 |

**Decision (rule of section 14): headroom NOT supported.** The primary contrast is -1.74%, not at or below -5%, and not Holm-significant. Even an EFT that knows the true time of every task is at most about 2% better than the greedy rule B4 (best interval end -4.0%), and no better than the real EFT with the solo table (-1.67%). Under EFT's per-task rule, prediction accuracy has no room to help on this workload.

**Why (read from the logs, not tuned).** Worker utilisation (busy seconds / workers x makespan, `runs.csv`): B4_gpu 0.95, EFT_E1_noctx_gpu 0.92, O_EFT_E5_e2e_gpu 0.94, O_EFT_E5_gpu 0.94, against 0.39 for B0_P_only. The workers are already busy about 95% of the time, so no placement rule can pack the work much tighter. The "fluid lower bound" computed from the solo profile before this session (0.87 s kernel only, 1.03 s with I/O and IPC, `lb` analysis in the chat) was too optimistic: it used solo task times, but tasks run slower when 14 workers run together (for example the median `source` on P took 115 ms in a run against 85 ms solo, and `edges` on G about 11 ms against 0.84 ms), and the single CUDA worker queues. The earlier statement that about 40% headroom existed is withdrawn.

**What this implies for the project.** (1) On this uniform, saturated batch, prediction-aware placement beats fixed rules and ties greedy, and the oracle shows that tie is the ceiling for EFT-style rules. (2) Any future workload should pass the same gate before real predictors are built: run the oracle (cached lookup) against the best non-predictive rule; only if the oracle is at least 5% faster is there anything for a predictor to win. (3) Workloads where greedy placement is wrong (heavy-tailed task sizes, critical-path structure, idle capacity) are the candidates; this one is not.

## 17. Heavy-tailed workload and oracle gate (written 2026-10-24 BEFORE any run of it)

**Why.** Section 16: on the uniform batch the workers were busy 92 to 95% of the time and an EFT with true times was only about 2% better than greedy B4, so no predictor can win there. A placement rule has room when task sizes are very uneven: a FIFO rule may give a huge task to a slow E core or start it late, and a rule that knows sizes can start the big tasks first on the fast cores. This section tests that, with the oracle as the gate before any real predictor claim.

**Workload** (`study2/workload.py::build_mixed`): 48 small (256 px) and 16 big (1024 px) independent chains `source -> denoise (x8) -> edges -> features`, one `aggregate`; CPU pools P (6 workers) and E (7 workers) only (the idle CUDA worker stays in the pool and is never eligible). Solo profile (`profile_mix_20261024_profile.json`, sha256 `51fce7f10115fbe936c4d541f0d6c0a8006aa5ff81a50f653b3c77eac34fbc22`, merged by `scripts/study2_merge_profiles.py` from `profile_mix_t256` and `profile_mix_t1024`): chain P-core time about 21 ms small, 564 ms big (27 times), E core about 74 ms and 1586 ms (E/P 2.8 to 3.7). Two instances = two fixed orders of the chains (`order_a` seed 11, `order_b` seed 22) alternating by block, so one lucky order cannot decide.

**Rules compared.** Non-predictive: `B0_P_only` (static), `B3` (shortest queue), `B4` (first idle worker, P before E, FIFO), `B4_largest_first` (B4 with the ready queue ordered by task size, largest first; no time model: the size heuristic a predictor must beat; `study2/policies.py`). Predictive: `EFT_E1_noctx` (solo table), `EFT_E1_rank_noctx` (EFT with upward-rank ready order). Oracles (EFT with true kernel times, cached lookup; `O_EFT_E5`, `O_EFT_E5_rank`).

**Oracle table.** From a coverage session (`design_study2_mixed_cover.json` sha256 `8012fcbf27261a7b6d23943cc991c0c3ac3c929efb0675605bc06b36b65361ea`: conditions random, B4, B4_largest_first, EFT_E1_noctx; 11 blocks, block 0 warm-up; seed 20261501) whose logs feed the table only; coverage of every (task, eligible pool) of both orders is checked before the gate session (no filling; if a pair is missing the gate is "not buildable").

**Gate (decision rule fixed now).** Gate session: the eight conditions above, 15 blocks (block 0 warm-up, 14 analysed, 7 per order), memory preflight 0.8 GB, AC power. The **primary oracle** is the one of `O_EFT_E5`, `O_EFT_E5_rank` with the lower mean makespan in the gate session itself. The gate PASSES only if EVERY non-predictive rule (B0_P_only, B3, B4, B4_largest_first) is at least 5.3% slower than the primary oracle (paired effect of the rule against the oracle at or above +5.26%, i.e. the oracle at least 5% faster) with p_holm < 0.05 over the conditions of that analysis (`analyze_experiment.py --reference <primary oracle> --seed 0`). Scheduling time per run of the oracle conditions above 0.2 s invalidates the measurement (as in section 15) and is checked first.

**If the gate passes:** a separate section will pre-register the confirmatory test of the real predictors (`EFT_E1_noctx`, `EFT_E1_rank_noctx` and any pre-named variant) against the strongest non-predictive rule, with the oracle as the ceiling. **If the gate fails:** no real-predictor claim on this workload and no further workload variant without a new section written first; the oracle result is the finding. The real predictors run in the gate session as exploratory (descriptive) conditions only and have no role in the gate.

**Limits.** One machine; a synthetic DAG shape made of real stages; the oracle table comes from sessions of other policies on the same machine (load differs between policies); the sizes (16x pixels) and the counts (48 and 16) were chosen from the solo profile and the question, not from any run of this workload.

## 18. Hidden-cost workload and two-part oracle gate (written 2026-10-24 BEFORE any run of it; supersedes section 17)

**What happened to section 17.** Its coverage session (`mixed_cover_sessions/`, 44 runs) was run; its gate session was NOT. From the coverage logs (median makespan, s: B4 2.38, B4_largest_first 2.44, EFT_E1_noctx 2.32, random 2.41; worker utilisation 77 to 86% of 13 CPU workers; random placement within about 2% of B4) I judged that the 256/1024 px mix is again throughput-bound and that its pre-registered gate could not pass, and I did not spend the gate session on it. That judgment is mine, made from exploratory logs, not the pre-registered rule. The workload is dropped; this section is its one and only replacement, and **no further workload will be tried without a new section written first**. Every variant tried so far (uniform batch, 256/1024 mix) is reported in the final report.

**Idea.** A table keyed by (stage, size) and a rule that orders by size are both blind to a task parameter that changes the cost without changing the size. A learned predictor that sees the parameter is the case the project's intuition is about. Runtime of `img_denoise` is linear in its `iterations` parameter (Pillow blur repeated); the parameter is known when the task is ready (decision-time safe).

**Workload** (`study2/workload.py::build_iters`): 64 independent chains `source -> denoise (xN) -> edges -> features` at ONE image size (512 px), 48 chains with N = 2 and 16 with N = 120 (60 times the denoise work), one `aggregate`; CPU pools P (6) and E (7) only. Two instances = two fixed chain orders (`order_a` seed 11, `order_b` seed 22) alternating by block. `Task.seed` carries the chain's N so that the replay oracle's key (task id, seed, stage, size, pool) separates the same task id in different orders (no stage reads `Task.seed`).

**Rules.** *Blind* (no access to N): `B0_P_only`, `B3` (shortest queue), `B4` (first idle worker, P before E, FIFO), `EFT_E1_noctx` (solo table keyed by stage and size, profile of the 512 px batch at denoise x8, so it predicts the same denoise time for every chain). *Informed non-predictive heuristic:* `B4_param_first` (B4 with the ready queue ordered by the chain's N, largest first; `study2/model.py`): what a person who knows the parameter would write. *Learned predictors:* `EFT_iter_model_noctx` and `EFT_iter_model_rank_noctx` (EFT / rank-ordered EFT with `IterModelEstimator`: denoise time = a + b N per pool, least squares from the coverage logs by `scripts/study2_fit_iter_model.py`; all other stages the solo table). *Oracles:* `O_EFT_E5`, `O_EFT_E5_rank` (true times from the coverage logs, cached lookup).

**Coverage session.** `design_study2_iters_cover.json` sha256 `f032a853ac5112489b201c9ef2ee4df7e8c6d80e371ea6c9c306ef0706d03449`: random, B4, B4_param_first, EFT_E1_noctx; 11 blocks (block 0 warm-up), seed 20261601. Its logs give the oracle table and the denoise lines (never an evaluation session). Coverage of every (task, eligible pool) of both orders is checked; if a pair is missing, one extra random coverage session is added under an amendment (as A6); if still missing the gate is "not buildable".

**Gate session.** The nine rules above, 15 blocks (block 0 warm-up, 14 analysed, 7 per order), memory preflight 0.8 GB, AC power, seed fixed with the design. The **primary oracle** is the one of `O_EFT_E5`, `O_EFT_E5_rank` with the lower mean makespan in the gate session. Analysis: `analyze_experiment.py --reference <primary oracle> --seed 0`, Holm over the conditions of that analysis.
* **Gate A (does runtime information matter?)** PASSES only if EVERY blind rule (B0_P_only, B3, B4, EFT_E1_noctx) is at least 5.3% slower than the primary oracle (paired effect at or above +5.26%, i.e. oracle at least 5% faster) with p_holm < 0.05.
* **Gate B (is a hand rule enough?)** Not a pass/fail gate: the effect of `B4_param_first` against the primary oracle is reported; if it is below +5.26% or not significant, the statement is "an informed heuristic reaches the ceiling, so prediction replaces knowing the parameter, it does not beat knowing it".
* Scheduling time per run of the oracle conditions above 0.2 s invalidates the measurement (checked first).

**After the gate.** Gate A fails: no learned-predictor claim; the oracle result is the finding. Gate A passes: a separate section pre-registers the confirmatory test of `EFT_iter_model_*` against the blind rules and against `B4_param_first` (equivalence or superiority at the project's 2% margin), with the oracle as the ceiling. The learned predictors run in the gate session as descriptive conditions only and have no role in the gate.

**Limits.** One machine; synthetic DAG of real stages; the denoise-iterations cost was chosen because it is linear and known, the predictor is a one-feature line per pool (a deliberately minimal learned model); the oracle table comes from other policies' sessions (load differs); sizes and counts were fixed from the solo profile and the question before any run of this workload.

Amendment A8 (2026-10-24, before the gate session of section 18): the coverage session `iters_cover_sessions/` (11 of 11 blocks, 40 runs) is complete but leaves 12 (task, pool) pairs without a logged run (all on E, e.g. `denoise_58`, `edges_15`, `features_31`, `source_30`). As in A6: one extra random coverage session, `design_study2_iters_cover2.json` sha256 `2717379748e5830b5086c2bba4f954841c7560fee1310c0f6a3968585d2f3f31` (condition `random` only, 13 blocks of which block 0 is the warm-up, seed 20261602), whose logs join the oracle table; the denoise line is fitted from both coverage sessions. Exploratory reading of the first coverage session (not the gate; medians of 10 runs, s): B4 3.94, B4_param_first 3.10, EFT_E1_noctx 5.53 (the blind table predicts the same denoise time for every chain and places badly), random 3.99; fitted denoise lines under load: P 2.3 ms + 7.4 ms x N, E 3.0 ms + 18.4 ms x N. The gate of section 18 is unchanged.

Amendment A9 (2026-10-24, before the gate session): after A8 the oracle table still has 9 uncovered (task, pool) pairs (`denoise_58`, `edges_41`, `features_15`, `features_41`, `features_57`, `features_59`, `source_30` to `source_32`, all on E: late, short tasks are dispatched when mostly P workers are idle, so E placements of them are rare under the rules run so far). Section 18 says an uncovered pair makes the gate "not buildable"; I relax that rule once more, in the same way and for the same reason as A6 and A8, because it costs minutes and no gate data exist yet (so the relaxation cannot depend on any outcome): a third random coverage session, `design_study2_iters_cover3.json` sha256 `8cf3b75b4f4b0ecbf66ae372e6e99c0d3c347b86d6ec06090633c6fb79dd56cd` (condition `random` only, 31 blocks of which block 0 is the warm-up, seed 20261604). If any pair is still uncovered after it, the gate is "not buildable" and stops there. The unused gate design `design_study2_iters_gate.json` (built with the incomplete table) is never run and is replaced by one built from the final table.

Amendment A10 (2026-10-24, before the gate session): after A9 (31 random blocks) 5 pairs are still uncovered (`denoise_58`, `features_15`, `features_57`, `features_59`, `source_31`, all on E). Reason read from the logs: under random placement a short task is released when its predecessor finishes and is dispatched to the one idle worker, usually of the same pool as its predecessor, so chains stay on the pool where they started and some (task, E) pairs never occur. Last relaxation: one coverage session in which every task runs on the E pool (`B0_E_only`), `design_study2_iters_cover4.json` sha256 `d36d7127d2e0a5f6763078a0fe6029b00150d1395293ccf6df18f40c39d41987` (7 blocks, block 0 warm-up, seed 20261605). Its E times are measured with only E workers busy, so the oracle's E medians mix two load patterns; this is stated as a limit of the oracle. If any pair is still uncovered after it the gate is "not buildable" and nothing further is run. The coverage procedure was fixed before any gate data existed and does not depend on any outcome.

Frozen before the gate session (2026-10-24): coverage complete after four sessions (`iters_cover_sessions`, `iters_cover2_sessions`, `iters_cover3_sessions`, `iters_cover4_sessions`): oracle table `oracle_rows_iters.json` sha256 `55191995a689b8b58305becd8da914e3a22ee557a9c0e67b5a7a2bdb601ceeac`, 22,616 rows, 0 missing (task, pool) pairs; denoise lines `iter_model_cover1234.json` sha256 `160388f0cce4d4e453a1c2b7852071fba710dd19ddf9c6d58a5f3fab1118ae37` (E: 1.94 ms + 19.04 ms x N, P: 2.08 ms + 7.61 ms x N, fitted from the same four sessions, never from the gate session). Gate design `design_study2_iters_gate_final.json` sha256 `e0fc24888e4d350e68aec049e565c00bfaea566891bab012fa92cf7789f760ba`: the nine rules of section 18, 15 blocks (block 0 warm-up, 14 analysed, 7 per order), seed 20261606, memory preflight 0.8 GB. The earlier file `design_study2_iters_gate.json` (incomplete table) was never run. Decision rules: section 18, unchanged.


## 19. Gate result (section 18) and pre-registration of the confirmatory session (written 2026-10-24; the gate result is read first, the confirmatory design is frozen BEFORE its first block)

### 19.1 Gate session result

Session `iters_gate_sessions/` (design `e0fc2488...`): complete, 15 of 15 blocks, 135 runs, all verified; 126 in the primary analysis (warm-up block excluded). Scheduling time per run of the oracle and learned conditions 0.059 to 0.063 s (below the 0.2 s limit, so the measurement is valid). Mean makespan over both orders (s): B4_param_first 3.385, EFT_iter_model_rank_noctx 3.437, O_EFT_E5_rank 3.755, EFT_iter_model_noctx 3.893, O_EFT_E5 3.980, B4 4.081, B0_P_only 4.174, EFT_E1_noctx 6.008, B3 6.904. Primary oracle (lower mean) = `O_EFT_E5_rank`. Analysis with that reference (`analysis_iters_gate_ref_O_EFT_E5_rank`, 14 blocks):

| rule | effect vs primary oracle | interval | p_holm | needed |
|---|---:|---|---:|---|
| B0_P_only (blind) | +11.02% | +7.28 to +14.68 | 0.0018 | at least +5.26% and p_holm < 0.05: yes |
| B3 (blind) | +81.92% | +72.91 to +92.66 | 0.0014 | yes |
| B4 (blind) | +8.86% | +5.56 to +12.22 | 0.0044 | yes (interval lower end 5.56) |
| EFT_E1_noctx (blind table predictor) | +57.75% | +44.68 to +71.76 | 0.0008 | yes |

**Gate A PASSES**: every blind rule is at least 5.3% slower than the oracle, Holm-significant.

**Gate B (reported, not a gate):** `B4_param_first` is **10.33% faster than the oracle** (-13.46 to -6.29, p_holm 0.0044). The informed heuristic reaches and passes the oracle EFT. So the oracle is not a ceiling for every scheduler on this workload: its table mixes load patterns (the E-only coverage session and the random sessions) and EFT's per-task rule is not optimal here. The statement of section 18 applies: an informed heuristic reaches the ceiling, so prediction replaces knowing the parameter, it does not beat knowing it.

Descriptive, against B4 (14 blocks): B4_param_first -17.63%, EFT_iter_model_rank_noctx -16.15% (-19.20 to -12.46), EFT_iter_model_noctx -4.82%, O_EFT_E5_rank -8.14%, B0_P_only +1.99% (not significant), EFT_E1_noctx +44.92%, B3 +67.12%. Paired sd of the log ratio of EFT_iter_model_rank_noctx against B4_param_first: 0.0975 (mean +1.79%). Also worth stating: the BLIND table predictor is 45% worse than blind greedy B4. A predictor that is wrong about a hidden cost is worse than no predictor.

### 19.2 Confirmatory session (pre-registration)

Design `design_study2_iters_confirm.json` sha256 `e9f2058760e8ecc3d7d1d795353905b92507c7d3d08de544ffc9cd75cb4f97dc`; adapter config unchanged (`15d4c3e9...`); denoise lines `iter_model_cover1234.json` (sha256 `160388f0cce4d4e453a1c2b7852071fba710dd19ddf9c6d58a5f3fab1118ae37`, fitted from the four coverage sessions only); profile `profile_t512` (denoise x8 solo table, as in the gate). Same workload as section 18 (64 chains, 48 with N = 2 and 16 with N = 120, 512 px, CPU pools), but **two chain orders never seen by any earlier session**: `order_c` seed 33 and `order_d` seed 44, alternating by block. Seed 20261701, **37 blocks (block 0 warm-up, 36 analysed, 18 per order)**, memory preflight 0.8 GB, AC power.

Conditions (6): `B0_P_only` (static, blind), `B4` (greedy, blind; session reference), `EFT_E1_noctx` (blind table predictor), `B4_param_first` (informed heuristic), `EFT_iter_model_noctx` and `EFT_iter_model_rank_noctx` (learned predictor, early binding without and with rank-ordered ready queue). The oracles are not in this session (their table is keyed by the chain orders of the coverage sessions and would not apply to new orders).

**Block count.** Paired sd of the log ratio in the gate session for the contrasts of interest: 0.034 to 0.098 (EFT_iter_model_rank_noctx against B4_param_first 0.0975). The rule of section 4 (n = ceil(((1.96 + 0.84) sd / ln(1 + m))^2)) gives 32 blocks for a +-5% equivalence margin at sd 0.0975, and about 190 for the 2% margin used in sections 12 to 16. The 2% margin is out of reach here, so **the equivalence margin of this section is +-5%** (stated and justified now), with 36 analysed blocks.

**Analyses (committed now; no others are confirmatory).** `scripts/analyze_experiment.py --seed 0` twice on the session: A with reference `B4` (output `analysis_iters_confirm_ref_B4`), B with reference `EFT_iter_model_rank_noctx` (output `analysis_iters_confirm_ref_EFT_iter_model_rank_noctx`); Holm over the conditions of each analysis; metric makespan; exclusions as in `EVALUATION_PROTOCOL.md` section 12.5; scheduling time per run reported beside it.

**Pre-stated predictions (from the gate session); wording "supported", "not supported", "not resolved by this design":**
* P1: `EFT_iter_model_rank_noctx` is faster than `B4` by 10% to 22%, Holm-significant.
* P2: `EFT_iter_model_rank_noctx` is faster than `EFT_E1_noctx` (blind table predictor) by 30% to 55%, Holm-significant.
* P3: `EFT_iter_model_rank_noctx` is faster than `B0_P_only` by 10% to 25%, Holm-significant.
* P4: `EFT_iter_model_rank_noctx` is equivalent to `B4_param_first`: the whole 95% interval of the paired effect lies inside +-5% (supported); an interval that reaches outside is "not resolved" or, if it lies entirely beyond 5%, "not supported".
* P5: rank ordering helps: `EFT_iter_model_rank_noctx` is faster than `EFT_iter_model_noctx` by 8% to 16%, Holm-significant.
* P6 (descriptive, no test of its own): `EFT_E1_noctx` is slower than `B4` by 30% to 60%.

**What the claims mean.** "A learned predictor that sees the task parameter beats blind scheduling" is supported only if P1, P2 and P3 are all supported. "It matches an informed hand heuristic" is supported only if P4 is. Nothing else is confirmatory.

**Limits (stated in advance).** One machine; a synthetic chain set of real stages; the learned model is a one-feature line per pool, fitted on coverage logs of the same machine; the workload shape and block count were fixed from the gate session; the gate's oracle is not a ceiling here (the heuristic beat it), so no "distance to optimal" claim is made.


## 20. Result of the confirmatory session (written 2026-10-24, AFTER the session and its analyses; sections 1 to 19 are unchanged)

Session `iters_confirm_sessions/20261024T211614` (design `e9f20587...`, matches section 19): complete, 37 of 37 blocks, 222 runs, all with status ok, output verified and event-log hash matching; 216 in the primary analysis (the 6 excluded are the warm-up block). Evidence manifest verified (0 missing, 0 changed, 0 extra); `reproduce_subset.py` re-derived summary and effects tables from the raw logs for both pre-registered analyses (`repro_analysis_iters_confirm_ref_B4.json`, `repro_analysis_iters_confirm_ref_EFT_iter_model_rank_noctx.json`, all checks `ok`). Power: the session ran on mains power (the wait-for-charger check passed at 21:16:13 local, one minute after the Windows System log shows the charger connected at 21:16:09; the log has no further power event until the session ended at 21:33:54). Scheduling time per run: learned conditions 0.062 to 0.063 s, B4 0.189 s, EFT_E1_noctx 0.053 s. Mean makespan (s): B4_param_first 3.360, EFT_iter_model_rank_noctx 3.571, EFT_iter_model_noctx 3.906, B4 4.148, B0_P_only 4.613, EFT_E1_noctx 5.706.

| prediction | contrast | effect | interval | p_holm | predicted | outcome |
|---|---|---:|---|---:|---|---|
| P1 | EFT_iter_model_rank_noctx vs B4 | -13.78% | -16.22 to -11.37 | 0.0005 | -10 to -22% | **supported** |
| P2 | EFT_iter_model_rank_noctx vs EFT_E1_noctx | -36.8% (reference table: E1 table is +58.14%, 50.06 to 66.65) | -33.4 to -40.0 | 0.0005 | -30 to -55% | **supported** |
| P3 | EFT_iter_model_rank_noctx vs B0_P_only | -22.5% (reference table: static is +29.02%, 26.64 to 31.15) | -21.0 to -23.8 | 0.0005 | -10 to -25% | **supported** |
| P4 | EFT_iter_model_rank_noctx vs B4_param_first | +6.3% (reference table: heuristic is -5.91%, -7.62 to -4.04) | +4.2 to +8.2 | 0.0005 | equivalent within +-5% | **not resolved** (the interval reaches outside +-5% and is not entirely beyond it; the heuristic is faster) |
| P5 | EFT_iter_model_rank_noctx vs EFT_iter_model_noctx | -8.6% (reference table: no-rank is +9.37%, 7.46 to 11.36) | -6.9 to -10.2 | 0.0005 | -8 to -16% | **supported** |
| P6 | EFT_E1_noctx vs B4 | +36.35% | +28.93 to +43.82 | 0.0005 | +30 to +60% | descriptive: as predicted |

(Percentages for P2, P3, P5 are converted from the reference-EFT table: speed of the learned rule = 1 / (1 + effect of the other rule); intervals converted the same way.) Other contrasts against B4: B4_param_first -18.87% (-20.77 to -17.02), EFT_iter_model_noctx -5.70% (-7.49 to -3.87), B0_P_only +11.25%. The 80%-power minimum detectable effect is 2.7% to 8.3% (the table predictor, whose runs vary most, 7.95%).

**Confirmatory claims (wording fixed in section 19).**
* **(a) "A learned predictor that sees the task parameter beats blind scheduling": SUPPORTED.** P1, P2 and P3 are all supported, on chain orders that no earlier session used. The learned, rank-ordered EFT is 13.8% faster than blind greedy B4, 22.5% faster than the static P-only rule and 36.8% faster than the table predictor that cannot see the parameter.
* **(b) "It matches an informed hand heuristic": NOT RESOLVED, with the direction against it.** The hand rule that orders the chains by the known parameter is about 5.9% faster than the learned predictor (+6.3% in the learned predictor's makespan), a significant difference at 36 blocks; the pre-registered +-5% equivalence interval is not met.
* Descriptive and reported plainly: the table predictor, wrong about a hidden cost, is 36% slower than blind greedy B4 (P6); rank ordering adds a further 8.6% over the same predictor (P5); the learned predictor places 180 of 257 tasks on the slow E cores and 77 on P (B4: 50 on E), i.e. it uses the slow cores for the cheap tasks and keeps the fast cores for the 16 big chains.

**What it means.** On a workload where runtime depends on a parameter that a size-keyed table cannot see, a predictor that learned the dependence from logs makes placement 14% to 37% faster than every rule that cannot see it, and the table-based prediction used in stages 1 to 5 hurts. So the project's idea (prediction-aware placement helps) holds when prediction carries information the other rules lack. It does not beat a person who already knows which parameter matters and sorts by it; prediction replaces that knowledge, and here the replacement is about 6% slower than the original.

**Limits (as stated in section 19, unchanged).** One machine; synthetic chains of real stages; the learned model is a one-feature line per pool fitted on coverage logs of the same machine; the equivalence margin is +-5% because 2% needs about 190 blocks; no distance-to-optimal claim.


## 21. Permanent fixes and policy development (written 2026-10-25 BEFORE the development session)

**Root cause, read from the logs (not tuned).** On the hidden-cost workload (section 18) the learned rank-ordered EFT is 13.8% faster than blind greedy but about 6% slower than the hand rule that only sorts by the parameter and places greedily on an idle worker. The predictor is not the weak part (hold-out median absolute percentage error 3% to 16% per stage, `param_model_cover1234.json`, evaluated on the confirmatory logs the fit never saw). The difference is in how the prediction is USED: EFT binds early (a task is queued behind a busy worker on the model's say-so) and places by a per-task finish estimate, so it is not work-conserving; the hand rule is. Stage 5 had already isolated the cost of early binding on Montage (`B0_P_early`, +1.7%). Literature points the same way: at high utilisation the processing ORDER matters more than the accuracy of the estimates (Ilyushkin and Epema, CCGrid 2018, abstract); HEFT driven by a predicted-runtime model reaches within about 5% of HEFT with perfect runtimes (Lotaru, arXiv 2309.06918, abstract). So the permanent fix is in the policy architecture, not in a heavier model: use predictions to ORDER and to choose among IDLE workers, never to leave a worker idle except for a bounded, measured gain.

**Permanent guards (code, all tested; none depends on a particular result).**
1. `study2/param_model.py` + `scripts/study2_train_param_model.py`: one generic learned model. Features are the numeric task parameters that vary in the training logs, chosen from the data (never typed); a stage whose parameters never vary gets the mean. A new workload, a new machine or a new pool (e.g. a Raspberry Pi) is retrained by one command from a coverage session, no code change; an unseen (workload, pool) is a `KeyError`, never a guess. Replaces the one-feature `IterModelEstimator` for all later work.
2. Decision-time budget test (`tests/test_study2.py::test_policy_decision_time_stays_inside_the_budget`): every study 2 policy decides in under 0.5 ms per task on 14 workers with full activity histories. Would have failed the three implementation costs found so far (context logging, the oracle's per-call median, a per-candidate heavy model).
3. Scheduling-cost guard in the adapter: a run whose scheduling time exceeds 25% of its makespan is recorded as failed, not as a result (`max_scheduling_fraction`).
4. `require_ac_power` in the design file: the runner aborts on battery before the session and before every block (`experiment/runner.py`, default off so old designs are unchanged; `tests/test_study2.py`).
5. `docs/research_redesign/claims.json` + `tests/test_claims.py`: every claim with its status and the stored number behind it; the test fails if a number or a status drifts from its `effects.csv`.
6. Same worker pool for every condition (amendment A1) and the cached oracle (A7) stay as they are.

**New policy.** `PredictedRankGreedy` (`study2/policies.py`): ready queue ordered by upward rank from the model's predicted times (as `RankEftScheduler`), LATE binding (a task goes only to an idle worker, the one with the smallest predicted time), no decision-context logging. Variant `PRED_RANK_HOLD`: a task is held when waiting for the best busy worker's predicted finish beats the best idle worker's time by more than `hold_min_s = 0.010` s (about twice the measured per-task I/O plus message cost of 3 to 8 ms, `e2e_terms_pilot2.json`; fixed now, not tuned). Existing candidates reused unchanged: `EFT_param_model_rank_noctx` (the section 20 policy with the generic model), `HEFT_param_model` and `PEFT_param_model` (static plans from the same predicted costs; they see a global picture, which a per-task rule cannot).

**Development session (exploratory, its only job is to select ONE candidate).** Design `design_study2_iters_dev2.json` sha256 `5d624bac03a9a7a657a0df803c8c03f47836a49247b8ff4b9686566babccae37`; model `param_model_cover1234.json` sha256 `19177cfcfeae3221735fa4f2dc4f9ca6de2fb550214356fd176ac651db6bec67` (fitted from the four coverage sessions of section 18, never from the development or confirmatory sessions); profile `profile_t512`; the workload of section 18 on the chain orders `order_a`, `order_b`; seed 20261801; 15 blocks (block 0 warm-up, 14 analysed); `require_ac_power`; 7 conditions: references `B4` and `B4_param_first`, candidates `EFT_param_model_rank_noctx`, `HEFT_param_model`, `PEFT_param_model`, `PRED_RANK_GREEDY`, `PRED_RANK_HOLD`. **Selection rule (fixed now):** the candidate with the lowest mean makespan over the analysed blocks; candidates within 1% of the lowest are ties and the simplest wins, simplicity order `PRED_RANK_GREEDY` < `PRED_RANK_HOLD` < `EFT_param_model_rank_noctx` < `HEFT_param_model` < `PEFT_param_model`. Nothing else is decided from this session, and its numbers are not used as results.

**Confirmatory session (section 22, written after the selection and BEFORE its first block).** The selected candidate against `B4`, `B4_param_first`, `B0_P_only` and the blind table predictor `EFT_E1_noctx`, on two chain orders never used before (`order_e` seed 55, `order_f` seed 66), 37 blocks, with predictions fixed in section 22. If no candidate is within 5% of the hand rule in the development session, the section 20 result stands as the project's result and the claims file is not changed.

**Limits.** One machine; synthetic chains of real stages; the candidate set and the hold constant were fixed before any run of this section; the development session selects, it does not confirm.


## 22. Development session 1 result, amendment A11 and development session 2 (written 2026-10-25; the second session is pre-registered BEFORE it runs)

### 22.1 Result of the development session of section 21

Session `iters_dev2_sessions/` (design `5d624bac...`): complete, 15 of 15 blocks, 105 runs; 90 runs status ok and verified, **15 runs (every `PRED_RANK_HOLD` run) recorded as failed by the scheduling-cost guard** (scheduling time 1.97 s in a 4.28 s run, 46% of the makespan, limit 25%); 84 runs in the primary analysis (the warm-up block and the failed runs excluded). Mean makespan over both orders (s): B4_param_first 3.189, **PRED_RANK_GREEDY 3.198**, HEFT_param_model 3.320, EFT_param_model_rank_noctx 3.403, PEFT_param_model 3.886, B4 4.042. Paired effect against B4: B4_param_first -21.07% (-22.54 to -19.60), PRED_RANK_GREEDY -20.84% (-22.59 to -19.22), HEFT_param_model -17.92%, EFT_param_model_rank_noctx -15.77%, PEFT_param_model -3.89%. Scheduling time per run: B4 0.20 s, B4_param_first 0.18 s, PRED_RANK_GREEDY 0.10 s, EFT_param_model_rank_noctx 0.20 s, HEFT 0.03 s, PEFT 0.04 s.

**Selection (rule of section 21): `PRED_RANK_GREEDY`** (lowest mean of the valid candidates; the next, HEFT_param_model, is 3.8% higher, so there is no tie). It is **equivalent to the hand rule in this session (3.198 s against 3.189 s, +0.3%)**, and no candidate is faster than the hand rule. The generic learned model with predicted ORDER and work-conserving PLACEMENT removes the 6% that the section 20 EFT lost to the hand rule. This is a development result, not a confirmation.

### 22.2 Why the hold variant failed, and amendment A11

The failure is a design cost, not a policy result: with a hold, a task that waits stays in the ready queue and the coordinator re-asks the policy about it on every dispatch pass; the first implementation also re-estimated the predicted remaining time of every busy worker for each of those calls (order of ready tasks x busy workers per pass). The scheduling-cost guard of section 21 did its job and marked every run invalid. **Amendment A11 (implementation fix, decided after seeing this):** `PredictedRankGreedy.order_ready` computes, once per dispatch pass, the soonest predicted free time of each pool; `select_worker` then needs a few dictionary lookups and skips the hold test for a task cheaper than the hold margin (it cannot gain more than it costs). Same hold rule and the same constant (0.010 s); one stated approximation (workers bound within the same pass are not added to the cache). Test: `tests/test_study2.py::test_hold_policy_waits_for_a_much_faster_busy_worker_only` and the decision-time budget test (both variants under 0.5 ms per decision).

### 22.3 Development session 2 (pre-registration)

Design `design_study2_iters_dev3.json` sha256 `098646f03708f7c67dd00d6bdd41089613c8e4018fd9d7f9f764151c4c480b70`, model `param_model_cover1234.json` (`19177cfc...`, unchanged), chain orders `order_a`, `order_b`, seed 20261802, 15 blocks (block 0 warm-up), `require_ac_power`, 4 conditions: `B4`, `B4_param_first`, `PRED_RANK_GREEDY`, `PRED_RANK_HOLD` (efficient version). **Selection rule (fixed now):** `PRED_RANK_HOLD` replaces `PRED_RANK_GREEDY` only if its mean makespan is at least 1% lower AND no run of it is flagged by the cost guard; otherwise `PRED_RANK_GREEDY` stays the selected policy (the simpler one). The selected policy goes to the confirmatory session of section 23 (written after this selection and before its first block): against `B4`, `B4_param_first`, `B0_P_only` and the blind table predictor `EFT_E1_noctx`, on two chain orders never used before (`order_e` seed 55, `order_f` seed 66).


## 23. Result of development session 2, selection, and pre-registration of the confirmatory session (written 2026-10-25; the design is frozen BEFORE its first block)

### 23.1 Development session 2 result and selection

Session `iters_dev3_sessions/` (design `098646f0...`): complete, 15 of 15 blocks, 60 runs, all status ok and verified, none flagged by the cost guard; 56 in the primary analysis. Mean makespan (s): B4_param_first 3.228, **PRED_RANK_GREEDY 3.246**, PRED_RANK_HOLD 3.280, B4 4.091. Against B4: B4_param_first -20.99%, PRED_RANK_GREEDY -20.53% (-21.87 to -19.05), PRED_RANK_HOLD -19.72% (-21.51 to -17.59). Scheduling time per run: PRED_RANK_GREEDY 0.093 s, PRED_RANK_HOLD 0.355 s, B4 0.186 s. **Selection (rule of section 22): `PRED_RANK_GREEDY`.** The hold variant is not 1% faster than the greedy (it is 1.0% slower) and costs four times the scheduling time, so the bounded hold gives nothing here; it stays in the code as a documented negative result. Paired sd of the log ratio of PRED_RANK_GREEDY against B4_param_first in the two development sessions: 0.027 and 0.017 (mean +0.29% and +0.59%).

### 23.2 Confirmatory session (pre-registration)

Design `design_study2_iters_confirm2.json` sha256 `7aa921033b4bc827df02f00274edecce2bd60a212869e038569a9fdf5609bbd1`; adapter config unchanged (`15d4c3e9...`); generic model `param_model_cover1234.json` sha256 `19177cfc...` (fitted from the four coverage sessions of section 18 only); profile `profile_t512`. The workload of section 18 on **two chain orders never used by any earlier session**: `order_e` seed 55 and `order_f` seed 66, alternating by block. Seed 20261901, **31 blocks (block 0 warm-up, 30 analysed, 15 per order)**, `require_ac_power`, memory preflight 0.8 GB. Conditions (5): `B4` (blind greedy; session reference), `B4_param_first` (informed hand rule), `B0_P_only` (static), `EFT_E1_noctx` (blind table predictor), `PRED_RANK_GREEDY` (the selected policy: learned generic model, predicted-rank order, work-conserving placement).

**Block count.** Paired sd of the log ratio of the contrast of interest in the development sessions 0.017 to 0.027; the rule of section 4 gives 15 blocks for a +-2% equivalence margin at sd 0.027; 30 are used. The equivalence margin is the project's +-2% (section 19 had to widen it to 5% because the paired sd was 0.10; it is 4 times smaller here).

**Analyses (committed now; no others are confirmatory).** `scripts/analyze_experiment.py --seed 0` twice: A with reference `B4` (`analysis_iters_confirm2_ref_B4`), B with reference `PRED_RANK_GREEDY` (`analysis_iters_confirm2_ref_PRED_RANK_GREEDY`); Holm over the conditions of each analysis; metric makespan; exclusions as in section 12.5 of `EVALUATION_PROTOCOL.md` plus any run flagged by the scheduling-cost guard (kept in the raw data); scheduling time per run reported.

**Pre-stated predictions (from development sessions 1 and 2):**
* P1: `PRED_RANK_GREEDY` is faster than `B4` by 17% to 24%, Holm-significant.
* P2: `PRED_RANK_GREEDY` is faster than `B0_P_only` by 20% to 35%, Holm-significant.
* P3: `PRED_RANK_GREEDY` is faster than `EFT_E1_noctx` (blind table predictor) by 30% to 55%, Holm-significant.
* P4: `PRED_RANK_GREEDY` is equivalent to `B4_param_first`: the whole 95% interval of the paired effect lies inside +-2% (supported); an interval that reaches outside +-2% is "not resolved", entirely outside "not supported". **No superiority over the hand rule is predicted.**

**What the claims mean.** "A learned predictor (generic model that finds the parameter by itself from logs, used for ordering and idle-worker placement) beats blind and static scheduling" is supported only if P1, P2 and P3 are all supported. "It reaches the informed hand rule without being told the parameter" is supported only if P4 is. Nothing else is confirmatory.

**Limits (stated in advance).** One machine; synthetic chains of real stages; the model was trained on coverage logs of the same machine and the same stages; the policy and the hold constant were fixed before the confirmatory data; the development sessions selected, they do not confirm; a result of "equivalent to the hand rule" is a result about this workload (one hidden parameter), not a claim about every hidden-cost workload.


## 24. Result of the second confirmatory session (written 2026-10-25, AFTER the session and its analyses; sections 1 to 23 are unchanged)

Session `iters_confirm2_sessions/20261024T235434` (design `7aa92103...`, matches section 23): complete, 31 of 31 blocks, 155 runs, all with status ok, output verified and event-log hash matching, none flagged by the cost guard; 150 in the primary analysis (warm-up block excluded). Evidence manifest verified (0 missing, 0 changed, 0 extra); `reproduce_subset.py` re-derived the summary and effects tables from the raw logs for both pre-registered analyses (`repro_analysis_iters_confirm2_ref_B4.json`, `repro_analysis_iters_confirm2_ref_PRED_RANK_GREEDY.json`, all checks `ok`). Mean makespan (s): B4_param_first 3.110, PRED_RANK_GREEDY 3.161, B4 3.971, B0_P_only 4.046, EFT_E1_noctx 5.668. Scheduling time per run: PRED_RANK_GREEDY 0.094 s, B4_param_first 0.171 s, B4 0.187 s, B0_P_only 0.137 s, EFT_E1_noctx 0.053 s. The power guard (`require_ac_power`) was on; the laptop was on mains for the whole session (wait-for-charger check passed before the first block).

| prediction | contrast | effect | interval | p_holm | predicted | outcome |
|---|---|---:|---|---:|---|---|
| P1 | PRED_RANK_GREEDY vs B4 | -20.39% | -21.24 to -19.26 | 0.0004 | -17 to -24% | **supported** |
| P2 | PRED_RANK_GREEDY vs B0_P_only | -21.9% (reference table: P-only is +28.08%, 26.07 to 29.47) | -22.8 to -20.7 | 0.0004 | -20 to -35% | **supported** |
| P3 | PRED_RANK_GREEDY vs EFT_E1_noctx | -42.9% (reference table: table predictor is +75.19%, 64.34 to 86.21) | -46.3 to -39.2 | 0.0004 | -30 to -55% | **supported** |
| P4 | PRED_RANK_GREEDY vs B4_param_first | +1.6% (reference table: hand rule is -1.54%, -2.88 to -0.64) | +0.6 to +3.0 | 0.0004 | equivalent within +-2% | **not resolved** (the interval reaches outside +-2%; the hand rule is faster by about 1.5%, a significant difference that is smaller than the project's 2% margin) |

(P2 to P4 converted from the reference-PRED table: speed of PRED = 1 / (1 + effect of the other rule); intervals converted the same way.)

**Confirmatory claims (wording of section 23).**
* **"A learned predictor (a generic model that finds the parameter by itself from logs, used for ordering and idle-worker placement) beats blind and static scheduling": SUPPORTED** (P1, P2 and P3), on chain orders never used before: 20.4% faster than blind greedy B4, 21.9% faster than static P-only, 42.9% faster than the table predictor that cannot see the parameter. Development sessions 1 and 2 gave the same picture (-20.8% and -20.5% against B4).
* **"It reaches the informed hand rule without being told the parameter": NOT RESOLVED**, with the direction against it by about 1.5% (0.6% to 3.0%). The previous policy (section 20, EFT with early binding) was about 6% behind the hand rule; ordering by predicted rank with work-conserving placement removes about three quarters of that gap, not all of it.

**What the remaining 1.5% is (read from the logs, not tuned).** Both policies place the same number of tasks per pool (P 176, E 81) and 7 of the 16 big denoise tasks on the slow E cores; the hand rule starts its first big task 11 ms earlier on average (0.204 s against 0.215 s) and finishes the last big task about 45 ms earlier (2.62 s against 2.67 s). The ordering by the exact parameter is, within the limit of the model's error (hold-out median absolute percentage error 3% to 16% per stage), the ordering the model approximates. No policy tried so far, including HEFT (3.32 s) and a bounded hold (3.28 s), is faster than the hand rule in any session; the hand rule is a very strong baseline on this workload because the information that matters is exactly the parameter it sorts by.

**What it means.** The project's claim is now implemented and confirmed twice on this workload (section 20 and this section): a learned, data-driven predictor makes scheduling 14% to 43% faster than every rule that cannot see the hidden cost, with 0.09 s of scheduling time per run, and it gets within about 1.5% of a rule that is handed the key parameter by a person. It does not beat that rule.


## 25. Retraining on a changed resource configuration (written 2026-10-25; the pilot is exploratory and is run after this section is committed)

**Why.** The claim of section 24 is only worth something if the model does not have to be rebuilt by hand whenever the resources change (a new machine, a new pool such as a Raspberry Pi). The permanent part of the fix is the generic model plus a one-command retraining path. This section tests that path on a changed configuration that exists on this machine: **2 P-core workers and 7 E-core workers** (the scarce-fast-core configuration of stage 5; `max_p_slots` 2) instead of 6 P and 7 E.

**Retraining (done, no code change).** `python scripts/study2_retrain.py retrain_p2 adapter_config_study2_p2.json profile_t512 --random-blocks 13 --e-blocks 7 --seed 31` wrote two coverage designs, ran them on the 2-P configuration (the worker-ready events of the logs show 2 P, 7 E, 1 idle G worker), and fitted the generic model: `retrain_p2/param_model.json`. The fitted groups are the same as for the 6-P configuration; the model again found `iterations` as the only varying parameter, for `img_denoise` only, by itself (`study2_train_param_model.py` output in `retrain_p2.stdout.txt`). Both sessions completed (13 and 7 blocks). Training MAE per group is 0.01 to 20 ms (img_source on E 20.0 ms, img_denoise on E 8.2 ms).

**Pilot (exploratory).** Design `design_study2_iters_p2_pilot.json` (sha256 `c234f225c5b88fe687397e278edd88d31fe644c4095eb912bf5cd6edae9e9617`): the workload of section 18, the chain orders `order_a`, `order_b`, the 2-P configuration (adapter config `adapter_config_study2_p2.json`), the retrained model, 9 blocks (block 0 warm-up), seed 20262001, `require_ac_power`; conditions `B4`, `B4_param_first`, `PRED_RANK_GREEDY`, `PRED_RANK_HOLD`. Its only job is to give the predictions and the block count of the confirmatory session (section 26, written after it and before that session's first block). It is not a result.


## 26. Pilot result for the 2-P-core configuration and pre-registration of its confirmatory session (written 2026-10-25; the design is frozen BEFORE its first block)

### 26.1 Pilot result (exploratory)

Session `iters_p2_pilot_sessions/` (design `c234f225...`): complete, 9 of 9 blocks, 36 runs, all status ok and verified; 32 in the primary analysis. Mean makespan over both orders (s), 2 P + 7 E workers, model retrained for this configuration: PRED_RANK_GREEDY 4.847, B4_param_first 4.874, B4 6.078, PRED_RANK_HOLD 6.137. Against B4: PRED_RANK_GREEDY -20.25% (-20.53 to -19.99), B4_param_first -19.80% (-20.10 to -19.49), PRED_RANK_HOLD +0.99%. Paired sd of the log ratio of PRED_RANK_GREEDY against B4_param_first 0.0056 (mean -0.57%, 8 blocks). The bounded hold again gives nothing (6.14 s, scheduling time 0.35 s per run, 6% of the makespan), consistent with section 23. The learned policy, retrained in one command on this configuration with no code change, reaches the same relation to the baselines as on the 6-P configuration: about 20% faster than blind greedy and level with the hand rule.

### 26.2 Confirmatory session (pre-registration)

Design `design_study2_iters_p2_confirm.json` sha256 `ab7aad29cfec9fd93b449425658b04e5dcd3e2c380ca561986728409c1c3a13e`; adapter config `adapter_config_study2_p2.json` (`max_p_slots` 2); model `retrain_p2/param_model.json` (sha256 `43d2015747440d55034a15ba3b82935f8c15f520a7ad8d63e9e43eb3fed861fc`, fitted from the retraining coverage sessions of section 25 only); profile `profile_t512` (solo table of the blind predictor, configuration independent). The workload of section 18 on **chain orders never used by any earlier session**: `order_g` seed 77 and `order_h` seed 88, alternating by block. Seed 20262101, **21 blocks (block 0 warm-up, 20 analysed, 10 per order)**, `require_ac_power`, memory preflight 0.8 GB. Conditions (5): `B4` (blind greedy; reference), `B4_param_first` (informed hand rule), `B0_P_only` (static, 2 P workers), `EFT_E1_noctx` (blind table predictor), `PRED_RANK_GREEDY` (generic model retrained for this configuration). **Block count:** paired sd of the contrast of interest 0.0056 in the pilot (0.017 to 0.027 on the 6-P configuration); the rule of section 4 gives at most 15 blocks for a +-2% margin at sd 0.027; 20 are used.

**Analyses (committed now; no others are confirmatory).** `analyze_experiment.py --seed 0` twice: A with reference `B4` (`analysis_iters_p2_confirm_ref_B4`), B with reference `PRED_RANK_GREEDY` (`analysis_iters_p2_confirm_ref_PRED_RANK_GREEDY`); Holm over the conditions of each analysis; metric makespan; exclusions as before, plus any run flagged by the scheduling-cost guard.

**Pre-stated predictions (from the pilot and section 24):**
* P1: `PRED_RANK_GREEDY` is faster than `B4` by 17% to 24%, Holm-significant.
* P2: `PRED_RANK_GREEDY` is faster than `B0_P_only` by at least 30% (lower bound only: no P-only run of this configuration exists yet), Holm-significant.
* P3: `PRED_RANK_GREEDY` is faster than `EFT_E1_noctx` by at least 20%, Holm-significant.
* P4: `PRED_RANK_GREEDY` is equivalent to `B4_param_first`: the whole 95% interval of the paired effect lies inside +-2% (supported); an interval reaching outside is "not resolved", entirely outside "not supported". No superiority is predicted.

**What the claims mean.** "The learned model, retrained by one command for a changed resource configuration, beats blind and static scheduling there" is supported only if P1, P2 and P3 are supported. "It reaches the informed hand rule there" only if P4 is.

**Limits.** The 2-P configuration is a different set of workers on the same machine, not a different machine; it tests the retraining path and the policy, not a new physical device. One machine, synthetic chains of real stages.


## 27. Result of the 2-P-core confirmatory session (written 2026-10-25, AFTER the session and its analyses; sections 1 to 26 are unchanged)

Session `iters_p2_confirm_sessions/` (design `ab7aad29...`, matches section 26): complete, 21 of 21 blocks, 105 runs, all with status ok, output verified and event-log hash matching, none flagged by the cost guard; 100 in the primary analysis (warm-up block excluded). Evidence manifest verified; `reproduce_subset.py` re-derived summary and effects for both pre-registered analyses (`repro_analysis_iters_p2_confirm_ref_*.json`, all `ok`). The configuration was 2 P + 7 E workers (worker-ready events), the power guard was on and the laptop on mains. Mean makespan (s): PRED_RANK_GREEDY 4.876, B4_param_first 4.895, B4 6.181, EFT_E1_noctx 7.819, B0_P_only 8.884. Scheduling time per run: PRED_RANK_GREEDY 0.086 s, B4_param_first 0.158 s, B4 0.181 s.

| prediction | contrast | effect | interval | p_holm | predicted | outcome |
|---|---|---:|---|---:|---|---|
| P1 | PRED_RANK_GREEDY vs B4 | -21.10% | -21.47 to -20.73 | 0.0004 | -17 to -24% | **supported** |
| P2 | PRED_RANK_GREEDY vs B0_P_only | -45.1% (reference table: P-only is +82.17%, 81.10 to 83.29) | -45.4 to -44.8 | 0.0004 | at least -30% | **supported** |
| P3 | PRED_RANK_GREEDY vs EFT_E1_noctx | -36.6% (reference table: table predictor is +57.65%, 47.17 to 68.89) | -40.8 to -32.1 | 0.0004 | at least -20% | **supported** |
| P4 | PRED_RANK_GREEDY vs B4_param_first | -0.4% (reference table: hand rule is +0.38%, -0.01 to +0.78) | -0.8 to +0.0 | 0.0731 | equivalent within +-2% | **supported** (the whole interval is inside +-2%) |

**Claims (wording of section 26).** (a) "The learned model, retrained by one command for a changed resource configuration, beats blind and static scheduling there": **SUPPORTED** (P1, P2, P3): 21.1% faster than blind greedy, 45.1% faster than P-only, 36.6% faster than the blind table predictor. (b) "It reaches the informed hand rule there": **SUPPORTED** at the project's 2% margin (-0.4%, -0.8 to +0.0).

**Reading both configurations together.** 6 P + 7 E (section 24): beats blind and static rules (P1 to P3 supported), within 1.6% of the hand rule but not within the 2% margin (not resolved, hand rule ahead). 2 P + 7 E, retrained with one command and no code change (this section): beats blind and static rules and is level with the hand rule. In both, the policy is about 20% faster than blind greedy at 0.09 s of scheduling time per run, and the blind table predictor of stages 1 to 5 is 37% to 43% slower than the learned model. No policy tried (EFT with early binding, HEFT, PEFT, a bounded hold) beats the hand rule in any session.


## 28. "Do no harm" check on the uniform batch (written 2026-10-25; the design is frozen BEFORE its first block)

**Question.** A scheduler that uses a learned model must not be worse than the simple rule when the model has nothing to learn. On the uniform batch of section 12 every chain has the same cost, so no parameter is hidden. Does the learned policy stay level with greedy B4 there (so that using it is safe by default), and does the same generic training command work on that very different workload?

**Model.** `scripts/study2_train_param_model.py` unchanged, trained from EARLIER uniform-batch logs only: `pilot2_sessions`, `pilot5_sessions` and `oracle_cover_sessions` (the confirmatory session of section 12 and the oracle sessions are not used; `param_model_uniform.json`, sha256 `9d82b1eb48715a706b54063d03ad14b32bf70c581c4698fb0eacd52c0b8300e6`). The model found no varying parameter in this workload and therefore uses the mean kernel time of each (stage, pool) group measured under load, including the CUDA pool G (hold-out median absolute percentage error on the section 12 session: 3% to 17% on the CPU pools, 22% to 69% on G where kernels last about a millisecond).

**Session.** Design `design_study2_uniform_nh.json` sha256 `64a5191512ea9a2bc351b30648d10104137565b05868b99342096806ed31dceb`; adapter config unchanged (`15d4c3e9...`); profile `profile_t512`; the workload, pools (6 P, 7 E, one CUDA worker), CUDA stage table (denoise, edges, features) and seed family of section 12. Seed 20262201, 31 blocks (block 0 warm-up, 30 analysed), `require_ac_power`. Conditions (4): `B0_P_only` (static), `B4_gpu` (blind greedy, priority G, P, E; session reference), `EFT_E1_noctx_gpu` (the section 13 predictive rule), `PRED_RANK_GREEDY_gpu` (generic model, predicted-rank order, work-conserving placement). Block count: paired sd of the section 13 contrasts 0.03; the rule of section 4 gives 18 blocks for a +-2% margin, 30 are used.

**Analyses (committed now; no others are confirmatory).** `analyze_experiment.py --seed 0` twice: A with reference `B4_gpu` (`analysis_uniform_nh_ref_B4_gpu`), B with reference `PRED_RANK_GREEDY_gpu` (`analysis_uniform_nh_ref_PRED_RANK_GREEDY_gpu`); Holm over the conditions; metric makespan; exclusions as before plus any run flagged by the scheduling-cost guard.

**Pre-stated predictions (from sections 13 and 24):**
* P1: `PRED_RANK_GREEDY_gpu` is equivalent to `B4_gpu`: the whole 95% interval of the paired effect lies inside +-2%.
* P2: `PRED_RANK_GREEDY_gpu` is faster than `B0_P_only` by 25% to 38%, Holm-significant.
* P3: `PRED_RANK_GREEDY_gpu` is equivalent to `EFT_E1_noctx_gpu` within +-2%.

**Claim.** "The learned policy does no harm where nothing is hidden" is supported only if P1 and P3 are supported; P2 repeats the static-rule comparison. An interval reaching outside +-2% is "not resolved", entirely outside "not supported", and the direction is reported in either case.


## 29. Result of the "do no harm" session (written 2026-10-25, AFTER the session and its analyses; sections 1 to 28 are unchanged)

Session `uniform_nh_sessions/` (design `64a51915...`, matches section 28): complete, 31 of 31 blocks, 124 runs, all with status ok, output verified and event-log hash matching (CUDA runs checked per task as before), none flagged by the cost guard; 120 in the primary analysis (warm-up block excluded). Evidence manifest verified; `reproduce_subset.py` re-derived summary and effects for both pre-registered analyses (`repro_analysis_uniform_nh_ref_*.json`, all `ok`). Power guard on, laptop on mains. Mean makespan (s): EFT_E1_noctx_gpu 1.761, B4_gpu 1.769, PRED_RANK_GREEDY_gpu 1.777, B0_P_only 2.403. Scheduling time per run: PRED_RANK_GREEDY_gpu 0.025 s, B4_gpu 0.016 s, EFT_E1_noctx_gpu 0.055 s, B0_P_only 0.139 s.

| prediction | contrast | effect (PRED vs this) | interval | p_holm | predicted | outcome |
|---|---|---:|---|---:|---|---|
| P1 | PRED_RANK_GREEDY_gpu vs B4_gpu | +0.45% | -0.25 to +1.23 | 0.27 | equivalent within +-2% | **supported** |
| P2 | PRED_RANK_GREEDY_gpu vs B0_P_only | -26.07% | -26.75 to -25.25 | 0.0003 | -25 to -38% | **supported** |
| P3 | PRED_RANK_GREEDY_gpu vs EFT_E1_noctx_gpu | +0.90% | -0.04 to +1.97 | 0.17 | equivalent within +-2% | **supported** (upper end 1.97%, inside the margin) |

(Converted from the reference-PRED table: speed of PRED = 1 / (1 + effect of the other rule); effects of the other rules vs PRED: P-only +35.26%, B4_gpu -0.45%, EFT_E1_noctx_gpu -0.89%.)

**Claim: "the learned policy does no harm where nothing is hidden": SUPPORTED** (P1 and P3). On the uniform batch, where the trained model finds no varying parameter and falls back to measured group means, the policy is level with greedy B4 (+0.45%) and with the section 13 predictive rule (+0.90%) at 0.025 s of scheduling time per run, and 26.1% faster than P-only. The same training command, with no code change, produced a usable model for this very different workload (a CUDA pool, no varying parameter, tasks of about a millisecond).

**Reading sections 24, 27 and 29 together.** The generic learned policy (a) is about 20% faster than blind greedy and 37% to 43% faster than the blind table predictor when a parameter hides the cost (6 P and 2 P configurations); (b) is level with the hand rule that is told the parameter on the 2 P configuration and 1.5% behind it on the 6 P configuration; (c) costs nothing where there is nothing to learn. Its default use is therefore safe: it was never worse than the simple rule by more than 2% in any confirmatory session, and never worse than the section 13 rule.


## 30. Two-factor hidden-cost workload (written 2026-10-25 BEFORE any run of it)

**Question.** Sections 20 to 29 showed that a learned model ties a rule that is handed ONE hidden parameter. A fair objection: a person who knows the parameter writes that rule. The harder case is a cost that depends on several things at once (image size and the number of repeats): a rule that sorts by one factor misorders the classes where the other factor dominates, and a person has to know the formula. Does the same generic model, extended to inputs and their products without any code naming them, find the structure from logs and beat the one-factor rules, and how does it compare with the hand-written formula?

**Model change (permanent, backward compatible).** `param_model.py` now also uses the task `size` and, when two or more inputs vary, all their pairwise products; features are standardised before the solve and coefficients returned in raw units (tests: `test_classes_batch_and_two_factor_model`, plus a regression check that refitting the hidden-cost workload's coverage logs reproduces the section 18 model: same features, coefficients equal to 1e-9). Models written earlier load and predict as before.

**Workload** (`study2/workload.py::build_classes`): independent chains `source -> denoise (x N) -> edges -> features`, each with its own (image side, N); one `aggregate`; CPU pools P (6) and E (7). TEST classes (the evaluation): 48 chains of (256 px, N = 2), 12 of (256 px, N = 300), 12 of (1024 px, N = 3). Solo P-core cost of a chain, from the profiles: about 21 ms, about 0.4 s and about 0.43 s. Sorting by repeats alone puts the 1024 px class (N = 3) among the light chains; sorting by size alone puts the 256 px class (N = 300) among the light chains: each misorders a class of 12 heavy chains. Two instances = two fixed chain orders (pilot: `order_a` seed 11, `order_b` seed 22; confirmatory: `order_e` seed 55, `order_f` seed 66, never used with this workload).

**Training (the section 21 retraining path, `--workload classes`).** `python scripts/study2_retrain.py <out> <adapter_config> <profile> --workload classes`: a random-placement coverage session and an E-only session on a GRID of (side, N) combinations (256, 512, 1024 px x N in {2, 20, 100}, plus (256, 400); the heaviest cells have one chain). The TEST classes (256, 300) and (1024, 3) are NOT grid points: the model interpolates between them.

**Rules (all CPU pools; list fixed now).** Non-predictive: `B4` (blind greedy), `B4_param_first` (sorts by repeats), `B4_largest_first` (sorts by size), `B4_cost_first` (sorts by pixels x repeats: the formula a person would write after learning that both factors matter; the strict baseline), `B0_P_only` (static). Learned: `PRED_RANK_GREEDY` (generic model, predicted-rank order, work-conserving placement; the policy of section 22, unchanged). The blind table predictor is not included: its profile has no entries for the sizes of this workload.

**Plan.** (1) Retraining and a pilot on the pilot orders (exploratory, to set predictions and the block count); (2) section 31, written after the pilot and BEFORE the confirmatory session: design hash, predictions, analyses; (3) the confirmatory session on `order_e`/`order_f`; (4) section 32 with the result. Same controls as before: `require_ac_power`, the scheduling-cost guard, 0.8 GB memory preflight, claims registry updated from the stored tables.

**Stated in advance.** A learned policy equal to `B4_cost_first` and ahead of the one-factor rules is the expected outcome and is what would support the claim; a learned policy behind `B4_cost_first` is reported as such. The model's hold-out error on the TEST classes is reported with the result, because a model that finds the structure but extrapolates badly would explain a failure.


## 31. Retraining and pilot result for the two-factor workload, and pre-registration of its confirmatory session (written 2026-10-25; the design is frozen BEFORE its first block)

### 31.1 Retraining and pilot (exploratory)

**Retraining (one command, no code change):** `study2_retrain.py retrain_classes ... --workload classes` ran the two coverage sessions (13 and 7 blocks, complete) on the (side, N) grid and fitted `retrain_classes/param_model.json` (sha256 `4731f3bc489e34ef8293c5a5cb23655a006f11e061ed54dbc022450e54a32d23`). The model found the structure by itself: `img_denoise` on both pools uses `iterations`, `size` and `iterations*size` (P: product coefficient 2.2e-8 s per pixel-repeat, i.e. 22 ms per repeat per million pixels, consistent with the solo profile of 24.7 ms); `img_source`, `img_edges`, `img_features` use `size` only; `img_aggregate` the mean. Training MAE per group: denoise 29 to 31 ms (the heaviest cells), source 21 to 34 ms, edges 3 to 4 ms, features 0.5 to 0.7 ms.

**Pilot** `classes_pilot_sessions/` (design `06992d61...`): complete, 9 of 9 blocks, 54 runs, all verified; 48 in the primary analysis; chain orders `order_a`, `order_b`. Mean makespan (s): B4_param_first 2.516, B4_cost_first 2.536, PRED_RANK_GREEDY 2.559, B4 2.675, B0_P_only 2.957, B4_largest_first 3.058. Paired effect of PRED_RANK_GREEDY against: B4_largest_first -16.4%, B0_P_only -13.5% (from the B4 table), B4 -4.4% (-6.97 to -0.77), B4_cost_first +1.0% (paired sd of the log ratio 0.038), B4_param_first +1.9% (sd 0.043). Reading: the heavy classes do not make the rule that sorts by repeats alone fail (the 1024 px class costs 0.43 s per chain, not enough to dominate a 2.5 s run), the rule that sorts by size alone is clearly worst, and all informed or learned rules are within 2% of each other. The workload is less discriminating than the one of section 18 (blind greedy is only 4% to 6% behind the best rule), so the confirmatory claims below are modest by design.

### 31.2 Confirmatory session (pre-registration)

Design `design_study2_classes_confirm.json` sha256 `e65fc6ad8ffe46c162798e593f72b3404ff733447124cbc1adab649828e9d871`; adapter config `adapter_config_study2.json` (6 P + 7 E + idle CUDA worker); model `retrain_classes/param_model.json` (`4731f3bc489e34ef8293c5a5cb23655a006f11e061ed54dbc022450e54a32d23`, fitted from the retraining coverage sessions only); the TEST classes of section 30 on **chain orders `order_e` (seed 55) and `order_f` (seed 66)**, alternating by block; seed 20262401; **41 blocks (block 0 warm-up, 40 analysed, 20 per order)**; `require_ac_power`; conditions (6): `B4` (reference), `B4_param_first` (sorts by repeats), `B4_largest_first` (sorts by size), `B4_cost_first` (sorts by pixels x repeats), `B0_P_only`, `PRED_RANK_GREEDY`. **Block count:** paired sd 0.038 to 0.058 in the pilot; the rule of section 4 gives 30 blocks for a +-2% margin at sd 0.038; 40 are used.

**Analyses (committed now; no others are confirmatory).** `analyze_experiment.py --seed 0` twice: A with reference `B4` (`analysis_classes_confirm_ref_B4`), B with reference `PRED_RANK_GREEDY` (`analysis_classes_confirm_ref_PRED_RANK_GREEDY`); Holm over the conditions; metric makespan; exclusions as before plus any run flagged by the scheduling-cost guard.

**Pre-stated predictions (from the pilot):**
* P1: `PRED_RANK_GREEDY` is faster than `B4_largest_first` by 10% to 22%, Holm-significant.
* P2: `PRED_RANK_GREEDY` is faster than `B0_P_only` by 8% to 20%, Holm-significant.
* P3: `PRED_RANK_GREEDY` is faster than `B4` by at least 2%, Holm-significant.
* P4: `PRED_RANK_GREEDY` is equivalent to `B4_cost_first`: the whole 95% interval inside +-2%.
* P5: `PRED_RANK_GREEDY` is equivalent to `B4_param_first` within +-3% (a wider margin because the sd is 0.043; a result of "not resolved" is possible and is reported as such).

**What the claims mean.** "The generic model, retrained by one command on a two-factor workload, finds the structure (size, repeats and their product) and beats the naive one-factor rule and the static rule" is supported only if P1 and P2 are; "it beats blind greedy" only if P3 is; "it matches the hand-written cost formula" only if P4 is. Nothing else is confirmatory.

**Limits (stated in advance).** One machine; synthetic chains of real stages; on this class mix the repeats-only rule is already close to the formula, so this workload cannot show a large gain over informed rules and is not meant to; the model is trained on a grid that contains the evaluation classes' neighbours, not the classes themselves.


## 32. Result of the two-factor confirmatory session (written 2026-10-25, after analysis; nothing in section 31 was changed)

Session `classes_confirm_sessions/20261025T005921`: complete, 41 of 41 blocks, design hash as in section 31 (`e65fc6ad...`), 40 blocks analysed, 246 runs (240 analysed), all status ok with output and log verified, none flagged by the scheduling-cost guard. Analyses exactly as pre-registered: `analysis_classes_confirm_ref_B4` and `analysis_classes_confirm_ref_PRED_RANK_GREEDY` (seed 0, Holm over the five contrasts).

**Mean makespan (s), mean of the two chain orders:** B4_param_first 2.64, B4 2.65, B4_cost_first 2.70, PRED_RANK_GREEDY 2.68, B4_largest_first 3.14, B0_P_only 3.13.

**Primary contrasts (makespan, paired log ratio, 40 blocks; effect = how much slower the row is than the reference, so a negative value means faster).**

| Reference | Row | Effect | 95% interval | Holm p |
|---|---|---:|---|---:|
| PRED_RANK_GREEDY | B4_largest_first | +17.4% | +15.3 to +19.7 | 0.0005 |
| PRED_RANK_GREEDY | B0_P_only | +17.1% | +14.3 to +20.1 | 0.0005 |
| PRED_RANK_GREEDY | B4 | -0.9% | -2.8 to +0.9 | 0.79 |
| PRED_RANK_GREEDY | B4_cost_first | +1.0% | -1.3 to +3.4 | 0.79 |
| PRED_RANK_GREEDY | B4_param_first | -1.4% | -3.8 to +1.1 | 0.79 |

(`PRED_RANK_GREEDY` against `B4` in the other table: +0.9%, interval -0.9 to +2.8, p = 0.67.)

**Predictions, as pre-registered.**
* **P1 supported.** The learned policy is faster than sorting by size alone by 17.4%, inside the predicted 10% to 22%, Holm-significant.
* **P2 supported.** Faster than the static P-only rule by 17.1%, inside the predicted 8% to 20%, Holm-significant.
* **P3 NOT supported.** The learned policy is not faster than blind greedy `B4`: +0.9% (interval -0.9 to +2.8). The pilot's 4.4% advantage over `B4` did not replicate; it was a feature of the two pilot orders and 8 blocks (interval -7.0 to -0.8), not a stable effect. The prediction "at least 2% faster" is wrong and is reported as wrong.
* **P4 not resolved.** Against the pixels x repeats formula the difference is +1.0% in favour of the learned policy, but the interval (-1.3 to +3.4) is wider than +-2%, so equivalence is not shown. The paired sd was 0.081, twice the pilot's 0.038, so the 40 blocks fixed from the pilot are too few for this margin.
* **P5 not resolved.** Against the repeats-only rule the point estimate is -1.4% (the other rule is 1.4% faster), interval -3.8 to +1.1, outside the +-3% margin on the low side.

**What this workload shows and does not show.**
* The two rules that are wrong about this mix (sort by size alone, or use only the P cores) lose 17% to everything that knows about the repeats, and the learned policy is on the right side of that line without any hand-written formula.
* Nothing separates the learned policy, blind greedy, the repeats-only rule and the pixels x repeats formula: all four are within about 2% of each other with intervals of about +-2.5%. On this workload, 72 chains on 13 CPU workers with one 48-chain light class, greedy placement is already near the best order, so there is little to gain and no policy gains it. The learned policy is not shown to be better than the blind policy here; the claim "prediction beats blind greedy" is NOT supported by this session.
* Scheduling work: the learned policy's scheduler time is 2.3 times that of `B4` (0.017 s against 0.0076 s per run mean total, about 0.6% of the makespan), far inside the guard of 25%.

**Hold-out error of the model (promised in section 30).** On the denoise stage of the confirmatory logs (the model never saw these classes), the mean predicted against mean measured time per class: P pool, 256 px with 300 repeats 0.605 s against 0.565 s (+7.1%); P pool, 1024 px with 3 repeats 0.122 s against 0.112 s (+8.3%); E pool, 256 px with 300 repeats 1.24 s against 1.26 s (-1.5%); E pool, 1024 px with 3 repeats 0.261 s against 0.277 s (-5.9%). The light class (256 px, 2 repeats, 48 chains) is predicted badly: 17.6 ms against 4.1 ms on P, and on E the linear fit extrapolates to zero (0.001 ms against 9.0 ms measured). A linear model fitted on a grid whose cheapest cell is the same class cannot represent a 4 ms cost next to a 0.5 s cost; this does not hurt the ordering (both are the lightest) but it means the model is not an accurate predictor of absolute time for the light tasks, and a log-scale or per-class error model would be the next improvement. The heavy classes, which decide the order, are predicted within 8%.

**Claims added to the registry (C1 to C5; `claims.json`, checked against these tables by `tests/test_claims.py`):** C1 supported (P1), C2 supported (P2), C3 not_supported (P3), C4 not_resolved (P4), C5 not_resolved (P5).

**Consequence for the project claim.** After the full set of sessions (sections 18 to 32): the learned policy (generic model, predicted-rank order, work-conserving placement) beats static and naive rules by 17% to 45% whenever a cost parameter is hidden and the mix is not already well ordered by arrival; it is level with the best hand-written rule given the hidden parameter; it is level with blind greedy where greedy is already close to the best order (the uniform batch of section 29 and this workload) and it beat blind greedy only on the one-factor workloads of sections 18 to 24. It has never beaten the best hand-written rule. That is the claim the data supports; "always beats the best rule" does not hold.
