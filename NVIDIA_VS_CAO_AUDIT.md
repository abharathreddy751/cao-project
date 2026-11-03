# NVIDIA technology audit: how it compares with the CAO framework

Investigation only. No source code changed, no policy changed, no experiment run. Labels used throughout:

- **[DOC]** verified from an NVIDIA or Microsoft page that was fetched in this audit.
- **[SRC]** verified by reading the repository source (file and line given).
- **[INT]** my technical interpretation.
- **[OPEN]** not established from the evidence available; needs an experiment or a primary source.

Support labels for the comparison table: *Supported and verified*, *Partially supported*, *Not supported*, *Not established from available evidence*.

---

## 1. NVIDIA technologies in plain English

### 1.1 NVIDIA Optimus (laptop GPU switching)

- **[DOC]** Optimus "lets applications render on the NVIDIA High Performance GPU while their output appears on monitors connected to the Integrated Graphics." The GPU is chosen **per application, at launch**: "The rendering device for a given application is determined when the application starts." Changing a setting does not affect running instances. Source: [NVIDIA Optimus, archived gameworks page](https://archive.docs.nvidia.com/gameworks/content/technologies/desktop/optimus.htm) (the original `docs.nvidia.com` URL redirects there).
- **[DOC]** Precedence, highest first: Forced Rendering Mode, right-click menu, application profile, static library bindings, global variable `NvOptimusEnablement`, global profile settings.
- **[DOC]** A developer can request the high-performance GPU for an app without a profile by exporting `NvOptimusEnablement` (`0x00000001`). Linking `nvapi.dll`, `nvcuda.dll` or `opencl.dll` also routes an app to the high-performance GPU.
- **Answers to your questions:** whole-application GPU selection, yes. Task-level placement, no: the page says nothing about tasks, transfer costs, dependencies or CPU availability. The developer does not write CPU and GPU paths for Optimus; the app is simply rendered on one GPU or the other.

### 1.2 NVIDIA Control Panel: "Preferred graphics processor"

- **[DOC]** Three values: Integrated, High performance, Auto-select (default Auto-Select:Integrated for new profiles). Per-application profiles can defer to the global setting. Source: [Control Panel help, Preferred graphics processor (Polish-language page in the index; English text not fetched)](https://www.nvidia.com/content/Control-Panel-Help/vLatest/pl-pl/mergedProjects/nv3dPLK/Setting_the_Preferred_Graphics_Processor.htm). The same page series states that Auto-select "automatically selects the appropriate graphics processor to use for the best performance" and that "The driver may override your selection if the program requires a specific graphics processor." Source: [Using Optimus Hybrid](https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-us/mergedProjects/nvcpl/Using_Optimus_Hybrid.htm).
- **[DOC]** Programs that "require the high-performance NVIDIA GPU for CUDA processing or advanced DirectX support" need the NVIDIA GPU; forcing a choice "may cause some programs to not run correctly or may result in shorter battery life."
- **Answers:** application-level GPU selection, yes. Task-level, no. No dynamic movement of arbitrary tasks, no transfer costs, no DAG.

### 1.3 Windows Graphics settings (per-app GPU preference)

- **[DOC, Microsoft DirectX blog, from search snippet]** The Graphics settings page lets the user set GPU preference per application, and that app-specific preference overrides the system-wide setting. Source: [Navigating the Redesigned Graphics Settings page](https://devblogs.microsoft.com/directx/navigating-the-redesigned-graphics-settings-page/). Not fetched in full.
- **[OPEN]** The options ("Let Windows decide", "Power saving", "High performance") are documented only in third-party guides and a Microsoft Q&A forum post. The registry key `HKCU\Software\Microsoft\DirectX\UserGpuPreferences` appears only in unofficial sources. Treat the registry details as unverified.
- **Answers:** application-level GPU selection, yes. Task-level, no.

### 1.4 Advanced Optimus

- **[OPEN]** No NVIDIA primary page was found for "Advanced Optimus" in this audit. Third-party sources (not NVIDIA) describe it as a **hardware MUX switch** that can change automatically between direct dedicated-GPU output and standard Optimus, without a reboot in some models. Sources: [WePC](https://www.wepc.com/gaming-laptop/faq/what-is-advanced-optimus-explained/), [ASUS ROG MUX article](https://rog.asus.com/articles/rog-gaming-laptops/maximize-your-rog-laptops-performance-with-a-mux-switch/). Its job is **display routing**, not scheduling. Nothing in the sources mentions tasks, DAGs or transfer costs.
- **Answers:** display path selection, not compute scheduling. Not a scheduler under any reading.

### 1.5 CUDA streams and asynchronous execution

- **[DOC]** A stream is "a work-queue into which programs can add operations." Operations in one stream run in enqueue order. Different streams may overlap, but "The actual concurrency achieved is dependent on available hardware resources and compute-capabilities." Priorities are hints only: they "does not guarantee a specific order of execution." Source: [CUDA Programming Guide, 2.5 Asynchronous Execution](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/asynchronous-execution.html).
- **[DOC]** Cross-stream ordering is done explicitly with events and `cudaStreamWaitEvent()`. The guide says "an application can specify a full directed acyclic graph (DAG) of operations." The application writes that DAG by hand.
- **[DOC]** The section does **not** describe the runtime choosing between CPU and GPU. Work is placed explicitly by the application.
- **[INT]** CUDA is a GPU-only programming model. It has no CPU execution path for a kernel. The CPU path for any task must be written by the developer. "Does CUDA automatically move a task to the CPU?" is therefore no, by construction. This is an inference from the model, not a quoted sentence.
- **Answers:** GPU execution scheduling within a stream set, yes (DAG expressible but written by the developer). Application DAG scheduling across CPU and GPU, no.

### 1.6 CUDA Graphs and MPS (GPU-side concurrency)

- **[DOC]** CUDA Graphs define a graph of asynchronous operations "up front" and then launch it. The graph runs on the GPU. Source: the same CUDA guide section.
- **[DOC]** MPS: without it, "work launched … from work queues belonging to different CUDA contexts cannot execute concurrently." MPS lets clients' kernels run simultaneously. On Volta and later "Clients submit work straight to the hardware, and the MPS server only arbitrates the remaining shared resources." Source: [MPS architecture](https://docs.nvidia.com/deploy/mps/architecture.html). Pre-Volta MPS: "CUDA graphs with host nodes are not supported under MPS on pre-Volta MPS clients."
- **[OPEN]** How graph launches are scheduled under MPS on Volta and later was not found.
- **Answers:** concurrency among processes sharing one GPU, yes. Cross-device placement, no.

### 1.7 Hardware-accelerated GPU scheduling (Windows, HAGS)

- **[DOC]** "Windows can now offload most of GPU scheduling to a dedicated GPU-based scheduling processor." The GPU handles "quanta management and context switching of various GPU engines." "Windows continues to control prioritization and decide which applications have priority among contexts." Source: [Microsoft DirectX blog, Hardware Accelerated GPU Scheduling](https://devblogs.microsoft.com/directx/hardware-accelerated-gpu-scheduling/).
- **Answers:** this is **GPU-internal context switching**, with priority decided by Windows. It does not decide CPU versus GPU for any task. Not a placement decision.

### 1.8 Summary of the NVIDIA stack

| Technology | Level | Chooses a device? | Per task? | Dynamic? | Dependencies? | Developer writes CPU and GPU paths? |
|---|---|---|---|---|---|---|
| Optimus | whole app, at launch | yes (GPU for app) | no | no (fixed at launch) | no | no |
| Preferred GPU / Auto-select | whole app | yes | no | driver may override | no | no |
| Windows per-app GPU preference | whole app | yes | no | no | no | no |
| Advanced Optimus | display path | no (display routing) | no | yes, display mode | no | no |
| CUDA streams / events | GPU work queue | no (GPU only) | no | runtime orders ready work | developer-written | yes |
| CUDA Graphs | GPU work set | no | no | no | defined up front | yes |
| MPS | processes sharing a GPU | no | no | concurrency | no | no |
| HAGS | GPU context switching | no | no | yes | no | no |

---

## 2. What NVIDIA schedules and at which level

- **Device selection:** whole application, decided at launch (Optimus, Preferred GPU, Windows per-app preference).
- **Kernel-level execution:** inside the GPU, by the hardware and driver (streams, HAGS, MPS). The developer chooses which kernels go in which stream.
- **Never:** placement of an arbitrary CPU-or-GPU task inside an application's DAG. The CUDA guide states the application specifies the DAG, and nothing in the NVIDIA pages reviewed moves tasks between devices.

**Caveat on coverage:** I did not find an NVIDIA page that says "NVIDIA never does per-task CPU/GPU placement." The claim rests on the pages above, which describe the mechanisms and say nothing about such placement. Treat it as "not supported by any NVIDIA mechanism reviewed," not as a proof of absence. [INT]

---

## 3. Our project: actual architecture and scheduling behaviour (verified in source)

### 3.1 Task and DAG creation

- Workflow tasks are built in `src/caosched/study2/workload.py`: `build_batch` (line 26), `build_mixed` (47), `build_iters` (74), `build_classes` (103). Each `Task` gets `dependencies`, `workload`, `size`, `params` and `eligible_pools`. [SRC]
- `Task` is defined in `src/caosched/core/task.py`; `dependencies` is a tuple of task ids (line 51). Self-dependency and duplicate dependencies are rejected (lines 92–94). [SRC]
- `DAG` is in `src/caosched/core/dag.py`. It validates unknown dependencies, precomputes a remaining-dependency count per task, and `mark_completed` returns the newly ready task ids (lines 37–89). [SRC]

### 3.2 DAG dependencies and ready-task identification

- `DAG.initial_ready_tasks` returns tasks with no dependencies (line 70–72). [SRC]
- `mark_completed` decrements the remaining count of each dependent and returns those that reach zero (lines 74–89). [SRC]
- The ready queue is `ReadyQueue` in `src/caosched/core/ready_queue.py`. [SRC, class at line 14]
- Dispatch happens in `Coordinator._dispatch_ready_tasks`, `src/caosched/core/coordinator.py:247–264`:
  1. `ordered = self.scheduler.order_ready(list(ready), self.state)` (line 250).
  2. For each task in order, if the policy is late-binding and no worker is idle, stop (lines 255–257).
  3. `worker_id = self.scheduler.select_worker(task, self.state)` (line 261). If `None`, the task stays in the queue.

### 3.3 Eligibility (which workers a task may use)

- Build-time: `resolve_eligibility` in `src/caosched/core/eligibility.py:39–69` narrows `task.eligible_pools` using `supported_kinds` (lines 22–36), which checks which pool kinds have an implementation of the workload. A CUDA variant exists only for stages in `cuda_stages()`. [SRC]
- Per-stage GPU eligibility is **static, set before the run**. In the study-2 adapter (`src/caosched/study2/adapter.py:159–165`), `gpu_stage_table` says which stages may use pool `G`. In `workload.py` each task gets `eligible_pools = LOCAL_POOLS + ("G",)` only when its stage is in `gpu_stages` (e.g. lines 33, 59, 87, 115). [SRC]
- Run-time: `eligible_workers(task, state, idle_only)` in `src/caosched/core/scheduler_base.py:91–97` filters idle or all workers by `task.eligible_pools`. Every policy chooses only from this list. [SRC]

**So CPU-or-GPU is chosen dynamically per task, but only among the pools that the stage's eligibility allows, and only for stages that have a CUDA variant.** Stages without a CUDA variant are CPU-only. [SRC + INT]

### 3.4 Execution-time estimation

- Estimators implement `ExecutionTimeEstimator` (`src/caosched/estimators/base.py`, not re-read here).
- Study-2 estimators: `IterModelEstimator` in `src/caosched/study2/model.py:21–42`. For `img_denoise` it returns `a + b * iterations` per pool, from a line fitted offline. Other stages use a static solo profile lookup. The learned generic model `ParamModelEstimator` is loaded in `adapter.py:56–59` (its internals were **not** re-read in this audit).
- `ReplayOracleEstimator` / `CachedOracle` (`src/caosched/study2/policies.py:57–74`) is an oracle ceiling, labelled as not a real rule. [SRC]

### 3.5 How B4 makes decisions

- Class: `GreedyEligibleScheduler` in `src/caosched/schedulers/simple.py:148–212`. [SRC]
- Ordering: `order_ready` is not overridden, so FIFO ready order (line 203 comment: "Ready tasks are considered in FIFO ready order").
- Placement (`select_worker`, lines 202–208): take the first idle eligible worker, scanning pools in fixed priority (P, then E) and workers in id order. **No cost model, no estimate, no transfer term, no lookahead.** The docstring says so explicitly (lines 149–155).
- Late binding: `binds_only_idle = True` (inherited from `SchedulerPolicy`, `src/caosched/core/scheduler_base.py:49`).
- Study-2 wiring: `build_study2_policy` in `src/caosched/study2/adapter.py:71–78` returns `ParamFirstGreedy` (the informed variant) for `param_first`, or `B4_param_first`; the base B4 comes from `build_policy` (`adapter.py:93`, `montage_adapter.build_policy`, not re-read).

### 3.6 How PRED_RANK_GREEDY makes decisions

- Class: `PredictedRankGreedy` in `src/caosched/study2/policies.py:95–145`. [SRC]
- Ordering: `order_ready` (lines 119–129) delegates to `RankEftScheduler.order_ready`, which sorts by the upward rank `self.rank[t]`, descending (`src/caosched/schedulers/rank_eft.py:62–63`).
- Upward rank: computed once per run in `RankEftScheduler.on_run_start` (`rank_eft.py:51–60`) from the estimator's idle-machine times `self._exec(t, p, None) + self._extra(t, p)`. The communication term is `self._transfer(child, p)` averaged over all pools (line 56–57). The module docstring says this is an approximation of HEFT's rank, "not HEFT-exact" (lines 10–13).
- Placement (`select_worker`, lines 131–142): `idle = eligible_workers(task, state, idle_only=True)`. Picks the idle eligible worker with the smallest predicted `exec(task, pool)` (`min(...)` over `(predicted, worker)`). Returns `None` if no idle worker.
- Hold rule: `hold_min_s` is `None` for the `pred_rank_greedy` binding (`src/caosched/study2/adapter.py:69–70`), so the hold branch (lines 136–140) never runs. The hold variant `pred_rank_hold` uses `hold_min_s=0.010`. [SRC]
- Late binding: `binds_only_idle = True` (`policies.py:112`).

### 3.7 Worker eligibility and CPU/GPU worker selection

- Pools are `P` (CPU, performance cores), `E` (CPU, efficiency cores) and optionally `G` (CUDA). Pool kinds are in `src/caosched/core/runtime_config.py:22–41` (`PoolSpec`, kinds: cpu, cuda, remote). [SRC]
- In the study-2 adapter, the CUDA pool is `PoolSpec((0,), "cuda")` (`src/caosched/experiment/gpu_adapter.py:85`). **There is one CUDA worker**, on device 0. [SRC]
- CPU workers are spawned one per logical processor slot and pinned to it (`src/caosched/core/worker_pool.py:301–309`; `affinity = [slot] if kind == "cpu" else []`, line 302). [SRC]
- Consequence: all GPU work contends for a single worker, and a CUDA task waits in the global ready queue while that worker is busy. [INT from the above]

### 3.8 GPU transfer overhead

- **Not in the scheduler's decision.** The study-2 policies build EFT/PRED without a transfer model: `EftNoContext`, `RankEftNoContext` and `PredictedRankGreedy` are constructed without `transfer=` (`src/caosched/study2/adapter.py:57–70`; `policies.py:29–39`). The EFT base returns 0 transfer for local pools (`src/caosched/schedulers/eft.py:12`, `_transfer` line 91). [SRC]
- **Not measured separately.** The adapter records `"h2d_d2h_copy_time": "not measured (inside the CUDA stage kernel time)"` (`src/caosched/study2/adapter.py:176`). The copy time is inside the stage's own timed kernel. [SRC]
- **E2E variant exists for EFT only.** An end-to-end term (measured setup and IPC overhead per pool) is applied only for `EFT_*` bindings that pass `e2e_terms` (`adapter.py:94–111`). `PredictedRankGreedy` does not use it. [SRC]

### 3.9 GPU availability and contention

- The scheduler sees the state of the single `G` worker through the same idle-or-busy rule as all workers (`eligible_workers`, `idle_only`). It does not model GPU utilisation or memory pressure. [SRC]
- The EFT family (not PRED) does model waiting time for a busy worker (`_wait`, `src/caosched/schedulers/eft.py:97–104`). PRED's placement is idle-only, so it ignores a busy GPU except through the ordering. [SRC]

### 3.10 Remote execution

- Remote workers are a separate pool kind (`worker_pool.py:239–295`; `kind="remote"`). [SRC]
- The transfer term comes from `FileTransferModel` (`src/caosched/schedulers/rank_eft.py:37–47`) with a `LinkConfig`. Local pools cost 0. [SRC]
- The remote link in the evidence was **emulated** (loopback plus a delay shim), per the project's own reports. [SRC for the emulation claim in `OVERNIGHT_FINAL_REPORT.md`; not re-read here]
- PRED's rank uses the transfer term for remote pools only through `comm`, and its placement does not include `transfer` in the decision. [SRC: `rank_eft.py:56–57`; `policies.py:131–142`]

### 3.11 Can our scheduler choose CPU or GPU for an individual task?

**Yes, for stages that have a CUDA variant and are listed in `gpu_stage_table`.** Both B4 and PRED pick among eligible pools at dispatch. **No, for stages without a CUDA variant**, which are CPU-only. The scheduler is not a general CPU-or-GPU placer for arbitrary code. [SRC + INT]

---

## 4. Side-by-side comparison

Labels: Supported and verified / Partially supported / Not supported / Not established from available evidence.

| Capability | NVIDIA technology | Our project |
|---|---|---|
| Application-level GPU selection | Supported and verified: Optimus, Preferred GPU, Windows per-app preference [DOC] | Not applicable. Our framework selects pools per task, not per app. |
| Individual task-level CPU/GPU selection | Not supported: no NVIDIA mechanism does it [DOC, see caveat §2] | **Partially supported**: dynamic among eligible pools, only for stages with a CUDA variant listed in `gpu_stage_table` [SRC §3.3, §3.11] |
| DAG dependency awareness | Partially supported: developer-written via CUDA events and CUDA Graphs; not automatic [DOC] | Supported and verified: `DAG.mark_completed` releases dependents [SRC §3.2] |
| Runtime prediction | Not supported: no runtime cost model in CUDA or Optimus [DOC] | Supported and verified for study 2: `IterModelEstimator`, `ParamModelEstimator`, profile lookup [SRC §3.4] |
| Resource availability awareness | Partially supported: HAGS and MPS manage GPU contexts; Windows decides app priority [DOC] | Partially supported: idle/busy only, no utilisation model for PRED [SRC §3.9] |
| CPU/GPU execution-cost comparison | Not supported at task level [DOC] | Supported and verified for EFT and PRED: predicted exec per pool [SRC §3.6] |
| Data-transfer-cost consideration | Not established from available evidence for task level. H2D/D2H is part of the kernel timing [DOC for the CUDA guide's overlap statement; `adapter.py:176`] | **Partially supported**: transfer term exists in EFT and remote link model, zero for local pools, not used by PRED for local GPU [SRC §3.8] |
| Dynamic task dispatch | Partially supported: CUDA streams dispatch kernels at runtime in stream order [DOC] | Supported and verified: coordinator dispatches on every completion [SRC §3.2] |
| Remote-worker scheduling | Not supported: no NVIDIA mechanism covers remote workers in this audit (NVIDIA networking/NCCL was not checked) | **Partially supported**: remote pool kind and transfer model exist; evidence is emulated [SRC §3.10] |

---

## 5. Overlap between NVIDIA and our project

- **Overlap in device selection:** Optimus and Preferred GPU select a device per application. Our `eligible_pools` does the same per stage, but it is finer-grained (per task) and includes CPU pools. The concept is the same at a coarser level; this is the only real overlap.
- **Overlap in GPU concurrency:** CUDA streams and MPS overlap GPU work. Our scheduler does not manage GPU concurrency at all: `G` is one worker (§3.7). If anything, the GPU is under-used by our design. [INT]
- **Overlap in dependencies:** CUDA events and CUDA Graphs express a DAG, but the developer writes it. Our runtime derives it from the workflow. This is a real difference of who does the work, not a duplicate.
- **No overlap in:** cross-device placement of tasks with predicted cost, DAG-aware dispatch across CPU and GPU, and remote workers.

---

## 6. Remaining research gap (critically stated)

**Answers to the six questions**

1. *Is NVIDIA Optimus doing the same thing as our scheduler?* No. Optimus selects a device for a whole application at launch. Our scheduler selects a pool for each task at each dispatch. [DOC, SRC]
2. *Is CUDA GPU execution scheduling equivalent to application-level DAG scheduling?* No. CUDA orders work within and across streams. The DAG is written by the developer. CUDA does not decide what runs on the CPU. [DOC]
3. *Does NVIDIA automatically choose CPU or GPU for every individual task in an arbitrary workflow?* No, not in any mechanism reviewed. [DOC, §2 caveat]
4. *What parts of our architecture already exist in NVIDIA technology?* Per-application device selection (Optimus, Preferred GPU, Windows per-app preference). Concurrent GPU kernels (streams, MPS). Nothing else in §4 is covered by NVIDIA.
5. *What parts are genuinely different?* Per-task cross-device placement using predicted cost; DAG-aware dispatch across CPU, GPU and remote pools; policy comparison against a non-predictive greedy rule. None of these is in the NVIDIA pages reviewed.
6. *Does our contribution go beyond selecting a preferred GPU?* Yes, in the sense that NVIDIA's stack does not do per-task placement across devices. **But this audit did not establish novelty against the wider literature.** The relevant comparison is to heterogeneous task-graph schedulers (HEFT, PEFT, StarPU-style runtimes, OpenMP task offloading), which were not reviewed here. [OPEN]
7. *What would we need to demonstrate?* Against NVIDIA-native baselines, the honest comparison is: (a) a CUDA-only application with per-stream ordering and CUDA Graphs; (b) Optimus/Preferred-GPU selection for the whole pipeline on the same machine. Our results already compare against the non-predictive baseline B4 and a static EFT/HEFT family, not against NVIDIA-native execution. This comparison is **not yet run**. [OPEN]

**Critical overlap statement (for faculty):** NVIDIA's device selection overlaps our idea at the application level. The defensible gap is per-task, cross-device, prediction-driven placement inside a DAG. The current results show a clear gain over a non-predictive greedy rule on one workload family, and no gain over an informed hand rule or over HEFT. The gap is real only as far as the measurements go.

---

## 7. What we can safely claim during faculty review

Safe:

- "NVIDIA's documented mechanisms choose a GPU per application (Optimus, Preferred GPU, Windows per-app preference). They do not choose a CPU or GPU per task inside an application." [DOC]
- "CUDA streams and events let the developer order GPU work and build a DAG by hand. The CUDA guide does not describe automatic CPU/GPU selection." [DOC]
- "Our scheduler selects a worker for each ready task from its eligible pools, at dispatch time, using the same eligibility rule for every policy." [SRC]
- "Our policies are compared on one laptop and a designed workload; the remote worker is emulated." [SRC, OVERNIGHT_FINAL_REPORT]

Not safe to claim:

- "NVIDIA does not support task-level CPU/GPU selection." Stated as "not found in the pages reviewed," this is defensible. Stated as absolute, it overreaches. [§2 caveat]
- "Our scheduler is novel." Not established against heterogeneous scheduling literature. [OPEN]
- "Our scheduler beats NVIDIA." No NVIDIA-native baseline was run. [OPEN]
- Anything about Advanced Optimus beyond display routing. No NVIDIA primary source found. [OPEN]
- Anything about Windows per-app registry values. Unofficial only. [OPEN]

---

## 8. What we should improve or investigate next

Investigation items only; none was run here.

1. Fetch the English Control Panel page for Preferred graphics processor and the NVIDIA Advanced Optimus primary page, to replace the Polish-page and third-party citations.
2. Fetch Microsoft's official Windows Graphics settings page (the learn.microsoft.com URL returned 404 in this audit).
3. Read `ParamModelEstimator` (`src/caosched/study2/param_model.py`) and `montage_adapter.build_policy` (for base B4 wiring), which were referenced but not re-read here.
4. Read `remote_adapter` to confirm how the remote pool's transfer term enters PRED's ordering and whether it is used in any policy decision (only the rank term was verified).
5. Decide whether the GPU pool should be modelled as one worker. It is a single CUDA worker by construction (`gpu_adapter.py:85`), which limits any GPU-concurrency claim.
6. Literature search: heterogeneous DAG schedulers (HEFT, PEFT, StarPU, OpenMP task offloading, Legion) for the novelty statement. Not done.
7. Optional baseline: run a CUDA-only and a whole-app-Optimus-style baseline on the same pipeline. This is a new experiment and needs a separate, pre-registered decision.

---

## Sources

NVIDIA and Microsoft (fetched in this audit unless noted):

- [NVIDIA Optimus (archived gameworks page, fetched)](https://archive.docs.nvidia.com/gameworks/content/technologies/desktop/optimus.htm)
- [Using Optimus Hybrid, NVIDIA Control Panel help (fetched)](https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-us/mergedProjects/nvcpl/Using_Optimus_Hybrid.htm)
- [Setting the Preferred Graphics Processor, Polish-language page (search snippet only)](https://www.nvidia.com/content/Control-Panel-Help/vLatest/pl-pl/mergedProjects/nv3dPLK/Setting_the_Preferred_Graphics_Processor.htm)
- [CUDA Programming Guide, 2.5 Asynchronous Execution (fetched)](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/asynchronous-execution.html)
- [MPS architecture (search snippet only)](https://docs.nvidia.com/deploy/mps/architecture.html)
- [Microsoft DirectX blog, Hardware Accelerated GPU Scheduling (fetched)](https://devblogs.microsoft.com/directx/hardware-accelerated-gpu-scheduling/)
- [Navigating the Redesigned Graphics Settings page (search snippet only)](https://devblogs.microsoft.com/directx/navigating-the-redesigned-graphics-settings-page/)

Third-party, not NVIDIA primary (used only where no primary source was found):

- [WePC, What is Advanced Optimus](https://www.wepc.com/gaming-laptop/faq/what-is-advanced-optimus-explained/)
- [ASUS ROG, MUX switch](https://rog.asus.com/articles/rog-gaming-laptops/maximize-your-rog-laptops-performance-with-a-mux-switch/)

Repository (read in this audit): `src/caosched/study2/policies.py`, `src/caosched/study2/model.py`, `src/caosched/study2/adapter.py`, `src/caosched/study2/workload.py` (grep), `src/caosched/schedulers/simple.py`, `src/caosched/schedulers/eft.py`, `src/caosched/schedulers/rank_eft.py`, `src/caosched/core/scheduler_base.py`, `src/caosched/core/coordinator.py` (grep), `src/caosched/core/dag.py`, `src/caosched/core/eligibility.py`, `src/caosched/core/task.py` (grep), `src/caosched/core/ready_queue.py` (grep), `src/caosched/experiment/gpu_adapter.py` (grep), `src/caosched/core/worker_pool.py` (grep), `src/caosched/core/runtime_config.py` (grep).
