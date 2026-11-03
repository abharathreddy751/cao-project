# Unified dataset (Phase 6A)

Built by `python scripts/build_dataset.py` (code: `src/caosched/dataset/build.py`)
into `data/datasets/<stamp>/`. Every row is derived from a real, logged task
execution on the project machine; **no value is synthesised**. Raw event logs
(`data/events/**`) are only read; each source file's SHA-256 is stored in the
manifest and re-checked by `validate_dataset`.

## Files

| file | content |
|---|---|
| `tasks.csv` | one row per completed task execution (the primary table) |
| `candidates.csv` | one row per worker candidate an EFT policy evaluated at a binding decision (predicted wait / transfer / exec / setup / overhead / finish, and whether it was chosen) |
| `splits.json` | leakage-safe split definitions |
| `manifest.json` | schema version, row counts, sessions, calibration profiles used, every source log with SHA-256 and row count, every excluded log with its reason |

## Provenance and exclusions

* A **run** is identified by `source_log` (the event-log path, unique);
  `run_id` repeats across Phase 5 configurations within one session.
* A **session** (`session_id`) is one experiment block (`experiment_id`),
  i.e. one contiguous period on the machine. Sessions differ measurably (P-core
  drift, Phase 3/4/5 findings), which is why splits are by session.
* Only runs whose log ends with `run_finished` status `completed` are used.
* Excluded (with reason in the manifest): Phase 1 logs (lifecycle timestamps
  from `time.time()`, ~1 ms quantized) and the n=1 smoke runs of Phases 2, 4
  and 5 and the 3-block Phase 6B smoke run `phase6b_20261003T160833` (pipeline
  checks, one of them under a superseded regret definition).
* `calibration_kernel_s` comes from the latest static profile measured at or
  before the row's session (named in `calibration_profile`), i.e. a value
  that was available when the session ran.
* Fields introduced after some logs were written are null for those logs,
  never back-filled: `target_busy_frac` (needs worker history or a window
  fully inside the run), `memory_available_bytes`, `software_version`
  (`"unrecorded ..."`).

## `tasks.csv` columns

| column | meaning |
|---|---|
| row_id | row index in this build |
| source_log, source_kind | event-log path; `campaign` / `phase2` / `phase4` / `phase5` / `phase6b` |
| experiment_id, session_id | experiment block (session) |
| scenario | configuration / condition (Phase 5: e.g. `remote_lan_1g`) |
| run_id, trace, repeat, order_index | run name, workload trace, repeat index, position in the shuffled order |
| order_randomized | run order was randomized within its block (scheduling experiments) |
| randomized_campaign | row comes from a randomized profiling campaign (random concurrency / worker subset / idle gap) |
| policy, policy_binding | scheduler name; `late` (binds idle workers only) or `early` |
| estimator, eft_model | EFT estimator name; `kernel` or `e2e` (end-to-end ablation); null for non-EFT |
| task_id, workload, size, seed | task identity (seed = deterministic input seed) |
| input_bytes, output_bytes | payload sizes per the workload data (`remote.link.payload_bytes`) |
| origin | where the task was submitted from (`coordinator` for all current data) |
| worker_id, pool, logical_processor | executing worker, pool (`P`, `E`, `R`), its pinned logical processor (readback) |
| timestamp_epoch | wall-clock start (epoch s, from the run's epoch/perf anchor; coarse) |
| t_ready_rel ... t_completed_rel | lifecycle times relative to run start (QPC seconds) |
| queue_wait_s | ready -> bound to a worker (global ready queue) |
| local_queue_wait_s | bound -> sent to the worker (worker-local queue, early binding) |
| dispatch_to_start_s | sent -> started (IPC; for `R` includes the upstream transfer) |
| kernel_s | **primary target**: timed kernel only (`wall_time_seconds`) |
| worker_span_s, setup_s | prepare + kernel on the worker; span - kernel (input generation) |
| transfer_s | remote only: measured round-trip link time excluding the node span |
| response_time_s | ready -> completed |
| busy_P, busy_E, busy_R, busy_total | other workers executing at this task's start, per pool |
| corun_* | those co-running tasks by workload type |
| target_busy_frac | this worker's busy fraction in the 0.5 s before the start (null if unknown) |
| calibration_kernel_s, calibration_profile | solo static-profile median for (workload, size, pool) and its source |
| predicted_exec_s, predicted_wait_s, predicted_transfer_s, predicted_finish_s | EFT's prediction for the chosen worker at decision time |
| pred_margin_s | second-best minus best predicted finish over all candidates |
| n_candidates | candidates evaluated |
| link_name | Phase 5 link condition |
| memory_available_bytes, software_version | recorded from Phase 6B on; null / "unrecorded" before |
| hardware_id | machine description |

## Splits (`splits.json`)

Never random row-level splits: rows of one run share session state and
co-runner context, so a random split leaks.

* `by_session` -- train on randomized profiling campaign sessions, test on
  scheduling-experiment sessions (the brief's preferred session/time split).
* `by_run_within_latest_campaign` -- first 70% of the latest campaign's runs
  (collection order) train, the rest test (same split as Phase 3's E4).
* `by_size` -- per workload, smallest profiled size train, largest test.
* `by_occupancy` -- busy_total <= 4 train, >= 5 test.

`by_size` and `by_occupancy` are extrapolation axes defined at row level;
combine them with `by_session` (train rows from train sessions only) to avoid
same-run leakage.

## Builds and coverage (verified 2026-10-04)

| build | task rows | candidate rows | runs | excluded logs | sessions |
|---|---|---|---|---|---|
| `20261003T160059` | 53,109 | 218,283 | 1,039 | 187 | campaign x2, phase2, phase4, phase5 |
| `20261003T210952` (**latest**) | 145,378 | 754,141 | 2,472 | 242 | the above + `phase6b_20261003T162145` (92,269 rows; its 1 interrupted run is EXCLUDED as "run not completed") |

## Sessions not yet included

* **Application-demo sessions (`appdemo_*`) are NOT in any build.** That
  includes the four accepted workload-intensity sessions
  (`appdemo_20261004T185921` k=1, `appdemo_20261003T213900` k=4,
  `appdemo_20261004T185801` k=16, `appdemo_20261003T214453` k=64). They were
  logged after build `20261003T210952`. The current builder would not add
  them: `classify()` recognises only `campaign_`, `phase2_`, `phase4_`,
  `phase5_` and `phase6b_` directories and EXCLUDES all 141 `appdemo_*` logs
  as "unrecognised source directory". A rebuild on 2026-10-04 confirmed this.
* Including them requires a builder change (NOT IMPLEMENTED). Open design
  decisions:
  - a new `source_kind`;
  - excluding each session's 6 pool-pinned `profile_*` runs, or labelling
    them separately;
  - keeping the Phase A classifications (accepted / interrupted EXCLUDED /
    verification only) instead of one generic reason;
  - `calibration_kernel_s`: the `img_*` stages have no entry in the
    `*_profile.json` profiles (their `.appprofile.json` files are not
    matched), so it would be null;
  - `corun_*`: only counts the three benchmark workloads, so `img_*`
    co-runners would not appear in it.

## Audit of 2026-10-04 (records: `data/results/dataset_audit_20261004/`)

* VERIFIED (both builds, read-only, `audit_dataset.py`):
  - Headers equal `TASK_FIELDS` (60 columns) and `CAND_FIELDS` (17).
  - Row counts equal the manifest overall, per source (2,472 / 1,039),
    per kind and per session.
  - `row_id` is contiguous; `(source_log, task_id)` has no duplicates.
  - No invalid values: kernel > 0; ready ≤ dispatched ≤ started ≤
    completed; pools in P/E/R; `transfer_s` present exactly for R rows;
    setup ≥ 0; `busy_total` = P + E + R; `target_busy_frac` in [0, 1].
  - No calibration profile postdates its session.
  - Every candidate links to a task. There is one decision per EFT task and
    exactly one chosen candidate per decision; the chosen candidate equals
    the executing worker and its `pred_finish_s`; candidate counts equal
    `n_candidates` (89,866 decisions in the latest build).
  - Nulls occur only where documented: non-EFT predictions,
    `transfer_s` (non-R), `memory_available_bytes` (pre-6B),
    `target_busy_frac` (unknown), `link_name`, `scenario`, and
    `repeat` / `order_index` (campaign).
* VERIFIED provenance: every source log's SHA-256 still matches
  (1,039/1,039 and 2,472/2,472); both builds' files are unchanged.
* VERIFIED reproducibility: the current builder, run into a scratch
  directory, reproduced `tasks.csv`, `candidates.csv` and `splits.json` of
  `20261003T210952` **byte-identically**. The manifest differs only in
  `built_at` and the 141 new `appdemo_*` exclusions; every earlier exclusion
  keeps its reason. This holds although `remote/link.py` and
  `apps/stages.py` were edited after that build.
* Splits (VERIFIED as defined; findings):
  - `by_session` train and test are disjoint and cover every session.
    Train = 12,000 campaign rows; test = 133,378 scheduling rows. No test
    row reuses a train input `(workload, size, seed)`.
  - `by_run` (140 / 60 runs of the latest campaign) is disjoint at the run
    level.
  - `by_size` uses a different size for train and test. Every workload has
    only 2 sizes, so it tests a single extrapolation step.
  - Train and test contain the same 3 workloads (compression,
    image_filter, matmul), so **no split measures generalisation to unseen
    workloads**.
  - `by_size` and `by_occupancy` are row-level and leak within a run unless
    combined with `by_session`, as already documented.
* Feature availability at decision time (finding; no repair):
  - `busy_*`, `corun_*` and `target_busy_frac` are reconstructed at task
    **start** (intentional; tested by
    `test_context_reconstructed_at_task_start`), not at the dispatch
    decision.
  - Measured against a dispatch-time reconstruction from the same rows,
    the co-runner count differs in **42.1%** of late-binding rows
    (dispatch→start gap median 0.52 ms; mostly +1 to +3, from tasks
    dispatched in the same burst) and **81.4%** of early-binding rows (gap
    median 7.6 ms, p90 134 ms).
  - In **46,229** early-binding rows, `target_busy_frac` includes an
    own-worker task that completed **after** the dispatch decision. This is
    information the scheduler did not have; it is 0 for late binding.
  - The online scheduler's own context (`EstimateContext.from_state`) is
    not logged, so exact train/serve parity cannot be VERIFIED.
  - Columns observed after the decision (outcomes, never decision-time
    features): `kernel_s` (target), `worker_span_s`, `setup_s`,
    `t_started_rel`, `t_completed_rel`, `dispatch_to_start_s`,
    `local_queue_wait_s`, `transfer_s`, `response_time_s`,
    `timestamp_epoch`.
* Tests: `tests/test_dataset.py` and `tests/test_dataset_build.py`, 8
  passed (EXECUTED and VERIFIED, 2026-10-04).

## Known gaps

* Memory state was not recorded before Phase 6B (`memory_available_bytes`
  null); CPU frequency is not observable through psutil on Windows.
* Remote rows come from one E core behind an emulated link; payload content
  is a stand-in buffer of the correct size (see PROJECT_STATUS.md, Phase 5).
