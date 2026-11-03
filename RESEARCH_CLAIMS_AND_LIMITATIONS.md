# Research claims and limitations (status 2026-10-27, after the overnight sprint)

Three categories, never mixed: **Supported** (established by verified code and results), **Not established** (plausible, not backed by enough evidence), **Not supported / null** (tested, did not show the claimed benefit). Evidence labels: real (this machine), emulation (loopback remote node behind a delay shim), simulation, plan. Every number is in `RESULTS_TABLE.csv` with its source session; `EVIDENCE_INDEX.md` lists paths and hashes. "Registered" = pre-registered design in `docs/research_redesign/EVALUATION_PROTOCOL_study2.md`; "overnight" = exploratory design written before its run, in `data/results/overnight_20261027/`.

## A. Supported

| # | Claim | Evidence | Scope | Competing explanation | Limitation | Additional experiment |
|---|---|---|---|---|---|---|
| S1 | On the hidden-cost workload `PredictedRankGreedy` (PRED) has a shorter makespan than blind greedy B4: about 20% to 22% | Registered: 6P+7E -20.39% [-21.24,-19.26] (30 blocks), 2P+7E -21.10% [-21.47,-20.73] (20 blocks). Reproduction on current code -21.79% [-23.67,-19.87] (10 blocks, same two orders). Overnight unseen orders: 6P+7E -19.32% [-20.04,-18.59] (36 blocks, 12 new orders, faster in 12 of 12 orders), 2P+7E -20.45% [-21.16,-19.78] (24 blocks, 8 new orders, 8 of 8) | One workload family (48 light chains of 2 denoise iterations, 16 heavy of 120), tile 512, this laptop, 6P+7E and 2P+7E | The gain is a longest-first ordering effect; B4 sends heavy chains late / to slow cores | The hidden cost is designed into the workload; unseen-order runs are exploratory; code hash differs between sessions | Other workload families; real applications with hidden costs |
| S2 | The same gain is obtained by a hand-written rule that knows the hidden parameter (`B4_param_first`) | Unseen orders 6P+7E: rule -19.85% [-20.74,-18.87] vs B4; PRED vs rule +0.66% [-0.23,+1.54] (Holm 0.21). 2P+7E: rule -20.67%, PRED vs rule +0.27% [-0.20,+0.77] (Holm 0.37) | as S1 | The prediction adds nothing beyond knowing the parameter | The intervals lie inside +-2% (the project's earlier equivalence margin), but equivalence was not declared in the overnight plans, so this is descriptive; registered 6P+7E session had PRED 1.5% behind the rule (not resolved) | Registered equivalence test with a declared margin |
| S3 | Static P-only is worse than the dynamic policies | 2P+7E: +45.8% vs B4, +83.7% vs the rule; 6P+7E: +3.7% vs B4, +29.4% vs the rule (overnight); registered sessions agree | same workload | none | | |
| S4 | The learned scheduler does no harm where nothing is hidden | Registered uniform batch: PRED vs B4_gpu +0.45% [-0.25,+1.22] (inside +-2%) | uniform batch with CUDA worker | | equivalence only against B4, one workload | |
| S5 | The model needs no hard-coded stage or parameter and is retrained by one command | Code (`param_model.py`, `study2_retrain.py`), tests, registered 2P+7E session with a retrained model (-21.10%) | the two layouts tried | | not demonstrated on another machine | Pi retraining (runbook step 6 notes it is not supported for the remote adapter) |
| S6 | Task-level GPU speed-up at large tiles | `img_edges` 15.06x at 1024 px, `img_features` 5.21x, `img_denoise` x8 1.36x; outputs equal within tolerance | kernels only, 15 repetitions | | host-device copies included for CUDA; says nothing about workflow makespan | |
| S7 | In the emulated remote setting, transfer-aware placement avoids the harm of blind remote placement | Registered level-1 session: B4_remote_slow_wan +31.18% vs EFT_E1_no_remote, EFT_E1_remote_slow_wan +0.32% (not significant); EFT placed no task on R | emulation, level 1 | B4 puts one task on R at the end | not a real network | |
| S8 | Predictions can be accurate yet give no gain | Overnight emulated session (level 30): 44 remote placements, predicted exec 0.1457 s vs measured 0.1464 s, predicted transfer 0.0937 s vs measured 0.0943 s, yet EFT_E1_remote_fast_lan is 3.78% slower than EFT_E1_no_remote | emulation | proxy runs on the coordinator core (hypothesis, not tested) | exploratory | pin the proxy to its own core and repeat |

| S9 | The size of the gain depends on how heavy the hidden cost is: large only at a large cost ratio, small (about 1% to 3%) below it | Overnight dose-response (6P+7E; heavy chains of L iterations, light chains 2). First pass, 4 new orders, 12 blocks per level: PRED vs B4 -2.60% [-3.51,-1.81] at L=6, +0.57% [-0.96,+2.61] at L=15, -6.10% [-9.52,-3.26] at L=40, -19.86% [-21.23,-18.53] at L=120. Follow-up with 8 further new orders, 24 blocks: -1.31% [-2.56,-0.10] (Holm 0.09) at L=15 and -2.89% [-4.34,-1.42] at L=40. The hand rule: -3.02%, -0.91%, -7.58%, -20.18% (first pass) and -2.77%, -3.53% (follow-up) | one workload family, one machine | the first-pass L=15 null and L=40 value of -6.1% were order-specific: the follow-up with more orders gives small gains at both; the curve is therefore flat and small up to a ratio of about 20x (denoise cost ratio) and large at 60x | exploratory; PRED model fitted at L=2 and 120 only (interpolation at 6, 15, 40); PRED is 0.4 to 1.6 points behind the hand rule at intermediate levels (not significant in the follow-up: +1.51% [-0.22,+3.07] at L=15, +0.66% [-0.16,+1.55] at L=40) | levels between 40 and 120; refit at intermediate levels |
| S10 | The scheduling-time inefficiency does not explain the headline result | Overnight: with a decision-preserving fix of the dispatch loop (coordinator time 0.197 to 0.008 s for B4, 0.100 to 0.024 s for PRED), PRED_fix vs B4_fix is -20.28% [-22.18,-18.44] against -19.47% [-20.68,-18.23] unfixed in the same session; B4_fix vs B4 -1.17% [-3.52,+1.18] | 6P+7E, L=120, 4 new orders, 12 blocks | | exploratory; the fix is in a separate adapter, not in the source | apply the fix in the source and rerun the registered design |
| S11 | A published list scheduler (HEFT) driven by the same learned model is level with PRED; PEFT and early-binding rank-EFT are worse | Overnight, 6 further unseen orders, 24 blocks, L=120: versus B4 PRED -18.97% [-19.93,-17.96], hand rule -19.27%, HEFT -18.08% [-19.38,-16.69], rank-EFT -13.21%, PEFT -2.58% [-3.75,-1.31]; versus PRED: HEFT +1.10% [-0.53,+2.81] (Holm 0.50), rank-EFT +7.11% [+5.95,+8.47], PEFT +20.23% [+19.26,+21.18] | one workload family, 6P+7E | the value comes from the learned costs and from ordering, not from the placement rule | HEFT and PEFT implemented from secondary descriptions (originals not read); exploratory; the HEFT interval is not inside +-2% so equivalence is not shown | other workload families, the originals' exact formulas |
| S12 | The gain depends on how many chains are heavy: largest with few heavy chains, small when most chains are heavy | Overnight (6P+7E, heavy 120 iterations vs light 2, 4 new orders, 12 blocks): PRED vs B4 -27.65% [-33.97,-18.73] with 4 of 64 heavy, -26.76% [-27.86,-25.74] with 8, about -19% to -20% with 16 (unseen-order sessions), -3.81% [-5.06,-1.85] with 40; hand rule -26.94%, -26.93%, -5.15%; PRED vs hand rule -0.98% [-3.12,+1.17], +0.24% [-0.41,+0.98], +1.42% [-0.73,+4.48]. B4 is very order-dependent with 4 heavy chains (paired sd 0.23); static P-only beats B4 with 4 and 8 heavy chains (-11.6%, -15.8%) | one family, one machine, 4 orders per session | consistent with the tail mechanism: blind dispatch can start a heavy chain late or on a slow core, and fewer heavy chains make one late start costlier; not tested directly | exploratory; no direction was declared in the plan | log which core and start time each heavy chain got in the B4 runs (the event logs have it) |

## B. Not established

| # | Claim | Why not established | Next experiment |
|---|---|---|---|
| N1 | Learned prediction beats a good informed simple rule | all comparisons are level or behind the rule | none needed unless a workload where the rule cannot know the cost (e.g. cost depends on data content) |
| N2 | The gain generalises to other workloads | only one family tested; unseen orders are the same family | new workload families (the dose-response sweep below varies the cost ratio only) |
| N3 | Resource-state awareness improves scheduling | oracle gate failed; revival v2 equivalent to B4; 0 of 18 decisions with a choice differed from B4 in the demo trace; the oracle was beaten by PRED so the gate is not a bound | a stronger headroom bound (optimal or LPT with true costs) before any new policy |
| N4 | GPU contention is a scheduling opportunity | Phase 1: 93.6% of dispatches forced; simulated headroom 0.05% | workload with GPU-dominated work, pre-generated inputs |
| N5 | A GPU speed-up at task level carries over to workflow makespan through scheduling | no measurement; GPU worker presence helped about 5% on the uniform batch in an older session, not the scheduler | GPU-eligible hidden-cost workload |
| N6 | Remote offloading benefit | emulation level 1: none; level 30: the predictive policy is slower with a remote worker on the fast link, blind B4 -1.5% (not significant) | real link with a worker that adds capacity (Pi runbook) |
| N7 | Raspberry Pi performance, real-network offloading | never run | `RASPBERRY_PI_VALIDATION_RUNBOOK.md` |
| N8 | Novelty | literature check is bounded; HEFT/PEFT originals and the patent claim text were not read | systematic search |

## C. Not supported / null

| # | Claim | Result |
|---|---|---|
| X1 | PRED beats blind greedy on a two-factor workload | +0.95% [-0.90,+2.84], 40 blocks (registered, claim C3 not supported) |
| X2 | Montage: predictive scheduling beats static P-only | EFT 1.6% slower (registered, one dominant serial path) |
| X3 | Resource-state-aware policy v1 does no harm | +2.3% [+1.2,+3.6] (registered failure, fixed in v2) |
| X4 | The oracle gate (>= 5% headroom on the contended mixed DAG) | not met: B4 1.24% faster than the oracle |
| X5 | Remote worker helps the predictive policy at denoise level 30 on a fast emulated link | EFT_E1_remote_fast_lan +3.78% [+2.27,+5.58] vs no remote |

## D. Limitations that affect every claim

1. The hidden-cost workload was built to contain a hidden cost. It shows when prediction or knowledge helps, not how often such costs occur in real workflows.
2. Registered sessions have only two chain orders per configuration; the overnight sessions add 12 and 8 orders but are exploratory.
3. Runs were made with a dirty working tree (commit recorded, tree not clean); source hashes differ between sessions (`f27b56f3`, `41a8f43b`, `ed70c36d`); sessions with different hashes are never pooled in an analysis.
4. Coordinator scheduling time is 2% to 5% of makespan for all late-binding policies because an idle CUDA worker defeats the early exit in the dispatch loop (97.5% of B4's `select_worker` calls returned None). It is not the cause of the headline result (the hand rule has the same overhead; with the loop fixed in a separate adapter PRED's gain is -20.28% instead of -19.47%, claim S10) but it limits an absolute-overhead claim, and fixing it is worth 1% to 2% of makespan.
5. The first run after the CPU reference computation of a new chain order is about 2% slower (11 cases).
6. One machine, makespans of about 3 s to 9 s, a laptop that is not idle by nature.
7. The literature check is bounded: bibliographic data for HEFT, PEFT, Ilyushkin and Epema, and Lotaru were confirmed through search metadata/abstracts only; the full texts of HEFT, PEFT and Ilyushkin and Epema were not read; the patent claims were read as a paraphrase; the StarPU journal year and volume are unresolved.

## E. Final static-versus-dynamic study (2026-11-01 to 2026-11-02; sections A to D above are unchanged)

Evidence label: real measurements, one laptop (6 P + 7 E workers, one RTX 3050 CUDA worker). Metric: end-to-end makespan (amendment F1). Primary session `eval_h16_l120`, 24 included blocks, Holm over 10 contrasts. Full report: `CAO_FINAL_EXPERIMENT_REPORT.md`; flat table: `RESULTS_TABLE_FINAL.csv`. Negative effect = faster.

| # | Claim | Evidence | Scope | Competing explanation | Limitation |
|---|---|---|---|---|---|
| F1 | A dynamic policy built on the learned model finishes sooner than a static HEFT plan from the same model | C3 PRED vs HEFT_param_model CPU -5.2% [-5.9, -4.6]; C5 strict GPU -12.2% [-13.4, -11.1]; C4 PRED_E2E vs HEFT_E2E -5.2% [-5.9, -4.5]; C6 -8.5% [-9.7, -7.6]; Holm p 0.001 to 0.001 | primary workload (16 heavy chains), 512 px | on GPU configurations part of the gap may be model error (hold-out GPU error 23 to 31%) that a fixed plan cannot correct | other five workloads exploratory; the earlier overnight HEFT result (S11, +1.1% [-0.5,+2.8]) was level |
| F2 | The same dynamic policy is much faster than blind B4 | C1 CPU -17.8% [-18.8, -16.7]; C8 strict GPU -21.2% [-22.6, -19.7] | as F1 | most of the gain is available from a parameter-aware rule (F4) | |
| F3 | Adding setup and IPC terms (PRED_RANK_GREEDY_E2E) neither helps nor hurts on the primary workload | C2 +0.6% [+0.1, +1.3] (equivalent), C7 -0.0% [-0.7, +0.5] (equivalent) | primary workload | the terms are small (a few ms) next to task times | exploratory harm on the uniform workload (X8) |
| F4 | The hand-written parameter-aware rule B4_param_first is within 1% of PRED_RANK_GREEDY | CPU/extended/strict GPU, exploratory, in the report Section 1 | primary workload | | confirms S2; prediction adds almost nothing beyond knowing the parameter |
| F5 | Allowing the GPU only where the spike records verified a speed-up helps the dynamic policy | extended set vs CPU only -7.5% [-7.8, -7.2] (exploratory); C9 strict set vs CPU only -2.6% [-3.3, -1.7] | primary workload | | one CUDA worker; GPU model error 23 to 31% |
| F6 | A B4/PRED hybrid selector is not justified | cells: 17; max headroom 1.1%; mean headroom 0.08%; cells above the 2% margin: 0. | 17 workload x configuration cells | | descriptive; no held-out hybrid test was needed |

| # | Not established | Why |
|---|---|---|
| N9 | Remote worker with the final policies | not rerun; earlier emulated sessions (S7, S8, N6, X5) show no benefit on a fast link |
| N10 | Gain on other workflow families or machines | one image-pipeline family, one machine |
| N11 | Static plan with realised per-run times as an upper bound | HEFT_oracle uses class medians from calibration sessions |

| # | Not supported / null | Result |
|---|---|---|
| X6 | The GPU helps blind B4 | C10 B4 strict GPU vs B4 CPU +1.6% [+0.2, +3.0] (inconclusive); B4 extended vs CPU +2.8% [+0.8, +4.9] |
| X7 | The end-to-end terms improve the dynamic policy | C2 and C7 equivalent (F3) |
| X8 | PRED_RANK_GREEDY_E2E does no harm on a uniform workload with the strict GPU set | PRED_E2E vs B4 on `uniform` strict GPU +2.9% [+0.4, +5.9] (exploratory, unadjusted) |
| X9 | PEFT is competitive | PEFT_param_model is the slowest static plan in the primary session (report Section 8) |
