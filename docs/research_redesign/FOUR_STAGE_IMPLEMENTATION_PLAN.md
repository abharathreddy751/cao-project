# Four-stage implementation plan

Status (2026-10-12): **Stage 1 done (gates met); Stage 2 software and measurement gates met, evidence under `data/results/stage2_20261012/` (commit: see git log); Stage 3 not done (predictor and split code exists with unit tests, but no real-workflow data collection, pilot or model selection has been run); Stage 4 not done (experiment tooling and scripts exist; no main experiment has been run).** Original proposal 2026-10-11. Effort: S/M/L are broad classes (small: days; medium: weeks; large: many weeks), not estimates. All thresholds are **provisional** and are set after the pilot of the stage that measures them; no improvement is promised.

Scope: **all stages run on this machine** (CPU cores, RTX 3050 for the separate GPU workload, emulated remote pool). The Raspberry Pi 5 is a later extension (see end).

A stage is not complete because code exists or tests pass. Its software, scientific and measurement gates must all be met and its evidence files must exist.

Contribution carried through all stages: a controlled, overhead-accounted, real-hardware study of how much predictor sophistication improves DAG scheduling (see [PROJECT_SPEC.md](PROJECT_SPEC.md)). Algorithm stack: baselines B4, E-only/round-robin/random, HEFT, PEFT; predictors E1, E3, +rc, Ridge, CatBoost, MLP, TabM only if gated in; proposed instrument = rank priority + predicted, queue-aware, transfer-aware EFT. Excluded: GNN+PPO, GRU/TCN, temporal Transformer, GNN predictor, image embeddings.

## Stage 1 — Research specification and reproducible workload (effort M)

**Objective and questions.** Fix the research question and evaluation protocol; decide the workload; make a small official Montage configuration run reproducibly; check GPU feasibility. Questions answered: Is Montage executable here? Does one small configuration give a stable, verifiable output? Does any CPU/GPU stage pair reach equivalence and a real speed-up?

**Substeps.**
1. Finish the literature gap: obtain the patent PDF (verbatim claims), the HEFT/PEFT originals, the LACHESIS IEEE text, the paywalled papers (Song 2023, Wang 2022, DDDQN-TS and others); extend the search (WorkflowSim, learned-HEFT variants, GPU workflow scheduling, WfCommons Montage recipe).
2. Re-baseline the environment: run the topology tool on this CPU, record RAM, GPU, driver; recreate the virtual environment; pin dependencies; decide how Montage is run (WSL2, Cygwin/MSYS2, container, or native Windows build) — needs approval.
3. Generate a small Montage configuration with the official generator; save the generated workflow files and the input list; hash all inputs; record sizes.
4. Execute the workflow sequentially (one task at a time) three times; verify the mosaic (hash equality or stated tolerance, WCS header sanity).
5. Extract the DAG, commands, input/output files and per-task times from the real run.
6. GPU feasibility: install CUDA-enabled PyTorch if approved; verify one CPU/GPU stage pair for numeric equivalence and speed-up.
7. Freeze the specification and evaluation protocol (these documents) after review.

**Algorithms included.** None implemented; selection rationale frozen.

**Expected changes.** `docs/research_redesign/*`, environment files (`requirements`/lock), new evidence folder `data/results/stage1_<stamp>/`. No scheduler code.

**Prerequisites.** Approval of the Montage environment choice; internet access for input data and the generator.

**Hardware and software.** This laptop; GPU only for step 6.

**Tests.** Hash and tolerance comparison of repeated outputs; DAG count and edge checks against the generator's own file dependencies; CPU/GPU equivalence test on a fixed input.

**Experimental protocol.** Sequential runs, 3 repetitions, timing recorded per task; machine otherwise idle; environment manifest written before the runs.

**Quantitative gates (provisional).** 3 of 3 runs complete; outputs equal within a pre-stated tolerance; DAG extracted with no manual edits; per-task wall times recorded for every task; one GPU pair equivalent within the stated tolerance with a measured speed-up greater than 1 (threshold set from the measurement, otherwise the stage is not GPU evidence).

**Evidence files.** Environment manifest; generated workflow files and input list with SHA-256; three raw run logs; mosaic hashes; GPU equivalence and timing log; literature-source table with inspected levels.

**Completion criteria.** Gates met; documents agree and are reviewed; decisions in RESEARCH_STATUS answered.

**Risks and fallbacks.** Montage does not build or run on Windows → use WSL2 or a container (approval needed). Input data unavailable or large → smaller configuration; as a labelled fallback use WfInstances traces as **[replay]**, never as application execution. GPU pair fails equivalence or shows no speed-up → option 2 (another workflow) or drop GPU claims and state so.

**Result 2026-10-12 (gates met; details and sources in [RESEARCH_STATUS.md](RESEARCH_STATUS.md), Stage 1 report).** Substeps: (1) literature gap **partly done**: patent verbatim claims and the HEFT/PEFT originals were not reachable, gaps are listed in `LITERATURE_UPDATE.md` and `RESEARCH_STATUS.md`, not closed. (2) environment re-baseline **done** (Python 3.11 venv, `requirements-lock.txt`; Montage route decided and built, see below). (3) one official Montage configuration generated and its inputs hashed **done** (instance `d1.1_dss2b_c56.7_24.0`, 59 jobs; URLs, sizes and SHA-256 in `data/montage/instances/.../instance.json`, referenced by `REPRODUCE.md`). (4) three sequential runs **done**: `data/results/stage1_20261011/valid/seq{1,2,3}/run.json`, 59 tasks each, 1459.4 / 1467.1 / 1469.3 s, `1-mosaic.fits`, `1-mosaic_area.fits`, `1-mosaic.png` byte-identical (`valid/stage1_gate.json`). (5) DAG extraction **done**: 59 jobs, 147 edges from `jobDependencies` equal to the 147 from file relations, 0 disagreements. (6) GPU feasibility **done** with the committed script `scripts/gpu_spike.py`, rerun `data/results/stage1_20261011/gpu/spike_20261012T092018/gpu_spike.json` (first run `gpu/gpu_spike.json` kept as history): `img_edges` and `img_features` pass (bit-exact, speed-up with host-device copies counted) from 512 px; `img_denoise` is bit-exact at every radius tested but its speed-up is only 1.03-1.09x at 1024-2048 px and below 1 at 512 px, so it is marginal. (7) freeze of the specification: documents written and cross-checked; a recorded owner sign-off was not found in the files read.
Deviations: **native Windows build** with MinGW-w64 (w64devkit 2.10.0, GCC 16.2.0) was used instead of WSL2/container; no admin rights needed; many workarounds, all listed in `MONTAGE_WINDOWS_BUILD.md`. Failed or invalid attempts are **kept as evidence and excluded from every gate**: `seq_run1` (wrong `mDiffFit` variant), `seq_runA/B/C` (PATH for the `svc`-spawned tools), first `rep1-3` (runner misread a tolerated message; partly concurrent), an unpinned set killed after `mProject` ran about 2x slower, `debug_resume1..3` (label debug; found the `mImgtbl` option-order and `mViewer` stack bugs). The machine was not idle during the timed runs (WSL VM, browser, editor; power plan Balanced), so the times are indicative; the profile used by the estimators was measured separately in Stage 2. No scheduling, model or Montage-GPU result is claimed by Stage 1.

## Stage 2 — Research-grade runtime and heterogeneous execution (effort L)

**Objective and questions.** Integrate the verified workflow through an explicit adapter and make heterogeneous execution correct. Questions answered: Does the real workflow run under every policy with output equal to the Stage 1 reference? Does the GPU worker give verified equal output?

**Substeps.**
1. Workflow adapter from the generated workflow files to the internal DAG.
2. External-command task: argv, declared inputs and outputs, resources, timeout, exit status; process-tree kill on timeout.
3. File staging and hashing; file sizes available to the transfer model.
4. Failure semantics: per-task status, dependents marked not run, reruns from clean directories.
5. Capability model and hardware-agnostic pool configuration (removes the hard-coded pool names and core IDs).
6. Uniform eligibility for all policies; device selection at dispatch; build-time CPU/GPU validation.
7. CUDA worker process for the separate GPU workload, with CPU reference verification.
8. Loop hardening: check timeout and dead workers on every iteration. Remote node frame caps and dashboard token (needed only before any real remote host).
9. Re-profile all pools on this machine; record the environment per run.

**Expected modules.** `core/task.py`, `core/dag.py`, `core/coordinator.py`, `core/worker_pool.py`, `core/runtime_config.py`, `schedulers/simple.py`, `schedulers/eft.py`, `estimators/base.py`, `apps/` (stages and image pipeline), `remote/`, `dashboard/`, a new workflow-adapter module, tests. Documentation: update ARCHITECTURE.md.

**Prerequisites.** Stage 1 gates met.

**Tests.** Unit: adapter round trip, task status, eligibility helper. Integration: every policy runs the Montage DAG and the restricted image DAG; injected failure, hang and missing-output cases; mixed-pool run. Correctness: Montage output equals the Stage 1 reference within tolerance; GPU output equals CPU within tolerance.

**Experimental protocol.** Each policy runs the DAG at least 3 times in randomised order; run manifests include policy, seed and environment hashes.

**Quantitative gates (provisional).** 100% of policy-by-run combinations complete or fail with a defined status; zero output mismatches; zero ineligible placements; injected-failure suite passes; GPU speed-up measured and reported with copies included.

**Evidence files.** Test logs; run logs; output hash table; GPU equivalence report; per-pool profiles with environment manifests.

**Completion criteria.** Gates met; old behaviour for the 68-task pipeline and previous tests unchanged (regression run).

**Risks and fallbacks.** Montage executables need many small files and short tasks, so runtime overhead may dominate; measure overhead early and report it. If the generator output cannot be adapted without edits, adapt from the trace format and label it **[replay]**. If GPU stages cannot meet equivalence, remove GPU claims.

**Result 2026-10-12 (software and measurement gates met; commit: see git log).** Substeps 1-7 **done** in code: workflow adapter `workflow/adapter.py`, external-command task `core/extcmd.py` (process-tree kill on timeout, output size and SHA-256 recorded), failure semantics (per-task terminal status incl. `not_run`), capability model in `core/runtime_config.py`, uniform eligibility `core/eligibility.py` + `scheduler_base.eligible_workers`, dispatch-time device choice, CUDA pool kind (`experiment/gpu_adapter.py`). Substep 8 **partly done**: dead-worker, task-timeout and run-timeout checks on every loop iteration are done; remote-node frame caps and the dashboard token (AD-12) are **not done**. Substep 9 **partly done**: pools re-profiled for the Montage task types only (`data/results/stage2_20261012/profile_montage/`, one task at a time, pinned to one logical processor of the pool): `mProject` median 111.8 s on a P-core versus 401.1 s on an E-core (n=4 each), the other task types take seconds; the kernel workloads and the 68-task pipeline were not re-profiled here.
Measured (`data/results/stage2_20261012/stage2_gate.json`, produced from the raw logs by `scripts/stage2_gate.py`; session `data/results/stage2_20261012/sessions/20261012T101305`, design sha256 `6f753ecc2f9d1ebaaab1d5e2afa8aab840b05c60805638b43e3586f8c2617887`): 14 policies x 3 interleaved seeded blocks = **42 runs of the frozen Montage instance, all 42 completed, output byte-identical to the Stage 1 reference in all 42**, 0 dependency violations, 0 worker overlaps, 0 ineligible placements, 0 failing checks. Descriptive makespan means of 3 (s): B0 P-only 270.9, B2 static-P 269.6, EFT E3 273.3, HEFT E1 274.5, EFT E1 rank 274.7, PEFT E1 275.0, EFT E1+rc 275.4, EFT E1 275.5; B4 greedy 410.5, B3 410.7, B5 413.4, random 416.5, B1 420.4; B0 E-only 811.8. Policies that never use E-cores or that know the pool speeds are near 270-276 s; those that put 9-30 tasks on E-cores are near 410-420 s. **Honest reading:** the simplest static baseline (B0 P-only, no prediction) equals the predictive and plan-based policies within about 1-2%, so on this instance prediction gives no measurable advantage over the strongest non-predictive baseline; it does beat the greedy patent-mapped baseline B4 by about a third. This is a pilot-type descriptive table: no confidence intervals were computed, one instance, one machine, and it is **not the Stage 4 result**.
Other gates: injected-failure suite (non-zero exit, hang with tree kill, missing output, dead worker, unmapped task, early-binding queue) passes in `tests/test_extcmd.py`, `tests/test_runtime_hardening.py`, `tests/test_eligibility.py`; full suite 366 passed, 1 skipped, mypy `src/caosched` 0 issues (`data/results/stage1_20261011/tests/full_suite_after_mypy.txt`, `mypy_raw.txt`); three independent read-only code reviews found two blocking bugs per area, all fixed. GPU: output equals CPU for the three tested stages (bit-exact) with copies counted (Stage 1 spike table); the GPU workload adapter exists and a CUDA pool run at tile 64 was verified within tolerance in `tests/test_gpu_adapter.py`.
Deviations: (a) runs executed as 3 blocks, each block running all 14 policies once in seeded random order (interleaved, as the protocol requires; "at least 3 times" is met). (b) The adapter option `cleanup_work` deletes the roughly 2 GB work directory of a run only after its outputs were verified against the reference; hashes and event logs are kept. (c) A smoke session `sessions_smoke` is exploratory; it exposed a cleanup-before-reverify bug that was fixed before the matrix. (d) The Montage runs use CPU pools P and E only: **no per-pool CUDA scheduling experiment on Montage** (none exists), and **no GPU scheduling experiment at realistic tile sizes has been run**. (e) The machine was not idle (WSL VM, browser, editor). (f) HEFT/PEFT implemented from secondary-source definitions (originals unreachable); the patent claim text is unverified; the remote pool was not exercised on Montage (emulation only in earlier work).

## Stage 3 — Advanced prediction and scheduling (effort L)

**Objective and questions.** Implement the selected predictors and schedulers on decision-time-safe data and compare them. Questions: how much prediction sophistication changes scheduling decisions and makespan after overhead? Do models generalise to unseen instances and sizes?

**Substeps.**
1. Data collection on the real workflow and the GPU workload: multiple instances and sizes, with online decision context logged.
2. Feature and split policy: decision-time features only; splits by instance, size and session; calibration from earlier profiles only.
3. Predictors: E1, E3, +rc, Ridge, CatBoost, MLP; TabM only if the entry rule in EVALUATION_PROTOCOL.md is met. Measure inference latency, memory and model size.
4. Schedulers: B4, E-only/round-robin/random, HEFT, PEFT, and the instrument (rank priority + predicted queue-aware, transfer-aware EFT with recalibration).
5. Offline evaluation (accuracy, calibration, generalisation) and decision-level regret from logs.
6. Pilot scheduling runs to set repeat counts and provisional thresholds.

**Algorithms.** As listed. Excluded: GNN+PPO, GRU/TCN, temporal Transformer, GNN predictor, image embeddings.

**Expected modules.** `estimators/`, `dataset/`, `analysis/`, `schedulers/`, scripts, tests.

**Prerequisites.** Stage 2 gates met.

**Tests.** Train/serve parity; leakage test; profile-binding; HEFT and PEFT on hand-built DAGs with known answers; estimator interface tests; regression of existing estimators.

**Experimental protocol.** Interleaved seeded blocks, one run of each condition per block; leave-instance-out evaluation; predictor and scheduler timing measured separately.

**Quantitative gates (provisional).** Parity and leakage tests pass; every candidate has accuracy, latency and memory reported; evaluation includes at least one instance or size withheld from training; final predictor chosen by the rule fixed before the pilot, with the evidence recorded.

**Evidence files.** Dataset manifest with hashes and exclusions; prediction CSVs; decision logs; pilot summary; model selection record.

**Completion criteria.** Gates met; the final configuration is frozen before Stage 4.

**Risks and fallbacks.** Too few Montage tasks for neural models → state it and keep ridge/CatBoost. Models do not beat E3/+rc → report honestly; the hypothesis allows it. Data from one configuration only → report limited generalisation.

## Stage 4 — Final evaluation and research submission (effort M–L)

**Objective and questions.** Run the planned experiments and answer the research question with confidence intervals; deliver the package.

**Substeps.**
1. Pilot-derived design: repeat counts, conditions, block order, exclusion rules, written before the main run.
2. Main experiments (Montage and the GPU workload) with output verification for every run.
3. Analysis: makespan, task and queue times, transfer and setup, scheduling/inference overhead, utilisation, memory, correctness; paired bootstrap intervals and change relative to the strongest applicable baseline; variability reported.
4. Plots, tables, limitations.
5. Dashboard-based demonstration; reproduction instructions tested from a clean checkout.
6. Final report and presentation; archive of configurations, raw immutable logs, hashes and manifests.

**Tests and checks.** Reproduce one result from raw logs with the analysis scripts; re-run hashes; clean-checkout run of a small subset.

**Quantitative gates (provisional).** All planned blocks complete; each excluded run listed with a reason; every reported number traces to an evidence file; correctness checks passed on all included runs; the confidence interval method matches the protocol.

**Evidence files.** Experiment manifest; raw logs; analysis outputs; figures; checksums; reproduction log.

**Completion criteria.** Gates met; claims limited to what the evidence labels support.

**Risks and fallbacks.** Time drift or memory pressure interrupts sessions (seen earlier at 0.79 GiB free) → memory preflight; report incomplete designs honestly instead of pooling. Hardware change mid-study → no pooling across machines.

## After the four stages: Raspberry Pi 5 extension (not part of the completion gates)

Plan only: ARM64 Linux, four cores, no CUDA. Needs the remote node on the Pi, a real network instead of the shim, a foreign-clock handling check, an ARM Montage build, node authentication, link calibration, and ARM numeric-tolerance output checks. Until it is executed, no claim about real edge offloading is made.

## Final project-completion checklist

- [x] Stage 1 gates and evidence files complete (2026-10-12; commit `6c94a89`; literature gaps listed, not closed).
- [x] Stage 2 gates and evidence files complete (2026-10-12; evidence `data/results/stage2_20261012/`; commit: see git log).
- [ ] Stage 3 gates and evidence files complete (not done: no real-workflow data collection, pilot or model selection).
- [ ] Stage 4 gates and evidence files complete (not done: no main experiment, no confidence intervals).
- [x] E4 base-profile fix committed (commit `4df01e0`) and covered by tests (full suite 366 passed, 1 skipped, 2026-10-12).
- [ ] Every result labelled real, replay, emulation, simulation or plan.
- [ ] Limitations and unverified items documented; no novelty claim beyond what the literature check supports.
- [ ] Old 68-task pipeline and historical evidence preserved.
- [ ] Reproduction from a clean checkout demonstrated.
