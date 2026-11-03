# CAO project: progress to 2026-10-10

Short status of the work done today. For the full technical findings, see
`D:\cao_records\2026-10-10_cao_technical_audit.md` (kept outside the repository).

## 1. Read-only technical audit: done

- Traced the implementation end to end: DAG creation, readiness, the policies
  (B0–B5, EFT), the estimator ladder (E0–E5), the dataset builder, the remote
  node and proxy, the application pipeline and the dashboard.
- Found that the GPU path is not reachable in a normal run, and that the
  remote and edge code runs only as a simulation on this laptop.
- Confirmed the main defects. The most serious are listed below.
  - **D1:** a CUDA stage applies to every task of its type, so a mixed pool
    aborts.
  - **D2:** the E4 model was served on a different base profile than the one it
    was fitted on.
  - **D3:** the documentation says every policy honours eligibility, but only
    B4 and EFT do.
  - **D4:** the predictor features are taken at task start, not at the decision.
  - **D7:** pool identities (P, E, R) are hard-coded.

## 2. Stage 0: preservation: done

| item | status |
|---|---|
| Backup `D:\cao_backups\cao_project_pre_stage0_20261010` | complete copy, 20,736 files, re-verified file by file against recorded SHA-256 |
| Git baseline `c23a96e` | "Baseline: CAO project state before Stage 0 fixes" |
| Manifest commit `7651eca` | data manifest (12,627 files under `data/`) and exclusion record |
| Large data kept out of Git | `data/artifacts`, `data/events`, `data/datasets`, `data/dashboard_runs`, and 7 result files over 1 MB. Covered by the manifest and the backup. |

Limitation: the backup and the data are on one physical disk. No copy exists on
a separate disk yet.

## 3. Stage 1: E4 base-profile fix: in progress

**Root cause (confirmed in code and saved metadata).** `build_estimator` passed
the session profile to `InterferenceRidgeEstimator.load`, and `load` accepted
it without checking. The Phase 5 and 6B runs therefore applied a model fitted
on `20261003T115606_profile.json` to `20261003T152700_profile.json`.

**Changes made (uncommitted):**

- `src/caosched/estimators/learned.py`
  - `save` records `base_profile`. It refuses a base with no source file.
  - `load` without `base` uses the recorded profile.
  - An explicit `base` with different measurements raises
    `BaseProfileMismatchError`. A copy at another path with the same
    measurements is accepted.
  - A model with a missing or invalid `base_profile` is refused.
  - A moved profile file is handled by a documented name check.
- `src/caosched/estimators/__init__.py`
  - `build_estimator` no longer rebases E4 onto the session profile. E0–E3
    still use it.
  - `BaseProfileMismatchError` is exported.
- `tests/test_estimators.py`: 12 new tests on the binding rules, plus one that
  reads the shipped Phase 3 model without writing to `data/`.

**Test results (focused run):** `tests/test_estimators.py`,
`tests/test_e2e.py`, `tests/test_phase4.py` and `tests/test_schedulers.py`:
**56 passed**, 0 failed. The 13 E4 tests in `test_estimators.py` all passed,
none skipped.

**Not done yet:**

- The D2 limitation has not been recorded in `PROJECT_STATUS.md` or
  `ARCHITECTURE.md`.
- The final diff has not been reviewed line by line.
- The fix has not been committed.
- The earlier 6B result (learned predictor +6.8% slower) was produced with the
  mismatched base. It is not invalid, but it should be re-analysed before
  anyone relies on it. This was not done, and it needs a decision.

## 4. Next milestone (proposed, not started)

Replace the hard-coded P/E/R worker assumptions with pool and device
capabilities, and move device eligibility to dispatch time. This is the
foundation for real NVIDIA GPU offloading. It touches `worker_pool.py`,
`estimators/base.py`, `dataset/build.py`, `schedulers/simple.py` and the
dashboard. It should be a separate commit.

## 5. Open risks

- A single physical disk holds the project, the backup and the records.
- No Git remote exists.
- The dependencies are unpinned.
- The GPU and edge paths have never executed.
