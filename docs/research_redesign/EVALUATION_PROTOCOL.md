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


## 14. Pre-registration of the emulated remote-pool session (written 2026-10-14, BEFORE its first block; label: emulation)

What is emulated: one real node process on a core of this machine behind a loopback link shim with a configured latency, bandwidth and per-message cost (no jitter, no real network, no foreign clock, no ARM host, no authentication beyond the tested handshake). All results of this session are labelled **emulation** and are never pooled with real-hardware sessions. Calibration (2026-10-14, idle machine, `data/results/stage5_20261013/remote/remote_profile.json`, raw `remote_profile_raw.csv`): transfer = 0.779 ms + 1.617 ns per byte at shim zero (n=60, median absolute residual 0.084 ms).

Design `data/results/stage5_20261013/designs/remote/design_remote.json` (sha256 `4dab0106d6d9a86af400af779cd2aaf789b7389d73c7b53eea77f89cb6ea3d57`; adapter config `7b6c04ee8ab30ec192448f09df980d5cb1b89351638c1fd88fd75c271589caac`): image pipeline tile 512, 16 branches, pools P (2 workers), E, R (emulated node), 7 conditions (B0 P-only, B4 no remote, EFT E1 no remote, B4 and EFT E1 with R on `fast_lan` 0.2 ms / 1000 Mbit/s and on `slow_wan` 30 ms / 20 Mbit/s), 12 blocks, reference `EFT_E1_no_remote`; family 6 contrasts, Holm threshold 0.05/6 = 0.00833, minimum attainable sign-flip p at 12 blocks 0.000488 (n >= 8 suffices, so up to 4 blocks may be lost). Pre-stated directions: D1 B4 with R is slower than B4 without R on the WAN link; D2 EFT places fewer tasks on R on the WAN link than on the LAN link; D3 no direction for EFT with R on the LAN link. Wording per prediction: supported / not supported / not resolved. The profile check stored in the design (modelled transfer time over R kernel time per stage and link) is the evidence that transfer is a visible share of task time on these links.

## 15. Results of the confirmatory sessions (written 2026-10-14, AFTER all four sessions and their analyses; sections 12 to 14 above are unchanged)

Paths are under `data/results/stage5_20261013/` (`S5`). Numbers are copied from the `effects.csv` of each analysis directory (rows `variant primary`, `metric makespan_s`, columns `cond`, `ref`, `effect_pct`, `ci_lo_pct`, `ci_hi_pct`, `p_holm`; 10,000 bootstrap resamples, seed 0) and from `summary.csv` and `gate_*.json`. Interpretation and caveats: [FINAL_REPORT.md](FINAL_REPORT.md) sections 8 and 11. The first-round Stage 4 sessions (section 12) are the PILOT and are not pooled with these results.

### 15.1 Execution facts

| Session | Design sha256 (as in section 13 or 14) | Blocks | Runs | Started to finished (UTC, 2026-10-13) | Gate (`S5/gate_*.json`) | Excluded runs |
|---|---|---|---|---|---|---|
| `stage5_main_confirm` | `9228d7ac...4648` (matches `analysis.json`) | 9 of 9 | 108 | 07:51:19 to 17:15:59 | 108 completed and verified, 0 failing checks | 0 |
| `stage5_regimeR_confirm` | `7dac58e3...5126` (matches) | 8 of 8 | 48 | 17:16:04 to 23:19:09 | 48 completed and verified, 0 failing checks | 0 |
| `stage5_gpu_confirm` | `273a155d...8af7` (matches) | 24 of 24 | 168 | 06:49:56 to 07:51:15 | 168 completed and verified, 0 failing checks | 0 |
| `remote_emulation_confirm` (label **emulation**) | `4dab0106...3d49` (matches) | 12 of 12 | 84 | 23:22:40 to 23:39:15 | 84 completed and verified, 0 failing checks | 0 |

Total 408 runs. Each session was committed to the protocol before its first block (section 13: commit `13d1649` at 12:19:40 +0530, first run 12:19:56 +0530; section 14: commit `868eeea` at 04:52:28 +0530 on 2026-10-14, first run 04:52:40 +0530). No design was changed after its first block; no interim look was taken.

### 15.2 Main session (reference B0 P-only, 9 blocks, family of 11 contrasts, smallest Holm step 0.05/11 = 0.0045, significant if `p_holm` < 0.05; `S5/analysis_main/effects.csv`)

| Condition | Effect (95% CI) | p_perm | p_holm | Significant | Post-hoc effect without blocks 5 and 6, 7 blocks (95% CI) |
|---|---|---|---|---|---|
| B0_P_early | +1.675% (+1.236 to +2.310) | 0.0049 | 0.0360 | yes | +1.403% (+1.197 to +1.598) |
| EFT_E1 | +1.619% (+1.210 to +2.277) | 0.0048 | 0.0360 | yes | +1.330% (+1.193 to +1.475) |
| EFT_E1_rank | +1.415% (+1.036 to +1.986) | 0.0047 | 0.0360 | yes | +1.148% (+0.980 to +1.308) |
| EFT_E3 | +1.586% (+1.113 to +2.221) | 0.0039 | 0.0360 | yes | +1.306% (+1.023 to +1.638) |
| EFT_Ridge | +1.536% (+1.119 to +2.059) | 0.0041 | 0.0360 | yes | +1.305% (+1.055 to +1.633) |
| HEFT_E1 | +1.545% (+1.144 to +2.083) | 0.0045 | 0.0360 | yes | +1.335% (+1.094 to +1.564) |
| PEFT_E1 | +1.730% (+1.135 to +2.476) | 0.0031 | 0.0341 | yes | +1.371% (+1.016 to +1.846) |
| EFT_CatBoost | +8.678% (+1.323 to +24.659) | 0.0044 | 0.0360 | yes | +1.444% (+1.229 to +1.696) |
| EFT_E1_rc | +13.925% (+1.633 to +41.714) | 0.0039 | 0.0360 | yes | +1.931% (+1.293 to +2.763) |
| EFT_MLP | +12.99% (+1.748 to +37.71) | 0.0036 | 0.0360 | yes | +2.043% (+1.393 to +3.028) |
| B4_greedy_eligible | +47.868% (+37.473 to +54.586) | 0.0052 | 0.0360 | yes | +53.49% (+51.59 to +55.47) |

Geometric-mean makespan of the reference B0 P-only: 282.99 s (all blocks, interval 271.7 to 304.5), 272.40 s (post-hoc set). Every contrast above is in the same direction in 9 of 9 blocks (computed from `analysis_main/runs.csv`). The post-hoc analysis (`S5/analysis_main_posthoc_excl_blocks_5_6/`, `--posthoc-exclude-blocks 5 6`, 24 runs listed in `exclusions.csv`) is **post-hoc and not pre-registered**; with 7 blocks its `p_holm` is 0.1584 for every contrast, so it cannot be significant and is read as intervals only. **Slow window:** blocks 5 and 6 (0-based ids `b0005`, `b0006`): 14 consecutive runs from 12:40:54 UTC (`b0005_00`) to the start of `b0006_02` at 14:29:56 UTC ran slower; block 5 about 1.4 times for every policy except B4, and three runs (`b0005_11_EFT_CatBoost` 712.1 s, `b0006_00_EFT_E1_rc` 750.1 s, `b0006_01_EFT_MLP` 683.7 s) about 2.5 times. The cause is identified: the laptop ran on battery from 18:11:21 to 19:59:07 local (`S5/windows_power_source_events.json`, Kernel-Power event 105); the load monitor (`S5/load/load_20261013T121952.jsonl`) shows no heavy non-experiment process. The exclusion rules of section 12.5 do not exclude such runs, so the table above is the pre-registered primary result.

### 15.3 Scarce-P session (reference B4 greedy, 8 blocks, family of 5 contrasts, smallest Holm step 0.01, significant if `p_holm` < 0.05; `S5/analysis_regimeR/effects.csv`)

| Condition | Effect (95% CI) | p_perm | p_holm | Significant |
|---|---|---|---|---|
| B0_P_only | +42.476% (+41.045 to +43.543) | 0.0081 | 0.0325 | yes |
| EFT_CatBoost | +15.647% (+14.835 to +16.117) | 0.0065 | 0.0325 | yes |
| EFT_E1 | -0.130% (-1.102 to +0.881) | 0.5515 | 1 | no |
| EFT_MLP | -0.019% (-0.212 to +0.266) | 0.9112 | 1 | no |
| EFT_Ridge | **-0.585%** (-1.185 to -0.184) | 0.0089 | 0.0325 | yes (below the 2% practical margin) |

Geometric-mean makespan of B4: 412.17 s; EFT_Ridge faster than B4 in 8 of 8 blocks (computed from `runs.csv`).

### 15.4 GPU session (reference EFT_E1_cpu, 24 blocks, family of 6 contrasts, smallest Holm step 0.0083, significant if `p_holm` < 0.05; `S5/analysis_gpu/effects.csv`)

| Condition | Effect vs EFT_E1_cpu (95% CI) | p_holm | Significant |
|---|---|---|---|
| EFT_E1_gpu | **-2.102%** (-2.934 to -1.348) | 0.0006 | yes |
| B0_P_only | -1.457% (-2.135 to -0.791) | 0.0012 | yes |
| HEFT_E1_gpu | +0.959% (+0.248 to +1.698) | 0.0396 | yes |
| B4_gpu | +1.484% (+0.362 to +2.587) | 0.0396 | yes |
| B4_cpu | +2.042% (+1.228 to +2.728) | 0.0012 | yes |
| random_gpu | +56.57% (+33.63 to +83.04) | 0.0006 | yes |

Exploratory second reference B0 P-only (`S5/analysis_gpu_vs_P/effects.csv`): EFT_E1_gpu -0.655% (-1.824 to +0.343), p_holm 0.2721; EFT_E1_cpu +1.478% (+0.806 to +2.171); B4_gpu +2.984% (+1.474 to +4.478); B4_cpu +3.551% (+2.458 to +4.335); HEFT_E1_gpu +2.451% (+1.693 to +3.176). **Computed here** (not in a stored table): EFT_E1_gpu against B4_gpu -3.53% (block-wise log ratios of `analysis_gpu/runs.csv`, 22 of 24 blocks faster; the point estimate equals the difference of the two stored effects).

### 15.5 Remote-pool session [emulation] (reference EFT_E1_no_remote, 12 blocks, family of 6 contrasts, smallest Holm step 0.0083, significant if `p_holm` < 0.05; `S5/analysis_remote/effects.csv`, `S5/analysis_remote_vs_B4/effects.csv`, `S5/gate_remote.json`)

| Condition | Tasks on R (12 blocks) | Effect vs EFT_E1_no_remote (95% CI), p_holm | Effect vs B4_no_remote (95% CI), p_holm |
|---|---|---|---|
| B0_P_only | 0 | -6.399% (-7.444 to -5.488), 0.0035 | -6.745% (-7.677 to -5.832), 0.0035 |
| B4_no_remote | 0 | +0.371% (-0.862 to +1.455), 1 | reference |
| B4_remote_fast_lan | 12 | +1.423% (+0.239 to +2.474), 0.1368 | +1.048% (+0.006 to +2.272), 0.4128 |
| B4_remote_slow_wan | 12 | +31.18% (+29.90 to +32.60), 0.0024 | **+30.69%** (+29.42 to +32.02), 0.0024 |
| EFT_E1_remote_fast_lan | 0 | +0.138% (-1.095 to +1.187), 1 | -0.232% (-1.240 to +0.811), 1 |
| EFT_E1_remote_slow_wan | 0 | +0.320% (-0.846 to +1.551), 1 | -0.051% (-1.208 to +1.184), 1 |

Link calibration (`S5/remote/remote_profile.json`): transfer = 0.779 ms + 1.617 ns per byte (n = 60). The `analysis.json` label of this session is `emulation`; the `label` field of `gate_remote.json` reads `real` (a field of the gate script, not of the analysis), and the session's own `session.json` and `design.json` say `emulation`.

### 15.6 Outcome per pre-stated prediction (wording of section 13.1 and section 14)

| Prediction | Outcome |
|---|---|
| P1: `B0_P_early` slower than `B0_P_only` by 1% to 2%, Holm-significant and positive | **Supported**: +1.675% (+1.236 to +2.310), p_holm 0.036 (post-hoc +1.403%, +1.197 to +1.598) |
| P2: EFT/HEFT/PEFT 1% to 2% slower than B0 P-only; B4 about 54% slower | **Supported** for EFT_E1 (+1.619%), E3 (+1.586%), rank (+1.415%), Ridge (+1.536%), HEFT (+1.545%), PEFT (+1.730%). **Direction only** for EFT_CatBoost (+8.678%), EFT_E1_rc (+13.925%) and EFT_MLP (+12.99%): their all-blocks magnitude is dominated by three runs of the slow window (+1.444%, +1.931%, +2.043% post-hoc). B4: +47.868% all blocks, +53.49% post-hoc |
| P3: scarce-P, EFT_E1 equals B4 within +-0.5%; B0 P-only about 41% slower; EFT_CatBoost about 15% slower | **Supported** for P-only (+42.476%) and CatBoost (+15.647%). EFT_E1: point estimate -0.130% inside +-0.5%, interval -1.102 to +0.881 wider than the band: **equivalence not resolved**. Ridge (-0.585%, p_holm 0.0325) and MLP (-0.019%) were exploratory |
| P4: EFT_E1 gpu faster than EFT_E1 cpu by 1% to 3% | **Supported**: -2.102% (-2.934 to -1.348), p_holm 0.0006 |
| D1 (emulation): B4 with R slower than B4 without R on the WAN link | **Supported**: +30.69% (+29.42 to +32.02), p_holm 0.0024 |
| D2 (emulation): EFT places fewer tasks on R on the WAN link than on the LAN link | **Not supported**: 0 tasks on R on both links, no placement on R at all |
| D3 (emulation): no direction for EFT_E1 with R on the LAN link | EFT_E1_remote_fast_lan +0.138% (-1.095 to +1.187), p_holm 1: not distinguishable from no remote |

### 15.7 Claims of section 12.5 after the confirmatory sessions

(a) Prediction beats the best non-predictive baseline in some condition: **not supported at the practical margin (2%) in all four conditions**; the only statistically significant advantage of a predictive policy over the strongest simple baseline is EFT_Ridge over B4 (-0.585%, 8 of 8 blocks) in the scarce-P regime, below the margin and not predicted. (b) A simple method matches prediction: **supported**. (c) Predictor sophistication improves scheduling: **not supported** (scarce-P CatBoost +15.647% worse, Ridge -0.585%, E1 and MLP tie B4). (d) Generalisation: offline Ridge yes on the held-out `d1.5` instance (MAE 1.36 s against 3.26 s for E1); scheduling effects do not depend on it. (e) Significance: **resolved** for P1, P3 (except equivalence of EFT_E1 at +-0.5%), P4 and D1.

### 15.8 Deviations and notes

* The post-hoc exclusion analysis and the second-reference analyses (`analysis_gpu_vs_P`, `analysis_remote_vs_B4`) were made after seeing the primary analyses and are exploratory; the stored `p_holm` of those tables adjusts within their own family. D1 is the exploratory contrast stated in section 14.
* The GPU session ran from source hash `d6e480bcfa67`, the main, scarce-P and remote sessions from `95a74ba36708` (`analysis.json`, `code_versions`); git dirty flag true in all four. Sessions are not pooled.
* The minimum free RAM seen by the load monitor (2.09 GB at 20:36:08 UTC, scarce-P session) is below the 2.5 GB preflight threshold, which is evaluated at block start; all runs of that session verified.
* Evidence manifests exist per session (`SHA256_MANIFEST.tsv` inside each session directory); a stage-level manifest of `S5` was written afterwards (`data/results/stage5_20261013/SHA256_MANIFEST.tsv`). Re-derivation of the `summary` and `effects` tables from the raw logs: `data/results/stage5_repro/repro_analysis_{main,regimeR,gpu,remote}.json`, all `ok`.
