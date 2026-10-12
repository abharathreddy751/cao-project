# Research status

Date: 2026-10-12. State: **Stage 1 complete (gates passed, see below); Stages 2-4 code written, reviewed and tested; Stage 2-4 experiments not yet run.** Older sections below are history (2026-10-11) unless marked.

## Verified current state

| Item | Verified how | Result |
|---|---|---|
| Git | `git status`, `git log` | Branch `main`, HEAD `7651eca` ("Stage 0: SHA-256 manifest..."); previous commit `c23a96e` |
| Uncommitted work | `git status` | Modified: `src/caosched/estimators/__init__.py`, `src/caosched/estimators/learned.py`, `tests/test_estimators.py`. Untracked: `PROGRESS.md`. This task did not stage or change them |
| E4 profile-mismatch fix | `PROGRESS.md`; earlier diff review | Implemented, reported as 56 focused tests passing on the earlier machine, **not committed**, tests not re-run here |
| Machine | PowerShell queries, 2026-10-11 | i5-13500HX, 15.7 GB RAM, NVIDIA RTX 3050 6 GB Laptop GPU, driver 581.83 |
| Historical machine | `data/environment/env_20261002T223753.json` | i5-1235U, 8.25 GB, 2P+8E, Intel UHD. All recorded experiments come from it |
| Toolchain on this machine | PowerShell | No WSL; no `nvcc`, `gcc` or `gfortran` on PATH; `python` is the Windows Store stub; `.venv` points to a deleted `C:\Program Files\Python311` |
| Audit report | `Test-Path` | `D:\cao_records` and `D:\cao_backups` do not exist on this machine; the audit text was not available |
| Survey workbook | file search | `C:\Users\Venkatesh\Downloads\AI_Heterogeneous_Computing_Literature_Survey.xlsx` found and read (12 papers, patent, platforms). `Copy of literature survey.xlsx` in the same folder is a different survey (medical-image models on edge devices) and was not used |

## Completed work and evidence (earlier machine)

Phases 0–6B, the dataset (rebuilt 145,378 task rows), the 68-task image pipeline, the dashboard and the Stage 0 backup/manifest are documented in `PROJECT_STATUS.md`, `PROGRESS.md` and `manifests/stage0_20261010/`. They are historical, machine-specific evidence and are not modified.

## Findings reused from the earlier audit

D1 CUDA flag applies to every task of a stage type; D2 E4 base-profile mismatch (fix uncommitted); D3 eligibility honoured by B4/EFT only; D4 features not decision-time safe (46,229 early-binding rows); D7 hard-coded P/E/R. These come from `PROGRESS.md` and the 2026-10-11 code read, not from the missing audit file.

## New this session (documentation research only)

- Base-patent claims read as a paraphrase: no machine learning, prediction, offloading or named hardware in the claims (see PROJECT_SPEC section 7).
- Literature positioning checked against primary sources where accessible (PROJECT_SPEC section 6).
- Montage workflow, toolkit, WfCommons, WfInstances and Rodinia pages inspected; no GPU path found in Montage (WORKLOAD_AND_DATA_PROVENANCE).
- Owner decision: **this machine first, Raspberry Pi 5 later.**

## Unverified claims (do not rely on them)

- Verbatim patent claim wording; patent legal status beyond the catalogue entry.
- HEFT, CPOP and PEFT original assumptions and complexity; TabM and CatBoost venue details beyond arXiv.
- Song et al. 2023, Wang et al. 2022, DDDQN-TS, Gong 2023, Nieto 2024, Liu 2024/2025 beyond abstracts; the IEEE versions of LACHESIS and Cao 2024; the journal version of SATA-DRL.
- Montage input data size, source host, build on Windows, generator version requirements, task count the generator really produces.
- Whether the earlier P/E speed ratios hold on the i5-13500HX; the 13500HX core layout.
- WfCommons Montage recipe, WfBench GPU support, Rodinia build on this machine.
- That an RTX 3050 gives a worthwhile speed-up for any stage after host-device copies.
- Workbook statements: "26.7% makespan reduction over seven baselines" (source says "at most", versus the second-best method, in large batch mode), and the Project_Summary's ML-recommends-a-resource idea as part of the patent (not in the claims).

## Decisions still requiring approval

1. Primary contribution: the prediction-sophistication study; exclusion of GNN+PPO, GRU/TCN, temporal Transformer and GNN predictors from the minimum project.
2. How Montage runs here: WSL2, Cygwin/MSYS2, container or native build (contradicts the earlier "no WSL/Docker" rule).
3. GPU design: Montage CPU workflow plus a separate CPU/GPU DAG (default: image-pipeline stages with PyTorch-CUDA variants); installing CUDA-enabled PyTorch.
4. Treat all i5-1235U data as historical and machine-specific.
5. Provide or locate: patent PDF, paywalled papers, `D:\cao_records` audit, `D:\cao_backups`.
6. Commit the E4 fix (separate commit) before Stage 1 starts.
7. Patent: we make no freedom-to-operate claim; seek advice if the work is to be commercialised.
8. Confirm that the Raspberry Pi 5 remains a post-completion extension.

## Execution-start log (2026-10-11, same day)

| Item | Result |
|---|---|
| Write access | At first the project tree was admin-only (only `docs/` writable); `src`, `tests`, `data`, `.git`, `.venv` could not be written. The owner changed the ACL; re-probe shows `src`, `tests`, `data\results`, `.git`, `.venv` writable [real] |
| Branch | `redesign/montage` created from `main` (HEAD `7651eca`); no commits on it yet; uncommitted E4 files carried over unchanged |
| E4 diff review | `git diff src/` read line by line: `learned.py` (record `base_profile` on save, refuse model without usable profile, `BaseProfileMismatchError` on differing measurements, moved-file name check) and `__init__.py` (E4 no longer rebased onto session profile). No defect found by reading. Tests **not yet re-run** (no Python on this machine) |
| Python 3.11 | `winget install Python.Python.3.11 --scope user` started 14:17; the installer log ends at "Launching elevated engine process", i.e. it waits for a UAC/elevation prompt. Not installed. Needs the owner to approve the prompt, or an alternative route |
| Owner instruction | Documentation-only redesign is completed and reviewed **before** any implementation stage starts. No stage has started. E4 commit waits for a working Python to run the four focused test files |

## Stage 1 report (2026-10-12) - PASS

| Gate | Result | Evidence |
|---|---|---|
| 3 of 3 runs complete | PASS: 3 sequential runs, 59 tasks each, status ok, 1459.4 / 1467.1 / 1469.3 s (pinned to P-core LP 2) | `data/results/stage1_20261011/valid/seq{1,2,3}/run.json` |
| Outputs equal | PASS: `1-mosaic.fits`, `1-mosaic_area.fits`, `1-mosaic.png` byte-identical in all 3 runs; FITS max abs difference 0.0 | `valid/stage1_gate.json` |
| WCS sanity | PASS: NAXIS 3960x3960, CRVAL/CDELT/CRPIX/CTYPE equal the requested header, finite fraction 0.9666 | same |
| DAG extracted with no manual edits | PASS: 59 jobs, 147 edges from `jobDependencies` = 147 from file relations, 0 disagreements | same |
| Per-task times for every task | PASS (all 59 timed in each run); mProject median 160.6 s, other tasks 0.1-4.2 s | same |
| GPU pair equivalent with speed-up > 1 (copies included) | PASS for `img_edges` and `img_features` from 512 px (bit-exact, 3.05-13.96x at 512-2048 px on the idle re-run); `img_denoise` bit-exact at every radius tested (0.7, 1.3, 2.0, 2.5, 4.0) but speed-up only 1.03-1.09x at 1024-2048 px and below 1 at 512 px, so it is not used as GPU evidence below 1024 px / iterations 1 and is marginal above | `gpu/spike_20261012T092018/gpu_spike.json` (rerun with the committed script, tolerances fixed in the script, script sha256 recorded) ; first run `gpu/gpu_spike.json` kept as history |
| Docs consistent, reviewed | Provenance, spec, build, literature docs updated; literature gaps listed (patent verbatim claims, HEFT/PEFT originals not reachable) | `LITERATURE_UPDATE.md`, `MONTAGE_WINDOWS_BUILD.md` |

Route used: native Windows build (route 1), no WSL/container/admin. Deviations and failures (kept, excluded): first run with the wrong mDiffFit variant; runs A-C and rep1-3 (PATH, then runner misreading a tolerated message; rep1-3 partly concurrent); an unpinned set killed after mProject ran ~2x slower; debug resume runs `debug_resume1..3` (label debug, found mImgtbl option-order and mViewer stack bugs, patched). The machine was not idle during timing (WSL VM, browser, editor; power plan Balanced). Timings in these runs are indicative; the E1 profile is measured separately.

Quality gates for code (2026-10-12): full suite 364 passed, 1 skipped, then 366 passed, 1 skipped after the mypy pass; mypy on `src/caosched`: 0 errors (6 targeted `# type: ignore[code]` with reasons, see the subagent report in this session); `data/results/stage1_20261011/tests/`.

Not claimed by Stage 1: any scheduling result, any model result, any speed-up of Montage on GPU (none exists).

## Documents in this redesign

[PROJECT_SPEC.md](PROJECT_SPEC.md) · [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) · [FOUR_STAGE_IMPLEMENTATION_PLAN.md](FOUR_STAGE_IMPLEMENTATION_PLAN.md) · [WORKLOAD_AND_DATA_PROVENANCE.md](WORKLOAD_AND_DATA_PROVENANCE.md) · [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md)

Older documents (`PROJECT_STATUS.md`, `docs/PROJECT_BRIEF.md`, `docs/B4_PATENT_MAPPING.md`, `docs/REMOTE_DEVICES.md`) are historical and unchanged. Where they describe the i5-1235U, P/E core numbers, the 68-task pipeline as the application target, or "claims not retrieved" for the patent, this redesign supersedes them once approved.

## Next action

Review and answer the decisions above. After approval, start Stage 1 step 1–2: environment re-baseline and the Montage environment choice. Do not start implementation before that.
