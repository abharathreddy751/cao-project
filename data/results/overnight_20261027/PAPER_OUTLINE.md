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
- Threats to the method: workload designed to have a hidden cost; two chain orders per configuration in the registered sessions; runs with a dirty working tree; one machine.

## 5. Results (numbers from `RESULTS_TABLE.csv`; no number here that is not in a table row)
- 5.1 Hidden-cost workload (6P+7E and 2P+7E): learned policy and hand rule both about 20% faster than B4; learned policy level with or slightly behind the hand rule.
- 5.2 Unseen chain orders (overnight exploratory run, 12 new orders): see the generalisation result.
- 5.3 No-harm and null workloads: uniform, two-factor, contended mixed DAG, Montage.
- 5.4 Scheduling overhead: per-dispatch versus total.
- 5.5 GPU: task-level speed-ups versus end-to-end effect; GPU contention (not established).
- 5.6 Remote offloading (emulation only): transfer-aware policy avoids the harm of blind remote placement but gains nothing in the tested regime.

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
