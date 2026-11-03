# Project Status

Last updated: 2026-10-03 (session 2: Phases 1-6; Phase 6 dataset + core experiment matrix)

## Hardware (this machine)

- HP 15s, Intel Core i5-1235U, 2 Performance + 8 Efficiency cores, 12 logical
  processors, 8 GB RAM, Intel UHD Graphics, Windows 11, 512 GB SSD.
- Confirmed via `Get-CimInstance Win32_Processor`: "12th Gen Intel(R) Core(TM)
  i5-1235U", NumberOfCores=10, NumberOfLogicalProcessors=12 (matches 2P+8E, P-cores
  with SMT, E-cores without SMT).
- Python: 3.11.9 at `C:\Program Files\Python311\python.exe` (project venv target).
  A separate 3.9.13 install also exists on this machine but is not used by this
  project.

## Completed work

### Repository scaffolding
- Repository scaffolded at `D:\cao project` (was empty at session start).
- `ARCHITECTURE.md` written: full system diagram, module responsibilities, Phase 0
  technical approach, directory layout, cross-phase design principles.
- Packaging: `pyproject.toml` (src layout, `caosched` package), `requirements.txt`
  (numpy, pillow, psutil, pyyaml, pandas, pytest — deliberately lightweight),
  installed editable (`pip install -e .`) into `.venv` (Python 3.11.9).

### Phase 0 — COMPLETE and validated on real hardware

**`caosched.phase0.topology`** — P/E-core + SMT-sibling discovery via the Windows
`GetSystemCpuSetInformation` API (ctypes), cross-checked against WMI. **Caught and
fixed a real bug during validation**: the first struct definition declared the
trailing `SchedulingClass`/`AllocationTag` fields as two sequential `uint64`s: the
real Win32 struct has them as a *union* (one 8-byte slot). This overcounted the
per-entry size as 40 bytes instead of the true 32, which silently dropped the last
logical processor from the enumeration (11 found instead of 12) with no error
raised. Found by writing a throwaway diagnostic script that dumped raw entry
headers, confirmed by checking `raw_len_bytes / entry_size` against `os.cpu_count()`.
Fixed, re-validated, and pinned with a regression test
(`tests/test_topology.py::test_parse_cpu_set_buffer_matches_real_32_byte_entry_size`)
that hand-packs a synthetic 32-byte-entry buffer independent of the struct
definitions under test, so the bug class cannot silently return. Confirmed final
topology on this machine:
  - P-cores: logical processors `{0,1}` (physical core 0) and `{2,3}` (physical
    core 2) — 2 physical P-cores × 2 SMT threads = 4 logical processors.
  - E-cores: logical processors `{4,5,6,7,8,9,10,11}` — 8 physical E-cores, no SMT.
  - Cross-check: `os.cpu_count()` = topology count = WMI
    `NumberOfLogicalProcessors` = 12, all consistent. `NumberOfCores` (WMI) = 10 =
    2 P + 8 E physical cores. Matches the hardware brief exactly.

**`caosched.phase0.env_record`** — environment JSON record generator. Verified
output includes: topology (above), WMI cross-check, RAM (8,245,321,728 bytes ≈
7.68 GiB, consistent with "8 GB RAM" after OS/firmware reservation), OS
(Windows 10.0.26100, edition CoreSingleLanguage — i.e. Windows 11 Home Single
Language per the `release`/`version` numbering), Python 3.11.9, **CPU affinity
support confirmed working** (set + readback test passed), and the planned worker
pool mapping: P-core slots = `[0, 2]` (one logical processor per physical P-core),
E-core slots = `[5,6,7,8,9,10,11]` (7 slots), coordinator reserved core = `4` —
exactly matching the brief's "2 P-core worker slots, 7 E-core worker slots, 1
E-core reserved for coordinator/OS."

**`caosched.util.threadpin`** — pins `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`,
`BLIS_NUM_THREADS` to `1`, called at module-import time in the subprocess worker
(`benchmarks/worker.py`) so it runs before numpy is ever imported in that process.

**`caosched.phase0.benchmarks`** — workloads (matmul via numpy, image filter via
Pillow Gaussian blur, compression via zlib), each split into `prepare()`/`run()`
so only the compute kernel is timed; a subprocess worker entry point
(`worker.py`) that runs as a fresh `multiprocessing` (spawn) process per
measurement so CPU affinity and thread-pinning apply cleanly; a harness
(`harness.py`) implementing K1 (P vs E, no load), K2 (P-core task under
increasing E-core load), and K5 (P-core SMT-sibling interference); and a gate
analysis module (`analysis.py`) with a fixed, pre-declared 15% relative-difference
threshold for "meaningful" variation.

**Scripts**: `phase0_characterize.py`, `phase0_benchmark.py` (`--quick` flag for
fast iteration), `phase0_gate_report.py` — all run successfully end-to-end.

**Tests**: 10 tests, all passing (`pytest`, 0.28s) — topology parser regression
test (above), truncated-buffer handling, a real-machine integration test, and
workload determinism/no-raise tests for all three workload kernels.

### Phase 0 gate decision — ACTUAL RESULT (not fabricated; see
`data/benchmarks/20261002T224247_60b468ab.csv` and
`data/reports/20261002T224247_60b468ab_gate.json` for raw data and full report)

Ran the `--quick` suite (small sizes, 5 repeats + 2 warmups per condition) on this
machine. Results:

| Scenario | Comparison | Result |
|---|---|---|
| K1 (matmul, N=128) | P vs E | P 0.266ms vs E 0.517ms → **48.5% faster on P** |
| K1 (matmul, N=256) | P vs E | P 1.416ms vs E 3.005ms → **52.9% faster on P** |
| K1 (image_filter, 256px) | P vs E | P 3.471ms vs E 4.792ms → **27.6% faster on P** |
| K1 (compression, 256KB) | P vs E | P 1.178ms vs E 1.852ms → **36.4% faster on P** |
| K2 (matmul, N=192) | 0 vs 4 loaded E-cores | 0.592ms → 0.926ms → **36.1% slower under load** |
| K5 (matmul, N=192) | P-core alone vs SMT sibling busy | 0.642ms → 1.294ms → **50.4% slower** |

**Verdict: execution time varies meaningfully (all six comparisons exceed the 15%
threshold) across P/E pools, under E-core load, and under SMT-sibling contention
on this machine. Proceeding with estimator ladder development (E0–E4) is
justified by real data, not assumed.** The K2 and K5 results are a genuinely
useful finding for Phase 3/4: a P-core task's execution time is not fixed even
when it stays on the same core — it depends measurably on system occupancy,
which is exactly the kind of signal E4 (interference-aware estimator) is meant
to exploit and which simpler static estimators (E0/E1) cannot see.

**Caveat for future sessions**: the above used `--quick` mode (small
problem sizes, short 15s load windows, 5 repeats). This is sufficient to answer
the Phase 0 gate question (does variation exist at all?) but the full suite
(`phase0_benchmark.py` without `--quick`: larger sizes, 10 repeats, 30s load
windows) should be run before treating these specific numbers as the final
reported Phase 0 dataset for the thesis.

### Phase 1 — core runtime — COMPLETE, hardened, validated on real hardware

Implements the DAG Manager / Ready Queue / Worker Pools / Coordinator /
Dispatcher / Event Logger boxes from `ARCHITECTURE.md`. Scheduler and
Estimator boxes remain placeholders (Phase 2 / Phase 3).

**History.** A first pass (session 1) delivered a working pipeline. Session 2
audited it component by component against the 10-item Phase 1 brief and found
real gaps, all now fixed and covered by tests:

| Component | Gap found in session-1 code | Fix (session 2) |
|---|---|---|
| Task | `TaskResult` defined but unused (raw tuples over IPC); no transition checks | `TaskMessage`/`TaskResult` used end to end; `Task.transition()` rejects illegal state changes; input validation |
| DAG / deps | Cycles accepted at construction (surfaced later as opaque "Deadlock"); key/id mismatch, double completion, unknown id silently accepted; O(deps) rescan per completion | Kahn's-algorithm validation at construction (`CycleError` names the tasks); remaining-dependency counters; `topological_order()`, `critical_path_length()` |
| Ready queue | Bare `deque` inside the coordinator | `core/ready_queue.py` (`ReadyQueue`, FIFO, overridable `ordered()` for Phase 2) |
| Worker pools / affinity | Affinity failure swallowed with `pass`, never read back; no startup handshake (cold start landed on first timed task) | Startup handshake: set affinity, **read back**, report requested vs. actual; optional warmup of every workload before any timed task; `strict_affinity` mode; dead-worker detection; busy/unknown-worker submit rejected |
| Coordinator | **Hung forever if a worker died** (poll returned None, loop retried); no run timeout | Explicit, fail-fast errors: `TaskFailedError`, `WorkerPoolError` (dead worker), `RunTimeoutError`, `DeadlockError`; returns `RunSummary` |
| Dispatch | Scheduler's returned worker id trusted blindly | Must be one of the idle ids offered, else `SchedulerContractError` |
| Completion | Tuple unpacking; no check that result matches assignment | Result validated against the worker's current assignment; `on_task_completed` feedback hook for future online estimators |
| Event log | No run/worker events; overwrote existing logs | `run_started` (DAG edges, task specs, clock anchor), `worker_ready` (affinity readback, warmup time), `task_failed`, `run_error`, `run_finished`; `seq` field; refuses to overwrite an existing log |
| Config | Core mapping re-derived ad hoc in script | `core/runtime_config.py`: `RuntimeConfig.from_topology()` wraps Phase 0's `planned_worker_pool_config` (single source of truth) |

**Real bug found during validation — clock resolution.** Decomposing the
session-2 event logs showed cross-process intervals quantized to exactly 0
or ~1 ms, and some tasks' recorded `t_completed - t_started` *shorter* than
the `perf_counter`-timed kernel inside it (physically impossible). Cause,
confirmed with `time.get_clock_info` on this machine: CPython 3.11 on Windows
implements `time.time()` with `GetSystemTimeAsFileTime` (nominal 15.6 ms
resolution, observed steps ~0.5 ms) and `time.monotonic()` with
`GetTickCount64` (15.6 ms). `time.perf_counter()` is `QueryPerformanceCounter`
(100 ns) and is system-wide: a spawned child's reading fell inside the
parent's before/after bracket in 3/3 trials. All lifecycle timestamps now use
`caosched.util.clock.now()` (= `perf_counter`); each event also carries `t` on
that timebase, and `run_started` records an (epoch, perf) anchor. Pinned by
`tests/test_clock.py` and a causal-consistency regression test
(`t_completed - t_started >= kernel time` for every task). **Consequence: the
session-1 event logs (`data/events/phase1_{independent,chain,fork_join,mixed}.jsonl`)
and the first two session-2 runs (`phase1_20261003T112949_*`,
`phase1_20261003T112952_*`) have ~1 ms-quantized timestamps and must not be
used for interval analysis.** They are left on disk unmodified as raw records.

**Validation run on this machine** (`python scripts/run_dag.py --size 256`,
logs `data/events/phase1_20261003T113132_*.jsonl`):

```
Runtime config (from Phase 0 topology): p_core_slots [0, 2], e_core_slots [5..11], coordinator_core 4
Coordinator pinned to core: 4
9 workers, every one: requested affinity == actual affinity (readback); warmup 0.12-0.18 s each
[independent] completed -- 9/9 tasks,  makespan  8.08 ms, per-pool {'P': 2, 'E': 7}
[chain]       completed -- 5/5 tasks,  makespan 11.60 ms, per-pool {'P': 5}
[fork_join]   completed -- 10/10 tasks, makespan 10.21 ms, per-pool {'P': 4, 'E': 6}
[mixed]       completed -- 7/7 tasks,  makespan 13.35 ms, per-pool {'P': 7}
```

Per-task latency decomposition from those logs (matmul N=256; small n, so
these are characterisation numbers, not thesis results):

| Interval | chain (n=5) median [min, max] | independent (n=9) median [min, max] |
|---|---|---|
| dispatch -> worker start (IPC out) | 0.211 ms [0.187, 0.319] | 0.275 ms [0.212, 0.494] |
| in-worker, untimed (`prepare()` input generation) | 1.112 ms [1.009, 1.200] | 1.581 ms [1.218, 1.668] |
| kernel (timed, `wall_time_seconds`) | 0.697 ms [0.601, 0.828] | 1.925 ms [0.891, 2.174] |
| worker done -> coordinator logs (IPC back) | 0.242 ms [0.143, 0.295] | 0.318 ms [0.209, 0.685] |
| completion -> next dispatch (coordinator) | 0.088 ms [0.081, 0.126] | — |

Observations (all from the logs above, nothing extrapolated):
- Runtime overhead per dependency hop is ~0.5 ms (IPC out + IPC back +
  coordinator bookkeeping). For kernels in the sub-ms range this is the same
  order as the work itself — relevant for Phase 7's K4 overhead experiment
  and for choosing task sizes where scheduling decisions can matter at all.
- `prepare()` (synthetic input generation) runs inside the worker, is *not*
  part of `wall_time_seconds`, but *is* part of makespan — at N=256 it is
  larger than the kernel. Phase 2+ must decide explicitly whether task
  "execution time" means kernel-only or prepare+kernel (see Next work).
- Kernel time by pool in the `independent` run: P median 1.012 ms (n=2), E
  median 1.979 ms (n=7) — same direction and similar ratio as Phase 0's K1
  matmul result; n is far too small to be more than a sanity check.
- Cold start: with the warmup handshake, the first DAG run's makespan is no
  longer dominated by import cost (session 1: 2.0 s on cold workers;
  session 2: 8 ms after warmup). The two numbers are not a controlled
  comparison (OS file cache state differs between sessions); the point is
  only that warmup cost is now paid and *recorded* (`worker_ready.warmup_seconds`)
  outside the timed run.

**Placeholder scheduler.** `RoundRobinScheduler` (logged as
`phase1_placeholder_first_idle`; despite the name it takes the first idle
worker, P first) exists only to exercise the pipeline. **Not a B0-B7 baseline.**

**Tests**: 70 total, all passing, stable over 4 consecutive runs (~4.4 s
each). Phase 1 tests (60) run real spawned processes, real affinity calls
with readback, and real queues — nothing is mocked. Highlights: cycle
detection (incl. a cycle behind a valid prefix); "every task unlocked exactly
once" under 20 random completion orders; impossible-affinity detection
(strict mode rejects it); worker killed mid-task -> `WorkerPoolError` instead
of a hang; run timeout; scheduler contract violation; deadlock detection;
failing task logged and fails fast; event log reconstructs the schedule
(dispatch order respects every DAG edge); clock causal-consistency regression.

### Project decision: execution time = kernel-only (2026-10-03)

Decided by the project owner after Phase 1 surfaced the question: a task's
"execution time" -- what every estimator predicts, what profiles and history
record, what the oracle will use -- is the **timed kernel only**
(`wall_time_seconds`: the workload's `run()`, excluding `prepare()` input
generation and runtime overhead). Both quantities remain logged. Measured
consequence (below): `prepare()` is ~30% of a worker's per-task time in the
Phase 2 traces, so EFT's wait estimates exclude it by construction.

### Brief recovered into the repository

B0-B7 / E0-E5 were referenced throughout the repo but never defined in it
(only in the session-1 instructions). The brief is now saved verbatim at
`docs/PROJECT_BRIEF.md` and is the authoritative specification.

### Phase 2 — baseline schedulers B0-B7 — COMPLETE, validated on real hardware

**Runtime extension: Runtime State Store** (`core/runtime_state.py`, the
diagram box that Phase 1 had not built). Per-worker local queues make two
binding styles possible: *late binding* (policy picks only idle workers; B0,
B2, B4, B5) and *early binding* (policy may queue a task behind a busy
worker; B1, B3, B6, B7). Without it, "shortest queue" and EFT's wait term
would be identically zero. Scheduler interface became
`select_worker(task, state)` + `on_run_start` / `order_ready` /
`on_task_completed` hooks; binding contract enforced by the coordinator.
New events: `task_submitted` (sent to worker; `local_queue_wait_seconds`) and
a `decision` payload on `task_dispatched` (EFT: every candidate's wait /
transfer / exec / finish). Phase 1 placeholder renamed `FirstIdleScheduler`
(it never was round robin); `B1_round_robin` is now a real policy.

**Policies** (`src/caosched/schedulers/`; exact rules in class docstrings):

| Name | Rule (as implemented) | Binding |
|---|---|---|
| B0_P_only / B0_E_only | single pool, first idle worker | late |
| B1_round_robin | fixed cyclic order over all workers, busy or not | early |
| B2_static_mapping | workload -> pool from config (matmul -> P, others -> E) | late |
| B3_shortest_queue | fewest bound tasks, P-first tie-break | early |
| B4_greedy_eligible | first idle eligible worker, pool priority P > E | late |
| B5_criticality | bottom-level priority; critical-path tasks -> P, non-critical -> E (P only if no critical task waiting) | late |
| B6_eft_static | argmin F = wait + transfer(0) + exec, exec from E1 static profile | early |
| B7_eft_history | same, exec from E3 moving history (window 8, E1 prior) | early |

**B4 patent mapping (resolved 2026-10-03).** The owner identified the patent:
US 11,561,826 B1, "Scheduling processing of machine learning tasks on
heterogeneous compute circuits" (Xilinx, granted 2023-01-24). B4 is a
**patent-mapped comparison baseline, not an implementation of the patent**.
Mapped: per-task eligibility (task assigned to one or more kernel types /
compute circuits) and availability-driven, eligibility-gated dispatch with no
performance model. Our additions: P-before-E priority among idle eligible
workers; one global FIFO ready queue instead of per-kernel queues. Not
implemented: kernel objects, accelerators, blocking/non-blocking kernels and
wait threads, buffer passing, job pipelining, utilization-triggered thread
scaling, anything claim-level (claims text was not retrieved). Full mapping
with verbatim source excerpts: `docs/B4_PATENT_MAPPING.md`. B4's dispatch
behaviour is unchanged (docstring + logged `scheduler_config.patent_mapping`
only), so Phase 2 was not rerun and its B4 results stand.

**Estimators needed by B6/B7** (`src/caosched/estimators/`; Phase 3 adds the
rest of the ladder behind the same interface): E1 `StaticProfileEstimator`
(strict lookup; unprofiled keys raise before the run starts) and E3
`MovingHistoryEstimator`.

**Static profile** (`scripts/profile_static.py`, raw
`data/profiles/20261003T115606_raw.csv`, derived
`data/profiles/20261003T115606_profile.json`): 1,242 solo measurements (one
task in flight machine-wide) over every worker slot, 3 warmup + 20 measured
rounds, seeded random order. Kernel-only medians:

| workload | size | P median (ms) | E median (ms) | E/P |
|---|---|---|---|---|
| matmul | 256 | 0.796 | 1.761 | 2.21 |
| matmul | 512 | 5.136 | 13.083 | 2.55 |
| image_filter | 512 | 5.549 | 9.455 | 1.70 |
| image_filter | 1024 | 23.236 | 43.871 | 1.89 |
| compression | 1 MiB | 3.387 | 5.490 | 1.62 |
| compression | 4 MiB | 13.205 | 21.825 | 1.65 |

n = 40 per P entry, 140 per E entry. Workers within a pool are homogeneous
when solo (E per-worker medians within ~2%, P within ~5%), so pool-level
entries are justified; the P pool has a wider p10-p90 band. Matmul has the
largest P advantage, consistent with Phase 0 K1 and with B2's config mapping.

**Traces** (`core/trace.py`, saved to `data/traces/`): seeded, JSON,
replayed as a fresh DAG per run; a saved trace that no longer matches its
config entry is refused. `layered_mixed` (80 tasks, 8 layers),
`independent_mixed` (60), `forkjoin_mixed` (53; 4 stages x 12 branches);
workloads mixed 1:1:1 over the profiled sizes.

**Experiment** `phase2_20261003T115816` (`scripts/run_baselines.py`; raw
`data/results/phase2_20261003T115816_runs.csv`, per-run event logs in
`data/events/phase2_20261003T115816/`, manifest + derived summary alongside):
3 traces x 9 policies x 5 repeats = 135 runs, all completed; policy order
shuffled per (repeat, trace) with a recorded seed; one warm pool, coordinator
pinned to core 4, strict affinity.

Median makespan (ms) [min-max over 5 repeats], ratio to best median:

| policy | layered_mixed | independent_mixed | forkjoin_mixed |
|---|---|---|---|
| B0_P_only | 671.0 [615-713] x1.58 | 401.8 [378-450] x2.24 | 609.2 [563-617] x1.64 |
| B0_E_only | 448.7 [408-500] x1.06 | 210.9 [204-243] x1.17 | 425.9 [411-475] x1.15 |
| B1_round_robin | 439.5 [413-515] x1.04 | 216.7 [209-276] x1.21 | 605.2 [542-627] x1.63 |
| B2_static_mapping | **423.4** [392-472] x1.00 | 190.5 [181-229] x1.06 | 407.6 [372-442] x1.10 |
| B3_shortest_queue | 443.3 [432-484] x1.05 | 218.4 [210-276] x1.22 | 432.7 [394-479] x1.16 |
| B4_greedy_eligible | 447.2 [404-491] x1.06 | **179.6** [179-218] x1.00 | **371.5** [351-447] x1.00 |
| B5_criticality | 431.1 [375-459] x1.02 | 186.5 [179-200] x1.04 | 403.1 [361-430] x1.08 |
| B6_eft_static | 433.8 [412-471] x1.02 | 192.1 [182-209] x1.07 | 385.7 [371-409] x1.04 |
| B7_eft_history | 442.1 [387-485] x1.04 | 185.9 [180-206] x1.04 | 400.7 [357-419] x1.08 |

What the data supports (and does not):
- Robust: B0_P_only is worst on every trace (2 slots cannot offset losing
  7); B1 round robin is as bad as P-only on fork-join (blind rotation queues
  branches behind slow tasks the join must wait for); B0_E_only, B1 and B3 are
  consistently behind the best group on `independent_mixed`.
- **Not supported: any ranking within the top group (B2, B4, B5, B6, B7).**
  They lie within ~2-10% of each other with heavily overlapping min-max
  ranges; the winner differs per trace (B2, B4, B4) and differed again in the
  n=1 smoke run (`phase2_20261003T115741`, pipeline check only -- not a
  result). **The EFT baselines did not beat simple greedy dispatch (B4) in
  this setting.** n=5 is a Phase 2 validation run, not the thesis
  experiment (Phase 7: more repeats, statistical tests).
- Bounded headroom: B0_E_only is only 6-17% behind the best policy. Adding
  2 P slots that are 1.6-2.5x faster to 7 E slots raises ideal capacity by
  (7 + 2 x 1.6..2.5) / 7 - 1 = ~46-71% for perfectly parallel work; DAG
  structure, `prepare()` time and runtime overhead consume much of that.
  This bounds how large any prediction-driven gain can be on this machine.

Diagnostics from the n=1 smoke logs (B6 runs; diagnostic, not results):
- **Interference:** observed kernel time under concurrent load was a median
  1.15-1.41x the solo-profile prediction (range 1.00-2.58x) depending on
  trace/pool -- consistent with Phase 0 K2. E1 cannot see this; it is the
  signal E3 partially and E4 (Phase 3) explicitly target.
- **Prepare share:** untimed `prepare()` is a median ~30% of each worker's
  per-task span, across policies -- excluded from EFT's model by the
  kernel-only decision.

**Tests**: 103 total, all passing (2 consecutive runs, ~4.6 s). New in
Phase 2: `test_runtime_state.py`, `test_schedulers.py` (decision logic of
every policy incl. EFT queue-vs-idle trade-off, B5 critical-path rule, B7
learning, registry freshness, profile metric check), `test_trace.py`
(determinism, validity, shapes, stale-trace refusal), and a parametrized
`test_coordinator.py` case running **every** policy through the real
coordinator + worker processes, checking dependency order, no worker ever
running two tasks at once, pool restrictions, logged EFT decisions, and that
early-binding policies really queue.

### Phase 3 — estimator ladder E0-E5 — COMPLETE (offline accuracy); validated on real hardware

**Implemented** (`src/caosched/estimators/`, `src/caosched/dataset/`):
- Interface `estimate(task, pool, ctx)` / `observe(...)` / `reset()`;
  `EstimateContext` = decision-time snapshot excluding the candidate worker
  (busy_P, busy_E, co-running workload counts, candidate's recent busy
  fraction). EFT builds it per candidate only for estimators that use it,
  so B6/B7 behaviour is unchanged (Phase 2 not rerun).
- E0 constant per (type, pool) | E1 static profile lookup | E2 analytic
  `a*size^b` (exponents 3/2/1 from config) | E3 moving history (window 8,
  E1 prior) | E4 learned interference ridge (multiplicative correction of
  E1, one model per (workload, pool), numpy only; feature sets
  `occupancy` and `occupancy+history`) | E5 replay oracle (same task in
  other logged runs, leave-run-out; offline only). `build_estimator()`
  registry pairs any online rung with EFT.
- Offline rows from any event log with the same context definition as
  online (`dataset/events.py`); unknown history is `None`, never guessed.
- Runtime additions (non-breaking): per-worker activity history persisted
  on the pool and logged as `run_started.worker_history`; policy hook
  `retry_after` (deliberate idling); data-collection policy
  `RandomOccupancyPolicy` (random concurrency, worker subset, idle gap).

**Data collected (all raw, under data/):**
- Campaign 1 `campaign_20261003T121528` (12:15): 200 runs x 30 tasks,
  random concurrency 1-9 and worker subsets, no idle gaps, no worker
  history (predates the field).
- Campaign 2 `campaign_20261003T144004` (14:40): same design plus random
  per-run idle gaps (0-200 ms) and logged worker history. E4 trained on its
  first 140 runs (by collection order), last 60 held out.
- Diagnostics `data/diagnostics/solo_patterns_20261003T121757.csv` and
  `..._20261003T144336.csv` (identical protocol, ~2.5 h apart).
- Models `data/models/e4_20261003T144301_occupancy_history.json` and
  `e4_20261003T144302_occupancy.json`.

**Findings on this machine:**
1. *Load inflation.* Under concurrent load, kernels run well above the solo
   profile (Phase 2 logs: actual/E1 median 1.46 P, 1.39 E for tasks started
   on a continuously busy worker).
2. *P-core idle penalty (reproduced).* One task in flight machine-wide,
   50 ms machine-idle gap before each P0 task: median 1.291x (p90 2.24x) at
   12:17 and 1.268x (p90 2.06x) at 14:43. Hypothesis (not directly
   observable: psutil reports no usable frequency on Windows): power
   management lowers an idle core's performance state.
3. *P-core session drift.* Back-to-back P0 went from 1.003x (12:17) to
   1.122x (14:43) of the profile; E-cores stayed at 1.01-1.02x. Campaign 1
   ran globally slower under load than campaign 2 (E4 occupancy-only
   intercepts 0.17-0.45 vs 0.01-0.10 log; train RMSE 0.28-0.32 vs
   0.09-0.20). **Correction:** an earlier statement here that drift since
   profiling was "ruled out" held only within one ~10-minute window; across
   hours, P-core performance drifts.

**Offline accuracy** (`scripts/evaluate_estimators.py`; raw
`data/results/phase3_20261003T144523_predictions.csv`, summary JSON
alongside). Median absolute % error (median signed error in brackets):

| estimator | c2 held-out (same session, 1,800 tasks) | c1 (earlier session, 6,000) | phase2 (earlier session, DAG runs, 8,685) |
|---|---|---|---|
| E0 constant | 63.1% (-6%) | 66.4% (-36%) | 67.3% (+61%) |
| E1 static profile | 7.8% (-8%) | 32.3% (-32%) | 27.9% (-28%) |
| E2 analytic | 8.2% (-8%) | 31.3% (-31%) | 27.2% (-27%) |
| E3 moving history | **5.9%** (-3%) | 22.8% (-15%) | **9.3%** (-6%) |
| E4 occupancy+history | 6.2% (+1%) | **19.8%** (-19%) | 12.9% (-12%) |
| E4 occupancy only | 6.0% (+1%) | 19.8% (-19%) | 13.1% (-12%) |
| E5 replay oracle | n/a | n/a | 8.4% (0%) |

What this supports:
- Size information is essential (E0 ~65% error vs E1 ~8% in-session).
- Every *offline-fitted* estimator (E1, E2, E4) is biased low on earlier
  sessions (-12% to -32%); session drift dominates their error. E3, which
  re-learns within the run, transfers best (9.3% on phase2, close to E5's
  8.4%, which measures irreducible run-to-run variation of the same task).
- E4 beats E1/E2 everywhere and is best in-session and on campaign 1, but
  not on phase2, where E3 is better.
- **The recent-activity feature adds no measurable accuracy** (ablation
  equal within 0.2-0.4 points on all three sets): the idle penalty is real
  but rare in these workloads (machine-wide idling is uncommon). Kept in
  code for transparency; not a claimed improvement.
- E2's analytic exponent extrapolates compression (+1 to +4%) and image
  filter (-3 to -13%) acceptably but overestimates matmul (+29% P, +10% E
  for 256->512; measured scaling 6.46x / 7.43x vs analytic 8x).
- These are accuracy results only. Whether these error differences change
  scheduling decisions (regret) is Phase 4's question; low MAE does not by
  itself imply better schedules.

**Tests:** 121 passing (Phase 3 adds `test_estimators.py`,
`test_dataset.py`, busy-fraction/history tests, and a real-process
`retry_after` idle-gap test).

### Project decision: online recalibration (2026-10-03)

Chosen by the project owner over per-session re-profiling to address the
Phase 3 session-level bias.

### Phase 4 — predictive scheduling, P, O, decision regret — COMPLETE, validated on real hardware

**Implemented:**
- `estimators/recalibrated.py` — "+rc" wrapper for offline-fitted rungs:
  per-pool multiplicative factor, log-space EWMA (alpha 0.2) of
  actual / base prediction, clamped [0.5, 3], scope per run (reset at run
  start, so runs stay independent). Ratios are taken against the prediction
  made with the *decision-time* context (EFT now passes it to `observe`).
  Not defined for E3 (already adaptive).
- EFT ladder as policies via `eft_factories`: EFT_E0, EFT_E1 (= B6),
  EFT_E2, EFT_E3 (= B7), **EFT_E4 (= P)**, EFT_E1_rc, EFT_E2_rc,
  EFT_E4_rc. **O** = EFT with E5 (`oracle_factory`), built from this
  experiment's own stage-A runs (same session). Each EFT decision logs every
  candidate's predicted wait / transfer / exec / finish, the chosen worker
  (rejected alternatives are the others), and the recalibration state.
- `analysis/decisions.py` — per-decision records and one-step hindsight
  regret from event logs alone (works for every policy, late or early
  binding). Hindsight exec time = E5 replay oracle, leave-run-out. Reported
  separately: **placement regret** (primary: given the binding moment, was
  the chosen worker the one that would have finished the task first),
  **bind delay** (time spent unbound in the ready queue), and ready-time
  regret (secondary; ignores contention among simultaneously ready tasks).
- **Two regret definitions were rejected on real data before settling**:
  bind-time-only hid waiting (B0_P_only scored 100% optimal in the n=1 smoke
  run `phase4_20261003T145622`, a pipeline check, not a result);
  ready-time-only charged unavoidable contention (every policy incl. the
  oracle scored ~0% optimal on the independent trace; its outputs
  `phase4_20261003T145958_decisions.csv` / `_summary.json` are kept on disk
  and superseded). The corrected analysis was re-derived from the same logs
  (`--analyze-only`), no new runs.
- `scripts/run_phase4.py`, `config/phase4.yaml`,
  `scripts/diag_decision_cost.py`.

**Experiment `phase4_20261003T145958`** (raw: `data/results/phase4_20261003T145958_runs.csv`,
events `data/events/phase4_20261003T145958/`; derived:
`..._decisions_20261003T150427.csv` + `..._summary_20261003T150427.json`):
Phase 2's three saved traces; stage A = B0_P_only, B0_E_only, B4 and the
8 EFT variants in shuffled order per (repeat, trace), 5 repeats (165 runs);
stage B = O, 5 repeats (15 runs); all 180 completed. Session calibration
just before (`data/diagnostics/solo_patterns_20261003T145942.csv`):
back-to-back P0 1.057x of profile, idle-gap P0 1.429x (p90 2.33x), E0
1.018x.

**This session was much slower and noisier than Phase 2's**: e.g.
B0_E_only on independent_mixed 386 ms median here vs 211 ms in Phase 2;
min-max makespan spreads up to ~2x within a policy. Background load was a
normal ~8% when checked; no cause was identified. Only within-session
comparisons are meaningful; makespan rankings at n=5 are NOT robust.

Decision-level results (thousands of decisions per policy; placement regret
in ms per decision, % optimal placements, chosen-worker exec prediction
median APE and median signed error):

| policy | layered: regret / optimal / exec APE (bias) | forkjoin: regret / optimal / exec APE (bias) | independent: regret / optimal / bind delay |
|---|---|---|---|
| B4_greedy_eligible | 2.88 / 74% / - | 2.03 / 83% / - | 4.82 / 61% / 110 ms |
| EFT_E0 | 13.52 / 53% / 68% (-55%) | 5.36 / 78% / 70% (-59%) | 54.43 / 37% / 7 ms |
| EFT_E1 (B6) | 12.09 / 55% / 49% (-48%) | 3.51 / 83% / 52% (-52%) | 17.61 / 43% / 8 ms |
| EFT_E1_rc | **6.07 / 65% / 21% (-4%)** | 3.62 / 81% / 28% (-19%) | 36.05 / 44% / 8 ms |
| EFT_E2 | 12.57 / 54% / 56% (-55%) | 2.35 / 83% / 53% (-53%) | 32.30 / 41% / 8 ms |
| EFT_E2_rc | **5.85 / 67% / 26% (-9%)** | 3.86 / 78% / 27% (-13%) | 34.12 / 40% / 9 ms |
| EFT_E3 (B7) | 9.64 / 56% / 34% (-10%) | 8.21 / 71% / 38% (-29%) | 35.31 / 39% / 10 ms |
| EFT_E4 (P) | 10.07 / 66% / 39% (-39%) | 2.68 / 86% / 39% (-39%) | 23.01 / 42% / 64 ms |
| EFT_E4_rc | **3.55 / 73% / 22% (+2%)** | 5.83 / 70% / 24% (-7%) | 29.92 / 44% / 57 ms |
| O (EFT_E5) | 3.76 / 70% / 24% (-1%) | 0.89 / 87% / 21% (-4%) | 27.31 / 47% / 22 ms |

Median makespan (ms) [min-max], 5 repeats — descriptive only:

| policy | layered_mixed | independent_mixed | forkjoin_mixed |
|---|---|---|---|
| B0_P_only | 1058.6 [632-1652] | 664.5 [559-1922] | 1088.7 [773-1561] |
| B0_E_only | 718.1 [687-1439] | 386.3 [353-750] | 830.4 [684-933] |
| B4_greedy_eligible | 851.7 [418-1106] | 345.3 [273-404] | 678.8 [576-1136] |
| EFT_E0 | 805.3 [658-1486] | 361.0 [277-624] | 798.4 [615-1152] |
| EFT_E1 (B6) | 816.4 [421-1143] | 341.0 [249-465] | 871.8 [543-1206] |
| EFT_E1_rc | 774.4 [669-1073] | 355.6 [288-503] | 693.8 [651-1505] |
| EFT_E2 | 886.9 [736-1095] | 316.8 [286-493] | 723.5 [556-1006] |
| EFT_E2_rc | 785.2 [690-1113] | 368.7 [298-1100] | 713.3 [606-1146] |
| EFT_E3 (B7) | 842.4 [758-1157] | 377.5 [278-484] | 922.0 [598-1683] |
| EFT_E4 (P) | 918.9 [595-1272] | 474.3 [329-536] | 719.0 [616-1039] |
| EFT_E4_rc | 803.6 [397-1022] | 488.2 [349-574] | 736.4 [637-1257] |
| O (EFT_E5) | 806.5 [493-833] | 406.6 [324-493] | 762.0 [669-1035] |

**Decision cost** (`scripts/diag_decision_cost.py`,
`data/diagnostics/decision_cost_20261003T150525.csv`; median
`select_worker` time, 9 workers, 0/9/30/60 tasks already bound; unpinned
process): E1 0.008/0.013/0.020/0.031 ms, E3 0.010/0.016/0.028/0.044 ms,
**E4 0.094/0.165/0.310/0.504 ms** (~10-16x E1), E4+rc 0.103/0.165/0.314/0.455 ms.

What the data supports:
1. **Online recalibration removes the session bias of offline-fitted
   estimators and, where decisions are spread over time, roughly halves
   placement regret** (layered: E1 12.09 -> 6.07, E2 12.57 -> 5.85, E4
   10.07 -> 3.55 ms/decision; bias -39..-55% -> -9..+2%). It cannot help
   when every decision is made before anything completes (independent
   trace: EFT binds all 60 tasks at t~0; no improvement). On fork-join,
   where placement regret is already low for all EFT variants, +rc did not
   reduce it (E4 2.68 -> 5.83; small absolute values).
2. **Better prediction accuracy did not translate into a robust makespan
   advantage in this session.** Greedy eligible dispatch B4 (no prediction)
   has placement regret as low as the best predictive policies (2.88 layered,
   2.03 forkjoin) and the best fork-join median makespan; makespan spreads
   overlap heavily across the top group. Not claimed: any makespan ranking
   among B4 / EFT variants / O.
3. **Estimator cost matters.** E4 is ~10-16x more expensive per decision;
   on the independent trace EFT_E4/EFT_E4_rc show 57-64 ms mean bind delay
   (vs ~8 ms for E1/E2) and the worst EFT makespans. The microbenchmark
   explains the direction but not the full size; the coordinator runs pinned
   to an E-core and logs a large per-candidate decision payload per dispatch
   (unquantified remainder; hypothesis, not measured).
4. **O is not an upper bound here.** EFT with the replay oracle does not beat
   the other policies on makespan: EFT itself is myopic, kernel-only (ignores
   `prepare()` ~30% and per-hop overhead), and O ran in stage B, later in the
   session. Its low placement regret is partly by construction (regret's
   hindsight exec times come from the same E5 table) and is not independent
   evidence.
5. Ready-time regret confirms the waiting cost of late binding (B0_P_only:
   79-536 ms mean bind delay) but is dominated by contention on the
   independent trace; not used for ranking.

**Tests:** 131 passing (Phase 4 adds `test_phase4.py`: recalibration
convergence/clamp/min_obs/reset, +rc registry rules, EFT passes the
decision-time context to `observe`, oracle factory, placement regret /
bind delay / ready regret on hand-built logs, real-process EFT+rc run).

### Project decisions after Phase 4 (2026-10-03)

1. **Kernel-only execution time remains the PRIMARY estimator / oracle
   target.** The definition is not replaced; all estimators, E5 and the
   primary regret stay kernel-only.
2. **End-to-end EFT is added as an explicit, separately labelled ablation.**
   `EarliestFinishTimeScheduler(e2e=EndToEndTerms)` adds measured setup
   (`prepare()`) and measured per-task runtime overhead to every task's time
   (exec term and the wait of executing/queued tasks). Policy names carry
   `_e2e`; every decision logs `"model": "kernel" | "e2e"`; placement regret
   is reported with both a kernel-only and an end-to-end hindsight yardstick
   on the same decisions.
3. **E4 decision cost is a measured scheduling-overhead issue.** A cheaper
   inference path `E4f` (same weights, same predictions to 1e-12 relative,
   plain-Python dot product) is an implementation optimization / ablation,
   not a research contribution. The original E4 implementation and its Phase
   4 measurements are preserved unchanged.

E2E terms measured (`scripts/derive_e2e_terms.py`, all from real data):
- `data/models/e2e_terms_20261003T151847.json`: setup from the Phase 2
  profile, overhead from Phase 4 event logs (loaded session): median
  1.197 ms (P), 1.369 ms (E). Setup is large relative to some kernels, e.g.
  image_filter 1024: 15.2 ms (E) / 9.7 ms (P); matmul 512: 6.1 / 4.6 ms.
- `data/models/e2e_terms_20261003T152812.json` (used in Phase 5): setup
  and solo overhead from the Phase 5 profile: overhead 0.64 ms (P/E),
  0.43 ms (R, link transfer excluded).

E4f decision cost (`data/diagnostics/decision_cost_20261003T151943.csv`,
median `select_worker` ms with 0/9/30/60 tasks bound): E1
0.009/0.017/0.028/0.044; E4 0.094/0.156/0.297/0.473; **E4f
0.035/0.055/0.083/0.119** (~3-4x cheaper than E4, still ~2.7x E1); E4f+rc
0.041/0.065/0.098/0.136.

### Phase 5 — remote offloading via a configurable local link shim — COMPLETE, validated on real hardware

**Implemented** (`src/caosched/remote/`):
- `LinkConfig` (latency, bandwidth, per-message overhead) and the shim:
  before each message of n bytes the sender waits latency + per-message +
  n/bandwidth (`precise_wait`: sleep then spin the last < 0.6 ms, because
  `time.sleep` overshoots 0.3-0.7 ms on this build -- measured), then really
  sends the n bytes over a localhost TCP socket. Achieved times are measured
  and logged; configured values are never reported as achieved.
- Wire protocol (length-prefixed JSON header + payload), a **node** process
  (runs tasks exactly like a local worker; affinity readback in its hello
  reply), and a **proxy** process per remote slot that the coordinator sees
  as an ordinary worker of pool `R`. Results carry measured `transfer_s`
  (round trip minus node span -- a duration, valid even with a foreign
  clock), `transfer_up_s`, `payload_bytes`; logged on `task_completed`.
- Payload sizes follow the workloads' actual data (matmul 16N^2 in / 8N^2
  out; image 3*side^2 both ways; compression: input bytes in, measured zlib
  output back). Payload *content* is a stand-in buffer; the node regenerates
  the deterministic inputs from the seed.
- `TransferModel` = configured shim + **measured socket cost**: the Phase 5
  profile with the shim at zero fitted transfer = **2.279 ms + 0.958
  ns/byte** (n=120, median |residual| 0.924 ms).
- A physical ARM device would run the same node (`python -m
  caosched.remote.node --host 0.0.0.0 --port N`), with `RemoteSlot(port=N)`
  and the shim set to zero; no scheduler change. Not tested (no device).

**Phase 5 profile** (`data/profiles/20261003T152700_profile.json`; node on
LP11 removed from E, proxy on LP4): R kernel medians match E (e.g. matmul
512: R 13.413 / E 13.470 ms; image 1024: 45.910 / 45.607 ms), as expected
for a node on an E-core. P medians drifted +5-11% vs the Phase 2 profile
(matmul 512: 5.548 vs 5.136 ms); E within ~3%.

**Experiment `phase5_20261003T153208`** (raw: `..._runs.csv`,
`..._transfer.csv`, `..._decisions.csv`, events
`data/events/phase5_20261003T153208/<config>/`): 6 configurations in
randomized order (lan_1g, loopback, local_2P6E, lan_100m, local_2P7E,
wifi_50m), 3 traces, policies shuffled per (repeat, trace), 3 repeats; 324
runs, all completed. Links: loopback (no shim), lan_1g (0.2 ms, 125 MB/s),
lan_100m (0.5 ms, 12.5 MB/s), wifi_50m (3 ms, 6.25 MB/s). The n=1 smoke run
`phase5_20261003T153046` was a pipeline check, not a result.

**Confound -- read first:** configurations ran sequentially, and the
session drifted: in `remote_lan_100m` *every* policy, including local-only
B4 (which never uses R), was much slower (layered 818 ms vs 569 ms in
local_2P6E; independent 384 vs 269). Even the extra 7th E core
(local_2P7E vs local_2P6E) shows no consistent gain. **Only comparisons
within one configuration are valid** (policies interleaved there).

Median makespan (ms) and tasks sent to R, within-configuration
(n=3, descriptive):

| config | trace | B4 local-only | B4_R (greedy, R last) | EFT_E1_rc | EFT_E4f_rc |
|---|---|---|---|---|---|
| wifi_50m | forkjoin | 499 (0) | **1836 (4)** | 382 (0) | 491 (0) |
| wifi_50m | independent | 261 (0) | 354 (2) | 276 (0) | 297 (0) |
| lan_100m | forkjoin | 585 (0) | **1032 (4)** | 615 (0) | 758 (0) |
| lan_100m | independent | 384 (0) | 496 (2) | 539 (0) | 510 (1) |
| lan_1g | layered | 545 (0) | 582 (3) | 533 (0) | 581 (1) |
| lan_1g | independent | 267 (0) | 261 (3) | 258 (4) | 265 (5) |
| loopback | layered | 565 (0) | 576 (3) | 547 (2) | 571 (4) |
| loopback | independent | 252 (0) | 292 (4) | 241 (6) | 309 (6) |

What the data supports:
1. **Blind (greedy) offloading is harmful on slow links**: B4_R is up to
   3.7x worse than local-only B4 on fork-join over wifi_50m and 1.8x over
   lan_100m; roughly neutral on lan_1g / loopback.
2. **Transfer-aware EFT avoids that harm** (0-1 tasks offloaded per run on
   the slow links, 0-7 on the fast ones) **but shows no measurable gain**
   from the extra remote slot even on fast links: one extra
   E-core-equivalent behind a link (~+10% capacity, minus transfer) is below
   what n=3 resolves in this noise.
3. **Transfer prediction**: measured / predicted median 1.06 (p10-p90
   0.98-1.19, n=70) on lan_1g, 1.02 (n=8) on lan_100m, but **1.27
   (0.92-2.03, n=153) on loopback**: the solo-calibrated socket cost
   under-models contention when little emulated delay masks it.

**Kernel vs end-to-end ablation** (local_2P7E; placement regret mean ms /
% optimal, judged by the kernel and by the e2e hindsight yardstick on the
same decisions):

| policy | kernel yardstick | e2e yardstick |
|---|---|---|
| B4_greedy_eligible | 2.60 / 71.0% | 3.99 / 66.7% |
| EFT_E1_rc | 4.07 / 67.2% | 3.74 / 69.1% |
| EFT_E1_rc_e2e | 4.90 / 76.9% | 4.52 / 78.6% |
| EFT_E4f_rc | 5.46 / 63.7% | 6.03 / 63.4% |
| EFT_E4f_rc_e2e | 3.72 / 72.9% | 4.09 / 71.7% |

- The e2e model **raises the share of optimal placements** for both
  estimators (E1 67->77%, E4f 64->73% kernel-judged; similar e2e-judged).
- It **lowers mean regret for E4f** (5.46 -> 3.72 ms) **but not for E1**
  (4.07 -> 4.90 ms): fewer mistakes, but some larger ones.
- Makespan shows no consistent kernel vs e2e difference at n=3 (local_2P7E
  layered 583.7 vs 586.0; independent 289.4 vs 337.7; forkjoin 531.3 vs
  495.9 ms).
- Greedy B4 again has the lowest mean placement regret by the kernel
  yardstick (2.60 ms).

**Tests:** 146 passing (Phase 5 adds `test_e2e.py`: e2e terms, labelled
e2e EFT, transfer hook, `@e2e` registry, E4f == E4; `test_remote.py`:
payload model, link validation, precise wait, transfer model, protocol with
a 5 MB payload, calibration fit, and real node + proxy processes through
the pool and coordinator).

### Phase 6 — dataset (6A) and core experiment matrix (6B) — COMPLETE with a documented deviation

#### 6A — unified dataset (validated)

`scripts/build_dataset.py` -> `data/datasets/20261003T160059/`: 53,109 task
rows and 218,283 candidate rows from 1,039 runs in 5 sessions (campaign 1,
campaign 2, Phase 2, Phase 4, Phase 5); 187 logs excluded with reasons
(16 Phase 1 logs with ~1 ms-quantized timestamps; 171 logs of n=1 smoke
runs). Every source log's SHA-256 is stored and re-verified. Schema,
provenance and leakage-safe splits (by session / run / size / occupancy,
never random rows): `docs/DATASET.md`. Tests: `tests/test_dataset_build.py`.
The 6B session is not yet in this build (see Next work).

#### 6B — experiment design (fixed before running: `config/phase6b.yaml`)

One worker pool for the whole session: P {0,2}, E {5..10}, remote node R0 on
LP11 behind the link shim (proxy on LP4, coordinator on LP4). A block = one
(repeat, trace); in every block all 14 conditions ran once in a seeded
random order, the link shim switched per run (`WorkerPool.set_link`); trace
order shuffled per repeat. Conditions: local (R unused) B0_E_only, **B4
(reference)**, EFT_E0, EFT_E1 (=B6), EFT_E1_rc, EFT_E3 (=B7), EFT_E4f_rc
(=P; same model as E4), EFT_E1_rc_e2e, EFT_E4f_rc_e2e, O (EFT with E5 built
only from runs completed earlier in the session); remote-capable per link
(lan_1g, wifi_50m): B4_R (greedy, R last) and EFT_E1_rc_R (transfer-aware).
Analysis: paired log-ratio vs the reference within each block, percentile
bootstrap 95% CI over blocks stratified by trace (10,000 resamples, seeded).

#### 6B — DEVIATION from the plan (read before the results)

* **Planned:** 40 repeats x 3 traces = 120 blocks (+ 12-run seed stage).
* **Completed:** 33 full repeats (99 blocks) plus a partial repeat 34 in
  which 2 of 3 blocks completed (layered, independent) and the fork-join
  block had 7 of 14 conditions when execution stopped; 1,433 runs completed
  (12 seed + 1,421 block runs).
* **Why it stopped:** Claude Code's background-task reaper stopped the
  process because the machine was critically low on memory (available
  memory was 0.79 GiB of 7.68 GiB right after the stop, 0.48 GiB shortly
  later, with other applications open). It was not a failure of the run and
  the stop did not depend on any result. Whether the runner's in-memory O
  table (which grows with every run) contributed was not determined.
* **Not rerun and not pooled** with any other session (project instruction).
* **Analysable:** 101 complete blocks; **primary analysis = the 99 blocks of
  the 33 full repeats** (balanced: 33 per trace); sensitivity analysis = all
  101 complete blocks.
* **Exclusions:** the incomplete fork-join block of repeat 34 (7 runs); in
  the primary analysis also repeat 34's two complete blocks (28 runs, for
  balance); 1 interrupted run log (`block__forkjoin_mixed__EFT_E4f_rc__r33.jsonl`,
  no `run_finished`, no row in runs.csv). The O replay tables used for regret
  include every completed local-condition run of the session (genuine
  observations), always leave-run-out.
* **Effect of the deviation on precision:** measured median paired SD of
  log makespan 0.133 -> 95% CI half-width ~2.65% pooled with 99 blocks
  (~2.4% would have resulted with 120); per trace n = 33 instead of 40.
  This is tighter than the +/-5% the design targeted, so the shortfall does
  not change what the experiment can resolve at the 5-10% level.
* **Reproducibility verified:** the analysis was run twice from the raw files
  (`--analyze-only ... --tag _full33_a` / `_full33_b`); effects JSON,
  decisions CSV and report are byte-identical (SHA-256 016d5edc..., 9d696bbc...,
  0c42d436...). Raw runs CSV, manifest and all 1,434 logs hash identically
  before and after analysis. Analysis peak memory was not measured (the
  monitor sampled the venv launcher process, not the interpreter); the
  system had 3.86 GiB available when it finished.

Files (experiment `phase6b_20261003T162145`): raw `data/results/..._runs.csv`,
`..._manifest.json`, `data/events/phase6b_20261003T162145/`; derived
`..._effects_full33_a.json`, `..._decisions_full33_a.csv`,
`..._report_full33_a.txt` (primary; `_b` = identical rerun) and
`..._*_complete101.*` (sensitivity). Smoke run `phase6b_20261003T160833`
(3 blocks) is a pipeline check, not a result.

#### 6B — results (primary: 99 blocks; % vs B4, 95% bootstrap CI; * = CI excludes 0)

| condition | makespan | mean response | throughput |
|---|---|---|---|
| EFT_E0 | +7.0 [+4.7, +9.5]* | +3.3 [+1.5, +5.2]* | -6.6 [-8.7, -4.5]* |
| EFT_E1 (B6) | +2.5 [+0.3, +4.8]* | +4.4 [+2.6, +6.2]* | -2.5 [-4.6, -0.3]* |
| EFT_E1_rc | -0.7 [-3.2, +1.9] | +1.0 [-1.1, +3.1] | +0.7 [-1.9, +3.3] |
| EFT_E3 (B7) | -1.1 [-3.8, +1.6] | +1.5 [-0.7, +3.6] | +1.2 [-1.6, +3.9] |
| EFT_E4f_rc (P) | +6.0 [+3.3, +8.8]* | +16.5 [+14.1, +19.1]* | -5.7 [-8.1, -3.2]* |
| EFT_E1_rc_e2e | -2.7 [-5.1, -0.2]* | +0.6 [-1.4, +2.5] | +2.8 [+0.2, +5.4]* |
| EFT_E4f_rc_e2e | +6.3 [+4.0, +8.7]* | +19.6 [+17.5, +21.8]* | -5.9 [-8.0, -3.9]* |
| O (EFT_E5) | +8.7 [+5.3, +12.3]* | +23.6 [+19.1, +28.2]* | -8.0 [-10.9, -5.0]* |
| B0_E_only | +18.8 [+16.1, +21.6]* | +31.8 [+29.2, +34.4]* | -15.8 [-17.7, -13.9]* |
| EFT_E1_rc_R@lan_1g | -1.7 [-3.9, +0.6] | -0.2 [-2.1, +1.7] | +1.7 [-0.6, +4.0] |
| EFT_E1_rc_R@wifi_50m | +0.5 [-2.2, +3.6] | +2.0 [+0.1, +4.1]* | -0.5 [-3.4, +2.3] |
| B4_R@lan_1g | +1.4 [-0.9, +3.8] | +1.2 [-0.6, +3.2] | -1.3 [-3.6, +1.0] |
| B4_R@wifi_50m | +85.1 [+75.8, +95.5]* | +18.3 [+16.5, +20.3]* | -46.0 [-48.9, -43.1]* |

Contrasts (makespan): EFT_E1 vs EFT_E0 **-4.2 [-6.2, -2.2]***; EFT_E1_rc vs
EFT_E1 **-3.2 [-5.2, -1.1]***; EFT_E3 vs EFT_E1 **-3.6 [-6.0, -1.2]***;
EFT_E4f_rc vs EFT_E1_rc **+6.8 [+4.6, +9.1]***; EFT_E1_rc_e2e vs EFT_E1_rc
-2.0 [-4.1, +0.0]; EFT_E4f_rc_e2e vs EFT_E4f_rc +0.3 [-2.0, +2.6]; O vs
EFT_E1_rc **+9.5 [+6.0, +13.0]***; EFT_E1_rc_R@lan_1g vs EFT_E1_rc -0.9
[-3.2, +1.3]; EFT_E1_rc_R@wifi_50m vs EFT_E1_rc +1.2 [-1.0, +3.6].

Per condition (mean [95% CI] over 99 runs):

| condition | makespan ms | sched. ms/run | decision us | exec pred. medAPE % | placement regret ms (kernel) | optimal % | regret ms (e2e) |
|---|---|---|---|---|---|---|---|
| B4 (ref) | 406.0 [398.2, 413.8] | 4.22 | 9.3 | - | 2.45 [2.39, 2.50] | 72.4 | 3.55 |
| EFT_E0 | 429.1 [422.0, 436.1] | 2.66 | 39.7 | 62.8 | 16.10 [15.74, 16.43] | 56.2 | 16.23 |
| EFT_E1 | 416.5 [409.3, 423.8] | 3.24 | 48.6 | 37.2 | 3.75 [3.54, 3.97] | 68.4 | 3.40 |
| EFT_E1_rc | 402.8 [396.4, 409.3] | 4.11 | 61.6 | 17.8 | 3.03 [2.81, 3.31] | 70.3 | 2.70 |
| EFT_E3 | 402.4 [395.1, 410.0] | 3.62 | 54.7 | 20.1 | 2.98 [2.82, 3.13] | 70.0 | 2.77 |
| EFT_E4f_rc | 425.6 [418.1, 432.8] | 44.45 | 676.9 | 14.1 | 4.35 [4.03, 4.66] | 68.1 | 4.35 |
| EFT_E1_rc_e2e | 395.0 [387.8, 402.1] | 5.47 | 82.6 | 18.3 | **1.12 [1.01, 1.25]** | **81.9** | **0.84** |
| EFT_E4f_rc_e2e | 430.4 [422.8, 438.5] | 47.90 | 733.2 | 14.3 | 3.46 [3.08, 3.85] | 72.4 | 3.47 |
| O | 433.7 [423.6, 443.8] | 63.67 | 1000.7 | 7.6 | 2.53 [2.35, 2.73] | 72.4 | 2.13 |
| B0_E_only | 477.0 [468.6, 485.5] | 2.21 | 4.7 | - | 9.59 | 0.0 | 11.89 |

Offload: EFT_E1_rc_R@lan_1g offloaded 1.36 tasks/run, 14.7 ms transfer per
offloaded task, transfer 8.4% of makespan, **measured/predicted transfer
1.01 [1.00, 1.02]**; EFT_E1_rc_R@wifi_50m offloaded 0.00 tasks/run; greedy
B4_R offloaded 3.51 (lan_1g, 28.9 ms/task) and 2.19 tasks/run (wifi_50m,
278.7 ms/task, transfer = 72% of makespan).

Placement regret vs relative decision margin (all EFT decisions, local
runs): margin < 2%: 4.26 ms, 75.0% optimal (n=28,315); 2-10%: 7.52 ms,
49.2% (n=9,661); 10-30%: 3.60 ms, 67.5% (n=6,798); >= 30%: 2.55 ms, 79.2%
(n=6,178).

Sensitivity (101 complete blocks): every estimate within 0.5 percentage
points of the primary analysis; no CI changes which side of zero it is on.

#### 6B — what the data supports (this session, this machine)

1. **Each step up the cheap prediction ladder helps makespan by ~3-4%**,
   with CIs excluding zero: size-aware profile over constant (E1 vs E0
   -4.2%), online recalibration (E1_rc vs E1 -3.2%), moving history (E3 vs
   E1 -3.6%). Phase 4's direction for +rc is confirmed with adequate power.
2. **None of the predictive policies beats greedy eligible dispatch (B4)
   by more than ~3%.** The best, EFT_E1_rc_e2e, is -2.7% [-5.1, -0.2];
   EFT_E1_rc and EFT_E3 are indistinguishable from B4. Prediction is needed
   to *match* a good greedy policy here, not to beat it by a large margin.
3. **More accurate is not faster when it costs decision time.** EFT_E4f_rc
   (exec error 14.1% vs 17.8% for E1_rc) is +6.8% slower than EFT_E1_rc, and
   O (7.6% error) is +9.5% slower: their decisions cost ~0.68 ms and ~1.0 ms
   (vs 0.06 ms), i.e. ~44 ms and ~64 ms of scheduling time per ~420 ms run,
   and their placement regret is not lower than E1_rc's. Measured scheduling
   overhead dominates the accuracy gain at these task sizes. (O's cost grows
   with its replay table -- an implementation property of this replay
   oracle, not an upper bound on prediction value.)
4. **End-to-end modelling sharply improves placement quality for the cheap
   estimator**: EFT_E1_rc_e2e placement regret 1.12 ms vs 3.03 ms, 81.9% vs
   70.3% optimal, and the only CI-excluding-zero makespan gain over B4
   (-2.7%); vs EFT_E1_rc the makespan difference is -2.0 [-4.1, +0.0]
   (borderline). No effect for E4f (overhead-dominated).
5. **Offloading**: transfer-aware EFT never hurts (wifi: offloads nothing,
   +1.2% ns; lan_1g: -0.9% ns) and its transfer prediction is accurate
   (1.01x); greedy offloading is catastrophic on the slow link (+85%
   makespan). One extra remote E-core-equivalent does not produce a
   detectable gain at +/-2.7% resolution.
6. **Decision margins**: regret is not monotone in the predicted margin --
   highest for 2-10% margins (49% optimal), lowest above 30%; near-ties
   (< 2%) are mostly harmless (75% optimal).
7. Phase 5's preliminary findings are consistent with these (greedy remote
   harm on slow links, no gain from one extra remote slot); Phase 4's
   tentative "+rc helps where decisions spread over time" is now supported
   as a makespan effect pooled over all three traces.

#### 6B — limitations

* Single session on one machine; generalization across sessions is not
  tested by design (no pooling). P-core drift between sessions (Phase 3)
  means absolute times are session-specific; paired effects are the result.
* 33 of 40 planned repeats (see deviation); per-trace estimates rest on 33
  blocks.
* Regret is one-step hindsight placement regret with replay-oracle exec
  times, local-condition runs only (no R oracle coverage); O's regret is
  partly circular (same E5 data).
* E4f decision cost reflects this implementation (Python, per-candidate
  context, coordinator pinned to an E-core); a faster implementation could
  change point 3.
* Remote node = an E-core behind an emulated link (Phase 5 caveats).

**Tests:** 157 passing.

### Final-system implementation (after Phase 6) — IN PROGRESS

* **Step 1 (dataset rebuild with 6B): EXECUTED and VERIFIED.**
  `python scripts/build_dataset.py` (1.02 GiB free at start) ->
  `data/datasets/20261003T210952/` (tasks.csv, candidates.csv, splits.json,
  manifest.json). The builder now streams rows to disk (same schema and
  rules). Built-in validation passed (every source log re-hashed): 145,378
  task rows, 754,141 candidate rows, 2,472 source logs (= runs), 242
  excluded logs; 1,056 remote rows; 89,866 rows with predictions.
  * Phase 6B `phase6b_20261003T162145` adds 1,433 logs / 92,269 task rows;
    this equals the experiment's own runs.csv (1,433 completed runs, sum of
    n_tasks 92,269). The one killed run of partial repeat 34 is excluded
    ("run not completed").
  * The 6B 3-block smoke run `phase6b_20261003T160833` (54 logs) is now
    excluded like the Phase 2/4/5 smoke runs (exclusion list entry added in
    `dataset/build.py`, documented in docs/DATASET.md); without it the
    pipeline-check runs would have entered the dataset.
  * Against the previous build `20261003T160059`: schema_version 1 both;
    tasks.csv (60 columns) and candidates.csv (17 columns) headers identical;
    all 1,039 old sources present with identical SHA-256 and row counts;
    row content (all columns except the build-global row_id) identical for
    all 1,039 common sources in tasks.csv and all 381 in candidates.csv; all
    187 old exclusions still excluded; 53,109 + 92,269 = 145,378.
  * Raw evidence unchanged: SHA-256 of all 2,769 files under data/events,
    data/results, data/profiles and data/models taken before the build and
    re-checked after it: 2,769 unchanged, 0 changed, 0 missing, 0 added.
    The 6B derived files still hash to the recorded 016d5edc / 9d696bbc /
    0c42d436.
* **Step 2 (lean runner): DONE.** O's replay table is compact
  `(run_id, kernel)` tuples shared live (grows only between runs: same
  semantics as the per-run copy, verified by a test); free-memory preflight
  (`experiment.min_available_gib`, default 1.0); per-run
  `coordinator_rss_mib` column. No protocol or definition change.
* **Steps 3-6 (application workflows): DONE and tested.** `src/caosched/apps/`:
  stage registry (decode / compute / encode; only compute is the kernel),
  artifact store, and the tiled image-analysis pipeline
  (source -> tile -> denoise -> edges -> features, mosaic, aggregate,
  package; 4k+4 tasks). Tasks gain `params` and `eligible_pools`; the
  coordinator passes artifact paths and enforces eligibility; workers run
  stages on real data; the remote proxy ships the real artifact bytes
  (benchmark kernels keep the old path, local P/E backend unchanged). Tests
  (`tests/test_apps.py`, real processes): final output bit-identical to a
  single-process reference both locally and with stages on the remote node;
  eligibility violations rejected; named pool `R_PI` and foreign-clock mode
  work.
* **Step 7 (Pi / T4 preparation): IMPLEMENTED; NOT EXECUTED and NOT
  VERIFIED on any Raspberry Pi or NVIDIA T4** -- status table in
  `docs/REMOTE_DEVICES.md`. No Pi or T4 functionality is claimed.
* **Blocker fixed before the demo:** `remote.link.payload_bytes` had no model
  for application stages, so transfer-aware EFT would have raised KeyError on
  the first remote-eligible stage. Added `apps.stages.stage_payload_bytes`:
  exact .npy sizes for stages whose bytes follow from task size (source,
  denoise, edges, features); fan-in stages raise rather than guess. New
  tests: model == real artifact sizes; transfer-aware EFT completes an app
  DAG with a remote node and matches the reference. No scheduler change.

#### Local end-to-end application demo — EXECUTED and VERIFIED (2026-10-03)

Command: `python scripts/run_app_demo.py` (defaults: 1024x1024 image,
grid 4 -> 68 tasks, seed 11, 2 profiling runs per pool; 1.06 GiB free at
start). Session `appdemo_20261003T211356`. Hardware: i5-1235U; coordinator
LP4; P workers LP0, LP2; E workers LP5-10; remote worker = node process on
LP11 behind the `lan_1g` link shim (0.2 ms latency, 125 MB/s, 0.05 ms per
message) over a real local TCP socket. This is a LOCAL remote worker, not a
physical device.

Artifacts:
* events: `data/events/appdemo_20261003T211356/` (8 logs: profile_{P,E,R}_{0,1},
  demo_B4_greedy_eligible_R, demo_EFT_E1_rc_R)
* stage outputs: `data/artifacts/appdemo_20261003T211356/<run>/<task>.bin` (92 MB)
* measured stage profile: `data/profiles/20261003T211356.appprofile.json`
  (not matched by the benchmark `*_profile.json` glob, so it does not enter
  dataset calibration)
* independent verification: `data/results/appdemo_20261003T211356_verification.json`
  (computed from the logs and artifact files only)

| run | status | tasks | makespan | final output vs single-process reference | remote tasks (bytes checked) |
|---|---|---|---|---|---|
| demo_B4_greedy_eligible_R | completed | 68/68 | 805.3 ms | exact (sha256 5a18729b92a37d78...) | 4/4 verified, 1,311,744 B |
| demo_EFT_E1_rc_R | completed | 68/68 | 828.9 ms | exact (same sha256) | 0 (none chosen) |
| profile_P_0 / _1 | completed | 68/68 | 1235.5 / 1038.2 ms | exact | - |
| profile_E_0 / _1 | completed | 68/68 | 1036.4 / 988.5 ms | exact | - |
| profile_R_0 / _1 | completed | 68/68 | 2356.1 / 2317.2 ms | exact | 68/68 verified each, 71,487,977 B each |

Stage placement in the two demo runs (task counts; denoise and edges are
the only remote-eligible stages):

| stage | B4_greedy_eligible_R | EFT_E1_rc_R |
|---|---|---|
| img_source (1) | P:1 | P:1 |
| img_tile (16) | P:4 E:12 | P:8 E:8 |
| img_denoise (16) | P:4 E:10 **R:2** | P:2 E:14 |
| img_edges (16) | P:3 E:11 **R:2** | P:4 E:12 |
| img_features (16) | P:3 E:13 | P:1 E:15 |
| img_mosaic (1) | P:1 | E:1 |
| img_aggregate (1) | P:1 | E:1 |
| img_package (1) | P:1 | E:1 |

Remote data transfer, VERIFIED: for every remote task (4 in B4, 68 + 68
in profile_R) the logged `payload_bytes` equals the on-disk input artifact
size(s) + the returned output size, the logged `output_bytes` equals the
output file size, and the output artifact the node returned is byte-identical
to the reference result of that task (e.g. denoise_1: 196,736 B up + 196,736 B
down, transfer 7.3 ms, kernel 3.5 ms; edges_6: 196,736 B up + 65,664 B down,
transfer 4.6 ms). Every final package is bit-identical to the reference.

Why EFT_E1_rc chose no remote placement (from its logged decisions, not
inferred): in all 32 remote-eligible decisions the predicted R0 finish was
at least 1.33 ms later than the best local candidate; predicted transfer
5.1-6.3 ms vs 2-3 ms stage kernels (B4's measured remote transfers: 4.6-10.7
ms). With 8 idle local workers the model correctly keeps these small stages
local. The transfer-aware remote path under EFT is covered by
`test_transfer_aware_eft_runs_application_dag`, not by this demo.

Limits: a single demo session, 1 run per policy; the two makespans are not
a comparison (n = 1, no CI) and are NOT research results. The stage
profile has n = 2 runs per pool (n = 32 samples for per-tile stages).

Post-demo checks: full suite **165 passed**; SHA-256 of all 2,769
pre-existing evidence files unchanged (0 changed / 0 missing); the only
new files are the 10 demo outputs listed above. Future dataset builds
exclude `appdemo_*` logs as "unrecognised source directory" (not part of
the controlled-experiment dataset).

Status labels:

| item | IMPLEMENTED | EXECUTED | VERIFIED |
|---|---|---|---|
| Dataset rebuild incl. Phase 6B | yes | yes | yes |
| Application DAG layer (params, artifacts, eligibility) | yes | yes | yes |
| Tiled image pipeline on local P/E through the scheduler | yes | yes | yes (bit-exact) |
| Remote stages carrying real input/output data | yes | yes (local node) | yes (byte counts + bit-exact outputs) |
| B4 greedy on the app DAG | yes | yes | yes |
| EFT_E1_rc transfer-aware on the app DAG | yes | yes | yes (output); remote placement: NOT EXECUTED in the demo (none chosen), exercised in tests only |
| Named remote pools / foreign-clock mode | yes | tests only | tests only |
| GPU stage variant (cuda) | yes | NOT EXECUTED | NOT VERIFIED |
| Raspberry Pi worker | prepared | NOT EXECUTED | NOT VERIFIED |
| NVIDIA T4 worker | prepared | NOT EXECUTED | NOT VERIFIED |

#### Application workload-intensity sweep — design fixed BEFORE execution (2026-10-03)

Purpose: give the offloading path a realistic computational opportunity in
the same verified app DAG, and measure where remote execution could pay off,
without tuning toward any outcome.
* Light stage identified (from `appdemo_20261003T211356`): denoise / edges
  kernels 1.7-3.9 ms vs remote transfer 4.6-10.7 ms. Blur `radius` is NOT a
  usable knob (measured: 1.54-1.69 ms for radius 1-32, Pillow box-blur
  approximation), and larger tiles scale compute and bytes together.
* Change (IMPLEMENTED): `img_denoise` param `iterations` = how many times
  the existing Gaussian blur is applied (compute x k, bytes moved
  unchanged); `build_image_pipeline(denoise_iterations=k)`, default 1 (k = 1
  output sha256 5a18729b... = the verified demo). DAG structure, stages,
  eligibility (denoise, edges -> R), scheduler, estimators unchanged.
  `run_app_demo.py --denoise-iterations k --repeats N --order-seed S`
  (seeded random B4/EFT order per repeat, runs.csv + manifest, per-run
  free-memory guard); `scripts/analyze_app_demo.py`.
* Pre-registered design: k in {1, 4, 16, 64} (one session each, run in that
  order), 10 paired repeats per k (B4_greedy_eligible_R vs EFT_E1_rc_R),
  order seed 0, 2 profiling runs per pool per session, 1024x1024, grid 4,
  seed 11, link lan_1g shim, remote worker = local node on LP11. Comparisons
  are within a level (paired); levels are separate sessions run back to back.

Execution status (as of 2026-10-04) -- **Phase A COMPLETE: all four
pre-registered levels have one complete, accepted session. Phase B analysis
EXECUTED 2026-10-04 (see "Phase B" below); Phase C NOT EXECUTED.**
Accepted: k = 1 appdemo_20261004T185921, k = 4 appdemo_20261003T213900,
k = 16 appdemo_20261004T185801, k = 64 appdemo_20261003T214453 (10/10 paired
repeats each). (Previous status, 2026-10-03: stopped with only k = 4 and
k = 64 complete.)

| session | k | status | demo runs completed (B4 / EFT) | profile runs | interruption | classification |
|---|---|---|---|---|---|---|
| appdemo_20261003T211356 | 1 | completed (earlier 1-run verified demo) | 1 / 1 | 6 | - | VERIFICATION ONLY |
| appdemo_20261003T212905 | 1 | interrupted | 2 / 3 | 6 | runner's own memory guard: "stopped before repeat 2 run 1: 0.44 GiB available" | EXCLUDED (incomplete) |
| (k = 16, first attempt) | 16 | NOT EXECUTED | 0 / 0 | 0 | demo preflight refused: 0.97 GiB < 1.0 GiB; no files written | - |
| appdemo_20261003T213900 | 4 | completed | 10 / 10 | 6 | - | ACCEPTED |
| appdemo_20261003T214453 | 64 | completed | 10 / 10 | 6 | - | ACCEPTED |
| appdemo_20261003T223138 | 16 | interrupted | 2 / 1 (+ demo_EFT_E1_rc_R_r01 unfinished) | 6 | job stopped externally by Claude Code's low-memory reaper during run r01; no runs.csv / manifest written | EXCLUDED (incomplete) |
| (k = 1, second attempt) | 1 | NOT EXECUTED | 0 / 0 | 0 | queued after k = 16, never started (job stopped) | - |
| appdemo_20261003T231850 | 16 | interrupted | 1 / 1 | 6 | runner's own memory guard: "stopped before repeat 1 run 0: 0.49 GiB available" (started at 1.22 GiB; the demo's 12 processes use ~0.65 GiB) | EXCLUDED (incomplete) |
| (k = 16, attempt 4) | 16 | NOT EXECUTED | 0 / 0 | 0 | the background wait for 1.4 GiB free RAM was stopped by Claude Code's low-memory reaper; not restarted (reaper instruction) | - |
| (k = 1, third attempt) | 1 | NOT EXECUTED | 0 / 0 | 0 | never started | - |
| (k = 16, attempt 5, 2026-10-04) | 16 | NOT EXECUTED | 0 / 0 | 0 | launch rule (>= 1.5 GiB, prefer 2.0) not met: `psutil.virtual_memory().available` = 0.72 GiB, re-check 0.64 GiB (total 7.68 GiB); no files written, no background watcher | - |
| (k = 1, attempt 4, 2026-10-04) | 1 | NOT EXECUTED | 0 / 0 | 0 | gated on a complete, verified k = 16 session; never started | - |
| appdemo_20261004T185801 | 16 | completed | 10 / 10 | 6 | - (pre-launch free RAM 2.28 GiB; min during runs 2.08 GiB) | ACCEPTED |
| appdemo_20261004T185921 | 1 | completed | 10 / 10 | 6 | - (pre-launch free RAM 2.44 GiB; min during runs 2.05 GiB) | ACCEPTED |

Re-check of 2026-10-04 (first): free RAM 0.72 / 0.64 GiB, no session
launched (rows "attempt 5" / "attempt 4" above).

Second retry of 2026-10-04: free RAM 2.16 GiB at the check. Both missing
levels were then run in the foreground with the original configuration
(args identical to the k = 64 manifest except `--denoise-iterations`:
`--size 1024 --grid 4 --profile-runs 2 --node-core 11 --link-profile
data/profiles/20261003T152700_profile.json --repeats 10 --order-seed 0
--min-run-gib 0.5`), memory guard enabled, k = 16 first, k = 1 only after
k = 16 verified. Post-run integrity check (read-only, per session):
manifest k / args / seed 11 / lan_1g / policies match the design;
`runs_completed` 20, `stop_reason` null; runs.csv 20 rows = 10 complete
B4/EFT pairs r00-r09; all `status` completed; all `output_match` exact with a
single output sha256 per session (k = 16: 6acdbb7c19df0658...; k = 1:
5a18729b92a37d78..., identical to the verified k = 1 demo reference);
every event log present and non-empty; 26 event files and 26 artifact dirs
(20 demo + 6 profile). Result: VERIFIED for both. No interruptions. All
earlier sessions were left in place; nothing was overwritten, merged or
deleted (8 `appdemo_*` session folders now exist).

Overnight run of 2026-10-03/04 -- **STOPPED in Phase A.** k = 16 and k = 1
still have no complete session, so Phase B (analysis) and Phase C were NOT
EXECUTED as specified. The design is unchanged. Accepted sessions remain
k = 4 (appdemo_20261003T213900) and k = 64 (appdemo_20261003T214453), 10/10
paired repeats each, not yet analyzed. Blocker: with ~7.7 GiB total RAM and
Chrome holding ~2 GiB, free RAM rarely exceeds ~1.2 GiB, while one session
needs about 1.15 GiB at start plus ~0.65 GiB of headroom above the 0.5 GiB
guard.

All runs that did complete produced the exact reference output (logged
`output exact` per run; independent re-verification pending the analysis).
Partial sessions are preserved unmodified and are not merged with anything.
Raw evidence: SHA-256 snapshot of 2,779 files taken before the sweep ->
2,779 unchanged, 0 changed, 0 missing; 83 files added, all belonging to the
sessions above. Test suite before the sweep: 166 passed (post-experiment
run pending). Free RAM was 0.58 GiB when execution stopped.

#### Phase B — sweep analysis — EXECUTED and VERIFIED (data integrity), 2026-10-04; awaiting review

Full report: `docs/PHASE_B_WORKLOAD_SWEEP.md`. Outputs (new directory, nothing
overwritten): `data/results/phaseB_appdemo_sweep_20261004/`.
* `scripts/analyze_app_demo.py` EXECUTED unchanged on the 4 accepted sessions
  only. Finding: its stage medians include the 6 pool-pinned profile runs per
  session; it gives medians only and one bootstrap CI.
* `scripts/analyze_app_sweep.py` IMPLEMENTED and EXECUTED (supplementary;
  demo runs only, run = unit, mean/SD, Student t CI per policy, paired t CI
  for EFT − B4, bootstrap cross-check; validates design, refuses mismatches).
* VERIFIED: design check passed for 4/4 sessions; 80/80 demo runs event log
  = runs.csv and final output exact vs a fresh reference; remote tasks
  byte/bit-verified 747/747; evidence SHA-256 12,512 files unchanged before
  vs after (0 changed / missing / added outside the new directory).
* Results (EXECUTED; interpretation in the report): EFT_E1_rc makespan
  longer than B4 at every k: +5.8% [+1.0, +10.8] (k=1), +8.8% [+0.3, +17.9]
  (k=4), +6.2% [+1.1, +11.6] (k=16), +4.7% [+0.2, +9.5] (k=64) (paired t on
  log ratio, n = 10 each). Denoise E kernel 3.9 -> 183 ms while transfer
  stayed 4.8-7.8 ms; remote path never cheaper per task than local E
  (+3.6 to +7.9 ms). Offloading pay-off regime NOT established (no
  local-only condition; remote = E core LP11 behind the lan_1g shim).
* Limitations: cross-k confounded (separate sessions; free RAM 0.50-0.68 GiB
  at k=4 vs ~2.1 GiB at k=1/16); order seed 0 put B4 first in 8/10 pairs at
  every k (position effect partly confounded with policy); not physical
  Pi/T4. Test suite NOT re-run in Phase B.
* Read-only audit (2026-10-04, before Phase C) -- EXECUTED and VERIFIED:
  - Paired statistics recomputed independently from the raw runs.csv
    files match at all 4 k (10 pairs keyed by repeat; paired t, df 9).
  - The t-table matches integrated Student-t quantiles to <= 0.0005. The
    large-df fallback (`T975.get(df, 1.960)`) passed synthetic tests up to
    n = 320, and no direct lookup that could raise a KeyError remains.
  - Evidence: 12,512 files re-hashed, unchanged.
  - Every figure quoted in the doc and here matches the JSON.
  - Minor defects, documented in docs/PHASE_B_WORKLOAD_SWEEP.md (outputs
    and script unchanged):
    (1) log-ratio % rounded before exp, max 0.0056 percentage points off;
    (2) profile-run reference block has task-level CIs, which are not valid
        and not used;
    (3) the transfer-vs-compute CIs count both runs of a pair separately,
        so treat them as approximate.
  - (At the time of this audit, Phase C had not yet been executed; see below.)

#### Phase C — final integrity audit and testing — EXECUTED and VERIFIED, 2026-10-04; awaiting review

No experiment was run or modified; no scheduler or feature change. Records:
`data/results/phaseC_integrity_20261004/` (`pytest_output.txt`,
`phaseB_outputs_sha256.txt`), kept separate from raw evidence and from the
Phase B outputs.

| check | status | result |
|---|---|---|
| Evidence vs saved snapshot `phaseB_appdemo_sweep_20261004/evidence_sha256_before_analysis.json` (data/events, data/results, data/profiles, data/artifacts/appdemo_*) | EXECUTED, VERIFIED | 12,512 files: 12,512 unchanged, 0 changed, 0 missing. Re-checked after the test run, still unchanged. The only added files in scope are the Phase C records. |
| Older raw logs vs the hashes stored in the dataset manifests | EXECUTED, VERIFIED | `data/datasets/20261003T160059`: 1,039/1,039 source logs unchanged. `data/datasets/20261003T210952`: 2,472/2,472 unchanged. |
| Earlier sweep snapshots (2,779 / 2,769 files, quoted above) | NOT EXECUTED | Only their results were recorded; the hash lists were never saved to disk, so there is nothing to compare against. Covered in practice by the 12,512-file snapshot and the dataset manifests. |
| Unexpected files | EXECUTED, VERIFIED | Every file modified since 19:00 is accounted for: PROJECT_STATUS.md, docs/PHASE_B_WORKLOAD_SWEEP.md, scripts/analyze_app_sweep.py, the 8 Phase B outputs and the Phase C records. None are unexpected. |
| No workers / background jobs | EXECUTED, VERIFIED | No other Python process before or after the tests; no background shell jobs. |
| Full test suite | EXECUTED, VERIFIED | Command `.venv\Scripts\pytest` (README), run from the project root at 2026-10-04 19:21:48. **166 collected, 166 passed, 0 failed, 0 skipped, 0 errors**, 14.49 s, exit 0. Python 3.11.9, pytest 9.1.1. The run wrote no files into evidence. |
| Phase B reproducibility | EXECUTED, VERIFIED | `scripts/analyze_app_sweep.py` was re-run into a scratch directory outside the project. `supplementary_summary.json`, `per_run.csv` and `paired.csv` were **byte-identical** to the saved files, and every printed result line was identical. |
| Docs vs saved results | EXECUTED, VERIFIED | Every row of the consolidated per-k table and every % [CI] quoted here and in the report match `supplementary_summary.json`. The audit's exact % values match a recomputation from the raw runs.csv. The four accepted sessions, excluded sessions, CI methods, confounds and audit defects are all documented. |
| Same-machine vs physical hardware | VERIFIED (documented) | Remote = a node process on LP11 behind the `lan_1g` shim. No Raspberry Pi / NVIDIA T4 execution exists (Step 7 above: Pi/T4 support is IMPLEMENTED, but NOT EXECUTED and NOT VERIFIED on any physical device). |

New minor defect, found and not fixed (cosmetic):
`analyze_app_sweep.py` exits with a ValueError after writing all outputs
when `--out-dir` is outside the project. The cause is the final print's
`Path.relative_to(ROOT)`. No result is affected.

#### Dataset freshness and quality audit — EXECUTED and VERIFIED, 2026-10-04; awaiting review

Details: `docs/DATASET.md` ("Builds and coverage", "Sessions not yet
included", "Audit of 2026-10-04"). Records:
`data/results/dataset_audit_20261004/`. No dataset version was created or
changed. No experiment, model training, scheduler change or Pi/T4 work.

* Latest build `data/datasets/20261003T210952`: 145,378 task rows, 754,141
  candidate rows, 2,472 runs, 6 sessions (incl. phase6b), 242 EXCLUDED logs
  with reasons. It covers every non-app-demo log on disk
  (2,472 + 242 = 2,855 − 141).
* **Not current for the app-demo experiment.** None of the 8 `appdemo_*`
  sessions (141 logs) is in any build. That includes the 4 accepted sweep
  sessions, which were logged after the build. The current builder EXCLUDES
  all of them as "unrecognised source directory" (`classify()` knows only
  campaign/phase2/4/5/6b). A rebuild therefore adds 0 eligible rows, so no
  new version was written. Including them needs a builder change (new
  source kind; profile-run and Phase A classification rules; no
  `img_*` calibration entries) -- NOT IMPLEMENTED, a decision for review.
* VERIFIED for both builds:
  - schema, counts (overall / per source / kind / session), no duplicates,
    no invalid values;
  - every candidate links to its task, with exactly one chosen candidate
    per decision, consistent with the task row (89,866 decisions);
  - no calibration profile from after its session;
  - source SHA-256 1,039/1,039 and 2,472/2,472;
  - both builds' files unchanged.
* VERIFIED reproducibility: a scratch rebuild with the current builder
  reproduced `tasks.csv`, `candidates.csv` and `splits.json` of
  `20261003T210952` byte-identically. Its manifest differs only in
  `built_at` and the 141 app-demo exclusions.
* Leakage / feature availability (findings; nothing repaired):
  - Splits are disjoint as defined, with 0% input reuse between
    `by_session` train and test. But train and test share the same 3
    workloads (no unseen-workload test), and `by_size` has only 2 sizes per
    workload.
  - Context features are taken at task start, not at the decision: the
    co-runner count differs from a dispatch-time reconstruction in 42.1%
    of late-binding and 81.4% of early-binding rows.
  - `target_busy_frac` uses post-decision information in 46,229
    early-binding rows.
  - The online decision context is not logged, so train/serve parity
    cannot be VERIFIED.
* Tests: dataset tests 8 passed (`.venv/Scripts/pytest
  tests/test_dataset.py tests/test_dataset_build.py -v`).

#### Demonstration dashboard — IMPLEMENTED, EXECUTED and VERIFIED, 2026-10-04; awaiting review

Launch with `.venv\Scripts\python -m caosched.dashboard --open`
(http://127.0.0.1:8765/). Details, limitations and a five-minute demo
script: `docs/DASHBOARD.md`.

* IMPLEMENTED: `src/caosched/dashboard/` (standard-library server, read-only
  data layer, live runner, static HTML/CSS/JS/SVG page; no new dependencies)
  with four screens: system overview, application workflow (DAG, timeline,
  critical path, real artifacts), scheduling comparison and hardware
  expansion. No scheduler, estimator or application code was changed.
* Replay reads the accepted sessions' logs and artifacts unchanged. The
  comparison screen reads `phaseB_appdemo_sweep_20261004/supplementary_summary.json`
  and the hardware screen parses `docs/REMOTE_DEVICES.md`. No result is
  hard-coded, and tests assert equality with the saved summary.
* EXECUTED and VERIFIED, live path: `live_20261004T200103_EFT_k16`, started
  through the server API, ran the real `WorkerPool`/`Coordinator`/EFT_E1_rc.
  It completed 68/68 tasks (P 21, E 43, R 4) with an **exact** output whose
  sha256 equals accepted k=16. Output is only in `data/dashboard_runs/`.
  Evidence re-hashed afterwards: 12,512 files unchanged.
* Tests: `tests/test_dashboard.py`, 12 passed and 1 SKIPPED. The skipped
  test is the end-to-end live run, guarded at 1.5 GiB free; 1.14 GiB was
  available. The full suite (`.venv\Scripts\pytest`) gave **178 passed,
  1 skipped**, 0 failed.
* Screens rendered in headless Chrome, dark and light, with no console
  errors.
* NOT EXECUTED: Raspberry Pi and NVIDIA T4. The dashboard shows them as NOT
  CONNECTED and displays no device metrics.

## Next work

- (Done 2026-10-03: the dataset was rebuilt with the 6B session as
  `data/datasets/20261003T210952`; verified 2026-10-04.) Open: decide
  whether and how to add the app-demo sessions to the dataset (builder
  change, see the dataset audit above).
- Before any future long experiment: reduce the runner's memory footprint
  (store O's replay table as compact tuples instead of row dicts) and check
  free memory at start; record peak memory of the interpreter process (not
  the venv launcher).
- Next stage (per project plan): extend the runtime to application-level
  DAG workflows, then integrate physical heterogeneous resources (Raspberry
  Pi, NVIDIA T4) through the existing remote-node interface without changing
  the scheduler architecture. No frontend yet; no paper writing yet.
- Run the full (non-`--quick`) Phase 0 benchmark suite for the final reported
  dataset (see caveat above).

## Known limitations / assumptions (update as discovered)

- `GetSystemCpuSetInformation`'s `EfficiencyClass` semantics (higher = more
  performant) are documented by Microsoft for hybrid parts. The exact struct byte
  layout was initially reconstructed incorrectly (see Phase 0 bug writeup above)
  and has since been validated empirically against this machine's real API
  output (confirmed 32 bytes/entry, 12 entries, matching WMI and `os.cpu_count()`
  exactly) and pinned with a regression test. Residual risk: this layout has only
  been validated on this one machine/Windows build (10.0.26100); a different
  Windows version could in principle use a different layout, which would most
  likely surface as a `cpu_count_cross_check.consistent: false` in the
  environment record rather than fail silently, since every count is
  cross-checked against WMI and `os.cpu_count()`.
- No Raspberry Pi / physical remote device is available or required; Phase 5's
  remote-worker interface will be validated against a local network shim only,
  as explicitly permitted by the project brief.
- This machine has 8 GB RAM — dataset generation and any later ML estimator
  training (Phase 3, E4) must stay mindful of memory budget; no large external
  datasets will be downloaded.
- Phase 0 gate numbers reported above are from `--quick` mode (small sizes, 5
  repeats, 15s load windows) — sufficient to answer the gate question honestly,
  but the full suite should be re-run for final thesis-grade numbers (see caveat
  above).
- Phase 1's worker cold-start effect (numpy import cost on a worker's first
  task) means makespan/response-time measurements taken from a cold worker
  pool are not directly comparable to a warm one; later experiments (Phase 7)
  should either always warm up workers first or explicitly treat cold-start as
  a measured condition, not an artifact to hide.
- Timing: all runtime intervals rely on `QueryPerformanceCounter` being
  system-wide (validated on this machine, pinned by `tests/test_clock.py`).
  `time.time()` on CPython 3.11/Windows is ~1-16 ms resolution and is kept in
  events only as a human-readable `timestamp`; never use it for intervals.
  Phase 0's benchmark harness times kernels with `perf_counter` inside one
  process and is unaffected.
- Runtime overhead is ~0.5 ms per dependency hop (Phase 1 measurement). DAGs
  of sub-millisecond tasks will be overhead-dominated regardless of policy.
- Phase 1 failure policy is fail-fast (first task error / dead worker aborts
  the run). No retry or worker restart; deliberate for an experiment harness
  where a silently-retried task would distort measurements.
- `FirstIdleScheduler` (formerly mis-named `RoundRobinScheduler`) is a
  test/pipeline placeholder only, not a baseline. The real B1 is
  `schedulers.simple.RoundRobinScheduler`.
- Kernel-only execution time (project decision) means EFT wait estimates
  omit `prepare()` (~30% of per-task worker time in Phase 2 traces) and
  per-hop overhead (~0.5 ms); EFT is therefore biased toward queueing behind
  busy workers.
- The static profile is measured solo; under concurrent load kernels ran
  1.15-1.41x (median) slower in the smoke diagnostics. B6 inherits this bias.
- B2's mapping and B4's eligibility/priority are config choices (justified
  in `config/phase2.yaml`), not derived automatically.
- P-core performance drifts across sessions (Phase 3: back-to-back P0
  1.003x -> 1.122x of profile within ~2.5 h; E-cores stable). Any
  comparison across policies must therefore run interleaved within one
  session (as Phase 2 did), never across sessions.
- After a machine-wide idle period, P-core tasks run ~1.27-1.29x slower
  (reproduced twice); runs starting from an idle machine are affected.
- Phase 3 E4 is trained on one campaign session; its cross-session bias is
  -12% to -19%. CPU frequency is not observable through psutil on Windows,
  so the drift/idle explanation remains a hypothesis.
- Phase 4 regret is one-step (myopic) hindsight regret with replay-oracle
  (E5) counterfactual kernel times; it does not capture downstream effects
  of a decision, and O's own regret is partly circular (same E5 table).
- Online recalibration is per run; decisions made before any completion in
  a run (e.g. all of an independent trace under early binding) are never
  corrected.
- Phase 5 remote node is an E-core of this machine behind an emulated link:
  its compute speed is the E core's (no compute emulation, by design), and
  its clock is shared with the coordinator (a physical device would not
  share it; transfer is computed from durations so it stays valid, but
  node-side t_started/t_completed would not be comparable).
- The remote proxy runs on the coordinator's reserved core and spin-waits
  up to 0.6 ms per shim delay; the socket-cost calibration is solo and
  under-models contention (loopback measured/predicted 1.27x).
- Payload content is a stand-in buffer of the correct size; the node
  regenerates inputs from the seed, so data never truly moves end to end.
- Phase 2 makespans are hundreds of ms; OS scheduling noise is visible
  (min-max spreads up to ~25%). Small policy differences need Phase 7's
  repeat counts and statistics before any claim.

## Commands used this session

```
py -0p                                              # confirm Python 3.11 is default
Get-CimInstance Win32_Processor ...                 # confirm CPU model/core/thread counts
py -3.11 -m venv .venv                              # create project venv
pip install -r requirements.txt                     # install numpy, pillow, psutil, pyyaml, pandas, pytest
pip install -e .                                    # editable-install caosched package
python src/caosched/phase0/topology.py              # validate topology discovery directly
python src/caosched/phase0/env_record.py            # generate environment JSON record
python scripts/phase0_benchmark.py --quick          # run K1/K2/K5 benchmark suite
python scripts/phase0_gate_report.py                # analyze results, print gate verdict
python scripts/run_dag.py --size 256                # Phase 1: all 4 DAG patterns on real topology
python scripts/profile_static.py                    # Phase 2: static (E1) profile, solo, all slots
python scripts/run_baselines.py [--repeats N]       # Phase 2: all traces x B0-B7, shuffled order
python scripts/collect_campaign.py                  # Phase 3: randomized interference campaign
python scripts/train_e4.py --campaign DIR --feature-set occupancy+history|occupancy
python scripts/diag_solo_patterns.py --blocks 4 --tasks 30   # Phase 3: idle/back-to-back diagnostic
python scripts/evaluate_estimators.py --e4 M.json --e4-ablation M2.json --c1 DIR --phase2 DIR
python scripts/run_phase4.py [--repeats N]          # Phase 4: EFT ladder + O, regret analysis
python scripts/run_phase4.py --analyze-only EXP_ID  # Phase 4: re-run log analysis only
python scripts/diag_decision_cost.py                # Phase 4/5: per-decision CPU cost by estimator (incl. E4f)
python scripts/derive_e2e_terms.py --profile P.json (--events DIR | --overhead-from-profile)
python scripts/profile_static.py --remote-node-core 11 --proxy-core 4   # Phase 5 profile incl. R + link calibration
python scripts/run_phase5.py [--repeats N]          # Phase 5: local vs remote configs, kernel vs e2e ablation
python scripts/build_dataset.py                     # Phase 6A: unified dataset + validation
python scripts/run_phase6b.py                       # Phase 6B: core experiment matrix (stopped at repeat 34)
python scripts/run_phase6b.py --analyze-only phase6b_20261003T162145 --block-filter full_repeats --tag _full33_a
python scripts/run_phase6b.py --analyze-only phase6b_20261003T162145 --block-filter complete_blocks --tag _complete101
python -m pytest -v                                 # run test suite
```

## Test results

```
157 passed
```
- Phases 0-5 as before (146), Phase 6A `test_dataset_build.py` (3), Phase 6B
  `test_stats.py` (8: bootstrap, paired effects under block drift, decision
  time logging, set_link, allowed_pools).
