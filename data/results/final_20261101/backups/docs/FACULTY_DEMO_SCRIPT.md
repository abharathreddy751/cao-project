# Faculty demo script (3 to 5 minutes)

All numbers below are read from files listed in `RESULTS_TABLE.csv` and `EVIDENCE_INDEX.md` (overnight sprint, 2026-10-27). Say "measured on this laptop" for them; say "emulated" for anything about a remote worker; say "not tested yet" for the Raspberry Pi.

## 1. What the project is (30 seconds)
"A workflow is a graph of tasks. Each ready task can run on a performance core, an efficiency core, a GPU, or in principle a remote device. A scheduler decides where and in what order. Our framework runs real tasks, logs everything, and lets us compare schedulers fairly: blind greedy dispatch, fixed rules, rules that know a cost parameter, and a scheduler that learns task costs from its own execution logs."

## 2. How it works (60 seconds)
- A coordinator dispatches ready tasks to workers; every dispatch and completion is written to an event log, and every output is checked against a CPU reference.
- The learned scheduler (`PredictedRankGreedy`): a small model per task type and core type, fitted by least squares from earlier logs, finds by itself which task parameters change the runtime; tasks are ordered by predicted remaining work, and each task goes to an idle eligible worker with the smallest predicted time. It never queues behind a busy worker.
- Experiments are run in randomised, interleaved blocks with a memory and power check, a hash of the code and the design, and a paired statistical comparison.

## 3. The strongest result (60 seconds)
"The workload is 64 independent image chains. Sixteen of them are 60 times more expensive because of a parameter that a size-based table cannot see. Blind greedy dispatch (B4) does not know which chains are heavy."
- Registered experiments (six fast cores + seven efficiency cores; and two fast + seven): the learned scheduler is about 20% to 21% faster than B4 (20.4% and 21.1%, 95% intervals about 2 points and 0.7 points wide).
- Overnight check on chain orders that were never used before (12 new orders on the six-core setup, 8 new on the two-core setup): 19.3% and 20.5% faster than B4; faster in every one of the 20 new orders; this is exploratory, one workload family.
- Fixed "P cores only" rule: slower than B4 and much slower than the learned scheduler.
Show: `data\results\overnight_20261027\phase3\per_order_summary.csv` and `analysis_ref_B4\fig_effect_vs_baseline.png`.

## 4. The honest part (60 seconds)
- "A hand-written rule that sorts by the heavy parameter gets the same gain: the learned scheduler is level with it (within about 1 point), not better. The value of learning is that nobody has to know the parameter in advance."
- "Where nothing is hidden or nothing can be reordered we tie blind greedy: a uniform batch, a two-factor batch, Montage. And the gain depends on how heavy the hidden cost is: about 1% to 3% when heavy chains cost 7 to 20 times a light chain, about 20% at 60 times (overnight dose-response). It also depends on how many chains are heavy: up to about 27% when only 4 or 8 of 64 are heavy, about 4% when 40 of 64 are."
- "A published list scheduler, HEFT, driven by the same learned model gets -18.1% against our -19.0% (not distinguishable); the other published one we implemented, PEFT, gets only -2.6%; both implemented from secondary descriptions."
- "The coordinator spends 3% to 5% of the run on scheduling for all of these policies; the learned one's own decision time is about 15 milliseconds per run."
- "GPU: single stages are up to about 15 times faster on the GPU at large tiles, but we have not shown a workflow-level gain from scheduling between CPU and GPU."
- "Remote offloading: tested only with a local emulated worker. Transfer-aware placement avoids the harm of blind remote placement; it did not give a gain in the regime we tested. The Raspberry Pi has not been tested; the validation runbook is ready."

## 5. What to show live (60 seconds)
1. Dashboard: `.\.venv\Scripts\python.exe -m caosched.dashboard --port 8765 --open`, then tab 5 for the experiment runs; commands and fallbacks in `FACULTY_DEMO_CHECKLIST.md`.
2. Stored evidence: a run's event log summary, the effects table.
3. If asked about reproducibility: `scripts\reproduce_subset.py` on an analysis folder (about a minute) re-derives the table from the raw logs.

## Likely questions
- "Is 20% a general number?" No. It applies to this workload family, these two core configurations, this machine.
- "Does the learned scheduler beat a good simple rule?" Not in our data; it matches it.
- "Is Raspberry Pi done?" No. Code path for an external node exists and was rehearsed over loopback (labelled emulation); the real test needs the device.
- "What is the overhead?" 15 ms of decision time per run for the learned policy; coordinator scheduling about 0.1 s per 3 s run.
