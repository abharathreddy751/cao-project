# Architecture

## Research question

How much execution-time prediction is enough to improve DAG task scheduling across
heterogeneous P-core / E-core / remote-worker pools? This is an empirical study, not
a new ML algorithm. ML (the E4 estimator) is one point on a ladder of estimators
(E0–E5); the scheduler and the experiment harness are the actual contribution.

## System overview

```
                 ┌─────────────────────────────────────────────┐
                 │                 Coordinator                  │
                 │   (pinned to a reserved E-core at startup)   │
                 └───────────────┬───────────────────────────────┘
                                 │
      ┌───────────────┬─────────┼─────────────┬───────────────┐
      ▼               ▼         ▼             ▼               ▼
 DAG Manager     Ready Queue  Runtime    Scheduler ──┐   Event Logger
 (deps, DAG      (eligible    State     (B0..B7, P,  │   (every state
  patterns)       tasks)      Store      O policies) │   transition,
      │                        │             │       │   timestamped)
      │                        │             ▼       │
      │                        │      Execution-Time │
      │                        │       Estimator     │
      │                        │      (E0..E5, swap- │
      │                        │       pable)        │
      │                        │             │       │
      │                        └─────────────┼───────┘
      │                                      ▼
      │                                 Dispatcher
      │                                      │
      │              ┌───────────────────────┼───────────────────────┐
      │              ▼                       ▼                       ▼
      │        P-core worker            E-core worker          Remote-worker
      │        pool (2 slots)           pool (7 slots)         interface (shim)
      └──────────────────────────────────────────────────────────────┘
                          completion events flow back to
                     Runtime State Store + Ready Queue + Event Logger
```

Everything downstream of "Scheduler" is replaceable independently:
- Swap the **Scheduler** policy (B0–B7, P, O) without touching the estimator.
- Swap the **Estimator** (E0–E5) without touching the scheduler or dispatcher.
- Swap the **Dispatcher** target (local pools vs. remote shim vs. a future physical
  ARM device) without touching the scheduler or estimator.

This modularity is what lets the same seeded workload trace be replayed under every
policy/estimator combination (Phase 7 requirement).

## Phase 0: hardware characterization

Two concerns, kept in separate modules:

1. **Topology discovery** (`caosched.phase0.topology`) — determines, as reliably as
   Windows allows, which logical processors are P-cores vs. E-cores, and which
   logical processors are SMT siblings on the same physical P-core. Windows does
   **not** guarantee logical processor IDs are grouped or ordered by core type, so
   this must be discovered at runtime, never assumed.

2. **Benchmark harness** (`caosched.phase0.benchmarks`) — runs controlled,
   affinity-pinned, repeated measurements of representative workloads (matrix
   multiplication, image filtering, compression) to determine whether execution
   time actually varies meaningfully across P vs. E pools and under load. This
   produces the evidence for the **Phase 0 gate decision** — whether prediction is
   worth building further estimator sophistication for.

### Topology discovery approach

Windows exposes per-logical-processor **CPU Sets** via the `GetSystemCpuSetInformation`
Win32 API (available since Windows 10 2004+), including an `EfficiencyClass` byte per
logical processor. On a hybrid part (Alder Lake and later), a higher `EfficiencyClass`
value means a higher-performance core type. This is the only documented, reliable way
to distinguish P-cores from E-cores on Windows without vendor-specific drivers — it is
what Task Manager and Windows' own scheduler use internally. We call this API directly
via `ctypes` (no extra dependency) and additionally record `CoreIndex` so that SMT
sibling logical processors (both threads of one physical P-core) are identifiable.

Cross-validated against:
- `NumberOfLogicalProcessors` / `NumberOfCores` from `Win32_Processor` (WMI).
- The expected shape stated by the user (2 P-cores with SMT = 4 threads, 8 E-cores
  without SMT = 8 threads, 12 threads total on the i5-1235U).

If the API is unavailable (older Windows) or the result doesn't parse, the system
records the failure explicitly in the environment JSON rather than guessing — per
the project's research-integrity rules, an unmeasurable property is documented as a
limitation, not silently assumed.

### Benchmark workloads

All workloads run as **separate OS processes** (`multiprocessing`, spawn context),
one process per measurement, so that:
- CPU affinity can be set per-process via `psutil.Process.cpu_affinity()` before the
  workload starts.
- Thread-count environment variables (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
  `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`) are set
  **before** `numpy` is imported in that process, eliminating hidden BLAS
  multithreading that would otherwise contaminate P-vs-E or load-level comparisons.

Implemented workloads (Phase 0 set): matrix multiplication (numpy, thread-pinned),
image filtering (Pillow, box/Gaussian blur), compression (zlib, stdlib — no extra
dependency). Sorting and ML inference are deferred to later phases per the brief.

## Directory layout

```
caosched/
  src/caosched/
    phase0/                 topology + environment record + benchmark harness
      topology.py
      env_record.py
      benchmarks/
        workloads.py        CPU-bound kernels (matmul, image filter, compression)
        worker.py           subprocess entry point (affinity + thread-pin + timing)
        harness.py          orchestrates warmups, repeats, concurrent-load scenarios
        analysis.py         raw CSV -> Phase 0 gate report
    core/                   Phase 1 runtime
      task.py               Task, TaskState (+ legal transitions), TaskMessage/TaskResult (IPC)
      dag.py                DAG (validation, cycle detection, dependency counters) + pattern builders
      ready_queue.py        ReadyQueue (global ready set, FIFO by ready time)
      runtime_state.py      Runtime State Store: per-worker executing task + local queue
      trace.py              seeded JSON workload traces, replayed as fresh DAGs
      runtime_config.py     RuntimeConfig.from_topology() -> Phase 0 planned_worker_pool_config
      worker_pool.py        persistent affinity-pinned P/E workers, startup handshake
      scheduler_base.py     SchedulerPolicy ABC (+ FirstIdleScheduler test placeholder)
      coordinator.py        main loop: dispatch, completion handling, failure detection
      event_log.py          append-only JSONL event logger
    schedulers/             Phase 2 baselines
      simple.py             B0-B5
      eft.py                Earliest-Finish-Time (B6, B7; Phase 4's P)
      __init__.py           config-driven registry (fresh instance per run)
    estimators/             execution-time estimators (kernel-only)
      base.py               ExecutionTimeEstimator, EstimateContext, TaskSpec
      constant.py           E0 constant per (type, pool)
      profile.py            E1 static profile lookup
      analytic.py           E2 analytic size model
      history.py            E3 moving history
      learned.py            E4 interference ridge (occupancy [+ recent activity])
      oracle.py             E5 replay oracle (offline only)
      recalibrated.py       "+rc" online recalibration wrapper (per-pool EWMA factor, per run)
      e2e.py                EndToEndTerms: measured setup + runtime overhead (e2e EFT ablation)
      profile_data.py       raw profile CSV loader
      __init__.py           build_estimator() registry
    remote/                 Phase 5 remote offloading
      link.py               LinkConfig, shim (precise_wait), payload_bytes, TransferModel
      protocol.py           length-prefixed JSON + payload frames over TCP
      node.py               remote execution node (portable to a physical device)
      proxy.py              local worker-slot process for a remote node (pool "R")
    analysis/
      decisions.py          per-decision records, placement regret, bind delay (from logs)
      stats.py              paired-block effects, stratified bootstrap CIs (Phase 6B)
    dataset/
      build.py              unified dataset (tasks/candidates/splits/manifest) from raw logs (Phase 6A)
      events.py             event log -> per-task rows + decision-time context
      campaign.py           RandomOccupancyPolicy (data collection, not a baseline)
    util/
      threadpin.py          sets BLAS/OMP env vars before numpy import
      clock.py              high-resolution cross-process clock (QPC) for all runtime stamps
  scripts/
    phase0_characterize.py  -> data/environment/<timestamp>.json
    phase0_benchmark.py     -> data/benchmarks/<run_id>.csv
    phase0_gate_report.py   -> data/reports/<run_id>_gate.json + printed verdict
    run_dag.py              Phase 1: DAG patterns on real topology -> data/events/<run_id>.jsonl
    profile_static.py       Phase 2: solo kernel profile -> data/profiles/<stamp>_{raw.csv,profile.json}
    run_baselines.py        Phase 2: traces x B0-B7 -> data/results/phase2_<stamp>_*, data/events/phase2_<stamp>/
    collect_campaign.py     Phase 3: randomized interference campaign -> data/events/campaign_<stamp>/
    train_e4.py             Phase 3: E4 fit (split by run order) -> data/models/e4_<stamp>_<features>.json
    evaluate_estimators.py  Phase 3: E0-E5 accuracy on held-out/cross-session sets -> data/results/phase3_*
    diag_solo_patterns.py   Phase 3: solo idle vs back-to-back diagnostic -> data/diagnostics/
    run_phase4.py           Phase 4: EFT ladder + O + regret analysis -> data/results/phase4_*
    diag_decision_cost.py   Phase 4: select_worker CPU cost per estimator -> data/diagnostics/
    derive_e2e_terms.py     e2e ablation terms (setup, overhead) -> data/models/e2e_terms_*.json
    run_phase5.py           Phase 5: local vs remote configs + kernel/e2e ablation -> data/results/phase5_*
  config/
    phase2.yaml             profile sizes, trace specs, policy settings, experiment settings
    phase3.yaml             campaign design, estimator settings (E2 exponents, E3 window, E4)
    phase4.yaml             Phase 4 policy set, recalibration settings, E4 model, experiment
    phase5.yaml             links, remote node/proxy cores, policies, profile + e2e terms paths
  docs/
    PROJECT_BRIEF.md        the original project brief, verbatim (authoritative spec)
    B4_PATENT_MAPPING.md    B4 vs US 11,561,826 B1: mapped / not-mapped mechanisms
  data/
    environment/            machine/environment JSON records (gitignored, regenerable)
    benchmarks/             raw per-measurement CSV (gitignored, regenerable)
    reports/                derived summaries/gate verdicts
    events/                 raw per-run runtime event logs (JSONL)
    profiles/               static profiles: raw CSV + derived JSON
    traces/                 saved workload traces (JSON)
    results/                per-experiment manifest, raw runs CSV, derived summary
    models/                 trained estimator parameters (E4)
    diagnostics/            targeted diagnostic measurements
  tests/
```

Later phases (core runtime, schedulers, estimators, remote shim, dataset generation,
experiment harness) add sibling packages under `src/caosched/` (`core/`,
`schedulers/`, `estimators/`, `remote/`, `dataset/`, `experiments/`) without
restructuring Phase 0.

## Phase 1: core runtime

Implements the DAG Manager, Ready Queue, Worker Pools, Coordinator, Dispatcher,
and Event Logger boxes from the system diagram above (the Scheduler and
Execution-Time Estimator boxes are stub/placeholder in Phase 1 -- their real
implementations are Phase 2 and Phase 3's job respectively).

### Concurrency model

Worker pools use **persistent, affinity-pinned OS processes** (`multiprocessing`,
spawn context) -- one process per configured core slot, living for the whole
run rather than one process per task. Core slots come from
`RuntimeConfig.from_topology()`, which calls Phase 0's
`planned_worker_pool_config` -- the runtime and the Phase 0 environment record
share one source of truth (on the i5-1235U: P slots `[0, 2]`, E slots
`[5..11]`, coordinator `4`).

Each worker process:
1. **Startup handshake.** Sets CPU affinity via `psutil`, *reads it back*, and
   (by default) runs every workload once at a tiny size so the one-time
   numpy/Pillow import cost is paid before any timed task. It then sends a
   `WorkerReady` (pid, requested vs. actual affinity, any affinity error,
   measured warmup seconds). The pool blocks until all workers report. A
   readback mismatch is recorded, never treated as pinned; with
   `strict_affinity=True` it aborts startup.
2. Loops: pull a `TaskMessage` from its own input queue, run
   `prepare()` then the timed `run()` kernel from
   `caosched.phase0.benchmarks.workloads`, push a `TaskResult` onto a shared
   output queue. Workload exceptions are returned as `error`, never crash the
   worker.

This differs deliberately from Phase 0's benchmark harness, which spawns a
fresh process per *measurement* for maximum isolation. The runtime keeps
workers warm because per-task process-spawn overhead would dominate and
distort measured times. The warmup handshake exists because the first
Phase 1 run showed a worker's first task paying ~2 s of import cost.

The coordinator runs single-threaded in the main process, pinned (with
readback) to the reserved coordinator core, and owns the `DAG`, the
`ReadyQueue`, the `WorkerPool` (busy = has a `current_task`), the injected
`SchedulerPolicy`, and the `EventLogger`. Loop:

```
seed ready queue with dependency-free tasks
while DAG incomplete:
    for task in ready_queue.ordered():          # FIFO unless a policy overrides
        scheduler.select_worker(task, idle_P, idle_E) -> worker | None
        (must be one of the offered idle ids, else SchedulerContractError)
    poll one TaskResult (timeout) -> validate it matches the worker's assignment
        -> DONE: log, scheduler.on_task_completed(task), DAG.mark_completed,
                 enqueue newly-ready dependents
        -> error: log task_failed, raise TaskFailedError
    on poll timeout: dead worker with work in flight -> WorkerPoolError;
                     past run_timeout -> RunTimeoutError
    nothing in flight and DAG incomplete -> DeadlockError
```

Failure policy is **fail-fast, no retry**: in an experiment harness a
silently retried or reassigned task would corrupt the measurements.

### Timing

All runtime lifecycle timestamps (`t_created`, `t_ready`, `t_dispatched`,
worker-side `t_started`/`t_completed`) use `caosched.util.clock.now()` =
`time.perf_counter()` = `QueryPerformanceCounter` on Windows (100 ns, and
system-wide, so coordinator and worker stamps are directly comparable).
`time.time()` is **not** used for intervals: on CPython 3.11/Windows it is
`GetSystemTimeAsFileTime` (15.6 ms nominal), and Phase 1 validation caught it
producing physically impossible intervals. See `util/clock.py`; pinned by
`tests/test_clock.py`.

Two per-task durations are recorded and must not be confused:
`wall_time_seconds` (the timed kernel only) and `t_completed - t_started`
(prepare + kernel, as the worker experienced it). Measured runtime overhead
outside both is ~0.5 ms per dependency hop on this machine.

**Project decision (2026-10-03): "execution time" = kernel-only
(`wall_time_seconds`)** for every estimator, profile, history observation and
the oracle. `prepare()` and runtime overhead are logged but not modelled.

### Scheduler interface

See Phase 2 below (the Phase 1 `select_worker(task, idle_p, idle_e)` form
was replaced when the Runtime State Store was added).

### Event log schema

`caosched.core.event_log.EventLogger` writes one JSON object per line to
`data/events/<run_id>.jsonl`, flushed per line, and refuses to overwrite an
existing file. Every record has `seq` (0,1,2,... total order), `t`
(`clock.now()`, the timebase for all interval arithmetic), `timestamp`
(epoch, coarse, for humans only) and `event`:

| event | fields |
|---|---|
| `run_started` | `run_id`, `scheduler`, `scheduler_config`, `metadata` (experiment/trace/repeat), `worker_history` {worker: [[t0, t1], ...] busy intervals in the 2 s before the run}, `n_tasks`, `critical_path_length`, `edges` [[dep, task]...], `tasks` {id: {workload, size, seed}}, `epoch_anchor`, `perf_anchor` |
| `worker_ready` | `worker_id`, `pool`, `pid`, `requested_affinity`, `actual_affinity`, `affinity_ok`, `affinity_error`, `warmup_seconds`, `warmup_error` |
| `task_ready` | `task_id` |
| `task_dispatched` | `task_id`, `worker_id`, `pool`, `queue_wait_seconds`, `worker_load_before`, optional `decision` (policy-specific; EFT: `chosen` + per-worker `wait`/`transfer`/`exec`/`finish`) |
| `task_submitted` | `task_id`, `worker_id`, `local_queue_wait_seconds` |
| `task_completed` | `task_id`, `worker_id`, `pool`, `wall_time_seconds`, `t_started`, `t_completed`, `response_time_seconds` |
| `task_failed` | `task_id`, `worker_id`, `pool`, `t_started`, `t_completed`, `error` |
| `run_error` | `error_type`, `error` |
| `run_finished` | `status`, `n_tasks`, `n_completed`, `makespan_seconds`, `tasks_per_pool`, `total_wall_time_seconds`, `mean_response_time_seconds` |

A log is self-describing: `run_started` contains the full DAG and task specs,
so a run can be replayed or re-analysed from the log alone. This is the raw
record Phase 6's dataset generation derives summary fields from.

## Phase 2: baseline schedulers

### Runtime State Store and binding

`core/runtime_state.py` holds, per worker, the executing task (sent to the
process, with its submit time) and a FIFO **local queue** of tasks bound to
that worker but not yet sent. The coordinator binds each task the policy
selects: an idle worker gets it immediately (`task_submitted`), a busy one
queues it; on every completion the worker's next local task is submitted.

* **Late binding** (`binds_only_idle = True`): the policy may only choose
  idle workers; tasks wait in the global ready queue. B0, B2, B4, B5.
* **Early binding**: the policy may choose any worker; tasks wait in local
  queues. B1, B3, B6, B7 -- required for queue-aware rules and for EFT's
  F(t,w) = wait(w) + transfer(t,w) + exec(t,w).

### Scheduler interface

```
SchedulerPolicy
  name, binds_only_idle, last_decision
  on_run_start(dag, state)          per-run setup (B5 levels, estimator reset)
  order_ready(ready_ids, state)     ready-queue priority (default FIFO; B5: bottom level)
  select_worker(task, state)        worker id or None
  on_task_completed(task)           feedback (B7: history observation)
  describe()                        logged in run_started
```

The coordinator enforces: chosen id exists; late-binding policies choose
only idle workers; `order_ready` returns a subset of the ready ids without
duplicates. `last_decision` (reset before every call) is logged on
`task_dispatched`. Policies get a read-only `RuntimeState` and the
`Task` (workload, size, dependencies) -- never worker handles.

### Estimator interface

`estimators.base.ExecutionTimeEstimator`: `estimate(workload, size, pool)`
(kernel-only seconds), `observe(...)`, `reset()`, `describe()`. EFT holds an
estimator and never knows which one (B6 = E1, B7 = E3 with E1 prior; P in
Phase 4 = E4), satisfying the "swap estimator without touching the scheduler"
principle. Phase 2 ships E1 and E3 only.

### Policy definitions

Exact rules live in the class docstrings of `schedulers/simple.py` and
`schedulers/eft.py` and are summarised in PROJECT_STATUS.md. B4 is a
patent-mapped comparison baseline for US 11,561,826 B1 (eligible-worker,
availability-driven dispatch only -- not an implementation of the patent);
see `docs/B4_PATENT_MAPPING.md` for what is and is not mapped.

### Replayable experiments

A trace (`core/trace.py`) is generated once from a config entry + seed and
saved; each run builds a fresh DAG from it and a fresh policy instance from
the registry, so no state crosses runs. `scripts/run_baselines.py` shuffles
policy order per (repeat, trace) with a recorded seed, shares one warm worker
pool across runs, and writes manifest -> raw runs CSV + per-run event logs ->
derived summary.

## Phase 3: estimator ladder

### Interface and decision-time context

```
ExecutionTimeEstimator
  estimate(task, pool, ctx=None) -> kernel-only seconds
  observe(task, pool, kernel_seconds, ctx=None)
  reset()                         per-run state only
  uses_context                    EFT builds a per-candidate EstimateContext only if True
EstimateContext(busy_P, busy_E, corunning, target_busy_frac)   # excludes the candidate
```

`EstimateContext.from_state(state, candidate)` (online) and
`dataset/events.py` (offline, from event logs) implement the same
definition, so a learned estimator is trained on exactly what it is later
queried with. `target_busy_frac` uses the per-worker activity history kept
on the `WorkerPool` across runs and logged in `run_started`.

### Rungs

| rung | model | fitted on |
|---|---|---|
| E0 | median per (workload, pool) | solo profile raw CSV |
| E1 | median per (workload, size, pool), strict lookup | solo profile |
| E2 | `a[workload,pool] * size^b[workload]`, b from config | solo profile |
| E3 | mean of last k observations per key in the current run, E1 prior | online |
| E4 | `E1 * exp(w . x(ctx))`, ridge per (workload, pool) | randomized campaign, split by run |
| E5 | median of the same task's kernel time in other logged runs | replay logs (offline only) |

### Data and evaluation

Training data comes from a randomized interference campaign
(`RandomOccupancyPolicy`: random concurrency, worker subset, idle gap per
run) logged in the standard event format. Evaluation never splits by random
row: held-out campaign runs (same session), an earlier campaign session, and
the Phase 2 runs (earlier session, DAG-driven occupancy). E3 is replayed
causally. Results and their limits are in PROJECT_STATUS.md; decision
quality (regret) is evaluated in Phase 4.

## Phase 4: predictive scheduling and decision regret

* **P** = `EarliestFinishTimeScheduler` with E4; the same class with E0-E3
  forms the ladder (EFT_E1 = B6, EFT_E3 = B7), and **O** uses E5 built from
  same-session logs. Every EFT decision logs each candidate's predicted
  wait / transfer / exec / finish and, for recalibrated estimators, the
  current per-pool factors.
* **Online recalibration** (`+rc`) multiplies an offline-fitted estimate by a
  per-pool factor learned from the run's own completions, compared against
  the prediction made with the decision-time context (EFT hands that context
  back to `observe`). Scope is per run.
* **Regret** is computed offline from logs for any policy
  (`analysis/decisions.py`): placement regret at the binding moment
  (primary), bind delay, and ready-time regret (secondary). Hindsight
  execution times come from the E5 replay oracle, leave-run-out; worker
  availability comes from the actual log. One-step (myopic) by design.
* `run_phase4.py` runs stage A (online policies, shuffled order) then stage B
  (O), then analyses all logs; `--analyze-only` re-derives the analysis from
  existing logs without new runs.

## Project decisions (2026-10-03, after Phase 4)

* **Kernel-only execution time is the primary target** of every estimator,
  the oracle, and the primary regret. It is not replaced.
* **End-to-end EFT is an explicit ablation**: `EarliestFinishTimeScheduler`
  takes an optional `EndToEndTerms` (measured `prepare()` setup per
  (workload, size, pool) + measured per-task runtime overhead per pool, both
  derived from raw data by `scripts/derive_e2e_terms.py`). With it, every
  task's modelled occupancy is kernel + setup + overhead (+ transfer on
  remote pools). Policies are named `..._e2e`, decisions are logged with
  `"model": "kernel" | "e2e"`, and `analysis/decisions.py` reports placement
  regret against both a kernel-only and an end-to-end (worker-span) hindsight
  yardstick so the two are directly comparable.
* **E4 decision cost is scheduling overhead, measured, not hidden.** `E4f`
  (`InterferenceRidgeFastEstimator`) is an implementation optimization of
  the same model (identical predictions) kept as an ablation; the original
  E4 class and its measurements remain unchanged.

## Phase 5: remote offloading

```
coordinator --TaskMessage--> proxy R0 (pool "R")  --[shim: latency + per-msg + bytes/bw]--> TCP --> node
            <--TaskResult---  (transfer_s, ...)   <--[shim]------------------------------- TCP <-- (kernel, span)
```

* The proxy is an ordinary worker slot to the coordinator (same queues,
  handshake, TaskResult), so schedulers see remote workers only as pool `R`
  plus a transfer term. Local Phase 5 runs put the node on one E core
  (removed from E) and the proxy on the coordinator core; a physical device
  runs the same node and is attached with `RemoteSlot(port=...)`, shim zero.
* `TransferModel` (EFT's transfer term) = configured link delay both ways +
  socket cost measured with the shim at zero (profile `link_calibration`).
  Remote workers are occupied for transfer + execution, so queued remote
  tasks contribute transfer to EFT's wait as well.
* Measured transfer is logged per task (`transfer_s`, `transfer_up_s`,
  `payload_bytes`) and compared to the prediction in the Phase 5 analysis.
* Experiments must interleave what they compare: configurations run one
  after another are confounded by session drift (Phase 5 finding).

## Phase 6: dataset and core experiment matrix

* **Dataset (6A)**: `dataset/build.py` turns every completed run's event log
  into task rows (lifecycle, occupancy context, calibration value, chosen
  prediction) and candidate rows (every EFT candidate's predicted terms),
  with per-source SHA-256 provenance, recorded exclusions, and group-level
  splits (session / run / size / occupancy). Schema: `docs/DATASET.md`.
* **Provenance in logs (from 6B on)**: `run_started.software`
  (version + source SHA-256), `run_started.memory_available_bytes`,
  `task_dispatched.decision_time_s`, `run_finished.scheduling_time_seconds`.
* **Interleaved design (6B)**: one pool containing every resource; each
  block (repeat x trace) runs every condition once in seeded random order;
  remote link conditions are switched per run (`WorkerPool.set_link`);
  local-only EFT variants use `allowed_pools`. Effects are paired within
  blocks and reported with stratified bootstrap 95% CIs
  (`analysis/stats.py`); `run_phase6b.py --analyze-only` re-derives every
  result from raw logs into tagged, never-overwritten files
  (`--block-filter full_repeats|complete_blocks`).

## Design principles carried through every phase

- **Modularity over cleverness.** Scheduler, estimator, and dispatcher are separate,
  independently swappable interfaces from day one, because the entire research
  question depends on being able to isolate "how much does the estimator matter"
  from everything else.
- **Raw data first.** Every component logs raw timestamped events; summaries and
  gate verdicts are derived artifacts, never the primary record.
- **No fabricated numbers.** Every number in any report traces back to an actual
  measurement on this specific machine, with the hardware/software configuration
  that produced it recorded alongside it.
- **Honest negative results.** If Phase 0 shows weak P/E variation, or if a later
  phase shows the learned estimator doesn't beat a simpler one, that is a valid and
  reportable outcome — not a failure to fix by adjusting the experiment until it
  shows the desired result.

## Application workflows (post-Phase 6)

`src/caosched/apps/`: application DAGs whose tasks pass real data.

* `stages.py` holds the stage registry. A stage is decode, then compute, then encode. Only `compute` is recorded as `wall_time_seconds`, the kernel; artifact I/O and codec time are logged separately as `io_s`.
* `artifacts.py` is the artifact store at `data/artifacts/<run>/<task>.bin`. Writes are atomic.
* `image_pipeline.py` contains the tiled image-analysis DAG (4k+4 tasks), a single-process reference, and `verify_output`, which reports an exact match or numeric closeness.
* `Task.params` marks a task as an application stage. `Task.eligible_pools` lists the pools the task may use. The coordinator enforces eligibility as a scheduler contract, and B0–B4 and EFT honour it.
* Local workers read and write artifacts directly. The remote proxy ships the real input bytes (op `stage`) and writes back the returned output.
* Benchmark kernels use the unchanged Phase 1–6 path.
* Remote pools have configurable labels (`RemoteSlot.pool`, e.g. `R_PI`, `R_T4`). Nodes report their capabilities in the handshake.
* `same_clock=False` reconstructs timestamps on the proxy side for devices with a foreign clock.
* See `docs/REMOTE_DEVICES.md` for what is verified and what is not.
