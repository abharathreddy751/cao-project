# Stage 3 and Stage 4 draft: pilot, model selection and pre-registration

Status: **[plan] draft, 2026-10-12. Not part of the frozen protocol.** Written by a second session for merging into `EVALUATION_PROTOCOL.md` by the session that owns the repository, after the pilot data exist. Nothing here was run. Every threshold is a proposal. Where a number is needed, this draft gives the rule or formula that produces it and names the evidence file it must come from; it does not supply the number. Sources read for this draft: `FOUR_STAGE_IMPLEMENTATION_PLAN.md`, `EVALUATION_PROTOCOL.md`, `PROJECT_SPEC.md`, `WORKLOAD_AND_DATA_PROVENANCE.md`, `MONTAGE_WINDOWS_BUILD.md`, `data/results/stage1_20261011/valid/stage1_gate.json`, `data/results/stage1_20261011/gpu/gpu_spike_stdout.txt`, and the module headers of `experiment/design.py`, `experiment/runner.py`, `experiment/montage_adapter.py`, `analysis/stats.py`, `analysis/stats_paired.py`, `analysis/model_eval.py`, `dataset/splits.py`, `estimators/tabular.py`, `scripts/evaluate_models.py`, `scripts/analyze_experiment.py`. The code was read, not run, so statements about what it does are from its docstrings and a quick read.

## 0. Known facts that shape the design

These come from evidence files that already exist.

- The primary instance `d1.1_dss2b_c56.7_24.0` has 59 tasks. Nine `mProject` tasks take a median of 160.6 s each (range 141.0 to 169.9 s over 27 measurements); all other task types have medians under 5 s (`valid/stage1_gate.json`, `per_transformation_wall_s`). The three sequential makespans were 1459.4 s, 1467.1 s and 1469.3 s. Roughly 98% of sequential work is the nine equal `mProject` tasks.
- Consequence for the hypothesis: scheduling headroom on this instance is small by construction. After the nine reprojections, the remaining 50 tasks add seconds. A policy can differ mainly in how the nine `mProject` tasks are spread over pools and in how soon the tail starts. A null result is a legitimate outcome and must be reported as one.
- The GPU spike (`gpu/gpu_spike_stdout.txt`) shows that GPU use pays only at larger tiles: `img_edges` passes from 256 px (1.67x), `img_features` from 512 px (2.88x), `img_denoise` only from 512 px with 8 iterations (1.16x) and about 1.2x to 1.4x at larger tiles. Equivalence held (`eq=True`, `maxabs=0.0`) in every row. So the GPU workload must use tiles of 512 px or more, and `img_denoise` is a small-margin stage.
- The machine is not idle by nature (a WSL VM, a browser and an editor are present). Hygiene and the memory preflight are therefore part of the protocol, not an afterthought.

## 1. Stage 3: data, splits and the pilot

### 1.1 Data to collect (before any model is fitted)

1. Montage: more than one instance and more than one size, so that a leave-instance-out and a size-extrapolation fold both exist. Each new instance needs its own generator run, input hashes and one sequential reference run (`scripts/montage_prepare.py`, `scripts/montage_sequential.py`) because the correctness check compares each policy run with that instance's reference. The number of instances and sizes is bounded by the cost of one sequential reference (about 24 minutes for the primary instance) and by the download size; the plan fixes the list in a file before collection starts (`PENDING(owner/pilot)`).
2. GPU workload: image-pipeline stages with PyTorch-CUDA variants, tiles of 512 px or more, with the CPU result as the reference for every run (tolerances as in the spike: `img_edges` max_abs 1 and frac 0.001, `img_features` rel 1e-9, `img_denoise` exact).
3. Decision-time context logged online for every task dispatch, and placements varied so every eligible pool is executed under varied occupancy. The dataset code names `RandomOccupancyPolicy` and random placement for this; counterfactual pools have no labels otherwise (note in `estimators/tabular.py`).
4. A static pool profile per pool (`scripts/profile_montage.py` on an idle machine, from `valid/seq1`). It must predate every session used to train or evaluate a model; `scripts/evaluate_models.py` takes it as `--profile`.

### 1.2 Split policy

Rows are never split individually (`dataset/splits.py`). Proposed use:

- Fitting and tuning: leave-one-instance-out folds on the training instances, plus a time-ordered split within a session for the drift check.
- Final test: at least one instance, and at least one size, that is never used for fitting or tuning. It is evaluated once, after the configuration is frozen (section 1.6). The held-out instance and size are named in the freeze file, not chosen after seeing errors.
- A run may not appear on both sides of a fold; the code raises otherwise. Size and occupancy axes need `allow_straddle` and then the straddling must be reported.

### 1.3 Candidate set and the TabM entry rule

Candidates: E1, E3, E1+rc (references), Ridge, CatBoost, MLP. TabM is not implemented by decision. Proposed entry rule, with no number invented: TabM enters only if all three hold on pilot data.

1. A learning-curve check on CatBoost and MLP (fit on increasing fractions of the training rows, held-out error each time) shows that held-out error is still falling at the full training size, so data volume is not the limiting factor.
2. CatBoost and MLP leave scheduling-relevant error: replaying the logged decisions with true times in place of predictions (one-step hindsight regret, `analysis/decisions.py`) shows regret that is large compared with the noise floor measured in the pilot. The noise floor is the pilot SD of the paired log-ratio (section 2.2).
3. The owner accepts the added implementation, inference and memory cost, which must be measured on a prototype and recorded.

If (1) fails the reason is stated as "too few rows for a neural tabular model" and the study continues with Ridge, CatBoost and MLP. The numeric cut-offs inside (1) and (2) are written into the freeze file by the owner before the pilot's scheduling part runs (`PENDING(owner)`).

### 1.4 Offline accuracy part

`scripts/evaluate_models.py` produces, on held-out rows only: MAE, RMSE, relative MAE, median and mean APE with the stated MAPE limitation, signed bias, calibration by decile, inference latency distribution (not only the mean), peak memory, model size and training time, per task type and per pool and overall. The config file (seed, split, feature set, model hyper-parameters, latency calls, selection margin) is hashed and stored beside the outputs. Headline relative error is the median APE, because MAPE is dominated by tiny times, which the module itself notes.

Prediction quality and scheduling value are reported in separate tables. The text must not infer one from the other.

### 1.5 Scheduling pilot

Purpose: measure noise, find the strongest applicable baseline, and decide the repeat count. It is not evidence for or against the hypothesis, and its runs are labelled `pilot` and never pooled with the main run (the analysis refuses to pool different design hashes anyway).

- Conditions: B4, E-only, round-robin, random, HEFT, PEFT, EFT with E1, E3, E1+rc, and, once fitted, EFT with Ridge, CatBoost and MLP, plus rank-priority EFT variants. B0 P-only is included as the sanity floor.
- Blocks: interleaved, seeded random order inside each block, one run of each condition per block, the first block as warm-up (the single warm-up exclusion rule available in the runner).
- Budget check before starting (formula, not a number): total wall time of the pilot is about `blocks x sum over conditions of the expected makespan`, plus startup. The expected makespan per condition comes from the Stage 2 policy matrix. If this product does not fit in the time the owner is willing to leave the machine idle, reduce the condition list by the screening rule in 1.5.1 instead of reducing blocks below what gives an SD estimate.
- 1.5.1 Screening rule (proposal): run the full list for a small, pre-declared number of blocks; drop a condition from the main design only if it is worse than the reference in every block and its interval excludes the reference's, by the same paired bootstrap used in the main analysis. Never drop a condition because it looks unpromising. Dropped conditions stay in the pilot record.
- Outputs of the pilot: per-condition SD of the log makespan, the paired SD of the log-ratio against each candidate reference, a variance decomposition between block, condition and residual if enough blocks exist, and the headroom check below.

Headroom check (proposal, important for this workload): before the main run, compute from the profile and the logged pilot runs the best makespan any placement of the nine `mProject` tasks over the available slots could reach, and compare it with the observed makespan of B4 and of the best pilot condition. If the possible gain over the strongest baseline is smaller than the minimum detectable effect that the feasible block count can resolve (section 2.2), the main run is declared "a precision-limited test" in advance, and the final report says so. This avoids presenting a null as informative when the design could not have detected an effect.

### 1.6 Model selection and freeze

The selection rule already in the protocol is implemented in `analysis/model_eval.select_model`: the cheapest model whose scheduling outcome is not worse than that of every more complex model, where "not worse" means the upper bound of the paired-bootstrap interval of `outcome(simple) - outcome(complex)` is at most `margin`, and missing pairs raise an error.

Open items to be fixed before the scheduling part of the pilot, in a freeze file with a SHA-256 recorded in the Stage 3 evidence:

| Item | Proposal | Set by | Evidence it must cite |
|---|---|---|---|
| `margin` | The smallest makespan difference the owner calls practically relevant, expressed as a percentage of makespan; the draft does not propose a value | owner, before the pilot | the freeze file |
| Complexity order of models | E1 < E3 < E1+rc < Ridge < CatBoost < MLP (by training and inference cost, to be confirmed by the measured latency and memory) | owner, then checked against the offline latency table | `metrics.json` |
| Outcome used for selection | Total makespan; decision overhead is part of makespan already, and is also reported separately | fixed here | the analysis tables |
| Held-out instance and size | Named in advance | owner | the freeze file |
| Refit procedure | Fit on all non-test rows with the config in the freeze file; test touched once | fixed here | the model files and config hash |

The Stage 3 outcome is the freeze file plus `selection_record.json`. Stage 4 starts only after both are hashed.

### 1.7 Stage 3 gate checklist (from the plan, with evidence)

- Parity and leakage tests pass: `tests/test_parity_leakage.py` (run again at the commit that gets frozen).
- Every candidate has accuracy, latency and memory reported: `metrics.json`.
- At least one instance or size withheld from fitting and tuning: split definition in the freeze file.
- Final predictor chosen by the rule fixed before the pilot, with `selection_record.json`.
- Dataset manifest with hashes and exclusions, prediction CSVs, decision logs, pilot summary: listed and hashed in a manifest (`scripts/make_manifest.py`).
- Honest limits stated: a single hardware configuration, few instances, TabM decision and its reason, models that do not beat E3 or E1+rc if that is what the data show.

## 2. Stage 4: pre-registration

The design file is the pre-registration. Its SHA-256 is stored by the runner (`design.sha256`) and by every run manifest, and the analysis refuses to pool runs with different design hashes. The draft below lists what the design file and an accompanying prose note must contain before the first main run. Once the first main block has started, none of it changes; any change creates a new session with a new design hash and its own report.

### 2.1 Design file fields (existing format in `experiment/design.py`)

`name`, `evidence_label` (`real`), `seed`, `n_blocks`, `instances` (the main instances, cycled in a seeded shuffle), `warmup_blocks` (the only warm-up rule), `min_free_ram_gb` (the preflight threshold, to be chosen with respect to the observed free memory, which was between about 4.3 and 6.0 GB during the 2026-10-12 test runs), `reference` (the strongest applicable baseline from the pilot), `run_timeout_s` (a multiple of the slowest pilot makespan, stated as such), and the `conditions` list with `policy`, `estimator`, `workload` and `kwargs` (profile path, model path and hashes, reference-output hashes, tolerance). Separate designs and sessions are used for Montage and for the GPU workload, because the GPU workload uses a different adapter and reference.

### 2.2 Repeat count from the pilot

The analysis computes the 95% CI half-width and the minimum detectable effect for the achieved block count (`analysis/stats.py`): `half-width% = (exp(1.96 * sd_log / sqrt(n)) - 1) * 100` and `MDE% = (exp((1.96 + 0.84) * sd_log / sqrt(n)) - 1) * 100`, where `sd_log` is the paired SD of the log makespan ratio and `n` the number of blocks. Inverting these gives the proposal:

- `n_blocks = ceil( (1.96 * sd_log / ln(1 + h))^2 )` for a target half-width `h`, and `n_blocks = ceil( (2.80 * sd_log / ln(1 + m))^2 )` for a target detectable effect `m`.
- `sd_log` is the largest paired SD among the contrasts of the primary family in the pilot, not the smallest, so the design is not under-powered for the hardest contrast.
- The targets `h` and `m` are chosen by the owner, together with the time budget `T`: the feasible block count is at most `T / (sum over conditions of expected makespan + overhead)`. If the required `n_blocks` exceeds the feasible count, the design is run with the feasible count and the report states the achieved half-width and MDE; it does not claim the lower target.
- The previous Phase 6B figure of about 2.65% with 33 blocks on the earlier machine is history and is not a target (EVALUATION_PROTOCOL section 8).
- A fixed number of blocks, decided up front. There are no interim looks and no early stopping on the observed effect.

### 2.3 Primary and secondary analyses

- Confirmatory family: makespan contrasts of the primary instrument (rank-priority predicted queue-aware, transfer-aware EFT with the selected predictor) against the reference, paired within block, stratified percentile bootstrap, Holm adjustment across the family. This follows `analysis/stats_paired.py`, which labels everything else exploratory and unadjusted.
- Secondary (exploratory, labelled so): contrasts of every other condition; queue wait, task time, transfer, scheduling and inference overhead per decision and in total, utilisation where logged, memory at start; the sensitivity pass that includes excluded runs; the Friedman and Wilcoxon cross-check, whose suitability for this design is unverified (EVALUATION_PROTOCOL section 9).
- No claim is made for an effect whose interval includes zero. Effect sizes are reported with their intervals, the spread, and the minimum detectable effect for the achieved block count.
- Placement regret from the logs is reported with its limit: one-step hindsight only.

### 2.4 Exclusion rules (match the code, `analysis/stats_paired.exclusion_reason`)

A run is excluded from the primary analysis if its session is not complete with all blocks, the run status is not `ok`, the event log is missing or its hash does not match, the output is unverified or fails verification, no makespan was recorded, or it belongs to a warm-up block. Every excluded run stays in the raw data with its reason in `exclusions.csv`, and the sensitivity analysis includes all runs that have a value. A policy that fails more often than the others is a finding and is reported as such, not removed.

### 2.5 Controls

- Machine hygiene before and during every session: the checklist in `REPRODUCE.md` section 11; the memory preflight before every block; a record of background processes at session start in the environment manifest or the session note.
- No pooling across machine ids, environment hashes, evidence labels, design hashes or code versions; the override `--allow-mixed-code` is not used for the main analysis.
- Committed code: the main sessions run from a clean commit (the manifest records the commit and a dirty flag). A dirty tree at run time is stated in the report.
- Montage and GPU sessions are separate; the remote pool, if used, is labelled `emulation`.

### 2.6 Reporting

Tables and figures produced by `scripts/analyze_experiment.py` from the raw sessions, each tagged with its evidence label; the final report states the research question, the hypothesis as written, the outcome in the form "supported", "not supported" or "not resolved by this design" (the third when the interval is wider than the effect that matters), the headroom statement from section 1.5, all limitations (single machine, one primary instance dominated by nine equal tasks, patched Windows Montage build, unverified licence of the DSS images, unverified HEFT and PEFT originals), and the unverified items.

### 2.7 Reproducibility package

Raw immutable logs and manifests (read-only event logs, per-run manifests), the design and freeze files with hashes, the analysis outputs, figures, SHA-256 manifest of each evidence directory (`scripts/make_manifest.py`), the clean-checkout reproduction log (`scripts/reproduce_clean_checkout.py`), and a statement of what the clean checkout cannot reproduce (Montage timings, because `data/` is not in Git).

### 2.8 Stage 4 gate checklist

- All planned blocks complete; each excluded run listed with its reason.
- Every reported number traces to an evidence file; every table and figure carries a label.
- Correctness checks passed on all included runs (hash equality or the stated tolerance, no ineligible placement, no dependency violation).
- The confidence interval method equals the one written here.
- One result reproduced from raw logs with the analysis scripts; hashes re-run; clean-checkout subset run.
- Claims limited to what the evidence labels support.

## 3. Values that still have to be set, and by whom

| Value | Needed for | Source it must come from | Status |
|---|---|---|---|
| List of Montage instances and sizes to collect | Section 1.1 | owner, constrained by sequential-reference cost and download size | `PENDING(owner)` |
| Held-out instance and size | Section 1.2 | owner, before fitting | `PENDING(owner)` |
| Cut-offs inside the TabM entry rule | Section 1.3 | owner, before the pilot's scheduling part | `PENDING(owner)` |
| `margin` of the selection rule | Section 1.6 | owner, before the pilot | `PENDING(owner)` |
| Number of pilot blocks and the screening rule parameters | Section 1.5 | owner, from the time budget | `PENDING(owner)` |
| Target half-width `h` or detectable effect `m`, time budget `T` | Section 2.2 | owner | `PENDING(owner)` |
| `sd_log` | Section 2.2 | the pilot analysis output | `PENDING(pilot)` |
| `min_free_ram_gb`, `run_timeout_s` | Section 2.1 | the observed memory range and the slowest pilot makespan | `PENDING(pilot)` |
| Strongest applicable baseline (the `reference`) | Section 2.1 | pilot results, chosen before the main run | `PENDING(pilot)` |

## 4. Risks specific to this plan

- The primary instance has little headroom; the headroom check in 1.5 is the safeguard against presenting an unresolved comparison as a result.
- Few Montage task types (eight) and one dominant type mean that models fitted to Montage see very few distinct (type, pool) groups; a learned model can reduce to a per-type constant. If so the report says that E1 or E3 is equivalent in effect.
- The machine is shared. If the preflight aborts sessions often, the session count falls and the design is reported as incomplete rather than pooled.
- Wall-clock cost: 15 or more conditions times the makespan times the blocks can exceed what is practical; section 1.5 provides the screening rule and section 2.2 provides the honest fallback.
