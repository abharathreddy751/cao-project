# Final report: execution-time prediction for dynamic DAG scheduling on a heterogeneous laptop

Status: **updated 2026-10-14 with the CONFIRMATORY sessions (branch `redesign/montage`; the sessions ran from git HEAD `13d1649` (main, scarce-P, GPU) and `868eeea` (remote emulation), working tree dirty in every session; the commit that contains this report: see `git log`).** The first-round Stage 4 sessions (`stage4_20261012`) are now the **PILOT** of the confirmatory sessions (section 8.1, results in section 8.4). Every number below comes from a named evidence file under `data/results/` or from a project document named next to it. A number marked "(computed here ...)" was derived while writing this report by reading that file (light read-only Python), not copied from a stored table. Paths: `S5` = `data/results/stage5_20261013`, `S4` = `data/results/stage4_20261012`. Evidence labels: **[real]** measured on real hardware; **[replay]**; **[emulation]**; **[simulation]**; **[plan]**; **[unverified]** (as in [PROJECT_SPEC.md](PROJECT_SPEC.md)). The remote-pool session is labelled **[emulation]** everywhere. What is still open is listed in section 14.3 (short list) and in section 12.

## Summary

- **Result: a null result, now confirmed by pre-registered sessions.** On this machine, with Montage and with a separate CPU/GPU image workload, prediction-aware placement did not beat the strongest simple baseline at the 2% practical margin of the freeze in any of four conditions (main, scarce-P, GPU, emulated remote pool). The confirmatory sessions are `stage5_main_confirm` (9 blocks, 108 runs), `stage5_regimeR_confirm` (8 blocks, 48 runs), `stage5_gpu_confirm` (24 blocks, 168 runs) and `remote_emulation_confirm` (12 blocks, 84 runs, **[emulation]**): 408 runs, all completed and verified, 0 failed gate checks (`S5/gate_*.json`). The first round (4, 3 and 12 blocks) is the pilot: its 4-block Holm test could not reach p < 0.05 (section 4.4), which is why a second round was run (section 8.1).
- **Main session (6 P + 7 E workers).** B0 P-only is the strongest baseline. Six EFT/HEFT/PEFT variants are 1.41% to 1.73% slower than it, all Holm-significant (EFT_E1 +1.62%, interval +1.21 to +2.28, p_holm 0.036; `S5/analysis_main/effects.csv`), each in 9 of 9 blocks (computed here). Greedy B4 is +47.9% over all blocks and +53.5% in the post-hoc analysis without the slow window. **Early versus late binding is now a controlled contrast:** `B0_P_early` (same placements as B0 P-only, early binding) is +1.68% (+1.24 to +2.31, p_holm 0.036).
- **A slow window in the main session (stated plainly).** Fourteen consecutive runs (block 5 run 0 at 12:40 UTC to block 6 run 1, ending about 14:30 UTC on 2026-10-13) ran slower than the rest: about 1.4 times for every policy but B4 (bound by its E-core tasks) in block 5, and about 2.5 times for three runs (EFT_CatBoost in block 5, EFT_E1_rc and EFT_MLP in block 6). The background-load monitor shows no heavy non-experiment process in that window, and **the cause is identified: the Windows System event log (`Kernel-Power` event 105, `data/results/stage5_20261013/windows_power_source_events.json`) records `AcOnline=false` at 18:11:21 local (battery at 100%) and `AcOnline=true` again at 19:59:07 (battery at 9.5%), i.e. the laptop ran on battery for 1 h 48 min; the first slow run started at 18:10:55 and the last ended at about 19:59, so the slow runs coincide with the battery interval; all other sessions ran on AC power according to the same log (AC online from 2026-10-12 08:59:39 to 2026-10-13 18:11:21, and again from 19:59:07; the Stage 1 reference runs of 2026-10-11 20:33-21:57 also fall in an AC interval)**. The pre-registered rules do not exclude such runs, so the primary analysis keeps them; they inflate the all-blocks effects of EFT_CatBoost (+8.68%), EFT_E1_rc (+13.92%) and EFT_MLP (+12.99%). A post-hoc analysis without blocks 5 and 6 (n = 7, labelled post-hoc) gives +1.44%, +1.93% and +2.04% for these three and +1.15% to +2.04% for all EFT variants. This is a measurement limit of this machine, not something to fix by re-running (section 8.2).
- **Scarce P cores (2 P + 7 E workers, 8 blocks).** EFT_E1 against greedy B4: -0.13% (-1.10 to +0.88): the point estimate is inside the pre-stated +-0.5%, the interval is wider, so equivalence at +-0.5% is **not resolved**. B0 P-only is +42.48% (+41.05 to +43.54) and EFT_CatBoost +15.65% (+14.84 to +16.12), both as predicted. **EFT_Ridge is 0.59% faster than B4** (-1.18 to -0.18, p_holm 0.0325; faster in 8 of 8 blocks, about 2.4 s of 412 s, computed here): statistically significant, below the 2% practical margin, no prediction had been made for it (`S5/analysis_regimeR/effects.csv`).
- **GPU workload (24 blocks).** EFT_E1 with the GPU is 2.10% faster than the same policy without it (-2.93 to -1.35, p_holm 0.0006), inside the pre-stated 1% to 3%; it is 3.53% faster than greedy B4 with the GPU (computed here) and indistinguishable from B0 P-only (-0.65%, -1.82 to +0.34, p_holm 0.27). Absolute makespans are about 7.1 s to 7.4 s because CPU stages dominate.
- **Emulated remote pool [emulation] (12 blocks).** Calibrated transfer cost 0.779 ms + 1.617 ns per byte. B4 with the remote pool R placed 12 tasks on R (one per block) on both links; the transfer-aware EFT placed none. D1 supported: B4 with R is 30.69% slower than B4 without R on the slow WAN link (+29.42 to +32.02, p_holm 0.0024). D2 not supported: EFT placed 0 tasks on R on both links, so there is nothing to compare. D3: EFT with R on the fast LAN +0.14% (-1.10 to +1.19), not distinguishable from no remote. The emulated pool gave no benefit to either policy.
- **Two mechanisms.** (1) Early versus late binding of the second wave of `mProject` tasks explains the 1.4% to 1.7% deficit of EFT, HEFT and PEFT against P-only: the controlled contrast B0_P_early reproduces it (section 8.2). (2) Knife-edge decisions amplify prediction bias: in the 2 P + 7 E regime the CatBoost predictions tipped a near tie the wrong way (pilot decision records; regret table in section 7.4).
- **Contribution (honest statement).** A controlled, overhead-accounted, real-hardware study with verified outputs and a null/negative headline confirmed in pre-registered sessions, two mechanisms, and the infrastructure (Windows-native Montage build, external-command DAG runtime, 14+ policies, decision-time-safe dataset builder, paired-block analysis, background-load monitor). It is not a new algorithm and not a general claim about prediction.
- **Outcome per pre-registered claim** (wording from EVALUATION_PROTOCOL section 12.5): (a) not supported at the practical margin in all four conditions; the only statistically significant advantage of a predictive policy over the strongest simple baseline is Ridge over B4 by 0.59% in the scarce-P regime; (b) supported; (c) not supported; (d) offline accuracy yes for Ridge on the held-out instance, scheduling effects do not depend on it; (e) significance resolved for P1, P3 (except equivalence of EFT_E1 at +-0.5%), P4 and D1. Details in section 8.3.
- **Gaps closed since the first version of this report:** patent claims read verbatim (0 occurrences of machine-learning or prediction terms in claims 1 to 20); HEFT and PEFT originals read and reproduced exactly by tests; DSS terms read; licences read from the files; drift check, learning curve and regret table run; figures fixed and three diagrams produced; background load measured; early binding tested as a controlled contrast; the Holm flaw resolved by the confirmatory sessions; the GPU session pre-registered before it ran. **Genuinely remaining:** five items, section 14.3 (the sixth, the slow-window cause, was closed: laptop on battery).

## 1. Question and hypothesis

Source: [PROJECT_SPEC.md](PROJECT_SPEC.md) sections 4 and 5.

- **Research question.** Under what workload and resource conditions does execution-time prediction improve dynamic DAG scheduling on heterogeneous resources after accounting for prediction, scheduling, queueing and data-transfer overhead?
- **Primary contribution.** A controlled, overhead-accounted, real-hardware study of how much predictor sophistication improves actual DAG scheduling of a real scientific workflow, using decision-time-safe data and a ladder from no prediction to learned models.
- **Supporting contributions.** (1) Generalisation of predictors and schedulers to instances and sizes not seen in training. (2) Transfer-aware placement to a remote or GPU pool: **[emulation]** for the remote pool (section 11.2: one emulated node behind a loopback link shim, no real network), **[real]** for the GPU on a separate workload (section 11.1).
- **Primary hypothesis (falsifiable, no promised size).** Prediction-aware placement beats the best non-predictive baseline only when the runtime ratios between resources and the contention are large relative to prediction cost, scheduling cost and timing noise. Otherwise a simple method matches it.
- **Supported by:** a paired-block makespan advantage whose confidence interval excludes zero in the high-ratio/high-contention conditions and not in the low conditions, after overhead is counted. **Rejected by:** no condition where predictive placement beats the strongest non-predictive baseline, or a gain that disappears once decision cost is counted. A null result is an accepted outcome.
- **Not claimed:** a new learning algorithm, a new list-scheduling algorithm, or novelty of "task graph + queues + eligibility" (claimed by the base patent, PROJECT_SPEC section 7). The proposed scheduler is a study instrument.

**Verdict on the hypothesis (pre-registered wording: "supported", "not supported", "not resolved by this design"; numbers are the confirmatory sessions, section 8).**

| Claim | Outcome | Evidence |
|---|---|---|
| (a) Prediction-aware placement beats the best non-predictive baseline in some condition | **Not supported** at the practical margin in all four conditions. Main (6 P + 7 E): the strongest baseline is B0 P-only; EFT_E1 +1.62% (+1.21 to +2.28), HEFT +1.54%, PEFT +1.73%, all slower in 9 of 9 blocks. Scarce P: EFT_E1 -0.13% against B4 (-1.10 to +0.88, n.s.); the only significant advantage is **EFT_Ridge -0.59%** (-1.18 to -0.18, p_holm 0.0325), about 2.4 s of 412 s and below the 2% margin. GPU: EFT_E1_gpu -0.65% against B0 P-only (-1.82 to +0.34, n.s.). Remote [emulation]: B0 P-only is 6.40% faster than EFT_E1 without remote (-7.44 to -5.49, as a change of P-only against EFT_E1) | `S5/analysis_main/effects.csv`, `analysis_regimeR/effects.csv`, `analysis_gpu_vs_P/effects.csv`, `analysis_remote/effects.csv` |
| (b) A simple method matches prediction otherwise | **Supported.** B0 P-only in the main, GPU and remote conditions (the remote session runs the image pipeline, label emulation); greedy B4 in scarce-P, where EFT_E1 and EFT_MLP are within 0.2% of it | same files |
| (c) Predictor sophistication improves scheduling | **Not supported.** Pilot: six predictors within 0.5% of each other (271.4 s to 272.7 s). Main: Ridge +1.54% and E3 +1.59% do no better than the static profile E1 +1.62% (post-hoc: CatBoost +1.44%, E1+rc +1.93%, MLP +2.04%, none better). Scarce P: CatBoost +15.65% (worse), Ridge -0.59% (tiny), MLP -0.02% | `stage3_20261012/pilot_gate.json`, main and scarce-P effects |
| (d) Generalisation to unseen instances and sizes | **Offline accuracy: yes for Ridge** on the held-out 157-task instance (MAE 1.36 s against 3.26 s for the static profile; CatBoost 2.32 s; MLP 2.98 s with RMSE 22.2 s); **no on the smallest fold**, where the learned models are worse than the static profile; learned-model error grows from the early to the late half of the runs (section 7.3). **Scheduling effects do not depend on it** (the policies tie or P-only wins on every instance used) | `stage3_20261012/eval/final_test/metrics.json`, `eval/tuning_loo/metrics.json`, `S5/analysis_extra/drift` |
| (e) Significance tests (Holm-adjusted sign-flip) | **Resolved** by the confirmatory sessions (block counts chosen so the smallest attainable p lies below the Holm threshold): P1, P4 and D1 significant as predicted; P3 supported for B0 P-only and CatBoost, EFT_E1 within +-0.5% as a point estimate but equivalence not resolved. The pilot's 3 to 4 blocks could not be significant (minimum p 0.25 and 0.125) | `S5/analysis_*/effects.csv` (`p_holm`), section 4.4 |

The rejection criterion of the hypothesis is met for the conditions tested. This does not show that no condition exists where prediction helps. The workload has one dominant task type (nine `mProject` tasks) and one pool speed ratio (3.59, computed here from `stage2_20261012/profile_montage/20261012T092355_profile.json`: 401.08 s on E against 111.77 s on P), and the pre-registration itself stated that a trivial rule is optimal whenever at least three P workers exist, so "a null result against the strongest baseline is expected by construction" (EVALUATION_PROTOCOL section 12.6).

## 2. Scope and evidence labels

- Machine-specific study: one laptop, one session family. Raspberry Pi 5 is a later extension; all Pi claims stay **[plan]**.
- What is **[real]**: Montage under 14 policies on this machine (Stage 2), Stage 3 collection, the pilot sessions, the confirmatory main, scarce-P and GPU sessions. What is **[emulation]**: the remote-pool session (one real node process on a core of this machine behind a loopback link shim; no real network). What is **[plan]**: Raspberry Pi 5.
- Historical evidence from the earlier machine (i5-1235U) and the 68-task image pipeline is kept as history and is not pooled with the Montage data. (The GPU workload of section 11 reuses the stage structure of that 68-task pipeline, 68 tasks per run, but all its numbers are new measurements on this machine.) Sessions with different design hash, code or environment are never pooled; the pilot and the confirmatory sessions are reported side by side, never pooled.

| Claim | Label | Evidence file |
|---|---|---|
| The Montage instance runs completely and reproducibly (sequential) | real | `stage1_20261011/valid/stage1_gate.json` |
| 14 policies run correctly on the heterogeneous runtime | real | `stage2_20261012/stage2_gate.json` |
| Offline prediction accuracy of six predictors on held-out rows | real (logged rows, offline) | `stage3_20261012/eval/{tuning_loo,final_test}/metrics.json` |
| Predictor selection by the frozen rule: EFT_E1 | real | `stage3_20261012/selection/selection_record.json` |
| Main session: six EFT/HEFT/PEFT variants 1.41% to 1.73% slower than B0 P-only (9 of 9 blocks) | real | `S5/analysis_main/effects.csv` |
| Early versus late binding explains that deficit (controlled contrast `B0_P_early`, +1.68%) | real | `S5/analysis_main/effects.csv` |
| Slow window in blocks 5 and 6 of the main session; cause identified: laptop on battery 18:11:21 to 19:59:07 local | real | `S5/analysis_main/runs.csv`, `S5/load/load_20261013T121952.jsonl`, `S5/analysis_main_posthoc_excl_blocks_5_6/` |
| Scarce P: EFT_E1 ties B4; Ridge -0.59%; CatBoost +15.65%; P-only +42.48% | real | `S5/analysis_regimeR/effects.csv` |
| GPU workload: EFT_E1 with GPU -2.10% against its CPU-only version; not distinguishable from P-only | real | `S5/analysis_gpu/effects.csv`, `analysis_gpu_vs_P/effects.csv` |
| Remote pool: B4 with R +30.69% on the WAN link; EFT never uses R | **emulation** | `S5/analysis_remote/effects.csv`, `analysis_remote_vs_B4/effects.csv`, `S5/gate_remote.json` |
| Drift check, learning curve, one-step regret | real (offline / derived from logs) | `S5/analysis_extra/` |
| Background machine load during the confirmatory sessions | real | `S5/load/load_20261013T121952.jsonl` |
| Pilot results (4, 3 and 12 blocks), kept as pilot | real | `S4/analysis_main/effects.csv`, `analysis_regimeR/effects.csv`, `gpu/analysis/effects.csv` |
| HEFT and PEFT results | real; implementations reproduce both papers' worked examples exactly (communication cost 0 in the Montage runs) | `S5/analysis_main/effects.csv`; [SOURCES_VERBATIM.md](SOURCES_VERBATIM.md) section 4 |
| Remote or edge offloading on a real network, Raspberry Pi 5 | plan, not done | none |
| Literature gap statement | bounded search: "not found in sources inspected" | [PROJECT_SPEC.md](PROJECT_SPEC.md) section 6, [LITERATURE_UPDATE.md](LITERATURE_UPDATE.md) |

## 3. Workload and environment

Sources: [WORKLOAD_AND_DATA_PROVENANCE.md](WORKLOAD_AND_DATA_PROVENANCE.md), [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md), the per-session `environment.json` of the Stage 4 sessions.

- **Workload.** Montage mosaic of DSS2 blue images, native Windows build of the Montage toolkit (Caltech-IPAC/Montage commit `ac0a15334f670ed83e328b6c5768f94b4b847359`, BSD 3-clause licence read in the `LICENSE` header), compiled with w64devkit (GCC 16.2.0) and patched for Windows (twelve workarounds listed in MONTAGE_WINDOWS_BUILD). The workflow generator is a Windows copy of `pegasus-isi/montage-workflow-v3` (commit `975047e916d3d049d9ff0da17e7fe5aaac979c64`, Apache-2.0) with three edits. Eight task types.
- **Primary instance** `d1.1_dss2b_c56.7_24.0`: 59 tasks, 147 dependency edges (`stage1_gate.json`: `dag.n_jobs` = 59, `dag.edges_jobDependencies` = 147; `only_in_jobDependencies` and `only_in_files` both empty). The 59 tasks are 9 `mProject`, 36 `mDiffFit`, 9 `mBackground`, and one each of `mConcatFit`, `mBgModel`, `mImgtbl`, `mAdd`, `mViewer` (computed here: 9 + 36 + 9 + 5 = 59; the gate file's per-transformation counts 27 and 108 are totals over three runs). Correction of an earlier skeleton line that read "27 `mProject` tasks": the instance has 9.
- **Other instances.** `d1.0_dss2b_c56.7_24.0` (19 tasks), `d1.1_dss2b_c10.7_41.3` (59 tasks), `d1.5_dss2b_c56.7_24.0` (157 tasks); roles in [STAGE3_FREEZE.md](STAGE3_FREEZE.md). Sequential times: section 5.
- **Input data.** Nine DSS images for the primary instance, 116,069,760 bytes, host `archive.stsci.edu`, survey `poss2ukstu_blue`, fetched 2026-10-11, hashes in `data/montage/instances/d1.1_dss2b_c56.7_24.0/instance.json`. **Terms of use read on 2026-10-13** ([SOURCES_VERBATIM.md](SOURCES_VERBATIM.md) section 6): the nine files carry survey POSSII-J, plate A1ET and the copyright card `Caltech/Palomar`; non-profit research use is free with an acknowledgement requested, commercial use needs written permission, and no page states a rule on third-party redistribution of the files, so the raw images stay out of public repositories. Acknowledgement text: section 15.
- **Environment** (`stage4_20261012/sessions_main/20261012T212448/environment.json`, same machine id `681ed3fc...` and environment hash `bac0fdd0...` in all three pilot sessions and, per `analysis.json`, in the four confirmatory sessions): Windows 11 Home Single Language 10.0.26200; i5-13500HX, 20 logical processors, RAM 16,858,472,448 bytes; the Windows topology API reports efficiency class 1 on logical processors 0 to 11 (six cores, two threads each) and class 0 on 12 to 19 (eight single-thread cores), which I read as P and E cores (the class-to-core-type reading is mine); WMI reports 14 cores. NVIDIA GeForce RTX 3050 6 GB Laptop GPU, driver 581.83, used only in the GPU workload. Python 3.11.9, numpy 2.4.6, pandas 3.0.6, scipy 1.17.1, torch 2.11.0+cu128, catboost 1.2.10.
- **Worker pools.** Main session: 6 P workers pinned to logical processors 0, 2, 4, 6, 8, 10 (one thread per P core) and 7 E workers pinned to logical processors 13 to 19, all with `affinity_ok` true in the `worker_ready` events (computed here from the event log of run `b0000_04_EFT_E1`); logical processor 12 is reserved for the coordinator (`planned_worker_pool_config` in `environment.json`, whose own P-slot list `[0, 2]` is the 2-P default and is the same in all sessions, so it does not describe the 6-P pinning). Scarce-P regime: 2 P workers (P0, P1) + 7 E. GPU workload: 6 P + 7 E + 1 CUDA worker (computed here from `worker_ready` counts).
- **Pool speed ratio.** `mProject` 111.77 s on a P core and 401.08 s on an E core (4 repetitions each), other task types seconds or less (`stage2_20261012/profile_montage/20261012T092355_profile.json`). `mProject` is 98.7% of sequential time (STAGE3_FREEZE section 4).
- **Machine state.** The machine was not idle (browser, editor, Claude desktop app, security and vendor services; a WSL VM in the pilot, as stated in RESEARCH_STATUS). For the confirmatory sessions the background-load monitor (`scripts/load_monitor.py`, `S5/load/load_20261013T121952.jsonl`) logged every 30 s: 1,928 samples from 06:50 to 23:18 UTC on 2026-10-13, longest gap 32 s (computed here). Median non-experiment CPU 35.1% summed over processes (psutil per-process percent, 100 = one logical processor, so about a third of one of 20), 95th percentile 70.2%, maximum 186%; median machine CPU 23.6%, maximum 49.5%; minimum free RAM 2.09 GB (9 samples below the 2.5 GB preflight threshold, which is evaluated at block start; the main session's 10 preflight records have a minimum of 3.90 GB, `sessions_main/20261013T132115/preflight.jsonl`). Most frequent non-experiment processes in the top five: claude.exe, dwm.exe, xboxpcapp.exe, code.exe, servicehost.exe. The monitor does not log CPU frequency or temperature. The pilot has no such record (only free RAM at preflight: at least 5.82 GiB before main-session runs, 5.75 GiB scarce-P and 5.08 GiB GPU, computed here from `runs.csv`, column `memory_available_start_bytes`).

## 4. Method

### 4.1 System architecture

Windows-native Python runtime: workflow adapter (Pegasus YAML to internal DAG, no manual edits), external-command task type with declared input and output files and fail-fast semantics, capability model for pools (cpu, cuda, remote), uniform eligibility for every policy, coordinator with ready queue and JSONL event log, affinity-pinned P and E worker processes plus one CUDA worker, pluggable schedulers and estimators, decision-context logging, dataset builder with train/serve parity tests, paired-block experiment runner and analysis, and a dashboard. Decision records and per-item implementation status: [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) (AD-1 to AD-14; status table dated 2026-10-12). Local pools cost zero transfer (all jobs share one work directory), so transfer cost is not exercised by the CPU-only Montage runs (AD-2).

### 4.2 Scheduling algorithms

- Non-predictive baselines: B0 (P-only, E-only), B1 round-robin, B2 static P, B3 shortest queue, B4 greedy eligible dispatch (a patent-mapped comparison baseline, not an implementation of the patent), B5 criticality, random.
- Predictive ladder: EFT with E1 static profile, E3 moving history, E1+rc online recalibration, `EFT_E1_rank` (rank priority; the study instrument), and learned Ridge (E4 form), CatBoost, MLP.
- Published static list schedulers: HEFT and PEFT. **The originals were read** ([SOURCES_VERBATIM.md](SOURCES_VERBATIM.md) sections 2 to 4): HEFT/CPOP in full from the open-access PDF; PEFT through chapter 3 of the author's open-access PhD thesis, which reproduces the paper (the IEEE-typeset article was not read, so its own equation numbers are not confirmed). `tests/test_heft_peft_papers.py` (3 tests) reproduces both papers' worked examples through the repository code: HEFT rank_u, processor assignment and makespan 80; PEFT OCT table (all 30 entries), rank_oct, step order and makespan 122; HEFT on the PEFT example 133. Four documented differences from the papers (SOURCES_VERBATIM 4.2): averages and processor sets are restricted to eligible workers; communication cost is 0 in the Montage runs (the adapter passes no `comm` callable), so HEFT's rank is computation-only and PEFT's OCT has no communication term; ties are broken deterministically; the plan is followed by an execution wrapper that does not re-plan a late task (ARCHITECTURE_DECISIONS AD-9).
- Binding: B0 P-only and B4 greedy dispatch a task only to an idle worker (late binding; `binds_only_idle` true in their run records); EFT, HEFT, PEFT and the learned-predictor EFT variants may queue a task on a chosen worker when it becomes ready (early binding; `binds_only_idle` false in every such run record of the pilot main session, computed here from the first event of each run). **`B0_P_early`**, new in the confirmatory main session, has the same placement set as B0 P-only (P workers only) but binds early (`binds_only_idle` false, pool P in its run records, computed here), so contrast P1 isolates binding style from placement. The binding style of B1, B2, B3, B5 and random was not checked here.
- Excluded: GNN+PPO, GRU/TCN, temporal Transformer, GNN predictor, image embeddings. **TabM is out** by the entry rule evaluated before data (needs at least 20,000 labelled rows; 2,706 fitting rows exist), stated reason: too few rows for a neural tabular model (STAGE3_FREEZE section 2).

### 4.3 Predictors and data

- Target: per-task, per-device kernel time. Setup/staging, transfer, queue wait and scheduling/prediction time are separate (EVALUATION_PROTOCOL section 3).
- Candidates: E1, E3, E1+rc, Ridge, CatBoost, MLP, hyper-parameters fixed before fitting (STAGE3_FREEZE amendment A1; no hyper-parameter tuned on errors). Frozen complexity order E1 < E3 < E1+rc < Ridge < CatBoost < MLP. Measured costs (section 7.2) put MLP below CatBoost in inference latency (median 22.5 µs against 478 µs) and model size (16 KB against 140 KB) but above it in training time (8.6 s against 0.75 s); no dated amendment of the order was written. The selection outcome does not depend on the CatBoost/MLP order, because the cheapest model (E1) qualified against every other model.
- Decision-time-safe features only; training rows from decision-context logs (`context_source=decision`) of runs whose output verified. Parity and leakage tests passed in the last recorded full suite (377 passed, 1 skipped; `stage3_20261012/full_suite_before_commit.txt`).
- Splits: leave-one-instance-out on three instances for fitting and tuning; `d1.5` final test, evaluated once.
- Collection: `designs_v2/` (42 runs, 14 blocks of three conditions: EFT_E1 and two RandomOccupancy settings), STAGE3_COLLECTION_PLAN.md. The v1 `designs/` directory is superseded and unused.

### 4.4 Selection rule and statistics

- Selection rule: cheapest model whose outcome is not worse than every more complex model, upper bound of the paired-bootstrap interval of `outcome(simple) - outcome(complex)` at most `margin`; **margin = 2.0% of makespan** (ln 1.02 = 0.0198; STAGE3_FREEZE section 2).
- Paired effect: log ratio of makespan against the reference within a block, stratified percentile bootstrap, 10,000 resamples, seed 0 (`analysis.json`: `n_boot`, `seed`). Confirmatory family = every condition against the reference, Holm over sign-flip p-values (`p_holm`); everything else is exploratory and unadjusted. The option `--posthoc-exclude-blocks` of `scripts/analyze_experiment.py` drops whole blocks for a sensitivity analysis and records the reason "post-hoc block exclusion (declared as such, not pre-registered)" in `exclusions.csv`; it is not a pre-registered rule.
- **Pre-registration flaw of the pilot, resolved by the confirmatory sessions.** The pilot's confirmatory family used Holm-adjusted sign-flip p-values (EVALUATION_PROTOCOL 12.5). A sign-flip test on n paired blocks cannot return a two-sided p-value below 2/2^n (n = 4: 0.125; n = 3: 0.25), and the pilot chose its block count from a minimum-detectable-effect rule without checking that; stored `p_holm` was 1.0 for every pilot main contrast and 0.9975 for every pilot scarce-P contrast. EVALUATION_PROTOCOL section 13 chose the confirmatory block counts so that 2/2^n lies below the Holm threshold of each family: main 9 blocks (2/512 = 0.0039 against 0.05/11 = 0.0045), scarce-P 8 (2/256 = 0.0078 against 0.01), GPU 24, remote 12 (0.00049 against 0.0083; section 14 of the protocol). The p-values are therefore attainable. One property to keep in mind (computed here): in the main session a contrast is Holm-significant only if all 9 blocks have the same sign (one discordant block gives 20/512 = 0.039 before and about 0.43 after the factor 11); all eleven contrasts are significant, ten with p_holm 0.036 and PEFT with 0.034, the smallest values this design can return, and every one of them is in the same direction in 9 of 9 blocks (computed here from `runs.csv`). The post-hoc analysis without blocks 5 and 6 has 7 blocks: its `p_holm` is 0.158 for every contrast (2/128 = 0.0156, times 11), so it cannot be significant by construction and is read as intervals only.
- Friedman and Wilcoxon cross-checks (`crosscheck.csv`, unadjusted, they only say that conditions differ): main Friedman statistic 53.09, p = 1.7e-07 (9 blocks); scarce-P 34.07, p = 2.3e-06 (8); GPU 96.68, p = 1.2e-18 (24); remote 49.96, p = 4.8e-09 (12). Wilcoxon against the reference agrees with the sign-flip results (for example main, every contrast p = 0.0039; scarce-P EFT_E1 p = 0.38, EFT_MLP p = 0.31, EFT_Ridge p = 0.0078).
- Block counts: pilot 4 (main, 2 per instance), 3 (scarce-P, budget-limited), 12 (GPU); confirmatory 9, 8, 24, 12 (EVALUATION_PROTOCOL 13, 14).

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
- **Time-ordered drift check (run 2026-10-13; `S5/analysis_extra/drift/`; commands and the sha256 of the frozen and the time-split config in `S5/analysis_extra/commands.txt`).** The frozen final-test config with only the split changed to a time policy (train fraction 0.7); `order_index` is empty in these datasets, so run order is the first task start time. Overall MAE of the time split (`eval_time/metrics.json`): E1 3.514 s, E3 3.503 s, E1+rc 3.531 s, Ridge 0.8395 s, CatBoost 2.123 s, MLP 1.334 s. Late against early half of the held-out runs (451 rows each; mean observed task time 27.57 s early and 32.13 s late, +16.6%, computed here; `drift/summary/drift_summary.csv`): MAE early to late Ridge 0.732 s to 0.947 s, MLP 1.120 s to 1.548 s, CatBoost 1.770 s to 2.476 s, against E1 3.480 s to 3.548 s. **The late/early MAE ratio is 1.29 (Ridge), 1.38 (MLP) and 1.40 (CatBoost) for the learned models and 1.01 to 1.02 for the references E1, E3 and E1+rc** (ratios computed here). Median absolute percentage error early to late: CatBoost 0.192 to 0.206, Ridge 0.255 to 0.304, MLP 0.195 to 0.260, E1 0.376 to 0.385, so the relative error of the learned models rises by 0.01 (CatBoost) to 0.07 (MLP) while the absolute error rises by 29% to 40%. On the `mProject` rows (71 per half) Ridge goes from MAE 3.61 s to 4.84 s. Reading: the learned models degrade from the early to the late runs of a session, the static references do not; the halves hold 2 to 3 runs per session, so this is descriptive (the script says so), not a test.
- `d1.5` final test, evaluated once, size withheld: table above. Limit: the test instance shares its sky centre with two training instances (it is a larger instance of the same region).
- **Learning curve (TabM entry rule condition 2; run 2026-10-13; `S5/analysis_extra/learning_curve/`, `curve.csv`, `learning_curve.png`, `run.log`).** Frozen configs, growing fractions of whole runs stratified by instance, 5 repeats, scored on held-out rows. **Ridge is flat from 20% of the fitting runs on `d1.5`** (MAE 1.37 s at 20%, 1.36 s at 100%) **and from 40% in leave-one-instance-out** (1.34 s and 1.32 s). **CatBoost is non-monotone** (`d1.5`: 2.46, 2.62, 2.01, 2.33, 2.47, 2.32 s at 10, 20, 40, 60, 80, 100%); the script's flag compares only 80% with the single 100% fit and says "falling" for CatBoost (-6.2% on `d1.5`, -9.2% in leave-one-instance-out) and "flat (within subsample spread)" for MLP and Ridge, whose subsample spread reaches 1.77 s (MLP). Condition 2 is therefore not established by a steady fall; TabM stays out regardless by condition 1 (2,706 rows against 20,000).

### 7.4 Decision-level regret

Run 2026-10-13 with `scripts/regret_table.py` (`S5/analysis_extra/regret/regret_table.md`, `regret_decisions.csv`, `regime_mProject_diff.csv`). **Data: the pilot sessions `S4/sessions_main` and `S4/sessions_regimeR`, with the Stage 2 and Stage 3 pilot sessions as extra oracle observations**, not the confirmatory sessions. Regret = finish of the chosen worker minus finish of the best worker, both with the replay-oracle kernel time (median of the same task on a pool in other runs) and the actual worker backlog at binding time; myopic (one step), kernel-only, workers whose pool has no oracle observation are left out of the minimum.

| Set | Policy | Decisions | Mean regret per decision (s) | Total per run (s) |
|---|---|---|---|---|
| main (4 runs per policy, 236 decisions) | B4_greedy_eligible | 236 | **6.850** | 404.1 |
| main | EFT_E1 | 236 | 0.312 | 18.4 |
| main | EFT_CatBoost | 236 | 0.117 | 6.9 |
| main | HEFT_E1 / PEFT_E1 | 236 | 0.362 / 0.331 | 21.4 / 19.6 |
| regime R (3 runs per policy, 177 decisions) | B4_greedy_eligible | 177 | 17.136 | 1011.0 |
| regime R | HEFT_E1 | 177 | 8.767 | 517.3 |
| regime R | **EFT_CatBoost** | 177 | **2.538** | 149.7 |
| regime R | **EFT_E1** | 177 | **0.134** | 7.9 |

(Other main-session policies are in `regret_table.md`; the Ridge model appears there under the name EFT_E4, 0.193; the table's B0 P-only rows are zero because it binds only to P.) **Exactly 6 `mProject` decisions differ between EFT_CatBoost and EFT_E1 in the scarce-P regime** (blocks 0 to 2, tasks ID0000007 and ID0000008): CatBoost chose a P worker at a predicted execution time of 94.4 s against actual 113.0 s to 115.7 s, E1 chose an E core (actual 395.4 s to 399.3 s), and the CatBoost choices carry a regret of 57.5 s to 61.7 s against 0 for E1 (`regime_mProject_diff.csv`). Limits: one-step and myopic, kernel-only, the oracle is a stand-in for the unobservable counterfactual, pilot sessions only.

### 7.5 Model selection

Frozen rule, margin 2.0%, applied to the Stage 3 scheduling pilot (`stage3_20261012/pilot_sessions/20261012T195449`, design `stage3_scheduling_pilot`, 6 predictors x 3 interleaved blocks on the primary instance, 18 runs, all verified, `n_failing_checks` 0, `pilot_gate.json`). Mean makespans: EFT_CatBoost 271.4 s, EFT_MLP 271.5 s, EFT_Ridge 271.6 s, EFT_E1 271.8 s, EFT_E1_rc 272.4 s, EFT_E3 272.7 s (all within 0.5%; computed from `pilot_gate.json`). Selection record (`selection/selection_record.json`): **EFT_E1 selected**; every comparison of E1 against a more complex model has a paired-log-ratio interval upper bound of at most 0.0050 (E3 0.0014, E1+rc 0.0037, Ridge 0.0036, CatBoost 0.0050, MLP 0.0033), far below the 0.0198 margin. TabM: out by the entry rule. Complexity order: not amended (see 4.3).

## 8. Scheduling results

### 8.1 Pilot, pre-registrations and design

- **The first round is the pilot.** The first-round Stage 4 sessions (`S4`: main 4 blocks and 44 runs, scarce-P 3 blocks and 15 runs, GPU 12 blocks and 84 runs; results in section 8.4) are the pilot of the confirmatory sessions. Reason for the second round: the pilot's pre-registered Holm-adjusted sign-flip test could not return p < 0.05 with 4 blocks (smallest attainable p 0.125, section 4.4), and the pilot GPU session had been written ten seconds before it started without an analysis plan (EVALUATION_PROTOCOL section 13). Pilot and confirmatory numbers are never pooled (different design hashes). The baseline pilot that fixed the strongest baselines and the first block counts is the Stage 2 matrix (14 policies x 3 blocks) and the Stage 3 scheduling pilot (EVALUATION_PROTOCOL 12.1 to 12.4).
- **Pre-registration of the confirmatory sessions** (EVALUATION_PROTOCOL sections 13 and 14, before the first block of each): section 13 (main, scarce-P, GPU) was committed in `13d1649` at 2026-10-13 12:19:40 +0530 (06:49:40 UTC); the GPU session, the first to run, started at 06:49:56 UTC, 16 s later; the main and scarce-P sessions started later (`session.json`). Section 14 (remote emulation) was committed in `868eeea` at 2026-10-14 04:52:28 +0530 (23:22:28 UTC on 13 October); that session started at 23:22:40 UTC, 12 s later. The design hash printed in the protocol equals `design_sha256` in every session's `analysis.json` (checked here, four of four). Pre-stated predictions: P1 to P4 (13.1) and D1 to D3 (14).
- **Sessions.**

| Session | Design hash | Pools | Instances / workload | Blocks | Runs | Reference | Run time (UTC, 2026-10-13) | Source hash |
|---|---|---|---|---|---|---|---|---|
| `stage5_main_confirm` (`S5/sessions_main/20261013T132115`) | `9228d7ac...4648` | 6 P + 7 E | `d1.1 c56.7_24.0` and `d1.1 c10.7_41.3`, alternating | 9 | 108 (12 conditions) | B0 P-only | 07:51 to 17:16 (9 h 25 min) | `95a74ba36708` |
| `stage5_regimeR_confirm` (`S5/sessions_regimeR/20261013T224600`) | `7dac58e3...5126` | 2 P + 7 E | `d1.1 c56.7_24.0` | 8 | 48 (6) | B4 greedy | 17:16 to 23:19 (6 h 03 min) | `95a74ba36708` |
| `stage5_gpu_confirm` (`S5/gpu_sessions/20261013T121953`) | `273a155d...8af7` | 6 P + 7 E + 1 CUDA G | image pipeline, tile 1024, 16 branches (68 tasks) | 24 | 168 (7) | EFT_E1_cpu | 06:49 to 07:51 (1 h 01 min) | `d6e480bcfa67` |
| `remote_emulation_confirm` (`S5/remote_sessions/remote_confirm`), **[emulation]** | `4dab0106...3d49` | 2 P + 6 E + 1 emulated remote R | image pipeline, tile 512, 16 branches (68 tasks) | 12 | 84 (7) | EFT_E1_no_remote | 23:22 to 23:39 (16.6 min) | `95a74ba36708` |

  Worker pools read from the `worker_ready` events of one run per session (computed here). All four sessions: machine id `681ed3fc...`, environment hash `bac0fdd0...` (`analysis.json`); status complete, all blocks completed, 0 failed gate checks and all runs `completed` and `output_verified` in `S5/gate_sessions_main.json` (108 runs), `gate_sessions_regimeR.json` (48), `gate_gpu_sessions.json` (168) and `gate_remote.json` (84); `warmup_blocks` 0, `n_excluded` 0 (`analysis.json`), all 408 runs in the primary analysis. Git HEAD `13d1649` for main, scarce-P and GPU, `868eeea` for remote, dirty flag true in all (the files that made it dirty were not recorded). The source hash of the GPU session differs from the other three (`analysis.json`, `code_versions`); what changed in between is not recorded in the manifests, and the sessions are not pooled in any analysis.
- Additional analyses made after the first analysis of a session, with a second reference, are exploratory and labelled as such: `analysis_gpu_vs_P` (reference B0 P-only), `analysis_remote_vs_B4` (reference B4_no_remote; D1 is stated as this exploratory contrast in EVALUATION_PROTOCOL section 14), `analysis_main_posthoc_excl_blocks_5_6` (post-hoc). The stored `p_holm` of those tables adjusts within each table's own family of contrasts.
- E-only, round-robin and random were not re-run (27 minutes per block, cannot be the strongest baseline); their numbers are the Stage 2 means in section 6 and are never pooled.

### 8.2 Confirmatory results

**Main session (6 P + 7 E workers, 2 instances, 9 blocks, 108 runs, reference B0 P-only).** All 108 runs completed with verified output. Makespan is the geometric mean pooled over instances with a 95% bootstrap interval stratified by instance (`S5/analysis_main/summary.csv`, rows `pooled_log_scale`); effects are paired against B0 P-only (`S5/analysis_main/effects.csv`, rows `primary`, `makespan_s`, tier confirmatory, `n_blocks` 9; `p_holm` from the same rows; Holm family of 11 contrasts). The last columns are the **post-hoc** analysis without blocks 5 and 6 (`S5/analysis_main_posthoc_excl_blocks_5_6/effects.csv`, 7 blocks, 84 runs; `p_holm` 0.158 for every contrast, so none can be significant). Decision time and tasks on E cores per run: `summary.csv` (`sched_overhead_total_s_mean`) and `gate_sessions_main.json` (`tasks_per_pool`, min to max over the 9 runs).

| Policy | Makespan, all blocks (s) | Effect vs B0 P-only, all blocks (95% CI) | p_holm | Post-hoc, 7 blocks: makespan (s), effect (95% CI) | Decision time per run (s) | Tasks on E |
|---|---|---|---|---|---|---|
| B0_P_only | 283.0 (271.7 to 304.5) | reference | | 272.4; reference | 0.0009 | 0 |
| **B0_P_early** (P1) | 287.7 (275.8 to 311.5) | **+1.68%** (+1.24 to +2.31) | 0.036 | 276.2; +1.40% (+1.20 to +1.60) | 0.0014 | 0 |
| EFT_E1 | 287.6 (275.4 to 311.4) | +1.62% (+1.21 to +2.28) | 0.036 | 276.0; +1.33% (+1.19 to +1.48) | 0.021 | 0 |
| EFT_E1_rank (instrument) | 287.0 (275.2 to 310.5) | +1.41% (+1.04 to +1.99) | 0.036 | 275.5; +1.15% (+0.98 to +1.31) | 0.021 | 0 to 2 |
| EFT_E3 | 287.5 (275.5 to 311.2) | +1.59% (+1.11 to +2.22) | 0.036 | 276.0; +1.31% (+1.02 to +1.64) | 0.022 | 0 to 30 |
| EFT_Ridge | 287.3 (275.4 to 310.7) | +1.54% (+1.12 to +2.06) | 0.036 | 276.0; +1.31% (+1.06 to +1.63) | 0.058 | 1 to 4 |
| HEFT_E1 | 287.4 (275.3 to 310.9) | +1.54% (+1.14 to +2.08) | 0.036 | 276.0; +1.34% (+1.09 to +1.56) | 0.0031 | 9 |
| PEFT_E1 | 287.9 (275.5 to 312.0) | +1.73% (+1.14 to +2.48) | 0.034 | 276.1; +1.37% (+1.02 to +1.85) | 0.0031 | 9 |
| EFT_CatBoost | 307.5 (275.8 to 379.6) | +8.68% (+1.32 to +24.66) | 0.036 | 276.3; +1.44% (+1.23 to +1.70) | 1.65 | 1 to 5 |
| EFT_E1_rc | 322.4 (277.0 to 402.7) | +13.92% (+1.63 to +41.71) | 0.036 | 277.7; +1.93% (+1.29 to +2.76) | 0.025 | 0 to 16 |
| EFT_MLP | 319.8 (277.4 to 390.4) | +12.99% (+1.75 to +37.71) | 0.036 | 278.0; +2.04% (+1.39 to +3.03) | 0.12 | 3 to 6 |
| B4_greedy_eligible | 418.5 (416.1 to 421.0) | +47.87% (+37.47 to +54.59) | 0.036 | 418.1; +53.49% (+51.59 to +55.47) | 0.0014 | 9 to 13 |

Reading, per pre-registered prediction (section 8.3):

- **P1, supported.** `B0_P_early` has exactly the placements of B0 P-only and differs only by binding style; it is slower in 9 of 9 blocks (2.6 s to 16.4 s, median 3.5 s, computed here from `runs.csv`), +1.68% (+1.24 to +2.31), p_holm 0.036. In the post-hoc analysis +1.40% (+1.20 to +1.60). Queue wait summed over tasks per run is 799 s for `B0_P_early` against 453 s for B0 P-only in the post-hoc set (`summary.csv`, `queue_wait_total_s_mean`, computed here): early binding queues tasks on workers. This is the mechanism behind the deficit of EFT, HEFT and PEFT, now shown by a controlled contrast and not only by the pilot logs.
- **P2, supported for the six stable variants.** EFT_E1 +1.62%, EFT_E1_rank +1.41%, EFT_E3 +1.59%, EFT_Ridge +1.54%, HEFT_E1 +1.54% and PEFT_E1 +1.73% lie inside the pre-stated 1% to 2%, all significant, each in 9 of 9 blocks. For EFT_CatBoost, EFT_E1_rc and EFT_MLP the all-blocks magnitude (+8.68%, +13.92%, +12.99%) is dominated by the three outlier runs of the slow window (below); the direction (slower than P-only) is supported, the magnitude is not a property of the policies: without blocks 5 and 6 they are +1.44%, +1.93% and +2.04%. B4 is +47.87% over all blocks and +53.49% in the post-hoc set; the pre-stated "about 54%" is met by the post-hoc value, and the all-blocks value is lower because P-only was slow in block 5 (378.3 s against 269 s to 277 s in the other blocks) while B4, which is bound by its E-core tasks, was not (418.4 s; computed here from `runs.csv`).
- **Practical reading.** Every EFT, HEFT and PEFT policy is slower than B0 P-only by 1.15% to 2.04% (about 3 s to 6 s) once the slow window is set aside. The achieved 80%-power minimum detectable effect is 0.89% to 1.28% for `B0_P_early` and the six stable variants and 21% to 36% for CatBoost, E1+rc and MLP, whose variance is inflated by the outlier runs (`effects.csv`, `mde_pct_80power`). Per-block differences are in `runs.csv`.

**The slow window of the main session (stated plainly).** Fourteen consecutive runs ran slower than the rest: block 5 run 0 (`b0005_00_B0_P_only`, started 12:40:54 UTC) to block 6 run 1 (`b0006_01_EFT_MLP`, started 14:18:27 UTC; the next run started 14:29:56 UTC and is normal), computed here from `run_manifest.json` and `runs.csv` (block ids are 0-based; the sixth and seventh blocks). In block 5 every policy took about 1.4 times as long as in the other blocks (B0 P-only 378.3 s, EFT_E1 394.8 s, EFT_E3 394.1 s, and so on, against about 270 s to 279 s elsewhere), except B4, whose makespan is bound by its E-core tasks (418.4 s). Three runs took about 2.5 times as long: `b0005_11_EFT_CatBoost` 712.1 s, `b0006_00_EFT_E1_rc` 750.1 s and `b0006_01_EFT_MLP` 683.7 s. The remaining ten runs of block 6 are normal (276.5 s to 280.9 s, B4 420.9 s). The `mProject` kernel on P cores took 114.8 s to 158.0 s in all other runs (median 144.6 s, 735 task records), 160 s to 223 s in the first ten runs of the window, 236 s to 245 s in the B4 run, and 296 s to 380 s in the last three runs; the nine `mProject` tasks stayed on P workers in every run of the window (6 in the B4 run; computed here from the event logs), so the slowdown is in the kernel time, not in placement. The background-load monitor (section 3) shows no heavy non-experiment process in that window: median non-experiment CPU 45.5% against 34.2% outside it, median machine CPU 29.2% against 22.9%, minimum free RAM 2.61 GB; the largest single reading in the window is `searchindexer.exe` at 48.3% (12:56:28 UTC) (computed here from the load log; processes are listed by name only). CPU frequency and temperature were not logged. The cause is **the cause is identified: the Windows System event log (`Kernel-Power` event 105, `data/results/stage5_20261013/windows_power_source_events.json`) records `AcOnline=false` at 18:11:21 local (battery at 100%) and `AcOnline=true` again at 19:59:07 (battery at 9.5%), i.e. the laptop ran on battery for 1 h 48 min; the first slow run started at 18:10:55 and the last ended at about 19:59, so the slow runs coincide with the battery interval; all other sessions ran on AC power according to the same log (AC online from 2026-10-12 08:59:39 to 2026-10-13 18:11:21, and again from 19:59:07; the Stage 1 reference runs of 2026-10-11 20:33-21:57 also fall in an AC interval)**. The pre-registered exclusion rules (EVALUATION_PROTOCOL 12.5) do not exclude such runs, so the primary analysis keeps them and the table above is the pre-registered result. The post-hoc sensitivity analysis (`--posthoc-exclude-blocks 5 6`, 24 runs listed in `exclusions.csv` with the reason "post-hoc block exclusion") has 7 blocks and cannot be Holm-significant by construction; all its intervals are narrow and positive: +1.15% to +2.04% for the EFT variants and +1.40% for B0_P_early. This is a measurement limit of this machine, not something to fix by re-running.

**Scarce-P session (2 P + 7 E workers, primary instance, 8 blocks, 48 runs, reference B4 greedy).** All runs completed with verified output (`S5/analysis_regimeR/summary.csv`, `effects.csv`, `gate_sessions_regimeR.json`; Holm family of 5 contrasts, smallest Holm step 0.01).

| Policy | Makespan (s), min to max | Effect vs B4 greedy (95% CI) | p_holm | Decision time per run (s) | Tasks on P / E per run |
|---|---|---|---|---|---|
| B4_greedy_eligible | 412.2 (410.2 to 421.7) | reference | | 0.0014 | 24.9 / 34.1 |
| EFT_E1 | 411.6 (409.7 to 421.5) | -0.13% (-1.10 to +0.88) | 1 | 0.015 | 41.0 / 18.0 |
| EFT_Ridge | 409.8 (409.4 to 411.0) | **-0.59%** (-1.18 to -0.18) | 0.0325 | 0.041 | 39.0 / 20.0 |
| EFT_MLP | 412.1 (409.4 to 421.0) | -0.02% (-0.21 to +0.27) | 1 | 0.087 | 34.0 / 25.0 |
| EFT_CatBoost | 476.7 (475.9 to 479.1) | **+15.65%** (+14.84 to +16.12) | 0.0325 | 1.17 | 31.1 / 27.9 |
| B0_P_only | 587.2 (582.3 to 593.1) | +42.48% (+41.05 to +43.54) | 0.0325 | 0.0008 | 59.0 / 0 |

(Tasks per run computed here from `gate_sessions_regimeR.json`, `tasks_per_pool` summed over the 8 runs and divided by 8.)

- **P3, supported.** B0 P-only +42.48% (pre-stated about 41%: the stated value lies just below the interval, +41.05 to +43.54); EFT_CatBoost +15.65% (about 15%: inside the interval); EFT_E1 against B4 -0.13%, a point estimate inside the pre-stated +-0.5%, with an interval (-1.10 to +0.88) wider than that band, so **equivalence at +-0.5% is not resolved**. B4 is the strongest simple baseline, as predicted from the profile (EVALUATION_PROTOCOL 12.2).
- **EFT_Ridge (exploratory, no prediction made).** -0.59% against B4 is statistically significant (p_holm 0.0325); Ridge is faster than B4 in 8 of 8 blocks, by 0.45 s to 10.7 s (median 1.0 s; computed here from `runs.csv`), about 2.4 s of 412 s on the geometric means. This is **below the 2% practical margin of the freeze** and is driven in part by two B4 blocks at 413.2 s and 421.7 s against 410.2 s to 410.6 s in the other six (computed here). EFT_MLP is -0.02% (-0.21 to +0.27), not significant, its interval inside +-0.5%; no equivalence test was pre-registered. EFT_E1 had one slow block too (421.5 s, block 1).
- Decision cost: CatBoost costs 1.17 s per run (19.8 ms per decision), 0.24% of its makespan (computed here); this is not what makes it 15.65% slower (the placement is, section 8.4).

**Mechanisms.** (1) Early versus late binding: the controlled contrast P1 above; the pilot's worker-timeline observation is kept in section 8.4. (2) Knife-edge decisions amplify prediction bias: derived from the pilot decision records (section 8.4) and quantified by the regret table (section 7.4: regime R mean regret EFT_CatBoost 2.538 s per decision against EFT_E1 0.134 s, six `mProject` decisions with regret 57.5 s to 61.7 s). In the confirmatory scarce-P session EFT_CatBoost places 31.1 tasks on P and 27.9 on E per run, the same split as in the pilot (31 and 28); the individual decision records of the confirmatory runs were not re-read here.

**Cross-checks and excluded runs.** The Friedman and Wilcoxon cross-checks are in section 4.4. No run is excluded in any primary analysis (`exclusions.csv` has only the header, except the post-hoc table).

### 8.3 Hypothesis check

Pre-registered predictions (EVALUATION_PROTOCOL 13.1 and 14), with the row of the effects table that carries the number (`variant primary`, `metric makespan_s`, columns `cond` and `ref`):

| Prediction | Outcome | File and row |
|---|---|---|
| P1: `B0_P_early` slower than `B0_P_only` by 1% to 2%; supported only if Holm-significant and positive | **Supported.** +1.68% (+1.24 to +2.31), p_holm 0.036; post-hoc +1.40% (+1.20 to +1.60) | `S5/analysis_main/effects.csv`, `B0_P_early` vs `B0_P_only`; `analysis_main_posthoc_excl_blocks_5_6/effects.csv` |
| P2: EFT/HEFT/PEFT 1% to 2% slower than B0 P-only; B4 about 54% slower | **Supported** for EFT_E1 +1.62%, E3 +1.59%, rank +1.41%, Ridge +1.54%, HEFT +1.54%, PEFT +1.73% (all significant). **Direction only** for EFT_CatBoost +8.68%, EFT_E1_rc +13.92%, EFT_MLP +12.99% (inflated by the slow window; +1.44%, +1.93%, +2.04% post-hoc). B4 +47.87% all blocks, +53.49% post-hoc | `S5/analysis_main/effects.csv`; post-hoc file |
| P3: in scarce-P EFT_E1 equals B4 within +-0.5%; B0 P-only about 41% slower; EFT_CatBoost about 15% slower | **Supported** for P-only (+42.48%, +41.05 to +43.54) and CatBoost (+15.65%, +14.84 to +16.12). **EFT_E1: -0.13% (-1.10 to +0.88): point estimate inside +-0.5%, equivalence not resolved.** Ridge -0.59% (p_holm 0.0325) and MLP -0.02% were exploratory | `S5/analysis_regimeR/effects.csv`, `B0_P_only`, `EFT_CatBoost`, `EFT_E1`, `EFT_Ridge`, `EFT_MLP` vs `B4_greedy_eligible` |
| P4: EFT_E1 with GPU faster than EFT_E1 CPU-only by 1% to 3% | **Supported.** -2.10% (-2.93 to -1.35), p_holm 0.0006 (faster in 20 of 24 blocks, computed here) | `S5/analysis_gpu/effects.csv`, `EFT_E1_gpu` vs `EFT_E1_cpu` |
| D1 [emulation]: on the WAN link B4 with R is slower than B4 without R | **Supported.** +30.69% (+29.42 to +32.02), p_holm 0.0024 (slower in 12 of 12 blocks, computed here) | `S5/analysis_remote_vs_B4/effects.csv`, `B4_remote_slow_wan` vs `B4_no_remote` |
| D2 [emulation]: EFT places fewer tasks on R on the WAN link than on the LAN link | **Not supported.** 0 tasks on R on both links, so no difference exists | `S5/gate_remote.json`, `tasks_per_pool` |
| D3 [emulation]: no direction for EFT_E1 with R on the LAN link | EFT_E1_remote_fast_lan +0.14% (-1.10 to +1.19) against no remote, not significant | `S5/analysis_remote/effects.csv`, `EFT_E1_remote_fast_lan` vs `EFT_E1_no_remote` |

The support criterion of section 1 (a paired-block advantage whose interval excludes zero in some high-ratio condition against the strongest non-predictive baseline, and which is practically relevant) is not met in any of the four conditions; the only interval that excludes zero in favour of a predictive policy is EFT_Ridge against B4 in the scarce-P regime (-0.59%), which is below the 2% margin. The rejection criterion ("no condition where predictive placement beats the strongest non-predictive baseline") is met for the conditions tested. The per-claim outcome table is in section 1. A null result is stated as a null.

### 8.4 Pilot results (first round, `S4`; kept as the pilot)

All paths in this subsection are under `S4` (`data/results/stage4_20261012`). These sessions (4, 3 and 12 blocks, source hash `5650bc0ab775`, git HEAD `4b66dcc`, dirty flag true) were pre-registered in EVALUATION_PROTOCOL section 12 (committed `4b66dcc` at 2026-10-12 21:24:39 +0530; the main session started 21:24:51 +0530; design hashes `e5302e6b...6ae0` and `9f619cc8...7f0f` equal the sessions' `design_sha256`). Their Holm-adjusted tests could not reach p < 0.05 (section 4.4), so the numbers below are descriptive intervals; the confirmatory sessions of section 8.2 supersede them. No session was excluded, `n_excluded` 0 in all three pilot `analysis.json`.

**Pilot main session (6 P + 7 E workers, 2 instances x 2 blocks, reference B0 P-only).** All 44 runs completed with verified output; makespan geometric mean pooled over instances with a 95% bootstrap interval stratified by instance (`analysis_main/summary.csv`), paired effect against B0 P-only (`effects.csv`, tier confirmatory, `n_blocks` 4), scheduling and inference time per run (`summary.csv`, `sched_overhead_total_s_mean`) and tasks on E cores over the four runs of each condition (`gate_sessions_main.json`, `tasks_per_pool`).

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

**Mechanism: early versus late binding (primary instance; observation from the pilot logs, later tested as a controlled contrast in the confirmatory session, section 8.2).** With 6 P workers and 9 `mProject` tasks, P-only runs two waves: six tasks first (142 s to 147 s each) and three later (114 s to 119 s each). Late binding hands the three remaining tasks to whichever workers finish first. EFT, HEFT and PEFT predict all P workers equal and bind the later tasks at dispatch time to a worker that does not necessarily finish first, whose first-wave time differs by several seconds. Computed here from the raw event logs of `sessions_main`: the last `mProject` completion occurs 260.6 s to 262.7 s after run start in the four B0 P-only runs (mean 261.2 s) and 263.4 s to 265.9 s in the four EFT_E1 runs (mean 264.6 s), a difference of 3.4 s that matches the makespan difference (268.5 s against 272.0 s, 3.5 s). Decision time is not the cause: EFT_E1 spends 0.021 s per run on decisions. The pairing of workers that produces the 3.4 s was taken from the parent session's check of worker assignment; this report verified the timing difference, not each assignment.

**Pilot scarce-P regime (2 P + 7 E workers, primary instance, 3 blocks, 15 runs, reference B4 greedy).** All runs completed with verified output.

| Policy | Makespan mean (s), min to max | Effect vs B4 greedy | Decision time per run (s) | Tasks on P / E |
|---|---|---|---|---|
| B4_greedy_eligible | 407.6 (407.2 to 408.0) | reference | 0.0013 | 23 to 26 / 33 to 36 |
| EFT_E1 | 407.6 (407.5 to 407.6) | -0.01% (-0.12 to +0.11) | 0.015 | 39 to 41 / 18 to 20 |
| HEFT_E1 | 407.9 (407.5 to 408.1) | +0.06% (+0.03 to +0.09) | 0.0029 | 33 / 26 |
| EFT_CatBoost | 468.6 (467.9 to 469.8) | **+14.96%** (+14.73 to +15.39) | 1.16 | 31 / 28 |
| B0_P_only | 576.5 (574.6 to 577.7) | +41.43% (+41.13 to +41.68) | 0.0008 | 59 / 0 |

The pre-registered expectation held: P-only needs about five waves (the protocol estimated about 560 s; observed 576.5 s) and greedy B4 is the strongest simple policy. EFT_E1 equals B4; HEFT is 0.06% (0.24 s, computed here) slower with an interval that excludes zero but is tiny.

**Mechanism: knife-edge decisions amplify prediction bias (computed here from the decision records of the three `EFT_CatBoost` runs, identical in all three).** With E1 the seventh to ninth `mProject` tasks go to E cores (predicted 401.1 s on E; actual 393 s to 399 s) while six tasks queue on the two P workers (predicted finish 335.3 s, actual about 345 s). CatBoost predicts the first two `mProject` tasks on P at 130.1 s and 134.2 s and every later one at 94.4 s, against actual 112.5 s to 115.7 s (an under-prediction of about 16% to 18%), so queued P finish times look short: the seventh and eighth tasks are queued on P0 and P1 with predicted finish 413.3 s and 417.4 s, while the best E finish is predicted 450.3 s (CatBoost also over-predicts the E-core time: 450.3 s against actual 401 s to 402 s, about +12%). Both errors push the same way, and correcting either one alone would flip the decision. Result: seven `mProject` tasks queue on two P workers, the last ending 459.7 s after run start (E-core placement would end near 400 s), which is the +15.0% (60 s) of the table. The parent session's summary of this decision gave the E prediction as 401 s (the E1 value); the CatBoost run records give 450.3 s (this report uses the run records). The lesson stands either way: Ridge, the more accurate model offline (MAE 1.36 s against 3.26 s for E1 on the held-out instance), does not guarantee a better schedule, because what matters is the error on the decisive task type at a near tie. The correlation of offline error and scheduling outcome across six predictors is not tested here.

**Cross-checks and excluded runs (pilot).** Friedman test over all conditions (unadjusted): main p = 0.032, scarce-P p = 0.034 (`crosscheck.csv`); no run excluded (`exclusions.csv` empty apart from the header; `runs.csv` `included_primary` true for 44, 15 and 84 runs).

## 9. Correctness

- Stage 1: sequential output identical across three runs and header checks passed (section 5).
- Stage 2: 42 of 42 runs verified, 0 failing checks (`stage2_gate.json`).
- Stage 3 collection: 42 of 42 collection runs completed and verified against the instance reference (RESEARCH_STATUS Stage 3 report); pilot 18 of 18 verified, `n_failing_checks` 0 (`pilot_gate.json`). The dataset manifest records a SHA-256 for every source log.
- Stage 4 pilot: `S4/gate_sessions_main.json` (44 runs), `gate_sessions_regimeR.json` (15 runs): `n_failing_checks` 0; all runs `completed` true and `output_verified` true, 0 dependency violations, 0 worker overlaps, 0 ineligible placements (counts re-summed here). GPU pilot `runs.csv`: 84 runs, status ok, `output_ok` and `log_ok` true; tolerances are those of the GPU spike (`img_edges` max abs 1 and fraction 0.001, `img_features` relative 1e-9, `img_denoise` exact). Main-session outputs are byte-identical to each instance's sequential reference.
- **Confirmatory sessions:** `S5/gate_sessions_main.json` (108 runs), `gate_sessions_regimeR.json` (48), `gate_gpu_sessions.json` (168), `gate_remote.json` (84): `n_failing_checks` 0 in all four; every run `completed` true and `output_verified` true, 0 dependency violations, 0 worker overlaps, 0 ineligible placements (counts re-summed here, 408 of 408). In the `runs.csv` of each analysis every run has status ok, `output_ok` true, `log_ok` true and `included_primary` true (computed here). The slow-window runs are verified like all others.
- Failure-injection tests (non-zero exit, hang with process-tree kill, missing output, dead worker, unmapped task, early-binding queue) pass in the suite (ARCHITECTURE_DECISIONS AD-3).
- Test suite: `S5/full_suite_before_confirmatory.txt` records **384 passed, 1 skipped** (file time 2026-10-13 12:19 +0530, before the first confirmatory session started at 12:19:56 +0530) and `S5/full_suite_final.txt` records **392 passed, 1 skipped** (2026-10-14 05:15 +0530, after all confirmatory sessions and analyses). The suite status at the exact source hash of each session is not recorded (the GPU session and the other three have different source hashes, section 8.1); the pilot-era full run was 377 passed, 1 skipped (`S4/full_suite_final.txt`).
- Train/serve parity and leakage tests (`tests/test_parity_leakage.py`, 10 tests) are inside the 377.

## 10. Overhead

- **Decision time** (confirmatory main session, `S5/analysis_main/summary.csv`, pooled mean per run and per decision; it includes estimator inference, which the log cannot separate; `not_measured_note` in `analysis.json`):

| Policy | Per decision | Per run (59 tasks) | Share of makespan |
|---|---|---|---|
| B0 P-only | 15 µs | 0.0009 s | 0.0003% |
| B4 greedy | 24 µs | 0.0014 s | 0.0003% |
| HEFT, PEFT | 52 µs | 0.0031 s | 0.001% |
| EFT_E1, E1_rank, E3, E1_rc | 352 µs to 429 µs | 0.021 s to 0.025 s | 0.007% to 0.008% |
| EFT_Ridge | 0.98 ms | 0.058 s | 0.02% |
| EFT_MLP | 2.06 ms | 0.12 s | 0.04% |
| EFT_CatBoost | 27.9 ms | 1.65 s | 0.54% (0.56% in the post-hoc set: 1.54 s of 276.3 s) |

  Shares computed here from `summary.csv` (all-blocks geometric means; for the three slow-window-inflated policies the post-hoc makespan is the fair denominator). In the scarce-P session CatBoost costs 1.17 s per run (19.8 ms per decision), 0.24% of its makespan. In the short image-pipeline runs the decision time is a visible share: EFT_E1 with the GPU spends 0.030 s of 7.13 s (0.42%), EFT_E1 in the remote session 0.021 s of 2.22 s (0.96%) (computed here from the GPU and remote `summary.csv`).
- **Queue wait, task time.** Reported in `summary.csv` per run as sums over tasks (not wall time). Main session, post-hoc set (`S5/analysis_main_posthoc_excl_blocks_5_6/summary.csv`, computed here): queue wait 453 s of task-seconds per run for B0 P-only, 799 s for `B0_P_early` (early binding queues tasks on workers, section 8.2), 446 s to 459 s for the EFT, HEFT and PEFT policies and 0.57 s for B4 (B4 binds only to idle workers; effect -99.87% in `effects.csv`). The overhead figure `S5/analysis_main/fig_overhead_breakdown.png` shows these components.
- **Transfer and setup:** transfer is "not measured" in the Montage and GPU sessions (local pools share a directory, zero by construction). In the remote session it is measured for the tasks that ran on R: 0.018 s per run for B4 on the fast LAN link and 0.695 s per run for B4 on the slow WAN link (`S5/analysis_remote/summary.csv`, `transfer_total_s_mean`; EFT placed nothing on R, so its transfer is "not measured"). Setup/staging is not reported as a separate component (ARCHITECTURE_DECISIONS AD-8). **Utilisation** (busy seconds of a worker divided by run makespan from `task_completed` intervals, EVALUATION_PROTOCOL 13.2) is in `summary.csv`: main session 0.349 to 0.355 for P-only, `B0_P_early` and the EFT policies, 0.409 for B4; scarce-P 0.203 (P-only), 0.825 (B4), 0.521 to 0.523 (EFT_E1, Ridge, MLP), 0.320 (CatBoost); GPU session 0.108 to 0.172. Peak memory of the run is not recorded; predictor memory and latency are in section 7.2.
- **Does the gain survive once decision cost is counted?** There is no gain to carry through: makespan is end-to-end and already contains decision time, and the predictive policies are slower than P-only in the main session even before decision time is subtracted (EFT_E1's decision time is 0.02 s of a 3.6 s deficit, post-hoc set). The most expensive predictor, CatBoost, adds 1.5 s per run, about 0.55% of makespan.
- Overhead per run in Stage 2 beyond the makespan (about 2.3 s, derived by the v1 collection plan from 15,314 s for 42 runs) is a planning figure and was not recomputed.

## 11. GPU workload [real, separate workload] and emulated remote pool [emulation]

### 11.1 GPU workload [real]

Workload: the 68-task image pipeline stage structure (1 source, 16 tiles, 16 denoise, 16 edges, 16 features, aggregate, mosaic, package) at tile 1024 px with 16 branches, with CUDA variants for `img_denoise`, `img_edges` and `img_features`, one CUDA worker (`gpu_stage_table`: all three true), RTX 3050 6 GB Laptop GPU. Montage has no GPU path; no claim is made about Montage on GPU.

**GPU kernel evidence** (`stage1_20261011/gpu/spike_20261012T092018/gpu_spike.json`, script sha256 `09f88cc0...`, copies included in the GPU time, one thread, machine not idle): at 1024 px `img_edges` 13.96x (CPU 33.9 ms, GPU 2.43 ms), `img_features` 4.87x, `img_denoise` 1.03x (radius 2.0, 1 iteration; 1.15x with 8 iterations); all bit-exact or inside the stated tolerances (`max_abs` 0.0). At 512 px `img_denoise` with 1 iteration is below 1 (0.88x to 0.91x, verdict DROPPED; 1.02x with 8 iterations), so it is not GPU evidence below 1024 px; at 1024 px it is allowed and marginal. Profile used by the scheduler at tile 1024 (`gpu/profile_t1024/20261013T025309_profile.json`, median of 5): per branch on a P core `img_denoise` 24.7 ms, `img_edges` 35.5 ms, `img_features` 9.7 ms; on the GPU 23.8 ms, 2.6 ms, 2.2 ms. The CPU-only stages dominate: `img_source` 5.63 s on a P core (14.40 s on E) and `img_package` 0.67 s on P (1.60 s on E), so about 6.3 s of a makespan of about 7.1 s is CPU-only work that no placement can move to the GPU (computed here from the profile and `summary.csv`). The GPU stages are milliseconds.

**Confirmatory session** `S5/gpu_sessions/20261013T121953` (design `stage5_gpu_confirm`, pre-registered in EVALUATION_PROTOCOL 13 before it started): 24 blocks x 7 conditions = 168 runs, all complete and verified, 6 P + 7 E + 1 CUDA G worker, tile 1024, 16 branches, reference EFT_E1_cpu. Makespan geometric mean pooled with 95% interval (`S5/analysis_gpu/summary.csv`); effect against EFT_E1_cpu from `S5/analysis_gpu/effects.csv` (pre-registered family of 6 contrasts, smallest Holm step 0.0083, significant if p_holm < 0.05); the last two columns are the exploratory second reference B0 P-only from `S5/analysis_gpu_vs_P/effects.csv`.

| Condition | Makespan (s) | Effect vs EFT_E1_cpu (95% CI) | p_holm | Effect vs B0 P-only (95% CI), exploratory | p_holm |
|---|---|---|---|---|---|
| EFT_E1_cpu (same policy, GPU removed) | 7.281 (7.230 to 7.339) | reference | | +1.48% (+0.81 to +2.17) | 0.0021 |
| **EFT_E1_gpu** | 7.128 (7.095 to 7.166) | **-2.10%** (-2.93 to -1.35) | 0.0006 | **-0.65%** (-1.82 to +0.34) | 0.27 |
| B0_P_only (CPU only) | 7.175 (7.117 to 7.252) | -1.46% (-2.14 to -0.79) | 0.0012 | reference | |
| HEFT_E1_gpu | 7.351 (7.302 to 7.403) | +0.96% (+0.25 to +1.70) | 0.040 | +2.45% (+1.69 to +3.18) | 0.0006 |
| B4_gpu (priority G, P, E) | 7.389 (7.322 to 7.468) | +1.48% (+0.36 to +2.59) | 0.040 | +2.98% (+1.47 to +4.48) | 0.0021 |
| B4_cpu | 7.430 (7.405 to 7.457) | +2.04% (+1.23 to +2.73) | 0.0012 | +3.55% (+2.46 to +4.34) | 0.0006 |
| random_gpu | 11.40 (9.73 to 13.29) | +56.57% (+33.63 to +83.04) | 0.0006 | +58.88% (+35.77 to +85.63) | 0.0006 |

- **P4, supported.** EFT_E1 with the GPU is 2.10% faster than the same policy without it (p_holm 0.0006), in 20 of 24 blocks (computed here), inside the pre-stated 1% to 3%. In seconds: 0.153 s (7.281 s to 7.128 s, computed here).
- **Against the greedy GPU-aware baseline:** EFT_E1_gpu against B4_gpu is **-3.53%** (computed here from the block-wise log ratios of `S5/analysis_gpu/runs.csv`: 22 of 24 blocks faster; a simple unstratified percentile bootstrap, 10,000 resamples, seed 0, gives -4.57% to -2.52%; this is not the project's analysis script, and the point estimate equals the difference of the two stored effects, +1.48% and -2.10%). B4_gpu against B4_cpu is -0.55% (computed here from the two stored effects, +1.48% and +2.04%; no interval; the pilot had -0.46% with an interval that included zero).
- **Against the strongest simple baseline (claim (a)):** EFT_E1_gpu against B0 P-only is -0.65% (-1.82 to +0.34), p_holm 0.27: not distinguishable. B0 P-only is faster than EFT_E1 without the GPU by 1.46% (p_holm 0.0012). So the GPU brings the predictive policy to the level of P-only and not below it; predictive placement is better than every other GPU-aware non-predictive baseline (B4_gpu, HEFT_E1_gpu) but not better than the strongest one (P-only).
- **Scale.** Absolute makespans are 7.1 s to 7.4 s; about 6.3 s of 7.1 s is CPU-only work (`img_source`, `img_package`) that no placement can move to the GPU, so the whole spread between the non-random policies is 0.30 s (7.128 s to 7.430 s, computed here). Decision time of EFT_E1_gpu is 0.030 s per run (0.42%).
- Figures: `S5/analysis_gpu/fig_makespan_by_policy.png`, `fig_effect_vs_baseline.png`, `fig_overhead_breakdown.png` (`S5/figures/gpu_analysis/` holds the re-drawn pilot figures, not these).

**Pilot session** (first round, kept as pilot and not pooled with the confirmatory session; paths under `S4`) `gpu/sessions/20261013T025636`: 12 blocks x 7 conditions = 84 runs, all complete and verified, reference B0 P-only. Makespan geometric mean pooled, 95% interval (`gpu/analysis/summary.csv`), and paired effects (`gpu/analysis/effects.csv`, 12 blocks; p_holm from the stored table, which is attainable with 12 blocks):

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

### 11.2 Emulated remote pool [emulation]

**What is emulated** (EVALUATION_PROTOCOL section 14): one real node process on a core of this machine (core 19, `remote_node_core` in `S5/remote/remote_profile.json`) behind a loopback link shim with a configured latency, bandwidth and per-message cost and no jitter. No real network, no foreign clock, no ARM host, no authentication beyond the tested handshake. Links (`S5/designs/remote/design_remote.json`): `fast_lan` 0.2 ms, 1000 Mbit/s, 0.05 ms per message; `slow_wan` 30 ms, 20 Mbit/s, 0.1 ms per message. Workload: the image pipeline at tile 512, 16 branches, 68 tasks; remote-eligible stages `img_denoise`, `img_edges`, `img_features`; pools 2 P + 6 E + 1 R (worker events, computed here). All results of this session are labelled **emulation** and never pooled with real-hardware sessions.

**Calibration** (`S5/remote/remote_profile.json`, raw `remote_profile_raw.csv`; loopback socket of this machine with the shim at zero, not a network measurement): transfer time = **0.779 ms + 1.617 ns per byte** (n = 60, median absolute residual 0.084 ms; calibration tiles 64, 128, 256, 512). The profile check stored in the design (modelled round-trip transfer over R kernel time) is 0.59 to 0.83 on the fast LAN and 25.8 to 35.2 on the slow WAN (`img_features` 25.8, `img_edges` 26.2, `img_denoise` 35.2), so transfer is a visible share of a task on both links.

**Session** `S5/remote_sessions/remote_confirm` (design `remote_emulation_confirm`, hash `4dab0106...3d49`): 12 blocks x 7 conditions = 84 runs, all complete and verified, reference EFT_E1_no_remote (family of 6 contrasts, smallest Holm step 0.0083, smallest attainable p 0.00049). Effects from `S5/analysis_remote/effects.csv`; the last two columns are the exploratory second reference B4_no_remote (`S5/analysis_remote_vs_B4/effects.csv`, where D1 is stated). Tasks on R summed over the 12 blocks from `gate_remote.json`.

| Condition | Makespan (s) | Tasks on R | Effect vs EFT_E1_no_remote (95% CI) | p_holm | Effect vs B4_no_remote (95% CI) | p_holm |
|---|---|---|---|---|---|---|
| B0_P_only | 2.077 (2.056 to 2.098) | 0 | -6.40% (-7.44 to -5.49) | 0.0035 | -6.75% (-7.68 to -5.83) | 0.0035 |
| B4_no_remote | 2.227 (2.211 to 2.244) | 0 | +0.37% (-0.86 to +1.46) | 1 | reference | |
| B4_remote_fast_lan | 2.250 (2.232 to 2.270) | 12 | +1.42% (+0.24 to +2.47) | 0.14 | +1.05% (+0.006 to +2.27) | 0.41 |
| **B4_remote_slow_wan** | 2.910 (2.887 to 2.939) | 12 | **+31.18%** (+29.90 to +32.60) | 0.0024 | **+30.69%** (+29.42 to +32.02) | 0.0024 |
| EFT_E1_no_remote | 2.219 (2.203 to 2.235) | 0 | reference | | -0.37% (-1.46 to +0.89) | 1 |
| EFT_E1_remote_fast_lan | 2.222 (2.203 to 2.240) | 0 | +0.14% (-1.10 to +1.19) | 1 | -0.23% (-1.24 to +0.81) | 1 |
| EFT_E1_remote_slow_wan | 2.226 (2.207 to 2.245) | 0 | +0.32% (-0.85 to +1.55) | 1 | -0.05% (-1.21 to +1.18) | 1 |

- **D1, supported.** On the WAN link B4 with R is 30.69% slower than B4 without R (p_holm 0.0024; slower in 12 of 12 blocks, by 0.62 s to 0.77 s, computed here). B4 placed exactly one task on R in every block on both links (12 in total per link); the measured transfer per B4 run is 0.695 s on the WAN link (`summary.csv`, `transfer_total_s_mean`) against a median makespan penalty of 0.685 s (computed here), so the penalty is of the size of the transfer time. On the fast LAN link B4 with R is +1.05% (+0.006 to +2.27), not significant.
- **D2, not supported.** The transfer-aware EFT placed **0 tasks on R on both links** (`gate_remote.json`), so there is no difference between WAN and LAN placement to observe: EFT never used the remote pool, including on the fast LAN.
- **D3.** EFT_E1 with R on the fast LAN is +0.14% (-1.10 to +1.19) against no remote: not distinguishable, as expected when nothing is placed on R.
- **Plain reading.** The emulated remote pool (one E core behind a link) gave no benefit to either policy: greedy B4 was hurt on the slow link, and the transfer-aware EFT avoided the harm by not using R. In this pipeline B0 P-only is the fastest policy (6.40% faster than EFT_E1 without remote, p_holm 0.0035), so claim (a) is not supported here either. No statement about real networks follows.
- Figures: `S5/analysis_remote/fig_makespan_by_policy.png`, `fig_effect_vs_baseline.png`, `fig_overhead_breakdown.png`.

## 12. Limitations and scope

The open items (what could not be done or checked) are the five items of section 14.3. The items below are properties of the design and the workload, each supported by a named file; they scope the claims.

1. **Patched Windows Montage build and a patched generator copy.** The native build needed twelve workarounds and the generator has three edits; the difference from the upstream Linux behaviour is not quantified.
2. **The machine was not idle.** The load was measured for the confirmatory sessions (section 3); timing noise, including the slow window of the main session (section 8.2), is part of the results.
3. **One dominant task type, a pool speed ratio of 3.59, and two 59-task instances in the main session.** A trivial rule (use only P cores) is optimal with at least three P workers, so the null was expected by construction (EVALUATION_PROTOCOL 12.6). The workload cannot show where prediction helps.
4. **Resolution of the confirmatory sessions.** Achieved 80%-power minimum detectable effects (`effects.csv`, `mde_pct_80power`): main 0.89% to 1.28% for `B0_P_early` and the six stable variants; scarce-P 0.38% (MLP) to 1.47% (EFT_E1); GPU 0.99% to 1.60% (random 25.7%); remote 1.56% to 1.78%. This is why equivalence of EFT_E1 and B4 at +-0.5% is not resolved (its minimum detectable effect is 1.47%).
5. **The GPU workload is dominated by CPU stages** (about 6.3 s of 7.1 s); absolute gains are fractions of a second.
6. **Few learning rows and one dominant task type for the predictors:** 2,706 fitting rows, 20% on E, all from one sky region; the learned models are worse than the static profile on the 19-task fold; median APE is dominated by sub-second tasks; the learned models' error grows from the early to the late runs of a session (section 7.3). TabM is excluded by the entry rule.
7. **Labels exist only for executed placements.** Counterfactual pools are covered by the E1 base profile plus the log correction and by random placement during collection. The regret table's oracle is a replay stand-in (section 7.4).
8. **Instances share a sky centre.** The final-test instance is a larger instance of a region also used in training.
9. **Different code states.** Stage 2, Stage 3 and Stage 4 sessions ran from three different `src_sha256` values; the GPU confirmatory session differs from the other three confirmatory sessions; the git dirty flag is true in every session; sessions are not pooled in any scheduling analysis, but the Stage 3 dataset pools Stage 2 and Stage 3 sessions.
10. **Reduced collection design (v2)** and an unreferenced `stage3_20261012/designs_v3/` directory whose role is not documented in the project documents.
11. **Thresholds** of the evaluation protocol were provisional until the pilot; changes after the freeze are dated amendments (STAGE3_FREEZE A1 to A3).
12. **First-run and failed attempts are kept** (Stage 1 runs A to C and `rep1` to `rep3`, the Stage 2 smoke session with the cleanup-before-reverify bug, the empty first dataset build). They are excluded from every gate by rule and documented; they are in the raw data.
13. **EFT_E3 and EFT_E1_rc adapt online and place a varying number of non-`mProject` tasks on E cores** (0 to 30 and 0 to 16 per run in the main session, `gate_sessions_main.json`); the nine `mProject` tasks stayed on P in the runs checked for the slow window.

## 13. Reproducibility

- Raw immutable logs, configurations, hashes and manifests: `data/results/stage1_20261011/`, `stage2_20261012/`, `stage3_20261012/`, `stage4_20261012/` (pilot) and `stage5_20261013/` (confirmatory). Pilot evidence manifest `S4/SHA256_MANIFEST.tsv` (366 entries; covers the three pilot sessions, the analyses `analysis_main`, `analysis_regimeR`, `gpu/analysis`, `gpu/analysis_ref_EFT_E1_cpu` and `gpu/analysis_ref_B4_cpu`, the designs and the GPU profile; it does not list `gpu/analysis_ref_B4_gpu`, computed here). **Confirmatory evidence has one SHA-256 manifest per session** (`S5/sessions_main/20261013T132115/SHA256_MANIFEST.tsv` 222 lines, `sessions_regimeR/20261013T224600/` 102, `gpu_sessions/20261013T121953/` 342, `remote_sessions/remote_confirm/` 174, line counts computed here, header included); **no stage-level manifest for `S5` (analyses, load log, designs, figures, extra analyses) has been written**. Stage 0 SHA-256 manifest of `data/` and the Git exclusion record are in commit `7651eca`; `data/` is not in Git, so Git alone cannot reproduce any timing.
- Code version of each session: pilot `src_sha256` `5650bc0ab775...` (all three), Stage 3 `e6c902ff9863...`, Stage 2 `a8e349763604...`; confirmatory `95a74ba36708` (main, scarce-P, remote) and `d6e480bcfa67` (GPU) from `analysis.json`. The two hashes differ only because a new file, `src/caosched/experiment/remote_adapter.py` (with its scripts and tests), was added between the end of the GPU session start (12:19 local) and the start of the main session (13:21 local); `find` over `src`, `scripts` and `tests` by modification time shows no other source change in that interval, and the new file is not on the code path of the Montage or GPU runs. Git HEAD `13d1649` (main, scarce-P, GPU) and `868eeea` (remote), dirty flag true everywhere. Sessions with different code, machine, environment or design hash are never pooled (`analyze_experiment.py`).
- Analysis from raw logs: `python scripts/analyze_experiment.py --sessions <session dir> --out <dir> --reference <condition> --seed 0 [--posthoc-exclude-blocks 5 6]`. Outputs: `runs.csv`, `exclusions.csv`, `summary.csv`, `effects.csv`, `crosscheck.csv`, `analysis.json`, three figures. Commands for the whole confirmatory chain are in [REPRODUCE.md](REPRODUCE.md) section 14.
- **Reproduction from raw logs.** Pilot: `scripts/reproduce_subset.py`, `stage4_repro/repro_analysis_main.json`, `repro_analysis_regimeR.json`, `repro_gpu.json`: all four checks pass in each and `ok` is true. **Confirmatory:** `data/results/stage5_repro/repro_analysis_main.json`, `repro_analysis_regimeR.json`, `repro_analysis_gpu.json`, `repro_analysis_remote.json` (2026-10-13 23:42 UTC): four checks each (session SHA-256 manifest with 0 missing, 0 changed, 0 extra; event-log hashes against run manifests; `summary` and `effects` tables re-derived from the raw logs and matched), `ok` true in all four. The post-hoc, `gpu_vs_P`, `remote_vs_B4` and `analysis_extra` outputs were not covered by `reproduce_subset.py`. Hash check of the Stage 0 data (`stage4_repro/historical_data_verify.json`, pilot era): 12,627 files checked, 0 missing, 0 changed; `ok` is false only because 15,275 files that did not exist at Stage 0 were present then.
- Clean-checkout run of a small subset (`scripts/reproduce_clean_checkout.py`): Observed 2026-10-12 22:19-22:21 UTC (`data/results/stage4_repro/repro_clean_checkout_log.json`): all 18 steps exit 0 (about 2 minutes); data/ is not in Git, so Montage and its timings are not re-run; the stub adapter is synthetic (label plan); only a 4-file pytest subset ran; CUDA tests and the GPU spike are not covered. It was not repeated for the confirmatory state. The clean checkout cannot rerun Montage or reproduce any timing.
- Test suites: section 9. Background load: `S5/load/load_20261013T121952.jsonl` (section 3). Machine hygiene checklist: [REPRODUCE.md](REPRODUCE.md) section 11. Its sections 12 and 14 hold the observed logs.
- Commit that contains this report: see `git log` on branch `redesign/montage`.

## 14. Decisions, checklist and open items

Decisions made by the assistant under the project owner's delegation (the owner may overrule; then a new freeze and new session are needed): [STAGE3_FREEZE.md](STAGE3_FREEZE.md) (instance roles, candidates, TabM out, margin 2.0%, splits, dated amendments A1 to A3); [STAGE3_COLLECTION_PLAN.md](STAGE3_COLLECTION_PLAN.md) v2 (reduced design); [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) sections 12 (pilot pre-registration), 13 and 14 (confirmatory pre-registrations); the scarce-P regime and the GPU workload design; the post-hoc sensitivity analysis of the slow window (declared post-hoc).

### 14.1 Completion checklist (only items with evidence)

- [x] Stage 1: workload runs, three identical sequential outputs, DAG extracted with no manual edits (`stage1_gate.json`).
- [x] Stage 2: 14 policies x 3 blocks = 42 runs, all verified, 0 failing checks (`stage2_gate.json`).
- [x] Stage 3: dataset manifest with hashes and exclusions (`dataset/20261012T195206/manifest.json`); six predictors evaluated on held-out rows with accuracy, latency, memory (`eval/*/metrics.json`); `d1.5` evaluated once; scheduling pilot 18 of 18 verified; selection by the frozen rule: EFT_E1 (`selection_record.json`).
- [x] Pilot (Stage 4, first round): main 44, scarce-P 15, GPU 84 runs verified, 0 failing checks (`S4/gate_*.json`, `S4/analysis_*`); pre-registration committed before the first block (`4b66dcc` 21:24:39 +0530; first run 21:24:51 +0530).
- [x] Confirmatory pre-registrations committed before the first block of each session: EVALUATION_PROTOCOL section 13 (`13d1649`, 12:19:40 +0530; first run 12:19:56 +0530) and section 14 (`868eeea`, 04:52:28 +0530; first run 04:52:40 +0530 on 2026-10-14).
- [x] Confirmatory sessions: main 108 of 108, scarce-P 48 of 48, GPU 168 of 168, remote [emulation] 84 of 84 runs complete and verified, 0 failing checks, 0 excluded (`S5/gate_*.json`, `S5/analysis_*`).
- [x] Pre-stated predictions P1 to P4 and D1 to D3 evaluated with the stated wording (section 8.3); post-hoc sensitivity analysis declared as post-hoc (`S5/analysis_main_posthoc_excl_blocks_5_6/`).
- [x] Background load measured for all confirmatory sessions (`S5/load/load_20261013T121952.jsonl`, 1,928 samples).
- [x] Drift check, learning curve and regret table run (`S5/analysis_extra/`, sections 7.3 and 7.4).
- [x] Figures fixed (zoom panels, correct axis labels, caption no longer overlapping) and three diagrams produced (`S5/figures/montage_dag`, `system_architecture`, `predictor_ladder_flow`, SVG and PNG); presentation outline filled ([PRESENTATION_OUTLINE.md](PRESENTATION_OUTLINE.md)).
- [x] Early-binding mechanism tested as a controlled contrast (P1); Holm flaw resolved by the confirmatory sessions; GPU session pre-registered before it ran.
- [x] Patent claims read verbatim (0 occurrences of machine-learning or prediction vocabulary in claims 1 to 20); HEFT and PEFT originals read and reproduced exactly by `tests/test_heft_peft_papers.py`; DSS terms read and acknowledgement text included (section 15); licences read from the files ([LICENCES.md](LICENCES.md)).
- [x] Tables re-derived from raw logs and event-log hashes checked for the four confirmatory analyses (`data/results/stage5_repro/repro_analysis_*.json`, all `ok`) and for the three pilot analyses (`stage4_repro/repro_*.json`).
- [x] Full suite: 392 passed, 1 skipped (`S5/full_suite_final.txt`).
- [x] Clean-checkout reproduction of the code path (pilot era, `stage4_repro/repro_clean_checkout_log.json`, 18 of 18 steps); historical evidence preserved (12,627 Stage 0 data files, 0 missing, 0 changed, `stage4_repro/historical_data_verify.json`); no tracked data or test file was modified or deleted by the experiments. Final run at commit `ebc68fb` (`data/results/stage5_repro/repro_clean_checkout_final.json`): 19 of 19 steps, fresh venv from the lock file with the pinned CUDA torch, the whole test suite (390 passed; 3 skipped, the three dashboard tests that read the historical event logs which the Stage 0 record keeps out of Git; all 393 pass on this machine), stub experiment, analysis, manifest build/verify, table re-derivation, and the Montage binaries and four instances hash-checked read-only.
- Not complete: the five open items of section 14.3 (facts about hardware and publisher access, not tasks). Done at the end: stage-level SHA-256 manifests for stage 1 to 5 (`data/results/stage*/SHA256_MANIFEST.tsv`), the exact chain scripts that ran every session stored in `scripts/chains/`, and a clean-checkout run at the final state (`data/results/stage5_repro/repro_clean_checkout_final.json`).

### 14.2 Decisions needed from the owner

1. **Further conditions.** Whether to test any condition where prediction might matter (for example other P worker counts, a workload with several heavy task types or a smaller pool ratio). None is analysed here.
2. **Raspberry Pi 5.** Go or no-go for the later extension (ARM Montage build, real network, foreign clock, authentication).
3. **Licence of the project and data rights.** The project has no licence file (the choice is the owner's); redistribution of the DSS images or figures derived from them is not addressed by the STScI pages read (SOURCES_VERBATIM section 6.2: ask the holder before publishing the raw FITS), so whether the mosaic image may appear in slides is the owner's decision.
4. **Archiving and Git.** `data/` is excluded from Git and the clean checkout cannot reproduce timings; decide where the evidence directories are archived, and whether the evidence directories are published (they are committed here except the multi-gigabyte work directories and the Montage tree).
5. **Paywalled sources (optional).** Supply the PDFs listed in SOURCES_VERBATIM section 7 if a later text should cite beyond the abstracts.
6. **Presentation details.** Title wording, author, date and institution (PRESENTATION_OUTLINE slide 1).
7. **Complexity order** (E1 < E3 < E1+rc < Ridge < CatBoost < MLP versus measured latency and size): leave as frozen (the selection is unaffected) or write a dated amendment.

### 14.3 Genuinely remaining

1. **Raspberry Pi 5, real network, foreign clock, ARM.** Requires hardware that is not available on this machine and is excluded by the project specification as a later extension; no edge claim is made.
2. **Full texts behind publisher paywalls or bot checks were not accessible** and are listed with every attempt in [SOURCES_VERBATIM.md](SOURCES_VERBATIM.md) section 7: the IEEE-typeset PEFT article, the LACHESIS, Cao and Song full texts, the Liu FGCS full text and the Wang accepted manuscript. None of them is a claim the results depend on.
3. **The project has no licence file of its own** (the owner's choice, section 15.2).
4. **The remote pool is emulated** (loopback, no jitter).
5. **One machine, patched Windows Montage build.**

## 15. Third-party licences and data acknowledgement

### 15.1 DSS image data: acknowledgement text

The input images are DSS2 blue plates (survey POSSII-J, plate A1ET, copyright card `Caltech/Palomar`) fetched from `archive.stsci.edu`. STScI asks users to include the following acknowledgement in publications as appropriate; the text is copied verbatim from the MAST mission-acknowledgements page (SOURCES_VERBATIM.md section 6.4, Source A, https://archive.stsci.edu/publishing/mission-acknowledgements, read 2026-10-13):

> The Digitized Sky Survey was produced at the Space Telescope Science Institute under U.S. Government grant NAG W–2166. The images of these surveys are based on photographic data obtained using the Oschin Schmidt Telescope on Palomar Mountain and the UK Schmidt Telescope. The plates were processed into the present compressed digital form with the permission of these institutions.
>
> The Second Palomar Observatory Sky Survey (POSS-II) was made by the California Institute of Technology with funds from the National Science Foundation, NASA, the National Geographic Society, the Sloan Foundation, the Samuel Oschin Foundation, and the Eastman Kodak Corporation. The Oschin Schmidt Telescope is operated by the California Institute of Technology and Palomar Observatory.

For these files the first paragraph and the POSS-II paragraph apply; the UK Schmidt sentence refers to southern plates. Terms as read on the same pages: non-profit research and teaching use of the copyrighted collections is free with the acknowledgement requested; commercial, for-profit use needs written permission from the holder (here Caltech, contact on the STScI page); the pages state no rule on redistributing copies of the image files, so the raw FITS stay out of public repositories. Not legal advice.

### 15.2 Licences of the components

Read from the licence files themselves and recorded with paths in [LICENCES.md](LICENCES.md) (not legal advice). Montage: BSD 3-clause (`LICENSE`, Caltech 2014) plus bundled libraries under their own files (bzip2, CFITSIO, zlib, WCSsubs LGPL 2.1, LodePNG, IJG libjpeg, FreeType offered under FTL or GPLv2 with the choice for our binaries not verified, libpng); the workflow generator `montage-workflow-v3`: Apache-2.0; the Python packages: their `dist-info` licence files (torch BSD-3-Clause, numpy, pandas, scipy, matplotlib, astropy and others); the MinGW-w64 runtime: the notice file in the kit. None of the third-party binaries, sources or data is committed to Git (`data/montage/` and `.venv/` are ignored); only our own patch scripts, helper sources and a 22-line diff of the Apache-2.0 generator are committed.

**Components for which no licence file was found** (a fact about the files, `LICENCES.md` section 5): the project itself (`caosched`, no `LICENSE` at the repository root; the licence is the owner's choice); Montage `lib/src/svc`, `boundaries`, `cmd`, `coord`, `json`, `mtbl`, `pixbounds`, `www`, `mcurl`, `test`; `two_plane_v1.1` (copyright line only); the `wcssubs` files `poly.c` and `slasubs.c`; the FreeFont `.ttf` files used by `mViewer`; the DSS2 image data (no terms in any local file; terms read on the MAST pages, section 15.1); the w64devkit components other than the MinGW-w64 runtime (GCC, GNU Make, binutils, busybox-w32, GDB, CMake, Ninja, Vim, Universal Ctags, Ccache, NSIS, aas-sign and the w64devkit scripts); catboost 1.2.10 (METADATA field only: Apache-2.0); Git for Windows `sh` (not searched); the CUDA libraries inside the torch wheel (no licence file read).
