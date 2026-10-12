# Final report: execution-time prediction for dynamic DAG scheduling on a heterogeneous laptop

Status: **written 2026-10-13 after the Stage 4 sessions (branch `redesign/montage`, HEAD `4b66dcc`, working tree not committed when this was written).** Every number below comes from a named evidence file under `data/results/` or from a project document named next to it. A number marked "(computed here from <file>)" was derived while writing this report by reading that file (light read-only Python), not copied from a stored table. Evidence labels: **[real]** measured on real hardware; **[replay]**; **[emulation]**; **[simulation]**; **[plan]**; **[unverified]** (as in [PROJECT_SPEC.md](PROJECT_SPEC.md)). One item is still open by instruction: the clean-checkout reproduction (section 13) is Observed 2026-10-12 22:19-22:21 UTC (`data/results/stage4_repro/repro_clean_checkout_log.json`, copy of the log written by `scripts/reproduce_clean_checkout.py`): clone of branch `redesign/montage` at its tip into a new directory, fresh Python 3.11.9 venv from `requirements-lock.txt` (torch lines dropped, no CUDA), `pytest` on 4 test files, stub-adapter experiment, analysis, SHA-256 manifest build and verify and `reproduce_subset.py`, and a read-only hash check of the Montage binaries and the primary instance: all 18 steps exit 0 (about 2 minutes). Limits (as recorded in the log): data/ is not in Git, so Montage and its timings are not re-run; the stub adapter is synthetic (label plan); only a 4-file pytest subset ran; CUDA tests and the GPU spike are not covered..

## Summary

- **Result: a null result, with two mechanisms.** On this machine, with Montage and with a separate CPU/GPU image workload, prediction-aware placement never beat the strongest simple baseline. With all pools (6 P + 7 E workers) the pre-registered strongest baseline, "use only the P cores" (B0 P-only), was faster than every predictive or plan-based policy by 1.3% to 1.9% (paired, 4 blocks; `analysis_main/effects.csv`). With scarce P cores (2 P + 7 E) the predictive policy EFT_E1 tied the greedy baseline B4 (-0.01%, interval -0.12% to +0.11%), and the CatBoost-driven variant was 15.0% slower. On the GPU workload EFT_E1 with the GPU was not distinguishable from P-only (-0.41%, interval -0.92% to +0.02%).
- **Mechanism 1 (early versus late binding).** EFT, HEFT and PEFT bind the second wave of `mProject` tasks to workers at dispatch time; P-only binds them to whichever P worker is idle first. Consistent with and confirmed by the worker and timeline records for the primary instance; not tested as a controlled experiment (section 8.2).
- **Mechanism 2 (knife-edge decisions amplify prediction bias).** In the 2 P + 7 E regime the choice between queueing a seventh `mProject` task on a P worker and sending it to an E core is a near tie, and the CatBoost predictions (P under-predicted, E over-predicted) tipped it the wrong way. A predictor with lower average error (Ridge, MAE 1.36 s against 3.26 s for the static profile on the held-out instance) did not guarantee a better schedule; the error on the decisive task type matters (section 8.2).
- **Contribution (honest statement).** A controlled, overhead-accounted, real-hardware study with verified outputs and a null/negative headline, two mechanisms, and the infrastructure (Windows-native Montage build, external-command DAG runtime, 14+ policies, decision-time-safe dataset builder, paired-block analysis). It is not a new algorithm and not a general claim about prediction.
- **Outcome per pre-registered claim** (wording from EVALUATION_PROTOCOL section 12.5): (a) not supported; (b) supported for the conditions tested; (c) not supported; (d) offline accuracy yes for Ridge on the held-out instance, scheduling not testable beyond ties; (e) significance testing not resolved by this design because of a flaw in the pre-registered test (section 4.4). Details in section 8.3.

## 1. Question and hypothesis

Source: [PROJECT_SPEC.md](PROJECT_SPEC.md) sections 4 and 5.

- **Research question.** Under what workload and resource conditions does execution-time prediction improve dynamic DAG scheduling on heterogeneous resources after accounting for prediction, scheduling, queueing and data-transfer overhead?
- **Primary contribution.** A controlled, overhead-accounted, real-hardware study of how much predictor sophistication improves actual DAG scheduling of a real scientific workflow, using decision-time-safe data and a ladder from no prediction to learned models.
- **Supporting contributions.** (1) Generalisation of predictors and schedulers to instances and sizes not seen in training. (2) Transfer-aware placement to a remote or GPU pool: **[emulation]** for the remote pool (not used here), **[real]** for the GPU on a separate workload.
- **Primary hypothesis (falsifiable, no promised size).** Prediction-aware placement beats the best non-predictive baseline only when the runtime ratios between resources and the contention are large relative to prediction cost, scheduling cost and timing noise. Otherwise a simple method matches it.
- **Supported by:** a paired-block makespan advantage whose confidence interval excludes zero in the high-ratio/high-contention conditions and not in the low conditions, after overhead is counted. **Rejected by:** no condition where predictive placement beats the strongest non-predictive baseline, or a gain that disappears once decision cost is counted. A null result is an accepted outcome.
- **Not claimed:** a new learning algorithm, a new list-scheduling algorithm, or novelty of "task graph + queues + eligibility" (claimed by the base patent, PROJECT_SPEC section 7). The proposed scheduler is a study instrument.

**Verdict on the hypothesis (pre-registered wording: "supported", "not supported", "not resolved by this design").**

| Claim | Outcome | Evidence |
|---|---|---|
| (a) Prediction-aware placement beats the best non-predictive baseline in some condition | **Not supported** in all three conditions tested. All pools: every predictive and plan-based policy is 1.3% to 1.9% slower than B0 P-only, all intervals above zero. Scarce P cores: EFT_E1 -0.01% against B4 (interval -0.12% to +0.11%), HEFT +0.06%, EFT_CatBoost +14.96%. GPU workload: EFT_E1 with the GPU -0.41% against B0 P-only (interval -0.92% to +0.02%, includes zero) | `stage4_20261012/analysis_main/effects.csv`, `analysis_regimeR/effects.csv`, `gpu/analysis/effects.csv` |
| (b) A simple method matches prediction otherwise | **Supported for the conditions tested.** P-only in all pools (it is faster); greedy B4 in scarce-P (tie with EFT_E1 and HEFT); P-only in the GPU workload (not distinguishable) | same files |
| (c) Predictor sophistication improves scheduling | **Not supported.** Pilot: six predictors within 0.5% of each other (271.4 s to 272.7 s). Main session: every learned predictor 1.4% to 1.6% above P-only, same as the static profile. Scarce P cores: CatBoost 15.0% worse than E1 | `stage3_20261012/pilot_gate.json`, `selection/selection_record.json`, main and regime R effects |
| (d) Generalisation to unseen instances and sizes | **Offline accuracy: yes for Ridge** on the held-out 157-task instance (MAE 1.36 s against 3.26 s for the static profile; CatBoost 2.32 s; MLP 2.98 s with RMSE 22.2 s); **no on the smallest fold**, where the learned models are worse than the static profile. **Scheduling: not testable beyond ties**, because the policies tie or P-only wins on every instance used in Stage 4 | `stage3_20261012/eval/final_test/metrics.json`, `eval/tuning_loo/metrics.json` |
| (e) Significance tests (Holm-adjusted sign-flip) | **Not resolved by this design.** With 4 blocks the smallest attainable p-value is 2/2^4 = 0.125 and with 3 blocks 2/2^3 = 0.25, so no contrast could be significant at 0.05. Results are reported as paired effects with bootstrap intervals (descriptive) | `analysis_main/effects.csv` (`p_perm` 0.118 to 0.131, `p_holm` 1.0 for every contrast); section 4.4 |

The rejection criterion of the hypothesis is therefore met for the conditions tested. This does not show that no condition exists where prediction helps. The workload has one dominant task type (nine `mProject` tasks) and one pool speed ratio (3.59, computed here from `stage2_20261012/profile_montage/20261012T092355_profile.json`: 401.08 s on E against 111.77 s on P), and the pre-registration itself stated that a trivial rule is optimal whenever at least three P workers exist, so "a null result against the strongest baseline is expected by construction" (EVALUATION_PROTOCOL section 12.6).

## 2. Scope and evidence labels

- Machine-specific study: one laptop, one session family. Raspberry Pi 5 is a later extension; all Pi claims stay **[plan]**.
- What is **[real]**: Montage under 14 policies on this machine (Stage 2), Stage 3 collection, the Stage 4 sessions, the GPU workload. What is **[emulation]**: the remote pool, from earlier work only, not used here. What is **[plan]**: Raspberry Pi 5. What is **[unverified]**: see section 14.3.
- Historical evidence from the earlier machine (i5-1235U) and the 68-task image pipeline is kept as history and is not pooled with the Montage data. (The GPU workload of section 11 reuses the stage structure of that 68-task pipeline, 68 tasks per run, but all its numbers are new measurements on this machine.)

| Claim | Label | Evidence file |
|---|---|---|
| The Montage instance runs completely and reproducibly (sequential) | real | `stage1_20261011/valid/stage1_gate.json` |
| 14 policies run correctly on the heterogeneous runtime | real | `stage2_20261012/stage2_gate.json` |
| Offline prediction accuracy of six predictors on held-out rows | real (logged rows, offline) | `stage3_20261012/eval/{tuning_loo,final_test}/metrics.json` |
| Predictor selection by the frozen rule: EFT_E1 | real | `stage3_20261012/selection/selection_record.json` |
| All pools: predictive and plan-based policies 1.3% to 1.9% slower than P-only | real | `stage4_20261012/analysis_main/effects.csv` |
| Scarce P: EFT_E1 ties B4; EFT_CatBoost 15.0% slower | real | `stage4_20261012/analysis_regimeR/effects.csv` |
| GPU workload: EFT_E1 with GPU not distinguishable from P-only | real | `stage4_20261012/gpu/analysis/effects.csv` |
| Early versus late binding explains the 1.3% to 1.9% | real, observational (not a controlled experiment) | worker and event records in `sessions_main` (section 8.2) |
| HEFT and PEFT results | real, for implementations written from secondary-source definitions | `analysis_main/effects.csv`; [LITERATURE_UPDATE.md](LITERATURE_UPDATE.md) section 2 |
| Remote or edge offloading, Raspberry Pi 5 | plan, not done | none |
| Literature gap statement | unverified (bounded search) | [PROJECT_SPEC.md](PROJECT_SPEC.md) section 6, [LITERATURE_UPDATE.md](LITERATURE_UPDATE.md) |

## 3. Workload and environment

Sources: [WORKLOAD_AND_DATA_PROVENANCE.md](WORKLOAD_AND_DATA_PROVENANCE.md), [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md), the per-session `environment.json` of the Stage 4 sessions.

- **Workload.** Montage mosaic of DSS2 blue images, native Windows build of the Montage toolkit (Caltech-IPAC/Montage commit `ac0a15334f670ed83e328b6c5768f94b4b847359`, BSD 3-clause licence read in the `LICENSE` header), compiled with w64devkit (GCC 16.2.0) and patched for Windows (twelve workarounds listed in MONTAGE_WINDOWS_BUILD). The workflow generator is a Windows copy of `pegasus-isi/montage-workflow-v3` (commit `975047e916d3d049d9ff0da17e7fe5aaac979c64`, Apache-2.0) with three edits. Eight task types.
- **Primary instance** `d1.1_dss2b_c56.7_24.0`: 59 tasks, 147 dependency edges (`stage1_gate.json`: `dag.n_jobs` = 59, `dag.edges_jobDependencies` = 147; `only_in_jobDependencies` and `only_in_files` both empty). The 59 tasks are 9 `mProject`, 36 `mDiffFit`, 9 `mBackground`, and one each of `mConcatFit`, `mBgModel`, `mImgtbl`, `mAdd`, `mViewer` (computed here: 9 + 36 + 9 + 5 = 59; the gate file's per-transformation counts 27 and 108 are totals over three runs). Correction of an earlier skeleton line that read "27 `mProject` tasks": the instance has 9.
- **Other instances.** `d1.0_dss2b_c56.7_24.0` (19 tasks), `d1.1_dss2b_c10.7_41.3` (59 tasks), `d1.5_dss2b_c56.7_24.0` (157 tasks); roles in [STAGE3_FREEZE.md](STAGE3_FREEZE.md). Sequential times: section 5.
- **Input data.** Nine DSS images for the primary instance, 116,069,760 bytes, host `archive.stsci.edu`, survey `poss2ukstu_blue`, fetched 2026-10-11, hashes in `data/montage/instances/d1.1_dss2b_c56.7_24.0/instance.json`. **Licence and terms of use of the image data are not verified.**
- **Environment** (`stage4_20261012/sessions_main/20261012T212448/environment.json`, same machine id `681ed3fc...` and environment hash `bac0fdd0...` in all three Stage 4 sessions): Windows 11 Home Single Language 10.0.26200; i5-13500HX, 20 logical processors, RAM 16,858,472,448 bytes; the Windows topology API reports efficiency class 1 on logical processors 0 to 11 (six cores, two threads each) and class 0 on 12 to 19 (eight single-thread cores), which I read as P and E cores (the class-to-core-type reading is mine); WMI reports 14 cores. NVIDIA GeForce RTX 3050 6 GB Laptop GPU, driver 581.83, used only in the GPU workload. Python 3.11.9, numpy 2.4.6, pandas 3.0.6, scipy 1.17.1, torch 2.11.0+cu128, catboost 1.2.10.
- **Worker pools.** Main session: 6 P workers pinned to logical processors 0, 2, 4, 6, 8, 10 (one thread per P core) and 7 E workers pinned to logical processors 13 to 19, all with `affinity_ok` true in the `worker_ready` events (computed here from the event log of run `b0000_04_EFT_E1`); logical processor 12 is reserved for the coordinator (`planned_worker_pool_config` in `environment.json`, whose own P-slot list `[0, 2]` is the 2-P default and is the same in all sessions, so it does not describe the 6-P pinning). Scarce-P regime: 2 P workers (P0, P1) + 7 E. GPU workload: 6 P + 7 E + 1 CUDA worker (computed here from `worker_ready` counts).
- **Pool speed ratio.** `mProject` 111.77 s on a P core and 401.08 s on an E core (4 repetitions each), other task types seconds or less (`stage2_20261012/profile_montage/20261012T092355_profile.json`). `mProject` is 98.7% of sequential time (STAGE3_FREEZE section 4).
- **Machine state.** The machine was not idle (WSL VM, browser, editor, as stated in RESEARCH_STATUS); no per-run record of other processes exists. The runner's memory preflight recorded at least 5.82 GiB free before main-session runs, 5.75 GiB (scarce-P) and 5.08 GiB (GPU) (computed here from `runs.csv`, column `memory_available_start_bytes`).

## 4. Method

### 4.1 System architecture

Windows-native Python runtime: workflow adapter (Pegasus YAML to internal DAG, no manual edits), external-command task type with declared input and output files and fail-fast semantics, capability model for pools (cpu, cuda, remote), uniform eligibility for every policy, coordinator with ready queue and JSONL event log, affinity-pinned P and E worker processes plus one CUDA worker, pluggable schedulers and estimators, decision-context logging, dataset builder with train/serve parity tests, paired-block experiment runner and analysis, and a dashboard. Decision records and per-item implementation status: [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) (AD-1 to AD-14; status table dated 2026-10-12). Local pools cost zero transfer (all jobs share one work directory), so transfer cost is not exercised by the CPU-only Montage runs (AD-2).

### 4.2 Scheduling algorithms

- Non-predictive baselines: B0 (P-only, E-only), B1 round-robin, B2 static P, B3 shortest queue, B4 greedy eligible dispatch (a patent-mapped comparison baseline, not an implementation of the patent), B5 criticality, random.
- Predictive ladder: EFT with E1 static profile, E3 moving history, E1+rc online recalibration, `EFT_E1_rank` (rank priority; the study instrument), and learned Ridge (E4 form), CatBoost, MLP.
- Published static list schedulers: HEFT and PEFT, formulas from **secondary sources** because the originals were not reachable (LITERATURE_UPDATE section 2, **[unverified]**). The rank term averages communication cost over all pools, so HEFT is HEFT-like, not HEFT-exact (ARCHITECTURE_DECISIONS AD-9).
- Binding: B0 P-only and B4 greedy dispatch a task only to an idle worker (late binding; `binds_only_idle` true in their run records); EFT, HEFT, PEFT and the learned-predictor EFT variants may queue a task on a chosen worker when it becomes ready (early binding; `binds_only_idle` false in every such run record of the main session, computed here from the first event of each run). The binding style of B1, B2, B3, B5 and random was not checked here.
- Excluded: GNN+PPO, GRU/TCN, temporal Transformer, GNN predictor, image embeddings. **TabM is out** by the entry rule evaluated before data (needs at least 20,000 labelled rows; 2,706 fitting rows exist), stated reason: too few rows for a neural tabular model (STAGE3_FREEZE section 2).

### 4.3 Predictors and data

- Target: per-task, per-device kernel time. Setup/staging, transfer, queue wait and scheduling/prediction time are separate (EVALUATION_PROTOCOL section 3).
- Candidates: E1, E3, E1+rc, Ridge, CatBoost, MLP, hyper-parameters fixed before fitting (STAGE3_FREEZE amendment A1; no hyper-parameter tuned on errors). Frozen complexity order E1 < E3 < E1+rc < Ridge < CatBoost < MLP. Measured costs (section 7.2) put MLP below CatBoost in inference latency (median 22.5 µs against 478 µs) and model size (16 KB against 140 KB) but above it in training time (8.6 s against 0.75 s); no dated amendment of the order was written. The selection outcome does not depend on the CatBoost/MLP order, because the cheapest model (E1) qualified against every other model.
- Decision-time-safe features only; training rows from decision-context logs (`context_source=decision`) of runs whose output verified. Parity and leakage tests passed in the last recorded full suite (377 passed, 1 skipped; `stage3_20261012/full_suite_before_commit.txt`).
- Splits: leave-one-instance-out on three instances for fitting and tuning; `d1.5` final test, evaluated once.
- Collection: `designs_v2/` (42 runs, 14 blocks of three conditions: EFT_E1 and two RandomOccupancy settings), STAGE3_COLLECTION_PLAN.md. The v1 `designs/` directory is superseded and unused.

### 4.4 Selection rule and statistics

- Selection rule: cheapest model whose outcome is not worse than every more complex model, upper bound of the paired-bootstrap interval of `outcome(simple) - outcome(complex)` at most `margin`; **margin = 2.0% of makespan** (ln 1.02 = 0.0198; STAGE3_FREEZE section 2).
- Paired effect: log ratio of makespan against the reference within a block, stratified percentile bootstrap, 10,000 resamples, seed 0 (`analysis.json`: `n_boot`, `seed`).
- **Pre-registration flaw (stated here, not corrected).** The pre-registered confirmatory family used Holm-adjusted sign-flip p-values (EVALUATION_PROTOCOL 12.5). A sign-flip test on n paired blocks cannot return a p-value below 2/2^n (two-sided; n = 4 gives 0.125, n = 3 gives 0.25). The pre-registration chose the block count from a minimum-detectable-effect rule (12.4) and did not check the smallest attainable p-value. Consequence: no contrast of the main session (4 blocks) or the scarce-P session (3 blocks) could be called significant by that test; the stored `p_holm` is 1.0 for every main contrast and 0.9975 for every scarce-P contrast. The GPU session has 12 blocks (minimum 2/4096), so its tests are attainable. Arithmetic (computed here): one contrast needs at least 6 blocks to reach p below 0.05 (2/64 = 0.031); a Holm family of ten contrasts needs at least 9 blocks for its smallest p-value to fall below 0.005 (2/512 = 0.0039). This report therefore reports paired effects with bootstrap intervals, treated as descriptive, applies the pre-registered outcome words per claim in section 1, and says "not resolved by this design" for significance. The Friedman cross-checks in `crosscheck.csv` are unadjusted and only say that the conditions differ (main: statistic 19.68, p = 0.032, 4 blocks; scarce-P: statistic 10.40, p = 0.034, 3 blocks).
- Repeat count: 4 blocks in the main session (2 per instance), 3 in the scarce-P session (budget-limited), 12 in the GPU session (EVALUATION_PROTOCOL 12.4; GPU: section 8.1).

## 5. Stage 1 results: reproducible workload [real]

All values from `data/results/stage1_20261011/valid/stage1_gate.json`, instance `d1.1_dss2b_c56.7_24.0`, `label` real.

| Item | Value | Field |
|---|---|---|
| Complete sequential runs | 3 of 3 (`completed_3_of_3` true) | `completed_3_of_3` |
| Wall time seq1, seq2, seq3 | 1459.4 s, 1467.1 s, 1469.3 s | `reps.seqN.total_wall_s` |
| Tasks per run, all timed | 59, `all_tasks_timed` true | `reps.seqN.n_tasks`, `all_tasks_timed` |
| Output hashes identical across runs | true (mosaic FITS `54c1c4b0...`) | `output_hashes_identical`, `reps.seqN.final_outputs` |
| Mosaic comparison, seq2 and seq3 against seq1 | `max_abs_diff` 0.0, shape and NaN pattern equal | `mosaic_comparison.comparisons[]` |
| WCS header checks | all ok (3960 x 3960 pixels, CRVAL 56.7, 24.0, TAN) | `wcs.all_header_ok`, `wcs.header_checks` |
| Finite fraction of the mosaic | 0.9666 | `wcs.finite_fraction` |
| `mProject` task time over the three runs | median 160.6 s, min 141.0 s, max 169.9 s (n = 27 tasks) | `per_transformation_wall_s.mProject` |
| DAG edges, job list versus files | 147 and 147, no differences | `dag` |

Sequential reference runs for the other instances (status ok, `data/results/stage3_20261012/refs/<instance>/run.json`, field `total_wall_s`, as quoted in STAGE3_COLLECTION_PLAN section 2): `d1.0` 489.7 s (19 tasks), `d1.1 c10.7_41.3` 1083.7 s (59 tasks), `d1.5` 1896.4 s (157 tasks).

Pool profile (`stage2_20261012/profile_montage/20261012T092355_profile.json`, median kernel time per task type, 2 to 40 repetitions): `mProject` 111.77 s (P), 401.08 s (E); `mViewer` 3.84 s (P), 10.58 s (E); `mAdd` 0.92 s and 2.63 s; `mDiffFit` 0.39 s and 1.19 s; `mBackground` 0.32 s and 0.84 s; `mBgModel` 0.36 s and 1.28 s; `mConcatFit` 0.19 s and 0.53 s; `mImgtbl` 0.09 s and 0.20 s.

Failed and discarded attempts, kept as evidence and excluded from every gate: the first run with the wrong `mDiffFit` variant, runs A to C and the first `rep1` to `rep3` set (PATH and runner problems; three partly concurrent runs made `mProject` 2 to 4 times slower, so timing runs are never concurrent), and debug resume runs that found the `mImgtbl` and `mViewer` defects (MONTAGE_WINDOWS_BUILD). The valid reference timings were taken with the machine not idle.

Reading: the workload runs completely and reproducibly on this machine. Hash identity across three sequential runs shows output determinism for the sequential case; the parallel runs are checked in section 9.

## 6. Stage 2 results: heterogeneous runtime, 14 policies [real, descriptive]

Source: `data/results/stage2_20261012/stage2_gate.json`: 42 runs, `n_runs` 42, `n_failing_checks` 0, `failing` empty; 3 blocks, one run per condition per block. Values are `makespan_by_condition.<condition>.mean_s` (n = 3 each) with min and max; the last column is the paired effect against B0 P-only from `analysis_stage2/effects.csv` (percent, 95% bootstrap interval, 3 blocks).

| Condition | Mean (s) | Min | Max | Effect vs B0 P-only |
|---|---|---|---|---|
| B2_static_P | 269.6 | 267.0 | 271.5 | -0.47% (-1.26 to +0.21) |
| B0_P_only | 270.9 | 270.4 | 271.3 | reference |
| EFT_E3 | 273.3 | 269.7 | 276.1 | +0.90% (-0.27 to +1.90) |
| HEFT_E1 | 274.5 | 273.8 | 275.9 | +1.35% (+0.93 to +1.85) |
| EFT_E1_rank | 274.7 | 274.4 | 275.1 | +1.42% (+1.39 to +1.48) |
| PEFT_E1 | 275.0 | 274.0 | 276.1 | +1.52% (+1.00 to +1.92) |
| EFT_E1_rc | 275.4 | 274.2 | 277.2 | +1.66% (+1.06 to +2.32) |
| EFT_E1 | 275.5 | 274.6 | 276.1 | +1.69% (+1.55 to +1.92) |
| B3_shortest_queue | 410.7 | 410.5 | 410.9 | +51.62% |
| B4_greedy_eligible | 410.5 | 409.9 | 411.1 | +51.54% (+51.09 to +51.78) |
| B5_criticality | 413.4 | 411.3 | 417.1 | +52.61% |
| random | 416.5 | 410.9 | 426.7 | +53.74% (+51.68 to +57.81) |
| B1_round_robin | 420.4 | 419.5 | 422.0 | +55.21% |
| B0_E_only | 811.8 | 811.4 | 812.1 | +199.71% |

Correctness in the same file: every run `completed` true, `output_verified` true (42 of 42, computed here), empty `dependency_violations`, `worker_overlaps` and `ineligible_placements`.

**Reading (descriptive, three blocks per policy):**

1. **B0 P-only is as fast as the predictive policies.** The predictive means lie between 273.3 s (EFT_E3) and 275.5 s (EFT_E1), 0.9% to 1.7% above P-only. B2 static P (269.6 s) has the fastest mean but its interval against P-only includes zero. The per-policy range within three blocks reaches 6.4 s (EFT_E3), about 2.3% of its mean, the same size as the gaps between these policies.
2. **Greedy B4 takes about one and a half times as long** (410.5 s against 270.9 s). B3, B5, random and round-robin sit in the same 410 s to 420 s band.
3. **Mechanism for the B4 band (now checked in the Stage 4 logs for the same policy).** In every B4 run of the main session three of the nine `mProject` tasks ran on E cores for 394 s to 410 s while the six P-core tasks took 150 s to 155 s (computed here from the raw event logs of `sessions_main`). Greedy dispatch hands a ready task to any idle eligible worker, including a 3.6 times slower E core. The Stage 2 logs themselves were not re-read for this. HEFT and PEFT also place 9 of 59 tasks on E, but none of these is an `mProject` task (computed here: in every main-session run of every policy other than B4, all nine `mProject` tasks ran on P workers), which is why they finish near the EFT policies.
4. The profile has a P pool much faster than the E pool for the dominant task type, so this table says nothing about workloads with a smaller speed ratio.

## 7. Stage 3 results: prediction

### 7.1 Collection

- Designs: [STAGE3_COLLECTION_PLAN.md](STAGE3_COLLECTION_PLAN.md) section 4 (42 collection runs, `designs_v2/`): all 42 completed and verified byte-identical to the instance references (RESEARCH_STATUS Stage 3 report). The dataset also includes the 18 Stage 2 runs of EFT-family and HEFT/PEFT policies that logged decision contexts (STAGE3_FREEZE amendment A2).
- Dataset `stage3_20261012/dataset/20261012T195206/manifest.json`: 60 runs from 5 sessions, 3,648 task rows (2,915 on P, 733 on E; computed here from `tasks.csv`) and 20,410 candidate rows; per instance 228 (`d1.0`), 708 (`d1.1 c10.7_41.3`), 1,770 (`d1.1 c56.7_24.0`), 942 (`d1.5`). Fitting rows 2,706 (three non-test instances), held-out 942.
- Exclusions: 24 runs (the B-family, random and E-only runs of Stage 2) had no logged decision context; their 1,416 completed tasks were dropped by the builder and counted (`n_rows_dropped_no_decision_ctx` 1416); 5 directories were not recognised as sources. A first build attempt that excluded everything (wrong directory layout) is kept as `dataset/20261012T195144`, unused.
- Coverage of the occupancy features over all 3,648 rows (computed here from `tasks.csv`): `busy_P` 0 to 6 (mean 2.71), `busy_E` 0 to 7 (mean 1.48), `target_busy_frac` 0 to 1 (mean 0.285). E-pool rows are 20% of the data.
- Sessions of three different code states were pooled into the dataset (`src_sha256` `a8e349763604` for Stage 2, `e6c902ff9863` for Stage 3); the analysis tool refuses such pooling for scheduling results, but the dataset builder does not.

### 7.2 Prediction quality (held-out rows only, separate from scheduling value)

Mean absolute error in seconds, with median absolute percentage error (headline relative error; dominated by tiny task times: mean observed time 29.8 s, and 1,310 of the 2,706 rows are below the 0.5 s floor, computed here from `n_above_floor` 1,396) and cost, from `eval/tuning_loo/metrics.json` (leave-one-instance-out over `d1.0`, `d1.1 c56.7_24.0`, `d1.1 c10.7_41.3`, n = 2,706) and `eval/final_test/metrics.json` (`d1.5`, n = 942, evaluated once).

| Metric | E1 | E3 | E1+rc | Ridge | CatBoost | MLP |
|---|---|---|---|---|---|---|
| MAE s, leave-one-instance-out | 3.54 | 3.53 | 3.55 | **1.32** | 2.35 | 1.86 |
| Median APE, leave-one-instance-out | 0.376 | 0.384 | 0.433 | 0.292 | 0.271 | 0.295 |
| Signed bias s, leave-one-instance-out | -3.12 | -3.17 | -3.18 | -0.35 | -0.17 | +0.48 |
| MAE s on `mProject` rows (n = 426), leave-one-instance-out | 21.04 | 21.04 | 21.04 | 7.21 | 13.57 | 10.68 |
| MAE s, `d1.5` final test | 3.26 | 2.71 | 2.69 | **1.36** | 2.32 | 2.98 |
| RMSE s, `d1.5` final test | 10.3 | 9.3 | 9.2 | 4.1 | 8.8 | 22.2 |
| Median APE, `d1.5` final test | 0.623 | 0.617 | 0.686 | 0.664 | 0.670 | 0.616 |
| MAE s on `mProject` rows (n = 96), `d1.5` | 28.13 | 23.36 | 23.35 | 10.31 | 19.40 | 25.24 |
| Inference latency per call, median (p99), µs, `d1.5` | 1.2 (4.4) | 1.1 (1.3) | 1.3 (1.5) | 6.1 (7.1) | 478 (970) | 22.5 (72) |
| Training time, s (final fit on 2,706 rows) | none | none | none | 0.009 | 0.75 | 8.63 |
| Model size, bytes | none | none | none | 4,098 | 139,512 | 16,060 |
| Peak resident-memory increase while training, MB | none | none | none | 1.1 | 64.0 | 550.8 |

Per-fold MAE in seconds, leave-one-instance-out (`per_fold`): `d1.0` (19 tasks, 228 rows) E1 1.81, Ridge 4.00, CatBoost 6.27, MLP 6.38; `d1.1 c10.7_41.3` (708 rows) E1 3.61, Ridge 0.90, CatBoost 2.21, MLP 1.51; `d1.1 c56.7_24.0` (1,770 rows) E1 3.74, Ridge 1.15, CatBoost 1.90, MLP 1.42. The learned models are worse than the static profile on the smallest instance.

Reading: Ridge is the most accurate overall model on absolute error, including on `mProject` (7.2 s against 21.0 s for the static profile), and it generalises to the held-out `d1.5`. The median APE does not separate the models on the final test (0.616 to 0.686) because it is dominated by sub-second tasks. MLP extrapolates badly on `d1.5` (RMSE 22.2 s). Calibration deciles are stored in the metrics file (`calibration_deciles`) and were not interpreted here. Check for collapse to a per-type constant: not run as a separate test; the `mProject` errors above show the learned models improve on the static profile for the dominant task type. Limit stated in advance: one dominant task type and few rows.

### 7.3 Generalisation

- Leave-one-instance-out folds: table above. Gain from learning on the two 59-task folds, loss on the 19-task fold.
- Time-ordered drift check within the primary session: **not run** (no result file exists in `eval/`; the metrics files contain no drift or time-split entry).
- `d1.5` final test, evaluated once, size withheld: table above. Limit: the test instance shares its sky centre with two training instances (it is a larger instance of the same region).
- Learning curve (TabM entry rule condition 2): **not run**; TabM is out regardless by condition 1 (rows).

### 7.4 Decision-level regret

The one-step hindsight regret table (`eval/regret.csv` in the plan) was **not produced**; no such file exists. The decision-level analysis that was done is the manual inspection of the scarce-P CatBoost decisions in section 8.2, which shows where a prediction error changes a placement.

### 7.5 Model selection

Frozen rule, margin 2.0%, applied to the Stage 3 scheduling pilot (`stage3_20261012/pilot_sessions/20261012T195449`, design `stage3_scheduling_pilot`, 6 predictors x 3 interleaved blocks on the primary instance, 18 runs, all verified, `n_failing_checks` 0, `pilot_gate.json`). Mean makespans: EFT_CatBoost 271.4 s, EFT_MLP 271.5 s, EFT_Ridge 271.6 s, EFT_E1 271.8 s, EFT_E1_rc 272.4 s, EFT_E3 272.7 s (all within 0.5%; computed from `pilot_gate.json`). Selection record (`selection/selection_record.json`): **EFT_E1 selected**; every comparison of E1 against a more complex model has a paired-log-ratio interval upper bound of at most 0.0050 (E3 0.0014, E1+rc 0.0037, Ridge 0.0036, CatBoost 0.0050, MLP 0.0033), far below the 0.0198 margin. TabM: out by the entry rule. Complexity order: not amended (see 4.3).

## 8. Stage 4 results: scheduling

### 8.1 Pilot and design

- **Baseline pilot** (used to choose the strongest baseline and the block count): the Stage 2 matrix (14 policies x 3 blocks, same machine and instance) and the Stage 3 scheduling pilot above; EVALUATION_PROTOCOL 12.1 to 12.4. No separate `stage4_pilot` directory exists.
- **Pre-registration** (EVALUATION_PROTOCOL section 12, committed in `4b66dcc` at 2026-10-12 21:24:39 +0530; the main session started at 21:24:51 +0530, 15:54:51 UTC in `session.json`; design files written 21:20:33): strongest baselines B0 P-only (all pools) and B4 greedy (scarce P, predicted before the run); reference, blocks and conditions as below. The design hashes in the protocol equal the `design_sha256` of the sessions (`e5302e6b...6ae0` and `9f619cc8...7f0f`; checked here).
- **Sessions.**

| Session | Design hash | Pools | Instances | Blocks | Runs | Reference | Run time (UTC) |
|---|---|---|---|---|---|---|---|
| `stage4_main` (`sessions_main/20261012T212448`) | `e5302e6b...6ae0` | 6 P + 7 E | `d1.1 c56.7_24.0`, `d1.1 c10.7_41.3` (2 blocks each) | 4 | 44 (11 conditions) | B0 P-only | 15:54 to 19:25, 3 h 31 min |
| `stage4_regimeR_P2E7` (`sessions_regimeR/20261013T005542`) | `9f619cc8...7f0f` | 2 P + 7 E | `d1.1 c56.7_24.0` | 3 | 15 (5 conditions) | B4 greedy | 19:25 to 21:19, 1 h 54 min |
| `stage4_gpu_workload` (`gpu/sessions/20261013T025636`) | `0a90f93d...e718` | 6 P + 7 E + 1 CUDA | 68-task image workload, tile 1024 | 12 | 84 (7 conditions) | B0 P-only | 21:26 to 21:57, 31 min |

  Not pre-registered: the GPU session's design file `gpu/designs/design_gpu.json` is not part of EVALUATION_PROTOCOL section 12; its file time (02:56:26 +0530) is ten seconds before the session started. Its reference (B0 P-only) follows the main session's choice, and the three extra analyses against B4_cpu, B4_gpu and EFT_E1_cpu (`gpu/analysis_ref_*`) were made after seeing the first analysis, so they are exploratory.
- All three sessions ran from source hash `5650bc0ab775` (`src_sha256` `5650bc0ab77574f86087632f4274a92146b6c8e6b0db0e0a0585a5bd4af9be54`), git HEAD `4b66dcc` with the dirty flag true (the files that made it dirty were not recorded). No session was excluded, no warm-up block (`warmup_blocks` 0), all runs included in the primary analysis (`n_excluded` 0 in all three `analysis.json`; the sensitivity variant including all runs is identical).
- E-only, round-robin and random are required baselines that were not re-run in Stage 4 (27 minutes per block, cannot be the strongest baseline); their numbers are the Stage 2 means in section 6 and are never pooled with Stage 4.

### 8.2 Main experiments

**Main session (6 P + 7 E workers, 2 instances x 2 blocks, reference B0 P-only).** All 44 runs completed with verified output; makespan geometric mean pooled over instances with a 95% bootstrap interval stratified by instance (`analysis_main/summary.csv`), paired effect against B0 P-only (`effects.csv`, tier confirmatory, `n_blocks` 4), scheduling and inference time per run (`summary.csv`, `sched_overhead_total_s_mean`) and tasks on E cores over the four runs of each condition (`gate_sessions_main.json`, `tasks_per_pool`).

| Policy | Makespan (s) | Effect vs B0 P-only | Decision time per run (s) | Tasks on E |
|---|---|---|---|---|
| B0_P_only | 268.5 (267.9 to 269.0) | reference | 0.0009 | 0 |
| EFT_E1_rc | 272.0 (271.2 to 272.7) | +1.30% (+0.81 to +1.80) | 0.023 | 0 to 2 |
| EFT_E1 | 272.0 (271.1 to 272.9) | +1.31% (+0.85 to +1.77) | 0.021 | 0 |
| EFT_CatBoost | 272.3 (271.7 to 272.9) | +1.42% (+1.07 to +1.77) | 1.50 | 0 to 2 |
| EFT_E3 | 272.5 (272.0 to 273.0) | +1.50% (+1.29 to +1.71) | 0.022 | 0 to 9 |
| EFT_E1_rank (instrument) | 272.6 (271.9 to 273.3) | +1.55% (+1.16 to +1.94) | 0.021 | 0 |
| EFT_MLP | 272.8 (272.1 to 273.5) | +1.62% (+1.55 to +1.69) | 0.115 | 2 to 6 |
| EFT_Ridge | 272.8 (272.4 to 273.3) | +1.64% (+1.41 to +1.86) | 0.056 | 1 to 5 |
| HEFT_E1 | 273.3 (272.2 to 274.3) | +1.80% (+1.55 to +2.05) | 0.0031 | 9 |
| PEFT_E1 | 273.5 (271.3 to 275.6) | +1.86% (+0.94 to +2.80) | 0.0031 | 9 |
| B4_greedy_eligible | 414.4 (414.1 to 414.8) | +54.38% (+54.07 to +54.70) | 0.0014 | 9 to 10 |

Every interval of an EFT, HEFT or PEFT policy lies above zero, so these policies were slower than B0 P-only, by 3.5 s to 5.0 s (computed here from the geometric means). The achieved 80%-power minimum detectable effect per contrast is 0.38% to 2.07% (`effects.csv`, column `mde_pct_80power`). Per-instance means and ranges are in `summary.csv` (for example B0 P-only 268.1 s and 268.8 s, EFT_E1 272.1 s and 271.9 s on the two instances). The instrument variants (kernel-only and end-to-end) were not run as separate conditions; `EFT_E1_rank` is the end-to-end instrument with the E1 predictor.

**Mechanism: early versus late binding (primary instance; consistent with and confirmed by the worker and timeline records; not tested as a controlled experiment).** With 6 P workers and 9 `mProject` tasks, P-only runs two waves: six tasks first (142 s to 147 s each) and three later (114 s to 119 s each). Late binding hands the three remaining tasks to whichever workers finish first. EFT, HEFT and PEFT predict all P workers equal and bind the later tasks at dispatch time to a worker that does not necessarily finish first, whose first-wave time differs by several seconds. Computed here from the raw event logs of `sessions_main`: the last `mProject` completion occurs 260.6 s to 262.7 s after run start in the four B0 P-only runs (mean 261.2 s) and 263.4 s to 265.9 s in the four EFT_E1 runs (mean 264.6 s), a difference of 3.4 s that matches the makespan difference (268.5 s against 272.0 s, 3.5 s). Decision time is not the cause: EFT_E1 spends 0.021 s per run on decisions. The pairing of workers that produces the 3.4 s was taken from the parent session's check of worker assignment; this report verified the timing difference, not each assignment.

**Scarce-P regime (2 P + 7 E workers, primary instance, 3 blocks, 15 runs, reference B4 greedy).** All runs completed with verified output.

| Policy | Makespan mean (s), min to max | Effect vs B4 greedy | Decision time per run (s) | Tasks on P / E |
|---|---|---|---|---|
| B4_greedy_eligible | 407.6 (407.2 to 408.0) | reference | 0.0013 | 23 to 26 / 33 to 36 |
| EFT_E1 | 407.6 (407.5 to 407.6) | -0.01% (-0.12 to +0.11) | 0.015 | 39 to 41 / 18 to 20 |
| HEFT_E1 | 407.9 (407.5 to 408.1) | +0.06% (+0.03 to +0.09) | 0.0029 | 33 / 26 |
| EFT_CatBoost | 468.6 (467.9 to 469.8) | **+14.96%** (+14.73 to +15.39) | 1.16 | 31 / 28 |
| B0_P_only | 576.5 (574.6 to 577.7) | +41.43% (+41.13 to +41.68) | 0.0008 | 59 / 0 |

The pre-registered expectation held: P-only needs about five waves (the protocol estimated about 560 s; observed 576.5 s) and greedy B4 is the strongest simple policy. EFT_E1 equals B4; HEFT is 0.06% (0.24 s, computed here) slower with an interval that excludes zero but is tiny.

**Mechanism: knife-edge decisions amplify prediction bias (computed here from the decision records of the three `EFT_CatBoost` runs, identical in all three).** With E1 the seventh to ninth `mProject` tasks go to E cores (predicted 401.1 s on E; actual 393 s to 399 s) while six tasks queue on the two P workers (predicted finish 335.3 s, actual about 345 s). CatBoost predicts the first two `mProject` tasks on P at 130.1 s and 134.2 s and every later one at 94.4 s, against actual 112.5 s to 115.7 s (an under-prediction of about 16% to 18%), so queued P finish times look short: the seventh and eighth tasks are queued on P0 and P1 with predicted finish 413.3 s and 417.4 s, while the best E finish is predicted 450.3 s (CatBoost also over-predicts the E-core time: 450.3 s against actual 401 s to 402 s, about +12%). Both errors push the same way, and correcting either one alone would flip the decision. Result: seven `mProject` tasks queue on two P workers, the last ending 459.7 s after run start (E-core placement would end near 400 s), which is the +15.0% (60 s) of the table. The parent session's summary of this decision gave the E prediction as 401 s (the E1 value); the CatBoost run records give 450.3 s (flagged in section 14.3). The lesson stands either way: Ridge, the more accurate model offline (MAE 1.36 s against 3.26 s for E1 on the held-out instance), does not guarantee a better schedule, because what matters is the error on the decisive task type at a near tie. The correlation of offline error and scheduling outcome across six predictors is not tested here.

**Cross-checks.** Friedman test over all conditions (unadjusted): main p = 0.032, scarce-P p = 0.034 (`crosscheck.csv`); these only say the conditions differ, driven mainly by B4 and P-only respectively.

**Excluded runs.** None in any session (`exclusions.csv` empty apart from the header; `runs.csv` `included_primary` true for 44, 15 and 84 runs).

### 8.3 Hypothesis check

The pre-stated criteria of section 1 applied to the tables above: the support criterion (a paired-block advantage whose interval excludes zero in some high-ratio condition against the strongest non-predictive baseline) was not met in any of the three conditions; the rejection criterion ("no condition where predictive placement beats the strongest non-predictive baseline") is met for the conditions tested. The per-claim outcome table is in section 1. A null result is stated as a null.

## 9. Correctness

- Stage 1: sequential output identical across three runs and header checks passed (section 5).
- Stage 2: 42 of 42 runs verified, 0 failing checks (`stage2_gate.json`).
- Stage 3 collection: 42 of 42 collection runs completed and verified against the instance reference (RESEARCH_STATUS Stage 3 report); pilot 18 of 18 verified, `n_failing_checks` 0 (`pilot_gate.json`). The dataset manifest records a SHA-256 for every source log.
- Stage 4: `gate_sessions_main.json` (44 runs), `gate_sessions_regimeR.json` (15 runs): `n_failing_checks` 0; all runs `completed` true and `output_verified` true, 0 dependency violations, 0 worker overlaps, 0 ineligible placements (counts re-summed here). `runs.csv` of the GPU analysis: 84 runs, status ok, `output_ok` and `log_ok` true; tolerances are those of the GPU spike (`img_edges` max abs 1 and fraction 0.001, `img_features` relative 1e-9, `img_denoise` exact). Main-session outputs are byte-identical to each instance's sequential reference.
- Failure-injection tests (non-zero exit, hang with process-tree kill, missing output, dead worker, unmapped task, early-binding queue) pass in the suite (ARCHITECTURE_DECISIONS AD-3).
- Test suite: the last recorded full run is **377 passed, 1 skipped** on 2026-10-12 21:24 (`stage3_20261012/full_suite_before_commit.txt`). No suite log exists for the Stage 4 source state (`src_sha256` differs from the Stage 3 sessions), so the suite status at the time of the Stage 4 runs is not recorded.
- Train/serve parity and leakage tests (`tests/test_parity_leakage.py`, 10 tests) are inside the 377.

## 10. Overhead

- **Decision time** (`summary.csv`, pooled, mean per run and per decision, includes estimator inference, which the log cannot separate; `not_measured_note` in `analysis.json`):

| Policy | Per decision | Per run (59 tasks) | Share of makespan |
|---|---|---|---|
| B0 P-only | 15 µs | 0.0009 s | 0.0003% |
| B4 greedy | 23 µs | 0.0014 s | 0.0003% |
| HEFT, PEFT | 52 µs, 53 µs | 0.0031 s | 0.001% |
| EFT_E1, E1_rank, E1_rc, E3 | 350 µs to 394 µs | 0.021 s to 0.023 s | 0.008% |
| EFT_Ridge | 0.96 ms | 0.056 s | 0.02% |
| EFT_MLP | 1.95 ms | 0.115 s | 0.04% |
| EFT_CatBoost | 25.3 ms | 1.50 s | 0.55% |

  Shares computed here from `summary.csv`. In the scarce-P session CatBoost costs 1.16 s per run (19.6 ms per decision).
- **Queue wait, task time.** Reported in `summary.csv` per run as sums over tasks (not wall time); the overhead figure `analysis_main/fig_overhead_breakdown.png` shows queue wait of 441 s to 453 s of task-seconds per run for every policy except B4 (0.53 s; B4 binds only to idle workers, effect -99.88% in `effects.csv`; values computed here from `summary.csv`) and a decision-time bar too small to see at that scale.
- **Transfer and setup:** transfer is "not measured" (local pools share a directory, zero by construction); setup/staging time is not reported as a separate component by the analysis (ARCHITECTURE_DECISIONS AD-8). **Utilisation** is in `summary.csv` (`utilisation_mean`: 0.355 for P-only, 0.350 for the EFT policies, 0.398 for B4 in the main session; its definition was not re-read from `analyze_experiment.py`). Peak memory of the run is not recorded; predictor memory and latency are in section 7.2.
- **Does the gain survive once decision cost is counted?** There is no gain to carry through: makespan is end-to-end and already contains decision time, and the predictive policies are slower than P-only even before decision time is subtracted (EFT_E1's decision time is 0.02 s of the 3.5 s deficit). The most expensive predictor, CatBoost, adds 1.5 s per run, about 0.55% of makespan.
- Overhead per run in Stage 2 beyond the makespan (about 2.3 s, derived by the v1 collection plan from 15,314 s for 42 runs) is a planning figure and was not recomputed.

## 11. GPU workload [real, separate workload]

Workload: the 68-task image pipeline stage structure (1 source, 16 tiles, 16 denoise, 16 edges, 16 features, aggregate, mosaic, package) at tile 1024 px with 16 branches, with CUDA variants for `img_denoise`, `img_edges` and `img_features`, one CUDA worker (`gpu_stage_table`: all three true), RTX 3050 6 GB Laptop GPU. Montage has no GPU path; no claim is made about Montage on GPU.

**GPU kernel evidence** (`stage1_20261011/gpu/spike_20261012T092018/gpu_spike.json`, script sha256 `09f88cc0...`, copies included in the GPU time, one thread, machine not idle): at 1024 px `img_edges` 13.96x (CPU 33.9 ms, GPU 2.43 ms), `img_features` 4.87x, `img_denoise` 1.03x (radius 2.0, 1 iteration; 1.15x with 8 iterations); all bit-exact or inside the stated tolerances (`max_abs` 0.0). At 512 px `img_denoise` with 1 iteration is below 1 (0.88x to 0.91x, verdict DROPPED; 1.02x with 8 iterations), so it is not GPU evidence below 1024 px; at 1024 px it is allowed and marginal. Profile used by the scheduler at tile 1024 (`gpu/profile_t1024/20261013T025309_profile.json`, median of 5): per branch on a P core `img_denoise` 24.7 ms, `img_edges` 35.5 ms, `img_features` 9.7 ms; on the GPU 23.8 ms, 2.6 ms, 2.2 ms. The CPU-only stages dominate: `img_source` 5.63 s on a P core (14.40 s on E) and `img_package` 0.67 s on P (1.60 s on E), so about 6.3 s of a makespan of about 7.1 s is CPU-only work that no placement can move to the GPU (computed here from the profile and `summary.csv`). The GPU stages are milliseconds.

**Session** `gpu/sessions/20261013T025636`: 12 blocks x 7 conditions = 84 runs, all complete and verified, reference B0 P-only. Makespan geometric mean pooled, 95% interval (`gpu/analysis/summary.csv`), and paired effects (`gpu/analysis/effects.csv`, 12 blocks; p_holm from the stored table, which is attainable with 12 blocks):

| Condition | Makespan (s) | Effect vs B0 P-only | p_holm |
|---|---|---|---|
| B0_P_only (CPU only) | 7.083 (7.044 to 7.117) | reference | |
| EFT_E1_gpu | 7.054 (7.025 to 7.080) | **-0.41% (-0.92 to +0.02)** | 0.129 |
| EFT_E1_cpu (same policy, GPU removed) | 7.197 (7.155 to 7.244) | +1.62% (+0.99 to +2.23) | 0.0052 |
| HEFT_E1_gpu | 7.290 (7.258 to 7.322) | +2.93% (+2.20 to +3.70) | 0.0024 |
| B4_gpu (priority G, P, E) | 7.343 (7.295 to 7.387) | +3.67% (+2.91 to +4.38) | 0.0033 |
| B4_cpu | 7.376 (7.355 to 7.397) | +4.15% (+3.55 to +4.83) | 0.0024 |
| random_gpu | 13.10 (10.73 to 15.83) | +85.01% (+51.17 to +123.01) | 0.0024 |

Contrasts that matter for the story (exploratory, chosen after the first analysis; `gpu/analysis_ref_*/effects.csv`, `analysis.json` `reference`): EFT_E1_gpu against EFT_E1_cpu **-2.00%** (interval -2.77 to -1.27, p_holm 0.0048); EFT_E1_gpu against B4_gpu **-3.94%** (interval -4.58 to -3.24, p_holm 0.003); B4_gpu against B4_cpu **-0.46%** (interval -1.12 to +0.23, includes zero).

Reading, with the scale stated: the GPU helps the predictive policy by about 2.0% (0.14 s, computed here from the two means: 7.197 s to 7.054 s), which brings EFT_E1 to the level of the CPU-only P-only baseline (-0.41%, interval includes zero), not below it. Predictive placement is therefore **not** better than the strongest simple baseline on this workload (claim (a) not supported) although it is better than the greedy GPU-aware baseline (3.9%, 0.3 s) and than HEFT. The absolute gains are a fraction of a second because CPU stages dominate. Output verification: 84 of 84 runs verified (`runs.csv`, `output_ok` true). Claims about GPU scheduling are limited to this workload and this GPU.

Figures: `gpu/analysis/fig_makespan_by_policy.png`, `fig_effect_vs_baseline.png` (shows the +85% random bar, which compresses the others), `fig_overhead_breakdown.png`.

## 12. Limitations

1. **One machine, one hardware configuration, one session family.** Conclusions are machine-specific; no pooling across machines.
2. **Patched Windows Montage build and a patched generator copy.** The native build needed twelve workarounds and the generator has three edits; the difference from the upstream Linux behaviour is not quantified.
3. **The machine was not idle** (WSL VM, browser, editor). Timing noise is part of the results; no per-run record of other processes exists (only free RAM at preflight).
4. **One dominant task type, a pool speed ratio of 3.59, and two 59-task instances in the main session.** A trivial rule (use only P cores) is optimal with at least three P workers, so the null was expected by construction (EVALUATION_PROTOCOL 12.6). The workload cannot show where prediction helps.
5. **Pre-registration flaw (Holm sign-flip test with 3 to 4 blocks cannot be significant).** Significance is "not resolved by this design"; results are descriptive intervals (section 4.4).
6. **Small block counts** (4 in the main session, 3 in the scarce-P session, 12 in the GPU session); minimum detectable effects 0.38% to 2.07% in the main session (`effects.csv`).
7. **HEFT and PEFT are implemented from secondary-source definitions** (originals unreachable), and HEFT's rank term averages communication over pools; their results hold for these implementations.
8. **Patent claim wording is not verified verbatim** (paraphrase through a fetch tool; PDF unreadable). No freedom-to-operate statement is made.
9. **DSS image data licence and terms of use are not verified.** Raw images are stored with hashes; they and any figure derived from them are not to be redistributed until checked.
10. **Raspberry Pi 5 extension not done.** No claim about real edge offloading, network, foreign clock or ARM Montage. All Pi statements are **[plan]**.
11. **The emulated remote pool was not used in any Montage run.** The earlier link-shim evidence is historical **[emulation]**.
12. **The GPU workload is dominated by CPU stages** (about 6.3 s of 7.1 s); absolute gains are fractions of a second; the GPU session was not part of the written pre-registration (section 8.1).
13. **The early-versus-late-binding mechanism for the 1.3% to 1.9% deficit is not tested as a controlled experiment** (no run with the two binding styles differing in nothing else); it is an observation from the logs of one instance. The knife-edge mechanism is shown from the decision records of one regime.
14. **First-run and failed attempts are kept** (Stage 1 runs A to C and `rep1` to `rep3`, the Stage 2 smoke session with the cleanup-before-reverify bug, the empty first dataset build). They are excluded from every gate by rule and documented; they are in the raw data.
15. **The dashboard header text still shows the old machine description** ("Intel Core i5-1235U, 2 P-cores + 8 E-cores", `src/caosched/dashboard/static/index.html` line 15 and `app.js` line 679), including in the historical tabs; it is not the machine of this study.
16. **Few learning rows and one dominant task type for the predictors:** 2,706 fitting rows, 20% on E, all from one sky region; the learned models are worse than the static profile on the 19-task fold; median APE is dominated by sub-second tasks. TabM excluded for this reason.
17. **Labels exist only for executed placements.** Counterfactual pools are covered by the E1 base profile plus the log correction and by random placement during collection.
18. **Instances share a sky centre.** The final-test instance is a larger instance of a region also used in training; generalisation to other workflows is untested.
19. **Different code states across stages.** Stage 2, Stage 3 and Stage 4 sessions ran from three different `src_sha256` values and git dirty flags were true throughout; sessions are not pooled in any scheduling analysis, but the Stage 3 dataset pools Stage 2 and Stage 3 sessions.
20. **Reduced collection design (v2)** and an unreferenced `stage3_20261012/designs_v3/` directory whose role is not documented in the project documents.
21. **Figure caveats.** The makespan figures label the axis "log scale" while the plotted ticks look linear, the y-axis does not start at zero, the "evidence: real" caption overlaps the first tick label, and the overhead figure's decision-time bar is invisible; I did not check the plotting code.
22. The thresholds in the evaluation protocol were provisional until the pilot; changes after the freeze are dated amendments (STAGE3_FREEZE A1 to A3).

## 13. Reproducibility

- Raw immutable logs, configurations, hashes and manifests: `data/results/stage1_20261011/`, `stage2_20261012/`, `stage3_20261012/`, `stage4_20261012/`. Stage 4 evidence manifest `stage4_20261012/SHA256_MANIFEST.tsv` (366 entries; covers the three sessions, the analyses `analysis_main`, `analysis_regimeR`, `gpu/analysis`, `gpu/analysis_ref_EFT_E1_cpu` and `gpu/analysis_ref_B4_cpu`, the designs and the GPU profile; it does not list `gpu/analysis_ref_B4_gpu`, computed here). Stage 0 SHA-256 manifest of `data/` and the Git exclusion record are in commit `7651eca`; `data/` is not in Git, so Git alone cannot reproduce any timing.
- Code version of each session: `src_sha256` `5650bc0ab775...` for all three Stage 4 sessions (`e6c902ff9863...` for Stage 3, `a8e349763604...` for Stage 2); git HEAD `4b66dcc` with dirty flag true in the Stage 4 sessions. Sessions with different code, machine, environment or design hash are never pooled (`analyze_experiment.py`).
- Analysis from raw logs: `python scripts/analyze_experiment.py --sessions <session dirs> --out <dir> --reference <condition> --seed 0`. Outputs: `runs.csv`, `exclusions.csv`, `summary.csv`, `effects.csv`, `crosscheck.csv`, `analysis.json`, three figures.
- **Reproduction from raw logs** (`scripts/reproduce_subset.py`, results `stage4_repro/repro_analysis_main.json`, `repro_analysis_regimeR.json`, `repro_gpu.json`): all four checks pass in each of the three files and `ok` is true: per-session SHA-256 manifest of the evidence directory (`sessions_*/<session>/SHA256_MANIFEST.tsv`), event-log hashes against the run manifests, and the summary and effects tables re-derived from the raw logs and matched. A first attempt the same evening (kept in `stage4_repro/first_attempt_without_session_manifests/`) had `ok` false only because the per-session manifests did not exist yet. Hash check of the Stage 0 data (`stage4_repro/historical_data_verify.json`): 12,627 files checked, 0 missing, 0 changed; `ok` is false only because 15,275 files that did not exist at Stage 0 are present (the new Stage 1-4 results and the Montage tree; the JSON lists the first 50 only).
- Clean-checkout run of a small subset (`scripts/reproduce_clean_checkout.py`): Observed 2026-10-12 22:19-22:21 UTC (`data/results/stage4_repro/repro_clean_checkout_log.json`, copy of the log written by `scripts/reproduce_clean_checkout.py`): clone of branch `redesign/montage` at its tip into a new directory, fresh Python 3.11.9 venv from `requirements-lock.txt` (torch lines dropped, no CUDA), `pytest` on 4 test files, stub-adapter experiment, analysis, SHA-256 manifest build and verify and `reproduce_subset.py`, and a read-only hash check of the Montage binaries and the primary instance: all 18 steps exit 0 (about 2 minutes). Limits (as recorded in the log): data/ is not in Git, so Montage and its timings are not re-run; the stub adapter is synthetic (label plan); only a 4-file pytest subset ran; CUDA tests and the GPU spike are not covered.. The clean checkout cannot rerun Montage or reproduce any timing.
- Machine hygiene checklist: [REPRODUCE.md](REPRODUCE.md) section 11. Its section 12 holds the observed clean-checkout log.
- Commit that contains the final report: see `git log` on branch `redesign/montage` (the commit named 'Final: clean-checkout reproduction, status and report updates').

## 14. Decisions and unverified list

Decisions made by the assistant under the project owner's delegation (the owner may overrule; then a new freeze and new session are needed): [STAGE3_FREEZE.md](STAGE3_FREEZE.md) (instance roles, candidates, TabM out, margin 2.0%, splits, dated amendments A1 to A3); [STAGE3_COLLECTION_PLAN.md](STAGE3_COLLECTION_PLAN.md) v2 (reduced design); [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) section 12 (Stage 4 pre-registration, strongest baselines, block counts, Holm family); the scarce-P regime and the GPU session design.

### 14.1 Completion checklist (only items with evidence)

- [x] Stage 1: workload runs, three identical sequential outputs, DAG extracted with no manual edits (`stage1_gate.json`).
- [x] Stage 2: 14 policies x 3 blocks = 42 runs, all verified, 0 failing checks (`stage2_gate.json`).
- [x] Stage 3: dataset manifest with hashes and exclusions (`dataset/20261012T195206/manifest.json`); six predictors evaluated on held-out rows with accuracy, latency, memory (`eval/*/metrics.json`); `d1.5` evaluated once; scheduling pilot 18 of 18 verified; selection by the frozen rule: EFT_E1 (`selection_record.json`).
- [x] Stage 4 main session: 44 of 44 runs complete, verified, 0 violations (`gate_sessions_main.json`); analysis tables and three figures (`analysis_main/`).
- [x] Stage 4 scarce-P session: 15 of 15 runs (`gate_sessions_regimeR.json`, `analysis_regimeR/`).
- [x] GPU workload: 84 of 84 runs verified, effects with 12 blocks (`gpu/analysis/`).
- [x] Pre-registration committed before the main session started (commit `4b66dcc` 21:24:39 +0530; first run 21:24:51 +0530).
- [x] Tables re-derived from raw logs and event-log hashes checked for the three Stage 4 analyses (`stage4_repro/repro_*.json`, all checks pass, see section 13).
- [x] Evidence manifest of Stage 4 written (`stage4_20261012/SHA256_MANIFEST.tsv`, 366 entries, regenerated after all Stage 4 files existed; per-session manifests inside each session directory).
- [x] Report sections 1 to 14 written with the outcome wording per claim; presentation outline filled ([PRESENTATION_OUTLINE.md](PRESENTATION_OUTLINE.md)).
- [x] Clean-checkout reproduction of the code path (`stage4_repro/repro_clean_checkout_log.json`, 18 of 18 steps) and full suite on the final source state (377 passed, 1 skipped, `stage4_20261012/full_suite_final.txt`; mypy `src/caosched` 0 issues).
- [x] Historical evidence preserved: 12,627 Stage 0 data files, 0 missing, 0 changed (`stage4_repro/historical_data_verify.json`); no tracked data or test file was modified or deleted.
- Not complete (no evidence): Raspberry Pi 5 (later extension, not part of the gates); time-ordered drift check, learning curve and regret table of the plan (not run); a controlled test of the early-binding mechanism; verbatim patent claims and the HEFT/PEFT originals.

### 14.2 Decisions needed from the owner

1. **Holm flaw.** Accept the descriptive reading ("not resolved by this design") or authorise more blocks (at least 6 for one contrast, at least 9 for a family of ten, computed here) in a new session with a new design hash, plus an amended confirmatory family.
2. **Further conditions.** Whether to test any condition where prediction might matter (for example other P worker counts, a workload with several heavy task types or a smaller pool ratio). None is analysed here; the project spec names the hypothesis condition (large ratio and contention) as untested beyond the two regimes run.
3. **Raspberry Pi 5.** Go or no-go for the later extension (ARM Montage build, real network, foreign clock, authentication).
4. **Data rights and licences.** DSS image terms and redistribution (and so whether the mosaic image may appear in slides), the licences of the tools bundled with w64devkit, the patent claim text (supply the Google Patents text or a text-layer PDF).
5. **HEFT and PEFT originals.** Supply the PDFs, or keep the "secondary sources" wording.
6. **Archiving and Git.** `data/` is excluded from Git and the clean checkout cannot reproduce timings; decide where the evidence directories are archived, and whether to commit the Stage 4 tooling files and this report (nothing is committed by this task).
7. **Dashboard header text.** Whether to fix the old machine description in `src/caosched/dashboard/static` (code change, not made here).
8. **Presentation details.** Title wording, author, date and institution (PRESENTATION_OUTLINE slide 1); whether to produce the missing architecture, ladder and DAG figures.
9. **Complexity order** (E1 < E3 < E1+rc < Ridge < CatBoost < MLP versus measured latency and size): leave as frozen (the selection is unaffected) or write a dated amendment.

### 14.3 Unverified list

- Literature positioning (PROJECT_SPEC section 6) and LITERATURE_UPDATE.md: sources not all read; the 20 open items of LITERATURE_UPDATE section 6; HEFT, CPOP and PEFT originals not read; the "not found in sources inspected" gap statement is a bounded search, not a proven gap.
- Verbatim US 11,561,826 B1 claim wording; the patent legal status beyond the catalogue entry.
- DSS image data licence and terms; licences of tools bundled with w64devkit and of the libraries bundled in the Montage tree (cfitsio, bzip2, wcssubs, freetype, jpeg, lodepng).
- Read-only status of the stored input files.
- Any statement about novelty beyond what the literature check supports.
- Raspberry Pi 5 behaviour; the remote-node code on a second host (never executed on another machine).
- The class-to-core-type reading of the Windows efficiency classes (class 1 as P, class 0 as E) is mine; the topology API output itself is in `environment.json`.
- The mechanism for the 1.3% to 1.9% deficit was verified here for the timing (last `mProject` end 3.4 s later) but the worker pairing behind it was taken from the parent session's check; it is not a controlled experiment.
- The CatBoost knife-edge numbers: the parent session's summary put the E-core prediction at 401 s and the under-prediction at 85 to 94 s; the decision records give 450.3 s for E and 94.4 s (130 s and 134 s for the first two tasks) for P. This report uses the decision records.
- Whether the "dirty" flag in every Stage 4 session reflects only untracked or modified non-source files: not recorded.
- Whether the full test suite passes on the exact Stage 4 source state: no log exists.
- Meaning and use of `stage3_20261012/designs_v3/`: not documented.
- Which sessions in the Stage 3 dataset used which design file beyond the `d1.5` hash match (`ff97ffe8...`): only the `d1.5` design hash was checked here.
- RESEARCH_STATUS.md (modified in the working tree, not edited here) has a "State" line that still says Stage 2 to 4 experiments are not yet run, and its Stage 3 pilot sentence says every EFT variant places all tasks on P; the Stage 4 main-session records show EFT_E3, EFT_MLP, EFT_Ridge, EFT_CatBoost and EFT_E1_rc sometimes placing 1 to 9 (non-`mProject`) tasks on E.
- The GPU contrasts against B4_cpu, B4_gpu and EFT_E1_cpu are post-hoc.
- Utilisation definition and the unadjusted Friedman test's suitability for this design (EVALUATION_PROTOCOL section 9 already marks the latter **unverified**).
