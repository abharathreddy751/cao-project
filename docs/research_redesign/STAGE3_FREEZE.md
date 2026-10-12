# Stage 3 freeze: decisions fixed BEFORE data collection, model fitting and the scheduling pilot

Date: 2026-10-12. Status: **[plan] frozen before any Stage 3 data were collected.** The SHA-256 of this file is recorded in the Stage 3 evidence manifest. Anything changed later is recorded as a dated amendment at the end, never edited in place. Chosen by the assistant under the project owner's delegation ("finish the project end to end"); the owner may overrule, and then a new freeze and a new session are needed.

Basis (all measured, files in `data/results/`): Stage 2 pool profile (mProject 111.8 s on P, 401.1 s on E), Stage 2 matrix (42 runs, `stage2_20261012/stage2_gate.json`): between-block spread of a policy's makespan up to 2.3% (EFT_E3: 269.7 s to 276.1 s), B0 P-only 270.9 s, B4 410.5 s, predictive policies 273-276 s.

## 1. Data and roles of instances

| Instance | Tasks | Role |
|---|---|---|
| `d1.0_dss2b_c56.7_24.0` | 19 | training |
| `d1.1_dss2b_c56.7_24.0` (primary) | 59 | training |
| `d1.1_dss2b_c10.7_41.3` | 59 | tuning fold (leave-one-instance-out) |
| `d1.5_dss2b_c56.7_24.0` | 157 | **final test, size withheld** (never used for fitting or tuning; evaluated once) |

Collection designs: `data/results/stage3_20261012/designs_v2/` (hash in the Stage 3 manifest). Conditions per block: `EFT_E1` (scheduling reference) and `RandomOccupancy` seeds 3101 and 3103 (every pool is executed under varied occupancy, so every eligible pool has labels). Training rows come from decision-context logs only (`context_source=decision`) of runs whose output verified.

## 2. Candidates and rules

* Candidates: E1 (static profile), E3 (moving history), E1+rc (online recalibration), Ridge (E4 form), CatBoost, MLP. TabM is **not** implemented.
* **TabM entry rule, evaluated now, before data:** TabM enters only if (1) there are at least 20,000 labelled training rows after the leakage filters, (2) the CatBoost/MLP learning curve is still falling at full size, and (3) one-step hindsight regret of CatBoost/MLP exceeds twice the pilot's noise floor. The planned collection yields about 1,500 to 2,500 task rows, so condition (1) cannot be met and **TabM is out**. The stated reason in the report will be "too few rows for a neural tabular model".
* Complexity order for the selection rule: E1 < E3 < E1+rc < Ridge < CatBoost < MLP (to be confirmed against measured latency and memory; a change is a dated amendment).
* Selection rule (`analysis/model_eval.select_model`): the cheapest model whose scheduling outcome is not worse than every more complex model, "not worse" meaning the upper bound of the paired-bootstrap interval of `outcome(simple) - outcome(complex)` is at most `margin`.
* **margin = 2.0% of makespan** (log-ratio ln(1.02)). Reason: it is not smaller than the largest between-block spread seen for a single policy in Stage 2 (2.3% range for EFT_E3, so a difference below about 2% cannot be told from block noise with few blocks); smaller values would make the rule select on noise.
* Outcome used for selection: end-to-end makespan on the primary instance (decision overhead is inside it and is also reported separately).
* Splits: leave-one-instance-out on the three non-test instances for fitting and tuning; time-ordered split within the primary session for the drift check; the d1.5 test is an `instance` split (the `size` column is 1 for every extcmd row, so a `size` split cannot express it). A run never appears on both sides of a fold.
* Refit: fit on all non-test rows with the config fixed in the freeze config file; the test instance is touched once.
* Metrics: MAE, RMSE, relative MAE, median and mean APE (median APE is the headline), signed bias, calibration by decile, latency distribution per call, peak memory, model size, training time; per transformation, per pool and overall; held-out rows only. Prediction quality and scheduling value are reported in separate tables.

## 3. What this freeze does not decide

The Stage 4 repeat count and the strongest-baseline choice come from the scheduling pilot and are fixed in `EVALUATION_PROTOCOL.md` section 12 before the main run. The pilot is `stage4_pilot` (see that section).

## 4. Known limits stated in advance

* Eight Montage task types, one dominant (`mProject`, 98.7% of sequential time); a learned model can collapse to a per-type constant, in which case E1/E3 is equivalent in effect and the report says so.
* About 59 tasks per run: few rows. Neural models are expected to be unreliable; CatBoost is the main candidate.
* Labels exist only for executed placements; counterfactual pools are covered by the E1 base profile plus the log-correction form and by random placement during collection.
* The machine is not idle (WSL VM, browser, editor); repeated collection under identical conditions is not guaranteed.

## Amendments

**A1 (2026-10-12, before any model was fitted):** model hyper-parameters and the evaluation configuration are fixed in `data/results/stage3_20261012/eval_cfg/cfg_tuning_loo.json` (SHA-256 `a8504e85160572d1024d1a1a86320963c587945dd025f91d55d85bdcd0c554e4`) and `cfg_final_test.json` (`ae2802ee11e685b6eb946902b1a8389dbdc6e49ccc46e90bb5b9056a59329843`): Ridge lambda 1.0, feature set occupancy+history; CatBoost 300 iterations, depth 4, learning rate 0.05, one thread, seed 0; MLP hidden [16,16], 200 epochs, lr 0.001, weight decay 0.0001, batch 64; selection margin 0.0198 (= ln 1.02); E3 window 8; rc alpha 0.2 clamp [0.5, 3]. No hyper-parameter was tuned on errors.

**A2 (2026-10-12):** data collection ran as `designs_v2` (42 runs, all completed and verified) instead of the larger first plan; the Stage 2 matrix runs of EFT policies (primary instance) are included in the fitting dataset because their decision contexts are logged and their outputs verified. The dataset built from decision contexts only: 3648 task rows (2706 fitting rows from d1.0, d1.1 primary, d1.1 c10.7; 942 rows from the held-out d1.5), `data/results/stage3_20261012/dataset/20261012T195206/` and `dataset_fit/20261012T195258/`. 1416 completed tasks without a logged decision context (B0-B5, random policies) were dropped by the builder and counted in the manifest. A first build attempt with a wrong event-directory layout excluded everything (`dataset/20261012T195144`, kept, unused).

**A3 (2026-10-12):** the scheduling pilot for model selection is `stage3_scheduling_pilot` (EFT with E1, E3, E1+rc, Ridge, CatBoost, MLP; 3 interleaved blocks on the primary instance), design file `data/results/stage3_20261012/pilot/design_stage3_pilot.json`. The strongest-baseline choice and the Stage 4 block count use the Stage 2 matrix as the baseline pilot (same machine, same instance, 3 blocks).
