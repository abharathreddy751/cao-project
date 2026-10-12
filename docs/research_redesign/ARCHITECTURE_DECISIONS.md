# Architecture decisions

Status: **proposal for approval**, 2026-10-11. See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the evidence labels. "Verified limit" means observed in code during the earlier audit (`PROGRESS.md`, code read of 2026-10-11) unless marked **[unverified]**.

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
- Cost and risk: large; the generator's output format and the executables' exact command lines are **[unverified]** until Stage 1 generates a real instance.
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
- Existing and limit: a device parameter is merged into every task of a stage type and the stage code switches on that parameter alone, so a CUDA-flagged stage stays eligible for CPU pools (audit D1). The GPU path has never executed [real: no].
- Recommended: device selection is a property of the chosen pool; build-time validation that no CUDA-only variant is eligible for a pool without CUDA.
- Test: mixed-pool run completes; CPU/GPU outputs agree within a stated tolerance; the GPU variant is faster by a measured factor, otherwise the stage is not used as GPU evidence.

### AD-7 Decision-time features and train/serve parity (C1, Minimum)
- Existing and limit: queued tasks are estimated with the new task's context; `target_busy_frac` uses information from after the decision in 46,229 early-binding rows of the earlier dataset; calibration lookup can use a later profile (audit D4, dataset audit); E4 was served on a different base profile than it was fitted on (D2, fix uncommitted).
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

Environment blockers on this machine: no CUDA toolkit, no `torch`, no C compiler, no WSL (checked 2026-10-11).

## Migration and deprecation policy for the 68-task pipeline

It is no longer the primary target. Source, tests and `data/` evidence stay unchanged. It may serve as the secondary GPU-capable workload. It is marked deprecated as a primary workload only after Montage (or the approved alternative) is integrated and validated against its Stage 2 gate. Nothing is deleted or moved in this phase.

## Risks and unresolved design questions

- Whether Montage runs on Windows natively, under Cygwin/MSYS2, or needs WSL2 or a container (the earlier brief forbade WSL/Docker as core dependencies; this needs approval).
- Exact command lines, file naming and input volumes of a small configuration (unverified).
- Whether the RTX 3050 gives a worthwhile speed-up for the chosen stages once host-device copies are counted (unmeasured).
- Whether the earlier P/E speed ratios transfer to the new CPU (unmeasured; old data is machine-specific history).
- Model-size and sample-count adequacy for CatBoost, MLP and TabM on Montage data (unknown until the pilot).
