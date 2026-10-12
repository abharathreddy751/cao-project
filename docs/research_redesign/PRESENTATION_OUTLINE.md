# Presentation outline (skeleton)

Status: **[plan] 2026-10-12.** 14 slides, three bullets each. Numbers appear only where an evidence file already holds them (file and field named); everything else is `PENDING(<file>)` and is filled from [FINAL_REPORT.md](FINAL_REPORT.md) at the end of Stage 4. Figure and table file names are the outputs of `scripts/analyze_experiment.py --out analysis/montage_main`: tables `runs.csv`, `exclusions.csv`, `summary.csv`, `effects.csv`, `crosscheck.csv`, `analysis.json`; figures `fig_makespan_by_policy.png`, `fig_overhead_breakdown.png`, `fig_effect_vs_baseline.png`. Each figure carries its evidence label (`evidence: real`). Figures with a path other than `analysis/montage_main/` are provisional names for files not yet written. Labels: **[real]**, **[emulation]**, **[plan]**, **[unverified]**.

| # | Slide | Figure or table |
|---|---|---|
| 1 | Title | none |
| 2 | Research question | none (text) |
| 3 | Why Montage and a GPU workload | DAG sketch from `data/montage/instances/d1.1_dss2b_c56.7_24.0/instance.json`; PENDING(figure file) |
| 4 | System architecture | architecture diagram PENDING(docs/research_redesign/figures/architecture.svg) |
| 5 | Workload facts | table from `data/results/stage1_20261011/valid/stage1_gate.json` |
| 6 | Method: the predictor and scheduler ladder | ladder table PENDING(docs/research_redesign/figures/ladder.svg) |
| 7 | Stage 1 result | table from `stage1_gate.json` |
| 8 | Stage 2 result | `data/results/stage2_20261012/stage2_gate.json` table; PENDING(analysis/stage2/fig_makespan_by_policy.png) |
| 9 | Stage 3: prediction | PENDING(data/results/stage3_20261012/eval/metrics.csv) |
| 10 | Stage 4: scheduling | `analysis/montage_main/fig_makespan_by_policy.png`, `analysis/montage_main/fig_effect_vs_baseline.png` |
| 11 | Overhead | `analysis/montage_main/fig_overhead_breakdown.png` |
| 12 | GPU workload | PENDING(data/results/stage1_20261011/gpu/gpu_spike.json) |
| 13 | Limitations | none (text) |
| 14 | Conclusions and next steps | `analysis/montage_main/effects.csv` |

## Slide 1. Title

- Title: execution-time prediction for dynamic DAG scheduling on heterogeneous resources, a real-hardware study (working title from PROJECT_SPEC section 1; confirm wording).
- Author, date, institution: PENDING(owner fills).
- Evidence scope line: one laptop, Montage plus a separate GPU workload, **[real]**; Raspberry Pi 5 is **[plan]**.

Figure: none.

## Slide 2. Research question

- Question: under what workload and resource conditions does prediction improve dynamic DAG scheduling after counting prediction, scheduling, queueing and transfer overhead? (PROJECT_SPEC section 4)
- Hypothesis: prediction-aware placement beats the best non-predictive baseline only when runtime ratios and contention are large relative to its own cost and to timing noise; a null result is accepted.
- Contribution: a controlled, overhead-accounted study of predictor sophistication, not a new algorithm; the base patent's task-graph-plus-queues idea is not claimed.

Figure: none.

## Slide 3. Why Montage and a GPU workload

- Montage is a recognised scientific workflow: a DAG of eight task types with file dependencies, built natively on this machine (Windows patch).
- It gives a real, reproducible, dozens-of-tasks DAG with heterogeneous task cost; earlier results came from an image pipeline of the project's own.
- The GPU workload is a separate **[real]** CPU/GPU kernel workload on the laptop's RTX 3050 6 GB, used for transfer-aware placement; no claim about Montage on GPU.

Figure: DAG sketch of the primary instance (PENDING(figure file); structure from `instance.json`).

## Slide 4. System architecture

- DAG runtime and coordinator, ready queue, event log, P and E worker pools.
- Pluggable scheduler (baselines, HEFT, PEFT, EFT ladder, instrument) and pluggable estimator (E0 to E5, Ridge, CatBoost, MLP).
- Decision-context logging feeds the dataset builder and the paired-block analysis; the dashboard shows runs live.

Figure: PENDING(docs/research_redesign/figures/architecture.svg), drawn from ARCHITECTURE_DECISIONS.md.

## Slide 5. Workload facts

- Primary instance: 59 tasks, 147 dependency edges (`stage1_gate.json`: `dag.n_jobs`, `dag.edges_jobDependencies`); 27 `mProject` tasks.
- Four instances with sizes 19, 59, 59 and 157 tasks; roles training, training, tuning, final test (STAGE3_FREEZE section 1).
- `mProject` dominates sequential time (98.7% per STAGE3_FREEZE section 4); pool profile 111.8 s on P against 401.1 s on E for `mProject` (STAGE3_FREEZE basis).

Figure: workload table built from `stage1_gate.json` and `data/results/stage3_20261012/refs/<instance>/run.json`.

## Slide 6. Method: the ladder from no prediction to learned models

- Baselines: B0 P-only and E-only, B1 round-robin, B2 static P, B3 shortest queue, B4 greedy eligible, B5 criticality, random; HEFT and PEFT (secondary-source formulas, **[unverified]**).
- Predictors: E1 static, E3 history, E1+rc recalibration, Ridge, CatBoost, MLP; TabM out by the pre-registered entry rule (too few rows).
- Protocol: decision-time-safe features, leave-instance-out, final-test instance evaluated once, paired blocks, selection margin 2.0% fixed before data (STAGE3_FREEZE).

Figure: ladder diagram PENDING(docs/research_redesign/figures/ladder.svg).

## Slide 7. Stage 1 result: reproducible workload

- Three complete sequential runs of the primary instance, identical output hashes (`stage1_gate.json`: `output_hashes_identical` true, `completed_3_of_3` true).
- Wall times 1459.4 s, 1467.1 s, 1469.3 s (`reps.seq1/seq2/seq3.total_wall_s`); WCS header checks all ok (`wcs.all_header_ok`).
- Sequential references also exist for the other three instances (`refs/<instance>/run.json`, all status ok).

Figure: Stage 1 table from `stage1_gate.json`.

## Slide 8. Stage 2 result: 14 policies on the heterogeneous runtime

- 42 runs, 0 failing checks (`stage2_gate.json`: `n_runs`, `n_failing_checks`); all outputs verified.
- Descriptive reading: B0 P-only mean 270.9 s is not slower than the predictive policies (273.3 s to 275.5 s); greedy B4 mean 410.5 s takes about 1.5 times as long (`makespan_by_condition.*.mean_s`).
- Three blocks per policy, no interval: this shows the P pool dominates on this profile, not that prediction is useless in general.

Figure: PENDING(analysis/stage2/fig_makespan_by_policy.png) from the 42 Stage 2 logs; table from `stage2_gate.json`.

## Slide 9. Stage 3: prediction

- Collection: 42 runs on four instances (`designs_v2/`), about 2,600 task rows at most; fitting rows PENDING(data/results/stage3_20261012/dataset/manifest.json).
- Accuracy of E1, E3, E1+rc, Ridge, CatBoost, MLP on held-out instances: median APE PENDING(data/results/stage3_20261012/eval/metrics.csv); final test on the withheld 157-task instance PENDING(data/results/stage3_20261012/eval_test/metrics.csv).
- Cost of each model (latency, memory, size) PENDING(data/results/stage3_20261012/eval/costs.csv); selected model PENDING(data/results/stage3_20261012/eval/model_selection.json).

Figure: held-out error by model and instance, PENDING(data/results/stage3_20261012/eval/fig_error_by_model.png).

## Slide 10. Stage 4: does prediction improve scheduling?

- Makespan by policy with 95% bootstrap intervals: PENDING(analysis/montage_main/summary.csv).
- Paired effect against the strongest non-predictive baseline, Holm-adjusted: PENDING(analysis/montage_main/effects.csv); verdict on the hypothesis follows the support and reject criteria fixed beforehand.
- Conditions with high versus low runtime ratio and contention are reported separately; a null result is stated as a null.

Figure: `analysis/montage_main/fig_makespan_by_policy.png` and `analysis/montage_main/fig_effect_vs_baseline.png`.

## Slide 11. Overhead

- Scheduling and inference time per run, queue wait and transfer, as measured components only: PENDING(analysis/montage_main/summary.csv).
- Latency and memory per predictor: PENDING(data/results/stage3_20261012/eval/costs.csv).
- Does the gain survive once decision cost is counted: PENDING(analysis/montage_main/effects.csv).

Figure: `analysis/montage_main/fig_overhead_breakdown.png`.

## Slide 12. GPU workload

- Separate **[real]** workload on the RTX 3050 6 GB Laptop GPU; Stage 1 spike PENDING(data/results/stage1_20261011/gpu/gpu_spike.json).
- Transfer-aware placement result, paired blocks: PENDING(data/results/stage4_main/gpu/gpu_effects.csv).
- Output verification and scope: this GPU and this workload only; PENDING(data/results/stage4_main/gpu/gpu_runs.csv).

Figure: PENDING(data/results/stage4_main/gpu/fig_gpu_effect.png).

## Slide 13. Limitations

- One machine, patched Windows Montage build, machine not idle; HEFT and PEFT from secondary sources; literature not fully verified; DSS image licence unverified.
- Few rows and one dominant task type; instances share a sky centre; Stage 2 is descriptive with three blocks per policy.
- Raspberry Pi 5 not done and the emulated remote pool not used: no edge-offloading claim.

Figure: none.

## Slide 14. Conclusions and next steps

- Answer to the research question and verdict on the hypothesis, limited to the evidence labels: PENDING(analysis/montage_main/effects.csv).
- What the data support so far: the workload is reproducible and the heterogeneous runtime is correct on this machine ([real], Stages 1 and 2).
- Next: Raspberry Pi 5 extension (ARM Montage build, real network, foreign-clock check, node authentication, ARM numeric-tolerance output checks), **[plan]**.

Figure: `analysis/montage_main/effects.csv` summary table.

## Open items for the speaker

- Every PENDING marker above must be replaced or the slide cut; a slide with an unfilled number is not shown.
- Wording on slide 8 stays "descriptive"; do not present the Stage 2 ordering as a test result.
