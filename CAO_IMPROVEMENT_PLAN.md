# CAO improvement plan: prioritised technical changes before the static-versus-dynamic benchmark

Status: **investigation only**. No source file changed, no scheduling policy changed, no experiment run, no hybrid built. Existing results and registered experiments are untouched. The only measurements below are read-only aggregates computed from event logs that already existed.

Labels: **[SRC]** read in source (file:line). **[LOG]** aggregate computed from an existing run log, nothing re-run. **[DOC]** from an NVIDIA page fetched earlier (see `NVIDIA_VS_CAO_AUDIT.md`). **[INT]** my interpretation. **[OPEN]** not established.

---

## 1. Findings that shape the plan

### 1.1 The headline result is a CPU-only result

- The registered overnight sessions I opened (`data/results/overnight_20261027/phase3g/sessions/heavy40/...`) have `gpu_pool: false` and `gpu_stages: []` in their run manifests. [LOG]
- Searching `data/results` for `"gpu_pool": true` returned only runs under `data/results/revival_20261025/uniform2_sessions/...` (the search was capped at 8 files, so this is not an exhaustive count). [LOG]
- So the −19% / −20% results against B4 come from P and E cores. The claim "dynamic CPU/GPU scheduling beats B4" is not what those sessions measured. [INT]

### 1.2 What a GPU task's measured time contains

- The CUDA stage functions do their own host-to-device copy, kernel, and device-to-host copy inside the timed call: `.cuda()` at the start and `.cpu()` at the end of `_denoise`, `_edges`, `_features` (`src/caosched/apps/cuda_stages.py:62-66, 75-81, 89-94`; module docstring lines 5-8). `apps/stages.py:178-187` repeats this: "the function does its own host/device copies and synchronisation, so its timing includes them". [SRC]
- `run_stage` times only `compute` (`apps/stages.py:195-202`). The worker records that as `wall_time_seconds`. The artifact read, decode, encode and write are timed separately as `io_s` (`core/worker_pool.py:146-152`). [SRC]
- `ParamModelEstimator` is fitted on `wall_time_seconds` per (workload, pool) group (`study2/param_model.py:99-104`). So its predictions for pool G **already include H2D and D2H**. Adding a separate copy term on top would double count. [SRC + INT]
- The part PRED does not see is `io_s` plus coordinator-worker IPC. `scripts/study2_e2e_terms.py` already derives both from logs: `setup = median((t_completed − t_started) − wall_time_seconds)` (artifact I/O inside the worker) and `overhead = IPC both ways`, per stage and pool, including pool G. [SRC]
- From `data/results/study2_20261024/e2e_terms_pilot2.json` at 512 px (262144 px): setup 3.1 to 6.0 ms on G, 3.7 to 4.65 ms on P, 6.5 to 8.3 ms on E; IPC overhead 1.85 ms on G, 2.72 ms on P, 3.01 ms on E. [LOG]
- Mean kernel time in the two GPU runs I aggregated (`revival_20261025/uniform2_sessions/20261025T092556`, PRED and B4): G 26.7 ms, P 67 ms, E 139 ms. [LOG]
- Put together, the part PRED ignores is about 5 to 8 ms per G task (roughly 20 to 30% of its kernel time), against about 7 ms per P task (about 10%) and about 10 ms per E task (about 7%). The unmodelled share is larger on G than on CPU pools. [INT, approximate: stage mix and sessions differ between the two sources]

### 1.3 PRED's rank and placement use different cost models

- `RankEftScheduler.on_run_start` ranks tasks with `self._exec(t, p, None) + self._extra(t, p)` (`schedulers/rank_eft.py:59`), so it would include e2e terms if they were configured.
- `PredictedRankGreedy.select_worker` places with `self._exec(task, state.pool_of(w), None)` only (`study2/policies.py:135`). It ignores `_extra` and `_transfer`. [SRC]
- `build_study2_policy` builds PRED with no e2e terms and no transfer model (`study2/adapter.py:69-70`). So today the inconsistency is dormant, but any attempt to pass e2e terms would change the rank and not the placement. [SRC]

### 1.4 PRED has no remote path

- `RemoteAdapter._policy` accepts only B4 and `EFT_*` policies and raises `ValueError` for anything else (`experiment/remote_adapter.py:121-124`). PRED is never run through the remote adapter. [SRC]
- Even if it were, `ParamModelEstimator.estimate` raises `KeyError` for any (workload, pool) group it was not trained on (`study2/param_model.py:99-103`), and a remote pool `R` has no group unless a coverage session trained one. [SRC]
- The remote link is emulated (loopback plus a delay shim); the adapter stamps `evidence_label = 'emulation'` (`remote_adapter.py:5-10`, docstring). [SRC]

### 1.5 The single CUDA worker, and what is known about it

- The study-2 CUDA pool is `PoolSpec((0,), "cuda")` (`experiment/gpu_adapter.py:85`): one worker on device 0. [SRC]
- `PoolSpec.slots` for kind "cuda" are device indices and the duplicate-slot check covers only CPU slots (`core/runtime_config.py:69-71`). `PoolSpec((0, 0), "cuda")` would therefore be accepted and would spawn two worker processes, `G0` and `G1`, on the same device (`core/worker_pool.py:250-253, 301-309`). [SRC]
- Two worker processes mean two CUDA contexts. NVIDIA's MPS documentation says kernels from different contexts cannot run concurrently without MPS and are time-sliced. [DOC] Whether MPS can be used on this Windows machine was not checked. [OPEN]
- Concurrency with streams **inside** one worker would need a multithreaded worker loop; the current loop handles one message at a time (`core/worker_pool.py:120-167`). [SRC]
- Observed, two runs only (PRED and B4 with GPU, `b0030_00_..._gpu`, `b0030_04_B4_gpu`): 43 and 44 G tasks, summed G kernel time 1.147 s and 1.163 s over a 1.73 s makespan, so the G worker was busy about **66%** of the run. Mean ready-to-dispatch wait (`queue_wait_seconds = t_dispatched − t_ready`, `core/task.py:121-125`): G 293 ms and 314 ms, P 349 ms and 315 ms, E 302 ms and 324 ms. G tasks did not wait longer than CPU tasks. [LOG]
- Two runs are not enough to say whether G is a bottleneck. [INT]

### 1.6 How availability is represented

- Per worker: `WorkerView` has `busy`, `idle`, `load`, `current_submitted_at`, and a 256-interval busy history (`core/runtime_state.py:35-54`); `RuntimeState.busy_fraction` walks that history (`:95-105`). `eligible_workers(..., idle_only=True)` and `state.idle_workers()` are the only availability signals B4 and PRED read. [SRC]
- GPU utilisation and free VRAM exist only in `revival/state.py` (`GpuTelemetry`, `StateProvider`), through `nvml_gpu_fn()`, which returns `None` when `pynvml` is missing (`revival/state.py:200-213`; docstring says NVML is not installed on this machine). No policy in `src/caosched/revival` reads a `.gpu` field (grep of `revival/` showed `gpu` only in `state.py`, `adapter.py`, `gpuprofile.py`, `workload.py`). `revival/gpuprofile.py` is profiling only: "Nothing here is imported by a scheduler." [SRC]
- Task memory is modelled: `Task.memory_bytes` is checked against `PoolSpec.memory_limit_bytes` in `core/eligibility.py:53`, but no pool in the study-2 or GPU adapters sets a limit. [SRC]

### 1.7 What "static" means in this code, and an accounting gap

- HEFT and PEFT are real static plan schedulers: `StaticPlanScheduler.on_run_start` computes the whole plan once; tasks go to their planned worker with early binding in planned-start order (`schedulers/heft.py:127-168`). The plan is blind to run-time occupancy and late arrivals are not corrected (module docstring `heft.py:25-29`). [SRC]
- A learned-cost static plan already exists: `HEFT_param_model` and `PEFT_param_model` (`study2/adapter.py:61-64`). `plan_factories` builds E1-profile versions (`schedulers/__init__.py:71-75`). [SRC]
- Plan cost is kernel-only: `StaticPlanScheduler._cost` calls `estimator.estimate(task, pool, None)` (`heft.py:141-142`); no e2e or transfer term is passed in the study-2 bindings. [SRC]
- **Accounting gap.** `RunSummary.makespan_seconds` is "first dispatch → last completion" (`core/coordinator.py:114, 419`). `scheduler.on_run_start` runs before the first task is marked ready (`coordinator.py:173-175`), and `_sched_time` counts only `order_ready` and `select_worker` (`:249-263`). So the one-off plan computation of HEFT/PEFT and the rank computation of PRED are in neither the makespan nor the scheduling-time total. [SRC + INT; whether another timer records `on_run_start` was not checked]
- B4's G inclusion is a configuration choice: `GreedyEligibleScheduler` defaults to pool priority P, E only (`schedulers/simple.py:199`), and the GPU runs I looked at set `policy_cfg.B4_greedy_eligible.priority` to start with `G` (`b0030_04_B4_gpu/run_manifest.json`). B4's behaviour on GPU workloads therefore depends on this ordering. [SRC + LOG]

### 1.8 Resolved items from the NVIDIA audit

| Audit item | Result |
|---|---|
| `ParamModelEstimator` internals | Per (workload, pool) group. Features are the numeric task parameters (and `size`) that vary in the training logs, plus pairwise products; fitted by ridge least squares. An optional `log_power` form (`fit_group_log_power`) fits log(time) on log inputs. No silent fallback: unseen group raises `KeyError`. Inference is a dot product (`study2/param_model.py:1-16, 54-67, 70-86, 99-104`). |
| `montage_adapter.build_policy` | Base B4 comes from `policy_factories(...)["B4_greedy_eligible"]` with eligibility and priority from `policy_cfg` (`schedulers/__init__.py:95, 103`); `EFT_*`, `HEFT_E1`, `PEFT_E1`, random and `B0_P_early` are the other branches (`montage_adapter.py:62-87`). |
| `remote_adapter` | Policies B4 and `EFT_*` only; the transfer term is `FileTransferModel` with link calibration read from the profile (`remote_adapter.py:116-134`); PRED unsupported (see 1.4). |
| Whether rank uses transfer | Yes, as the mean of the child's transfer cost over all pools (`rank_eft.py:56-57`); local pools contribute 0 (`remote/link.py:127-130`). |

---

## 2. Priorities at a glance

| ID | Change | Class | Effort | Risk |
|---|---|---|---|---|
| A | Add GPU-enabled workloads to the benchmark (evidence, not code) | **Essential** | medium (runs) | low |
| B | Define and add the static comparators (cost-matched, plus oracle ceiling) and report plan time | **Essential** | small | low |
| C | Cost-consistent PRED placement (e2e and transfer in placement, as a new named variant) | **Essential** | small | low-medium |
| D | Task-level GPU eligibility predicate backed by the verified-equivalence record | Important | small-medium | low-medium |
| E | PRED on the remote pool (adapter, model coverage, transfer in placement) | Important (if remote is in the final claim) | medium | medium |
| F | Availability signals: VRAM guard now, GPU telemetry as logging only | Optional | small | low |
| G | More CUDA concurrency (second worker, MPS, streams) | Optional, measure first | medium-large | medium-high |
| H | Dispatch loop early exit with an always-idle G worker | Optional | small | medium (changes registered timing) |

---

## 3. Per-improvement detail

### A. Put GPU workloads into the benchmark (Essential)

- **Problem.** The registered gain is P/E only (1.1). The objective names CPU and GPU, and the only GPU evidence is a handful of uniform-workload runs where PRED's difference from B4 was not the finding.
- **Relevant files.** `study2/workload.py` (`build_batch`, `build_mixed`, `build_iters`, `build_classes`, the `gpu_stages` argument), `study2/adapter.py:159-165` (`gpu_stage_table`), the existing GPU design `revival_uniform2` (manifest `design.name`), `scripts/gpu_spike.py` (which rows may be True).
- **Change.** Add GPU-enabled conditions (resource set P+E+G) for the heterogeneous families already used (heavy-count and cost-ratio families) to the next registered design, with the same policies and orders. No code change. Use `gpu_stage_table` rows from the spike file only.
- **Overhead.** One more worker process per run; one extra warm CUDA context (known from `b0030`: `worker_ready` count 14).
- **Test.** Output verification already exists per CUDA task (`study2/adapter.py:212-226`: the CPU stage is re-run on the task's own inputs and compared within the spike tolerance).
- **Risk.** Low. Main risk is workloads with no GPU headroom (as with Montage) producing a null; that is a legitimate result and must be reported.

### B. Genuine static comparators (Essential)

- **Problem.** The claim "dynamic beats static" needs a static schedule built from the same information PRED uses, plus an upper bound for what a static plan could achieve. HEFT/PEFT exist, but plan time is outside makespan (1.7) and the plan cost is kernel-only.
- **Files and functions.** `schedulers/heft.py` (`StaticPlanScheduler`, `heft_plan`, `Problem`), `schedulers/peft.py`, `study2/adapter.py:61-64` (`param_model_heft`, `param_model_peft`), `study2/policies.py:57-74` (`CachedOracle`), `core/coordinator.py:173-175, 249-263`.
- **Proposed change.** Four static comparators on identical eligibility and pools:
  - S1 `HEFT_param_model` (exists).
  - S2 `PEFT_param_model` (exists).
  - S3 HEFT with the same cost as improvement C (kernel + e2e), as a new named binding.
  - S4 HEFT with `CachedOracle` costs, an upper bound for a static plan, labelled "ceiling, never a real rule" as the oracle binding already is (`adapter.py:44`).
  Add the one-off `on_run_start` wall time as a logged field for every policy, so HEFT's plan time and PRED's rank time are reported next to makespan and scheduling time.
- **Overhead.** Plan cost is about O(n · w) per task placement for n=257 tasks and w=14 workers (insertion search in `earliest_slot`); not measured here. [OPEN]
- **Test.** For each static run: executed placement equals planned placement (the `plan.assign` is logged in `last_decision`, `heft.py:158-165`); compare plan makespan with actual (plan error is itself a result). Unit test that S3 with zero e2e terms equals S1.
- **Risk.** Low. Risk of unfair comparison if plan time is silently excluded; the logged field removes it.

### C. Cost-consistent PRED placement (Essential)

- **Problem.** Section 1.3 and 1.2: rank and placement use different cost models, and the unmodelled non-kernel cost is a larger share on G than on P or E, so G is favoured relative to its true cost when both are idle.
- **Files and functions.** `study2/policies.py:131-142` (`PredictedRankGreedy.select_worker`, line 135), `schedulers/eft.py:87-95` (`_extra`, `_transfer`, `_occupancy`), `study2/adapter.py:52-70` (binding construction), `estimators/e2e.py` (`EndToEndTerms`), `scripts/study2_e2e_terms.py`.
- **Proposed change.** A **new named variant** (for example `PRED_RANK_GREEDY_E2E`) whose placement minimises `_occupancy(task, pool, None)` = transfer + kernel prediction + extra, and which receives e2e terms from a session different from the evaluated one (the script's own rule). The existing `PRED_RANK_GREEDY` stays byte-for-byte as registered. Do **not** add a separate H2D/D2H term (1.2).
- **Overhead.** Three dictionary lookups per candidate per decision. Current decision time in the GPU runs: 16.5 ms summed over 257 tasks for PRED, 8.2 ms for B4 (about 1% and 0.5% of the makespan). [LOG] Expected increase: small; to be measured in the pilot. The existing guard (`max_scheduling_fraction`, 25%, `study2/adapter.py:197`) stays.
- **Test.** (1) Regression: with all e2e terms set to zero the decisions equal the current variant on recorded states. (2) Unit test: a candidate with larger io but smaller kernel loses to one with smaller total. (3) Registered pilot, paired against current PRED and B4 on the GPU workloads of A.
- **Risk.** Low-medium. Risk of overfitting the e2e terms to the evaluation session; mitigated by session separation. Risk of changing which of P/E/G wins on many tasks: that is the point, and it must be measured.

### D. Task-level GPU eligibility (Important)

- **Problem.** GPU eligibility is a stage-level table: a task may run on G only if its stage is in `gpu_stage_table`/`gpu_stages` (`study2/workload.py:33, 59, 87, 115`). It cannot say "denoise with 8 iterations at 512 px is GPU-safe, 64 iterations at 4096 px is not".
- **Files and functions.** `study2/workload.py` (the four builders), `study2/adapter.py:159-165`, `experiment/gpu_adapter.py:61` (table from `gpu_spike.json`), `core/eligibility.py:22-69` (`supported_kinds`, `resolve_eligibility`), `apps/cuda_stages.py` (`CUDA_STAGES`), `core/worker_pool.py:141-144` (worker-side guard).
- **Proposed change.** Replace `stage in gpu_stages` with a predicate `cuda_ok(stage, params, size)` that is true only if (a) a CUDA variant exists (already `supported_kinds`), (b) equivalence has been verified for the task's parameter region (read from the spike results, not typed), and (c) `Task.memory_bytes` fits a `PoolSpec.memory_limit_bytes` set for the G pool. `resolve_eligibility` keeps raising `EligibilityError` for any explicit pool that cannot run a task.
- **Overhead.** Build time only; no cost at dispatch.
- **Test.** Property test over random parameter draws: no task with an unverified region has G in `eligible_pools`; existing per-task output verification (`adapter.py:220-226`) catches any task that still diverges; unit test that the worker still rejects a stage without a CUDA variant.
- **Risk.** Low-medium. The danger is silently widening the verified region; the predicate must read recorded verification rows.

### E. PRED on the remote pool (Important if remote is in the final claim)

- **Problem.** 1.4: PRED cannot run through the remote adapter; its model has no remote group; its placement ignores transfer.
- **Files and functions.** `experiment/remote_adapter.py:116-134` (`_policy`), `schedulers/rank_eft.py:37-47` (`FileTransferModel`), `remote/link.py:100-133` (`TransferModel`, `payload_bytes`), `study2/policies.py:131-142`, `study2/param_model.py:99-103`, `scripts/study2_train_param_model.py` (retrain, as named in `param_model.py` docstring), `scripts/calibrate_link.py` (link calibration).
- **Proposed change.** Add a PRED binding to the remote adapter that passes the existing `FileTransferModel` into the placement of improvement C. Train a remote group (coverage session through the emulated link). Keep the evidence label `emulation`.
- **Overhead.** One transfer estimate per candidate: `shim_delay` twice plus `payload_bytes` (for `img_*` stages it calls `stage_payload_bytes`; its cost was not measured). [OPEN]
- **Test.** With link set to zero latency and infinite bandwidth the remote pool should behave like a local pool in decisions; with a slow link tasks should stay local. Compare against `EFT_*_rank` with transfer, which already runs there.
- **Risk.** Medium: model coverage for R, and the earlier result that emulated remote EFT showed no gain (+3.78%) suggests the benefit may be small.

### F. Availability, utilisation, memory pressure (Optional)

- **Problem.** Policies see idle or busy only (1.6). Foreign GPU load and VRAM are invisible.
- **Files.** `core/runtime_state.py`, `revival/state.py:200-213` (`nvml_gpu_fn`), `revival/gpuprofile.py:133-190` (`GpuBurner`), `core/eligibility.py:53`.
- **Proposed change.** (1) Set `memory_limit_bytes` on pool G and `memory_bytes` on GPU tasks, so oversized tasks are ineligible rather than failing at run time. (2) Log GPU telemetry in the run log without using it in decisions. (3) Defer decision use until a contention experiment (with the existing `GpuBurner`) shows predictions degrade under foreign GPU load.
- **Overhead.** (1) none at dispatch. (2) `nvidia-smi` sampling is slow ("low-frequency", `gpuprofile.py:3`) and must stay off the task path.
- **Test.** Unit test for the memory guard; contention experiment later.
- **Risk.** Low. Do not add utilisation to scheduling decisions without evidence: in the two runs measured, the only GPU contention is the application's own, which `busy/idle` already captures.

### G. More CUDA concurrency (Optional, measure first)

- **Problem.** One G worker, 66% busy in two runs (1.5). A second worker or streams might raise throughput, or might only time-slice.
- **Files.** `experiment/gpu_adapter.py:85`, `core/runtime_config.py:69-71`, `core/worker_pool.py:86-167, 250-253, 301-309`.
- **Options and cost.**
  - Two worker processes on device 0: configuration-sized change (`PoolSpec((0, 0), "cuda")`). Contexts are time-sliced without MPS [DOC]; per-task kernel time may rise, which invalidates the solo-profile and model groups for G and forces a retrain.
  - MPS: platform support on this Windows machine unchecked. [OPEN]
  - Streams in one worker: needs a threaded worker loop, per-thread stream handling and completion routing; large change.
- **Overhead.** Per extra process: a CUDA context (GPU memory and startup time, unmeasured).
- **Test.** First, read-only: from every GPU-enabled log, G busy fraction, G queue wait, and whether G tasks lie on the critical path. Only if that says G is limiting, a pilot with a 2-worker G pool as a separate registered design, with kernel-time inflation reported.
- **Risk.** Medium-high. Recommendation: do not change yet.

### H. Idle CUDA worker defeats the dispatch-loop early exit (Optional)

- **Problem.** `_dispatch_ready_tasks` returns early only when there are no idle workers (`core/coordinator.py:255-257`). A G worker that stays idle (no G-eligible task ready) keeps the loop scanning every ready task each pass. The earlier overhead study measured this; fixing it shifted the gain by about 0.8 percentage points.
- **Proposed change.** Skip early only when no worker is idle **and eligible** for any ready task. Any such change alters scheduling time in registered experiments, so it must ship as a new amendment with both timings reported, never as a silent edit.
- **Risk.** Medium for comparability, low technically.

---

## 4. Proposed benchmark design (not run)

| Aspect | Specification |
|---|---|
| Resource sets | P+E; P+E+G; P+E+G+R (emulated link, labelled as such) |
| Static comparators | S1 HEFT_param_model, S2 PEFT_param_model, S3 HEFT with e2e cost, S4 oracle-cost HEFT (ceiling) |
| Dynamic baselines | B4 with G-first priority as registered, B4_param_first, PRED_RANK_GREEDY (registered), PRED_RANK_GREEDY_E2E (new) |
| Workloads | the heavy-count and cost-ratio families, GPU-enabled; Montage as a no-headroom control; uniform as an equivalence control |
| Design | interleaved seeded blocks, paired log-ratio of makespan, stratified bootstrap, Holm, ±2% equivalence margin, as in the registered studies |
| Separation | model and e2e terms trained on sessions disjoint from evaluation sessions; selector and thresholds (if a hybrid is built later) pre-registered |
| Reported per run | makespan, scheduling time, `on_run_start` time, plan-versus-actual makespan for static runs, G busy fraction, tasks per pool, output verification |
| Fairness checks | same cold or warm pool in every condition of a session (adapter note A1); identical eligibility; scheduling fraction under the 25% guard |
| Labels | real, emulation, simulation, plan |

---

## 5. Open items and data-hygiene notes

- Condition `policy` fields in manifests are not unique identifiers: the GPU PRED run lists `"policy": "EFT_E1"` while `extra.policy` is `PRED_RANK_GREEDY` and `condition.name` is `PRED_RANK_GREEDY_gpu`. Analyses must group by `condition.name` or `extra.policy`.
- Not read in this investigation: `schedulers/peft.py` beyond its header, `remote/proxy.py`, `remote/node.py`, `study2/workload.py` beyond the grep lines, `scripts/study2_train_param_model.py`.
- Not measured: plan computation time, `payload_bytes` cost for image stages, CUDA context memory and startup, MPS availability on Windows, G busy fraction across all GPU-enabled logs.
- GPU numbers in 1.2 and 1.5 come from two runs of one session; they motivate hypotheses, not conclusions.
- Everything in this document concerns one laptop; Raspberry Pi is out of scope; the remote worker is emulated.

## 6. Preservation rules for the next phase

- New policies get new names; registered policy classes and their bindings stay unchanged.
- New code paths ship with unit tests and a default that reproduces current decisions.
- Every change to timing or accounting (items B, C, H) is recorded as a protocol amendment before any run.
- No result file, manifest or event log is overwritten; each experiment writes to a new directory.
