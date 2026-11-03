# CPU/GPU profiling and opportunity audit (Phase 1)

2026-10-25, branch `revival/resource-state-aware`. Protocol: `PROTOCOL_gpu_cpu_profile.md` (written before the sweep; amendments A1 to A4 dated). No scheduler, coordinator, worker pool, estimator or earlier protocol was changed. All data: `data/results/revival_gpu_profile_20261025/`.

## 1. Decision

**Opportunity not established. Do not launch a GPU-contention scheduling pilot on these workloads.** Measured facts behind it: only 6.4% of dispatches of the real runtime (blind greedy B4 with the CUDA worker, 20 046 dispatches) have two or more eligible idle workers and only 0.8% have both the GPU worker and a CPU worker idle; the CPU-only `img_source` stage is 60% of the work, so the GPU can touch at most 40%; and a validated list-scheduling simulation shows an oracle with perfect cost knowledge that obeys the same work-conserving rule gains 0.0 to 0.05% over B4 under both a quiet and a busy GPU. GPU contention is real and does flip the best device for large denoise tasks, but that cannot be exploited when the placement is forced. Details and the one formally satisfied sub-gate are in section 8.

## 2. Hardware and software (measured)

NVIDIA GeForce RTX 3050 6GB Laptop GPU, driver 581.83, torch 2.11.0+cu128; 14 physical / 20 logical CPU cores (6 P cores at even logical ids, 7 E cores 13 to 19, coordinator on core 12); 15.7 GB RAM; Windows 11; Python 3.11.9; AC power throughout (the run refuses battery). NVML (`pynvml`) is **not installed** and was not installed: GPU utilisation, memory, power, temperature and clocks come only from `nvidia-smi` at about 0.5 s intervals, and one call costs 0.14 to 0.16 s (median) so the label attached to a task can lag the real GPU state by up to about 0.7 s. Free VRAM and utilisation were therefore NEVER available as per-decision signals; they were available as profiling-time samples only. Repository state before work: branch `revival/resource-state-aware` @ `b84e489`, tracked change `progress.txt`, 70 untracked entries, tag `baseline-null-result`, no remotes (`env.json` of every run).

## 3. Which stages run on the GPU (from the code, not from names)

`CUDA_STAGES` = `img_denoise`, `img_edges`, `img_features` (`apps/cuda_stages.py`). `img_source`, `img_tile`, `img_mosaic`, `img_aggregate`, `img_package` have no CUDA variant. A CUDA worker runs application stages only and does decode, encode and artifact I/O on the host with the CPU stage's code. Equivalence tolerances (unchanged): denoise bit-exact, edges max |d| <= 1 and <= 0.1% of pixels, features relative 1e-9. The profile enforced them on every sample: **0 failed samples** among 928 valid single-task samples and 544 pair samples (`counts.json`); CPU outputs were byte-identical to the sequential reference.

## 4. What was run

| Item | Result |
|---|---|
| Smoke run (3 blocks, 256/512 px) | complete; machinery check only, not used |
| Main sweep attempt 1 (`profile_main`) | stopped after block 0: free RAM 0.92 GB < 1.0 GB rule (kept, not used) |
| **Main sweep attempt 2 (`profile_main2`)** | blocks 0 to 8 completed, then the same RAM rule fired (0.49 GB): **8 measured repetitions** per condition (4 for 2048 px cells), 1678 samples, 0 failed; THIS is the data of the report |
| Attempts 3, 3b, 4 | stopped by the RAM rule before or right after block 0 (0.20, 0.25, 0.39 GB); no usable samples; kept |
| Monitoring on/off mini-profile | complete (8 blocks) |
| DAG-runtime reference runs (W1, W2) | **not run**: three attempts (`dag_w1`, `dag_w1b`, `dag_w1c`) stopped at the first block preflight with 0.54, 0.59 and 0.67 GB free, the last one launched with 3.0 GB free (the 14-worker pool plus reference artifacts need more than 2 GB); the audit uses stored real runs and a validated simulation instead (deviation from protocol section 4(b), amendment A5) |

The planned 15 to 25 repetitions were not reached: another application set (a WSL virtual machine holding about 3 GB, browser, desktop clients) left only 0.2 to 2 GB free during most of the session, and the stopping rule (1.0 GB) was not weakened. Consequence: confidence intervals are wider than planned and rare outliers weigh more.

## 5. Complete cost per task (median of occupation = submit to result received, ms; 8 repetitions, quiet GPU unless marked)

| Task | P | E | G | G, GPU busy | best (quiet -> busy) |
|---|---:|---:|---:|---:|---|
| img_edges 256 px | **6.2** | 9.9 | 7.2 | 8.0 | P -> P |
| img_edges 512 px | 13.6 | 29.5 | **9.1** | 9.5 | G -> G |
| img_edges 1024 px | 45.0 | 99.1 | **14.8** | 18.8 | G -> G |
| img_edges 2048 px (4 rep) | 176.6 | 378.8 | 124.8 | 53.5 | G -> G (the quiet G value has an outlier, see section 9) |
| img_features 512 px | **6.3** | 11.5 | 7.5 | 8.9 | P -> P |
| img_features 1024 px | **14.7** | 30.8 | 14.9 | 16.2 | P -> P (tie) |
| img_features 2048 px (4 rep) | 52.4 | 110.8 | **22.2** | 40.6 | G -> G |
| img_denoise x8 512 px | **52.3** | 156.4 | 63.6 | 142.2 | P -> P |
| img_denoise x8 1024 px | 215.3 | 693.8 | 214.2 | 515.0 | G (tie) -> **P (firm flip)** |
| img_denoise x60 512 px | **366.5** | 1133.4 | 461.9 | 995.7 | P -> P |
| img_denoise x60 1024 px | 1562.3 | 5103.6 | **1156.9** | 3569.5 | G -> **P (firm flip)** |
| img_source 512 px (CPU only) | 102.0 | 221.6 | n/a | n/a | P |

Read-outs. (a) The GPU wins on complete cost for `img_edges` from 512 px (1.5x at 512, 3.0x at 1024), for `img_features` only at 2048 px, for `img_denoise` only for heavy variants at 1024 px (x60: 1.35x; x8: parity). (b) A busy GPU (continuous 4096 x 4096 matrix products from a second process; `nvidia-smi` utilisation median 100% against 0% quiet) multiplies G occupation of denoise by 2.2x (512 px) to 3.1x (x60 at 1024 px) but leaves the small edges kernels nearly unchanged (+3% to +27%); P and E occupation of large tasks changes by less than 5%, small CPU tasks (edges, features at 512 px) by +16% to +32% with coefficients of variation of 30% to 60%. (c) Hypotheses of the protocol: H1 holds for edges and features; H2 holds for denoise only (edges stays below 1.5x); H3 holds for tasks above 50 ms and fails for 5 to 15 ms tasks; H4 holds (P+G pair efficiency 0.88 to 1.03 for tasks above 50 ms; `overlap.csv`; small edges at 512 px 0.69); H5 holds (section 7).

Variability (coefficient of variation of the 8 repetitions): P 4 to 20% for tasks above 10 ms; E 1 to 15%; G 4 to 100%: the CUDA path has occasional large outliers (for example `img_denoise` x8 at 512 px quiet G has a 95% interval of the median [50.6, 324.6] ms around a median of 63.6), which is why many G intervals in `summary.csv` are wide.

## 6. Where the time goes (quiet; share of occupation)

| Task, device | occupation (ms) | kernel (incl. H2D/D2H for G) | artifact I/O + decode + encode | IPC in + out | other worker time |
|---|---:|---:|---:|---:|---:|
| img_edges 512, G | 9.1 | **33%** | **51%** | 8% | 2% |
| img_edges 512, P | 13.6 | 72% | 21% | 5% | 1% |
| img_edges 1024, G | 14.8 | 23% | 61% | 5% | 3% |
| img_features 512, G | 7.5 | 27% | 51% | 10% | 1% |
| img_features 512, P | 6.3 | 45% | 43% | 11% | 0% |
| img_denoise x8 1024, G | 214 | 90% | 7% | 1% | 0% |
| img_denoise x8 1024, P | 215 | 97% | 3% | 1% | 0% |

For the cheap GPU stages the kernel is a minority of what a scheduler would have to predict: the host-side costs measured separately in this process are `write_artifact` 2.4 to 3.0 ms (temporary file plus atomic replace), read 0.5 to 0.6 ms, decode 0.3 to 0.5 ms, encode 0.1 to 0.3 ms per 512 px task. H2D and D2H of a 512 px edges input are 0.29 and 0.27 ms, the whole CUDA function 2.3 ms (derived kernel 1.8 ms), but the same task occupies the G worker for 9.1 ms. Worker startup (pool creation including CUDA context) was 9.3 s; warm-up tasks are recorded and excluded.

## 7. How often is there a choice? (Q5)

Reconstructed from the event logs of REAL runs (read only; late-binding policies only, where the set of idle workers at a dispatch is well defined): B4 with the CUDA worker, 20 046 dispatches: **93.6% forced (one eligible idle worker), 6.4% two or more, 0.8% with both a G and a CPU worker idle**; `PredictedRankGreedy` and the three revival policies (7710 dispatches each): 5.1% two or more, 0.0% G-and-CPU. 98% of the tasks waited in the ready queue. (Early-binding policies are not interpretable by this reconstruction and are excluded.) Simulated (section 8), quiet / busy GPU: at 512 px 5.1% / 4.7% with two or more idle workers and 0.4% / 0.0% with G and CPU; at 1024 px 14.6% / 21.9% and 1.0% / 4.2%.

## 8. Opportunity estimate and gate (the numbers are labelled by kind)

* **Measured:** sections 5 to 7 and the stored makespans (B4_gpu 1.754 s, B0_P_only 2.406 s, quiet).
* **Simulation (estimate):** a deterministic list scheduler over the measured medians for 64 chains at 512 px (and 24 chains at 1024 px), serial coordinator cost per dispatch fitted ONCE so that the simulated B4_gpu equals the measured 1.754 s (fitted value 4.9 ms per dispatch, a catch-all for all serial work). Validation not used in the fit: simulated B0_P_only 2.377 s against measured 2.406 s (-1.2%). The 1024 px workload has no measured counterpart (unvalidated).
* **LP bound (estimate):** a fluid lower bound that ignores precedence and the coordinator; it is an unattainable limit, not a schedule.

| Workload | load | best simple (sim) | oracle, same work-conserving rule (sim) | headroom (sim) | LP bound x overhead ratio r | headroom vs LP (upper bound) |
|---|---|---|---|---:|---:|---:|
| W1 512 px, 64 chains | quiet | B4_gpu_all 1.754 s | 1.753 s | 0.05% | - | 27.3% |
| W1 | GPU busy | B4_gpu_all 1.827 s | 1.827 s | 0.00% | - | 26.4% |
| W2 1024 px, 24 chains (unvalidated) | quiet | B4_gpu_all 1.829 s | 1.829 s | 0.00% | no r | 22.6% raw |
| W2 | GPU busy | B4_gpu_all 2.319 s | 2.317 s | 0.05% | no r | 47.6% raw |

Gates of the protocol (section 6): **G1** (a firm flip of the best device under GPU contention for a class with at least 20% of the work): W1 fails (no flip at 512 px); W2 holds (`img_denoise` x8 flips G -> P, 34% of the work). **G2** (at least 20% of dispatches with two or more eligible idle workers including a G and a CPU worker): fails for the measured real runs (0.8%) and for both simulated workloads (0.4% and 4.2%). **G3** (headroom of at least 5%): the LP-based value formally exceeds 5% (26 to 27% for W1) but it is the unattainable bound; the validated simulation of the same rule class the scheduler would have to obey gives 0.0 to 0.05%. The LP gap is mostly structure that no placement removes: 60% of the work is `img_source` (CPU only) and the dispatch path is serial (about 4.9 ms effective per task in this fit, 257 dispatches in 1.75 s). All three gates must hold; G2 does not. In the simulation the contended GPU costs W2 27% of its makespan (1.83 s -> 2.32 s), so contention matters for the workload; but with one CUDA worker that is usually the only idle worker when it frees up, work-conserving placement cannot avoid it, and refusing it (`B4_gpu_ef`, denoise on CPU only) is not better (2.356 s) because the slow GPU still adds capacity.

## 9. Telemetry, monitoring cost, limitations

* `nvidia-smi` sampling: 919 samples, none unavailable; maximum 76 C and 60.5 W under the burner; utilisation at task time: quiet median 0%, busy median 100%.
* Cost of monitoring (same mini-profile with the monitor on and off, alternating, 8 blocks): pooled median change of occupation **+0.4%** (cell values from -5.0% to +10.1%, i.e. at the noise level of 8 repetitions); `nvidia-smi` call 0.16 s.
* Not achieved: 15 to 25 repetitions (8; 4 at 2048 px), DAG-runtime reference runs (RAM), a measured contended makespan of any policy. The 2048 px cells carry an outlier-sensitive quiet G value for `img_edges` (124.8 ms against 53.5 ms busy, 4 repetitions each), reported as measured and not interpreted.
* The burner is one process on one GPU context; real co-tenants, thermal throttling over long runs and multiple GPUs are out of scope.

## 10. Next step

**Stop this avenue for the registered workloads.** If a GPU-contention study is ever revisited it needs a redesign that creates real choices first, and that redesign can be screened without hardware by changing the inputs of the simulator (`gpuprofile.simulate_list_schedule`, validated here at quiet): GPU-eligible work must dominate (inputs pre-generated so `img_source` is not 60%), tasks long enough that dispatch is not the bottleneck, and fewer ready tasks than workers for a meaningful share of the time. Only if that simulated oracle headroom reaches 5% would a measured pilot be justified. The resource-state-aware scheduler is NOT shown to improve performance by this phase.

## 10b. Tests (actual)

`tests/test_gpu_profile.py`: 14 passed (arguments and configuration, deterministic block order, summaries excluding warm-up and invalid samples and recomputed from raw, best-device flip detection, telemetry unavailable = null with a reason, monitor thread and file, burner cleanup on normal exit / never-ready timeout / lifetime expiry, dispatch-choice reconstruction, LP against a hand calculation, simulation against hand calculations, verification of a corrupt CPU output and an out-of-tolerance CUDA output, no overwrite of existing paths, manifest verification, and one hardware test that skips without CUDA; it ran here). Full suite (`logs/phase1_pytest.txt`): **471 passed, 1 failed in 333 s**; the failure is `tests/test_profile_montage.py::test_profile_format_csv_fit_and_cleanup`, which reads the machine's real free RAM and refused to start with 1.61 GB < 2.0 GB; it passes when run alone with 3.0 GB free (2 passed), so it is the known free-RAM guard under memory pressure, which was not weakened. mypy (`logs/phase1_mypy.txt`) reported two typing errors in the new script on the first run; fixed, `mypy scripts/revival_profile_cpu_gpu.py`: no issues. Manifests of every run directory verify (`verify` subcommand: all OK).

## 11. Commands

```bash
# tests and typing
.venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_gpu_profile.py
.venv/Scripts/python.exe -m pytest -p no:cacheprovider -q
.venv/Scripts/python.exe -m mypy src scripts/revival_profile_cpu_gpu.py --ignore-missing-imports
# regenerate every table from the saved raw samples (no profiling is rerun; output dirs are created exclusively)
R=data/results/revival_gpu_profile_20261025
.venv/Scripts/python.exe scripts/revival_profile_cpu_gpu.py summarize $R/profile_main2 /tmp/summary_again
.venv/Scripts/python.exe scripts/revival_profile_cpu_gpu.py summarize $R/profile_main2 /tmp/x --check $R/summary_main2/summary.csv   # recomputed table identical?
.venv/Scripts/python.exe scripts/revival_profile_cpu_gpu.py opportunity $R/profile_main2 /tmp/opp_again --stored data/results/revival_20261025/uniform2_sessions/* data/results/study2_20261024/confirm_sessions/* --validate data/results/revival_20261025/analysis_uniform2_ref_B4_gpu
.venv/Scripts/python.exe scripts/revival_profile_cpu_gpu.py verify $R/profile_main2 $R/monitor_overhead $R/summary_main2 $R/opportunity   # SHA-256 manifests
# rerun the safe profile (mains power and >= 1 GB free RAM required; needs the GPU)
.venv/Scripts/python.exe scripts/revival_profile_cpu_gpu.py run data/results/revival_gpu_profile_NEW/profile --blocks 20
# roll back only what this phase added (nothing existing is touched); review the list first
git diff --stat b84e489..HEAD -- docs/revival/GPU_CPU_OPPORTUNITY_REPORT.md docs/revival/PROTOCOL_gpu_cpu_profile.md src/caosched/revival/gpuprofile.py scripts/revival_profile_cpu_gpu.py tests/test_gpu_profile.py
git revert --no-edit <the Phase 1 commits>          # or: git checkout b84e489 -- <those five paths>; data/results/revival_gpu_profile_20261025 is plain data and can be archived
```
