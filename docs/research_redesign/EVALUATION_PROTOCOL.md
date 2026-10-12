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
