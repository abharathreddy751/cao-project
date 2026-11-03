# Stage 3 data-collection plan

Status: **[plan] 2026-10-12. Fixed before any Stage 3 collection run; revised once the same day (v2) before collection, after the Stage 2 timing showed about 7 minutes per random run.** No Stage 3 result exists; nothing below is a finding. Every number is a design decision made by the author of this plan and is changed only by writing a new design (new SHA-256) and saying so in the report. Figures taken from evidence files are named with their source; figures marked *assumption* are not measured for the Stage 3 conditions. Roles of instances, the candidate list, the TabM decision, the margin and the splits are governed by [STAGE3_FREEZE.md](STAGE3_FREEZE.md); where this file and the freeze differ, the freeze wins.

Related: [STAGE34_DRAFT.md](drafts/STAGE34_DRAFT.md) (section 1.1 and 1.2), [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) (sections 3 to 6), `scripts/make_stage3_designs.py` (writes the design files listed here).

**Superseded and unused:** `data/results/stage3_20261012/designs/` (v1, 105 runs: five conditions per block, 6/6/6/3 blocks). Those files stay on disk unchanged because `data/` is not edited, but no run uses them and they must not be launched. The designs actually used are in `data/results/stage3_20261012/designs_v2/` (section 4).

## 1. Purpose

Collect real Montage task executions under varied placements and occupancy, on more than one workflow instance and more than one size, so that (a) Ridge, CatBoost and MLP can be fitted on some instances, (b) a leave-instance-out fold exists, and (c) one instance and size is never touched until the final test. Collection runs scheduling policies on a shared set of workers; it is not a comparison of policies. Prediction quality and scheduling value are reported separately (EVALUATION_PROTOCOL section 1).

## 2. Instances and their roles

Roles are those of STAGE3_FREEZE.md section 1.

| Instance | Tasks | Inputs | Role | Sequential reference (status ok) |
|---|---|---|---|---|
| `d1.0_dss2b_c56.7_24.0` | 19 | 4 | training | 489.7 s, `refs/d1.0_dss2b_c56.7_24.0/run.json` field `total_wall_s` (489.69) |
| `d1.1_dss2b_c56.7_24.0` | 59 | 9 | training (primary instance of Stage 1/2) | 1459.4 s, Stage 1 run `data/results/stage1_20261011/valid/seq1` (`stage1_gate.json`, `reps.seq1.total_wall_s`) |
| `d1.1_dss2b_c10.7_41.3` | 59 | 9 | tuning fold (leave-one-instance-out) | 1083.7 s, `refs/d1.1_dss2b_c10.7_41.3/run.json` |
| `d1.5_dss2b_c56.7_24.0` | 157 | 16 | **final test, size withheld**; evaluated once | 1896.4 s, `refs/d1.5_dss2b_c56.7_24.0/run.json` |

The three `refs/` values were read from the `status`, `total_wall_s` and `n_tasks` fields of the `run.json` files on 2026-10-12 (all `status: ok`). The primary instance's reference is the Stage 1 run, not a file under `refs/`.

Rules (STAGE3_FREEZE.md sections 1 and 2):

- Fitting and tuning use `d1.0`, `d1.1 c56.7_24.0` and `d1.1 c10.7_41.3` only. Folds: leave-one-instance-out over these three, plus the time-ordered split within the primary session as the drift check. A run never appears on both sides of a fold.
- `d1.5` is **final test only**. It is evaluated once, after the configuration and the selected model are frozen; it is never used for fitting or tuning. Its sessions are written to a separate directory (section 6) and its dataset is built only at that point.
- `d1.1 c10.7_41.3` is a tuning fold (decided in the freeze), so it is **not** an untouched test instance. The protocol requirement "at least one instance and one size never used for fitting or tuning" is met by `d1.5` alone (a new instance and a new size at once).
- The `size` split policy of `dataset/splits.py` cannot express "size held out" for Montage: every extcmd row has `size = 1` (the transformation is the workload; see `tests/test_est_identity.py`). The size hold-out is therefore an `instance` split with `test = ["d1.5_dss2b_c56.7_24.0"]`.
- Limitation to report: `d1.0`, `d1.1 c56.7_24.0` and `d1.5` share one sky centre, and `d1.1 c10.7_41.3` has the same DAG shape as the primary. Montage has eight task types and one dominant type (`mProject`, 98.7% of sequential time per STAGE3_FREEZE.md section 4), so the instances differ mainly in task counts, file sizes and the number of `mProject` and `mDiffFit` tasks. The test instance is therefore a larger instance of the same sky region, not an independent workload.

## 3. Conditions

Each block runs every condition once, in a seeded random order (`experiment/design.py`). The conditions are identical for all four instances. Three conditions per block (v2).

| Condition | Policy | Role | Settings |
|---|---|---|---|
| `EFT_E1` | earliest finish time with the E1 static profile (early binding) | reference; also decision logs for `candidates.csv` | profile `data/results/stage2_20261012/profile_montage/20261012T092355_profile.json` |
| `RandomOccupancy_s1` | `RandomOccupancy` (late binding) | data collection | seed 3101, all pools, `min_idle_s` 0.0 |
| `RandomOccupancy_s3` | same | data collection | seed 3103, `min_idle_s` 1.0, `concurrency` [4, 13] (random subset of 4 to 13 workers per run) |

Dropped from v1 to v2: `RandomOccupancy_s2` (seed 3102, subset, no idle gap) and `RandomOccupancy_s4` (seed 3104, all pools, idle gap 2.0 s). Reason: the Stage 2 timing (about 7 minutes per random run) made the five-condition design too long. The consequence is less variety in the occupancy settings; whether the remaining two span `busy_P`, `busy_E` and `target_busy_frac` widely is checked after collection by counting rows per feature value, not assumed.

Notes:

- `RandomOccupancy` is `dataset/campaign.RandomOccupancyPolicy` reached through `montage_adapter.build_policy`. Seeds are fixed per condition, so a condition repeats the same random stream in every block; the placements still differ between blocks because they depend on which workers are idle at the time. The subset lower bound of 4 workers caps the worst-case makespan (single narrow subsets of slow E workers); the Stage 2 worker set had 13 workers (6 P, 7 E).
- It places each task on a uniformly random idle worker that is eligible for the task. It logs the context of the chosen worker only (not a cost model), so it yields rows in `tasks.csv` but none in `candidates.csv`. `candidates.csv` rows come from `EFT_E1` (all 13 workers per decision, as the Stage 2 `EFT_*` logs).
- The reference is a data-collection reference: no confirmatory analysis is planned on these sessions.

## 4. Blocks, runs and rows

Design files: `data/results/stage3_20261012/designs_v2/design_<instance>.json`, with `adapter_config_<instance>.json` beside each (same format as `stage2_20261012/adapter_config.json`: `timeout_s` 1800, `cleanup_work` true, `run_timeout_s` equal to the design's). One design file per instance, because blocks cycle through `instances`. SHA-256 values below are of the files as they exist on disk (read with `sha256sum` on 2026-10-12, not by the runner); the Stage 3 evidence manifest should record the runner's own hash and the two must agree.

| Instance | Blocks | Runs (blocks x 3) | `run_timeout_s` | Design seed | Design SHA-256 |
|---|---|---|---|---|---|
| `d1.0_dss2b_c56.7_24.0` | 4 | 12 | 1800 | 20261013 | `8986d99aaaabcdead79e23bcf069ab1fca788f0ccfde17e10394e1e2629d0834` |
| `d1.1_dss2b_c56.7_24.0` | 4 | 12 | 2400 | 20261014 | `9b9a2919492c22832a702c0eb1c4c2a2347493f54d7b4523d11552f47ba04391` |
| `d1.1_dss2b_c10.7_41.3` | 4 | 12 | 2400 | 20261015 | `95364983ae6e0eb5e70397995d9fd5eba818b4f6a34d43d524460577ffcc8cd8` |
| `d1.5_dss2b_c56.7_24.0` | 2 | 6 | 7200 | 20261016 | `ff97ffe8771384acc78e67ba22c8946f22b4b15de7a2e993c475157125109ac5` |
| Total | 14 | **42** | | | |

Adapter config SHA-256: `d1.0` `2f28e6361f25340cb86922ff73e073cd735beb8625b61c8d7914434cc02f56d9`; both `d1.1` configs `398e207fe218f117c33a839f99508bebc0db4ccf5d8062973835c3082387e1b8` (identical files); `d1.5` `ec56b3d5e820498f5c7c7cf029b00e94e1552af89292a0dcc365306e26e18568`.

Other design fields: `evidence_label` real, `warmup_blocks` 0 (collection, not a comparison, so no warm-up exclusion is needed), `min_free_ram_gb` 2.5 (as Stage 2), `reference` `EFT_E1`, `fits_atol` null, final outputs checked by hash: `1-mosaic.fits`, `1-mosaic_area.fits`, `1-mosaic.png`.

Reference binding in the designs: `d1.1 c56.7_24.0` points at `data/results/stage1_20261011/valid/seq1/run.json` and `.../work` (the Stage 1 run, as Stage 2 used); the other three point at `refs/<instance>/run.json` and `refs/<instance>/work`.

Task rows if every run completes and verifies: 12 x 19 + 12 x 59 + 12 x 59 + 6 x 157 = 228 + 708 + 708 + 942 = 2586. Fitting data (the three non-test instances) is at most 1644 rows (228 + 708 + 708), of which two thirds come from `RandomOccupancy` runs; the final-test instance contributes at most 942 rows. This is consistent with the 1,500 to 2,500 rows assumed in STAGE3_FREEZE.md section 2, and far below the "about 10k samples" regime where the protocol cites trees as often winning. The `RandomOccupancy` conditions log the context of the chosen worker only, so with `context_source = decision` they contribute rows only for the pool actually chosen. The learning-curve check reports whether volume is limiting; TabM is already excluded by the entry rule (20,000 rows needed, section 2 of the freeze).

`run_timeout_s` check against the sequential references (rule: at least twice the slowest plausible narrow-subset makespan): `d1.0` 1800 s against 489.7 s; `d1.1` 2400 s against 1083.7 s (c10.7) and 1459.4 s (primary); `d1.5` 7200 s against 1896.4 s. The Stage 2 worst case on the primary was `B0_E_only` at 811.8 s mean (`stage2_gate.json`, `makespan_by_condition.B0_E_only.mean_s`), well inside 2400 s. The `d1.5` worst case is unmeasured.

Time budget (arithmetic from Stage 2 evidence; the Stage 3 conditions were not measured):

- Stage 2: 42 runs in 15 314 s = 364.6 s per run against a mean makespan of 362.3 s over the 14 conditions, so about 2.3 s of overhead per run (rounded up to 2.5 s below). These two figures come from the v1 version of this plan and were not re-derived here; the makespan means per condition are in `stage2_gate.json`.
- Planning makespans for `d1.1` (*assumption*): `EFT_E1` 275.5 s (`stage2_gate.json`, `makespan_by_condition.EFT_E1.mean_s`), each `RandomOccupancy` 416.5 s (`random.mean_s`, the nearest policy in kind). One block is about 275.5 + 2 x 416.5 + 3 x 2.5 = 1116 s, so 4 blocks take 74 min per `d1.1` instance, 149 min for both.
- `d1.0`: scale by sequential reference time (489.7 s against about 1459 s for `d1.1`, factor 0.334): about 0.334 x 1108.5 + 7.5 = 378 s per block, 4 blocks 25 min.
- `d1.5`: scale by task count (157 / 59 = 2.66, *assumption*): about 2.66 x 1108.5 + 7.5 = 2956 s per block, 2 blocks 98 min. Scaling by sequential reference time instead (1896.4 / 1459.4 = 1.30) would give a much shorter figure; the true value is unknown.
- Total about 272 min = 4.5 h of dedicated machine time, planning figure about 5 h. Narrow-subset runs of `RandomOccupancy_s3` can take longer than the planning figure.

## 5. What must exist before the first session

1. Reference outputs: `data/results/stage3_20261012/refs/<instance>/run.json` (status ok, three `final_outputs` hashes) and `.../work` for `d1.0`, `d1.1 c10.7_41.3` and `d1.5`, and the Stage 1 `valid/seq1` run for the primary. **All four exist and are status ok** (read 2026-10-12). A run whose reference is missing is recorded unverified (`verify raised ...`) and is excluded from the dataset.
2. A clean commit (or the dirty flag stated in the report), the machine hygiene checklist of `REPRODUCE.md` section 11, and the runner's memory preflight. The static profile (stamp `20261012T092355`) predates every Stage 3 session, as `dataset/build.py` requires.
3. The designs written by `python scripts/make_stage3_designs.py` (default output `designs_v2`; exclusive create; it refuses to overwrite) and their hashes recorded (section 4).

Observed state when this section was last edited: a session directory `data/results/stage3_20261012/sessions/20261012T153253` already exists (first run `b0000_00_RandomOccupancy_s3`, `d1.0` work files). Whether that session completed was not checked here; `session.json` is the authority.

## 6. Sessions, order and commands

One session per design, run one after another in this order (cheapest first, so a plumbing fault costs least): `d1.0`, `d1.1 c56.7_24.0`, `d1.1 c10.7_41.3`, `d1.5`.

```
set CAO_MONTAGE_ADAPTER_CONFIG=data\results\stage3_20261012\designs_v2\adapter_config_<instance>.json
.venv\Scripts\python.exe scripts\run_experiment.py --design data\results\stage3_20261012\designs_v2\design_<instance>.json ^
    --out data\results\stage3_20261012\sessions --adapter caosched.experiment.montage_adapter:factory
```

The `d1.5` session uses `--out data\results\stage3_20261012\sessions_test` instead, so the fitting dataset can be built from `sessions` without it.

## 7. Dataset construction and use

```
.venv\Scripts\python.exe scripts\build_dataset.py --events data\results\stage3_20261012\sessions ^
    --profiles data\results\stage2_20261012\profile_montage --out data\results\stage3_20261012\dataset
```

`context_source` is `decision` (the default). Verified facts from the shake-out on the Stage 2 logs (section 8): the builder keeps only runs whose `run_manifest.json` says status ok and verification passed, and reports exclusions with reasons in `manifest.json`. Folds are defined in STAGE3_FREEZE.md; `evaluate_models.py` then runs with `split = {"policy": "instance", "leave_one_out": true}` on the fitting dataset and, once, with `{"policy": "instance", "test": ["d1.5_dss2b_c56.7_24.0"]}` on a dataset that contains both. The model list and the margin are fixed in the freeze (candidates E1, E3, E1+rc, Ridge, CatBoost, MLP; TabM out; margin 2.0% of makespan); hyper-parameters stay in the freeze config file.

## 8. Pipeline shake-out that preceded this plan

Run on the 42 real Stage 2 logs only (`data/results/stage3_20261012/shakeout_dataset/`, `shakeout_eval/`); it tested plumbing, not accuracy, and no accuracy claim is made.

- Builder: the logs were first excluded as "unrecognised source directory" because the session layout `<stamp>/runs/<run>/<run>.jsonl` was not a known source kind; fixed (kind `session`), with a regression test. `preflight.jsonl` is correctly not treated as a run log.
- Builder: runs whose output did not verify are now excluded (they were not before); regression test added.
- `scripts/build_dataset.py` takes `--profiles` and `--out`.
- Decision contexts exist only for the `EFT_*`, `EFT_*_rank` (13 candidates each) and `HEFT_E1` / `PEFT_E1` (the chosen worker only, no cost model) policies; B0 to B5 and `random` log none, so `context_source = decision` drops them, as designed. `RandomOccupancy` logs the chosen worker's context.
- Splits that are impossible on one instance, one session and one size: `instance`, `session`, `size` (empty train side), and `occupancy` without `allow_straddle` (runs straddle). `time` and `occupancy` with `allow_straddle` run.

## 9. Limits stated in advance

Single machine and hardware configuration; patched Windows Montage build; four instances, three of them sharing a sky centre; data volume of the order of thousands of rows (at most 1644 fitting rows if every run verifies); two `RandomOccupancy` settings only after the v2 reduction; `RandomOccupancy` makespans and their range unmeasured; `d1.5` run times unmeasured under any policy; the machine is not idle (WSL VM, browser, editor), so repeated collection under identical conditions is not guaranteed; collection runs at one worker topology; the test instance is a larger instance of a sky region also used for training; no claim about scheduling value follows from this collection.
