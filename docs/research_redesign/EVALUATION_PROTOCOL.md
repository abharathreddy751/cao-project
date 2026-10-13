# Evaluation protocol

Status: **proposal; frozen after Stage 1 review**, 2026-10-11. Thresholds are provisional and are set from pilot measurements. Evidence labels as in [PROJECT_SPEC.md](PROJECT_SPEC.md). Scope: this machine; Raspberry Pi 5 is a later extension.

## 1. Questions the evaluation answers

1. Does predictive placement beat the strongest applicable non-predictive baseline, and under which workload and resource conditions, after overhead is counted?
2. How accurate must the predictor be, and what does sophistication cost?
3. Do predictors and schedulers hold on workflow instances or sizes not seen in training?
4. Is output correct and reproducible under every policy?

Prediction quality and scheduling value are reported separately: low prediction error does not imply a better schedule.

## 2. Baselines and compared methods

| Role | Methods |
|---|---|
| Required non-predictive baselines | B4 greedy eligible dispatch (patent-mapped comparison baseline, not an implementation of the patent); E-only; round-robin; random |
| Published static list schedulers | HEFT (upward rank + insertion-based earliest finish with a profile cost matrix); PEFT (optimistic cost table). CPOP optional. HEFT/PEFT originals still to be read **[unverified]** |
| Predictive ladder (existing) | EFT with E0 constant, E1 static profile, E2 analytic, E3 moving history, E1+rc, E4 learned ridge (and fast variant) |
| Added predictors | CatBoost; MLP; TabM only if entry rule below is met |
| Proposed instrument | Rank-priority + predicted, queue-aware, transfer-aware EFT with online recalibration, with kernel-only and end-to-end variants |
| Oracle references | E5 replay oracle as an *offline reference only*; it is not an upper bound (earlier finding) |
| Excluded from the minimum project | GNN+PPO, GRU/TCN, temporal Transformer, GNN predictor, pixel embeddings |

The "strongest applicable baseline" for each comparison is the best of the non-predictive and published methods on that workload, chosen from the pilot, not after seeing the final results.

## 3. Prediction target and features

- Target: per-task, per-device kernel (compute) time. Setup/staging time, transfer time, queue wait and scheduling/prediction time are measured separately and are not mixed into the target.
- Queue wait and transfer are state- and link-dependent quantities; they are computed from runtime state and the link model at decision time, and compared with the later measurement for accuracy reporting only.
- Allowed features: task type, input file sizes, declared resources, target pool or device, decision-time occupancy, history observed before the decision, calibration from profiles that predate the session.
- Forbidden: anything measured after the decision (actual start, actual queue length at start, later completions, future profiles); labels from the same run in features; raw Montage pixels (unless a pilot shows size/metadata features leave error that image content explains — then a separately labelled study).
- Offline features must be reconstructed from the logged online decision context. A parity test enforces this.

## 4. Predictor selection

| Candidate | Use | Reason |
|---|---|---|
| E1, E3, +rc, Ridge | Required references | Existing; low cost |
| CatBoost | Required comparator | Strong structured-data baseline; trees often win at ~10k samples (Grinsztajn 2022, abstract only) |
| MLP | Required | Neural baseline |
| TabM | Conditional | Enter only if the pilot dataset has enough samples for a stable fit and CatBoost/MLP leave scheduling-relevant error; inference and memory counted. Its benchmarks cover medium-to-large tabular datasets and it is slower than MLP/GBDT |
| GRU/TCN, temporal Transformer | Excluded | Only if resource telemetry sequences are shown to add information in a pilot; none of the inspected sources show that for runtime prediction |
| GNN | Excluded | No inspected source shows a GNN beating tabular models for runtime; graph structure used through priority ranks |

Selection rule (fixed before the pilot): choose the cheapest model whose scheduling outcome is not worse than that of a more complex model within the confidence interval.

## 5. Data splits

- Primary unit: workflow instance (configuration/size) and session. Never random rows.
- Training on some instances and sizes; validation on others for tuning; test on instances or sizes never used for training or tuning.
- Within one session, time-ordered splits; across sessions, session-held-out splits.
- Profiles and calibration values used for a run must have been produced before that run.
- Final model refit uses the pre-declared procedure; test data is touched once.
- Reference: leakage taxonomy of Kapoor and Narayanan 2023 (preprint read).

## 6. Prediction metrics

MAE, RMSE, median and mean absolute percentage error with its limitation near small values, signed bias, calibration (observed versus predicted by decile), inference latency per call and per decision (distribution, not only mean), peak memory, model size, training time. Computed per task type, per device and overall, on held-out instances only.

## 7. Scheduling metrics

End-to-end makespan; task execution time; queue wait; setup/staging; data transfer; scheduling and inference overhead (per decision and total); CPU/GPU utilisation where instrumented (otherwise "not measured"); memory footprint; output correctness; throughput only where several workflows run; placement regret from logs (one-step hindsight, with its limits); change relative to the strongest applicable baseline. All come from the raw event log.

## 8. Experimental design

- Controlled machine state: no other heavy applications; memory preflight (earlier sessions were interrupted by low free memory); environment manifest per session.
- Interleaved blocks: each block runs every condition once in seeded random order; blocks repeated; instance order randomised. Cross-configuration comparisons are not made unless interleaved (earlier finding: session drift).
- Repetitions: set from the pilot variance to reach a pre-declared confidence-interval half-width; the number is not fixed in advance. The earlier Phase 6B study reached about ±2.65% with 33 blocks on the older machine; this is **not** a target for the new design.
- Warm worker pools and recorded warm-up; first runs excluded only by a rule written beforehand.
- Seeds recorded for orders and any stochastic model.
- Any run that fails, times out or has an output mismatch is kept in the raw data, flagged, and excluded from primary analysis only under the pre-declared rule, with a sensitivity analysis including it.

## 9. Statistical analysis

- Paired within-block effects (log ratio of makespan against the reference) with a stratified percentile bootstrap, as in `analysis/stats.py` (per-metric seeds to be added).
- Report effect sizes with intervals, not only p-values; for multiple conditions use Friedman/Wilcoxon-type non-parametric comparison as a cross-check (Demšar 2006, abstract only) — **unverified** that it suits this design.
- Report variability (spread, not only mean), and the minimum detectable effect for the achieved number of blocks.
- No claim is made for an effect whose interval includes zero.
- Provisional thresholds (for example, what counts as a practically relevant improvement) are set after the pilot and stated before the main runs.

## 10. Correctness tests

- Montage: final mosaic hash equal, or within a stated numeric tolerance, to the Stage 1 sequential reference; WCS header sanity.
- CPU/GPU: output equivalence on fixed inputs within a stated tolerance, for every GPU stage used; failing stages are not used as GPU evidence.
- Runtime: all dependencies respected, no worker runs two tasks at once, no ineligible placement.
- Feature parity and leakage tests (section 5).
- Reproduction: a subset reproduced from raw logs and from a clean checkout.

## 11. Result recording

- Raw logs append-only and never overwritten; derived files carry tags and are re-derivable.
- Every result file has a manifest: configuration snapshot, environment manifest, code version and source hash, seeds, input hashes.
- SHA-256 manifests for evidence directories.
- Every table and figure states its label: real, replay, emulation, simulation or plan.
- Results from the earlier machine are history and are not combined with new results.

## 12. Pre-registration for the Stage 4 main run (written 2026-10-12, BEFORE the first main block)

Status: **[plan] frozen before the main sessions start.** The design files are the pre-registration; their SHA-256 is stored by the runner and in every run manifest. Anything changed after the first main block creates a new session with a new design hash and its own report. Written by the assistant under the owner's delegation; numbers come from the files cited.

### 12.1 Evidence used to set the design (pilot-type data, not part of the main analysis)

* Stage 2 matrix (`data/results/stage2_20261012/sessions/20261012T101305`, 14 policies x 3 blocks, analysis `stage2_20261012/analysis_stage2/effects.csv`, reference B0 P-only): paired sd of log makespan (sd_log) among the predictive/plan contrasts is between 0.0005 (EFT_E1_rank) and 0.0109 (EFT_E3); the largest of the confirmatory contrasts is 0.0109 (EFT_E3). Predictive and plan policies were 0.9% to 1.7% **slower** than B0 P-only (EFT_E1 +1.69%, CI +1.55% to +1.92%); B4 greedy was +51.5% (CI +51.1% to +51.8%) slower than B0 P-only.
* Stage 3 scheduling pilot (`stage3_20261012/pilot_sessions`, 6 predictors x 3 blocks, EFT with E1, E3, E1+rc, Ridge, CatBoost, MLP): all 18 runs verified, mean makespans 271.4 to 272.7 s, i.e. within 0.5% of each other. Model selection by the frozen rule (`stage3_20261012/selection/selection_record.json`, margin ln 1.02): **EFT_E1 is selected** (cheapest model not worse than any more complex one).
* Pool profile: mProject 111.8 s on a P-core, 401.1 s on an E-core. With 9 mProject tasks the possible gain of any placement is bounded: all-P gives about two waves of 112 s (observed 270 s total), the best mix with scarce P-cores is bounded by one E-core task (401 s).

### 12.2 Strongest applicable baseline (chosen before the main run)

* Regime with all pools (6 P + 7 E workers): **B0 P-only** (270.9 s, fastest non-predictive policy in the Stage 2 matrix). B4 greedy is the patent-mapped comparison baseline and is also reported.
* Regime with scarce fast cores (2 P + 7 E workers): **B4 greedy** is expected to be the strongest simple policy (P-only needs five waves of 112 s = about 560 s, greedy puts tasks on E-cores and is bounded by 401 s); this is a prediction made here from the profile, to be checked by the run, not an assumed result.

### 12.3 Sessions (design files in `data/results/stage4_20261012/designs/`)

| Session | Design file (sha256) | Pools | Instances | Blocks | Conditions | Reference |
|---|---|---|---|---|---|---|
| `stage4_main` | `design_main.json` (`e5302e6b3ac31b4f0a1b150f16196c746d81cc2763b36dc0c524cfbc6ce06ae0`) | 6 P + 7 E | d1.1 primary, d1.1 c10.7 (2 blocks each, seeded order) | 4 | B0 P-only, B4 greedy, HEFT, PEFT, EFT E1, EFT E3, EFT E1+rc, EFT Ridge, EFT CatBoost, EFT MLP, rank-priority EFT (E1) | B0 P-only |
| `stage4_regimeR_P2E7` | `design_regimeR.json` (`9f619cc8dfa393302430e29cb6f988807551a4897d413602d7517abd93bc7f0f`) | 2 P + 7 E | d1.1 primary | 3 | B0 P-only, B4 greedy, EFT E1, HEFT, EFT CatBoost | B4 greedy |

The proposed instrument is the rank-priority, predicted, queue-aware EFT with the predictor selected in Stage 3 (E1). E-only, round-robin and random are required non-predictive baselines; they are reported from the Stage 2 matrix (same machine, same instance, 3 blocks) and are **not** re-run in the main session, because they cost 27 minutes per block and cannot be the strongest baseline. They are never pooled with the main session (different design hash).

### 12.4 Repeat count

Rule (Section 9, `analysis/stats.py`): blocks n = ceil((1.96 + 0.84) * sd_log / ln(1 + m))^2 for a target minimum detectable effect m. With the largest observed sd_log = 0.0109 and m = 2% (the selection margin; below 2% differences cannot be separated from block noise in the pilot data) the rule gives n = 3; the design uses **4 blocks** (2 per instance, so both instances are balanced) for the main session and 3 for the regime session (budget-limited; the achieved half-width and MDE are reported, the regime session is exploratory about sensitivity, not confirmatory). If the achieved MDE exceeds 2% the report says "not resolved by this design". Blocks are fixed in advance; no interim looks.

### 12.5 Primary and secondary analysis

* Confirmatory family (Holm-adjusted): makespan contrasts of the instrument (rank-priority EFT, E1) and of each EFT predictor against the reference B0 P-only, paired within block, percentile bootstrap stratified by instance (`analysis/stats_paired.py`).
* Exploratory: every other contrast, per-task times, queue wait, decision overhead per decision and in total, transfer (none: shared directory), utilisation where logged, and the regime session. Correctness: every included run's final outputs must be byte-identical to the instance's sequential reference.
* Exclusions (`stats_paired.exclusion_reason`): session not complete, run status not ok, log missing/hash mismatch, output unverified or failed, no makespan. Excluded runs stay in the raw data; the sensitivity analysis includes them.
* Outcome wording: "supported", "not supported" or "not resolved by this design". No claim for an interval that includes zero.

### 12.6 Controls and limits stated in advance

* Machine not idle by nature (WSL VM, browser, editor); memory preflight 2.5 GB before every block; environment manifest per session.
* Code state: sessions run from the committed code of the Stage 3 commit plus the files listed in the Stage 4 commit; a dirty flag is recorded in each manifest.
* The workload has one dominant task type (nine equal mProject tasks) and a pool speed ratio of 3.6: a trivial rule (use only P-cores) is optimal when at least three P workers exist, so a **null result against the strongest baseline is expected by construction** and is a reportable finding, not a failure.

## 13. Pre-registration of the confirmatory sessions (written 2026-10-13, BEFORE their first block)

Why: section 12's main design (4 blocks) cannot reach p < 0.05 under its own Holm-adjusted sign-flip test (minimum attainable p = 2/2^4 = 0.125), and the GPU session of the first round was written 10 seconds before it started, without a pre-registered analysis plan. The first-round sessions (`stage4_20261012`) are therefore treated as the PILOT for the sessions below; their numbers are not pooled with them (different design hashes). Block counts here are the smallest n for which the smallest attainable sign-flip p-value 2/2^n is below the Holm threshold of the family.

| Session | Design (sha256) | Pools | Blocks | Conditions | Reference | Family / threshold |
|---|---|---|---|---|---|---|
| `stage5_main_confirm` | `design_main_confirm.json` `9228d7ac5bc4115554b5b9267d248ef24433d38dfe206844a1adf91fe9a94648` | 6 P + 7 E | 9 (instances alternate primary / c10.7) | B0 P-only, **B0 P-early (new)**, B4, HEFT, PEFT, EFT E1, E3, E1+rc, Ridge, CatBoost, MLP, rank-EFT | B0 P-only | 11 contrasts; Holm threshold 0.05/11 = 0.0045; 2/2^9 = 0.0039 |
| `stage5_regimeR_confirm` | `design_regimeR_confirm.json` `7dac58e327362e752e0cf31679ab205d28ed56ce773544112b8eab34bb905126` | 2 P + 7 E | 8 (primary) | B0 P-only, B4, EFT E1, Ridge, CatBoost, MLP | B4 greedy | 5 contrasts; Holm 0.01; 2/2^8 = 0.0078 |
| `stage5_gpu_confirm` | `gpu/design_gpu_confirm.json` `273a155df65f69ebcadb14eabfc62c8b6618028dcd06f12af43198978f3d8af7` | P, E + CUDA pool G, tile 1024, 16 branches | 24 | B0 P-only, B4 cpu, B4 gpu, random gpu, EFT E1 cpu, EFT E1 gpu, HEFT gpu | EFT E1 cpu | 6 contrasts; Holm 0.0083; 2/2^24 negligible |

Adapter configs are in the same directories (SHA-256 recorded in the session `session.json`/run manifests). A background-load monitor (`scripts/load_monitor.py`) logs machine CPU, free RAM and the top non-experiment processes every 30 s during all sessions (`stage5_20261013/load/`), so how idle the machine really was is a measured quantity in the report.

### 13.1 Pre-stated predictions (made from the pilot, before the confirmatory data)

* P1 (mechanism): `B0_P_early` is slower than `B0_P_only` by 1% to 2% in the main session (same placement set, early instead of late binding). Supported only if the Holm-adjusted contrast is significant and positive.
* P2: in the main session EFT/HEFT/PEFT variants are slower than B0 P-only by 1% to 2%; B4 is about 54% slower.
* P3: in the scarce-P session EFT E1 equals B4 within +-0.5%; B0 P-only is about 41% slower; EFT CatBoost is slower than B4 by about 15%. Ridge and MLP effects are exploratory (no prediction).
* P4: in the GPU session EFT E1 gpu is faster than EFT E1 cpu by 1% to 3%.
Outcome wording per prediction: supported (pre-stated direction, Holm-significant, effect inside the stated range or stated as outside it), not supported, or not resolved. No other claim is confirmatory.

### 13.2 Analyses planned for the same data

Analysis tables from `scripts/analyze_experiment.py` per session with the stated reference; Friedman/Wilcoxon cross-check (scipy 1.17.1 installed; reported as a cross-check, not a substitute); utilisation = busy seconds of a worker divided by session-run makespan from `task_completed` intervals; overhead components as in `analysis/stats_paired.py`. Exclusion rules unchanged (section 12.5). Early-binding claims are drawn only from the `B0_P_early` contrast and the worker timelines.
