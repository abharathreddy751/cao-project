# Final study: static versus dynamic heterogeneous workflow scheduling (protocol, written before any final run)

Status: **frozen when its SHA-256 is written to `data/results/final_20261101/ACTIVITY_LOG.md` before the first final session starts.** Anything decided after seeing a final result goes into an amendment file (`docs/final/AMENDMENT_F*.md`) and is labelled post hoc.

## 1. Research question

Can the end-to-end dynamic heterogeneous scheduling framework (DAG manager, runtime estimation, rank-based prioritisation, late-bound CPU/GPU worker selection, execution feedback) reduce **total workflow completion time** compared with a **fixed static workflow schedule**, and under which workload and resource conditions? The framework, not only its learned model, is evaluated: the same cost model feeds both the static and the dynamic schedulers, so differences come from when and how decisions are made.

Resources: P cores, E cores, one local CUDA GPU (one CUDA worker), and, as a separate secondary study that is **not part of this protocol's confirmatory family**, an emulated remote worker. Raspberry Pi is out of scope. One laptop; every number is a measurement on this machine.

## 2. What is registered and what is new

| Kind | Names | Rule |
|---|---|---|
| Registered, unchanged | B4, B4_param_first, PRED_RANK_GREEDY, HEFT_param_model, PEFT_param_model, `ParamModelEstimator`, `EndToEndTerms`, all earlier designs and sessions | not edited; the new code only adds options |
| New policies | PRED_RANK_GREEDY_E2E, HEFT_E2E, HEFT_ORACLE_REF | `src/caosched/final/policies.py`, new names |
| New timing convention | `init_seconds`, `policy_setup_seconds`, `end_to_end_makespan_seconds` | `AMENDMENT_F1_timing.md` |
| New eligibility mechanism | `GpuRegion` (per task, from recorded GPU-spike rows) | `src/caosched/final/gpu_region.py` |

Preservation record: `data/results/final_20261101/preservation/` (commit `9d8ea22`, working-tree status and diff before any change, SHA-256 of every source file, of 164 earlier designs and adapter configs, of the key documents, the run-manifest count 4753, baseline test run). Files edited in tracked code, each with a backup in `backups/`: `core/coordinator.py`, `study2/adapter.py` (three extra fields), `analysis/stats_paired.py` (new optional arguments, defaults unchanged), `scripts/analyze_experiment.py` (new options).

## 3. What each cost term contains (checked in the source)

* **Kernel prediction.** `ParamModelEstimator` is fitted on `wall_time_seconds` = the timed `compute` call (`apps/stages.py:run_stage`). For a CUDA stage that call performs the host-to-device copy, the kernels and the device-to-host copy (`apps/cuda_stages.py`: `.cuda()` first, `.cpu()` last; `gpu_spike.py` times it between `torch.cuda.synchronize()` calls). **H2D and D2H are therefore inside the kernel term and are never added again.**
* **Setup** (`EndToEndTerms.setup`) = median over completed tasks of (worker span minus `wall_time_seconds`) for the same stage, size and pool = artifact read/decode and encode/write in the worker. Not in the kernel term. Derived by `scripts/study2_e2e_terms.py`.
* **IPC overhead** (`EndToEndTerms.overhead`) = coordinator-to-worker plus worker-to-coordinator message time per pool. Not in the kernel term.
* **Transfer** = link model of a remote pool. Zero for P, E and G, and zero throughout this protocol (no remote pool in the confirmatory family).
* `PRED_RANK_GREEDY_E2E` places a task on the idle eligible worker with the smallest kernel + setup + IPC; its rank already used kernel + setup + IPC (`rank_eft.py:59`), so rank and placement now agree. `HEFT_E2E` plans with the same sum.

## 4. Resource configurations and GPU eligibility

| suffix | workers | CUDA eligibility |
|---|---|---|
| `_cpu` | P + E (the idle CUDA worker stays in the pool, as in every registered Study 2 session; no task is eligible for it) | none |
| `_gpu` (strict) | P + E + G | only (stage, 512 px, parameters) with verdict PASS in the **original** record `data/results/stage1_20261011/gpu/gpu_spike.json`: `img_edges`, `img_features`; plus `img_denoise` with 8 iterations (uniform workload only) |
| `_ext` (extended) | P + E + G | the strict set plus `img_denoise` for the iteration counts that PASS in the **new** record `data/results/final_20261101/gpu_spike_iters/spike_20261101T144333/gpu_spike.json` (same compare, tolerances, timing and verdict as the original, imported from `scripts/gpu_spike.py`): 6, 15, 40, 120 PASS (speed-up 1.06, 1.19, 1.77, 1.20); **2 DROPPED (0.99)**, so light chains' denoise never gets the CUDA pool. Applied per task by `GpuRegion`. |

The strict family follows the rule "only recorded, verified regions". The extended family goes beyond the original record only through a **new recorded verification made with the same rule before any benchmark ran**; it is reported separately and is exploratory.

B4 and B4_param_first use the pool priority G, P, E when G is eligible (as in the registered `revival_uniform2`), else P, E.

## 5. Data separation

| purpose | sessions | orders |
|---|---|---|
| train `ParamModelEstimator` (one file, `param_model_final.json`) and derive `EndToEndTerms` and oracle class medians | `final_cal_l15`, `final_cal_l40`, `final_cal_l120`, `final_cal_uniform` (random placement incl. G and `B0_E_only_cpu`) | chain orders 9101, 9102 |
| hold-out accuracy of that model (reported, not used for tuning) | `final_hold_l40`, `final_hold_l120` | 9201, 9202 |
| final evaluation | `final_eval_*` (section 7) | 9301 to 9304 |
| hybrid development / held-out (section 10) | decided there, new orders 9401 and later | |

No file is trained on a final evaluation session. The model, the terms and the oracle rows are not refitted after any final result is seen.

## 6. Policies in every final session

| role | name (suffix `_cpu`, `_gpu`, `_ext`) | cost information |
|---|---|---|
| STATIC | `HEFT_param_model`, `PEFT_param_model` | kernel prediction (`ParamModelEstimator`) |
| STATIC | `HEFT_E2E` | kernel prediction + setup + IPC |
| STATIC, reference only | `HEFT_ORACLE_REF` | `CachedOracle` filled with class-median **measured** kernel times from the calibration sessions (stage, size, iterations, pool). Oracle-informed reference; never called a deployable static scheduler. |
| DYNAMIC | `B4` | none |
| DYNAMIC | `B4_param_first` | the hidden parameter by hand, no model |
| DYNAMIC | `PRED_RANK_GREEDY` | kernel prediction (rank, placement) |
| DYNAMIC | `PRED_RANK_GREEDY_E2E` | kernel + setup + IPC (rank, placement) |

Static means: the whole task-to-worker assignment is computed in `on_run_start` and never changed (`StaticPlanScheduler`, early binding, planned-start order); the planned and executed placement and the planned makespan are logged per run (`extra.static_plan`, `task_dispatched.decision`). Dynamic means: a task is bound only when a worker is idle (late binding), using the information the policy has at that moment.

## 7. Workloads and sessions

All workloads: 64 independent chains `source -> denoise -> edges -> features` plus an aggregate, 512 px (the registered hidden-cost family).

| session | chains (light x 2 iterations / heavy) | configs | blocks (analysed) | status |
|---|---|---|---|---|
| `final_eval_h16_l120` | 48 / 16 x 120 | cpu, gpu, ext | 25 (24) | **primary** |
| `final_eval_h04_l120` | 60 / 4 x 120 | cpu, gpu, ext | 13 (12) | exploratory (heavy-count dependence) |
| `final_eval_h40_l120` | 24 / 40 x 120 | cpu, gpu, ext | 13 (12) | exploratory |
| `final_eval_h16_l15` | 48 / 16 x 15 | cpu, gpu, ext | 13 (12) | exploratory (cost-ratio dependence) |
| `final_eval_h16_l40` | 48 / 16 x 40 | cpu, gpu, ext | 13 (12) | exploratory |
| `final_eval_uniform` | 64 x 8 iterations | cpu, gpu | 13 (12) | no-harm control |

Block 0 is warm-up (excluded by the design rule). Each block runs every condition once in a seeded random order; the four chain orders (9301 to 9304) alternate across blocks. Montage is not rerun: its registered result (no headroom; claim X2) is cited as the low-headroom control. The emulated remote worker is not part of this protocol.

Designs are written by `scripts/final_make_designs.py` with the model, terms and oracle files named inside; their SHA-256 values are in `data/results/final_20261101/eval/designs_sha256.txt` and are logged before each session starts. Sessions run with the machine on mains power; a block aborts (and the session is rerun under a new id) if free RAM falls below 0.8 GB.

## 8. Metrics

Primary: `makespan_e2e_s` (`AMENDMENT_F1_timing.md`). Also reported, as separate columns: `makespan_s` (old convention), `init_s`, `policy_setup_s`, scheduling time (`sched_overhead_total_s`), queue wait, tasks per pool, GPU busy fraction (sum of kernel time of G tasks over the end-to-end makespan), CPU utilisation (busy time over workers x makespan, as `stats_paired`), per-task kernel time, plan-versus-actual makespan for static runs, output correctness (every run verified against the sequential reference; CUDA tasks within the recorded tolerance). A run with a failed verification is excluded and counted.

## 9. Statistics and decision rules

* Effect = paired within-block log-ratio of the condition against its reference, reported as percent (negative = faster), stratified (by chain order) percentile bootstrap, 10000 resamples, sign-flip p-value (`analysis/stats.py`).
* **Better / worse:** the 95% CI excludes 0 and the Holm-adjusted p < 0.05. **Equivalent:** the 95% CI lies inside [-2%, +2%] (the project's earlier margin; the margin is declared here, for the contrasts below). Otherwise **inconclusive**. Nothing is classified by any other threshold, and no threshold changes after a result is seen.
* **Confirmatory family (Holm, 10 contrasts, primary session `final_eval_h16_l120`, metric `makespan_e2e_s`):**
  C1 PRED_cpu vs B4_cpu; C2 PRED_E2E_cpu vs PRED_cpu; C3 PRED_cpu vs HEFT_param_model_cpu; C4 PRED_E2E_cpu vs HEFT_E2E_cpu; C5 PRED_gpu vs HEFT_param_model_gpu; C6 PRED_E2E_gpu vs HEFT_E2E_gpu; C7 PRED_E2E_gpu vs PRED_gpu; C8 PRED_gpu vs B4_gpu; C9 PRED_gpu vs PRED_cpu; C10 B4_gpu vs B4_cpu.
* Everything else (other workloads, `_ext`, PEFT, B4_param_first, oracle reference, old-convention makespan) is **exploratory**, unadjusted, labelled as such.
* Expected before any final data, as predictions and not as decision thresholds: C1 faster (the earlier unseen-order sessions gave about -19% on the old convention); C2 equivalent on `_cpu` (same pools, almost equal setup terms); C3 and C4 inconclusive or equivalent (earlier PRED vs HEFT: +1.1% [-0.5, +2.8]); C7 faster or equivalent (the unmodelled setup + IPC is a larger share on G than on P or E: about 20 to 30% of the G kernel against about 7 to 10% on P and E, from `e2e_terms_pilot2.json` and the `uniform2` logs); C9 and C10 small, because the strict GPU set covers only edges and features; the uniform control equivalent to B4 within 2%.
* Sessions with different source hashes are never pooled. A run's free RAM at start is in its log; a sensitivity analysis drops runs that started with less than 1.2 GB.

## 10. Hybrid selector (decided only after the main results)

No hybrid is built before the main sessions are analysed. A hybrid is considered only if (a) a workload property known **before execution** (for example the spread of predicted task cost, or the number of tasks whose predicted cost exceeds a multiple of the median) separates the workloads where B4 is not worse than PRED from those where PRED is better, in the **development** sessions (the main sessions); (b) the switching rule is fixed, written down and hashed before the held-out sessions run; (c) it is evaluated on **new orders and, if possible, a new workload family** run after the freeze, against B4, PRED, PRED_E2E and B4_param_first; (d) an oracle best-of-B4-and-PRED per workload is reported as a reference that no runtime policy can reach. No claim that a hybrid is universally best.

## 11. Limits stated in advance

One machine, one GPU, one CUDA worker; designed workload family; learned model is a regression on those same stages; oracle reference uses class medians, not per-run realised times; HEFT and PEFT follow the project's implementation from secondary descriptions (originals not read); the remote worker is not part of the confirmatory family; a security service holding several GB of RAM made the machine's free memory 0.4 to 1.2 GB during preparation (earlier sessions had 2.4 to 3.0 GB), which may add noise.
