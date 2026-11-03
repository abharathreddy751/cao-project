# Phase 3 plan: unseen chain orders (EXPLORATORY, written 2026-10-26 before the run)

Label: **real hardware, exploratory generalisation check**. It is not a re-registration of a confirmatory design.

Question: does the effect seen on chain orders e,f,g,h (PRED_RANK_GREEDY and the hand rule faster than blind B4) also appear on chain orders that no earlier session, coverage session or model fit has used?

Fixed before running (nothing below changes after outcomes are seen):
- Design file: `design_unseen_orders.json` (written by `make_design.py`, SHA-256 recorded by the runner and in the activity log).
- Workload and conditions copied unchanged from the pre-registered `design_study2_iters_confirm2.json`: 64 chains of 512 px (48 with 2 denoise iterations, 16 with 120), 6 P + 7 E workers, no GPU pool. Policies: B4 (reference), B4_param_first, B0_P_only, PRED_RANK_GREEDY with the unchanged model `param_model_cover1234.json` and profile `profile_t512/20261024T001156_profile.json`. EFT_E1_noctx (blind table predictor, already known to be far slower) is dropped to save time; this is a declared change of the condition list, not an outcome-based exclusion.
- New chain orders: 12 seeds, 1001 to 1012 (instances `order_n01`..`order_n12`), consecutive integers, not searched. Used by earlier work: 11, 22, 33, 44, 55, 66, 71, 72, 77, 88.
- Blocks: 37 (block 0 warm-up, excluded by the existing design rule; 36 analysed, about 3 per order; the planner cycles through the 12 orders in seeded shuffles, so counts per order can differ by one).
- Seed 20261027. Preflight 0.8 GB free RAM, mains power required (both existing runner guards). Run timeout 120 s per run (adapter config of the earlier session).
- Model: not refit; fitted only on coverage logs from other orders (a/b/c/d), no evaluation outcome used.
- Analysis, fixed: `scripts/analyze_experiment.py --reference B4 --seed 0` (paired log-ratio of makespan within block, percentile bootstrap stratified by order, Holm across the three conditions) plus a second analysis with `--reference B4_param_first` for the direct learned-versus-hand-rule contrast. Per-order means reported so that order-level consistency is visible.
- Success reading, fixed: "supports generalisation" only if PRED_RANK_GREEDY vs B4 has an interval below zero AND PRED is faster than B4 in each of at least 10 of the 12 orders (order-level means). Otherwise "does not support / inconclusive".
- Stopping rule: run the design once. If the session aborts (preflight, power, crash) the partial raw data is kept and reported, and no second attempt is made unless the cause is an environment fault that is recorded; then one retry with a new session id and the same design file.
- Exclusions: only the declared warm-up block, plus any run that is not `ok`, fails output verification or has a hash-mismatching event log (the existing analysis rule). Sensitivity pass with all runs is produced by the same analysis.
- Interpretation limit: twelve orders of ONE workload family (48 light + 16 heavy chains, 60x cost ratio) and one machine. It cannot show generalisation to other workload families.
