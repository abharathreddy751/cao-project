# Phase 1: evidence verification (2026-10-26/27)

Checked directly from files in the repository; scripts: `../verify_session.py`, `p1`-style verification (output `session_verification.json`), `diag_sched_time.py`.

## 1. State recorded
Branch `revival/resource-state-aware`, HEAD `9d8ea2211e6c30fcc7f8448dc14b9cb47ebfe76d`, 74 status entries at start (one modified tracked file, `data/results/study2_20261024/progress.txt`; the rest untracked). Free RAM about 3.5 GB, free disk on D: 83 GB, mains power. Snapshot files: `../snapshot/` (git status, diff stat, log, pip freeze, software hash). Current source hash (before any code change today): `41a8f43ba2a3...` (`software_info()`).

## 2. The latest reproduction (session `20261026T220714`) is consistent with what you reported
- Session `complete`, 11 of 11 blocks, 55 runs, all `status ok`, all outputs verified, 55 of 55 event-log hashes match the manifests, design file hash equals the session's recorded hash (`182a47d2...`).
- Code recorded: commit `9d8ea221` with a dirty tree, source hash `41a8f43b`. The earlier registered session (`20261024T235431`) was run at commit `ae5395fe`, dirty tree, source hash `f27b56f3`. **Different code versions: they are not pooled.**
- `effects.csv` (reference B4, 10 analysed blocks, orders e and f only): PRED_RANK_GREEDY -21.79% [-23.67, -19.87], Holm 0.0067; B4_param_first -21.35% [-23.97, -18.94], Holm 0.0074; B0_P_only +0.72% [-0.98, +2.57], Holm 0.59; EFT_E1_noctx +36.44% [+26.60, +49.98]. All as stated. Direction: effect_pct is the paired geometric-mean change of the condition relative to the reference; negative = shorter makespan. Warm-up block 0 excluded (5 runs); no run flagged by the cost guard.
- Reconciliation with the registered session of 2026-10-24 (same design, same two orders, other code hash): PRED -20.39% [-21.24, -19.26] (30 blocks). The two intervals overlap; the reproduction is a repeat measurement of the same two workload instances, not independent evidence.

## 3. The scheduling-overhead discrepancy is a metric-definition difference, plus one real inefficiency
Two different numbers exist for "scheduling time":
- `sched_overhead_total_s` (analysis tables) = sum of `decision_time_s` on `task_dispatched` events = time of the `select_worker` calls that bound a task.
- `extra.decision_time_total_s` (run manifest; coordinator `scheduling_time_seconds`) = time in `order_ready` plus time of EVERY `select_worker` call, including calls that returned `None`.
Means per run (hidden-cost batch; same in all three sessions): B4 0.007 s versus 0.188 s; hand rule 0.0065 versus 0.172; PRED 0.015 versus 0.095; P-only 0.0047 versus 0.138; EFT_E1_noctx 0.0513 versus 0.0517 (early binding, no wasted calls). The protocol text quoting 0.094 s / 0.187 s was the second definition.
Instrumented runs (`phase1/diag_run2/diag_sched_time.json`, one run each): B4 made 10,299 `select_worker` calls, 10,042 of them returned `None`, costing 0.184 s of the 0.209 s total; PRED made 11,329 calls, 11,072 `None`. Cause, verified from the event log (`worker_ready` shows pools P x6, E x7 and **G x1**): the Study 2 worker pool always contains an idle CUDA worker (one pool for every condition, to avoid rebuild confounds), no task of this DAG is eligible for it, so `Coordinator._dispatch_ready_tasks` never takes its early exit (`if late and not self.state.idle_workers(): return`) and scans every ready task on every pass (about 39 per pass, 257 passes).
Consequence: all late-binding policies carry 0.07 to 0.19 s of coordinator time per run (2% to 5% of makespan), more for B4 and the hand rule than for PRED. This does not explain the headline result: the hand rule has B4's overhead and is 19.9% faster. It is an upper bound of about 2 percentage points on how much of PRED's gain over B4 could come from the overhead difference. The honest statement for the paper: "coordinator scheduling time is 2-5% of makespan for all late-binding policies on this setup; PRED's per-dispatch cost is 15 ms per run (0.5%)". **Not fixed**: the fix (leave out workers that cannot take any ready task when deciding the early exit) changes the timing of every policy and the source hash the night before the review; proposed for the post-review code, with a regression test that counts `None` returns.

## 4. Other checks
- Order-position effect: in 12 blocks the first run follows the CPU reference computation for a new chain order (about 55 s of wall time before the run); those runs have makespan about 2% above the median of the other runs of the same condition (11 non-warm-up cases). Conditions are randomised within blocks, so it is noise, not bias, but it is a limitation.
- Claims registry: `tests/test_claims.py` re-reads every cited `effects.csv`; all claim tests pass in the full run (472 passed, `../tests/full_suite.txt`).
- `PROJECT_BACKBONE_CURRENT_STATUS.md` does not exist; `PROJECT_BACKBONE.md` is the file.
- The Stage 5 remote session file `gate_remote.json` has `"label": "real"` while the session and analysis are labelled `emulation`; the analysis labels are the correct ones.

## 5. Follow-up experiment: how much of the gain is overhead? (phase3d, exploratory)
Session `phase3d/sessions/exit_fix` (78 runs, all ok and verified, code hash `ed70c36d`, 4 new orders, 12 analysed blocks, L = 120). The adapter in `phase3d/cao_overnight_adapter.py` (a separate file; no project source changed) swaps in a copy of the dispatch loop whose early exit ignores idle workers that no ready task may use. The change cannot alter which placements a policy can choose (a skipped call could only have returned None); a smoke run checked that outputs stay verified.
- Coordinator scheduling time per run, plain to fixed: B4 0.197 to 0.008 s; hand rule 0.181 to 0.015 s; PRED 0.100 to 0.024 s.
- Makespan effect of the fix: B4_fix vs B4 -1.17% [-3.52, +1.18] (not distinguishable from 0); PRED_fix vs PRED about -2.2% and hand_fix vs hand about -1.9% (derived from the two reference-B4 effects, not separate contrasts).
- With overhead equalised, PRED_fix vs B4_fix is -20.28% [-22.18, -18.44]; the unfixed pair in the same session is -19.47% [-20.68, -18.23]. The overhead difference therefore accounts for at most about 0.8 percentage points of the gain, inside the 1-point criterion written in the plan. The headline result is not an overhead artefact.
- Not done: the fix is not applied to `src/caosched/core/coordinator.py`.
