# Phase B — workload-intensity sweep analysis (2026-10-04)

Status: **Phase B EXECUTED and VERIFIED (data integrity); read-only audit
of the statistics EXECUTED and VERIFIED 2026-10-04 (3 minor defects
documented below; no result changes). Phase C (final integrity audit and
test suite) EXECUTED and VERIFIED 2026-10-04 -- see PROJECT_STATUS.md,
"Phase C"; full suite 166 passed.**

Labels: IMPLEMENTED = code exists; EXECUTED = it was run on the recorded
data; VERIFIED = the result was independently checked.

## Scope and inputs

Primary analysis uses ONLY the four accepted Phase A sessions (design fixed
before execution; see PROJECT_STATUS.md, "Application workload-intensity
sweep"):

| k (denoise iterations) | session | paired repeats |
|---|---|---|
| 1 | appdemo_20261004T185921 | 10 |
| 4 | appdemo_20261003T213900 | 10 |
| 16 | appdemo_20261004T185801 | 10 |
| 64 | appdemo_20261003T214453 | 10 |

Excluded from all results: appdemo_20261003T211356 (verification only);
appdemo_20261003T212905, appdemo_20261003T223138, appdemo_20261003T231850
(interrupted).

Setup, as recorded: 1024x1024 image, grid 4 (68 tasks, critical path 7
stages), seed 11, `lan_1g` link **shim** (0.2 ms latency, 125 MB/s), remote
worker = a **local node process on logical processor 11 (an E core of the same
laptop)**. This is NOT a Raspberry Pi or NVIDIA T4 measurement.

## Outputs (all new; nothing overwritten)

`data/results/phaseB_appdemo_sweep_20261004/`

| file | content |
|---|---|
| existing_analyzer_analysis.json, existing_analyzer_stdout.txt | `scripts/analyze_app_demo.py`, run unchanged |
| supplementary_summary.json, supplementary_stdout.txt | `scripts/analyze_app_sweep.py` (new, Phase B) |
| per_run.csv | one row per demo run (80) |
| paired.csv | one row per paired repeat (40) |
| stage_breakdown_stdout.txt | ad-hoc read-only query: per-stage kernel sums, critical path, run-order effect |
| evidence_sha256_before_analysis.json | SHA-256 of 12,512 evidence files taken before the analysis |

Reproduce: `PYTHONPATH=src python scripts/analyze_app_demo.py <4 sessions> --out <name>` and
`PYTHONPATH=src python scripts/analyze_app_sweep.py --out-dir data/results/<new dir>`.

## Analyzer check (before use)

* `scripts/analyze_app_demo.py` — EXECUTED. It handles these sessions correctly
  (no schema mismatch), but: (a) its per-stage kernel/transfer/service medians
  include the 6 pool-pinned `profile_*` runs of each session, not only the 20
  B4/EFT runs (e.g. k = 1 img_denoise transfer n = 54 task observations); (b) it
  gives medians/min/max only; (c) its only CI is a percentile bootstrap over
  the 10 paired makespan log-ratios. Its output is kept as-is for reference;
  where its stage numbers differ from the tables below, that is the
  profile-run mixing.
* `scripts/analyze_app_sweep.py` — IMPLEMENTED and EXECUTED. It is a
  supplementary analysis that does not change the experiment, the data or the
  schedulers. It checks each session against the pre-registered design (and
  writes nothing if one does not match), uses demo runs only, treats the run
  as the unit (task times are averaged within a run first), and reports the
  mean, SD and 95% CI. Per-policy CIs are Student t intervals over n = 10
  runs. B4 vs EFT CIs are paired t intervals over the n = 10 per-repeat
  differences (EFT − B4). As a cross-check, the existing log-ratio bootstrap
  (`paired_effect`, 10,000 resamples, seed 0) is reported alongside.

## Verification — VERIFIED

* Design check passed for all 4 sessions: k, size, grid, profile runs,
  node core, link profile, repeats, order seed, memory guard, seed 11,
  `lan_1g`, policies; 20 runs; no stop reason; 10 complete B4/EFT pairs.
* Per demo run (80/80): the event log agrees with runs.csv (scheduler,
  completed, makespan, 68/68 tasks, P/E/R counts); the final package
  re-verified **exact** against a freshly computed single-process reference;
  its SHA-256 equals runs.csv.
* Existing analyzer: final outputs exact in 26/26 logs per session (demo +
  profile); every remote task's payload bytes = on-disk input + output
  artifact sizes and output bit-identical to the reference task result:
  184/184 (k=1), 185/185 (k=4), 198/198 (k=16), 180/180 (k=64).
* Evidence unchanged: 12,512 files (data/events, data/results,
  data/profiles, data/artifacts/appdemo_*) hashed before, re-hashed after:
  12,512 unchanged, 0 changed, 0 missing, 0 added outside the new directory.
* Verification failures: **none**.

## Per-k results (demo runs; mean ± SD [95% t-CI], n = 10 runs per policy)

### Makespan, total kernel time, scheduler latency, placement

| k | policy | makespan ms | sum of kernel times / run ms | decision latency µs (per dispatch, run mean) | scheduling / run ms | tasks per run P / E / R |
|---|---|---|---|---|---|---|
| 1 | B4 | 1015.9 ± 52.8 [978.1, 1053.6] | 807.0 ± 41.7 [777.2, 836.8] | 14.1 ± 4.2 [11.1, 17.1] | 1.49 | 18.0 / 46.1 / 3.9 |
| 1 | EFT_E1_rc | 1073.8 ± 21.9 [1058.1, 1089.4] | 836.3 ± 25.0 [818.5, 854.2] | 99.9 ± 4.7 [96.5, 103.2] | 6.88 | 18.2 / 48.9 / 0.9 |
| 4 | B4 | 838.2 ± 46.5 [804.9, 871.5] | 800.6 ± 46.4 [767.4, 833.8] | 9.5 ± 0.4 [9.2, 9.8] | 1.11 | 17.0 / 47.0 / 4.0 |
| 4 | EFT_E1_rc | 918.7 ± 143.4 [816.1, 1021.3] | 834.5 ± 71.6 [783.3, 885.6] | 84.8 ± 5.2 [81.1, 88.5] | 5.83 | 16.2 / 50.9 / 0.9 |
| 16 | B4 | 1137.7 ± 77.9 [1082.0, 1193.4] | 1613.0 ± 107.0 [1536.4, 1689.5] | 14.1 ± 4.0 [11.2, 16.9] | 1.46 | 19.3 / 44.8 / 3.9 |
| 16 | EFT_E1_rc | 1206.6 ± 46.5 [1173.4, 1239.8] | 1654.7 ± 40.5 [1625.7, 1683.6] | 107.3 ± 12.8 [98.2, 116.4] | 7.38 | 21.2 / 44.5 / 2.3 |
| 64 | B4 | 1146.3 ± 39.9 [1117.7, 1174.8] | 3509.4 ± 65.8 [3462.3, 3556.5] | 12.4 ± 4.8 [9.0, 15.9] | 1.02 | 17.2 / 48.4 / 2.4 |
| 64 | EFT_E1_rc | 1201.1 ± 52.8 [1163.3, 1238.8] | 3442.6 ± 70.4 [3392.2, 3492.9] | 81.9 ± 6.9 [76.9, 86.8] | 5.63 | 28.0 / 38.0 / 2.0 |

Remote placements of the two eligible stages (totals over 10 runs):

| k | B4 denoise@R | B4 edges@R | EFT denoise@R | EFT edges@R | EFT decisions with R predicted faster |
|---|---|---|---|---|---|
| 1 | 22 | 17 | 0 | 9 | 9 / 320 |
| 4 | 20 | 20 | 4 | 5 | 9 / 320 |
| 16 | 20 | 19 | 23 | 0 | 23 / 320 |
| 64 | 20 | 4 | 20 | 0 | 20 / 320 |

EFT placed a task remotely in exactly the decisions where its own model
predicted the remote finish to be earlier (9, 9, 23, 20) — EXECUTED,
consistent with its design. Whether those predictions were accurate is not
evaluated here.

### Computation vs transfer (img_denoise; run-level means, both policies, ms)

Local P/E = kernel on this laptop's P / E workers during the demo runs;
R = the remote-node process (an E core). `io` = artifact read + decode/encode
+ write (logged for local and remote tasks). `transfer` = remote round trip
minus node span and local write (shim delay + socket/framing).

| k | kernel P | kernel E | kernel R | transfer R (n runs) [95% CI] | E kernel / R transfer | remote path − local E (kernel+io) [95% CI] (n) | remote path − local P [95% CI] (n) |
|---|---|---|---|---|---|---|---|
| 1 | 4.66 | 3.85 | 3.75 | 7.79 (10) [6.07, 9.50] | 0.49 | +7.92 [3.04, 12.80] (10) | +4.58 [−0.30, 9.45] (10) |
| 4 | 18.87 | 11.72 | 10.98 | 6.24 (14) [5.27, 7.21] | 1.88 | +3.59 [−0.96, 8.14] (14) | −6.81 [−15.15, 1.52] (14) |
| 16 | 48.49 | 55.93 | 55.35 | 6.16 (20) [5.45, 6.86] | 9.09 | +7.05 [3.61, 10.50] (20) | +12.44 [5.73, 19.15] (20) |
| 64 | 166.08 | 183.34 | 186.14 | 4.80 (20) [4.60, 5.00] | 38.2 | +5.75 [2.37, 9.12] (20) | +19.24 [11.12, 27.35] (20) |

img_edges (unchanged by k): kernel ≈ 4–7 ms, transfer 3.9–10.1 ms; remote
path − local E = +5.6 to +10.8 ms at every k.

## B4 vs EFT_E1_rc (paired; n = 10 repeats per k; EFT − B4)

| k | makespan diff ms, mean ± SD [paired t 95% CI] | % (t on log ratio) [95% CI] | % bootstrap [95% CI] | pairs EFT slower | remote tasks/run diff [95% CI] | scheduling/run diff ms |
|---|---|---|---|---|---|---|
| 1 | +57.9 ± 66.4 [+10.4, +105.4] | +5.8 [+1.0, +10.8] | [+1.8, +10.0] | 8/10 | −3.0 [−3.5, −2.5] | +5.4 |
| 4 | +80.5 ± 121.5 [−6.4, +167.4] | +8.8 [+0.3, +17.9] | [+2.7, +17.2] | 8/10 | −3.1 [−3.7, −2.5] | +4.7 |
| 16 | +68.9 ± 75.0 [+15.2, +122.5] | +6.2 [+1.1, +11.6] | [+2.4, +11.2] | 9/10 | −1.6 [−2.2, −1.0] | +5.9 |
| 64 | +54.8 ± 74.0 [+1.8, +107.7] | +4.7 [+0.2, +9.5] | [+1.0, +8.7] | 9/10 | −0.4 [−0.8, −0.03] | +4.6 |

At k = 4 the absolute-difference CI includes 0 (one EFT run at 1315 ms);
the log-ratio CIs exclude 0. All lower bounds are close to 0: the
evidence for "EFT slower" is consistent but its size is uncertain.

## Consolidated per-k table (generated from supplementary_summary.json; mean [95% CI])

n = 10 runs per policy and 10 pairs per k. Makespan and decision-latency CIs
are Student t over runs. EFT − B4 uses a paired t over the 10 per-repeat
differences; the % column uses a paired t on log(EFT/B4); the bootstrap
column is the percentile bootstrap (10,000 resamples) over the same 10 log
ratios. The denoise kernel/transfer CIs are t intervals over run-level means:
both policies' runs are included, and for transfer only runs with ≥1 remote
denoise task count (n shown).

| k | B4 makespan ms | EFT makespan ms | EFT − B4 ms (paired t) | EFT vs B4 % (paired t on log ratio) | % bootstrap CI | remote tasks B4 / EFT (total; per run) | tasks/run P/E/R B4 ; EFT | denoise kernel E ms | denoise transfer R ms (n runs) | decision µs B4 / EFT |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1015.9 [978.1, 1053.6] | 1073.8 [1058.1, 1089.4] | +57.9 [+10.4, +105.4] | +5.8 [+1.0, +10.8] | [+1.8, +10.0] | 39 / 9; 3.9 / 0.9 | 18.0/46.1/3.9 ; 18.2/48.9/0.9 | 3.85 [3.76, 3.93] | 7.79 [6.07, 9.50] (10) | 14.1 [11.1, 17.1] / 99.9 [96.5, 103.2] |
| 4 | 838.2 [804.9, 871.5] | 918.7 [816.1, 1021.3] | +80.5 [-6.4, +167.4] | +8.8 [+0.3, +17.9] | [+2.7, +17.2] | 40 / 9; 4.0 / 0.9 | 17.0/47.0/4.0 ; 16.2/50.9/0.9 | 11.72 [11.03, 12.41] | 6.24 [5.27, 7.21] (14) | 9.5 [9.2, 9.8] / 84.8 [81.1, 88.5] |
| 16 | 1137.7 [1082.0, 1193.4] | 1206.6 [1173.4, 1239.8] | +68.9 [+15.2, +122.5] | +6.2 [+1.1, +11.6] | [+2.4, +11.2] | 39 / 23; 3.9 / 2.3 | 19.3/44.8/3.9 ; 21.2/44.5/2.3 | 55.93 [54.72, 57.15] | 6.16 [5.45, 6.86] (20) | 14.1 [11.2, 16.9] / 107.3 [98.2, 116.4] |
| 64 | 1146.3 [1117.7, 1174.8] | 1201.1 [1163.3, 1238.8] | +54.8 [+1.8, +107.7] | +4.7 [+0.2, +9.5] | [+1.0, +8.7] | 24 / 20; 2.4 / 2.0 | 17.2/48.4/2.4 ; 28.0/38.0/2.0 | 183.34 [181.62, 185.06] | 4.80 [4.60, 5.00] (20) | 12.4 [9.0, 15.9] / 81.9 [76.9, 86.8] |

## Answers to the research question (EXECUTED; interpretation)

1. **Computation cost** of img_denoise rose with k as designed (E kernel
   3.9 → 11.7 → 55.9 → 183 ms; sum over 16 tiles 64 → 2,887 ms per run).
2. **Transfer cost** stayed roughly flat (4.8–7.8 ms per denoise task) —
   bytes moved do not depend on k — so the E-kernel / transfer ratio grew
   from 0.49 (transfer dominates) to 38 (compute dominates).
3. **Per-task break-even was not reached.** The remote path was never
   cheaper than running the same task on a local E worker: +3.6 to +7.9 ms
   per task at every k (CI excludes 0 at k = 1, 16, 64). The relative
   overhead fell from ≈29% (k = 1) to ≈3% (k = 64) of the local E
   kernel+io time. This is expected: the "remote" node runs on an E core of
   the same CPU, so offloading can only add capacity (an 11th worker), never
   faster compute.
4. **Placement:** B4 used the remote worker greedily (≈4 tasks/run, 2.4 at
   k = 64). EFT_E1_rc used it rarely while transfer dominated (0.9 tasks/run
   at k = 1, 4, mostly edges) and shifted to denoise as compute grew (2.3 at
   k = 16, 2.0 at k = 64; 0 edges). At k = 64 EFT also moved img_edges from
   E to P (85 vs 22 placements in B4).
5. **Policy performance:** EFT_E1_rc had a longer makespan than B4 at every
   k (+4.7% to +8.8%; see table). Its scheduling overhead (+4.6 to
   +5.9 ms/run, ≈80–100 µs per decision vs ≈10–14 µs) can account for at most
   ≈10% of that gap. The cause of the remainder is not established by these
   data.
6. **Offloading pay-off regime: NOT established.** The design has no
   local-only (no-remote) condition, so the application-level benefit of
   offloading cannot be measured directly. B4 (more remote) beat EFT (less
   remote), but the two policies also differ in every other placement, so
   this is not evidence that remote use caused the gain.
7. **Makespan barely responded to denoise intensity at k ≥ 16** (B4
   1138 → 1146 ms while summed kernel time rose 1,613 → 3,509 ms). The
   single img_source task (≈440–550 ms/run, serial) and img_package
   dominate the 7-stage critical path; denoise is spread over 16 parallel
   tiles. Descriptive only — cross-session.

## Limitations

* **Not physical hardware.** Remote = local process on LP11 behind a
  configurable `lan_1g` shim. No Raspberry Pi / T4 result is implied.
* **Cross-k comparisons are confounded.** Each k is a separate session
  (k = 4, 64 on 2026-10-03; k = 1, 16 on 2026-10-04). Example of drift: B4
  makespan k = 4 (838 ms) < k = 1 (1016 ms) despite more work, and
  img_source alone differed (447 vs 540 ms per run). No cross-k difference
  is attributed to workload intensity alone; no cross-k CIs are given.
* **Memory pressure differed between sessions** (free RAM logged per run in
  runs.csv): k = 4 ran at 0.50–0.68 GiB (at the 0.5 GiB guard), k = 64 at
  0.78–0.85 GiB, k = 1 at 2.05–2.20 GiB, k = 16 at 2.08–2.16 GiB. A further
  cross-k confound.
* **Run order is unbalanced and identical across k.** Order seed 0 (as
  pre-registered) gave B4 first in 8/10 pairs at every k. The second run of
  a pair was slower on average (+32 to +53 ms by position), so EFT's
  penalty is partly confounded with position. Exploratory, post-hoc: in the
  EFT-first pairs (n = 2 per k, 8 total) EFT was still slower (mean +34 to
  +70 ms per k), suggesting the effect is not only an order artifact; with
  n = 8 this is not conclusive.
* n = 10 pairs per k; percentile-bootstrap CIs at n = 10 tend to be narrow,
  which is why the paired t interval is the primary CI here.
* Local P-core kernel times in the demo runs exceed E at k = 1 and 4
  (SMT siblings co-running), unlike the pinned profile runs; reported as
  logged.
* The test suite was NOT re-run in Phase B (last recorded: 166 passed,
  before the sweep).

## Read-only audit of Phase B (2026-10-04, before Phase C) — VERIFIED

An independent script (numpy only; it did not reuse the analyzer's
statistics code) recomputed the statistics from the RAW
`appdemo_*_runs.csv` files and compared them with
`supplementary_summary.json`. Nothing was written to the evidence or to
earlier outputs.

* Completeness: 4/4 k levels; each has 10 complete pairs keyed by `repeat`
  (B4 and EFT from the same repeat), 20/20 runs passing all three run-level
  checks.
* Pairing: EFT − B4 differences are formed within the same `repeat`. The
  mean, SD and paired t-CI match the recomputation (n = 10, df = 9,
  t = 2.262) at all 4 k. Per-policy means and t-CIs (n = 10 runs) match.
  Remote-task totals match runs.csv.
* t quantiles: the table (df 1–30) agrees with independently integrated
  Student-t quantiles to ≤ 0.0005. The only lookup is
  `T975.get(df, 1.960)` (line 59); no direct `T975[...]` indexing remains.
  Synthetic tests of `summ()` with n = 1, 2, 10, 31, 32, 50 and 320, empty
  input and `None` values: no exception, and mean/SD/CI equal numpy.
  Above df 30 the fallback uses z = 1.960 (true t: 2.040 at df 31), but no
  primary CI uses it: every reported CI has n ≤ 20.
* Units: every per-policy stage statistic has n ≤ 10 (runs) and every
  transfer-vs-compute statistic has n ≤ 20 (runs). The EFT predicted-gap
  summary (task level, n = 320) carries no CI.
* Evidence: 12,512 files re-hashed, all equal to
  `evidence_sha256_before_analysis.json` (0 changed, 0 missing, 0 added).
* Documents: every per-k makespan mean ± SD [CI], paired difference and
  % [CI] quoted in this file and in PROJECT_STATUS.md matches the JSON.

Defects found (minor; outputs NOT regenerated, script NOT changed):

1. **Rounding before back-transform.** `makespan_pct_t` exponentiates the
   log-ratio mean and CI after `summ()` has rounded them to 4 decimals.
   Maximum deviation from exact: 0.0056 percentage points. Exact values:
   k=1 +5.81 [+1.00, +10.85]; k=4 +8.77 [+0.32, +17.93];
   k=16 +6.23 [+1.08, +11.64]; k=64 +4.75 [+0.23, +9.47]. No value changes
   at the 1-decimal precision reported here.
2. **Task-level CIs in a reference block.** In
   `profile_runs_reference_task_level`, 56 entries carry t-CIs computed over
   task-level observations (e.g. n = 32 tasks from 2 profile runs). These
   treat tasks as independent and are **not valid as inferential CIs**. They
   are not used anywhere in this report; only the n and means are
   descriptive.
3. **Runs within a pair counted separately.** The transfer-vs-compute
   intervals (n ≤ 20) pool B4 and EFT runs, so the two runs of a pair are
   counted as separate observations although they share block conditions.
   Treat these CIs as approximate.

Pairing did not always narrow the interval. The within-pair correlation of
B4 and EFT makespan was −0.50, +0.60, +0.36 and −0.26 (k = 1, 4, 16, 64). At
k = 1 and 64 the paired half-width (47.5 and 53.0 ms) is wider than an
unpaired Welch-style one (40.9 and 47.3 ms). The paired interval is still the
correct one for this design, and it is the one reported.

## Confounds — explicit statement

* **Fixed run order.** Order seed 0 at every k produced the identical
  shuffle: B4 first in 8/10 pairs at every k. The second run of a pair was
  slower on average (position 1 vs 0: +32, +53, +47 and +41 ms for k = 1, 4,
  16, 64). Because EFT was usually second, part of its measured penalty may
  be position. In the 8 EFT-first pairs (2 per k), EFT was still slower
  (+64, +70, +56, +34 ms means). That is supportive but not conclusive.
* **Different RAM conditions.** Free RAM per run was 2.05–2.20 GiB (k = 1),
  0.50–0.68 GiB (k = 4, at the 0.5 GiB guard), 2.08–2.16 GiB (k = 16) and
  0.78–0.85 GiB (k = 64).
* **Separate sessions.** k = 4 and 64 were run on 2026-10-03, k = 1 and 16 on
  2026-10-04, with no interleaving. Thermal state, background load and
  memory pressure all vary with the session, which is why k = 4 (838 ms)
  can be faster than k = 1 (1016 ms) for B4. No cross-k difference is
  attributed to workload intensity alone.
* **Not physical hardware.** The "remote" worker is a node process on
  logical processor 11 (an E core of the same i5-1235U) behind a software
  `lan_1g` shim. Nothing here measures or validates a Raspberry Pi or an
  NVIDIA T4.

## Not done (by instruction)

Phase C (integrity audit, final testing), new experiments, scheduler
changes, Raspberry Pi / T4 integration — NOT EXECUTED.
