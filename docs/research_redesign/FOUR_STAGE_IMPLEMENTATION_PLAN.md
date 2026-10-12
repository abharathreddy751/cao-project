# Four-stage implementation plan

Status: **proposal; no stage has started.** 2026-10-11. Effort: S/M/L are broad classes (small: days; medium: weeks; large: many weeks), not estimates. All thresholds are **provisional** and are set after the pilot of the stage that measures them; no improvement is promised.

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

- [ ] Stage 1 gates and evidence files complete.
- [ ] Stage 2 gates and evidence files complete.
- [ ] Stage 3 gates and evidence files complete.
- [ ] Stage 4 gates and evidence files complete.
- [ ] E4 base-profile fix committed and covered by tests.
- [ ] Every result labelled real, replay, emulation, simulation or plan.
- [ ] Limitations and unverified items documented; no novelty claim beyond what the literature check supports.
- [ ] Old 68-task pipeline and historical evidence preserved.
- [ ] Reproduction from a clean checkout demonstrated.
