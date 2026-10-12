# Workload and data provenance

Status (updated 2026-10-12): **Stage 1 executed on this machine; the sequential-run gate is passed.** Montage and the generator were cloned and built natively on Windows, one configuration was frozen, its inputs were downloaded and hashed, and three valid sequential runs completed with identical outputs [real] (`data/results/stage1_20261011/valid/stage1_gate.json`). Several earlier attempts failed for tool-chain or runner reasons and are kept as evidence and excluded (see [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md)). Evidence labels as in [PROJECT_SPEC.md](PROJECT_SPEC.md).

## 1. Who supplies what

| Component | Supplied by | Ours to implement | Open question |
|---|---|---|---|
| Workflow generator (Python, Pegasus.api) | `pegasus-isi/montage-workflow-v3` | Run it; read its output | Python/Pegasus versions it needs [unverified]; superseded 2026-10-11: run with a 3-edit Windows copy under the locked `pegasus-wms.api==5.1.3` (section 4, item 5) |
| Montage executables (`mProject`, `mDiffFit`, ...) | Montage toolkit (Caltech-IPAC) | Build or obtain them for this machine | Native Windows build unconfirmed; superseded 2026-10-11: built natively with w64devkit and workarounds, see [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md) |
| Workflow description (`montage-workflow.yml`, replica and transformation catalogs, `pegasus.properties`) | Generator output | Workflow adapter into our DAG | Exact file formats seen only in the generator source |
| Input images | Remote archives (DSS2 and 2MASS examples) | Download, hash, record | Host service, sizes [unverified]; superseded 2026-10-11: host `archive.stsci.edu`, sizes and hashes in section 3; licence/terms still unverified |
| Execution engine | Pegasus / HTCondor (not used by us) | Our coordinator executes the commands | Whether per-job semantics (clustering, staging) can be reproduced |
| Task-level traces | WfInstances (real executions, WfFormat 1.6) | Optional **[replay]** use | Not application execution |
| Synthetic workflow generators and benchmarks | WfCommons (WfChef, WfGen, WfBench) | Optional | Montage recipe and WfBench GPU support [unverified] |
| CPU/GPU kernels | Rodinia (optional cross-check) | Build with local toolchain | Windows build and CUDA toolkit missing |

Generator, toolkit, data source and execution engine are four separate components. A DAG trace or simulation is not equivalent to executing the application.

## 2. Official sources inspected

| Source | URL | Organisation | Date / version seen | Claim supported | Inspected |
|---|---|---|---|---|---|
| Montage workflow v3 (README and `montage-workflow.py`) | https://github.com/pegasus-isi/montage-workflow-v3 | Pegasus (ISI) | No releases or tags; 15 commits; container named `montage-workflow-v3-20260810.sif`; Apache-2.0 | Generator structure, jobs, outputs, Apptainer requirement | yes (page text) |
| Pegasus workflow gallery, Montage page | https://pegasus.isi.edu/workflow_gallery/ , .../gallery/montage/index.php | Pegasus (ISI) | n/a | Example run: 387 tasks, 441 s workflow runtime; no GPU mention, no data sizes | yes |
| Montage toolkit | https://github.com/Caltech-IPAC/Montage | Caltech-IPAC | README mentions 7.0 and a v6.1 tag; no release dates; BSD 3-clause | ANSI C, Cygwin/cross-compile mention; no CUDA/GPU mention found | yes (README) |
| WfCommons | https://github.com/wfcommons/wfcommons | WfCommons | No release shown; LGPL-3.0 | Framework for traces, generators, benchmarks; Python 3.11+ | yes (page) |
| WfInstances | https://github.com/wfcommons/WfInstances | WfCommons | LGPL-3.0; WfFormat 1.6 | Real-execution traces; 17 Montage JSON files (`pegasus/montage`, platform `chameleon`) | yes (page and directory) |
| Rodinia mirror | https://github.com/socal-ucr/Rodinia | UVA / mirror | Release 3.1, 2015-12-12; BSD-style | CPU and CUDA benchmarks; standalone kernels | yes (page, LICENSE) |
| Coleman et al., "WfCommons: A Framework for Enabling Scientific Workflow Research and Development", FGCS 128:16–27, 2022, doi 10.1016/j.future.2021.09.043 | via repository page | Coleman, Casanova, Pottier, Kaushik, Deelman, Ferreira da Silva | 2022 | Citation for WfCommons | identified only |
| Pegasus | https://github.com/pegasus-isi/pegasus | ISI | Apache-2.0 | Engine; not used by us | page only |
| **Added 2026-10-11 (Stage 1).** Montage toolkit, shallow clone | https://github.com/Caltech-IPAC/Montage | Caltech-IPAC | commit `ac0a15334f670ed83e328b6c5768f94b4b847359`, dated 2026-04-06 in [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md) | Source of the executables used [real]; licence BSD 3-clause (header of `LICENSE` read) | cloned and built; build copy outside the project |
| Workflow generator `montage-workflow-v3`, clone | https://github.com/pegasus-isi/montage-workflow-v3 | Pegasus (ISI) | commit `975047e916d3d049d9ff0da17e7fe5aaac979c64`, dated 2026-09-22 in the build note; Apache-2.0 (`LICENSE`) | Generated the workflow instance [real] | cloned; used through a Windows copy (`data/montage/montage-workflow-windows.py`, three edits, diff in `data/montage/montage-workflow-windows.diff`) |
| Build toolchain w64devkit | https://github.com/skeeto/w64devkit/releases/tag/v2.10.0 (`w64devkit-x64-2.10.0.7z.exe`) | skeeto | v2.10.0; SHA-256 `18d0a4c71a166f8401ab6305781bec5882b40b5e06ba9807c61cb5f3b3c6325e` (the build note says it matches the digest GitHub shows); GCC 16.2.0, GNU Make 4.4.1 per the build note | Compiler for the native Windows build [real] | downloaded; licences of the bundled tools **not read**, not redistributed |
| DSS image data via the STScI archive | `http://archive.stsci.edu/cgi-bin/dss_search?v=poss2ukstu_blue&r=...&d=...&e=J2000&w=42.60&h=42.60&f=fits&c=gz` (nine URLs recorded in `data/montage/instances/d1.1_dss2b_c56.7_24.0/instance.json`; the survey code `poss2ukstu_blue` is in each URL) | STScI archive (host `archive.stsci.edu`) | Fetched 2026-10-11 (file times); plain HTTP | Raw input images, 116,069,760 bytes in total [real] | downloaded and hashed. **Licence and terms of use of the image data NOT verified** (no terms page was read) |
| Python environment | `requirements-lock.txt` in the repository root; `data/results/stage1_20261011/environment_manifest.json` | n/a | Python 3.11.9 (CPython, MSC v.1938, AMD64) per the manifest; `pegasus-wms.api==5.1.3`, `pegasus-wms.common==5.1.3`, `astropy==8.0.1`, `numpy==2.4.6`, `PyYAML==6.0.3`, `requests==2.34.2`, `torch==2.11.0+cu128` | Versions the scripts ran with [real] | read from the lock file |

What the owner should check for the image data (not done here): the STScI Digitized Sky Survey terms of use and any citation or acknowledgement text the archive requires, and whether copies of the downloaded FITS files may be redistributed with a thesis or a public repository. Until then the raw images stay under `data/` (excluded from Git per the Stage 0 record) and are not redistributed.

Montage task details from the generator source (code reading, not a documented specification): jobs per band are `mProject` (one per image), `mDiffFit` (one per overlapping pair; runs `mDiff` and `mFitplane`), `mBackground` (one per image), and one each of `mConcatFit`, `mBgModel`, `mImgtbl`, `mAdd`, `mViewer`; a colour `mViewer` job is added if red, green and blue bands are all given. Logical jobs per band: 2N + M + 5 (N images, M overlapping pairs). Each job requests 1 core, 1 GB memory and 4 GB disk. Generator clustering factors are 10 for `mProject` and 20 for `mDiff`, `mDiffFit` and `mBackground`. Commands: `montage-workflow.py --work-dir ... --center "RA DEC" --degrees D --band survey:...`; execution through `pegasus-run`. Raw images are registered as remote replicas fetched by URL. The generator exits if the output `data/` folder already exists, so each run needs a fresh directory. Intermediate names: `p<base>.fits`, `p<base>_area.fits`, `c<base>.fits`, `<id>-fit.<base>.txt`, `<id>-*.tbl`; outputs `<id>-mosaic.fits`, PNG and `mosaic-color.png`.

WfInstances Montage sizes (instance file names; degree reading of the file codes is my interpretation): 2MASS 0.05° 58 tasks, 0.1° 103, 0.5° 1,738, 1° 4,846, 2° 9,805; DSS 0.5° 58, 1.0° 472, 2.0° 6,448. These are sizing hints for the real trace, **not** predictions of what the generator produces.

## 3. Smallest reproducible configuration

Superseded 2026-10-11 (kept for history): "Candidates: a DSS or 2MASS configuration of roughly 0.1–0.5° single-band; the generator reports its own task count when run. Unknown now: input bytes, download time, whether the commands run on Windows, and the real per-task times." The 0.1–0.5° candidates were not tried; the exploratory trials started at 1.0° (table in 3.2). I have no recorded reason for skipping the smaller sizes other than the project decision to look for a DAG with dozens of tasks.

### 3.1 Frozen primary configuration [real]

Instance name `d1.1_dss2b_c56.7_24.0` (directory `data/montage/instances/d1.1_dss2b_c56.7_24.0/`, record `instance.json`, label `real`).

| Field | Value (source) |
|---|---|
| Centre | `56.7 24.0` (instance.json) |
| Size | 1.1 degrees; the generator's `mArchiveList` call used 1.562 x 1.562 (`generator_stdout.txt`) |
| Band | `dss:DSS2B:blue` (instance.json); archive survey code `poss2ukstu_blue` in the URLs |
| Input images | 9 (instance.json). Nominal 2556 x 2556 pixels in `1-images.tbl` (`naxis1`, `naxis2`); the downloaded FITS headers I read in all nine files say NAXIS1 = 2531, NAXIS2 = 2536, BITPIX = 16. **The "2556 x 2556" figure is the archive-list nominal size, not the file size.** |
| Input bytes | 116,069,760 in total; 12,896,640 per image (instance.json) |
| Input hashes | the nine SHA-256 values are in instance.json (`inputs[].sha256`) and are not copied here, to avoid transcription errors; first image `poss2ukstu_blue_001_001.fits` = `e27d898cbe6b2355d95221ea6b76188d3dd8d6f14b7d0c5d26efb8003b4566f2` |
| Workflow file | `data/montage/instances/d1.1_dss2b_c56.7_24.0/data/montage-workflow.yml`, SHA-256 `951afb1bb4256cadcfc75bf81f3dc3f021caa56367e69861e8d21736e3ba35e3` (recorded in instance.json; I recomputed it from the file and it matches); the file's `pegasus:` field reads 5.0.4 (workflow schema version) |
| Jobs | 59 in total (instance.json `n_jobs`): mProject 9, mDiffFit 36, mBackground 9, mConcatFit 1, mBgModel 1, mImgtbl 1, mAdd 1, mViewer 1. I counted these in the workflow file (`name:` lines per transformation); the sum is 59 and equals 2N + M + 5 with N = 9 and M = 36 (36 overlaps reported by `mOverlaps`) |
| Output region | `region-oversized.hdr` is 3960 x 3960 pixels, RA---TAN/DEC--TAN, centre 56.7 24.0, CDELT 0.000277778 degrees |
| Generate / download time | 1.88 s and 75.81 s (instance.json) |
| Generator | Windows copy of `montage-workflow-v3` at commit `975047e916d3d049d9ff0da17e7fe5aaac979c64` (section 2) |
| Montage | commit `ac0a15334f670ed83e328b6c5768f94b4b847359` built natively ([MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md)) |

Results that depend on the sequential runs, not yet available:

| Quantity | Value |
|---|---|
| Per-task wall time of a complete valid run (59 tasks) | [real] all 59 tasks timed in each of 3 runs (`data/results/stage1_20261011/valid/seq{1,2,3}/run.json`, pinned to P-core logical processor 2). Medians over the 3 runs, seconds: mProject 160.6 (n=27, min 141.0, max 169.9), mDiffFit 0.25 (n=108), mBackground 0.34 (n=27), mViewer 4.16 (n=3), mAdd 0.87, mBgModel 0.38, mConcatFit 0.21, mImgtbl 0.09 (`stage1_gate.json`, `per_transformation_wall_s`). The 9 mProject tasks are about 98.7% of the sequential time (9 x 160.6 s of ~1465 s; computed here) |
| Mosaic hash equality across repeated runs | [real] `1-mosaic.fits` SHA-256 `54c1c4b0c827970e7dc6cb2ba949b4123ea069d51eae608ef0c031cb4ecdd84b`, `1-mosaic_area.fits` `49f3b92a57451509f58994e6e784a71896239b709f9cf48fe7c875c3d6b4ea64`, `1-mosaic.png` `2c33f7ce8590b9bd83e35e8fb7696b32c9d3b35c699637fa66a274fb2c11d935` identical in all 3 runs; FITS data max abs difference 0.0 (`stage1_gate.json`: `output_hashes_identical` true) |
| WCS sanity of the mosaic against `region.hdr` | [real] NAXIS 3960x3960, CRVAL 56.7/24.0, CDELT, CRPIX 1980.5, CTYPE RA---TAN/DEC--TAN all equal the requested header; finite pixel fraction 0.9666 (`stage1_gate.json`, `wcs`). (The check uses `region.hdr`, the output template; `region-oversized.hdr` is the intermediate projection frame.) |
| DAG edge agreement, generator dependencies versus file producer-consumer relations | [real] 59 jobs; 147 edges from `jobDependencies`, 147 from file relations, 0 only in either (`stage1_gate.json`, `dag`) |
| Total sequential makespan | [real] 1459.4 s, 1467.1 s, 1469.3 s (3 runs, one core, `valid/seq*/run.json`); the machine was not idle (WSL VM, browser, editor running; see `environment_manifest.json`), power plan Balanced, processor performance ~79% at one sample |

### 3.2 Exploratory sizes tried [real, generation only]

Each trial ran only the generator steps (`mArchiveList`, `mDAGTbls`, `mOverlaps`); no images were reprojected. Counts are from `gen.log` in `data/montage/runs/trial_*` (images and overlaps). The job count is the generator formula 2N + M + 5 applied to those counts, and for the 1.1 degree instance it equals the 59 jobs counted in the workflow file.

| Requested size (degrees) | Images (N) | Overlapping pairs (M) | Jobs (2N + M + 5) | Evidence |
|---|---|---|---|---|
| 1.0 | 4 | 6 | 19 | `runs/trial_1.0/gen.log` |
| 1.1 | 9 | 36 | 59 | `runs/trial_1.1/gen.log`; workflow file counted |
| 1.2 | 9 | 36 | 59 | `runs/trial_1.2/gen.log` |
| 1.3 | 9 | 36 | 59 | `runs/trial_1.3/gen.log` |
| 1.4 | 9 | 36 | 59 | `runs/trial_1.4/gen.log` |
| 1.5 | 16 | 120 | 157 | `runs/trial_1.5/gen.log` |
| 2.0 | 25 | 300 | 355 | `runs/trial_2.0/gen.log` |

A quick line count of `id:` entries in the trial workflow files gave one less than the formula for every trial, including 1.1 degrees where the full count is 59 (the pattern probably misses one entry); the formula was therefore used. Only the 1.1 degree job total is a full count of the workflow file; the other totals are formula values. Directories `trial05` and `trial05b` also exist under `runs/`; their parameters were not inspected and no result is claimed from them.

### 3.3 Reason for the choice

The 1.1 degree configuration is the smallest tried that gives a DAG with enough structure for a scheduling study: 59 tasks, a 36-way parallel `mDiffFit` stage, 9 parallel `mProject` and 9 parallel `mBackground` tasks, and a serial tail (`mConcatFit`, `mBgModel`, `mImgtbl`, `mAdd`, `mViewer`). The 1.0 degree run has 4 images and 19 jobs, which is too small for dozens of tasks; 1.2 to 1.4 degrees give the same 9 images and 59 jobs as 1.1; 1.5 degrees and above need 16 or more images (157 or more jobs, at least 16 reprojections of the kind timed below). The measured `mProject` time (section 4, item 6) makes the cost of larger configurations a practical constraint on this laptop: the 9 `mProject` tasks alone took about 17 minutes in sequence in the first run.

## 4. Compatibility questions: status after Stage 1 (2026-10-11)

The original six questions are kept with their answers. Answers marked [real] rest on files I read in this repository; the sequential-run gate values are in section 3 and `valid/stage1_gate.json`.

1. **Native Windows build of Montage versus Cygwin/MSYS2, WSL2 or a container (Apptainer is Linux-only).** Answered [real]: a native Windows build with the w64devkit toolchain produced the executables the workflow uses (`mProject`, `mDiffFit`, `mDiff`, `mFitplane`, `mConcatFit`, `mBgModel`, `mBackground`, `mImgtbl`, `mAdd`, `mViewer`, `mArchiveList`, `mDAGTbls`, `mOverlaps`), without WSL2, a container or admin rights. It needed ten workarounds (compiler flags for GCC 16, renamed `wcs*` functions, libjpeg and FreeType built by hand, a ported `svc` library and `mArchiveList`, and others), all listed in [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md). The Montage `Windows/Notes.txt` describes a different route (Docker cross-compile). That the full set of executables produces a correct, repeatable mosaic is shown by `valid/stage1_gate.json` (3 of 3 runs, identical hashes).
2. **Whether our coordinator can execute each job's command line directly, or the generator's clustered jobs and pre/post scripts must be reproduced.** Answered by design [real, code present; run results PENDING]: each of the 59 YAML jobs is run as its own command line without a shell (`src/caosched/core/extcmd.py`, `src/caosched/experiment/montage_adapter.py`), i.e. **unclustered**. The generator's clustering factors (10 and 20, section 2) are Pegasus profiles and are not reproduced. The reference script `scripts/montage_sequential.py` does the same in file order. Whether unclustered execution changes per-task times compared with Pegasus clustering was not measured.
3. **Data-staging semantics (Pegasus stages files between sites; we use one shared directory).** Answered [real]: one flat work directory per run; raw inputs and the generator's `.tbl` and `.hdr` files are copied in before the first task, and every task reads and writes there (`scripts/montage_sequential.py`; the adapter creates a fresh `<workdir>/work`). There is no staging between sites. Consequence: transfer cost of file movement between pools is **not** measured by Montage runs on this machine; any remote-pool effect is [emulation] only.
4. **Input archive availability and licence terms of the image data.** Partly answered: the archive was reachable on 2026-10-11 and delivered 9 files, 116,069,760 bytes, in 75.81 s (instance.json). **Licence and terms of use: not verified** (section 2 lists what the owner should check).
5. **Montage version and the generator's required Python and Pegasus versions.** Partly answered. Montage: commit `ac0a15334f670ed83e328b6c5768f94b4b847359`; the README's version labelling was found inconsistent in the literature pass and no release number was resolved. Generator: commit `975047e916d3d049d9ff0da17e7fe5aaac979c64`. The generator ran under Python 3.11.9 with `pegasus-wms.api==5.1.3` (from `requirements-lock.txt` and the environment manifest); the generated YAML states `pegasus: 5.0.4` as its schema version. The generator's **declared minimum** Python and Pegasus versions were not extracted, and the generator also targets an Apptainer container (section 2), which we do not use: not found in sources inspected for a minimum version.
6. **Whether each task is long enough to schedule meaningfully compared with our ~0.5 ms per-hop runtime overhead (earlier measurement) and process start-up cost.** Partly answered from the first sequential run (`data/results/stage1_20261011/seq_run1/run.json`, status `failed:ID0000011`, 11 tasks recorded, total 1036.68 s): the nine `mProject` tasks took 113.89 to 117.15 s each (about 115 s), against ~0.5 ms runtime overhead, so these are long enough by a factor of over 10^5. The first `mDiffFit` took 0.55 s; the second exited 1 after 0.048 s (the failure described in [MONTAGE_WINDOWS_BUILD.md](MONTAGE_WINDOWS_BUILD.md)). Times of the other task types and of full 59-task runs are in the section 3 table (medians: mDiffFit 0.25 s, mBackground 0.34 s, mViewer 4.2 s, mAdd 0.87 s); process start-up cost was not measured separately. Short tasks such as `mDiffFit` may be comparable to start-up cost; this is open until measured.

State of the sequential runs when I inspected the folders (`data/results/stage1_20261011/`): `seq_run1` failed at task `ID0000011` (excluded from gates by the build note); `seq_runA`, `seq_runB`, `seq_runC` each recorded 10 tasks and `failed:ID0000010` (the stored output tail of `seq_runA` shows `svc_init(): fork() failed`); `rep1` has only a `work` folder and no `run.json`. The build note says runs A to C use the corrected binary, which does not match these statuses, so a later fix and rerun may exist that I could not see. No run is treated as valid here.

## 5. Dataset and input-data source

Inputs: archive images referenced by the generator (DSS2/2MASS examples). Superseded 2026-10-11: "Source host not verified" is now answered for the frozen instance (host `archive.stsci.edu`, survey `poss2ukstu_blue`, section 2 and 3.1); its licence terms are still not verified. Every downloaded file is stored read-only with SHA-256, size and URL in a manifest; for the frozen instance the per-file URL, size and SHA-256 are in `instance.json` (read-only status of the files was not checked here). Historical datasets under `data/datasets/` (145,378 task rows) come from the earlier machine and the earlier benchmark and image workloads; they stay as history and are not mixed with Montage data.

## 6. DAG generation process

Plan (original) and what was done (2026-10-11):

1. Create a fresh work directory; run the generator with the fixed configuration inside the chosen environment. **Done** [real] by `scripts/montage_prepare.py --name d1.1_dss2b_c56.7_24.0 --center "56.7 24.0" --degrees 1.1 --band dss:DSS2B:blue`: it runs the Windows-patched generator, downloads the raw inputs and writes `data/montage/instances/<name>/{data/,inputs/,instance.json}`; it refuses to reuse a name. The generator's stdout is kept in `generator_stdout.txt` (three sub-commands: `mArchiveList`, `mDAGTbls`, `mOverlaps`).
2. Copy `montage-workflow.yml`, catalogs and properties to the evidence folder with hashes. **Done for the instance**: the workflow file is under the instance's `data/` and its SHA-256 is recorded in `instance.json`; `pegasus.properties` is in the instance folder. A separate copy in the Stage 1 evidence folder was not checked.
3. Run the adapter (Stage 2) to produce the internal DAG; compare job counts and edges to the workflow file. **Code written** (`src/caosched/experiment/montage_adapter.py`, `tests/test_montage_adapter.py`, `tests/test_workflow_adapter.py`); the edge comparison is implemented in `scripts/stage1_report.py` (function `dag_vs_generator`, compares the generator's `jobDependencies` with producer-consumer file relations). Result [real]: 59 jobs, 147 edges from `jobDependencies` = 147 from file relations, 0 disagreements (`valid/stage1_gate.json`). Test status: full suite 364 passed, 1 skipped on 2026-10-12 (`data/results/stage1_20261011/tests/full_suite_single_process.txt`).
4. Run the commands sequentially (Stage 1) and record per-task wall time, input and output files, sizes and exit status. **Script written and started** [real]: `scripts/montage_sequential.py --instance d1.1_dss2b_c56.7_24.0 --out <fresh dir>` reads the YAML directly, copies inputs into a fresh `work` folder, checks that every job's inputs exist before it starts (so file order is verified as a valid topological order), runs jobs one at a time with the Montage `bin_win64` directory first on `PATH` (because `mDiffFit` starts `mDiff` and `mFitplane` by name), and writes `run.json` with per-task wall time, exit status, output sizes and SHA-256 values. No complete valid run was available when I inspected the evidence folder (section 4). Then `scripts/stage1_report.py --evidence data/results/stage1_20261011 --instance d1.1_dss2b_c56.7_24.0 <run dirs>` compares repeated mosaics (shape, NaN pattern, maximum absolute difference), checks the mosaic header against `region-oversized.hdr` (WCS sanity), and compares the DAG edges; it writes `stage1_gate.json`, which does not exist yet.

## 7. Provenance and hashing plan

- Environment manifest per session: OS build, CPU model and topology, RAM, GPU and driver, Python and package versions, Montage and generator commits, container or WSL image digest.
- SHA-256 of generator output, input files, intermediates (optional), and final mosaic.
- Raw logs are append-only and never overwritten; a manifest like `manifests/stage0_20261010/` is produced for each new evidence set.
- Configuration snapshot copied beside every result file.

Done so far (2026-10-11) [real]: environment manifest `data/results/stage1_20261011/environment_manifest.json` (Python 3.11.9 among other fields); `requirements-lock.txt`; Montage and generator commits (section 2); w64devkit SHA-256 (section 2); executable hashes in `docs/research_redesign/montage_build/bin_win64_sha256.txt` (named by the build note; I did not open it); input URLs, sizes and SHA-256 and the workflow-file SHA-256 in `instance.json`; per-task output sizes and SHA-256 in each sequential `run.json`; raw sequential logs kept, including failed runs (`seq_run1`, `seq_runA`, `seq_runB`, `seq_runC`). The SHA-256 of the final mosaic of a valid run and the container/WSL digest (not applicable: native build) are in `valid/stage1_gate.json` (`1-mosaic.fits` `54c1c4b0c827970e7dc6cb2ba949b4123ea069d51eae608ef0c031cb4ecdd84b`) and n/a respectively. The generator's SHA-256 for the Windows copy `montage-workflow-windows.py` was not recorded in the files I read.

## 8. Application execution, trace replay and simulation

- **Application execution [real]:** our coordinator launches the Montage executables and the outputs are checked.
- **Trace replay [replay]:** WfInstances records re-fed to a model; no application runs. Allowed for scale studies if clearly labelled.
- **Simulation [simulation]:** generated or modelled runtimes. Not used for primary claims.
- **Emulation [emulation]:** real tasks over a link shim.
- Results from different categories are never pooled or presented as one.

## 9. Literature sources

The literature table (with inspected level per paper) is in [PROJECT_SPEC.md](PROJECT_SPEC.md) section 6. Additional references used for algorithm and model decisions:

| Reference | Used for | Inspected |
|---|---|---|
| Topcuoglu, Hariri, Wu, IEEE TPDS 13(3):260–274, 2002 (HEFT, CPOP) | Baseline assumptions | Abstract and secondary sources only; original **not read** |
| Arabnejad and Barbosa, IEEE TPDS 25(3):682–694, 2014 (PEFT) | Baseline | Snippets and one secondary paper; original **not read** |
| Gorishniy, Kotelnikov, Babenko, TabM, ICLR 2025, arXiv 2410.24210 | Neural tabular candidate; Apache-2.0 code `tabm`, k=32 default | arXiv HTML, README; PDF not parsed |
| Prokhorenkova et al., CatBoost, NeurIPS 2018 (venue from memory), arXiv 1706.09516 | Tree-based comparator; Apache-2.0 | Abstract, repository page |
| Grinsztajn, Oyallon, Varoquaux, NeurIPS 2022 (venue from memory), arXiv 2207.08815 | Trees vs deep models on medium tabular data | Abstract |
| Gorishniy et al., NeurIPS 2021, arXiv 2106.11959 | MLP baseline background | Abstract |
| Kapoor and Narayanan, Patterns 4(9):100804, 2023 | Leakage taxonomy | arXiv preprint full text |
| Demšar, JMLR 7, 2006 | Non-parametric comparison background | Abstract/snippet |
| da Silva, Juve, Rynge, Deelman, Livny, Parallel Processing Letters 25(3), 2015 | Montage runtime estimation | Full text |
| Augonnet et al., StarPU, CCPE 23(2):187–198, 2011 (volume/pages from a reference list) | Prediction-driven CPU/GPU scheduling | Preprint full text |
| Teodoro et al., arXiv 1505.03819 | Scheduler sensitivity to runtime error | Relevant section |

Added 2026-10-11 from [LITERATURE_UPDATE.md](LITERATURE_UPDATE.md) (inspected levels copied exactly; FULL-DIRECT = PDF text extracted and read; FULL-VIA-FETCH = read through a summarising fetch tool, numbers to be re-checked; ABSTRACT; SNIPPET; NOT REACHABLE):

| Reference | Used for | Inspected |
|---|---|---|
| Chen and Deelman, WorkflowSim (author-hosted PDF; venue and year not printed in the extracted text) | Montage with real Pegasus traces in a simulator; overhead modelling; FCFS/MCT/MinMin/MaxMin, not HEFT | FULL-DIRECT |
| Coleman et al., WfCommons, arXiv 2105.14352 | Montage traces (17 instances) and recipes; simulation validation | FULL-DIRECT |
| Coleman et al., WfBench, arXiv 2210.03170 | Montage-shaped benchmark; GPU listed as future work in the paper | FULL-DIRECT |
| Beaumont et al., "Scheduling on Two Types of Resources: a Survey", arXiv 1909.11365, section 6.1.1 | HEFT description (rank, EFT with insertion) | FULL-DIRECT |
| Dai and Zhang, Scientific World Journal 2014, DOI 10.1155/2014/465702 | Secondary source for HEFT rank, EST/EFT, PEFT OCT formulas | FULL-VIA-FETCH |
| Guo, Zhou, Gu, Micromachines 13(7):1067, 2022, DOI 10.3390/mi13071067 | Secondary source for PEFT OCT, rank_oct, O_EFT | FULL-VIA-FETCH |
| Bader et al., Lotaru, arXiv 2309.06918v1 | Predicted runtimes driving HEFT in simulation | FULL-VIA-FETCH |
| Bader et al., Reshi, arXiv 2208.07905v2 | Predicted runtimes, injected error, HEFT baseline in simulation | FULL-VIA-FETCH |
| Bader et al., "Predicting the Performance of Scientific Workflow Tasks for Cluster Resource Management", arXiv 2504.20867v1 | Survey of runtime-prediction methods; none targets GPUs | FULL-VIA-FETCH |
| Lu and Reda, "Agentic CPU-GPU Scheduling for Heterogeneous AI Workloads", arXiv 2607.22242v1 (preprint) | Real CPU/GPU hardware, HEFT variant baseline, no learned predictor | FULL-VIA-FETCH |
| Wang et al., INSPIRIT, arXiv 2404.03226v1 (preprint) | StarPU DMDAP priority scheduling, offline average times | FULL-VIA-FETCH |
| Rhea et al., dfreproject, arXiv 2505.03932v2 | GPU reprojection library (not Montage); speedup figures unread | FULL-VIA-FETCH |
| Ilyushkin and Epema, CCGrid 2018, "The impact of task runtime estimate accuracy on scheduling workloads of workflows" | Estimate accuracy versus scheduling policy in simulation | ABSTRACT |
| Rayej et al., WIDESim, arXiv 2206.03538 | Peripheral simulator | ABSTRACT |
| Li, Paolieri, Golubchik, "Partition-Aware Scheduling for Mobile Heterogeneous Inference Co-Execution", arXiv 2609.14213 | Mobile CPU+GPU with latency predictors; HEFT baseline claim unverified | ABSTRACT |
| John, Milthorpe, Hérault, Bosilca, FGCS 2024, DOI 10.1016/j.future.2024.03.017 | PaRSEC multi-GPU work sharing | ABSTRACT (OpenAlex) |
| Berriman et al., arXiv 2111.11624 | Montage at scale with Pegasus; no GPU | ABSTRACT |
| Casanova et al., WRENCH (SC18 WORKS) | Simulation framework used by WfCommons validation | SNIPPET |
| Pham et al. 2017; Nadeem et al. 2019; Monge et al. 2014; Chirkin et al. | Runtime-prediction work linked to workflow scheduling | SNIPPET (titles only; not to be cited beyond title) |
| Parsl, Dask, Ray, Pegasus documentation pages | GPU handled as resource labels and pinning | FULL-VIA-FETCH (the Pegasus Python API page: first 100,000 of 169,271 characters) |
| WfCommons repository files (Montage recipe, `bench.py`, releases v1.4 and v1.5) and WfInstances Montage README | Recipe existence; `gpu_work` parameter; 17 Montage traces | FULL-VIA-FETCH (WfBench kernels unread; recipe class name SNIPPET) |
| HEFT/CPOP original (Topcuoglu et al. 2002, DOI 10.1109/71.993206) and PEFT original (Arabnejad and Barbosa 2014, DOI 10.1109/TPDS.2013.57) | Baselines | NOT REACHABLE (abstract and metadata only) |
| LACHESIS IEEE version (DOI 10.1109/MDM55031.2022.00040), Cao IoT-J final (DOI 10.1109/JIOT.2024.3374969), Liu FGCS final (DOI 10.1016/j.future.2024.04.034) | Final published versions | NOT REACHABLE |

Items not verified anywhere in this repository, after the 2026-10-11 literature pass: verbatim patent claim text (the paraphrase was reached twice; the PDF routes failed); HEFT/PEFT originals (formulas now exist from secondary sources only, and a possible same-processor condition in PEFT's OCT communication term is unresolved); the IEEE camera-ready of LACHESIS; final journal versions of Cao 2024 and Liu 2024; the paywalled papers; the licence and terms of the DSS image data. Superseded 2026-10-11 (were listed as unverified here, now partly answered): Pegasus version requirements (locked version `pegasus-wms.api==5.1.3` is known, the generator's declared minimum is not); WfBench GPU support (present in current code, content of the kernels unread); WfCommons Montage recipe (directory exists, class name only from a snippet); Montage input data volumes (116,069,760 bytes for the frozen 9-image instance, measured; other sizes not measured).
