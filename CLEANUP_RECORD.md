# Clean-up record (3 November 2026)

At the end of the project the folder `D:\cao project` was reduced to the final version. This file says what was removed, what was kept and why, so that nobody has to guess.

## Removed (about 34 GB)

| What | Size | Why it is not needed |
|---|---|---|
| `data/results/stage1_20261011/` run work folders: `debug_resume1-3`, `rep1-3`, `seq_run1`, `seq_runA-C`, `valid`, `valid_unpinned_killed` | about 22.9 GB | Scratch and output folders of the early Montage runs (stage 1). Their summaries, manifests and logs were kept. |
| `data/results/stage3_20261012/refs/` | about 8.6 GB | Reference outputs for the stage 3 predictor study. Designs, evaluation files and manifests were kept. |
| `data/montage/` | about 1.7 GB | Montage workflow inputs, needed only to run Montage again. |
| `data/datasets/` | about 0.4 GB | Training datasets of the stage 3 predictors. The final model is trained from the final study's own logs. |
| `data/dashboard_runs/` | about 57 MB | Live runs of the earlier dashboard. |
| `publications/` drafts, old zip and test folder | about 0.2 GB | Replaced by `SUBMISSION_FINAL/`. |
| `.mypy_cache`, `__pycache__` folders | small | Rebuilt automatically. |

Effect on the claims: the Montage result (EFT 1.6% slower than static P-only) is still supported by the summaries, manifests and analysis files in `data/results/stage1_*`, `stage2_*`, `stage4_*` and `stage5_*`. The raw run work folders behind it were removed, so a Montage run cannot be re-checked file by file from this folder.

## Kept

* All code: `src/`, `scripts/`, `tests/`, `config/`, `manifests/`, `docs/`. The final code imports the older modules, so none were removed.
* `data/results/final_20261101/` (final benchmark), `study2_20261024/`, `revival_20261025/`, `overnight_20261027/`, `revival_gpu_profile_20261025/`, `demo_20261027/`, `phaseB_appdemo_sweep_20261004/`, `stage2`, `stage4`, `stage5` summaries, and `stage1_20261011/gpu/` (the GPU speed-up record used by the final study).
* `data/events/`, `data/artifacts/`, `data/profiles/`, `data/models/` (tab 2 replay and the saved models), `data/dashboard_runs_v3/`.
* `SUBMISSION_FINAL/` (all deliverables), `publications/figures/` and `publications/_work/` (inputs of the document builders), `.git/` (history), `.venv/`.

## Check after the clean-up

`pytest`: 519 passed, 1 failed, 1 skipped. The failure (`tests/test_profile_montage.py::test_profile_format_csv_fit_and_cleanup`) and the skip are caused by low free RAM (0.4 GB; the test refuses to start below 2 GB), not by the clean-up. The claims, final-region, estimator, workflow and dashboard test files all pass when run alone. Dashboard v3 serves tabs 1 to 6 data, including the tab 2 replay and its image.

Not touched: everything outside `D:\cao project`, including `D:\cao_upload_copy`, `D:\cao_checkpoint_revival` and `D:\cao_project_guide_output`.

Note: the 25 small tracked `run.json` files of the removed stage 1 folders (run configuration of each Montage run) were restored from git, so the record of what each run was set up to do is kept.
