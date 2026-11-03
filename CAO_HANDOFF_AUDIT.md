# CAO handoff audit (2026-10-26, evening before the faculty review)

Scope: read-only audit. No source, protocol, configuration, result or Git history was changed, no benchmark or test suite was run. Checks done: file reads, reading CSV/JSON analysis outputs, one dry load of a design copy written to a scratch folder outside the project (it loads and plans 11 blocks), `run_experiment.py --help`. Labels: VERIFIED = I read it in a raw or analysis file; DOC-ONLY = taken from a project document, raw data not re-opened; NOT FOUND / NOT VERIFIED / NOT REPRODUCIBLE FROM AVAILABLE ARTIFACTS as stated.

## 1. Executive verdict

- **Strongest verified result:** on the hidden-cost workload, `PRED_RANK_GREEDY` has a shorter real makespan than blind greedy B4. 6 P + 7 E workers: **-20.39%** (95% interval -21.24 to -19.26, 30 paired blocks, outputs verified). 2 P + 7 E: **-21.10%** (-21.47 to -20.73, 20 blocks). Both numbers match the saved analysis files exactly (`effects.csv`).
- **Important qualifier, VERIFIED:** the informed hand rule `B4_param_first` (sort chains by the hidden parameter, no predictor at all) gets **-21.61%** in the same session. The learned policy is 1.5% behind it (not resolved) on 6P and level on 2P. So the win comes from longest-first ordering; the learned model supplies the knowledge a person would otherwise hard-code. It does not beat that rule.
- **What does not work:** no consistent edge over B4 on the uniform batch (+0.45%, equivalent), on the two-factor workload (+0.95%, interval -0.90 to +2.84), or on the contended mixed DAG (best policy about 2% ahead of B4, gate needed 5%). Resource-state-aware and GPU-contention directions produced no end-to-end gain.
- **Montage:** valid null result (EFT 1.6% slower than static P-only), tag `baseline-null-result`.
- **Not demonstrable at all:** Raspberry Pi, real network, GPU-contention scheduling benefit, Montage scheduling gain.

## 2. Current implementation

- Branch `revival/resource-state-aware`, HEAD `9d8ea22` ("PROJECT_BACKBONE.md: full chronological record..."). Other refs: `study2/affinity` (tip `ceae094`), `redesign/montage`, `main`, tag `baseline-null-result`. 71 commits on this branch.
- Working tree: the only modified tracked file is `data/results/study2_20261024/progress.txt`; about 70 untracked items (analysis folders, session folders, `PROJECT_MASTER_DOCUMENTATION.md`, `STUDY_MATERIAL*.md`). `PROJECT_BACKBONE_CURRENT_STATUS.md` is **NOT FOUND**; the equivalent is `PROJECT_BACKBONE.md` in the root.
- Hidden-cost runs were made at commit `ae5395fef8f7439cacb238e0fd06703cdb77ec20` (an ancestor of HEAD) with the tree **dirty** (`git_dirty: true` in every run manifest). What was dirty is **NOT VERIFIED**; the recorded source hash is `f27b56f3...`. The same hash covers the 6P hidden-cost, 2P hidden-cost and uniform no-harm sessions.
- Active policies (VERIFIED in code, `src/caosched/study2/policies.py`, `adapter.py`): `B4` = `GreedyEligibleScheduler` (`schedulers/simple.py:148`), first idle eligible worker, priority P then E, ready queue in arrival order. `B4_param_first` = the same with the ready queue sorted by the hidden parameter. `PredictedRankGreedy` (`policies.py:95`) = ready queue sorted by predicted upward rank, placement only on an idle eligible worker, the one with the smallest predicted time. Model: `ParamModelEstimator` loaded from `data/results/study2_20261024/param_model_cover1234.json` (file exists). Workload: `build_iters` (`workload.py:74`): 64 independent chains source, denoise, edges, features plus one aggregate (257 tasks); 48 chains with 2 denoise iterations and 16 with 120; 512 px images; only the iteration count differs, so a size-keyed table cannot see the cost.

## 3. Evidence table

All rows: real hardware, this machine (i5-13500HX), makespan, paired within block, bootstrap interval, effect = change relative to the reference (negative = faster). "Code" = recorded source hash prefix; results from different hashes are never combined.

| Experiment | Workload / config | Compared | Result | Blocks | Code | Raw path (under `data/results/`) | Status |
|---|---|---|---|---|---|---|---|
| Hidden cost, 6P+7E | 48x2 + 16x120 iterations, orders e,f | PRED vs B4 | -20.39% [-21.24,-19.26] | 30 | f27b56f3 | `study2_20261024/analysis_iters_confirm2_ref_B4` | confirmatory, Holm-significant |
| same | same | hand rule vs B4 | -21.61% [-22.05,-21.17] | 30 | f27b56f3 | same | significant |
| same | same | P-only vs B4 | +1.97% [+1.34,+2.60] | 30 | f27b56f3 | same | significant |
| same | same | blind table predictor (EFT_E1_noctx) vs B4 | +39.5% [+30.4,+48.9] | 30 | f27b56f3 | same | significant |
| Hidden cost, 2P+7E | orders g,h, model retrained by one command | PRED vs B4 | -21.10% [-21.47,-20.73] | 20 | f27b56f3 | `study2_20261024/analysis_iters_p2_confirm_ref_B4` | confirmatory |
| Uniform no-harm | 64 identical chains, GPU worker | PRED vs B4_gpu | +0.45% [-0.25,+1.22] | 30 | f27b56f3 | `study2_20261024/analysis_uniform_nh_ref_B4_gpu` | equivalent within +-2% |
| Two-factor | 48x(256px,2), 12x(256px,300), 12x(1024px,3) | PRED vs B4 | +0.95% [-0.90,+2.84] | 40 | f5cc0717 | `study2_20261024/analysis_classes_confirm_ref_B4` | no gain; hand rules also tie B4 (-0.47%, +1.98%) |
| Contended mixed DAG, oracle gate | 295 tasks, spinner contention, instances g1,g2 | B4 vs schedule-aware oracle | B4 1.24% faster than oracle [-3.0,+0.5] | 12 | 054c25d8 | `revival_20261025/analysis_gate_ref_ORACLE_STATE` | gate (needs 5%) failed; no pilot run |
| Revival uniform v2 | uniform batch + CUDA worker | RSA variants vs B4_gpu | +0.70% to +0.98% | 30 | bde95ef3 | `revival_20261025/analysis_uniform2_ref_B4_gpu` | equivalent, no gain |
| Uniform, GPU on/off (older) | uniform batch | EFT without GPU vs B4_gpu | +5.14% [+4.54,+5.73] | 48 | 0464e357 | `study2_20261024/analysis_confirm_ref_B4_gpu` | GPU worker presence is worth about 5%; EFT itself ties B4 (+0.25%) |
| Montage | 59 tasks | EFT vs static P-only | +1.6% (DOC-ONLY) | - | - | `data/results/stage5_20261013` | null; raw not re-opened |
| Task-level GPU | `img_edges` 1024 px | GPU vs CPU kernel | 15.06x; `img_denoise` x8 1.36x | 15 reps | - | `stage1_20261011/gpu/gpu_spike_stdout.txt` | task level only |

Derived percentages quoted in project documents (e.g. "21.9% faster than P-only", "42.9% faster than the table predictor") are the inverse view (reference = PRED) and follow from `effects.csv` of the PRED-referenced analyses: P-only +28.08%, table predictor +75.19% (6P); +82.17% and +57.65% (2P). I recomputed 1 - 1/1.2808 = 21.9% and 1 - 1/1.7519 = 42.9%. They match.

Discrepancies found:
1. `EVALUATION_PROTOCOL_study2.md` (confirm2 paragraph) gives scheduling time per run PRED 0.094 s, B4 0.187 s. `runs.csv` of the same session gives mean decision time (`sched_overhead_total_s`) PRED 0.0147 s, B4 0.0068 s, EFT 0.0517 s, hand rule 0.0065 s. The two do not agree; I did not find what the protocol numbers measure. Use the `runs.csv` numbers (PRED decision time is 0.47% of its 3.16 s makespan, VERIFIED).
2. The same protocol paragraph names the session `20261024T235434`; the folder is `20261024T235431`. Cosmetic.
3. Only **two chain orders per configuration** exist (orders e,f at seeds 55,66; g,h at 77,88). Thirty blocks are 15 repeats of each of two random permutations, so the number of independent workload instances is 2, not 30. B4 itself differs by order (3.836 s vs 4.105 s), PRED does not (3.185 vs 3.137). The interval reflects run-to-run noise, not variation across workload instances.
4. The Study 2 report's first headline table (27.6% faster than P-only, tie with B4) is for the uniform batch at code hash 0464e357, not for the hidden-cost workload.

## 4. Root cause

Pipeline traced: workload and dependencies (`build_iters`) -> ready-task ordering (`order_ready`) -> runtime prediction (`ParamModelEstimator`) -> placement (`select_worker`) -> execution on P/E/CUDA workers -> output verification (adapter `verify`, reference hash) -> makespan (event log `run_finished`).

| Cause class | Finding | Support |
|---|---|---|
| Software defect | None found affecting the headline result. Earlier defects (E4 profile mismatch, pool-rebuild confound, state-snapshot overhead) were fixed and documented. | VERIFIED: docs, claims V6 (failed v1) |
| Inaccurate predictions | Not the limiting factor on heavy classes: within 8% of measured (DOC-ONLY, `holdout_check_classes_confirm.json` not re-opened). Light classes badly predicted (17.6 ms vs 4.1 ms), but light tasks do not decide makespan. | DOC-ONLY |
| Policy weakness | The old EFT bound tasks to busy workers (early binding) and lost about 6% to a hand rule; replaced by rank order plus idle-only placement. | DOC-ONLY (Study 2 report, Update 3) |
| Too few meaningful choices | **Leading cause of the missing gains.** Real-run dispatch log: 93.6% of 20,046 B4+GPU dispatches had exactly one eligible idle worker; only 0.8% had a GPU and a CPU worker idle. With one idle worker the placement is forced and only ordering can matter. | DOC-ONLY (`GPU_CPU_OPPORTUNITY_REPORT.md` line 67), raw logs not re-opened |
| Baseline / design | (a) B4 is a weak baseline exactly where ordering matters: it hands the next queued chain to the first idle worker with priority P then E, so heavy chains can start late or land on a slow E core (E is about 3x slower on denoise, DOC-ONLY profile table). (b) Two chain orders only. (c) Several results come from different code hashes. | VERIFIED (code, `runs.csv`, `summary.csv`) |
| Scheduling overhead | Small: PRED 14.7 ms per run (0.47% of makespan). Not the reason for any null. The earlier 2.2-2.6% harm of the revival v1 was a state snapshot per completion, fixed. | VERIFIED (`runs.csv`), DOC-ONLY for v1 |
| Missing capability | NVML/`pynvml` not installed, so there is no GPU utilisation or VRAM signal; no Pi hardware. | DOC-ONLY |

**Why the learned policy wins on hidden-cost and not elsewhere (evidence-supported):** the gain available on this machine is a longest-first ordering effect. The hidden-cost workload has 16 chains 60 times heavier than the other 48 and a shuffled queue, so B4's arrival-order dispatch creates a long tail; any rule that starts heavy chains first removes it. Evidence: the no-prediction hand rule gets the same gain (-21.6% vs -20.4%), and P-only is only 2% slower than B4 on this workload (B4 gains little from the E cores). Where nothing can be reordered (uniform) or where informed ordering rules also do not beat B4 (two-factor: -0.47% and +1.98%, intervals including zero), there is nothing for a predictor to win, so PRED ties B4. This is an inference from these measurements, not a separately tested mechanism; whether the tail is caused by late starts or by heavy chains landing on E cores is **NOT VERIFIED** (the event logs could settle it).

**Why the newer directions did not help:** the gate in `revival_20261025` compared the best simple rule with a work-conserving "oracle" and found no headroom. Caution: in that same session the learned policy was **faster than the oracle** (-3.10% [-4.62,-1.61] relative to ORACLE_STATE; oracle mean on g2 2.819 s vs B4 2.726 s), so the oracle is not an upper bound and "no headroom" means "this particular oracle rule could not improve on B4", not "no schedule is better". True optimum: NOT VERIFIED. Per the protocol no pilot followed, and the 5% gate was a pre-registered choice, so stopping was correct. For GPU, Phase 1 found the best device flips under GPU contention only for `img_denoise`, a minority of work (about 34% in the unvalidated W2 workload), and simulated headroom of 0.05% under the same rule. Those simulation numbers are estimates (DOC-ONLY).

## 5. Recommendation: one action

**Reproduce the 6P+7E hidden-cost comparison against B4 in a bounded fresh session on the current code, and show it next to the hand rule, stating in the talk that the win is ordering-based.** Reason: it is the only measured end-to-end scheduling gain, it is pre-registered and verified, all inputs exist, it costs a few minutes, and it needs no code change. Fixing a defect or changing the workload would add risk on the night before the review with no evidence that either is needed; the GPU benchmark is a separate claim (see section 9).

- Files: `scripts/run_experiment.py`, `caosched.study2.adapter:factory` (`src/caosched/study2/adapter.py:229`), design `data/results/study2_20261024/designs/design_study2_iters_confirm2.json` (sha256 verified: `7aa921033b4bc827df02f00274edecce2bd60a212869e038569a9fdf5609bbd1`), model `param_model_cover1234.json`, profile `profile_t512/20261024T001156_profile.json` (both exist), `scripts/analyze_experiment.py`.
- Environment: `.\.venv\Scripts\python.exe` (3.11.9), CUDA not required for this design (the recorded runs show `gpu_pool: false`), laptop on mains power (the design sets `require_ac_power`; currently plugged in at 99%), free RAM at the audit was 4.4 GB (design threshold 0.8 GB), no other heavy program. Close the browser and any WSL VM.
- Scope cap: 1 session, 11 blocks (1 warm-up + 10 analysed), 5 conditions, no tuning, no edits. Expected duration about 4 to 5 minutes (estimate: recorded mean makespans sum to about 20 s per block, plus startup; not measured on this code version).

## 6. Exact commands

Commands were checked by reading the code. A scratch script doing the same design edit as the one-liner below was dry-loaded (11 blocks planned, 5 conditions); the one-liner itself, `memory_preflight.py` and the experiment run were not executed. Run from `D:\cao project` in PowerShell.

```powershell
$env:CAO_STUDY2_ADAPTER_CONFIG = "data\results\study2_20261024\designs\adapter_config_study2.json"
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/results/study2_20261024/designs/design_study2_iters_confirm2.json')); d['name']='demo_iters_repro_from_confirm2'; d['n_blocks']=11; import os; os.makedirs('data/results/demo_20261027', exist_ok=True); json.dump(d, open('data/results/demo_20261027/design_demo.json','x'), indent=1)"
.\.venv\Scripts\python.exe scripts\memory_preflight.py --min-free-gb 2
.\.venv\Scripts\python.exe scripts\run_experiment.py --design data\results\demo_20261027\design_demo.json --out data\results\demo_20261027\sessions --adapter caosched.study2.adapter:factory
```

Then analyse (use the session folder name printed by the run):

```powershell
.\.venv\Scripts\python.exe scripts\analyze_experiment.py --sessions data\results\demo_20261027\sessions\<SESSION_ID> --out data\results\demo_20261027\analysis_ref_B4 --reference B4
```

Notes: the design copy keeps the same chain orders (e,f) and seeds as the recorded session, which makes it a reproduction; it has a new design hash (a different `n_blocks` changes the plan), so it is never pooled with the old session. It uses the code of the current branch, whose source hash differs from `f27b56f3`. The first command writes only into a new folder and refuses to overwrite (`'x'` mode). The older `scripts\reproduce_subset.py` re-derives tables from existing raw logs and is the fallback for showing the recorded result without a run.

## 7. Expected evidence

- Session status `complete`, 11 of 11 blocks, 55 runs, all `status: ok` and `output_ok: True` (hash check inside the adapter), zero runs flagged by the scheduling-cost guard.
- In `effects.csv` (primary, `makespan_s`): `PRED_RANK_GREEDY` vs `B4` negative with the interval excluding zero. Recorded reference magnitude: -20.4%; with 10 blocks the interval will be wider (about +-3%, from the recorded paired sd of 0.055). `B4_param_first` about -21.6%, `B0_P_only` about +2%, `EFT_E1_noctx` far slower (+30% or more).
- Mean makespans near the recorded ones (B4 3.97 s, PRED 3.16 s, hand rule 3.11 s, P-only 4.05 s, EFT blind table 5.68 s). Absolute times may shift a little with background load.
- Decision time per run in `runs.csv` (`sched_overhead_total_s`): PRED about 15 ms, B4 about 7 ms. This is the "latency" figure to quote; makespan percentage is the performance figure. Keep them as two separate numbers.
- Success criterion written now, before the run: PRED faster than B4 in at least 9 of 10 analysed blocks and interval excludes zero. Anything else is reported as it is.

## 8. Fallback and stop conditions

- Stop at once if: the run aborts on the memory preflight or power check, any run has `output_ok: False`, any run fails or times out (120 s limit), free RAM falls under 0.8 GB, or the session is still going after 15 minutes.
- Do not rerun to get a better number and do not edit the policy or workload. If the result differs from the record, report both and the code-hash difference.
- Fallback if the environment prevents a run: show the stored session read-only: `data\results\study2_20261024\iters_confirm2_sessions\20261024T235431`, its `analysis_iters_confirm2_ref_B4\effects.csv` and `summary.csv`, and `.\.venv\Scripts\python.exe scripts\reproduce_subset.py --help` for the re-derivation from raw logs (command arguments **not verified here**). The dashboard (`python -m caosched.dashboard`) shows recorded runs; whether its Study 2 sessions appear on the Montage & GPU tab is NOT VERIFIED.
- Optional if time remains, same method: 2P+7E (`design_study2_iters_p2_confirm.json`, adapter config `adapter_config_study2_p2.json`). Not needed for tomorrow.

## 9. Review and publication readiness

**Real hardware tested:** P and E core pools (6P+7E and 2P+7E), the CUDA worker (RTX 3050) as an ordinary fast worker, real image-stage execution with output verification, Montage via native Windows build (null scheduling result). **Emulated:** the remote pool (loopback TCP with a link shim, pinned to an E core), labelled emulation; REMOTE_EMULATION_PLAN.md is a plan, its sweep was not run (DOC-ONLY). **Simulated:** GPU opportunity headroom (coordinator-cost model), LP bounds: estimates. **Untested:** Raspberry Pi, real network, GPU telemetry, GPU-contended end-to-end runs, any workload outside the synthetic image chains plus Montage.

**GPU / CPU results:** task-level timings (VERIFIED, Stage 1 spike: `img_edges` 15.06x at 1024 px, `img_features` 5.21x, `img_denoise` x8 1.36x; Phase 1 complete-cost medians in `revival_gpu_profile_20261025`, 8 repetitions, DOC-ONLY). The only full-workflow GPU effect is the uniform-batch comparison with and without the GPU worker (about 5%), and it comes from having the worker, not from the scheduler (B4_gpu ties the predictive rule). No result shows the full workflow finishing faster because the scheduler chose between CPU and GPU. Do not mix the two claims.

**What we can honestly say tomorrow:**
1. Prediction-aware scheduling shortens real makespan by about 20% against blind greedy when task cost is hidden in a parameter and ordering matters, and by 17% to 45% against static or naive rules; verified, pre-registered, outputs checked.
2. The same effect is obtained by a hand-written rule that knows the parameter; the learned model removes the need to hand-code it and retrains in one command.
3. Where nothing is hidden or nothing can be reordered it ties blind greedy and does no harm (<1% decision overhead).
4. Honest negatives: Montage, uniform, two-factor, contention-aware and GPU-contention directions showed no gain. Limits to state: two chain orders per configuration, dirty-tree runs, one machine, synthetic workload designed to have a hidden cost.

**Smallest credible experiment before requesting a Raspberry Pi:** use the existing remote-emulation path (`src/caosched/experiment/remote_adapter.py`, `scripts/calibrate_link.py`, `scripts/make_remote_design.py`) on the hidden-cost workload with one extra remote pool and a link calibrated to a measured LAN figure, and apply the project's own gate first: a transfer-aware oracle must be at least 5% faster than the best simple rule. If it passes, one short real-link micro-measurement (transfer time of a 512 px artifact versus its denoise time on P) justifies the Pi request; if it fails, the Pi cannot add scheduling value for this workload and the request is not justified. Pi 5 compute speed relative to an E core is NOT FOUND and must be measured on the device.

**Needed for a defensible paper:** more than two chain orders (or randomised orders per block); a clean committed tree at run time; one re-run of the headline experiment on a single code hash; a stronger baseline than first-idle-worker (LPT with true costs or a proper optimum bound) so the "no headroom" conclusions are bounded; resolution of the scheduling-time discrepancy in section 3; HEFT/PEFT originals and the patent text still unverified; related-work novelty not claimed. Raspberry Pi claims stay plan until executed.

## Location, key findings, first action

- File: `D:\cao project\CAO_HANDOFF_AUDIT.md`.
- Key findings: headline numbers verified (-20.39%, -21.10%); the same gain comes from a no-prediction longest-first rule, so the result is an ordering effect; only two workload orders per configuration; B4 is weak only where ordering matters; the revival "oracle" was beaten by the learned policy, so "no headroom" is not a bound; decision overhead is about 0.5% of makespan.
- First action: free the machine (plugged in, browser and WSL closed), run section 6 (4 to 5 minutes), analyse, and compare with section 7 before the review.

---

## Addendum 2026-10-27 (written during the overnight sprint; the text above is unchanged)

Corrections and resolutions, with evidence in `data/results/overnight_20261027/phase1/PHASE1_FINDINGS.md`:
1. **Overhead discrepancy resolved.** Section 3, discrepancy 1 and section 4 ("decision time is about 0.5% of makespan") mixed two metrics. The analysis tables' `sched_overhead_total_s` is the sum of per-dispatch decision times (PRED 15 ms per run, 0.5% of makespan). The protocol text's 0.094 s and 0.187 s are the coordinator's total scheduling time (`extra.decision_time_total_s`), which also counts `order_ready` and every `select_worker` call that returned None. For B4, 10,042 of 10,299 calls returned None because the pool always holds an idle CUDA worker that no task can use, which defeats the dispatch loop's early exit. So the honest overhead for these policies is 2% to 5% of makespan (PRED about 3%), not 0.5%. A decision-preserving fix, tested in a separate adapter, removes most of it (B4 0.197 to 0.008 s, PRED 0.100 to 0.024 s) and changes PRED's gain over B4 by less than 1 percentage point.
2. **New order coverage.** The concern that only two chain orders were used is addressed exploratorily: 12 new orders (6P+7E) and 8 new orders (2P+7E) give PRED -19.32% and -20.45% versus B4, faster in 12 of 12 and 8 of 8 orders. The learned policy remains level with the hand rule (+0.66% and +0.27%).
3. **Recommended action carried out.** The bounded reproduction of section 6 was run last night (session `20261026T220714`, -21.79% [-23.67,-19.87]); the sprint then used the remaining time on the items above.
4. Still open from this audit: clean-tree reruns, a stronger headroom bound than the revival oracle, HEFT/PEFT originals, Raspberry Pi.
