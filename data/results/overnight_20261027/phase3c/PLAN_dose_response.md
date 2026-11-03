# Phase 3c plan: dose-response of the hidden cost (EXPLORATORY, written before any run)

Question: how heavy must the hidden-cost chains be, relative to the light ones, before ordering by (predicted) cost beats blind greedy B4? The registered and unseen-order results all use heavy chains of 120 denoise iterations against 2 for the light chains (about 60 times the denoise cost). The project's claim "prediction helps when cost is hidden" has no dose axis yet.

Fixed before running:
- Four sessions, one per heavy-chain iteration level L in {6, 15, 40, 120} (denoise cost ratio heavy:light about 3, 7.5, 20, 60), designs from `make_designs_dose.py`; 16 heavy and 48 light chains, tile 512, 6 P + 7 E workers (default adapter config), 13 blocks each (block 0 warm-up, 12 analysed), 4 NEW chain orders seeded 3001 to 3004 (shared by the four levels, never used before), seeds 20261036, 20261045, 20261070, 20261150 (20261030 + L).
- Conditions: B4 (reference), B4_param_first, B0_P_only, PRED_RANK_GREEDY (unchanged model `param_model_cover1234.json`, unchanged profile). The model was fitted on coverage logs at iterations 2 and 120 only; levels 6, 15, 40 are interpolation of a linear-in-iterations model, not refits.
- Analysis, fixed: `analyze_experiment.py --reference B4 --seed 0` per session and `--reference B4_param_first`; effects with 95% CI. Expectation written now (a hypothesis, not a threshold): the gain of PRED and of the hand rule over B4 grows with L; at L = 6 it is small. No effect-size threshold is set; nothing is classified "works" or "fails" by a cut-off.
- Run order: L = 6, 15, 40, 120, one run of each session; no repeat. Same code hash for the four sessions (no source edit between them).
- Limits: one workload family, one machine, 4 orders per level (12 analysed blocks); exploratory.
