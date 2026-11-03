# Phase 3b plan: unseen chain orders, scarce-fast-core configuration 2 P + 7 E (EXPLORATORY, written before the run)

Label: real hardware, exploratory. Same question as `phase3/PLAN_unseen_orders.md`, for the 2 P + 7 E configuration where the earlier registered session (orders g,h) also showed a ~21% gain over B4.

Fixed before running:
- Design `design_unseen_orders_p2.json` from `make_design_p2.py`: conditions copied unchanged from `design_study2_iters_p2_confirm.json` (B4, B4_param_first, B0_P_only, PRED_RANK_GREEDY with the 2P model `retrain_p2/param_model.json`), EFT_E1_noctx dropped; 8 new orders with seeds 2001 to 2008; 25 blocks (block 0 warm-up, 24 analysed); seed 20261028; mains-power and 0.8 GB preflight; adapter config `adapter_config_study2_p2.json` (max_p_slots 2).
- Analysis: `analyze_experiment.py --reference B4 --seed 0` and `--reference B4_param_first`, then `phase3/per_order.py`.
- Reading, fixed: "supports generalisation" only if PRED vs B4 has an interval entirely below zero and PRED is faster than B4 in at least 7 of the 8 orders (order-level means). Otherwise "does not support / inconclusive".
- Run once; no repeat unless an environment fault is recorded (then one retry with a new session id and the same design).
- Interpretation limit: eight orders of one workload family, one machine; not a new confirmatory test.
