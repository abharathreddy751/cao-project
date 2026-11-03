# Protocol: CPU/GPU profiling and opportunity audit (Phase 1)

Written 2026-10-25 on branch `revival/resource-state-aware` (base commit `b84e489`), BEFORE the measurement sweep. Amendments are appended below with a date, before the
experiment they affect. Nothing here changes the scheduler, coordinator, worker pool, estimators or earlier protocols; the profile only reads them.

## 1. Questions

Q1 which stages can run on the GPU; Q2 at which image sizes the GPU is faster than a P or E core when the COMPLETE task cost is measured; Q3 how that cost splits into compute,
host/device transfer, conversion (decode/encode), artifact I/O, IPC and setup; Q4 whether GPU contention changes which resource is best for a task class; Q5 how often the real DAG runtime
offers two or more eligible idle workers at a dispatch; Q6 whether the evidence justifies a GPU-contention scheduling experiment that could beat the strongest simple work-conserving
policy by at least 5%.

## 2. Supported device mappings (from the code, fixed now)

`CUDA_STAGES` (`apps/cuda_stages.py`) contains exactly `img_denoise`, `img_edges`, `img_features`. Every other stage (`img_source`, `img_tile`, `img_mosaic`, `img_aggregate`,
`img_package`) has no CUDA variant and is CPU-only. A CUDA worker runs application stages only and needs the CPU stage for decode/encode/artifact I/O
(`core/worker_pool.py`, `_worker_loop`). Equivalence tolerances (`scripts/gpu_spike.py`, fixed before this profile and not changed): `img_denoise` bit-exact; `img_edges` max abs diff <= 1 level and
<= 0.1% of elements; `img_features` max relative error <= 1e-9. All-CPU outputs must be byte-identical to the sequential reference.

## 3. Method

* One `WorkerPool` for every measurement of the run: one P worker (second P slot), one E worker, one CUDA worker, warm-up disabled in the pool (as the adapters do) and replaced by an explicit
  warm-up of every worker on every cell before measuring (3 discarded tasks per worker per cell per block-0 visit; recorded with `warmup=true`). The profiler process is pinned to the
  coordinator's reserved core. The GPU contention process is pinned to one E core that hosts no worker. No condition rebuilds the pool.
* Cells: `img_denoise` (radius 2.0) with iterations 2, 8 and 60 at sides 256, 512, 1024; `img_edges`, `img_features` at sides 256, 512, 1024, 2048; `img_denoise` iterations 2 and 8 at 2048
  (60 iterations at 2048 is skipped: about 4 s per P sample). CPU-only reference cells: `img_source` at the four sides on P and E. Inputs of a cell are ONE set of artifacts produced by the
  CPU stages, shared by every device condition (sha256 recorded).
* Per task the profiler submits through `WorkerPool.submit` and receives with `poll_result`, so the cost includes exactly the IPC and worker path of the real runtime. Timestamps (all
  `clock.now()` = `time.perf_counter`, system-wide on Windows and pinned by `tests/test_clock.py`): coordinator submit, worker `t_started`, worker `t_completed`, coordinator receipt. Worker reports
  kernel seconds (`wall_time_seconds`; for CUDA it includes H2D, kernels and D2H) and `io_s` (artifact read + decode + encode + write). Derived: `ipc_in` = t_started - t_submit; `worker_span`;
  `worker_other` = span - kernel - io_s; `ipc_out` = t_recv - t_completed; `occupation` = t_recv - t_submit (the complete cost a scheduler would have to predict).
* Components that the worker does not separate are measured separately, in the profiler process, before the pool starts: read, decode, encode, write per (stage, side); H2D, D2H and kernel of
  each CUDA stage (CUDA events and `torch.cuda.synchronize`; kernel = total - H2D - D2H, labelled derived); startup of a worker (pool creation to ready, from `ready_infos`).
* Conditions per block: phase `quiet` (GPU burner paused) and phase `contended` (burner running), each visiting every (cell, device in {P, E, G}) once in an order shuffled with a block seed;
  phase order alternates between blocks. Contended P and E samples answer "CPU work while the GPU is busy". Phase `pair`: for every cell the same task is submitted at the same instant to the P worker and
  the CUDA worker (quiet GPU), and to the E worker and the CUDA worker; the time until BOTH finished is compared with the larger of the two solo occupations (overlap efficiency).
* GPU contention: `revival.gpuprofile.GpuBurner`, a spawned process (module-level target, `__main__`-safe), pinned to an E core, running continuous 4096 x 4096 float32 matrix products with a
  synchronise per product, ready/stop/pause events, a hard timeout, termination in `__exit__` and `atexit`. Its achieved load is sampled with `nvidia-smi` (below), never assumed.
* Telemetry: NVML (`pynvml`) is not installed and is not installed here. `nvidia-smi --query-gpu=...` is used at low frequency (one sample about every 0.5 s) in a thread of the profiler process
  that is never called from a task path. Fields: utilisation.gpu, memory.used, memory.total, power.draw, temperature.gpu, clocks.sm. Per-call cost is measured. Unavailable fields are `null` with
  a reason. Monitoring overhead is measured separately: the same mini-profile (a fixed set of 6 cells x 3 devices, 12 repetitions) with the monitor on and off, alternating by block.
* Repetitions: 20 blocks (block 0 is warm-up and discarded), i.e. 19 measured repetitions per condition; cells at 2048 px run in every second block (10 repetitions) because of their duration. Any
  reduction is recorded in the summary.
* Controls before each block: mains power (abort otherwise), free RAM >= 1.0 GB (abort otherwise), system CPU utilisation over 1 s below 20% (wait up to 30 s, recorded), GPU temperature below
  85 C (cool down; abort if not reached in 60 s). Worker death or more than 10% failed samples in a block stops the run (recorded).
* Verification (outside the timed region): CPU outputs byte-identical to the in-process sequential reference of the same cell; CUDA outputs decoded and compared with `gpu_spike.compare` and `TOL`.
  A sample is VALID iff the task returned without error and verification passed; failed samples stay in the raw file with `valid=false` and the reason; summaries use valid, non-warm-up samples
  only. Rule fixed now; tolerances are not modified.
* Data: every sample is one JSON line in `raw_samples.jsonl` (schema `gpuprofile/1`), plus `env.json`, `telemetry.jsonl`, `host_side.json`, `transfer.json`, `monitor_overhead.json`; `summary.csv` and
  all tables are regenerated from the raw files by `scripts/revival_profile_cpu_gpu.py summarize`. `SHA256_MANIFEST.tsv` covers every file. Output directories are created exclusively.

## 4. Opportunity audit (fixed now)

(a) Best device per cell under quiet and contended GPU from the median `occupation` with a 95% bootstrap interval of the median difference (seed 0); a FLIP is a change of the best device between
quiet and contended in which the intervals of the two best candidates do not overlap in one of the loads.
(b) DAG-runtime reference (small, not confirmatory): the Study 2 uniform batch (64 chains, 512 px, denoise 8 iterations, GPU-eligible stages through the CUDA worker) run through `Study2Adapter`
with policy B4 and the variants `B4_gpu_all` (denoise, edges, features on G), `B4_gpu_ef` (edges, features on G), `B4_cpu` (G ineligible), in both loads, 10 blocks (block 0 warm-up), alternating load
order, same pool for every run, outputs verified by the adapter. Raw event logs are kept.
(c) Choice counts: from the event logs of (b) AND of the stored uniform-batch sessions (`uniform2_sessions`, read only), the set of eligible idle workers at every dispatch is reconstructed
(busy from dispatch to completion event; eligibility from the task's pools): shares with 1, >=2, and with both a G and a CPU worker; and the share of dispatched tasks that had to wait in the ready queue.
(d) Headroom estimate (an ESTIMATE, labelled so): a fluid lower bound on the makespan from a linear program over measured per-(stage, pool) mean occupation (unrelated machines, no precedence), once with
quiet and once with contended costs, versus the strongest simple baseline of (b) in the same load; the structural overhead ratio r = (measured B4_cpu makespan) / (LP bound with CPU pools only) corrects the
bound for coordinator and startup overhead. Headroom_realistic = best_simple / (LP_bound x r) - 1; Headroom_raw without r. No optimality claim is made.

## 5. Hypotheses (stated before the sweep)

H1 the GPU wins on complete cost for `img_edges` from 512 px and `img_features` from 1024 px and not for 256 px; `img_denoise` is near parity (0.9x to 1.5x) at 8 iterations. H2 a continuous GPU burner
raises CUDA occupation by a factor >= 1.5. H3 P and E occupation change by < 5% under GPU contention. H4 solo P + G overlap with efficiency >= 80%. H5 fewer than 20% of dispatches in the uniform
batch have >= 2 eligible idle workers including both a G and a CPU worker. Outcomes outside these are reported.

## 6. Continuation gate (fixed now; all must hold)

GO to a GPU-contention scheduling pilot only if ALL of: G1 at least one FLIP exists for a task class that carries >= 20% of the total work of the representative uniform batch; G2 >= 20% of dispatches in the
reference runs have >= 2 eligible idle workers including a G and a CPU worker; G3 Headroom_realistic >= 5% under contention. Otherwise the decision is "opportunity not established" and no pilot or
confirmatory campaign is launched. In either case the next step recommended in the report follows from which of G1 to G3 failed.

## 7. Stopping rules

Stop and report if: power is lost, RAM falls below 1.0 GB, a worker dies, GPU temperature stays above 85 C for 60 s, the wall-clock budget of 90 minutes is exceeded (the partial raw file is kept and the
summary states the achieved repetitions), or verification fails for more than 10% of a block.

## 8. Not covered

GPU utilisation or VRAM as scheduler inputs (only profiling-time `nvidia-smi` samples exist); multi-GPU; remote GPU; a scheduler change; any claim that the resource-state-aware scheduler improves performance.

## 9. Amendment A1 (2026-10-25, before the second attempt of the main sweep)

The first attempt (`profile_main`, started 09:11 UTC) stopped at its block-1 preflight because free RAM fell to 0.92 GB, below the 1.0 GB stopping rule of section 3 (other applications on the
machine: browser and the desktop client). The rule worked as designed; the 206 samples written before the stop are retained in `profile_main/` (no manifest: the script then terminated through
`SystemExit` without finishing; it now records the stop and writes the manifest) and are NOT used. The sweep is rerun unchanged (same cells, conditions, repetitions, thresholds) into
`profile_main2/`. If a stopping rule fires again, the partial result is reported as partial. The only code change is that a preflight stop is recorded in `run_end.json` and the manifest is written.

## 10. Amendment A2 (2026-10-25, before the third attempt)

The second attempt (`profile_main2`) completed blocks 0 to 8 (8 measured repetitions per condition; 1678 samples; manifest written) and stopped at the block-9 preflight because free RAM fell to
0.49 GB (stopping rule of section 3; the browser and desktop client on the machine are the other memory users). It is a valid PARTIAL result and is kept as it is. To approach the planned 15 to 25
repetitions, one more run with the same code, cells, conditions and thresholds but a different block seed is started into `profile_main3` (12 blocks, the first is its own warm-up). The two runs
are analysed pooled ONLY by concatenating their raw samples (the `run_block` and the source directory stay in every record, so each can also be analysed alone); the summary states the number of
measured repetitions actually achieved per cell. If the third attempt is also stopped early, the pooled result is whatever was completed. Cells at 2048 px run in even blocks only, so they have fewer repetitions.

## 11. Amendment A3 (2026-10-25, after the partial main sweep, before any DAG-runtime reference run)

The partial main sweep (`profile_main2`, 8 repetitions, 0 failed samples) shows per-task results that bear on section 6 before the DAG reference exists: at 512 px (the representative uniform batch)
the best device is G for `img_edges`, P for `img_features` and `img_denoise` (8 iterations), under both loads; a firm best-device flip under GPU contention exists only for `img_denoise` at
1024 px and above (G is best or tied when quiet, P when the GPU is busy). Gate G1 as written (a flip for a class carrying >= 20% of the work of the uniform batch) is therefore expected to fail for the
512 px batch. To avoid concluding about the whole avenue from one workload, the DAG reference of section 4(b) is run on TWO workloads, both fixed here: W1 = the registered uniform batch (64 chains, 512 px,
denoise 8 iterations); W2 = a larger-image batch chosen from the per-task flips already seen (24 chains, 1024 px, denoise 8 iterations). The gate of section 6 is evaluated for each workload separately and the
report states both verdicts; W2 is a candidate redesign for a possible later study, not a result about the project's registered workload. G1 uses the work shares and flips of the workload's own image
side (profile cells at 512 for W1, at 1024 for W2). Nothing else changes. Known limitation recorded here: the telemetry sample attached to a task can lag the real GPU state by up to about 0.7 s
(0.5 s interval plus a 0.14 s `nvidia-smi` call), so `gpu_util_pct` of a sample taken just after a phase change can still show the previous phase; the burner pause/resume timing, not the
telemetry label, defines the load condition.

## 12. Amendment A4 (2026-10-25, before the fourth attempt)

Attempts 3 and 3b were stopped by the RAM rule at the preflight of block 0 (free RAM 0.20 GB and 0.25 GB; a WSL virtual machine and the desktop clients hold most of the 15.7 GB); they wrote no samples and are
kept as empty-result directories (`profile_main3`, `profile_main3b`, with `env.json`/`run_end.json`). Free RAM at idle is now 1.7 to 2.0 GB. The profiler carried an unnecessary CUDA context of its own for the whole sweep (the
H2D/D2H/total micro-profile ran in the profiler process); that micro-profile now runs in a short-lived child process (same code, same cells), so the sweep needs about 1.5 GB less memory. The measured
conditions (workers, cells, loads, order, thresholds) are unchanged. The monitoring-overhead run now also applies the free-RAM, power and temperature preflight. A fourth attempt (`profile_main4`, 12 blocks, seed
20262611) is made; it is pooled with `profile_main2` only by concatenating raw samples, as in A2. The RAM threshold (1.0 GB) is not lowered.

## 13. Amendment A5 (2026-10-25, after the third DAG-reference attempt)

The DAG-runtime reference runs of section 4(b) could not be executed: three attempts (`dag_w1`, `dag_w1b`, `dag_w1c`) were stopped by the free-RAM rule at their first block (0.54, 0.59, 0.67 GB free; the last was
launched with 3.0 GB free), because the 14-worker pool, the CUDA contexts and the reference artifacts need more than 2 GB. The rule was not lowered. Substitution, fixed here before the opportunity analysis was
run: (c) choice counts come from stored REAL runs (read only: `uniform2_sessions`, `confirm_sessions`); (d) the headroom estimate uses a list-scheduling simulation over the measured profile medians, with one
serial-coordinator constant fitted on the stored B4_gpu makespan and validated on the stored B0_P_only makespan, together with the LP bound; G3 is judged on the simulation and the LP is reported as an
unattainable upper bound. W2 (1024 px) has no stored measured counterpart and is marked unvalidated. The gate decision rule (all of G1, G2, G3) is unchanged.
