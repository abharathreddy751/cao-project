# Study 2 report: can prediction beat static scheduling? (branch `study2/affinity`)

Date: 2026-10-24. Everything here comes from files under `data/results/study2_20261024/` and the pre-registration in [EVALUATION_PROTOCOL_study2.md](EVALUATION_PROTOCOL_study2.md) (sections 1 to 13). Stage 1 to 5 files are unchanged; rollback is `git checkout baseline-null-result`.

## In simple words

Stage 5 found that a scheduler that predicts task times did not beat the simple rule "use only the fast cores", on Montage. The reason (read from the profiles) is that every Montage task prefers the fast cores and one big task dominates, so there is nothing for a smarter rule to win.

Study 2 builds a workload where there is something to win: 64 independent small image jobs (source, denoise, edges, features, then one aggregate), run on three kinds of workers at once: 6 fast CPU cores, 7 slow CPU cores and one GPU worker. All stage speeds are measured, none are assumed.

**Result (confirmatory session, 441 runs, all outputs verified):**

| Compared with | Prediction-aware scheduler (EFT, no context logging) is | Verdict |
|---|---|---|
| "Fast cores only" (strongest static rule) | **27.6% faster** (interval 26.9 to 28.2) | beats it |
| Fixed task-to-worker map (GPU for edges/features) | **36.6% faster** | beats it |
| HEFT (static plan) | 10.4% faster | beats it |
| Greedy dynamic rule B4 (no prediction) | **0.25% slower, interval -0.55 to +1.05** | **tied** |

So "beat static scheduling" is achieved on this workload, as pre-registered. But the prediction itself is not what wins: the simple greedy rule B4 that hands each task to the first free worker (GPU first, then fast cores, then slow cores) does as well. The win over static rules comes from using all workers at once, not from knowing task times.

## What was learned on the way (all kept in the data)

1. **Pilot 1 failed on a measurement problem.** The stage 5 GPU adapter rebuilds the whole worker pool whenever a run switches between "with GPU" and "without GPU", so some runs started with cold workers. Makespans were two-humped (2.0 s versus 2.7 s). Fixed in the new adapter: one pool for every condition (`study2/adapter.py`).
2. **The stage 5 EFT pays for logging.** It builds a "decision context" for every candidate worker, which the dataset builder needed in stage 3. That cost 3% of the makespan (EFT 1.824 s versus 1.778 s without it; the difference is +2.62%, interval 1.87 to 3.39). The decisions are the same. This was pre-registered as prediction P4 and confirmed.
3. **Telling the predictor about task I/O did nothing.** The kernel-only model says a GPU edge task takes 0.84 ms, but the worker is busy about 6 ms with reading and writing. Adding measured I/O and message time (the existing end-to-end ablation) gave +0.09% against B4 (interval -0.72 to +1.04): no gain.
4. **Late-binding EFT was a negative result.** Holding a task until its predicted-best worker is free made runs about 50% slower (2.7 s), because idle workers waited while tasks were held, and the policy spent 0.7 to 1.0 s deciding. Pilot 4 was first a 10 to 33 s runaway caused by the logging cost above (the decision context walks the worker histories on every held task); that is documented as an implementation cost, not a policy result. The late policy is not in the confirmatory design.
5. **The GPU is worth having.** The same EFT without the GPU is 4.87% slower (prediction P5, confirmed).

## What this means for the project

* Montage null (stage 5): unchanged. Study 2 does not overturn it, it shows where the room is.
* Honest headline for a review: *prediction-aware placement clearly beats fixed rules, and the benefit appears when workers differ and tasks are many; but a simple greedy dynamic rule gets the same result, so prediction by itself is not what delivers the gain, at least with these predictors on this machine.*
* To make prediction beat the greedy rule too, the workload needs a case where "first free worker" is a bad choice: task types that are much faster on one worker kind AND scarce workers of that kind, with costs the greedy rule cannot see (long tail tasks, uneven task sizes). This study has uniform tasks, so B4 never gets it wrong. That is the next experiment, not done here.

## Reproduce and check

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_study2.py
.venv\Scripts\python.exe scripts\make_manifest.py data\results\study2_20261024\confirm_sessions\20261024T013322 --verify
.venv\Scripts\python.exe scripts\reproduce_subset.py --analysis-dir data\results\study2_20261024\analysis_confirm_ref_B4_gpu --log <new log path>
```
Re-running the session needs the CUDA torch install, an idle laptop on mains power, and `data/results/study2_20261024/designs/design_study2_confirm.json` with `CAO_STUDY2_ADAPTER_CONFIG` pointing at `adapter_config_study2.json` (see EVALUATION_PROTOCOL_study2.md section 12; about 40 minutes).

## Files added by this study (nothing else was edited)

`src/caosched/study2/{__init__,workload,policies,adapter}.py`; `scripts/study2_{profile,gate,design,e2e_terms}.py`; `tests/test_study2.py` (10 tests); `docs/research_redesign/EVALUATION_PROTOCOL_study2.md`, this file; `data/results/study2_20261024/` (profile, gate, designs, five pilot sessions, the confirmatory session, analyses, manifests, repro logs).

## Checks run at the end

Full suite, three runs: 402 passed, 1 failed each time; the failure is `tests/test_profile_montage.py::test_profile_format_csv_fit_and_cleanup` with `SystemExit: refusing to start: free RAM 1.50 GB < 2.0 GB` (the test's own memory guard; this machine runs with 1 to 2.6 GB free because of other programs), and the test passes when run alone or with its neighbours (2 passed; 22 passed in a three-file subset). The audit run before study 2 had 393 passed. No study 2 file runs before it (alphabetical order) and no stage 1 to 5 file changed. All 10 study 2 tests pass. `mypy` on `src/caosched`: no issues in 83 files. `git diff --name-status baseline-null-result HEAD` shows only added files.

## Update: the oracle check (same day, protocol sections 14 to 16)

Question asked: is there room for a better predictor on this workload? We ran EFT with TRUE task times (taken from earlier logs, a ceiling, not a real rule).

* Oracle session 1 was flawed: the oracle's table lookup cost 1.3 s of scheduling time per run (in 1.7 s runs), so it looked 29% slower than B4. Kept and reported; fixed by caching the medians (same numbers).
* Oracle session 2 (valid): EFT with true times is **1.74% faster than B4** (interval -3.84 to +0.08), and the same as the real EFT (-1.67%). So the ceiling for EFT-style rules here is about 2%.
* Workers are busy 92 to 95% of the time with B4, EFT or the oracle. The earlier estimate of "40% headroom" came from solo task times and was too optimistic; it is withdrawn.

Meaning: on this uniform, saturated batch, prediction cannot beat greedy, even with perfect predictions. The next workload must pass this oracle gate first (oracle at least 5% faster than the best simple rule) before any predictor is built. Candidates: heavy-tailed task sizes, critical-path structure, idle capacity.

## Update 2: the workload where prediction wins (protocol sections 18 to 20)

The oracle check showed the uniform batch has no room. So we built a workload where a table cannot see the cost: 64 independent image chains of the same size, 48 with a light denoise step and 16 with a denoise step 60 times heavier (the number of repeats is a task parameter). We tested it in three steps, each with the rules written down before the run.

1. **Gate (126 runs).** An EFT with true times is at least 5% faster than every rule that cannot see the parameter. Gate passed.
2. **Confirmatory (216 runs, new chain orders, all outputs verified).**

| Compared with | Learned predictor (rank-ordered EFT that sees the parameter) is | Verdict |
|---|---|---|
| Greedy B4 (blind) | 13.8% faster | supported |
| Static "P cores only" | 22.5% faster | supported |
| Table predictor (blind to the parameter) | 36.8% faster | supported |
| Hand rule "sort by the parameter" | about 6% **slower** | not resolved, direction against us |

3. **What it means.** The project's idea works when prediction carries information the other rules lack. A table-based prediction that is wrong about a hidden cost is worse than no prediction (36% slower than greedy). A learned predictor that sees the parameter fixes that. It does not beat a person who already knows which parameter matters and sorts by it, but it replaces that knowledge automatically.

Honest notes: 256/1024 px mix workload was tried first and dropped after its coverage session (all rules within about 5%); the oracle's lookup table needed four coverage sessions (amendments A8 to A10); the oracle EFT was itself beaten by the hand rule here, so it is not a ceiling on this workload.


## Update 3: the permanent fix (protocol sections 21 to 29)

**What was wrong.** On the hidden-cost workload the section 20 predictor was accurate, but the scheduler that used it (EFT) bound tasks early, behind busy workers, so it was about 6% slower than a hand rule that only sorts by the hidden parameter. The literature agrees that order matters more than accuracy under load (Ilyushkin and Epema 2018). So the weak part was how predictions are used, not the model.

**What we changed (all permanent, all tested).**

1. **Policy.** `PredictedRankGreedy`: order ready tasks by predicted remaining time (HEFT-style rank), give each task to the idle worker with the smallest predicted time, never queue behind a busy worker. About 0.09 s of scheduling time per run.
2. **Model.** `ParamModelEstimator`: one generic model. It finds by itself which task parameters change the runtime (here, the number of denoise repeats) and fits a line per stage and pool from logs. Nothing in the code names a stage or a parameter. An unseen stage or pool is an error, never a guess.
3. **Retraining.** `scripts/study2_retrain.py`: one command runs two coverage sessions on the current machine or pool layout and fits the model. Used for a Raspberry Pi later, no code change.
4. **Guards.** A decision-time budget test, a scheduling-cost guard (a run that spends more than 25% of its time deciding is recorded as failed), a mains-power check in the runner, and a claims registry (`docs/research_redesign/claims.json`) whose numbers are re-checked against the stored tables by `tests/test_claims.py`.

**Results (all pre-registered, all outputs verified, fresh chain orders each time):**

| Test | Beats blind greedy B4 | Beats static P-only | Beats the blind table predictor | Versus the hand rule that knows the parameter |
|---|---|---|---|---|
| 6 P + 7 E workers (30 blocks) | 20.4% faster | 21.9% faster | 42.9% faster | 1.6% behind (equivalence not resolved) |
| 2 P + 7 E workers, model retrained by one command (20 blocks) | 21.1% faster | 45.1% faster | 36.6% faster | level (within 0.4%, inside the 2% margin) |
| Uniform batch, nothing hidden (30 blocks) | level (+0.45%) | 26.1% faster | level (+0.90%) | not applicable |

**What it means.** The project's claim holds and is implemented: a learned, data-driven predictor beats blind and static scheduling by 20% to 45% where runtime depends on something a table cannot see, reaches a rule that is handed the key parameter, and does no harm where there is nothing to learn.

**What did not work, kept in the record.** EFT with early binding (6% behind), HEFT (3% behind), PEFT (20% behind), a bounded hold of tasks for fast workers (no gain, four times the decision cost), a perfect-knowledge oracle EFT (beaten by the hand rule). Nothing tried beats the hand rule.

## Update 4: the two-factor workload (protocol sections 30 to 32)

**Question.** Does the same generic model, retrained by one command, find a cost that depends on two things at once (image size and number of repeats), and beat the one-factor rules?

**Result (pre-registered, 40 blocks, fresh chain orders, 246 runs all verified).** Sorting by size alone and the static P-only rule are 17% slower than the learned policy (both Holm-significant, as predicted). The learned policy is level with blind greedy (0.9% slower, interval -0.9 to +2.8; the pilot's 4% advantage did not replicate), the repeats-only rule and the pixels x repeats formula (equivalence within +-2% / +-3% not shown, because the paired spread was twice the pilot's). The model predicts the heavy classes within 8% of the measured time but not the lightest class.

**What it means.** The learned policy avoids the 17% loss of the wrong simple rules without a hand-written formula, which supports "the model finds the structure". It does not beat blind greedy here, and the claim "prediction beats blind greedy" stays limited to the one-factor hidden-cost workloads (sections 18 to 24). Nothing tried beats the best hand-written rule. Claims C1 to C5 are in `claims.json`. Next improvement named by the data: a log-scale or per-class error model for the light tasks.
