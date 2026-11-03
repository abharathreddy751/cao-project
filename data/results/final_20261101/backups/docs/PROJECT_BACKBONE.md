# CAO project: complete record (backbone file)

Updated 2026-10-25 to cover the WHOLE working history: every request, decision, experiment, result (positive and negative), error, fix and current state. Read it alone to understand and act on the project. Numbers marked (measured) come from experiments with stored raw logs; (estimate) are simulations or bounds. Paths are given only so evidence can be found later.

---
# PART 1. THE PROJECT

## 1.1 What it is
**CAO** = Python package `caosched` in `D:\cao project`: prediction-aware task scheduling for workflows (DAGs). A scheduler decides which worker runs each ready task and in what order. Goal: **lower end-to-end makespan**, not better prediction metrics. Original intention: an AI-assisted heterogeneous offloading framework that observes machine state, estimates each task's time per resource, and dispatches across CPU P/E cores, a GPU when genuinely available, and a remote worker when transfer cost makes offloading worthwhile.

## 1.2 Machine
Windows 11 laptop; 6 P cores (logical ids 0,2,...,10), 7 E cores (13 to 19), coordinator on core 12; 14 physical / 20 logical cores; 15.7 GB RAM; RTX 3050 6 GB Laptop GPU (driver 581.83, torch 2.11+cu128); remote pool = loopback emulation only; Raspberry Pi planned but no hardware. Practical limit: free RAM (a WSL VM holds ~3 GB).

## 1.3 What existed before this work (stages 0 to 5)
DAG runtime (coordinator, ready queue, worker pool with P/E/CUDA/remote workers, event logs); estimators E0 constant, E1 static table keyed (stage,size,pool), E2 analytic, E3 moving history, E4 learned ridge with occupancy context, CatBoost, MLP, E5 replay oracle; policies B0 (P-only static) to B7, B4 = blind greedy (first idle eligible worker), EFT/HEFT/PEFT, rank-EFT; dataset and evaluation code; GPU image pipeline with CUDA variants of 3 stages; remote shim; dashboard; ~393 tests; pre-registered evaluation protocol with paired-block bootstrap and Holm correction.
**Stage 5 confirmatory result (measured): NEGATIVE.** On the Montage astronomy workflow prediction-aware EFT was 1.6% slower than static P-only (285 s), HEFT +1.5%, PEFT +1.7%. Reason: one dominant serial path; every task prefers P cores (P/E ratio 2.3 to 3.6 for all task types), so placement cannot help; early binding alone costs 1.7%. Saved as git tag `baseline-null-result` (`7dd1847`).

---
# PART 2. THE CONVERSATION, IN ORDER (what the user asked, what was done)

1. **Master audit prompt:** read-only, evidence-based audit of the whole folder; single output `PROJECT_MASTER_DOCUMENTATION.md` with a two-member work split and roadmap. Done (111 KB, untracked, in root).
2. **"Why is the project 40 GB? Is it finished for CPU and GPU? Raspberry Pi is next; why is it not beating static scheduling? Is the idea not working?"** Answered: size = scratch/artifact/result folders; CPU path finished, GPU partly, Pi not started; Montage had no headroom so a null result was expected; the idea can work only where task cost is hidden.
3. **Upload everything to Google Drive (5 TB Google One), logged in browser; then "use the Claude built-in browser".** Not possible with the available tools; instead a 15 GB copy was made at `D:\cao_upload_copy` (with `SHA256_COPY.txt`, `README.txt`) for the user to upload; originals kept. User later asked whether disk cleanup was safe and whether work could continue during upload (yes, copy-based; no data deleted).
4. **"Make a plan to make the project work without changing old files (duplicates, so we can roll back)."** Plan: tag `baseline-null-result`, branch `study2/affinity`, new package `src/caosched/study2/`, new protocol file, gate before any run. User chose direction "whatever makes the project beat static scheduling", limited tokens (needs capacity for a QuakeWatch deployment), new pre-registration file. "Not now, just plan", then "explain in very simple layman terms".
5. **"Proceed, do not stop until completion. I am going to sleep, full approval, autopilot."** Led to Study 2 (Part 3), run unattended with safety rules (no deletion, no push, no questions).
6. **"What to do now?" / "No paper writing, first make the project work."** Focus stayed on experiments.
7. **Study material:** an easy-English study file `STUDY_MATERIAL.md`, then `STUDY_MATERIAL_FINAL.md` with an "actions to overcome drawbacks" section (both untracked, root).
8. **Deep analysis request** ("publish, make it work as in the abstract, is ML overhead from multiple models, would R help, what to do?") and **"what happened, what did you do, plan of action in simple words."** Answered with the findings of Part 3.
9. **Disk clean-up question, duplicate for upload, "permanent root-cause fixes, make sure what we claim is implemented, same problems must not recur after adding the Raspberry Pi; keep git aside until the project works."** Led to the permanent fix architecture (rank order + work-conserving, generic model, one-command retrain, guards).
10. **Later runs under autopilot (6 hours + 6 hours)** until the claim was tested honestly; final two-factor result written; user then asked "what to do next" and "where is the file with everything" (answer: master document and Study 2 report).
11. **Revival task (long structured prompt):** audit and checkpoint, build `ResourceStateAwareRankGreedy`, ablations, oracle gate, dynamic-contention workload, fair design, docs. Done (Part 4). Final status: gate failed.
12. **Phase 1 GPU/CPU profiling task:** measure whether CPU/GPU placement is a real opportunity before any new scheduler work. Done (Part 5); verdict no-go.
13. **Status questions** ("how much progress left in scale 100", "finished or in progress?"): answered; finished with limits.
14. **This file** requested twice (first a summary, then this complete version). Weekly usage limit is almost exhausted, so work should stay small.

Standing constraints from the user: keep git history changes aside until the project works (no rewrite, no push, no remote work); no paper writing; Raspberry Pi on hold; do not delete data without a yes; keep old stage files and results intact (additive changes only); be honest, pre-register, report negatives; the charger must be plugged in for sessions; no mid-run questions.

---
# PART 3. STUDY 2 (branch `study2/affinity`, last commit `ceae094`)

## 3.1 Method
New code `src/caosched/study2/` (workload.py, adapter.py, policies.py, model.py, param_model.py); protocol `docs/research_redesign/EVALUATION_PROTOCOL_study2.md` (sections 1 to 32, written before each run, with dated amendments); report `STUDY2_REPORT.md` (Updates 1 to 4); `claims.json` re-read by a test. Blocks of conditions in random order, paired log-ratio bootstrap, Holm correction, evidence manifests, `reproduce_subset.py`. Guards: scheduling cost may not exceed 25% of makespan (run is failed), mains power required (`require_ac_power`), 0.8 GB RAM preflight, ONE worker pool for all conditions (an early pilot was confounded by pool rebuilds with cold workers, fixed by amendment), cached oracle table.

## 3.2 Workloads
- `build_batch`: 64 identical chains source->denoise->edges->features + aggregate (uniform).
- `build_mixed` (256/1024 px mix): dropped.
- `build_iters`: chains differing only in hidden denoise iterations (cost hidden from size-keyed tables).
- `build_classes`: two-factor chains [[count, side, iterations]]; evaluation classes 48x(256 px,2), 12x(256 px,300), 12x(1024 px,3).

## 3.3 Findings in order (measured)
1. **Uniform batch has no headroom:** workers ~95% utilised; replay-oracle EFT only ~2% faster than greedy.
2. **Old EFT lost ~6% to a hand rule** because of early binding (tasks committed to busy queues), not prediction error. Hand rules: `B4_param_first` (sort by repeats), `B4_cost_first` (pixels x repeats), `B4_largest_first` (size).
3. **Failed ideas:** late-binding EFT (runaway from logging cost, removed), HEFT (~3% behind), PEFT (~20% behind), bounded hold for a busy fast worker (no gain, 4x decision cost), perfect-knowledge oracle EFT (beaten by hand rule).
4. **Permanent fix = `PredictedRankGreedy`:** order the ready queue by predicted upward rank, place only on an idle eligible worker (work-conserving, late binding), choose the idle worker with the smallest predicted time.
5. **Generic model** (`param_model.py`): per (stage,pool) ridge on numeric task parameters and size plus pairwise products, features chosen from the logs (nothing names a stage); unseen (stage,pool) raises an error. **One-command retraining** (`study2_retrain.py`) for a new pool layout or machine (the Raspberry Pi path).
6. **Hidden-cost confirmatory results:** 6P+7E (30 blocks): learned policy 20.4% faster than B4, 21.9% faster than P-only, 42.9% faster than the blind table predictor, 1.6% behind the hand rule that knows the parameter (equivalence not resolved). 2P+7E retrained by one command (20 blocks): 21.1% faster than B4, 45.1% faster than P-only, 36.6% faster than the table predictor, level with the hand rule (within 0.4%).
7. **No-harm control, uniform batch (30 blocks):** level with B4 (+0.45%), 26.1% faster than P-only, level with the EFT rule (+0.90%).
8. **Two-factor result (pilot 9 blocks, confirmatory 41 blocks, orders order_e/order_f):** vs the learned policy: sort-by-size 17.4% slower, P-only 17.1% slower (both supported); B4 0.9% slower (-0.9% to +2.8%): pilot's 4.4% edge over B4 did not replicate; equivalence to pixels x repeats formula (+1.0%, -1.3 to +3.4) and repeats-only rule (-1.4%, -3.8 to +1.1) not resolved (paired sd 0.08, twice the pilot). Model hold-out: heavy classes within 8% (P 256px x300: 0.605 s predicted vs 0.565 s; 1024px x3: 0.122 vs 0.112), lightest class badly (17.6 ms vs 4.1 ms on P; E predicted ~0 vs 9 ms).
9. Conclusion of Study 2: the claim "learned prediction beats static and naive scheduling" holds (17% to 45%); "beats blind greedy" holds only on hidden-cost workloads; nothing beat the best hand-written rule.

## 3.4 Claims registry (`docs/research_redesign/claims.json`, ~30 claims)
U1-U2, H1-H5, G1-G4, R1-R4, N1-N3 (earlier Study 2 claims, 18); C1-C5 (two-factor: C1 size-only slower supported, C2 P-only slower supported, C3 "at least 2% faster than B4" not supported, C4 and C5 equivalence not resolved); V1-V7 (revival, below). `tests/test_claims.py` re-reads every number from its `effects.csv`.

---
# PART 4. REVIVAL (branch `revival/resource-state-aware`, base `b84e489`)

## 4.1 Preservation and audit
Checkpoint outside the repo: `D:\cao_checkpoint_revival\` (git bundle of all refs, patch of the tracked change, status, log, copies of the three untracked documents). No remote exists. Baseline: 438 tests passed, mypy clean; stored analyses reproduce from raw logs. Audit written to `docs/revival/BASELINE_AUDIT.md`. The "Montage profile test free-RAM guard" in the supplied summary could not be reproduced (the test injects its RAM reader); a different test with the same name pattern does read real RAM (see 6.2).

## 4.2 What was built (all additive, `src/caosched/revival/`)
state snapshot with optional signals (residual correction per worker, per-core foreign load, free RAM, GPU telemetry marked unavailable); cost breakdown (compute, load, setup, transfer); `ResourceStateAwareRankGreedy` (rank order, work-conserving, fallback to B4 with logged reasons `no_model_coverage`, `gain_below_cost`, `decision_budget`; ablation switches); contention harness (spinner processes pinned to cores, same schedule started for every policy); schedule-aware oracle with the same constraints; mixed-DAG workload (72 chains, 6 groups, two-level fan-in, 295 tasks); adapter; power-law runtime model form (`fit_group_log_power`, per-group form chosen on held-out logs); scripts `revival_*.py`; 13 tests. Edits to old files: `study2/adapter.py` (`_build_policy` method), `study2/param_model.py` (new form, old models load unchanged).

## 4.3 Measurements and results
- Calibration (measured): one spinner on a worker's core slows a long task 1.77x, two 2.72x; a task shorter than the OS time slice is not slowed; per-core utilisation sample costs 48 microseconds.
- Model comparison (fit on coverage logs, choose on pilot logs, report on confirmatory logs): denoise median error 3.4 (P) / 1.0 (E) with the additive form vs 0.19 / 0.02 with the power law.
- **Oracle gate: FAILED (measured).** 13 blocks, instances g1/g2: PRED_RANK_GREEDY 2.662 s, B4 2.712, B4_param_first 2.726, ORACLE 2.748, B4_cost_first 2.759, size-first 3.053, P-only 3.105. Headroom of the best simple rule over the oracle: -1.24% (-3.0% to +0.5%); required >= 5%. Contention was real (heavy tasks inside a hot window 0.815 s vs 0.532 s outside) but cost B4 only ~2.5%. No pilot or confirmatory run; nothing tuned.
- **Engineering no-harm check on the uniform batch with the CUDA worker (31 blocks):** v1 revival policies +2.2% to +2.6% slower than B4 (outside +-2%): cause measured, a state snapshot taken after every completion (~100 microseconds on the slow coordinator core); fixed by taking it lazily and skipping computation when only one worker is idle. v2: +0.7% to +1.0% (all intervals inside +-2%), scheduling time ~1% of makespan; PRED_RANK_GREEDY itself +1.3% (-0.2 to +2.7, equivalence not shown). Static P-only +37%. v1 kept and registered as a failed claim.
- Why no headroom: a saturated pool leaves one idle worker so placement is forced (in a demo run 18 of 295 dispatches had a choice, 0 chose differently from B4); contention changes speed less than the E/P gap; the heaviest early tasks are dispatched before any state signal exists.
- Claims V1 to V7 added: V1 oracle gate not supported; V2-V4 revival variants equivalent to B4_gpu within +-2% (v2) supported; V5 P-only >20% slower supported; V6 v1 equivalence not supported; V7 existing policy equivalence not resolved.
- Related work checked: Lotaru (arXiv 2309.06918, FGCS 2024), Carvalho et al. PVLDB 2024 (tutorial), Ilyushkin & Epema CCGrid 2018 (conclusions not read), Lu & Reda arXiv 2607.22242 (closest: LLM agent plus runtime monitor for GPU/CPU choice); a 2026 survey unverified. No novelty is claimed (`docs/revival/RELATED_WORK.md`).
- Tests at that point: 458 passed; mypy clean. Documents: `docs/revival/{BASELINE_AUDIT,PROTOCOL_revival,IMPLEMENTATION_REPORT,FINAL_STATUS,RELATED_WORK,EXPLAINED_SIMPLY}.md`.

---
# PART 5. PHASE 1: CPU/GPU PROFILING AND OPPORTUNITY AUDIT

## 5.1 Method
Protocol `docs/revival/PROTOCOL_gpu_cpu_profile.md` written before the sweep (hypotheses H1-H5, gate G1-G3, stopping rules; amendments A1-A5). Script `scripts/revival_profile_cpu_gpu.py` (subcommands run, overhead, dag, summarize, opportunity, verify) and helpers `src/caosched/revival/gpuprofile.py`. One worker pool (one P, one E, one CUDA worker) for all conditions; per task the complete cost = submit to result received, split into kernel (incl. host/device copies for CUDA), file I/O + decode + encode, IPC in/out, other; GPU contention by a separate pinned process doing continuous 4096x4096 matrix products (ready/pause/stop/timeout/cleanup; guarded `__main__`); telemetry from `nvidia-smi` (NVML not installed, not installed by us); outputs verified (CPU byte-identical, CUDA within existing tolerances).

## 5.2 What actually ran
Smoke run (kept, not used); main sweep attempt 1 stopped after block 0 by the RAM rule; **attempt 2 completed 8 measured repetitions** (4 for 2048 px), 1678 samples, 0 failed, the data used; attempts 3, 3b, 4 stopped by RAM before usable data; monitoring-overhead run completed; DAG-runtime reference attempts (3) stopped by RAM at first preflight (launched with 3.0 GB free, fell to 0.67 GB). The 1.0 GB stopping rule was never lowered. Amendment A4 moved the transfer micro-profile into a child process to save memory. Data: `data/results/revival_gpu_profile_20261025/` (~48 MB, all manifests verify).

## 5.3 Results (measured; median complete cost in ms; quiet GPU -> busy GPU for G)
- `img_edges`: 256 px P 6.2 / G 7.2; 512 px P 13.6, E 29.5, G 9.1 (busy 9.5); 1024 px P 45.0, E 99.1, G 14.8 (busy 18.8); 2048 px P 177, G 125 (n=4, outlier-prone) / busy 53.5.
- `img_features`: 512 px P 6.3, G 7.5; 1024 px P 14.7, G 14.9; 2048 px P 52.4, G 22.2.
- `img_denoise` x8: 512 px P 52.3, E 156, G 63.6 (busy 142); 1024 px P 215, E 694, G 214 (busy 515): best device flips G->P under contention. x60: 512 px P 367, G 462; 1024 px P 1562, G 1157 (busy 3570): flips G->P.
- `img_source` (CPU only) 512 px P 102, E 222.
- Breakdown (quiet): G edges 512 px = kernel+copies 33%, file I/O and codec 51%, IPC 8%; H2D of a 512 px edges input 0.29 ms, whole CUDA function 2.3 ms but G worker occupied 9.1 ms; `write_artifact` ~2.4 to 3.0 ms, read ~0.5, decode ~0.4, encode ~0.1 to 0.3; worker pool startup 9.3 s.
- GPU busy: GPU denoise 2.2x to 3.1x slower; edges barely; P/E large tasks <5% change, small CPU tasks +16% to +32%; P+G overlap efficiency 0.88 to 1.03 for tasks > 50 ms.
- Variability: CV P 4-20%, E 1-15%, G 4-100% (outliers). Monitoring overhead +0.4% median (cells -5% to +10%); nvidia-smi call 0.14 to 0.16 s; max 76 C, 60.5 W under load.
- Hypotheses: H1 true for edges/features; H2 true only for denoise; H3 true above 50 ms tasks; H4 true; H5 true.
- **Choice frequency (stored real runs, late-binding policies):** B4+GPU 20,046 dispatches: 93.6% forced, 6.4% two or more idle, 0.8% with both a GPU and a CPU worker idle; revival policies 5.1% / 0%.
- **Simulation (estimate; coordinator constant 4.9 ms/dispatch fitted on B4_gpu 1.754 s; unfitted check P-only simulated 2.377 vs measured 2.406 s):** 512 px workload: best simple 1.754 s, same-rule oracle 1.753 s (0.05% headroom) quiet; 1.827 vs 1.827 (0%) with GPU busy. 1024 px workload (unvalidated): 1.829 vs 1.829; busy 2.319 vs 2.317; busy GPU costs this workload 27%. Fluid LP bound headroom 26 to 27% (unattainable: ignores precedence and the serial coordinator). 60% of the work is CPU-only `img_source`.
- **Gate:** G1 (flip for a class with >=20% of work): fails at 512 px, holds for 1024 px denoise; G2 (>=20% of dispatches with a GPU and a CPU worker idle): fails everywhere; G3 (>=5% headroom): only the unattainable bound passes. **Verdict: opportunity not established; no GPU-contention pilot.**
- Tests: 14 new profiling tests passed; full suite 471 passed, 1 failed (`tests/test_profile_montage.py::test_profile_format_csv_fit_and_cleanup` refuses to run below 2.0 GB free RAM; passes alone with 3 GB). mypy clean. Report: `docs/revival/GPU_CPU_OPPORTUNITY_REPORT.md`. Latest commits: `d4c53dd`, `673c700`, then this file `fd573e8` and later.

---
# PART 6. ERRORS, DEFECTS AND HOW THEY WERE HANDLED

6.1 Historical (stage 1 to 5, fixed earlier): E4 base-profile mismatch, eligibility inconsistencies, decision-time feature capture, decision-context logging cost.
6.2 During Study 2/revival/Phase 1: pilot confounded by worker-pool rebuilds (one pool for all conditions now); logging and oracle-median cost inflated scheduling (cached oracle, no-context EFT variants, 25% cost guard); a launch ran before its design existed and did nothing (design recreated from files); bash heredoc quoting failures (scripts now written with the file-write tool); an unguarded test script spawned recursive child processes (spawn without `__main__` guard; killed, all burner code guarded); an attempt to delete an empty failed result directory was blocked by the tool's safety policy and was not retried (new directory names used instead); free RAM repeatedly below 1.0 GB ended sweeps early (rule kept); the revival policy's first version cost 2% (state snapshot per completion; fixed).
6.3 Not errors but limits: NVML not installed (no per-decision GPU utilisation/VRAM), remote hardware absent, only 8 profiling repetitions, no measured GPU-contended DAG runs.

---
# PART 7. SCOREBOARD OF CLAIMS

| Claim | Status |
|---|---|
| Prediction-aware scheduling beats static and naive rules | **Supported**: 17% to 45% (several workloads, pre-registered) |
| It beats blind greedy B4 | Only where a hidden task parameter makes ordering decisive (20 to 21%); level or null on uniform, two-factor, contended workloads |
| Matches the best hand rule that knows the hidden parameter | Level on one layout, 1.6% behind on another (unresolved); never better |
| Live resource state improves scheduling | Not shown (oracle gate failed) |
| No harm where nothing is hidden | Supported after one fix (+0.7% to +1.0% of B4) |
| GPU contention is a scheduling opportunity | Not established |
| Raspberry Pi / real remote | Not tested |
| Montage | Valid null result |

Reading: the project produced a mapped result. Scheduling helps when task cost is hidden in parameters and the pool is not already forced into single-choice dispatches; it does not help when one worker is idle at a time, when most work cannot use the accelerator, or when serial dispatch is the bottleneck.

---
# PART 8. HOW THE PROJECT CHANGED DIRECTION

Montage null -> look for workloads with headroom (oracle check first) -> found it in hidden-cost chains -> early policies lost -> root cause (early binding) -> permanent fix (rank + work-conserving + generic model + retraining) -> two-factor and uniform tests show a tie with blind greedy where nothing is hidden -> revival adds live state but its own oracle gate says no headroom -> Phase 1 asks the same of the GPU and says no. Method rule that came out of it: check headroom with an oracle before building a predictor; pre-register; keep negatives.

---
# PART 9. WHERE THINGS ARE
Branches: `study2/affinity` @ `ceae094`; `revival/resource-state-aware` (current, latest commits after `673c700`); tag `baseline-null-result`; pre-revival bundle `D:\cao_checkpoint_revival\repo_ceae094.bundle`; upload copy `D:\cao_upload_copy`. Documents: this file; `PROJECT_MASTER_DOCUMENTATION.md` (audit, untracked), `STUDY_MATERIAL*.md` (untracked), `docs/research_redesign/{EVALUATION_PROTOCOL_study2,STUDY2_REPORT,claims.json}`, `docs/revival/*`, `docs/INDEX.md`. Data: `data/results/study2_20261024/`, `data/results/revival_20261025/`, `data/results/revival_gpu_profile_20261025/`. Code: `src/caosched/{study2,revival}/`, scripts `study2_*.py`, `revival_*.py`. Rollback: `git checkout study2/affinity` or `git checkout baseline-null-result`. Run tests: `.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q` (needs >= 2 GB free RAM for the one guarded test).

# PART 10. NEXT OPTIONS
1. Consolidate and stop (low cost): merge docs, tidy git (deferred by the user), archive scratch data, keep the negative-result story.
2. Write up the established results and the method (medium; user said no paper for now).
3. New workload with real choices (fewer ready tasks than workers, pre-generated inputs so GPU work dominates, longer tasks); screen with the simulator first, run hardware only if simulated oracle headroom >= 5%.
4. Raspberry Pi/real remote (needs hardware; one-command retraining exists).
5. More Phase 1 repetitions/DAG runs (needs ~3 GB free RAM; unlikely to change the verdict).
6. Improve light-class prediction (power-law form exists) inside the two-factor policy (small gain).
Recommended: option 1, then 3 or 4. Do not invest further in live-state or GPU-contention ideas for the current workloads.

# PART 11. CAUTIONS
Keep the charger on and RAM free for sessions; never pool results across code versions; never delete or overwrite `data/results`; treat simulation and LP numbers as estimates; the weekly usage limit of the assistant was nearly exhausted when this file was written, so large new analyses should wait.
