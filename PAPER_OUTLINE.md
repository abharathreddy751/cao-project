# Paper outline (working draft, 2026-10-27)

Working title: *When does lightweight, runtime-derived prediction help scheduling heterogeneous task graphs? A measured study on a laptop with performance cores, efficiency cores and a GPU.*

Scope statement (to appear in the abstract): the study shows where prediction helps, where it ties blind or informed simple rules, and where nothing can help; it does not claim a universal improvement, a new scheduling algorithm, or any Raspberry Pi or real-network result (until the physical-device runbook has been executed).

Evidence labels used throughout: real hardware (this machine), emulation (loopback remote node behind a delay shim), simulation (coordinator-cost model), plan (not executed).

## 1. Introduction
- Problem: dispatching ready tasks of a DAG onto workers with different speeds; classical list schedulers (HEFT, PEFT) assume known execution times, learned schedulers are mostly evaluated in simulation, decision overhead is rarely measured.
- Research question: under what workload and resource conditions does a cheap, log-derived runtime model improve end-to-end makespan after its own cost is counted, compared with blind, static and informed simple rules?
- Contributions to verify before claiming (candidates, not novelty claims): (1) a generic per-(stage, pool) runtime model fitted from execution logs that discovers which task parameters matter and is retrained by one command; (2) a work-conserving predicted-rank dispatcher; (3) a measured map of when it helps and when it ties; (4) negative results and the oracle-gate method (check headroom before building a predictor).
- Honest framing: the main positive result is reproduced by a hand-written rule that knows the hidden parameter; the contribution of the learned model is removing the need to know it.

## 2. Background and related work (all items below to be re-verified before submission; levels in `LITERATURE_UPDATE.md`)
- List scheduling: HEFT/CPOP (Topcuoglu, Hariri, Wu, IEEE TPDS 13(3):260-274, 2002: bibliographic data confirmed by search, original text not read) and PEFT (Arabnejad, Barbosa, IEEE TPDS 25(3):682-694, 2014, DOI 10.1109/TPDS.2013.57: bibliographic data confirmed, original not read). The project's HEFT/PEFT code follows secondary descriptions.
- Prediction-driven scheduling: StarPU (Augonnet et al., 2011), Lotaru (Bader et al., arXiv 2309.06918, FGCS 2024), Reshi; runtime-estimate accuracy versus slowdown (Ilyushkin and Epema, CCGrid 2018: abstract level only, conclusions not read).
- CPU/GPU placement and agentic schedulers (Carvalho et al. PVLDB 2024 tutorial; Lu and Reda arXiv 2607.22242, abstract level).
- Workflow systems and workloads: Montage, WfCommons/WfBench, WorkflowSim.
- Base patent US 11,561,826 B1 (claims read as a paraphrase only; no prediction in the claims): B4 is a comparison baseline, not an implementation of the patent.
- Gap statement to use: "not found in the sources inspected" (bounded search), not "no prior work".

## 3. System architecture
- Coordinator and event log; ready queue; worker pools (P cores, E cores, CUDA worker, remote worker via proxy/node); eligibility; late binding; output verification against a CPU reference.
- Policies: B0 (static P-only), B4 (greedy eligible, priority P then E), B4_param_first and size/cost-first hand rules, EFT with estimators E0-E5, HEFT, PEFT, `PredictedRankGreedy`, revival state-aware variants.
- Runtime model: ridge per (stage, pool) on numeric task parameters and size and their products; log-power variant; decision-time safe; no silent fallback.
- Experiment framework: interleaved seeded blocks, memory and mains-power preflight, run manifests with code hashes, exclusion rules, paired log-ratio bootstrap, Holm correction, sign-flip p, equivalence margins.

## 4. Methodology
- Workloads: Montage (59 tasks, real, native Windows build); uniform image-chain batch; hidden-cost batch (48 chains with 2 denoise iterations, 16 with 120; same image size); two-factor batch; contended mixed DAG; image pipeline with emulated remote pool.
- Baselines and why each: blind (B4), static (B0), informed hand rule (`B4_param_first`), size rule, cost formula, HEFT, PEFT, oracle variants.
- Metrics: makespan (primary), per-dispatch decision time versus coordinator scheduling time (two definitions, both reported), queue wait, task time, transfer.
- Pre-registration, amendments, claims registry with automatic re-check (`claims.json`, `tests/test_claims.py`).
- Threats to the method: workload designed to have a hidden cost; two chain orders per configuration in the registered sessions (12 and 8 more in exploratory sessions); runs with a dirty working tree; source hashes differ between sessions; one machine.

## 5. Results (every number is a row of `RESULTS_TABLE.csv`; labels as in the abstract)
- 5.1 Hidden-cost workload, registered sessions: PRED -20.39% [-21.24,-19.26] (6P+7E, 30 blocks) and -21.10% [-21.47,-20.73] (2P+7E, 20 blocks) versus B4; static P-only +28% and +82% versus PRED; blind table predictor +75% and +58% versus PRED.
- 5.2 Unseen chain orders (exploratory, overnight): 12 orders on 6P+7E, PRED -19.32% [-20.04,-18.59], faster than B4 in 12 of 12 orders; 8 orders on 2P+7E, -20.45% [-21.16,-19.78], 8 of 8. Informed hand rule -19.85% and -20.67%; PRED versus hand rule +0.66% [-0.23,+1.54] and +0.27% [-0.20,+0.77].
- 5.3 Dose-response of the hidden cost (exploratory): heavy:light denoise cost ratio 3, 7.5, 20, 60 gives PRED -2.60%, +0.57%, -6.10%, -19.86% on 4 orders per level; a follow-up with 8 further orders gives -1.31% (7.5x) and -2.89% (20x): small gains up to about 20x, large only near 60x.
- 5.3a Number of heavy chains (exploratory, 4 new orders each): PRED versus B4 -27.65% (4 of 64 heavy), -26.76% (8), about -19% to -20% (16), -3.81% (40); hand rule within 1.4 points of PRED; static P-only beats blind B4 when few chains are heavy.
- 5.3b Established list schedulers with the same learned model (exploratory, 6 further orders): HEFT -18.08% (versus PRED +1.10% [-0.53,+2.81]), PEFT -2.58%, early-binding rank-EFT -13.21%, PRED -18.97%, hand rule -19.27%, all versus B4.
- 5.4 No-harm and null workloads: uniform batch +0.45% (equivalent within +-2%), two-factor +0.95% [-0.90,+2.84], contended mixed DAG (oracle gate failed), Montage (EFT 1.6% slower than static P-only).
- 5.5 Scheduling overhead: per-dispatch decision time (PRED 15 ms per run) versus coordinator scheduling time (PRED 0.100 s, B4 0.197 s per run) and the dispatch-loop inefficiency (idle CUDA worker defeats the early exit; 97.5% of B4's select calls return None). A decision-preserving fix lowers coordinator time to 0.024 s (PRED) and 0.008 s (B4) and moves PRED's gain by 0.8 percentage points (-20.28% versus -19.47%).
- 5.6 GPU: task-level speed-ups up to about 15x (img_edges, 1024 px); no workflow-level scheduling gain established; GPU contention not established as an opportunity.
- 5.7 Remote offloading (emulation only): transfer-aware placement avoids the +31% harm of blind remote placement on a slow link (level 1) but gives no gain; at denoise level 30 the remote worker is used (1.7 tasks per run) with accurate predictions (exec 0.1457 s predicted versus 0.1464 s measured; transfer 0.0937 s versus 0.0943 s) and still makes EFT 3.78% [+2.27,+5.58] slower on the fast link. Raspberry Pi: not tested.

## 6. Discussion
- Why ordering, not prediction accuracy, explains the main gain; relation to the order-versus-accuracy literature (to be checked against the full text).
- Why ties elsewhere: dispatches with a single eligible idle worker; saturated pools; precedence.
- The oracle gate and its limits (the oracle is not an upper bound).
- What the learned model adds: parameter discovery and one-command retraining; evidence that it matches but does not beat the informed rule.

## 7. Threats to validity
Internal: dirty-tree runs, differing code hashes across sessions, short runs (about 3 s), warm-up handling. External: one machine, one workload family with a designed hidden cost, two or twelve chain orders, loopback instead of a real network, no Pi. Construct: makespan only; GPU telemetry absent. Statistical: blocks are repeated measures of few workload instances.

## 8. Conclusion and future work
Supported: scheduling by predicted cost beats static and blind rules where cost is hidden in a task parameter; ties elsewhere. Not established: advantage over informed rules, resource-state benefit, GPU-contention benefit, remote offloading benefit. Next: Raspberry Pi real-link experiment (runbook), more workload families, stronger baselines (true-cost LPT, optimal bounds), clean-tree reruns.

## Appendix
Claims registry, protocols and amendments, reproduction commands, evidence index (`EVIDENCE_INDEX.md`).
