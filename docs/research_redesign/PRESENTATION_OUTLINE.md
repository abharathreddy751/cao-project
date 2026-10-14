# Presentation outline

Status: **updated 2026-10-14 from [FINAL_REPORT.md](FINAL_REPORT.md) after the confirmatory sessions.** 16 slides, three bullets each. Confirmatory numbers are primary; the first-round sessions appear only as "the pilot". Paths are relative to `data/results/`; `S5` = `stage5_20261013`, `S4` = `stage4_20261012`. Every number names its evidence file. Figure files that exist are named exactly. Labels: **[real]**, **[emulation]** (remote pool), **[plan]**. Do not pool pilot and confirmatory numbers. Open items for the speaker are listed at the end.

| # | Slide | Figure or table |
|---|---|---|
| 1 | Title | none |
| 2 | Research question | none (text) |
| 3 | Why Montage and a GPU workload | `S5/figures/montage_dag.svg` / `.png`; task-type table as backup |
| 4 | System architecture | `S5/figures/system_architecture.svg` / `.png` |
| 5 | Workload facts | table from `stage1_20261011/valid/stage1_gate.json` and `stage3_20261012/refs/<instance>/run.json` |
| 6 | Method and design: ladder, pilot, pre-registered confirmatory sessions | `S5/figures/predictor_ladder_flow.svg` / `.png`; session table from FINAL_REPORT 8.1 |
| 7 | Stage 1 result | table from `stage1_gate.json` |
| 8 | Stage 2 result | `stage2_20261012/analysis_stage2/fig_makespan_by_policy.png`; table from `stage2_gate.json` |
| 9 | Stage 3: prediction, drift, learning curve | `S5/analysis_extra/learning_curve/learning_curve.png`; MAE table from `stage3_20261012/eval/{tuning_loo,final_test}/metrics.json` |
| 10 | Confirmatory main session and the early-binding contrast | `S5/analysis_main/fig_makespan_by_policy.png`, `S5/analysis_main/fig_effect_vs_baseline.png`; table from `S5/analysis_main/effects.csv` and `S5/analysis_main_posthoc_excl_blocks_5_6/effects.csv` |
| 11 | Scarce P cores and decision regret | `S5/analysis_regimeR/fig_makespan_by_policy.png`, `S5/analysis_regimeR/fig_effect_vs_baseline.png`; `S5/analysis_extra/regret/regret_table.md` |
| 12 | Overhead | `S5/analysis_main/fig_overhead_breakdown.png`; decision-time table |
| 13 | GPU workload | `S5/analysis_gpu/fig_effect_vs_baseline.png`, `S5/analysis_gpu/fig_makespan_by_policy.png` |
| 14 | Emulated remote pool [emulation] | `S5/analysis_remote/fig_effect_vs_baseline.png`, `S5/analysis_remote/fig_makespan_by_policy.png` |
| 15 | Limitations and what remains | none (text) |
| 16 | Conclusions and next steps | four-condition table from the `effects.csv` files of `S5/analysis_main`, `analysis_regimeR`, `analysis_gpu`, `analysis_remote` |

Note on figure sets: `S5/analysis_*/fig_*.png` are the confirmatory figures (9, 8, 24 and 12 blocks; two panels, the right one a linear zoom). `S5/figures/analysis_main`, `analysis_regimeR` and `gpu_analysis` are the pilot figures re-drawn with the fixed plotting code (4, 3 and 12 blocks, files with the same names); use them only if the pilot is shown, labelled as the pilot.

## Slide 1. Title

- Title: Prediction-aware dynamic scheduling of scientific-workflow DAGs on heterogeneous CPU/GPU resources: how much prediction is enough? (PROJECT_SPEC section 1; confirm wording; a one-line version: "a real-hardware study with a pre-registered, confirmed null result").
- Author, date, institution: owner fills (no source file holds them).
- Evidence scope line: one laptop (i5-13500HX, RTX 3050 6 GB), Montage plus a separate GPU workload, **[real]**; remote pool **[emulation]** (loopback link shim); Raspberry Pi 5 **[plan]**, no edge claim.

Figure: none.

## Slide 2. Research question

- Question: under what workload and resource conditions does prediction improve dynamic DAG scheduling after counting prediction, scheduling, queueing and transfer overhead? (PROJECT_SPEC section 4)
- Hypothesis (pre-registered, falsifiable): prediction-aware placement beats the best non-predictive baseline only when runtime ratios and contention are large relative to its own cost and to timing noise; a null result is accepted.
- Contribution: a controlled, overhead-accounted, verified real-hardware study with a confirmed null result and two mechanisms, plus the infrastructure; not a new algorithm, and the base patent's task-graph-plus-queues idea is not claimed (its claims 1 to 20 contain no machine-learning or prediction term, SOURCES_VERBATIM section 1).

Figure: none.

## Slide 3. Why Montage and a GPU workload

- Montage is a recognised scientific workflow: a DAG of eight task types with file dependencies, built natively on this machine (Windows patch, twelve workarounds, MONTAGE_WINDOWS_BUILD.md). Primary instance: 59 tasks = 9 `mProject`, 36 `mDiffFit`, 9 `mBackground`, 1 each of `mConcatFit`, `mBgModel`, `mImgtbl`, `mAdd`, `mViewer` (`stage1_gate.json`: `dag.n_jobs` 59; counts computed in FINAL_REPORT section 3).
- `mProject` is 98.7% of sequential time (STAGE3_FREEZE section 4) and runs 111.8 s on a P core against 401.1 s on an E core (`stage2_20261012/profile_montage/20261012T092355_profile.json`): a 3.59 times speed gap.
- The GPU workload is a separate **[real]** 68-task image pipeline (tile 1024 px, 16 branches) with CUDA stages on the RTX 3050; Montage has no GPU path, so no claim about Montage on GPU. Data credit: the DSS images need the STScI acknowledgement of FINAL_REPORT section 15.1 wherever the data are described.

Figure: `S5/figures/montage_dag.svg` (`.png`), generated by `scripts/make_diagrams.py`. Do not show the Montage mosaic image: it derives from DSS data, and the STScI pages state no rule on redistributing the files (SOURCES_VERBATIM section 6.2).

## Slide 4. System architecture

- DAG runtime and coordinator, ready queue, JSONL event log, affinity-pinned P and E worker pools plus one CUDA worker and one emulated remote worker, external-command tasks with declared files and fail-fast semantics.
- Pluggable scheduler (B0 to B5, random, HEFT, PEFT, the EFT ladder, rank-priority instrument, the early-binding control `B0_P_early`) and pluggable estimator (E1, E3, E1+rc, Ridge, CatBoost, MLP); one eligibility check for every policy; 0 ineligible placements in all 408 confirmatory runs (`S5/gate_*.json`).
- Decision-context logging feeds the dataset builder (train/serve parity and leakage tests) and the paired-block analysis; a background-load monitor logs CPU and RAM during the sessions; the dashboard shows runs live (its header now separates the historical tabs from the Montage and GPU tab).

Figure: `S5/figures/system_architecture.svg` (`.png`).

## Slide 5. Workload facts

- Primary instance: 59 tasks, 147 dependency edges (`stage1_gate.json`: `dag.n_jobs`, `dag.edges_jobDependencies`), 9 `mProject` tasks per run (the gate file's 27 is the total over three runs).
- Four instances of 19, 59, 59 and 157 tasks with sequential times 489.7 s, 1459.4 s, 1083.7 s and 1896.4 s; roles training, training, tuning, final test (STAGE3_FREEZE section 1; times from `stage1_gate.json` and `stage3_20261012/refs/<instance>/run.json`).
- Pool profile: `mProject` 111.8 s on P and 401.1 s on E; every other task type takes seconds or less.

Figure: workload table built from `stage1_gate.json` and the `refs/<instance>/run.json` files.

## Slide 6. Method and design: the ladder, the pilot, the pre-registered confirmatory sessions

- Baselines: B0 P-only and E-only, B1 round-robin, B2 static P, B3 shortest queue, B4 greedy eligible, B5 criticality, random. HEFT and PEFT from the published originals: both papers' worked examples are reproduced exactly by `tests/test_heft_peft_papers.py` (3 tests; makespans 80, 122 and 133), communication cost 0 in the Montage runs (SOURCES_VERBATIM section 4).
- Predictors: E1 static profile, E3 history, E1+rc recalibration, Ridge, CatBoost, MLP; TabM out by the pre-registered entry rule (2,706 rows, 20,000 needed). EFT placement uses each predictor; the instrument is rank-priority EFT with E1.
- Design: the first round (4, 3 and 12 blocks) is the **pilot**; its 4-block Holm test could not reach p < 0.05, so four confirmatory sessions were pre-registered before their first block (EVALUATION_PROTOCOL 13 and 14): main 9 blocks, scarce-P 8, GPU 24, remote 12 = 408 runs, all verified, 0 failed checks. Predictions P1 to P4 and D1 to D3 were stated beforehand.

Figure: `S5/figures/predictor_ladder_flow.svg` (`.png`); table backup: E1 < E3 < E1+rc < Ridge < CatBoost < MLP (frozen order; measured inference median 1.2, 1.1, 1.3, 6.1, 478 and 22.5 µs, `eval/final_test/metrics.json`).

## Slide 7. Stage 1 result: reproducible workload

- Three complete sequential runs of the primary instance with identical output hashes (`stage1_gate.json`: `output_hashes_identical` true, `completed_3_of_3` true); FITS max abs difference 0.0.
- Wall times 1459.4 s, 1467.1 s, 1469.3 s (`reps.seq1/seq2/seq3.total_wall_s`); WCS header checks all ok (`wcs.all_header_ok`); finite fraction 0.9666.
- Sequential references also exist for the other three instances (`refs/<instance>/run.json`, all status ok).

Figure: Stage 1 table from `stage1_gate.json`.

## Slide 8. Stage 2 result: 14 policies on the heterogeneous runtime

- 42 runs, 0 failing checks, all outputs verified (`stage2_20261012/stage2_gate.json`: `n_runs`, `n_failing_checks`).
- B0 P-only mean 270.9 s is not slower than any predictive policy (273.3 s to 275.5 s, +0.9% to +1.7%); greedy B4 mean 410.5 s takes 1.52 times as long (`makespan_by_condition.*.mean_s`; effects with intervals in `analysis_stage2/effects.csv`).
- Three blocks per policy: descriptive. It shows the P pool dominates on this profile, not that prediction is useless in general. The confirmatory sessions (slides 10 to 14) test this with enough blocks.

Figure: `stage2_20261012/analysis_stage2/fig_makespan_by_policy.png`; table from `stage2_gate.json`.

## Slide 9. Stage 3: prediction, drift and learning curve

- Collection: 42 verified runs on four instances plus 18 Stage 2 runs = 60 runs, 3,648 task rows (2,706 fitting, 942 held out on `d1.5`); 1,416 tasks without a logged decision context dropped and counted (`stage3_20261012/dataset/20261012T195206/manifest.json`). Held-out MAE in seconds, leave-one-instance-out (`eval/tuning_loo/metrics.json`): E1 3.54, E3 3.53, E1+rc 3.55, Ridge 1.32, CatBoost 2.35, MLP 1.86; final test `d1.5` evaluated once (`eval/final_test/metrics.json`): E1 3.26, Ridge 1.36, CatBoost 2.32, MLP 2.98 (RMSE 22.2 s); on the 19-task fold the learned models are worse than the static profile (Ridge 4.00 s against 1.81 s). Selection by the frozen rule: **EFT_E1** (`selection/selection_record.json`).
- Drift (time-ordered split, `S5/analysis_extra/drift/summary/drift_summary.csv`): late/early MAE ratio 1.29 (Ridge), 1.38 (MLP), 1.40 (CatBoost) against 1.01 to 1.02 for E1, E3 and E1+rc; time-split MAE E1 3.514 s, Ridge 0.8395 s, CatBoost 2.123 s, MLP 1.334 s.
- Learning curve (`S5/analysis_extra/learning_curve/`): Ridge flat from 20% (`d1.5`) and 40% (leave-one-instance-out) of the runs, CatBoost non-monotone, MLP noisy; TabM stays out (condition 1: rows; condition 2 not established by a steady fall).

Figure: `S5/analysis_extra/learning_curve/learning_curve.png`; MAE table above.

## Slide 10. Confirmatory main session and the early-binding contrast

- 6 P + 7 E workers, 9 blocks, 108 runs (`S5/analysis_main/effects.csv`, reference B0 P-only): EFT_E1 +1.62% (+1.21 to +2.28), E3 +1.59%, rank +1.41%, Ridge +1.54%, HEFT +1.54%, PEFT +1.73%, all Holm-significant (p_holm 0.036) and slower in 9 of 9 blocks; greedy B4 +47.9% (+53.5% post-hoc). **P1: `B0_P_early`, the same placements as B0 P-only with early binding, is +1.68% (+1.24 to +2.31), p_holm 0.036**: the early-versus-late-binding mechanism is confirmed by a controlled contrast.
- **Slow window, stated plainly:** 14 runs from 12:40 to 14:30 UTC (block 5 and the first two runs of block 6) ran about 1.4 times slower (three runs about 2.5 times); the load monitor shows no heavy non-experiment process, and the Windows event log shows the laptop ran on battery from 18:11:21 to 19:59:07 local (AcOnline=false/true): that is the cause. The pre-registered analysis keeps these runs, which inflates EFT_CatBoost (+8.68%), EFT_E1_rc (+13.92%) and EFT_MLP (+12.99%).
- Post-hoc and labelled as such (`S5/analysis_main_posthoc_excl_blocks_5_6/effects.csv`, 7 blocks, cannot be Holm-significant): without blocks 5 and 6 all EFT, HEFT and PEFT variants are +1.15% to +2.04% and `B0_P_early` +1.40% (+1.20 to +1.60). A measurement limit of this machine, not fixed by re-running.

Figure: `S5/analysis_main/fig_makespan_by_policy.png` and `S5/analysis_main/fig_effect_vs_baseline.png`; table of the post-hoc effects.

## Slide 11. Scarce P cores and decision regret

- 2 P + 7 E workers, 8 blocks, 48 runs (`S5/analysis_regimeR/effects.csv`, reference B4 greedy 412.2 s): EFT_E1 -0.13% (-1.10 to +0.88): within the pre-stated +-0.5% as a point estimate, equivalence not resolved; B0 P-only +42.48% (+41.05 to +43.54); **EFT_CatBoost +15.65%** (+14.84 to +16.12); MLP -0.02%.
- **EFT_Ridge -0.59% (-1.18 to -0.18), p_holm 0.0325, faster in 8 of 8 blocks: statistically significant, about 2.4 s of 412 s, below the 2% practical margin of the freeze; no prediction had been made for it.**
- Regret (`S5/analysis_extra/regret/regret_table.md`, pilot sessions): mean one-step regret per decision B4 6.85 s in the main set and EFT_E1 0.312 s; scarce-P EFT_CatBoost 2.538 s against EFT_E1 0.134 s; exactly 6 `mProject` decisions differ (CatBoost chose P at a predicted 94.4 s, actual 113 s to 116 s), regret 57.5 s to 61.7 s. Myopic, kernel-only.

Figure: `S5/analysis_regimeR/fig_makespan_by_policy.png`, `S5/analysis_regimeR/fig_effect_vs_baseline.png`.

## Slide 12. Overhead

- Decision time per run (`S5/analysis_main/summary.csv`): E1 0.021 s, HEFT 0.003 s, Ridge 0.058 s, MLP 0.12 s, CatBoost 1.65 s (about 0.55% of makespan); per decision 0.35 ms (E1) to 28 ms (CatBoost). It includes estimator inference, which the log cannot separate.
- Predictor memory and latency by model: slide 9 and FINAL_REPORT section 7.2 (training RSS increase 1 MB Ridge, 64 MB CatBoost, 551 MB MLP). Transfer is "not measured" for the local pools; in the remote session B4's transfer is 0.018 s per run on the LAN link and 0.695 s on the WAN link (`S5/analysis_remote/summary.csv`).
- Does the gain survive once decision cost is counted? There is no gain: makespan is end-to-end and the predictive policies are slower than P-only; E1's decision time (0.02 s) is not the cause of its 3.6 s deficit (post-hoc set).

Figure: `S5/analysis_main/fig_overhead_breakdown.png` (queue wait dominates the bar; the decision-time bar is small at that scale). Better: show the table of decision time per run.

## Slide 13. GPU workload

- Separate **[real]** workload on the RTX 3050 6 GB: at 1024 px `img_edges` 13.96x, `img_features` 4.87x, `img_denoise` 1.03x with copies counted, all within tolerance (`stage1_20261011/gpu/spike_20261012T092018/gpu_spike.json`). Makespan about 7.1 s to 7.4 s: CPU-only `img_source` (5.6 s on a P core) and `img_package` (0.67 s) dominate.
- Confirmatory session, 24 blocks x 7 conditions = 168 verified runs (`S5/analysis_gpu/effects.csv`): **P4 supported, EFT_E1 with GPU against its CPU-only version -2.10% (-2.93 to -1.35), p_holm 0.0006**; against greedy B4 with GPU -3.53% (computed in FINAL_REPORT 11.1 from `analysis_gpu/runs.csv`); **against B0 P-only -0.65% (-1.82 to +0.34), not distinguishable** (`S5/analysis_gpu_vs_P/effects.csv`, exploratory second reference).
- Scope: the absolute gain is 0.153 s; this GPU and this workload only. The pilot GPU session (12 blocks, `S4/gpu/analysis/`) gave -2.00% against EFT_E1_cpu and was not pre-registered.

Figure: `S5/analysis_gpu/fig_effect_vs_baseline.png` and `S5/analysis_gpu/fig_makespan_by_policy.png`.

## Slide 14. Emulated remote pool [emulation]

- One real node process on a core of this machine behind a loopback link shim (fast LAN 0.2 ms, 1000 Mbit/s; slow WAN 30 ms, 20 Mbit/s); calibrated transfer cost 0.779 ms + 1.617 ns per byte (n = 60, `S5/remote/remote_profile.json`). Image pipeline at tile 512, 12 blocks, 84 runs, label emulation, no real network.
- **D1 supported:** B4 with the remote pool is +30.69% (+29.42 to +32.02), p_holm 0.0024, slower than B4 without it on the WAN link (`S5/analysis_remote_vs_B4/effects.csv`); B4 placed one task on R per block on both links. **D2 not supported:** the transfer-aware EFT placed 0 tasks on R on both links (`S5/gate_remote.json`). D3: EFT with R on the LAN +0.14% (-1.10 to +1.19), not distinguishable.
- Plain reading: the emulated remote pool gave no benefit to either policy; greedy was hurt on the slow link, EFT avoided the harm by not using R; B0 P-only is the fastest policy here (6.40% faster than EFT_E1 without remote). No claim about real networks.

Figure: `S5/analysis_remote/fig_effect_vs_baseline.png` and `S5/analysis_remote/fig_makespan_by_policy.png`.

## Slide 15. Limitations and what remains

- Genuinely remaining (FINAL_REPORT 14.3): (1) Raspberry Pi 5, real network, foreign clock and ARM need hardware not available here and are a later extension (no edge claim); (2) (closed) the slow window was the laptop running on battery (Windows Kernel-Power event 105); (3) full texts behind paywalls or bot checks were not accessible (list and attempts in SOURCES_VERBATIM section 7; no claim depends on them); (4) the project has no licence file of its own (owner's choice); (5) the remote pool is emulated (loopback, no jitter); (6) one machine, patched Windows Montage build.
- Scope of the claims: one dominant task type, speed ratio 3.59, two 59-task instances in the main session, so the null was expected by construction (EVALUATION_PROTOCOL 12.6); the GPU workload is dominated by CPU stages (about 6.3 s of 7.1 s); minimum detectable effects 0.89% to 1.28% (main) and 1.47% for EFT_E1 in scarce-P, which is why that equivalence is not resolved.
- Closed since the first version: patent claims read verbatim (no ML or prediction term in claims 1 to 20), HEFT/PEFT originals read and reproduced, DSS terms and acknowledgement, licences, drift check, learning curve, regret table, figures fixed, background load measured, the Holm flaw resolved by the confirmatory sessions.

Figure: none.

## Slide 16. Conclusions and next steps

- Answer: under the conditions tested prediction-aware placement did **not** beat the best simple baseline at the practical margin: main (P-only wins by 1.4% to 1.7%), scarce-P (EFT_E1 ties greedy; Ridge -0.59% is the only significant advantage and is below the 2% margin), GPU (not distinguishable from P-only), remote [emulation] (P-only fastest); a simple method matches prediction; predictor sophistication did not improve scheduling (CatBoost +15.65% worse in scarce-P).
- What the data support: the workload is reproducible, the heterogeneous runtime is correct (408 confirmatory runs verified, 0 violations), and the study is a confirmed, pre-registered real-hardware null result with two mechanisms (early versus late binding, shown by a controlled contrast; knife-edge decisions amplify prediction bias). The expected null by construction (one dominant task type, trivial P-only optimum) is stated in the pre-registration.
- Next: owner decisions (FINAL_REPORT 14.2): a workload or pool condition where prediction can matter, then the Raspberry Pi 5 extension (ARM Montage build, real network, foreign-clock check, node authentication, ARM numeric-tolerance output checks), **[plan]**.

Figure: four-condition summary table from `S5/analysis_main/effects.csv`, `S5/analysis_regimeR/effects.csv`, `S5/analysis_gpu/effects.csv`, `S5/analysis_remote/effects.csv`.

## Open items for the speaker

- Slide 1 needs title wording, author, date and institution from the owner. Slide 9 has one figure (`learning_curve.png`) and the MAE table.
- State the slow window (slide 10) before showing the all-blocks CatBoost, E1+rc and MLP numbers; label the post-hoc analysis as post-hoc. Do not present the pilot as a test; the pilot's 3 to 4 blocks could not be significant (FINAL_REPORT 4.4).
- Do not call the Ridge advantage in scarce-P a practical win (0.59%, below the 2% margin) and do not claim equivalence for EFT_E1 and B4 (interval wider than +-0.5%).
- Label every remote-pool number **emulation**. Do not show images derived from the DSS data (for example the mosaic) before the owner decides on redistribution; include the acknowledgement of FINAL_REPORT section 15.1.
- The clean-checkout reproduction passed for the pilot-era code path (18 of 18 steps, `stage4_repro/repro_clean_checkout_log.json`; it re-runs the code path, not Montage timings) and was not repeated for the confirmatory state; the confirmatory tables were re-derived from the raw logs (`stage5_repro/repro_analysis_*.json`, all `ok`). Final run at commit `ebc68fb` (`data/results/stage5_repro/repro_clean_checkout_final.json`): 19 of 19 steps, fresh venv from the lock file with the pinned CUDA torch, the whole test suite (390 passed; 3 skipped, the three dashboard tests that read the historical event logs which the Stage 0 record keeps out of Git; all 393 pass on this machine), stub experiment, analysis, manifest build/verify, table re-derivation, and the Montage binaries and four instances hash-checked read-only.
- Figure caveats: the figures now carry a log-axis panel and a linear zoom panel; the pilot figures in `S5/figures/analysis_*` must be labelled as the pilot.
