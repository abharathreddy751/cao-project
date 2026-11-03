# Baseline audit (2026-10-25, before any source change of the revival)

All results below were measured in this session on this checkout unless marked "documented, not rerun". Raw outputs: `docs/revival/logs/`.

## 1. Repository state

| Item | Value |
|---|---|
| Starting branch | `study2/affinity` |
| Starting commit | `ceae09451ce437ad4bdbd895e5fe19e361af1b85` ("Study 2: two-factor confirmatory result (section 32) ...") |
| Tags | `baseline-null-result` (`7dd1847`, the stage 1-5 null result) |
| Git remotes | none (`git remote -v` prints nothing): nothing can be pushed, none was |
| Tracked change at start | `data/results/study2_20261024/progress.txt` (a run log appended by the sessions) |
| Untracked at start | 57 entries: `PROJECT_MASTER_DOCUMENTATION.md`, `STUDY_MATERIAL.md`, `STUDY_MATERIAL_FINAL.md`, and session/analysis directories of Study 2 under `data/results/study2_20261024/` |
| Checkpoint (outside the repo) | `D:\cao_checkpoint_revival\`: `repo_ceae094.bundle` (all refs), `tracked_changes.patch`, `git_status.txt`, `git_log.txt`, copies of the three untracked documents |
| Work branch | `revival/resource-state-aware`, created with `git switch -c` from `ceae094`: the working tree (including all untracked data) is carried over unchanged |

Nothing was stashed, reset, cleaned or deleted. The raw evidence of Study 2 stays untracked in the working tree (it is large; `data/results` is kept out of Git by the Stage 0 record).

## 2. Environment (measured)

Windows 11 Home 10.0.26200; Python 3.11.9; Intel hybrid CPU with 14 physical / 20 logical cores (6 P cores at even logical ids 0 to 10, 7 E cores at logical ids 13 to 19, coordinator on logical core 12, from `RuntimeConfig.from_topology`); 15.7 GB RAM (3.4 GB free at the start of the audit); NVIDIA GeForce RTX 3050 6GB Laptop GPU, driver 581.83, torch 2.11.0+cu128, `torch.cuda.is_available() == True`; on AC power (battery 100%, plugged in); disks: D: 84 GB free, C: 20 GB free. Packages: numpy 2.4.6, scipy 1.17.1, catboost 1.2.10, pytest 9.1.1, mypy 2.4.0, psutil 7.2.2. **Not installed: `pynvml`** (so GPU utilisation/VRAM telemetry is not available through NVML in this environment; the revival marks it unavailable instead of guessing).

## 3. Tests and static typing (measured)

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q -rA` | **438 passed in 213 s** (`logs/baseline_pytest.txt`) |
| `.venv\Scripts\python.exe -m mypy src --ignore-missing-imports` | **Success: no issues found in 85 source files** (`logs/baseline_mypy.txt`). Without `--ignore-missing-imports` mypy reports 16 "stubs not installed" notes (psutil and others), not code errors |
| `tests/test_claims.py` | 24 passed (part of the 438): every claim in `docs/research_redesign/claims.json` equals the number in its stored `effects.csv` |

Known free-RAM guard of the Montage profile test (`tests/test_profile_montage.py::test_refuses_low_free_ram`): it **injects** `free_fn`, so it does not read the machine's real free RAM and passes under memory pressure in this checkout (3.4 GB free). The guard in the production code path (`min_free_gb`) was not weakened. The older failure noted in the supplied summary could not be reproduced here and is therefore reported as "not reproduced".

## 4. Reproduction of stored results from raw logs (measured)

`scripts/reproduce_subset.py` re-derived the tables from the raw event logs and re-checked every event-log hash against its run manifest:

| Stored analysis | Result |
|---|---|
| `analysis_iters_confirm2_ref_B4` (one-factor hidden-cost, 6P+7E) | all checks true (`logs/repro_analysis_iters_confirm2_ref_B4.json`) |
| `analysis_confirm_ref_B4_gpu` (uniform batch with the CUDA worker) | all checks true (`logs/repro_analysis_confirm_ref_B4_gpu.json`) |
| `analysis_classes_confirm_ref_B4` and `..._ref_PRED_RANK_GREEDY` (two-factor, written earlier today) | all checks true after the session manifest was generated |

Claims reproduced: the two-factor effects of section 32 (learned policy +17.4% / +17.1% better than size-only / P-only, level with B4 at +0.9% slower with interval -0.9 to +2.8). Claims **documented, not rerun**: the 20 to 45% gains on the one-factor workloads (sections 18 to 27), the stage 5 Montage null; their stored analyses reproduce from raw logs as shown, the experiments themselves were not repeated.

## 5. Code audit (read from the code; each point cites the file)

* **Eligibility is uniform.** Every scheduler in `src/caosched/schedulers/` and `study2/policies.py` selects from `eligible_workers()` (`core/scheduler_base.py`), and the coordinator re-checks the choice against `task.eligible_pools` and raises `SchedulerContractError` otherwise (`core/coordinator.py:268`). A task not listed for the CUDA pool `G` cannot be dispatched there.
* **Late vs early binding.** `binds_only_idle` is enforced by the coordinator (line 272); early binding to a busy worker queues the task locally. `PredictedRankGreedy` is late-binding.
* **Feature timing.** `EstimateContext.from_state` is built at decision time from the runtime state; `ctx_version 2` stores the context of each decision and feeds the same object to `observe` (`schedulers/eft.py`). `ParamModelEstimator` reads only the task's own declared parameters and size. No actual-runtime field of the task being scheduled is read before dispatch.
* **Profile provenance.** E4/CatBoost/MLP are bound to the profile recorded in their model file (audit finding D2, fixed earlier); the learned param model records its coverage sessions; `describe()` of every estimator reports its source.
* **Scheduling cost.** `EftNoContext` switches the decision-context logging off (it walks 256 history intervals per worker per candidate); the study 2 adapter fails a run whose scheduling time exceeds 25% of the makespan (`max_scheduling_fraction`). Measured earlier: 0.017 s of scheduling per 2.7 s run for `PredictedRankGreedy`.
* **GPU dispatch.** The coordinator adds `device=cuda` only for workers of kind `cuda`; CUDA variants exist for `img_edges` and `img_features` (and others in `apps/cuda_stages.py`); outputs of CUDA tasks are verified per task against the CPU stage within the tolerances of `scripts/gpu_spike.py`; an all-CPU run must equal the sequential reference byte for byte.
* **Remote shim.** `core/worker_pool.py` (`RemoteSlot`, `set_link`) and `remote/link.py` implement a socket worker with an injected delay/bandwidth model; on this machine it is a loopback emulation (docs/REMOTE_DEVICES.md), never real remote hardware.
* **Known historical defects** (documented in the protocols, fixed in code): mismatched E4 base profile (D2), eligibility inconsistencies (D3), decision-time context capture (D4/AD-7), logging cost of decision contexts (A5), worker-pool rebuild between conditions (A1).

## 6. Evidence statement carried into the revival

Authoritative: `docs/research_redesign/EVALUATION_PROTOCOL_study2.md` (sections 1 to 32; later sections supersede earlier hypotheses), `docs/research_redesign/STUDY2_REPORT.md` (Updates 1 to 4; Update 4 is the two-factor result), `docs/research_redesign/claims.json`. Historical: stage 1 to 5 protocols and reports, the master documentation's pre-Study-2 sections.

Result of the audit: the checkout is consistent, tests and typing are green, stored analyses reproduce. The starting point for the revival is therefore the committed state `ceae094` with a measured negative/neutral last result (two-factor: level with blind greedy).

## 7. Blockers / unverified at audit time

None blocking. Unverified: GPU utilisation telemetry (no NVML), remote hardware (none), the older one-factor experiments (documented only).
