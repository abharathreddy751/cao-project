# Phase 3e plan (EXPLORATORY, written before any run)

## 3e-1: established list schedulers driven by the same learned model, unseen orders
Question: how does PRED_RANK_GREEDY compare with HEFT and PEFT (published list schedulers, implemented from secondary descriptions; originals not read) when all three use the same learned cost model, on chain orders not used before? An earlier development session (older code, orders a and b, used during development) gave HEFT -17.9%, PEFT -3.9%, rank-EFT -15.8% and PRED -20.8% versus B4; this is the clean repeat.
- Design `design_heft_peft.json`: conditions B4 (reference), B4_param_first, EFT_param_model_rank_noctx, HEFT_param_model, PEFT_param_model, PRED_RANK_GREEDY (copied from `design_study2_iters_dev2.json`, PRED_RANK_HOLD dropped; model `param_model_cover1234.json`, profile unchanged), 6P+7E, L = 120, 6 new orders (seeds 7001 to 7006), 25 blocks (block 0 warm-up), seed 20261207.
- Analysis: `analyze_experiment.py --reference B4` and `--reference PRED_RANK_GREEDY`; per-order means.
- Reading, fixed: report each effect with its interval; "HEFT is level with PRED" only if the interval of HEFT versus PRED lies inside +-2%.

## 3e-2: dose-response follow-up (resolves whether the absent gain at L=15 and the large spread at L=40 are order-specific)
- Designs `design_dose2_h015.json`, `design_dose2_h040.json`: the phase3c designs with 8 NEW orders (seeds 5001 to 5008) and 25 blocks each (24 analysed, 3 per order); conditions B4, B4_param_first, B0_P_only, PRED_RANK_GREEDY unchanged.
- Analysis as phase3c. Reading, fixed: if PRED versus B4 at L=15 is again within +-1% with an interval including zero, the absent gain is reproduced; otherwise the earlier result was order-specific. No threshold is applied to classify "works".
- Run order: 3e-1, then L=15, then L=40; each once; same code hash as the other sessions of today after the code changes (`ed70c36d`).
