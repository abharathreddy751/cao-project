# Final report: skeleton

Status: **[plan] skeleton written 2026-10-12 during Stage 3 data collection.** It contains structure, fixed text taken from the project documents, and result slots. Every result value is the literal marker `PENDING(<evidence file that will supply it>)`, except Stage 1 and Stage 2 values quoted from `data/results/stage1_20261011/valid/stage1_gate.json` and `data/results/stage2_20261012/stage2_gate.json` with file and field named. Evidence-file paths inside `PENDING(...)` markers for files that do not exist yet are provisional names; fix them when the files are written. No sentence in a result section may be filled without a value from the named file. Evidence labels: **[real]** measured on real hardware; **[replay]**; **[emulation]**; **[simulation]**; **[plan]**; **[unverified]** (as in [PROJECT_SPEC.md](PROJECT_SPEC.md)).

## 1. Question and hypothesis

Source: [PROJECT_SPEC.md](PROJECT_SPEC.md) sections 4 and 5.

- **Research question.** Under what workload and resource conditions does execution-time prediction improve dynamic DAG scheduling on heterogeneous resources after accounting for prediction, scheduling, queueing and data-transfer overhead?
- **Primary contribution.** A controlled, overhead-accounted, real-hardware study of how much predictor sophistication improves actual DAG scheduling of a real scientific workflow, using decision-time-safe data and a ladder from no prediction to learned models.
- **Supporting contributions.** (1) Generalisation of predictors and schedulers to instances and sizes not seen in training. (2) Transfer-aware placement to a remote or GPU pool: **[emulation]** for the remote pool, **[real]** for the GPU on a separate workload.
- **Primary hypothesis (falsifiable, no promised size).** Prediction-aware placement beats the best non-predictive baseline only when the runtime ratios between resources and the contention are large relative to prediction cost, scheduling cost and timing noise. Otherwise a simple method matches it.
- **Supported by:** a paired-block makespan advantage whose confidence interval excludes zero in the high-ratio/high-contention conditions and not in the low conditions, after overhead is counted. **Rejected by:** no condition where predictive placement beats the strongest non-predictive baseline, or a gain that disappears once decision cost is counted. A null result is an accepted outcome.
- **Not claimed:** a new learning algorithm, a new list-scheduling algorithm, or novelty of "task graph + queues + eligibility" (claimed by the base patent, PROJECT_SPEC section 7). The proposed scheduler is a study instrument.
- **Verdict on the hypothesis:** PENDING(analysis/montage_main/effects.csv and analysis/montage_main/analysis.json). Written only after Stage 4; wording must be "supported", "not supported" or "inconclusive", with the interval.

## 2. Scope and evidence labels

- Machine-specific study: one laptop, one session family. Raspberry Pi 5 is a later extension; all Pi claims stay **[plan]**.
- Table of claims, each with its label and its evidence file: PENDING(table built from the sections below at the end of Stage 4).
- What is **[real]**: Montage under 14 policies on this machine (Stage 2), Stage 3 collection, Stage 4 runs, the GPU workload. What is **[emulation]**: the remote pool, from earlier work only, not used here. What is **[plan]**: Raspberry Pi 5. What is **[unverified]**: see section 14.
- Historical evidence from the earlier machine and the 68-task image pipeline is kept as history and is not pooled with the Montage data.

## 3. Workload and environment

Sources: [WORKLOAD_AND_DATA_PROVENANCE.md](WORKLOAD_AND_DATA_PROVENANCE.md), [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md), `data/results/stage1_20261011/environment_manifest.json` (not interpreted in this skeleton).

- **Workload.** Montage mosaic of DSS2 blue images, native Windows build of the Montage toolkit (Caltech-IPAC/Montage commit `ac0a15334f670ed83e328b6c5768f94b4b847359`, BSD 3-clause licence read in the `LICENSE` header), patched for Windows. Eight task types.
- **Primary instance** `d1.1_dss2b_c56.7_24.0`: 59 tasks, 147 dependency edges, 27 `mProject` tasks (`stage1_gate.json`: `dag.n_jobs` = 59, `dag.edges_jobDependencies` = 147, `per_transformation_wall_s.mProject.n` = 27). Edges from the job list and from file dependencies agree (`dag.only_in_jobDependencies` and `dag.only_in_files` both empty).
- **Other instances.** `d1.0_dss2b_c56.7_24.0` (19 tasks), `d1.1_dss2b_c10.7_41.3` (59 tasks), `d1.5_dss2b_c56.7_24.0` (157 tasks); roles in [STAGE3_FREEZE.md](STAGE3_FREEZE.md). Task counts and sequential times from `data/results/stage3_20261012/refs/<instance>/run.json`.
- **Input data.** Nine DSS images for the primary instance, 116,069,760 bytes in total, from host `archive.stsci.edu`, survey `poss2ukstu_blue`, fetched 2026-10-11, hashes in `data/montage/instances/d1.1_dss2b_c56.7_24.0/instance.json` (WORKLOAD_AND_DATA_PROVENANCE section 2). **Licence and terms of use of the image data are not verified.**
- **Environment.** Windows 11 Home laptop; CPU i5-13500HX with performance and efficiency cores (core layout [unverified] until the topology tool is interpreted); NVIDIA RTX 3050 6 GB Laptop GPU used only for the separate GPU workload. Exact versions, driver, Python and package versions: PENDING(data/results/stage1_20261011/environment_manifest.json). Worker pools: 13 workers, 6 P and 7 E in the Stage 2 profile (STAGE3_COLLECTION_PLAN section 3). Pool speed ratio from the Stage 2 profile: mProject 111.8 s on P and 401.1 s on E (STAGE3_FREEZE basis), source PENDING(data/results/stage2_20261012/profile_montage/20261012T092355_profile.json).
- **Machine state.** The machine was not idle during data collection (WSL VM, browser, editor); see section 12.

## 4. Method

### 4.1 System architecture

DAG runtime, coordinator, ready queue, event log, P/E worker pools, scheduler interface, estimator interface, dataset builder, analysis, dashboard. Components and where each is implemented: PENDING(docs/research_redesign/ARCHITECTURE_DECISIONS.md, summarised at final writing).

### 4.2 Scheduling algorithms

- Required non-predictive baselines: B0 (P-only, E-only), B1 round-robin, B2 static P, B3 shortest queue, B4 greedy eligible dispatch (a patent-mapped comparison baseline, not an implementation of the patent), B5 criticality, random.
- Predictive ladder: EFT with E1 static profile, E3 moving history, E1+rc online recalibration, `EFT_E1_rank` (rank priority); learned: Ridge (E4 form), CatBoost, MLP.
- Published static list schedulers: HEFT and PEFT, formulas from **secondary sources** because the originals were not reachable (PROJECT_SPEC section 6, **[unverified]**).
- Instrument: rank-based priority plus predicted, queue-aware, transfer-aware earliest-finish-time placement with online recalibration. A study instrument, not a novelty claim.
- Excluded: GNN+PPO, GRU/TCN, temporal Transformer, GNN predictor, image embeddings. **TabM is out** by the entry rule evaluated before data (needs at least 20,000 labelled rows; fewer than 2,600 exist), stated reason: too few rows for a neural tabular model (STAGE3_FREEZE section 2).

### 4.3 Predictors and data

- Target: per-task, per-device kernel time. Setup/staging, transfer, queue wait and scheduling/prediction time are separate (EVALUATION_PROTOCOL section 3).
- Candidates and complexity order: E1 < E3 < E1+rc < Ridge < CatBoost < MLP (STAGE3_FREEZE section 2; to be confirmed against measured latency and memory).
- Decision-time-safe features only; training rows from decision-context logs (`context_source=decision`) of runs whose output verified.
- Splits: leave-one-instance-out on three instances; time-ordered split for the drift check; `d1.5` final test, evaluated once.
- Collection design: STAGE3_COLLECTION_PLAN.md (`designs_v2/`, 42 runs, 2586 task rows at most). The v1 `designs/` directory is superseded and unused.

### 4.4 Selection rule and statistics

- Cheapest model whose outcome is not worse than every more complex model, upper bound of the paired-bootstrap interval of `outcome(simple) - outcome(complex)` at most `margin`; **margin = 2.0% of makespan** (STAGE3_FREEZE section 2).
- Confirmatory family: primary variant, makespan, every condition against the reference, Holm-adjusted sign-flip p-values; everything else exploratory and unadjusted (`stats_paired.py` metadata). Paired bootstrap, 10,000 resamples. Stage 4 repeat count and strongest-baseline choice come from the pilot and are fixed in EVALUATION_PROTOCOL section 12 before the main run: PENDING(docs/research_redesign/EVALUATION_PROTOCOL.md section 12).

## 5. Stage 1 results: reproducible workload [real]

All values from `data/results/stage1_20261011/valid/stage1_gate.json`, instance `d1.1_dss2b_c56.7_24.0`, `label` real.

| Item | Value | Field |
|---|---|---|
| Complete sequential runs | 3 of 3 (`completed_3_of_3` true) | `completed_3_of_3` |
| Wall time seq1, seq2, seq3 | 1459.4 s, 1467.1 s, 1469.3 s | `reps.seqN.total_wall_s` |
| Tasks per run, all timed | 59, `all_tasks_timed` true | `reps.seqN.n_tasks`, `all_tasks_timed` |
| Output hashes identical across runs | true | `output_hashes_identical` |
| Mosaic comparison, seq2 and seq3 against seq1 | `max_abs_diff` 0.0, shape and NaN pattern equal | `mosaic_comparison.comparisons[]` |
| WCS header checks | all ok (3960 x 3960 pixels, CRVAL 56.7, 24.0, TAN) | `wcs.all_header_ok`, `wcs.header_checks` |
| Finite fraction of the mosaic | 0.9666 | `wcs.finite_fraction` |
| Median `mProject` task time | 160.6 s (27 tasks) | `per_transformation_wall_s.mProject.median` |
| DAG edges, job list versus files | 147 and 147, no differences | `dag` |

Sequential reference runs for the other instances (status ok, from `data/results/stage3_20261012/refs/<instance>/run.json`, field `total_wall_s`): `d1.0` 489.7 s (19 tasks), `d1.1 c10.7_41.3` 1083.7 s (59 tasks), `d1.5` 1896.4 s (157 tasks).

Pool profile (Stage 2 prerequisite, from Stage 1 tooling): PENDING(data/results/stage2_20261012/profile_montage/20261012T092355_profile.json).

Reading: the workload runs completely and reproducibly on this machine. Hash identity across three sequential runs shows output determinism for the sequential case only; the parallel runs are checked in section 8.

## 6. Stage 2 results: heterogeneous runtime, 14 policies [real, descriptive]

Source: `data/results/stage2_20261012/stage2_gate.json`: 42 runs, `n_runs` 42, `n_failing_checks` 0, `failing` empty; 3 blocks, one run per condition per block. Values are `makespan_by_condition.<condition>.mean_s` (n = 3 each) in seconds, with min and max.

| Condition | Mean | Min | Max |
|---|---|---|---|
| B2_static_P | 269.6 | 267.0 | 271.5 |
| B0_P_only | 270.9 | 270.4 | 271.3 |
| EFT_E3 | 273.3 | 269.7 | 276.1 |
| HEFT_E1 | 274.5 | 273.8 | 275.9 |
| EFT_E1_rank | 274.7 | 274.4 | 275.1 |
| PEFT_E1 | 275.0 | 274.0 | 276.1 |
| EFT_E1_rc | 275.4 | 274.2 | 277.2 |
| EFT_E1 | 275.5 | 274.6 | 276.1 |
| B3_shortest_queue | 410.7 | 410.5 | 410.9 |
| B4_greedy_eligible | 410.5 | 409.9 | 411.1 |
| B5_criticality | 413.4 | 411.3 | 417.1 |
| random | 416.5 | 410.9 | 426.7 |
| B1_round_robin | 420.4 | 419.5 | 422.0 |
| B0_E_only | 811.8 | 811.4 | 812.1 |

Correctness in the same file: every run `completed` true, `output_verified` true, empty `dependency_violations`, `worker_overlaps` and `ineligible_placements` (`runs.<run>.*`).

**Honest reading (descriptive, three blocks per policy, no interval, no hypothesis test):**

1. **B0 P-only is as fast as the predictive policies.** B0 P-only (270.9 s) is not slower than any predictive policy: the predictive means lie between 273.3 s (EFT_E3) and 275.5 s (EFT_E1), about 0.9% to 1.7% above P-only. B2 static P (269.6 s) is the fastest mean. The per-policy range within three blocks reaches 6.4 s (EFT_E3, 269.7 s to 276.1 s), about 2.3% of its mean, which is the same size as the gaps between these policies. These data do not show any benefit of prediction over placing everything on the P pool on this workload and this worker set.
2. **Greedy B4 takes about one and a half times as long.** B4 (410.5 s) has a mean makespan 1.52 times that of B0 P-only (equivalently, P-only is about a third shorter). B3, B5, random and round-robin sit in the same 410 s to 420 s band.
3. **Likely mechanism, not tested:** in the per-run tables B4, B3, B5 place 9 to 10 of 59 tasks on E (`tasks_per_pool`), and the pool profile gives `mProject` 111.8 s on P against 401.1 s on E; HEFT and PEFT also place 9 tasks on E but finish near the EFT policies. The difference between those groups is therefore not explained by the E-task count alone; the cause is not established here.
4. This is a profile in which the P pool is much faster than the E pool for the dominant task type (`mProject`). It says nothing about workloads or worker sets with a smaller speed ratio. The hypothesis in section 1 predicts exactly this null for a low-ratio or low-contention setting; it is not tested by Stage 2 and must not be quoted as support or rejection.

## 7. Stage 3 results: prediction

### 7.1 Collection

- Designs, hashes, run counts: [STAGE3_COLLECTION_PLAN.md](STAGE3_COLLECTION_PLAN.md) section 4 (42 runs, `designs_v2/`).
- Runs completed / verified / excluded with reasons: PENDING(data/results/stage3_20261012/dataset/manifest.json).
- Rows per instance and per pool; coverage of `busy_P`, `busy_E`, `target_busy_frac`: PENDING(data/results/stage3_20261012/dataset/manifest.json).

### 7.2 Prediction quality (held-out rows only, separate from scheduling value)

| Metric (median APE is the headline) | E1 | E3 | E1+rc | Ridge | CatBoost | MLP |
|---|---|---|---|---|---|---|
| Median APE, leave-one-instance-out | PENDING(data/results/stage3_20261012/eval/metrics.csv) | PENDING(same) | PENDING(same) | PENDING(same) | PENDING(same) | PENDING(same) |
| MAE, RMSE, relative MAE, mean APE, signed bias | PENDING(data/results/stage3_20261012/eval/metrics.csv) | | | | | |
| Calibration by decile | PENDING(data/results/stage3_20261012/eval/calibration.csv) | | | | | |
| Per transformation and per pool | PENDING(data/results/stage3_20261012/eval/metrics_by_group.csv) | | | | | |
| Inference latency per call, peak memory, model size, training time | PENDING(data/results/stage3_20261012/eval/costs.csv) | | | | | |

Check for collapse to a per-type constant (one dominant task type): PENDING(data/results/stage3_20261012/eval/metrics_by_group.csv).

### 7.3 Generalisation

- Leave-one-instance-out folds (`d1.0`, `d1.1 c56.7_24.0`, `d1.1 c10.7_41.3`): PENDING(data/results/stage3_20261012/eval/metrics.csv).
- Time-ordered drift check within the primary session: PENDING(data/results/stage3_20261012/eval/metrics.csv).
- `d1.5` final test, evaluated once, size withheld: PENDING(data/results/stage3_20261012/eval_test/metrics.csv). Limit: the test instance shares its sky centre with two training instances.
- Learning curve (TabM entry rule condition 2; out regardless by condition 1): PENDING(data/results/stage3_20261012/eval/learning_curve.csv).

### 7.4 Decision-level regret

One-step hindsight regret of each candidate from the decision logs, compared with the pilot noise floor: PENDING(data/results/stage3_20261012/eval/regret.csv).

### 7.5 Model selection

Selected model by the rule of section 4.4 (margin 2.0%), with the record of every comparison: PENDING(data/results/stage3_20261012/eval/model_selection.json). Complexity order confirmed or amended against measured cost: PENDING(STAGE3_FREEZE.md amendments section).

## 8. Stage 4 results: scheduling

### 8.1 Pilot and design

Pilot summary, noise floor, repeat count, strongest non-predictive baseline (chosen from the pilot, not from final results): PENDING(data/results/stage4_pilot/pilot_summary.json). Main-run design and hash: PENDING(data/results/stage4_main/design.json).

### 8.2 Main experiment

- Makespan per policy, pooled and per instance (geometric mean, 95% bootstrap interval): PENDING(analysis/montage_main/summary.csv); figure PENDING(analysis/montage_main/fig_makespan_by_policy.png).
- Paired effect of each policy against the reference, with Holm-adjusted p-value for the confirmatory family: PENDING(analysis/montage_main/effects.csv); figure PENDING(analysis/montage_main/fig_effect_vs_baseline.png).
- Change relative to the strongest applicable baseline, by condition (high or low runtime ratio, high or low contention): PENDING(analysis/montage_main/effects.csv).
- Friedman and Wilcoxon cross-checks (unadjusted, cross-check only): PENDING(analysis/montage_main/crosscheck.csv).
- Variability (between-block spread per policy): PENDING(analysis/montage_main/summary.csv).
- Excluded runs with reasons: PENDING(analysis/montage_main/exclusions.csv). Per-run record: PENDING(analysis/montage_main/runs.csv).
- Instrument variants (kernel-only and end-to-end): PENDING(analysis/montage_main/effects.csv).

### 8.3 Hypothesis check

The pre-stated support and rejection criteria of section 1, applied to the table above: PENDING(analysis/montage_main/effects.csv).

## 9. Correctness

- Stage 1: sequential output identical across three runs and header checks passed (section 5, `stage1_gate.json`).
- Stage 2: 42 of 42 runs verified, 0 failing checks (`stage2_gate.json`: `n_runs`, `n_failing_checks`).
- Stage 3 collection: verified output for each included run, hash comparison against the instance reference: PENDING(data/results/stage3_20261012/dataset/manifest.json).
- Stage 4: dependency violations, worker overlaps, ineligible placements and output verification on all included runs: PENDING(analysis/montage_main/runs.csv).
- Test suite status at the time of the final run: PENDING(data/results/stage4_main/full_suite.txt). Last recorded figure in the project documents is 366 passed, 1 skipped on 2026-10-12 (FOUR_STAGE_IMPLEMENTATION_PLAN checklist); it predates the Stage 3 and analysis code.
- Train/serve parity and leakage tests: PENDING(data/results/stage4_main/full_suite.txt).

## 10. Overhead

- Scheduling and inference overhead per decision and per run, queue wait, transfer and setup, utilisation, memory: PENDING(analysis/montage_main/summary.csv); figure PENDING(analysis/montage_main/fig_overhead_breakdown.png). The figure shows measured components only; scheduling overhead includes estimator inference, which the log cannot separate (`analysis.json` field `not_measured_note`).
- Predictor latency and memory by model: PENDING(data/results/stage3_20261012/eval/costs.csv).
- Overhead per run in Stage 2 beyond the makespan (about 2.3 s, derived by the v1 collection plan from 15,314 s for 42 runs): the underlying figures are not in `stage2_gate.json`; treat as a planning figure until recomputed from PENDING(data/results/stage2_20261012/sessions/20261012T101305/session.json).
- Does the gain survive once decision cost is counted: PENDING(analysis/montage_main/effects.csv).

## 11. GPU workload [real, separate workload]

The GPU is an RTX 3050 6 GB Laptop GPU on a CPU/GPU workload that is separate from Montage. A GPU spike exists from Stage 1: PENDING(data/results/stage1_20261011/gpu/gpu_spike.json).

- Workload description, CPU and GPU kernel times, transfer cost: PENDING(data/results/stage1_20261011/gpu/gpu_spike.json).
- GPU scheduling experiment (placement with transfer cost, paired blocks): PENDING(data/results/stage4_main/gpu/gpu_effects.csv).
- Output verification on the GPU workload: PENDING(data/results/stage4_main/gpu/gpu_runs.csv).
- Claims about GPU scheduling are limited to this workload and this GPU; no claim about Montage on GPU.

## 12. Limitations

1. **One machine, one hardware configuration, one session family.** Conclusions are machine-specific; no pooling across machines.
2. **Patched Windows Montage build.** The Windows-patched generator and a native build were used; the difference from the upstream Linux behaviour is not quantified.
3. **The machine was not idle** (WSL VM, browser, editor). Timing noise is part of the results; repeated runs under identical conditions are not guaranteed (STAGE3_FREEZE section 4).
4. **Literature not fully verified.** Several sources were not read in the original; items are listed in section 14.
5. **HEFT and PEFT formulas come from secondary sources**; the original papers were not reachable. Their results are for these implementations.
6. **Raspberry Pi 5 extension not done.** No claim about real edge offloading, network, foreign clock or ARM Montage. All Pi statements are **[plan]**.
7. **Emulated remote pool not used.** The earlier link shim evidence is historical **[emulation]** and not part of the Montage study.
8. **DSS image data licence and terms of use are not verified.** Raw images are stored with hashes but the redistribution status is unknown; the images are not to be redistributed with this report.
9. **Few rows and one dominant task type.** About 1.6 thousand fitting rows; `mProject` is 98.7% of sequential time, so a learned model can collapse to a per-type constant (STAGE3_FREEZE section 4). TabM excluded for this reason.
10. **Labels exist only for executed placements.** Counterfactual pools are covered by the E1 base profile plus the log correction and by random placement during collection.
11. **Instances share a sky centre.** The final-test instance is a larger instance of a region also used in training; generalisation to other workflows is untested.
12. **Stage 2 is descriptive.** Three blocks per policy, no intervals; the P pool is much faster than E for the dominant task type, which favours P-only placement.
13. **Reduced collection design (v2).** Two `RandomOccupancy` settings only; the range of occupancy covered is checked after collection, not assumed.
14. The thresholds in the evaluation protocol were provisional until the pilot; changes after the freeze are dated amendments.

## 13. Reproducibility

- Raw immutable logs, configurations, hashes and manifests: `data/results/stage1_20261011/`, `data/results/stage2_20261012/`, `data/results/stage3_20261012/`, Stage 4 directory PENDING(data/results/stage4_main/manifest.json). Stage 0 SHA-256 manifest of `data/` and the Git exclusion record are in commit `7651eca`.
- Code version of each session: PENDING(session.json `src_sha256` fields of every session). Sessions with different code, machine, environment or design hash are never pooled (`analyze_experiment.py`).
- Analysis from raw logs: `python scripts/analyze_experiment.py --sessions <session dirs> --out analysis/montage_main --reference <condition> --seed 0`. Outputs: `runs.csv`, `exclusions.csv`, `summary.csv`, `effects.csv`, `crosscheck.csv`, `analysis.json`, three figures. Reproduce one result from raw logs: PENDING(data/results/stage4_main/reproduction_log.txt).
- Clean-checkout run of a small subset (`scripts/reproduce_clean_checkout.py`, `scripts/reproduce_subset.py`): PENDING(data/results/stage4_main/reproduction_log.txt).
- Machine hygiene checklist: [REPRODUCE.md](REPRODUCE.md) section 11. Dirty-flag state of the working tree at each session: PENDING(session.json).
- Commit that contains the final report: PENDING(git log after the final commit).

## 14. Decisions and unverified list

Decisions made by the assistant under the project owner's delegation (the owner may overrule; then a new freeze and new session are needed): STAGE3_FREEZE.md (instance roles, candidates, TabM out, margin 2.0%, splits); STAGE3_COLLECTION_PLAN.md v2 (reduced design). Dated amendments: PENDING(STAGE3_FREEZE.md amendments section).

Unverified items (carry unchanged from the project documents, to be copied here with their current status at final writing):

- Literature positioning (PROJECT_SPEC section 6) and LITERATURE_UPDATE.md: sources not all read; HEFT and PEFT originals not read.
- CPU core topology and the `environment_manifest.json` contents.
- DSS image data licence and terms.
- Licences of the tools bundled with the build toolchain (w64devkit) not read.
- Read-only status of the stored input files not checked.
- Any statement about novelty beyond what the literature check supports.
- Raspberry Pi 5 behaviour.
