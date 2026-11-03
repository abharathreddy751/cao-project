# Project brief (verbatim)

Recovered verbatim from the session-1 (2026-10-02) instructions so the
baseline/estimator definitions live in the repository. This is the
authoritative research specification; ARCHITECTURE.md implements it.

---

We are now BUILDING the project. Do not redesign the research direction unless you discover a hard technical blocker.

PROJECT TITLE:
Prediction-Aware Dynamic Task Scheduling and Offloading for DAG Workloads on Heterogeneous Cores: How Much Prediction Is Enough?

CURRENT HARDWARE:
- HP 15s
- Intel Core i5-1235U
- 2 Performance cores + 8 Efficiency cores
- 12 logical processors
- 8 GB RAM
- Intel UHD Graphics
- Windows 11
- 512 GB SSD

CORE RESEARCH IDEA:
Build an instrumented runtime that executes DAG workloads and dynamically places ready tasks across:
1. P-core worker pool
2. E-core worker pool
3. Remote worker interface

The scheduler should choose the worker/pool using predicted finish time:

F(t,w) = waiting time + transfer time + execution time

The research question is:
HOW MUCH EXECUTION-TIME PREDICTION IS ENOUGH TO IMPROVE SCHEDULING?

This is NOT an attempt to claim a new ML algorithm.
The contribution is an empirical and reproducible study of how different prediction levels affect scheduling decisions and outcomes on real heterogeneous P/E-core hardware.

IMPORTANT RESEARCH POSITION:
- ML is one estimator inside the scheduler, not the whole project.
- Adaptive task granularity is NOT the main contribution.
- Selective ML prediction is an analysis/ablation, not the main contribution.
- Raspberry Pi is OPTIONAL and must NOT block development.
- QEMU/ARM emulation must never be treated as valid performance evidence.
- Do NOT claim novelty for generic ML scheduling, DAG scheduling, dynamic offloading, or adaptive granularity.
- Do NOT fabricate benchmark values, datasets, or literature results.

PRIMARY PLATFORM:
Use native Windows processes.
Do NOT make WSL/Docker a dependency for the core project.
Memory is limited to 8 GB.

TARGET ARCHITECTURE:

Coordinator
  -> DAG Manager
  -> Ready Queue
  -> Runtime State Store
  -> Scheduler
  -> Execution-Time Estimator
  -> Dispatcher
  -> Event Logger

Worker pools:
  P-core pool
  E-core pool
  Remote-worker pool/interface

The coordinator should preferably run on a reserved E-core.
Initial worker configuration:
- 2 P-core worker slots
- 7 E-core worker slots
- 1 E-core reserved for coordinator/OS

Do NOT blindly assume Windows logical processor IDs correspond to P/E cores.
Discover the topology/mapping at startup and record it.

ESTIMATOR LADDER:

E0 = constant execution profile by task type/resource
E1 = profile lookup by task size
E2 = analytic size-based model
E3 = moving historical execution-time estimate
E4 = learned interference-aware estimator
     Features may include:
     - task type
     - task size
     - target worker/pool
     - busy slots
     - occupancy
     - co-running task types
     - calibration execution time
     - available memory
E5 = oracle estimator for offline/replay analysis only

Do not force a Random Forest or other ML model if the collected data shows that simpler estimators are sufficient.
The experiment itself should determine whether ML actually helps.

BASELINE POLICIES:

B0 = P-only / E-only
B1 = Round Robin
B2 = Static mapping
B3 = Shortest queue
B4 = Patent-mapped greedy eligible-worker dispatch
B5 = Simple criticality-aware DAG rule
B6 = Earliest Finish Time using static profile
B7 = Earliest Finish Time using moving history
P  = Earliest Finish Time using learned estimator
O  = Oracle replay

The patent baseline must be implemented only as a documented comparison to the patent's eligible-worker/greedy dispatch concept. Do not misrepresent the patent.

WORKLOADS FOR INITIAL DEVELOPMENT:
1. Matrix multiplication
2. Image filtering
3. Compression
4. Sorting can be added later
5. ML inference can be added later

DAG patterns:
- independent tasks
- chain
- fork-join
- mixed DAG

PHASED BUILD ORDER:

PHASE 0:
Build an environment/hardware characterization system.

It must:
- detect CPU model
- detect physical/logical CPU topology
- determine P/E core mapping as reliably as Windows allows
- detect RAM
- detect OS
- record Python version
- test CPU affinity support
- record runtime configuration
- create a machine/environment JSON record

Then build a benchmark harness to measure:
- task execution time
- P-core vs E-core performance
- execution time under different levels of concurrent load
- P-core hyperthread/sibling interference if measurable
- runtime overhead
- memory usage

Use controlled warmups and repeated measurements.
Do not use arbitrary manually typed benchmark numbers.

Important:
Avoid hidden multithreading from numerical libraries.
Ensure workload thread counts are controlled.

PHASE 0 GATE:
Before building the ML scheduler, determine whether task execution time actually changes meaningfully across:
- P vs E pools
- different occupancy levels
- task types/sizes

If the data shows weak variation, record that honestly and adapt the emphasis of later experiments.
Do not manufacture an ML benefit.

PHASE 1:
Build the core runtime:
- task abstraction
- DAG representation
- dependency tracking
- ready queue
- worker pools
- worker affinity
- coordinator
- dispatch
- completion handling
- event logging

Every task execution should record timestamps.

PHASE 2:
Implement baseline schedulers:
B0-B7 where practical.

Keep scheduler policies modular so the same workload trace can be replayed under different policies.

PHASE 3:
Implement the estimator interface:
E0-E4 and offline oracle E5.

Each estimator must be replaceable without changing the scheduler.

The scheduler should calculate candidate finish times for eligible workers and log them.

PHASE 4:
Implement predictive scheduling:
Choose the worker with minimum predicted finish time.

Record:
- predicted execution time
- predicted queue/wait time
- transfer time
- predicted finish time
- actual execution time
- actual finish time
- selected worker
- rejected alternatives
- regret relative to the best actual choice when available

Decision regret is important.
Do NOT evaluate the estimator only by MAE/RMSE.

PHASE 5:
Implement remote offloading as an interface.

Initially use a controllable local link/network shim on Windows.
Support configurable:
- latency
- bandwidth/rate
- serialization/transfer overhead

Do not require a Raspberry Pi.

Later, a physical ARM device can be connected without redesigning the scheduler.

PHASE 6:
Implement dataset generation.

The dataset must be generated automatically from profiling and scheduler runs.

Include fields such as:
- run/session ID
- timestamp
- task type
- task size
- input/output bytes
- origin
- worker/pool
- occupancy
- busy slots
- co-running workload type
- memory state
- calibration time
- queue time
- transfer time
- execution time
- predicted times
- candidate finish times
- selected policy
- estimator
- scenario
- seed
- software version
- hardware configuration
- randomized flag

Do NOT create fake CSV values.

Use randomized profiling campaigns for training/evaluation.
Avoid leakage from random row splitting.
Prefer splits by:
- task size
- occupancy/load
- session/time

PHASE 7:
Build the experiment harness.

Same seeded traces must be replayable across policies.
Use randomized experiment order where appropriate.
Use repeated runs and preserve raw results.

Initial key experiments:
K1: task performance alone on P vs E
K2: P-core task under increasing E-core load
K3: performance/calibration behavior under sustained load
K4: runtime scheduling overhead
K5: P-core sibling/HT interference if measurable

Then scheduling experiments comparing:
- static/profile estimators
- history estimator
- learned estimator
- oracle

Measure:
- makespan
- task response time
- throughput
- resource utilization
- scheduling overhead
- offload overhead
- prediction error
- decision regret
- scheduling decision changes

Also analyze:
- prediction margin between best and second-best workers
- cases where ML changes the scheduling decision
- cases where prediction is unnecessary
- offloading break-even conditions

CODING RULES:
- Keep components modular.
- Use Python unless there is a strong reason not to.
- Prefer standard libraries plus lightweight dependencies.
- Do not add huge frameworks unnecessarily.
- Do not require Docker/WSL for the core runtime.
- Do not download large datasets unless actually required.
- Do not delete existing user files.
- Preserve useful existing code.
- Add documentation for every major component.
- Add tests for important runtime behavior.
- Make scripts directly runnable on Windows.
- Use config files instead of hard-coded experimental settings.
- Log raw data first; generate summaries afterward.

RESEARCH INTEGRITY:
Never invent measurements.
Never invent hardware capabilities.
Never claim an experiment passed if it was not actually run.
Never claim novelty unless supported.
When an assumption is necessary, mark it clearly in documentation.
When a feature cannot be reliably measured on Windows, document the limitation and use a defensible proxy.

AUTONOMOUS WORK MODE:
You are responsible for implementing the project, not merely describing how to implement it.

First:
1. Inspect the existing repository/files.
2. Determine what already exists.
3. Create a clean project structure if needed.
4. Create a PROJECT_STATUS.md and ARCHITECTURE.md.
5. Start implementing Phase 0 immediately.

Then continue through the phases in order whenever the previous phase has been implemented and validated.

Do not stop just because the project is large.
Work incrementally.
Run tests/benchmarks after implementing components.
Fix errors you encounter.
Keep PROJECT_STATUS.md updated with:
- completed work
- current work
- next work
- known limitations
- commands used
- test results

At the end of each major phase, leave the repository in a runnable state.

Do not ask me for routine confirmations.
Do not redesign the project.
Only stop and ask me if there is a genuinely blocking decision that cannot be resolved from the project requirements.

START NOW.
