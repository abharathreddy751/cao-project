# Revival: implementation report

Branch `revival/resource-state-aware` (from `study2/affinity` at `ceae094`). Everything is additive; the only edits to existing files are listed in section 6.

## 1. What was built

| Piece | File | What it does |
|---|---|---|
| State snapshot | `src/caosched/revival/state.py` | `StateSnapshot` (immutable) and `StateProvider`: per-worker load correction from (a) completed-task residuals (class-aware pool bias, per-worker relative slowdown that decays with time) and (b) per-core foreign load of an idle worker (`psutil.cpu_percent(percpu=True)` minus the worker's own busy share); host free RAM; GPU busy fraction and free VRAM through NVML only if installed. Every signal that cannot be read is named in `unavailable`, never guessed. |
| Cost breakdown | `src/caosched/revival/cost.py` | `CostBreakdown(compute, load_extra, setup, transfer)`: separately inspectable components of the predicted occupation of a worker. |
| Policy | `src/caosched/revival/policy.py` | `ResourceStateAwareRankGreedy`: predicted upward-rank order (as `PredictedRankGreedy`), work-conserving late binding to an idle eligible worker, cost = compute x class-aware residual x worker load factor + measured setup + transfer, B4 fallback with a logged reason (`no_model_coverage`, `gain_below_cost`, `decision_budget`), decision record schema `revival/1`. `live_state=False` is the task-feature-only ablation; an estimator without task-parameter knowledge plus `live_state=True` is the resource-state-only ablation. |
| Contention harness | `src/caosched/revival/contention.py` | `ContentionSchedule` (disjoint phases on seeded sets of P cores) and `ContentionRunner` (persistent pinned spinner processes), started at `on_run_start` of every policy so all conditions see the same schedule. |
| Offline oracle | `src/caosched/revival/oracle.py` | `ScheduleOracleRankGreedy`: the same constraints as the deployable policies, with exact isolated task times (E5) and exact knowledge of the contention schedule. Upper-bound reference only. |
| Workload | `src/caosched/revival/workload.py` | `build_dyn`: 72 image chains in 6 groups with a two-level fan-in (295 tasks, depth 6), existing stages only. |
| Adapter | `src/caosched/revival/adapter.py` | `ReviveAdapter(Study2Adapter)`: `dyn` workload, instances = (chain order, contention schedule), revival bindings `rsa_combined`, `rsa_task_only`, `rsa_state_only`, `oracle_state`; all Study 2 bindings still work. |
| Model | `src/caosched/study2/param_model.py` (+`fit_group_log_power`, `predict_group`) | A power-law form `log t = a + sum b_i log x_i` next to the additive form; old model files load and predict unchanged. |
| Scripts | `scripts/revival_*.py` | calibration, model evaluation and training, designs (cover, gate, pilot, confirm, uniform), oracle table, demo/trace. |
| Tests | `tests/test_revival.py` | 13 tests (below). |

## 2. Signals and what each can and cannot do

Available at decision time and used: worker occupancy; residual of earlier completed tasks; foreign load of the idle worker's core; host free RAM (read, logged,
not used in any cost). Measured in `calibration_core0.json`: one spinner on a worker's core slows a long task 1.77x, two spinners 2.72x, and does not slow a task
shorter than the OS time slice (img_edges at 512 px: 1.01x). Consequence: contention is visible through the runtime of long tasks (residual) and through the
utilisation of the core (foreign load), not through the short tasks.

Not available on this machine and therefore marked unavailable: GPU utilisation and free VRAM (`pynvml` is not installed; installing a package was
not done), remote link telemetry (no remote hardware; the loopback shim is an emulation).

## 3. Fallback

The policy decides with the cost model only when it has a real choice (two or more eligible idle workers). It returns B4's choice and logs the reason when the
estimator has no entry for a (stage, pool) (`no_model_coverage`, whole run), when the predicted benefit over B4's choice is not larger than the measured
cost of deciding (`gain_below_cost`), or when its own mean decision latency exceeds `decision_budget_s` (2 ms; `decision_budget`, rest of the run). With one idle
worker the placement is forced and nothing is computed except the base prediction needed for the later residual.

## 4. Tests (actual)

`tests/test_revival.py` (13): snapshot without any telemetry is safe and names the missing signals; task-only ablation decides like `PredictedRankGreedy`;
work conservation, idle-only binding and eligibility with a CUDA worker (a task not eligible for G never goes to G, a task that may use G does when it is the only
idle worker); a residual signal steers away from a slow worker; every fallback reason is logged; the decision never reads outcome fields of the task being
scheduled (a task object that raises on `wall_time_seconds`, `t_started`, `t_completed`, ...); the decision record is versioned and minimal by default, rich
diagnostics opt-in; the hot-path total equals the component total; decision latency at the maximum pool size (6 P + 7 E + G, full 256-interval histories, a live
provider) below 1 ms; contention schedule determinism, disjointness and exact slowed-duration arithmetic; the oracle avoids a contended worker but never leaves a worker
idle; the mixed-DAG shape and its validation; an end-to-end run of the adapter with a real worker pool, contention and output verification against the sequential
reference. Full-suite counts are in `FINAL_STATUS.md`.

## 5. Limitations

* Evidence is from one machine and one workload family; contention is an emulated foreign load (spinning processes), not a real co-tenant.
* The foreign-load signal cannot tell one spinner from two (both saturate the core); the residual corrects this only after a long task completes on the worker.
* Live-state correction acts on the choice among idle workers; with a saturated pool there is usually one idle worker, so the choice is forced and only the order
  (rank) matters. This is why the oracle gate found no headroom.
* The CUDA worker, GPU contention, remote offloading and the Raspberry Pi are not exercised by the new study (see `FINAL_STATUS.md`).

## 6. Edits to existing files

* `src/caosched/study2/adapter.py`: `run_one` builds its policy through the new method `_build_policy` (default behaviour identical); a subclass extends the bindings.
* `src/caosched/study2/param_model.py`: `fit_group_log_power`, `predict_group`; `estimate` calls `predict_group`; old models predict identically (21 Study 2 tests pass).
* Nothing else under `src/` was edited. No file under `data/results/study2_*` or `stage*` was modified (appended session logs excluded: `progress.txt` was already modified before the revival).
