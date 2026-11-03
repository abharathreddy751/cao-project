# Stage 0 preservation manifest (2026-10-10)

Recorded before any Stage 1 fix. Nothing under `data/` was created, modified,
renamed or deleted by Stage 0.

## Files in this directory

| file | content |
|---|---|
| `data_sha256.tsv` | Every file under `data/` (12,627 files, 2,491,760,971 bytes). Columns: `relpath` (relative to `data/`, `/` separators), `size` (bytes), `mtime_ns` (filesystem modification time, ns since the Unix epoch), `sha256`. SHA-256 of this TSV: `0213f362fc76982eb6fc1d018ad0e5cdc8a80ca941226b7eaab3406ee9993bb7`. |
| `MANIFEST.md` | This description. |

Verify later with any SHA-256 tool, e.g. recompute each `data/<relpath>` and
compare with column 4.

## Baseline

* Git baseline commit: `c23a96e3e8eb1d301dd25a9fb8f750692eecd260` (branch `main`).
  Repository-local `core.autocrlf=false`, so committed blobs are byte-identical
  to the files on disk.
* Full-tree snapshot of the project before the backup (20,736 files,
  2,669,979,346 bytes, incl. `.venv` and caches):
  `D:\cao_records\stage0\S0_original_full_20261010.tsv`
  (SHA-256 `5be9a4466e28e8ff9287860ad94bd0e980d036027eb517bf3f8e567bd470fda3`).
* Backup: `D:\cao_backups\cao_project_pre_stage0_20261010` (robocopy /E,
  timestamps preserved). Its own snapshot
  `D:\cao_records\stage0\S1_backup_full_20261010.tsv` is byte-identical to S0
  (same SHA-256): 20,736/20,736 files, identical size, mtime and SHA-256.
  Limitation: the backup is on the same physical NVMe disk as the project
  (C: and D: are partitions of disk 0), so it does not protect against disk
  failure. An off-disk copy is recommended.
* Audit report: `D:\cao_records\2026-10-10_cao_technical_audit.md`.

## Data: tracked in Git vs kept only on disk

| directory | files | MB | in Git | reason |
|---|---|---|---|---|
| data/artifacts | 9,586 | 1,647.14 | 0 | bulky stage outputs (binary); hashed here + backup |
| data/events | 2,855 | 334.45 | 0 | raw JSONL event logs (primary evidence, bulky); hashed here + backup |
| data/datasets | 8 | 423.45 | 0 | derived dataset builds; hashed here + backup (each build also has its own manifest with source SHA-256) |
| data/dashboard_runs | 71 | 11.83 | 0 | live demo outputs, not experiment records |
| data/results | 76 | 74.15 | 69 | files <= 1 MB tracked; 7 files > 1 MB not tracked (list below) |
| data/models | 5 | 0.02 | 5 | referenced by configs |
| data/profiles | 12 | 0.27 | 12 | referenced by configs (incl. raw profile CSVs) |
| data/traces | 3 | 0.03 | 3 | replayable workload traces |
| data/diagnostics | 8 | 0.41 | 8 | small diagnostic records |
| data/environment | 1 | 0.00 | 0 | ignored by the original `.gitignore` (`data/environment/*.json`) |
| data/benchmarks | 1 | 0.01 | 0 | ignored by the original `.gitignore` (`data/benchmarks/*.csv`) |
| data/reports | 1 | 0.00 | 0 | ignored by the original `.gitignore` (`data/reports/*.json`) |

`data/results` files > 1 MB, not in Git (all in `data_sha256.tsv` and the backup):

* `phase3_20261003T144523_predictions.csv` (16.7 MB)
* `phase4_20261003T145958_decisions.csv` (3.2 MB)
* `phase4_20261003T145958_decisions_20261003T150427.csv` (3.2 MB)
* `phase6b_20261003T162145_decisions_complete101.csv` (15.3 MB)
* `phase6b_20261003T162145_decisions_full33_a.csv` (15.0 MB)
* `phase6b_20261003T162145_decisions_full33_b.csv` (15.0 MB)
* `phaseB_appdemo_sweep_20261004/evidence_sha256_before_analysis.json` (1.8 MB)

## Non-data paths not in Git

Ignored by the original `.gitignore` and left unchanged: `.venv/` (7,899 files,
168 MB; cannot be recreated without installing packages, so it is preserved in
the backup), `.pytest_cache/`, all `__pycache__/`, `src/caosched.egg-info/`.

The untracked data paths above are listed in the repository-local
`.git/info/exclude` (not versioned) so that `git add .` cannot add them by
accident. The original `.gitignore` was not modified.
