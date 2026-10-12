# Architecture decisions

Status: **proposal for approval**, 2026-10-11; implementation status added 2026-10-12 (section "Implementation status (2026-10-12)" at the end). The decision records below are kept as written; statements marked **[superseded 2026-10-12]** no longer hold. See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the evidence labels. "Verified limit" means observed in code during the earlier audit (`PROGRESS.md`, code read of 2026-10-11) unless marked **[unverified]**.

Classes: **C1** mandatory for credible research; **C2** mandatory only for the CPU/GPU or edge claims; **C3** optional enhancement. "Minimum" = needed for the minimum completed project; "Extension" = later.

Scope reminder: everything runs on this machine first; Raspberry Pi 5 is a later extension.

## Current versus recommended architecture

Current: a Windows-native Python runtime. `Task` carries `workload`, `size` and optional `params`; the coordinator dispatches to affinity-pinned worker processes in pools "P", "E" and "R"; schedulers B0–B5 and `EarliestFinishTimeScheduler` pick workers; estimators E0–E5 predict kernel time; JSONL logs feed a dataset builder.

Recommended: keep the coordinator, event log, estimator interface and EFT scheduler. Add (a) a **workflow adapter** that turns an official workflow description into the internal DAG, (b) a generic **external-command task**, (c) a **capability model** for pools, (d) **uniform eligibility** and dispatch-time device choice, (e) **decision-time-safe features**, (f) **published baselines** (HEFT, PEFT), (g) a **CUDA worker** for a separate verified CPU/GPU workload.

## Decision records

### AD-1 Workflow representation and external commands (C1, Minimum)
- Existing and limit: `core/task.py` tasks are benchmark kernels or in-process image stages; files are passed as `<task>.bin` artefacts in `apps/artifacts.py`. No argv, declared input/output files, exit status or per-task resources.
- Recommended: a workflow adapter (Pegasus workflow YAML and/or WfFormat JSON → internal DAG) and an external-command task type with argv, declared input and output files, resource request, timeout and exit status.
- Why: Montage tasks are executables communicating through files; without this the scheduler cannot run the real application.
- Research benefit: the workload becomes a recognised application, not hand-authored kernels.
- Cost and risk: large; the generator's output format and the executables' exact command lines are **[unverified]** until Stage 1 generates a real instance. **[superseded 2026-10-12]** Stage 1 generated and ran a real instance (59 jobs); the adapter reads the Pegasus YAML with no manual edits.
- Test: round-trip a generated workflow to the internal DAG with no manual edits; per-task command, inputs and outputs match the generator's catalogs.
- Alternative rejected: embedding Montage-specific logic in the scheduler; keeps application knowledge out of the scheduling layer.

### AD-2 Files and intermediate artefacts (C1, Minimum)
- Existing and limit: artefact store keyed by task id; sizes known only for the image pipeline.
- Recommended: declared files with path, size and SHA-256; staging per work directory; sizes feed the transfer-cost model.
- Why: dependencies in Montage are files; transfer cost needs file sizes; reproducibility needs hashes.
- Test: re-run from a clean work directory produces identical or tolerance-equal outputs; hashes recorded in the log.

### AD-3 Failure semantics and reruns (C1, Minimum)
- Existing and limit: fail-fast on task error, dead worker, timeout and deadlock (kept). No dependency-failure reporting per task, no external-process kill on timeout [unverified for child processes].
- Recommended: keep fail-fast, no automatic retry; record per-task exit status; kill the process tree on timeout; mark dependents as not run; reruns start from a clean work directory.
- Test: injected non-zero exit, hang and missing output each yield a defined run status and a complete log.

### AD-4 Pool and capability model (C1, Minimum)
- Existing and limit: pool names "P", "E", "R" and core IDs are hard-coded in several modules (worker pool, `EstimateContext`, B5, dataset builder, dashboard); the remote-pool occupancy is not part of the estimator context (audit D7).
- Recommended: pools and their capabilities (CPU, CUDA, memory limit, supported task types) declared once in `RuntimeConfig`; topology detected on this CPU.
- Why: this machine has a different CPU and a GPU; old core IDs do not apply.
- Test: a configuration with an arbitrary pool name runs end to end; context features include all pools.

### AD-5 Eligibility for every policy (C1, Minimum)
- Existing and limit: the coordinator rejects an ineligible choice for every policy, but only B4 and EFT choose among eligible workers; other baselines can raise or deadlock (audit D3).
- Recommended: one helper in the policy base returns eligible workers; all policies use it.
- Test: a parametrised test runs every policy on a DAG with restricted tasks.

### AD-6 Placement at dispatch, not in the DAG (C2 for GPU; Minimum for the GPU workload)
- Existing and limit: a device parameter is merged into every task of a stage type and the stage code switches on that parameter alone, so a CUDA-flagged stage stays eligible for CPU pools (audit D1). The GPU path has never executed [real: no] **[superseded 2026-10-12: CUDA stage variants and a CUDA pool have executed; see the status table]**.
- Recommended: device selection is a property of the chosen pool; build-time validation that no CUDA-only variant is eligible for a pool without CUDA.
- Test: mixed-pool run completes; CPU/GPU outputs agree within a stated tolerance; the GPU variant is faster by a measured factor, otherwise the stage is not used as GPU evidence.

### AD-7 Decision-time features and train/serve parity (C1, Minimum)
- Existing and limit: queued tasks are estimated with the new task's context; `target_busy_frac` uses information from after the decision in 46,229 early-binding rows of the earlier dataset; calibration lookup can use a later profile (audit D4, dataset audit); E4 was served on a different base profile than it was fitted on (D2, fix uncommitted **[superseded 2026-10-12: fix committed as `4df01e0`]**).
- Recommended: log the online decision context; build offline features only from it; calibration only from profiles that predate the session; splits by workflow instance, size and session.
- Test: parity test (offline features equal online features); leakage test (feature values unchanged when post-decision events are removed); profile-binding test (existing).

### AD-8 Prediction target and cost accounting (C1, Minimum)
- Existing and limit: kernel time is the primary target; setup and overhead are an ablation.
- Recommended: predict per-task, per-device kernel time; measure setup/staging, transfer, queue wait and scheduling/prediction overhead as separate recorded components; evaluate accuracy, inference cost and makespan separately.
- Why: the research question is about the net value after overhead.

### AD-9 Baselines (C1, Minimum)
- Required: B4 greedy; E-only, round-robin and random; HEFT; PEFT (CPOP optional); the existing EFT ladder as the predictor ladder.
- HEFT and PEFT are static plan methods (a known computation cost matrix; HEFT assumes no contention, per the secondary sources read). They need a profile-based cost matrix and an online variant is not claimed. The originals were not read in full **[unverified]**; obtain the papers before citing their assumptions or complexity.

### AD-10 Predictor choice (C3 for TabM; C1 for the rest)
Decision table (full reasoning in [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md)):
- Required: E1 profile, E3 history, +rc, Ridge, CatBoost, MLP.
- Conditional: TabM (ICLR 2025, Apache-2.0). Enter only if the pilot dataset is large enough and CatBoost/MLP leave scheduling-relevant error. Its benchmarks cover medium-to-large tabular data and it is slower than MLP and GBDTs.
- Excluded from the minimum project: GRU/TCN, temporal Transformer, GNN predictor, image-pixel embeddings.
- Why not GNN or sequence models: no inspected source shows them beating tabular models for runtime prediction; Montage runtime is size-predictable (da Silva 2015). Graph structure enters through priority ranks.
- Rule fixed before the pilot: choose the cheapest model whose scheduling outcome is not worse than a more complex one within the confidence interval.

### AD-11 Learned scheduling policy (GNN + PPO) (C3, Extension)
- Excluded from the minimum project. The inspected learned schedulers are trained in simulators, need workflow diversity (Montage alone is one family; WfCommons recipe availability **[unverified]**), and report inference at the ten-millisecond scale. Revisit only after Stage 4 if the gap and training environment justify it.

### AD-12 Security and hardening (C2)
- Existing and limit: the remote node has no authentication and trusts frame lengths; the dashboard POST has no Origin or token check.
- Recommended: frame-size caps and a shared-secret handshake before any real remote device (including the Pi 5); token plus Origin check on the dashboard POST.
- Needed for: any claim involving a real remote host. On this machine with loopback only, it is hardening, not a research requirement.

### AD-13 Reproducible environment (C1, Minimum)
- Existing and limit: `.venv` points to a deleted Python; dependencies have lower bounds only; `pyproject.toml` declares none.
- Recommended: pinned dependencies and a lock file; recorded Python, driver, CUDA, Montage and generator versions with hashes in every run manifest.

### AD-14 Evidence labels (C1, Minimum)
- Every result carries one label: real, replay, emulation, simulation or plan. WfInstances traces are replay or simulation, never application execution.

## CPU/GPU and Montage suitability decision

Finding: the Montage toolkit README gave no mention of CUDA or GPU, and a web search found no GPU-accelerated Montage. Evidence level: README read through a fetch tool, search snippets. A negative search is not proof.

Options compared:
1. Montage as the end-to-end CPU workflow plus a **separate real GPU-capable DAG** with a verified CPU reference. **Recommended.**
2. A different established workflow with verified DAG provenance and genuine GPU execution. Fallback if the Stage 1 Montage spike fails its gate. No candidate has been found or verified yet.
3. Montage with selected GPU-accelerated operations. Allowed only as a later extension with an independent correctness reference (for example flux and WCS checks against the CPU `mProject` output); it requires inventing and validating GPU astronomy code.

Why option 1: it keeps a recognised scientific workflow for scheduling evidence and obtains GPU evidence only from a task set with a defensible role and a CPU reference. Arbitrary CUDA kernels are not added to Montage.

How GPU execution evidence is obtained (all **[plan]**): the second DAG reuses stages of the 68-task image pipeline, which has a bit-exact CPU reference, adds PyTorch-CUDA variants for selected compute-heavy stages, and proves (1) numeric equivalence to the CPU stage within a stated tolerance, (2) a measured per-stage speed-up on the RTX 3050 including host-device copies, and (3) scheduler placements logged with device, memory and utilisation. Rodinia (BSD-style licence, 2015 mirror; standalone OpenMP/CUDA kernels, not DAGs) is an optional external cross-check if it builds with the local toolchain.

How the two workloads support the same research question: Montage tests prediction value on real file-dependent workflows across CPU pools; the CPU/GPU DAG tests whether prediction helps when device differences are large and transfer includes host-device copies.

Environment blockers on this machine: no CUDA toolkit, no `torch`, no C compiler, no WSL (checked 2026-10-11). **[superseded 2026-10-12]** CUDA-enabled `torch==2.11.0+cu128` was installed (driver 581.83) and a MinGW-w64 toolchain (w64devkit, GCC 16.2.0) was used for a native Windows Montage build; no WSL or container is used by the project. A WSL VM was seen running during timed sessions (it made the machine non-idle); it is not part of any workflow.

## Migration and deprecation policy for the 68-task pipeline

It is no longer the primary target. Source, tests and `data/` evidence stay unchanged. It may serve as the secondary GPU-capable workload. It is marked deprecated as a primary workload only after Montage (or the approved alternative) is integrated and validated against its Stage 2 gate. Nothing is deleted or moved in this phase.

## Risks and unresolved design questions

- Whether Montage runs on Windows natively, under Cygwin/MSYS2, or needs WSL2 or a container (the earlier brief forbade WSL/Docker as core dependencies; this needs approval). **[answered 2026-10-12]** It runs natively on Windows after a MinGW-w64 build with workarounds (`MONTAGE_WINDOWS_BUILD.md`); three sequential runs gave byte-identical mosaics.
- Exact command lines, file naming and input volumes of a small configuration (unverified). **[answered 2026-10-12]** Recorded in the instance files; 59 jobs, 147 edges.
- Whether the RTX 3050 gives a worthwhile speed-up for the chosen stages once host-device copies are counted (unmeasured). **[answered 2026-10-12]** Measured: `img_edges` and `img_features` pass from 512 px; `img_denoise` is marginal (1.03-1.09x at 1024-2048 px, below 1 at 512 px); `data/results/stage1_20261011/gpu/spike_20261012T092018/gpu_spike.json`.
- Whether the earlier P/E speed ratios transfer to the new CPU (unmeasured; old data is machine-specific history). **[answered for Montage 2026-10-12]** `mProject` median 111.8 s on a P-core versus 401.1 s on an E-core (n=4 each), about 3.6x; other tasks take seconds (`data/results/stage2_20261012/profile_montage/`). Other workloads not re-measured.
- Model-size and sample-count adequacy for CatBoost, MLP and TabM on Montage data (unknown until the pilot).

## Implementation status (2026-10-12)

Status words: **implemented** = code exists and the named test or evidence file exercises it; **partly**; **not done**. "Validated" always names a file. Test counts are from `data/results/stage1_20261011/tests/suite_by_file_20261012T090704.txt`; whole suite 366 passed, 1 skipped, mypy `src/caosched` 0 issues (`full_suite_after_mypy.txt`, `mypy_raw.txt`). Real-run evidence: `data/results/stage2_20261012/` (stage2_gate.json: 42 of 42 runs complete and byte-identical to the Stage 1 reference, 0 dependency violations, 0 worker overlaps, 0 ineligible placements).

| AD | Status | Validated by | Deviation or open point |
|---|---|---|---|
| AD-1 workflow adapter, external-command task | implemented | `tests/test_extcmd.py` (14), `tests/test_montage_adapter.py` (5); real instance: 59 jobs, 147 edges from `jobDependencies` equal to the file relations, 0 disagreements (`stage1_20261011/valid/stage1_gate.json`); 42 real Montage runs | Pegasus YAML only (WfFormat JSON not implemented); jobs are not clustered; Montage specifics live in `experiment/montage_adapter.py`, not in the scheduler layer |
| AD-2 files and artefacts | implemented | output size and SHA-256 recorded per task (`TaskResult.outputs`, `task_completed`); `Task.input_bytes`/`output_bytes`; reruns from an empty work directory (`tests/test_runtime_hardening.py`); run manifests hold output hashes | All jobs share one flat work directory (shared-filesystem style). The file transfer model (`FileTransferModel`) exists, but local pools cost 0 transfer, so it is not exercised by the CPU-only Montage runs. `cleanup_work` deletes the ~2 GB work directory of a verified run (hashes and event logs kept) |
| AD-3 failure semantics | implemented | `tests/test_extcmd.py`, `tests/test_runtime_hardening.py` (10): non-zero exit, hang with process-tree kill, missing output, dead worker, deadlock, early-binding queue; per-task terminal status incl. `not_run` | Fail fast, no retry (as decided). A grandchild process re-parented before the kill is missed (`shortcut:` note in `core/extcmd.py`) |
| AD-4 pool and capability model | implemented for the runtime | `core/runtime_config.py` (`PoolSpec`: kind cpu/cuda/remote, `task_types`, `memory_limit_bytes`), `tests/test_eligibility.py` (32 passed incl. parametrised, arbitrary pool names X1/X2/Q) | Names "P", "E", "R" remain the defaults and label the detected efficiency classes. A repo-wide audit that no other module (dashboard, dataset builder, B5) still hard-codes them was not done |
| AD-5 uniform eligibility | implemented | `scheduler_base.eligible_workers` used by all policies; `NoEligibleWorkerError`; `tests/test_eligibility.py`; 0 ineligible placements in 42 real logs | none |
| AD-6 placement at dispatch / GPU | partly | `core/eligibility.py` build-time validation; device variant chosen from the worker's pool kind; `tests/test_cuda_stages.py` (5), `tests/test_gpu_adapter.py` (4: CUDA pool run at tile 64 within tolerance); CPU-vs-CUDA spike `stage1_20261011/gpu/spike_20261012T092018/gpu_spike.json` | `img_edges` and `img_features` bit-exact with speed-up from 512 px; `img_denoise` bit-exact but speed-up only 1.03-1.09x at 1024-2048 px and below 1 at 512 px. **No GPU scheduling experiment at realistic tile sizes has been run, and none on Montage** (Montage has no GPU path). `scripts/profile_gpu_workload.py` exists; a run of it was not verified here |
| AD-7 decision-time features, parity | implemented in code and tests | `tests/test_parity_leakage.py` (10: offline equals online features, leakage, calibration only from earlier profiles, rows without logged context dropped and counted); E4 base-profile binding fix committed `4df01e0` with tests in `tests/test_estimators.py` and `tests/test_models.py`; leakage-safe splits `dataset/splits.py` | The earlier 46,229-row early-binding dataset was not shown to be rebuilt in decision mode; logs from before the context logging lack decision context and are dropped by that mode |
| AD-8 prediction target, cost accounting | partly | Learned predictors target kernel time only (`estimators/tabular.py`); event logs carry queue wait, `decision_time_s`, `scheduling_time_seconds`; host-device copy time is inside the CUDA stage's kernel time (`experiment/gpu_adapter.py`) | Setup/staging time of Montage tasks and prediction cost were not found reported as separate components from real data in the evidence read (a Stage 3/4 analysis item); host-device copy is not separated |
| AD-9 baselines | implemented | B0 P-only/E-only, B1-B5, random, B4 eligible, HEFT (`schedulers/heft.py`), PEFT (`schedulers/peft.py`), rank-priority EFT (`schedulers/rank_eft.py`); `tests/test_heft_peft.py` (9, hand-built DAGs); all ran in the 42 real runs | HEFT/PEFT written from secondary-source definitions, originals not read **[unverified]**; the rank term's communication cost is averaged over all pools (HEFT-like, not HEFT-exact); CPOP not implemented (optional) |
| AD-10 predictor choice | partly | E1, E3, +rc, Ridge (E4) exist and ran or are tested; CatBoost and MLP in `estimators/tabular.py`; `tests/test_models.py` (19, incl. model selection rule, splits, `evaluate_models.py` end to end); only E1, E3 and E1+rc ran in the real Montage matrix | **No predictor has been trained or evaluated on real Montage data** (Stage 3 not done), so the selection rule has not been applied. TabM deliberately not implemented. Excluded models stay excluded |
| AD-11 learned scheduling policy | not done (excluded by decision) | - | Extension only |
| AD-12 security and hardening | implemented (loopback-tested) | `src/caosched/remote/{protocol,node,proxy}.py`: frame-size caps (`FrameTooLarge` before allocation), nonce/HMAC-SHA256 mutual handshake with a shared token (>=32 bytes required for non-loopback binds), node survives malformed frames; `src/caosched/dashboard/server.py`: per-start token + Host/Origin checks on POST. Tests: `tests/test_remote.py`, `tests/test_dashboard.py` (server endpoints) | Tested on loopback only, never against a real remote host or in a real browser; payloads are not encrypted; the dashboard token only blocks browser CSRF (any local process can read it); the earlier text search claim of 'no cap' was wrong and is corrected |
| AD-13 reproducible environment | partly | `requirements-lock.txt` exists (torch `2.11.0+cu128` is not on PyPI, see REPRODUCE.md); each session writes `environment.json` (machine id, environment hash, packages, git commit and dirty flag, source SHA-256); Montage and generator commits, toolchain hash and executable hashes in `MONTAGE_WINDOWS_BUILD.md` | Clean-checkout reproduction (`scripts/reproduce_clean_checkout.py`) has not been run end to end (REPRODUCE.md marks `[not yet run]`); the Stage 2 session's `environment.json` records `"dirty": true` (uncommitted working tree at run time; the source SHA-256 is recorded); `pyproject.toml` dependency declaration not checked |
| AD-14 evidence labels | implemented in tooling | Design files carry `evidence_label` (Stage 2: `real`); the stub adapter is forced to `plan`; the analysis refuses to pool sessions with different labels, machines or environment hashes (`tests/test_analysis_paired.py::test_refuses_to_pool_across_environments_and_labels`) | Labelling of every prose statement is a Stage 4 review item |

Not an AD, but built: the `experiment/` package (design file, seeded interleaved blocks, runner, evidence manifest, Montage and GPU adapters) and the scripts listed in `ARCHITECTURE.md`. The Stage 4 analysis (`scripts/analyze_experiment.py`, paired bootstrap) is tested on synthetic data only; no Stage 4 result exists.

Migration policy for the 68-task pipeline: unchanged. Its source and tests are still in the tree and its tests pass inside the 366; `data/` historical evidence was not modified by this work (not re-verified file by file). It is **not** yet marked deprecated, because the policy waits for Montage validation, which is met for the CPU workflow; the owner decides.

Reading of the first real result (not a decision): on the Montage instance the strongest non-predictive baseline, B0 P-only (270.9 s mean of 3), is within about 1-2% of the predictive and plan-based policies (EFT E1 275.5, E3 273.3, HEFT 274.5, PEFT 275.0 s) and about a third faster than the greedy B4 (410.5 s). Source: `data/results/stage2_20261012/stage2_gate.json`. Descriptive, no intervals, one instance, one machine; it does not support or refute the prediction-value hypothesis. It does show that the reference baseline for Stage 4 must be chosen from the pilot (B0 P-only or B2 static-P), not assumed to be B4 (the Stage 2 design file `design_stage2_matrix.json` names `B4_greedy_eligible` as `reference`).
