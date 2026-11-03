# Revival protocol: resource-state-aware scheduling under dynamic contention

Written 2026-10-25 on branch `revival/resource-state-aware`, BEFORE any run of the new workload. Later parts (section 6 onwards) are
added before the run they govern and committed first; nothing written here is edited after the run it governs. Older protocols
(`docs/research_redesign/EVALUATION_PROTOCOL*.md`) stay unchanged and authoritative for the sessions they cover.

## 1. Question

The earlier result (Study 2, sections 18 to 32): a learned, work-conserving rank policy (`PredictedRankGreedy`) beats static and naive
rules by 17% to 45% when a task's cost hides in its parameters, and is level with blind greedy (B4) when nothing is hidden or when greedy is
already near the best order. The remaining idea of the project: **besides what a task is, the state of the machine also decides where it
should run.** Question: does adding live resource state (which worker is currently slowed by foreign load, how recent runtimes deviate
from the prediction) to a work-conserving rank policy lower the makespan, relative to the best simple work-conserving rule, on a workload
where the isolated profiles become stale during the run?

Contribution tested (not claimed): low-overhead resource-state-aware cost estimation + work-conserving rank dispatch + end-to-end cost
terms, judged by an **oracle gate first**, then pre-registered paired blocks.

## 2. Workload (fixed now)

* DAG: `revival.workload.build_dyn` with the three classes of the two-factor study, [48 x (256 px, 2 repeats), 12 x (256 px, 300), 12 x
  (1024 px, 3)] = 72 chains source -> denoise -> edges -> features, in 6 groups of 12 chains with a per-group `img_aggregate` and one
  final `img_aggregate` (depth 6, 6 + 72 x 4 + 1 = 295 tasks). Existing stages, unchanged.
* Pools: CPU only (6 P workers on logical cores 0,2,...,10; 7 E workers; the CUDA worker, present in the pool, is ineligible). The
  GPU path is not part of this protocol: GPU runs are a separate, labelled study (section 9).
* Contention (`revival.contention`, started at `on_run_start` of every policy, identical for all conditions of an instance): two
  consecutive phases of 1.0 s beginning 0.2 s after the run starts; in each phase 3 of the 6 P cores (disjoint between phases, chosen
  by the instance's contention seed) are shared with 2 spinning processes. Measured (`data/results/revival_20261025/calibration_core0.json`):
  a long task on a core shared with 1 / 2 spinners runs 1.77x / 2.72x slower; a task shorter than the OS time slice (img_edges at 512 px)
  is not slowed at all. The schedule is a measurement instrument and is never visible to a deployable policy except through the
  signals of section 4.
* Instances = (chain order seed, contention seed): gate g1 = (71, 101), g2 = (72, 102); pilot p1 = (81, 111), p2 = (82, 112);
  confirmatory c1..c4 = (91..94, 121..124). All differ from the orders and schedules used to train the model (two-factor study orders 11,
  22, 55, 66; no contention) and from each other.

## 3. Policies (fixed now)

Non-predictive: `B4` (blind greedy), `B4_param_first` (sort by repeats), `B4_cost_first` (sort by pixels x repeats; informed hand rule),
`B4_largest_first` (sort by size), `B0_P_only` (static). Predictive, deployable: `PRED_RANK_GREEDY` (the existing policy, unchanged),
`RSA_TASK_ONLY` (revival policy, task model only, no live state), `RSA_STATE_ONLY` (baseline size-only profile + live state),
`RSA_COMBINED` (task model + live state). Reference only: `ORACLE_STATE`. Learned models: `param_model_revival.json` (per-group
functional form chosen on the held-out two-factor pilot logs, trained on the two-factor coverage sessions; sha256 recorded in section 11) and
`blind_model_revival.json` (size is the only input). `EFT_param_model_rank` and `HEFT_param_model` (existing, early-binding / static) join
the pilot for completeness.

Oracle (`revival.oracle.ScheduleOracleRankGreedy`): the same rank order, eligibility, late binding and no-waiting rule as the deployable
policies, with (i) exact isolated task times per (task, pool) from an E5 replay table built from isolated coverage sessions of the SAME
instances, and (ii) exact knowledge of the contention schedule and of the measured slowdown per spinner count. It is an upper-bound
reference (it uses the future), never a candidate.

## 4. Live state available to a deployable policy (fixed now)

Only information available before the dispatch of the task being scheduled: occupancy of workers from the runtime state; completed-task
residuals (actual / predicted kernel time, class-aware and per worker); per-core utilisation of an idle worker's logical core
(`psutil.cpu_percent(percpu=True)` since the previous sample, minus the worker's own busy share); host free RAM. GPU busy fraction and
free VRAM are read through NVML only if `pynvml` is installed; it is not installed on the development machine, so the signal is
reported unavailable. No signal reads a field of the task being scheduled that is only known after it ran (unit-tested).

## 5. Oracle gate (decision rule fixed now)

1. Isolated coverage: `B0_P_only` and `B0_E_only` on the gate instances without contention (9 blocks, block 0 warm-up); E5 table from
   those logs only (`scripts/revival_oracle_rows.py` checks that every task x eligible pool is covered).
2. Gate session: conditions B4, B4_param_first, B4_cost_first, B4_largest_first, B0_P_only, PRED_RANK_GREEDY, ORACLE_STATE on instances
   g1, g2 (alternating), 13 blocks (block 0 warm-up, 12 analysed: 6 per instance), `require_ac_power`, same worker pool for all
   conditions, scheduling-cost guard 25%.
3. Let S be the non-predictive work-conserving condition (B4, B4_param_first, B4_cost_first, B4_largest_first) with the lowest mean makespan
   (chosen after seeing the gate data, which is conservative towards the baseline). **Headroom** = paired mean percentage by which S is
   slower than ORACLE_STATE (`analyze_experiment.py --reference ORACLE_STATE`, paired log-ratio bootstrap over blocks, seed 0).
4. **Pass** iff the headroom point estimate is at least 5% and the lower end of its 95% interval is above 0. Otherwise the result is reported as
   "insufficient headroom for this workload"; no predictor is tuned for it, no variant of the workload is invented to change the verdict,
   and sections 6 and 10 are not executed.
5. Gate data are exploratory and are never pooled with pilot or confirmatory data.

## 6. If the gate passes: pilot and confirmatory study (to be completed before they run)

Pilot (instances p1, p2, all conditions of section 3 incl. HEFT and EFT-rank, 13 blocks) is exploratory: it sets the number of blocks
for the confirmatory session from the paired standard deviation of `RSA_COMBINED` against the best simple rule (rule of the Study 2
protocol, section 4: blocks needed for a 95% interval half-width of 2.5%, rounded up to an even number). Then section 7 (predictions, analyses,
exclusions, design hash) is committed BEFORE the confirmatory session (instances c1..c4, conditions B4, B4_param_first, B4_cost_first,
B4_largest_first, B0_P_only, PRED_RANK_GREEDY, RSA_TASK_ONLY, RSA_STATE_ONLY, RSA_COMBINED; no oracle). Primary metric: makespan. Holm over the
contrasts against the best simple rule S* (named in section 10 from the pilot). Equivalence margin for the no-harm control: +-2%.

## 7. No-harm control (fixed now)

The uniform control is the Study 2 uniform batch (no hidden cost, no contention; sessions `uniform_nh_*` of Study 2, section 29). The revival
policy must stay inside +-2% of B4 there. If the gate passes, the control is rerun with the revival policies in the confirmatory campaign; if the gate
fails, no rerun is needed because the policy is not promoted.

## 8. Success targets (targets, not results)

Oracle headroom >= 5% (the gate above); `RSA_COMBINED` at least 5% faster than S* on held-out instances with the pre-registered interval supporting it;
no-harm within +-2%; scheduling overhead below 5% of the makespan (hard failure at 25%); no eligibility or output errors; manifests and analyses
reproduce. A null result is reported with its cause: insufficient oracle headroom, no incremental information, poor policy use,
telemetry or decision cost, transfer/setup cost, or statistical uncertainty.

## 9. Not covered here (stated in advance)

Real GPU contention (the machine has an RTX 3050; the CUDA worker is idle in this protocol; `pynvml` is not installed, so GPU utilisation
and VRAM telemetry are unavailable and are not guessed); remote offloading (the loopback shim is an emulation; a separately labelled sweep
of link delay and bandwidth would use the existing `FileTransferModel` term, which the revival cost model already accepts, but is not run
under this protocol); a Raspberry Pi (no hardware).

## 11. Frozen files (hashes written before the coverage session)

| File | sha256 |
|---|---|
| `designs/design_revival_cover.json` (isolated coverage for the oracle table, 9 blocks, seed 20262501) | `70672217d3832f9482a8814302002529a079e8af2d227b5f9df297e7e9693a52` |
| `param_model_revival.json` (trained on the two-factor coverage sessions, form per group chosen on the two-factor pilot logs; report set: two-factor confirmatory logs) | `1cad709736c944d04ac832a70b3c868ec71e58552b0f06463e1338e118459fdf` |
| `blind_model_revival.json` (size is the only input) | `a29c8f18fed0435e261ec7b916497119c4b99038830d4c90f29c198ba39a1c62` |
| `calibration_core0.json` (measured spinner slowdown, sampling cost) | `3389c55d84ae430d14b78fe4948ff2cd88e2cdaf52306b365d1533571a11b3e3` |

Exploratory model comparison (`model_eval.json`, fitted on the coverage sessions, chosen on the pilot logs, reported on the confirmatory logs of the
two-factor study, so no leakage): for `img_denoise` the power-law form reduces the median absolute percentage error from 3.4 (P) / 1.0 (E) to 0.19 / 0.02
and the mean absolute error from 32 ms to 16 ms (P) on the report set; the additive form with a class-aware correction reaches 0.19 / 0.03 in median error
but not in absolute error. Whether a better absolute prediction changes any scheduling result is a separate, measured question (pilot).

### 11.1 Gate files (written after the coverage session, before the gate session)

Coverage session `cover_sessions/20261025T085407`: complete, 9 of 9 blocks, 18 runs, all status ok; oracle table `oracle_rows_gate.json` (4720 rows, every
task x eligible pool of both gate instances covered), sha256 `696b9ec30b68dbbdd357187ab9bc1e985670327b10f8385d49836def26cc1b7a`. Gate design `designs/design_revival_gate.json` (13 blocks, seed 20262502, 7
conditions, instances g1 and g2), sha256 `f6661cb6acf04cc75f5add003bc1b4df74b2a3630ca02c86c76830305f0eba3c`.

## 12. Gate result and the engineering check that follows (section written after the gate, before the check)

**Gate: FAILED** (`analysis_gate_ref_B4`, `analysis_gate_ref_ORACLE_STATE`; session `gate_sessions/20261025T085649`, 13 of 13 blocks, 12 analysed). S = `B4`
(lowest mean makespan among the non-predictive work-conserving rules: B4 2.712 s, B4_param_first 2.726 s, B4_cost_first 2.759 s); `ORACLE_STATE` 2.748 s.
Headroom of S over the oracle: **-1.24%** (interval -3.0% to +0.5%): the schedule-aware oracle is not faster than blind greedy, the upper end of the
interval is 10 times below the 5% the gate requires. Result: **insufficient headroom for this workload.** Per section 5.4 no pilot or
confirmatory session of this workload is run and no predictor is tuned for it. (Verification that the contention was real: heavy denoise tasks that
ran entirely inside a hot window took a median 0.815 s against 0.532 s outside, 1.53x, n = 11 and 235.)

**Engineering check (exploratory, not part of any claim).** The revival policies are new code; independent of the gate they must (a) run on the real
worker pool including the CUDA worker without eligibility or correctness errors, (b) decide fast, (c) do no harm where nothing is hidden. The Study 2
uniform batch with the CUDA worker (no hidden cost, no contention) is rerun with the revival policies: design `designs/design_revival_uniform.json`
sha256 `3c7f944d59f89e04277eb0b674777add56ebda2d47072d1b955b8e6679b1b562` (31 blocks, seed 20262503; conditions B0_P_only, B4_gpu (reference), PRED_RANK_GREEDY_gpu, RSA_TASK_ONLY_gpu, RSA_STATE_ONLY_gpu,
RSA_COMBINED_gpu). Pre-stated expectations: (P1) every revival policy is equivalent to B4_gpu within +-2% (whole 95% interval inside); (P2) B0_P_only is
slower than B4_gpu by more than 20% (Study 2 measured 26%); (P3) scheduling time below 5% of the makespan for every policy; (P4) no output mismatch,
no eligibility violation; (P5) fallback reasons are logged for every decision that did not follow the cost model. An outcome outside P1 is reported as
such; the policy is not promoted either way, because the gate failed.

### 12.1 Result of the engineering check v1 and amendment A1 (written before the rerun)

Check v1 (`uniform_sessions/20261025T...`, `analysis_uniform_ref_B4_gpu`; 31 of 31 blocks, 30 analysed, 186 runs, all ok and output verified). Makespan against B4_gpu:
B0_P_only +36.3% (35.0 to 37.6), PRED_RANK_GREEDY_gpu +0.1% (-0.8 to +1.2), **RSA_COMBINED_gpu +2.3% (+1.2 to +3.6), RSA_STATE_ONLY_gpu +2.6% (+1.5 to +3.9),
RSA_TASK_ONLY_gpu +2.2% (+0.8 to +4.0)**. P1 (equivalence within +-2%) FAILS for all three revival policies, P2 holds, P3 holds (scheduling time 1.9% of the
makespan), P4 holds. RSA_TASK_ONLY (no live state) is as slow as RSA_COMBINED, so the harm is not caused by the live-state signals. Measured per-decision time
(coordinator clock): RSA 119 to 132 us, PRED_RANK_GREEDY 63 us, B4 32 us; the first version logged the full snapshot and cost components with every
decision (the coordinator writes the record before it submits the task) and built them on the hot path. Every decision of the check was recorded as
`gain_below_cost` (7967 of 7967): at a saturated pool one worker is idle at a time, so the placement choice is forced and only the order matters; the
reason is logged also when the cost model's choice equals B4's choice, which is not a fallback in effect.

**Amendment A1 (code, no change of rule):** (a) the hot path computes plain float totals (`_total`), the component breakdown is built only for diagnostics;
(b) the logged record is minimal by default (schema, chosen worker, fallback reason, predicted total, idle count, slowdown of the chosen worker); the full snapshot,
cost components, B4's choice and the runner-up are opt-in (`diagnostics=True`); (c) the state snapshot is taken lazily, once per dispatch pass and only when a decision has a real choice (two or more eligible idle workers); with one idle worker the
placement is forced and nothing but the base prediction (needed for the later residual) is computed; (d) decisions are unchanged (unit tests: hot-path total equals the
component total; the task-only ablation decides like PredictedRankGreedy). Measured afterwards (microbenchmark, not part of the claims): writing the full and the minimal
decision record costs 13 us and 9 us per event, so the logging size was NOT the cause of the harm; the per-pass snapshot (a utilisation sample, history scan and three
mapping proxies on every completion, about 100 us on the E-core the coordinator is pinned to) was, which is why (c) is the change that matters.
Rerun: same workload and conditions, new design `designs/design_revival_uniform2.json` sha256 `840b674c0698da7ce43d36cfdf0220a3f06d28167df9dc8f516f6613e3820e71` (31 blocks, seed 20262504), same predictions P1 to P5.
v1 is kept as evidence; v2 is not pooled with it. If P1 still fails the harm is reported and investigated, the policy is not promoted either way.
