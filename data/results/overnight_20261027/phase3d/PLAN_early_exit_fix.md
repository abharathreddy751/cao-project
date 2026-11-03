# Phase 3d plan: how much of the PRED-vs-B4 gain is scheduling overhead? (EXPLORATORY, written before the run)

Background: `phase1/PHASE1_FINDINGS.md`. All late-binding policies waste coordinator time because an idle CUDA worker defeats the dispatch loop's early exit (B4: 0.188 s per run, hand rule 0.172 s, PRED 0.095 s). PRED's overhead is lower than B4's by about 0.09 s (2.3% of B4's makespan), so some of PRED's gain over B4 could be an overhead difference.

Fixed before running:
- The decision-preserving fix lives in `cao_overnight_adapter.py` (no project file changed): same method with the early exit based on idle workers that any ready task may use.
- Design `design_exit_fix.json` (from `make_design_exit.py`): 6 conditions = {B4, B4_param_first, PRED_RANK_GREEDY} x {plain, `_fix`}; L = 120 (the registered workload), 6 P + 7 E, 4 new orders (4001 to 4004), 13 blocks (block 0 warm-up), model/profile unchanged, reference B4. Run once through `run_experiment.py` with `--adapter cao_overnight_adapter:factory` and PYTHONPATH set to this folder; code hash recorded by the runner.
- Analysis: `analyze_experiment.py --reference B4` (effect of each condition on makespan; B4_fix vs B4 = the pure overhead effect) and `--reference B4_fix` (PRED_fix and hand_fix vs the fixed baseline = the gain with overhead equalised), plus mean coordinator scheduling time per condition from the run manifests.
- Reading, fixed: if PRED_fix vs B4_fix is within 1 percentage point of PRED vs B4, the overhead difference explains at most 1 point of the gain.
- A smoke run (1 analysed block, separate session id, not analysed) checks that the adapter loads and the fix lowers the coordinator time; it is not evidence.
