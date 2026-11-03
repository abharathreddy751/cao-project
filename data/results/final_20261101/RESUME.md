# Resume guide for the final study (paused 2026-11-01 for a possible Windows restart)

## State at the pause

* The waiting pipeline (`scripts/final_stage1.ps1`, background task) was stopped through the harness. It had not started any session, so there is **no partial session** and no result to protect: `data/results/final_20261101/calibration/` holds only `designs/` and `designs_sha256.txt` (6 calibration / hold-out designs, created exclusively), and the first malformed launch left stdout files with no session.
* Nothing was overwritten or deleted. Earlier results (4753 run manifests, 164 designs) are untouched; their hashes are in `preservation/`.
* Free RAM when paused: about 0.5 GB (the reason for the pause: `rsEngineSvc` ~5.7 GB, WSL VM ~6 GB private).
* Checkpoint of everything new: `preservation/checkpoint_20261101T120846Z/` = git state (commit `9d8ea22`, branch `revival/resource-state-aware`), status, full tracked diff (`tracked_changes.patch`), SHA-256 of 49 final-study files, and `final_study_code_docs_state.zip` (relative paths, verified). Backups of the originals of the tracked files I edited: `backups/`. Baseline test log: `preservation/pytest_before.stdout.txt`; after phases A to C: `pytest_after_ABC.stdout.txt` (515 passed, 1 pre-existing RAM failure).

## After the restart

1. Check memory: `.\.venv\Scripts\python.exe -c "import psutil;print(psutil.virtual_memory().available/2**30)"`. A session needs about 2.4 GB free at start (pool ~1.4 GB, runner rule 0.8 GB left). Do not start a session below that.
2. Check the code is unchanged since the checkpoint: compare `git diff | Get-FileHash`-style against `preservation/checkpoint_*/tracked_changes.patch`, or re-hash with `final_study_files_sha256.txt`. The runner records `src_sha256` per run; sessions with different hashes are never pooled.
3. Run the baseline tests once: `.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider` (expect 515 passed and the 1 known RAM failure; it needs 2 GB free for that test).
4. Start stage 1 again. It is idempotent: it skips complete sessions, never overwrites an existing model or design, and reruns an aborted design under a new id (`_r2`, ...):

   ```powershell
   Set-Location "D:\cao project"; .\scripts\final_stage1.ps1
   ```

   Stage 1 = calibration + hold-out sessions, `param_model_final.json`, `e2e_terms_final.json`, evaluation designs, oracle rows, a 2-block smoke session of the primary design.
5. After `STAGE1_DONE.txt` appears: freeze the protocol (log the SHA-256 of `docs/final/PROTOCOL_final.md` and `eval/designs_sha256.txt` in `ACTIVITY_LOG.md`), then run the evaluation sessions in this order with `scripts/final_run_sessions.ps1 -Dir data\results\final_20261101\eval -Designs <name>`: `eval_h16_l120`, `eval_uniform`, `eval_h04_l120`, `eval_h40_l120`, `eval_h16_l40`, `eval_h16_l15`.
6. Analyse each complete session: `.\.venv\Scripts\python.exe scripts\final_analyze.py --session <dir> --out data\results\final_20261101\eval\analysis_<workload> [--confirmatory]` (`--confirmatory` only for `eval_h16_l120`). Then `scripts/final_workload_features.py`, the hybrid decision (protocol section 10), `scripts/final_results_table.py`, and the reports.

## Not done yet

Calibration, model training, evaluation sessions, analysis, hybrid check, `CAO_FINAL_EXPERIMENT_REPORT.md`, updated results table and claims file, faculty checklist, contribution statement.
