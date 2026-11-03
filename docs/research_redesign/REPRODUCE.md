# Reproduction instructions (Stage 4)

Status: **written 2026-10-11 before any of these commands was re-run for this document.** Every command carries a marker. `[not yet run]` means the author of this file has not seen it succeed; the commands were read from the scripts' own usage text and argument parsers, not executed. Nothing below is a result. Replace markers only with the outcome recorded in `repro_log.json` (section 12), never from memory.

**Update 2026-10-14:** sections 14 and 15 were added after the confirmatory sessions (stage 5). Section 14 lists the stage-5 commands, reconstructed from the scripts' own usage text and argument parsers and from the session metadata (the exact chain script that ran the sessions is not stored in the repository); section 15 lists the logs that were actually observed, with their paths. Sections 1 to 13 are unchanged and keep their original markers.

Paths: `<REPO>` is the repository root, `<DATA>` is `<REPO>/data`. Commands are shown for a Windows shell with the repository venv active; use `python` from that venv. Scripts that take no path arguments (`montage_prepare.py`, `montage_sequential.py`, `stage1_report.py`, `gpu_spike.py` default) resolve `data/` relative to their own location, so they must be run from a full checkout that has `data/montage/`.

## 0. What can and cannot be reproduced from git alone

| Item | From git alone? | Why |
|---|---|---|
| Source, tests, scripts, documents, `requirements-lock.txt` | yes, once **committed** | A clone contains committed files only. When this file was written, `git status` listed `scripts/run_experiment.py`, `scripts/analyze_experiment.py`, `src/caosched/experiment/`, `docs/research_redesign/`, `requirements-lock.txt` and others as untracked, so a clone of the branch tip would lack them. Commit them first; the clean-checkout script checks this (`required_files_present`). |
| Unit tests, stub-adapter experiment, analysis, manifests (section 10) | yes, after commit | Pure Python, synthetic data, no `data/`. |
| Montage executables, `w64devkit`, instance inputs, raw results, `work/` directories, experiment sessions | **no** | `.gitignore` excludes `data/montage/`, `data/results/stage*/**/work/` and `data/experiments/`. They are recorded by SHA-256 manifests instead. |
| Montage input images | **re-downloadable**, not stored in git | URL, size and SHA-256 of every input are in `data/montage/instances/<name>/instance.json` (written by `montage_prepare.py`). The archive host must still serve identical files; this was not checked. |
| Montage executables | **rebuildable**, not byte-identical by assumption | Sources, versions and workarounds: [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md). Compare a rebuild to `montage_build/bin_win64_sha256.txt`; a different compiler build may change bytes (not tested). |
| GPU and CPU timing numbers, makespans, profiles, speed-ups | **no** | Machine-specific (this laptop: P/E cores, RTX 3050, driver 581.83). A rerun gives new numbers. Never pool runs from different machines or environment hashes; the analysis refuses to. |

## 1. Environment

Required: Python 3.11 (the venv used so far is 3.11.9; `pyproject.toml` says `>=3.11`), Git, network access for pip, and for the GPU part an NVIDIA driver (581.83 tested) with a CUDA 12.8 torch wheel.

1. Create the venv. `[not yet run]`
   ```
   python -m venv .venv
   ```
2. Install the pinned packages. `requirements-lock.txt` pins `torch==2.11.0+cu128`, which is **not on PyPI**; install everything else first, then torch from the cu128 index. `[not yet run]`
   ```
   .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
   ```
   fails on the torch line unless the index is given, so for a CPU-only environment drop that line from a copy of the lock file (the clean-checkout script does exactly this and writes `requirements-cpu.txt`):
   ```
   .venv\Scripts\python.exe -m pip install -r requirements-cpu.txt
   ```
   GPU (only for section 6): `[not yet run]`
   ```
   .venv\Scripts\python.exe -m pip install torch==2.11.0+cu128 --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple
   ```
3. Install the package itself, editable (the lock file records it as an editable install, not as a pin). `[not yet run]`
   ```
   .venv\Scripts\python.exe -m pip install --no-deps -e .
   ```
4. Record the environment of every real session: the runner writes `environment.json` (machine id, environment hash, packages, git commit and dirty flag, `src_sha256`) into each session directory automatically (section 8).

## 2. Montage toolchain build (summary)

Full detail, versions, licences and every workaround: [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md). Helper sources and patch scripts: `docs/research_redesign/montage_build/` (`gccshim.c`, `compat.h`, `patch_svc.py`, `patch_archivelist.py`, `montage-workflow-windows.diff`, `bin_win64_sha256.txt`). There is **no single script that rebuilds Montage**; the build was done by hand module by module. `[not yet run]` (no step of the build has been repeated for this document)

Pinned inputs, as recorded in the build document:

- Montage `https://github.com/Caltech-IPAC/Montage`, commit `ac0a15334f670ed83e328b6c5768f94b4b847359`.
- Workflow generator `https://github.com/pegasus-isi/montage-workflow-v3`, commit `975047e916d3d049d9ff0da17e7fe5aaac979c64`.
- Toolchain `w64devkit-x64-2.10.0.7z.exe` from `https://github.com/skeeto/w64devkit/releases/tag/v2.10.0`, SHA-256 `18d0a4c71a166f8401ab6305781bec5882b40b5e06ba9807c61cb5f3b3c6325e` (verify before unpacking); GCC 16.2.0, GNU Make 4.4.1.
- Build in a directory **without spaces** outside the project (the Makefiles require it); then copy the executables to `data/montage/bin_win64/`.
- The generator used by the pipeline is `data/montage/montage-workflow-windows.py` (upstream script plus three Windows edits, diff in `montage_build/montage-workflow-windows.diff`).
- `bin_win64/mDiffFit.exe` must be the `grid/Pegasus` variant (the MontageLib variant made sequential run 1 fail; see the build document).

Check an existing or rebuilt `bin_win64` against the recorded hashes (PowerShell, read-only). `[not yet run]`
```
Get-Content docs\research_redesign\montage_build\bin_win64_sha256.txt | ForEach-Object { $h,$n = $_ -split ' \*'; if ((Get-FileHash "data\montage\bin_win64\$n" -Algorithm SHA256).Hash -ne $h.ToUpper()) { "MISMATCH $n" } }
```
The clean-checkout script does the same comparison with `--montage-subset` (section 10).

## 3. Generate and download one instance

`scripts/montage_prepare.py` runs the Windows-patched generator with `data/montage/bin_win64` on `PATH`, downloads every raw input from the URLs in the generated replica catalog and records URL, size and SHA-256 in `instance.json`. It refuses to reuse a name (creates `data/montage/instances/<name>/` exclusively). Needs network and `data/montage/` from section 2. `[not yet run]`
```
python scripts/montage_prepare.py --name d1.1_dss2b_c56.7_24.0 --center "56.7 24.0" --degrees 1.1 --band dss:DSS2B:blue
```
The instance name above is the one referenced by the Stage 1 evidence; the exact arguments used originally are recorded in that instance's `instance.json` and `generator_stdout.txt`, which are the authority if they differ from this line.

## 4. Sequential reference runs

`scripts/montage_sequential.py` runs the jobs of one instance one at a time in a fresh `work/` directory, records per-task wall time, exit status, sizes and SHA-256, and writes `run.json`. Stage 1 requires 3 completed runs; the machine must be otherwise idle (section 11). `--out` must not exist. `[not yet run]`
```
python scripts/memory_preflight.py --min-free-gb 3
python scripts/montage_sequential.py --instance d1.1_dss2b_c56.7_24.0 --out data/results/stage1_<STAMP>/seq_runA
python scripts/montage_sequential.py --instance d1.1_dss2b_c56.7_24.0 --out data/results/stage1_<STAMP>/seq_runB
python scripts/montage_sequential.py --instance d1.1_dss2b_c56.7_24.0 --out data/results/stage1_<STAMP>/seq_runC
```
Exit code 1 means a task failed (`status` in `run.json` names it). A failed run is kept as evidence and excluded from the gates (as `seq_run1` was); do not delete it.

## 5. Stage 1 gate report

Compares the three mosaics (hashes, NaN pattern, max difference), checks the WCS header against `region.hdr`, compares the extracted DAG with the generator's own `jobDependencies`, and summarises per-transformation times. Writes `stage1_gate.json` **exclusively** into the evidence directory (fails if it exists). `[not yet run]`
```
python scripts/stage1_report.py --evidence data/results/stage1_<STAMP> --instance d1.1_dss2b_c56.7_24.0 seq_runA seq_runB seq_runC
```
Gate (FOUR_STAGE_IMPLEMENTATION_PLAN, Stage 1): 3 of 3 runs complete, outputs equal within the pre-stated tolerance, DAG extracted without manual edits, per-task times for every task. The report prints the facts; whether the gate is met is a reading of `stage1_gate.json`, not an output of the script.

## 6. GPU spike

CPU reference versus PyTorch-CUDA for three image-pipeline stages, with tolerances fixed in the script before the recorded run. Needs the CUDA torch of section 1 and an otherwise idle GPU and CPU. Output goes to a new timestamped directory under `--out` (default `data/results/stage1_20261011/gpu`; pass your own `--out` to avoid mixing with existing evidence). `[not yet run]`
```
python scripts/gpu_spike.py --reps 15 --out data/results/stage1_<STAMP>/gpu
```
A stage counts as GPU evidence only if it is numerically equivalent within the stated tolerance **and** the speed-up including host-device copies is above 1; otherwise the script's verdict is `DROPPED`.

## 7. Profiling the Montage tasks

Solo kernel times per transformation and pool, from a completed sequential run (reads its `work/`, does not modify it). `--out` must not exist; stops if free RAM falls below `--min-free-ram-gb`. `[not yet run]`
```
python scripts/profile_montage.py --run-dir data/results/stage1_<STAMP>/seq_runB --out data/profiles/montage_<STAMP> --reps 2 --mproject-max 2 --min-free-ram-gb 2
```
Optional: `scripts/run_workflow.py` runs one generated workflow under one policy and compares the final outputs with a reference-hash JSON (use it for the Stage 2 correctness check); see its docstring. `[not yet run]`

## 8. Run an experiment session

Prerequisites: a design file written and frozen **before** the run (fields in `src/caosched/experiment/design.py`: `name`, `evidence_label`, `seed`, `n_blocks`, `warmup_blocks`, `instances`, `min_free_ram_gb`, `reference`, `conditions`, optional `run_timeout_s`), the instances of section 3, a reference-hash file from the Stage 1 runs, and (for learned estimators) the profile and model files. The adapter reads its constructor settings from a JSON file named by the environment variable `CAO_MONTAGE_ADAPTER_CONFIG` (optional keys `montage_root`, `bin_dir`, `executables`, `timeout_s`, `run_timeout_s`; defaults: `data/montage` and its `bin_win64`). Per-condition settings (`profile`, `model_path`, `est_cfg`, `policy_cfg`, `reference_hashes`, `reference_dir`, `fits_atol`, `eligible_pools`, `final_outputs`, ...) go into the `kwargs` of each condition in the design file; see the module docstring of `src/caosched/experiment/montage_adapter.py`. `[not yet run]`
```
$env:CAO_MONTAGE_ADAPTER_CONFIG = "<path to adapter_config.json>"
python scripts/memory_preflight.py --min-free-gb 3
python scripts/run_experiment.py --design <design.json> --out data/experiments --adapter caosched.experiment.montage_adapter:factory --session-id <SESSION_ID>
```
Exit codes: 0 session complete, 2 session aborted (for example the memory preflight failed; `session.json` says why). A crash leaves `session.json` with status `crashed` and the analysis excludes that session. Nothing is overwritten: the session directory is created exclusively and failed or unverified runs are kept and flagged.

Dry run of the whole path with the synthetic adapter (label `plan`, never evidence): `[not yet run]`
```
python scripts/run_experiment.py --design <design.json> --out <tmp dir> --adapter stub
```

## 9. Analysis, manifests, reproduction from raw logs

Analysis from the raw session logs; pooling sessions with different machine id, environment hash, evidence label, design hash or code version is refused (`--allow-mixed-code` is recorded if used). `--reference` defaults to the design's. `[not yet run]`
```
python scripts/analyze_experiment.py --sessions data/experiments/<S1> [data/experiments/<S2> ...] --out analysis/<NAME> --reference B4 --seed 0
```
SHA-256 manifest of each evidence directory (refuses to overwrite one without `--force`; do not use `--force` on evidence), then verification (exit 1 on any changed, missing or extra file). `[not yet run]`
```
python scripts/make_manifest.py data/experiments/<S1>
python scripts/make_manifest.py data/experiments/<S1> --verify
```
Re-derive the reported tables from raw logs and re-check every hash; exit 0 only if everything matches, a missing manifest counts as a failed check. `[not yet run]`
```
python scripts/reproduce_subset.py --analysis-dir analysis/<NAME> --log analysis/<NAME>_reproduction_log.json
```

## 10. Clean-checkout test

`scripts/reproduce_clean_checkout.py` clones the branch from this checkout into a new empty directory, builds a fresh venv from `requirements-lock.txt` (CPU-only unless `--with-gpu`), runs a small pytest subset, runs the stub-adapter experiment end to end (design, run, analysis, manifest, verify, `reproduce_subset.py`), and writes `repro_log.json` (steps, exit codes, durations, python version, clone commit, `limits`) into the destination with exclusive create. Standard library only; no shell; per-step timeouts; any failed or skipped step makes the exit code 1. The script itself was only syntax-checked (`py_compile`) and its helpers are unit-tested in `tests/test_reproduce_clean_checkout.py`; the end-to-end run is `[not yet run]`.

Run it when the machine is idle (it installs packages and runs tests) and **after committing** everything the stub pipeline needs. `[not yet run]`
```
python scripts/reproduce_clean_checkout.py --dest <NEW EMPTY DIR OUTSIDE THE REPO>
```
Options: `--tests <paths...>` (default `tests/test_task.py tests/test_stats.py tests/test_experiment_design.py tests/test_analysis_paired.py`), `--with-gpu`, `--timeout-s`, `--install-timeout-s`, `--branch` (default `redesign/montage`), `--source`.

Optional read-only hash check of the original, git-ignored data (never copies or writes it; it hashes the binaries listed in `montage_build/bin_win64_sha256.txt` and, for each `--instance`, the workflow file and every raw input against `instance.json`). `[not yet run]`
```
python scripts/reproduce_clean_checkout.py --dest <NEW EMPTY DIR> --montage-subset --data-dir <REPO>\data --instance d1.1_dss2b_c56.7_24.0
```
The clean checkout **cannot** rerun Montage or reproduce any timing: `data/` is not in git. The log says so in `limits`.

## 11. Machine hygiene rules for any timing run

From EVALUATION_PROTOCOL section 8 and the Stage 4 risks in FOUR_STAGE_IMPLEMENTATION_PLAN:

1. Idle machine: close other heavy applications, no builds, installs, downloads or tests while a timed session runs. Run `scripts/memory_preflight.py` first; the runner repeats the preflight before every block and aborts the session cleanly below `min_free_ram_gb` (an earlier session was interrupted at 0.79 GiB free).
2. Interleaved, seeded blocks: each block runs every condition once in random order. Do not compare conditions run in different sessions or configurations unless interleaved (session drift was observed before).
3. Rules written before the run: design file, warm-up rule (`warmup_blocks`), exclusion rule, repeat counts. Failed, timed-out or unverified runs stay in the raw data, flagged; report incomplete designs as incomplete instead of pooling.
4. No pooling across machines or environment hashes. A hardware change mid-study starts a new study.
5. Raw logs are immutable: every directory and file is created exclusively and event logs are made read-only; never `--force` a manifest of evidence.
6. Every reported number must trace to an evidence file; label every result `real`, `replay`, `emulation`, `simulation` or `plan`.

## 12. Observed reproduction log

Observed 2026-10-12 22:19-22:21 UTC (`data/results/stage4_repro/repro_clean_checkout_log.json`, copy of the log written by `scripts/reproduce_clean_checkout.py`): clone of branch `redesign/montage` at its tip into a new directory, fresh Python 3.11.9 venv from `requirements-lock.txt` (torch lines dropped, no CUDA), `pytest` on 4 test files, stub-adapter experiment, analysis, SHA-256 manifest build and verify and `reproduce_subset.py`, and a read-only hash check of the Montage binaries and the primary instance: all 18 steps exit 0 (about 2 minutes). Limits (as recorded in the log): data/ is not in Git, so Montage and its timings are not re-run; the stub adapter is synthetic (label plan); only a 4-file pytest subset ran; CUDA tests and the GPU spike are not covered.

Fill this section only from the `repro_log.json` written by `scripts/reproduce_clean_checkout.py`: clone commit, Python version, one line per step (name, exit code, duration), overall `ok`, and the `limits` list. Until that file exists nothing here is observed. Attach the log file path and its SHA-256 (`python scripts/make_manifest.py` on its directory, or `Get-FileHash`).

## 13. Open items (not verified when this was written)

- None of the commands above was executed for this document; markers `[not yet run]` stay until a log shows them succeeding.
- Whether the commit that will be cloned contains every file the stub pipeline imports (including `tests/_exp_helpers.py`, used by `tests/test_experiment_design.py`) is checked at run time only.
- The cu128 index install of `torch==2.11.0+cu128` together with `--extra-index-url https://pypi.org/simple` was not tried; if pip resolves a different torch, the `pip_freeze` log shows it.
- Re-downloaded Montage inputs equal the recorded hashes only if the archive still serves the same files; not checked.
- Rebuilt Montage executables are not claimed to be byte-identical to the recorded hashes.

## 14. Stage 5 (confirmatory sessions): commands

`S5` = `data/results/stage5_20261013`. Prerequisites and hygiene as in sections 1 to 11. The sessions ran on 2026-10-13 (the remote session ended 23:39 UTC); the commands below are what the scripts accept, in the order in which the evidence was produced. Markers: `[observed]` means the output named in section 15 exists; `[reconstructed]` means the invocation is derived from the usage text and the session metadata, not from a stored command log. Nothing was re-run for this document.

**14.1 Designs (written and committed before the first block; exclusive create; the SHA-256 goes into every run manifest).** `[reconstructed]` Output hashes: main `9228d7ac...4648`, scarce-P `7dac58e3...5126`, GPU `273a155d...8af7`, remote `4dab0106...3d49` (EVALUATION_PROTOCOL 13, 14).
```
python scripts/make_stage5_designs.py data/results/stage5_20261013/designs data/results/stage1_20261011/gpu/spike_20261012T092018 data/results/stage4_20261012/gpu/profile_t1024/20261013T025309_profile.json
python scripts/profile_gpu_workload.py --out data/results/stage5_20261013/remote/profile_t512 --tile 512 --n-images 16 --no-gpu
python scripts/calibrate_link.py --base-profile data/results/stage5_20261013/remote/profile_t512/<STAMP>_profile.json --out data/results/stage5_20261013/remote/remote_profile.json --tile 512
python scripts/make_remote_design.py data/results/stage5_20261013/designs/remote data/results/stage5_20261013/remote/remote_profile.json 12
```
Adapter settings: `designs/adapter_config_main.json`, `adapter_config_regimeR.json`, `gpu/adapter_config_gpu.json`, `remote/adapter_config_remote.json` (timeouts; `max_p_slots` 2 for remote). The link calibration (`remote_profile.json`, `remote_profile_raw.csv`) is label emulation: a loopback socket with the shim at zero.

**14.2 Background-load monitor (start it before the first session, leave it running through all of them).** `[reconstructed]`; output `[observed]`: `S5/load/load_20261013T121952.jsonl`.
```
python scripts/load_monitor.py data/results/stage5_20261013/load/load_<STAMP>.jsonl --interval 30
```

**14.3 Run chain.** Run the sessions one after another on an otherwise idle machine (memory preflight, section 11). `[reconstructed]`; outputs `[observed]`: the session directories and `S5/{gpu,main,regimeR,remote}.stdout.txt`, `S5/progress.txt`. Session ids default to the local timestamp (the directory names).
```
$env:CAO_GPU_ADAPTER_CONFIG = "data\results\stage5_20261013\designs\gpu\adapter_config_gpu.json"
python scripts/run_experiment.py --design data/results/stage5_20261013/designs/gpu/design_gpu_confirm.json --out data/results/stage5_20261013/gpu_sessions --adapter caosched.experiment.gpu_adapter:factory
$env:CAO_MONTAGE_ADAPTER_CONFIG = "data\results\stage5_20261013\designs\adapter_config_main.json"
python scripts/run_experiment.py --design data/results/stage5_20261013/designs/design_main_confirm.json --out data/results/stage5_20261013/sessions_main --adapter caosched.experiment.montage_adapter:factory
$env:CAO_MONTAGE_ADAPTER_CONFIG = "data\results\stage5_20261013\designs\adapter_config_regimeR.json"
python scripts/run_experiment.py --design data/results/stage5_20261013/designs/design_regimeR_confirm.json --out data/results/stage5_20261013/sessions_regimeR --adapter caosched.experiment.montage_adapter:factory
$env:CAO_REMOTE_ADAPTER_CONFIG = "data\results\stage5_20261013\designs\remote\adapter_config_remote.json"
python scripts/run_experiment.py --design data/results/stage5_20261013/designs/remote/design_remote.json --out data/results/stage5_20261013/remote_sessions --adapter caosched.experiment.remote_adapter:factory --session-id remote_confirm
```
The gate files (`gate_sessions_main.json`, `gate_sessions_regimeR.json`, `gate_gpu_sessions.json`, `gate_remote.json`) hold per run: `completed`, `output_verified`, `dependency_violations`, `worker_overlaps`, `ineligible_placements`, `makespan_s`, `tasks_per_pool`; they are produced from the raw event logs by `python scripts/stage2_gate.py <session_dir> <out.json>` `[reconstructed: the usage text of that script matches the file layout; the invocation is not stored]`. The script's output carries the label `real`, so `gate_remote.json` says `real` while the session metadata and the analysis say `emulation`.

**14.4 Analyses** (reference as in the design; seed 0; 10,000 bootstrap resamples). `[reconstructed]` from `analysis.json` (`paths`, `reference`); outputs `[observed]`.
```
python scripts/analyze_experiment.py --sessions data/results/stage5_20261013/sessions_main/<ID> --out data/results/stage5_20261013/analysis_main --reference B0_P_only --seed 0
python scripts/analyze_experiment.py --sessions data/results/stage5_20261013/sessions_regimeR/<ID> --out data/results/stage5_20261013/analysis_regimeR --reference B4_greedy_eligible --seed 0
python scripts/analyze_experiment.py --sessions data/results/stage5_20261013/gpu_sessions/<ID> --out data/results/stage5_20261013/analysis_gpu --reference EFT_E1_cpu --seed 0
python scripts/analyze_experiment.py --sessions data/results/stage5_20261013/remote_sessions/remote_confirm --out data/results/stage5_20261013/analysis_remote --reference EFT_E1_no_remote --seed 0
```
Second-reference analyses (exploratory, made after the first analyses; no figures were written for them, so `--no-figures` was presumably used):
```
python scripts/analyze_experiment.py --sessions <gpu session> --out data/results/stage5_20261013/analysis_gpu_vs_P --reference B0_P_only --seed 0 --no-figures
python scripts/analyze_experiment.py --sessions <remote session> --out data/results/stage5_20261013/analysis_remote_vs_B4 --reference B4_no_remote --seed 0 --no-figures
```
**Post-hoc sensitivity option** (declared post-hoc, never a pre-registered rule; the dropped runs and the reason are written to `exclusions.csv`; 7 blocks cannot be Holm-significant):
```
python scripts/analyze_experiment.py --sessions data/results/stage5_20261013/sessions_main/<ID> --out data/results/stage5_20261013/analysis_main_posthoc_excl_blocks_5_6 --reference B0_P_only --seed 0 --no-figures --posthoc-exclude-blocks 5 6
```
Relate slow runs to the load log (prints runs above a factor of their condition's median with the load samples in their time window): `python scripts/load_vs_runs.py <session_dir> data/results/stage5_20261013/load/load_20261013T121952.jsonl --factor 1.2` `[reconstructed; its output was not stored]`.

**14.5 Per-session manifests and reproduction from raw logs.** `[reconstructed]`; outputs `[observed]` in `data/results/stage5_repro/`.
```
python scripts/make_manifest.py data/results/stage5_20261013/sessions_main/<ID>
python scripts/make_manifest.py data/results/stage5_20261013/sessions_main/<ID> --verify
python scripts/reproduce_subset.py --analysis-dir data/results/stage5_20261013/analysis_main --log data/results/stage5_repro/repro_analysis_main.json
```
(same pattern for `analysis_regimeR`, `analysis_gpu`, `analysis_remote`). The stage-level manifest of `S5` (analyses, load log, designs, figures, extra analyses) was written at the end: `data/results/stage5_20261013/SHA256_MANIFEST.tsv`.

**14.6 Offline analyses, figures, tests.** Drift, learning curve and regret use the exact commands recorded in `S5/analysis_extra/commands.txt` `[observed]` (frozen config `stage3_20261012/eval_cfg/cfg_final_test.json`, sha256 `ae2802ee...3843`; the time-split config differs only in `"split": {"policy": "time", "train_fraction": 0.7}`).
```
python scripts/make_diagrams.py --out data/results/stage5_20261013/figures --analysis
python -m pytest -q
```
`make_diagrams.py` writes the three diagrams and re-draws the pilot analysis figures into `figures/analysis_main`, `analysis_regimeR`, `gpu_analysis` (the confirmatory figures are the `fig_*.png` written by `analyze_experiment.py` into each analysis directory). The full-suite invocation is not recorded; the logs are in section 15.

## 15. Observed logs, confirmatory sessions (read 2026-10-14; paths under `data/results/stage5_20261013`, `S5`)

| Item | Observation | File |
|---|---|---|
| Main session | `stage5_main_confirm`, 9 of 9 blocks, started 2026-10-13T07:51:19Z, finished 17:15:59Z, status complete; run-chain `rc=0` | `sessions_main/20261013T132115/session.json`, `main.stdout.txt`, `progress.txt` |
| Scarce-P session | `stage5_regimeR_confirm`, 8 of 8 blocks, 17:16:04Z to 23:19:09Z, status complete; `rc=0` | `sessions_regimeR/20261013T224600/session.json`, `regimeR.stdout.txt`, `progress.txt` |
| GPU session | `stage5_gpu_confirm`, 24 of 24 blocks, 06:49:56Z to 07:51:15Z, status complete; `rc=0` | `gpu_sessions/20261013T121953/session.json`, `gpu.stdout.txt`, `progress.txt` |
| Remote session (emulation) | `remote_emulation_confirm`, 12 of 12 blocks, 23:22:40Z to 23:39:15Z, status complete; `rc=0`; `progress.txt` ends `ALLDONE` after gpu, main and regimeR | `remote_sessions/remote_confirm/session.json`, `remote.stdout.txt` |
| Gates | 108, 48, 168 and 84 runs, `n_failing_checks` 0 in all four | `gate_sessions_main.json`, `gate_sessions_regimeR.json`, `gate_gpu_sessions.json`, `gate_remote.json` |
| Analyses | `n_runs` 108, 48, 168, 84; `n_excluded` 0; design hashes equal the protocol; evidence labels real, real, real, emulation; `code_versions` `95a74ba36708` (main, scarce-P, remote) and `d6e480bcfa67` (GPU) | `analysis_main`, `analysis_regimeR`, `analysis_gpu`, `analysis_remote` (`analysis.json`) |
| Post-hoc analysis | `n_runs` 108, `n_included_primary` 84, `n_excluded` 24 | `analysis_main_posthoc_excl_blocks_5_6/analysis.json`, `exclusions.csv` |
| Reproduction from raw logs | four checks each (session manifest with missing, changed, extra all empty; event-log hashes; `summary` table; `effects` table), `ok` true, written 2026-10-13T23:42:27Z to 23:42:33Z | `data/results/stage5_repro/repro_analysis_{main,regimeR,gpu,remote}.json` |
| Full test suite | before the sessions: `384 passed, 1 skipped in 98.01s` (file time 2026-10-13 12:19 +0530); after: `392 passed, 1 skipped in 131.54s` (2026-10-14 05:15 +0530) | `full_suite_before_confirmatory.txt`, `full_suite_final.txt` |
| Background load | 1,928 samples from 2026-10-13T06:50:24Z to 23:18:48Z, longest gap 32.0 s; median non-experiment CPU 35.1%, median machine CPU 23.6%, minimum free RAM 2.09 GB (computed here) | `load/load_20261013T121952.jsonl` |
| Drift, learning curve, regret | see `analysis_extra/commands.txt` for the commands and config hashes; learning-curve verdicts in `learning_curve/run.log` | `analysis_extra/` |

Not observed here: a rebuild of Montage from the patched sources (the recipe is in `MONTAGE_WINDOWS_BUILD.md`). Added at the end: the exact chain scripts that ran the sessions are stored in `scripts/chains/` (`run_stage5.sh` is the stage-5 chain), stage-level SHA-256 manifests exist for stages 1 to 5, and a clean-checkout run at the final state is `data/results/stage5_repro/repro_clean_checkout_final.json`.
