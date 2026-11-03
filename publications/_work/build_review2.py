import sys
sys.path.insert(0, r"D:\cao project\publications\_work")
from ieee_docx import IEEEDoc, export_pdf

FIG = r"D:\cao project\publications\figures"
OUT = r"D:\cao project\publications"

d = IEEEDoc(
    "Redoing the Base Work and Identifying Gaps: Eligibility-Gated Greedy Dispatch versus Prediction-Aware Scheduling on Heterogeneous Cores",
    ["Lakshay S", "Arkkadu Bharath Reddy"],
    ["Reg. Nos. 26MAI0064, 26MAI0058 \u2014 Course: Computer Architecture and Organization", "[Institution, department, guide and e-mail to be filled by the authors]"],
    "The base work of this project is US 11,561,826 B1 ({{p_xilinx}}), which schedules the tasks of a dependency graph onto heterogeneous compute circuits through per-kernel task queues and threads, "
    "without predicting execution time. We *redo* the base work in the sense that is possible on a laptop: we re-read its claims, map its dispatch idea onto a reimplemented runtime (policy B4: eligibility-gated greedy dispatch), "
    "reimplement the classical list schedulers HEFT and PEFT ({{heft,peft}}), and evaluate all of them on real executions of a Montage workflow and of image-processing task graphs on an Intel P/E-core laptop with a CUDA GPU. "
    "The redo shows where the base idea is strong (it keeps every worker busy at a cost of milliseconds) and where it fails: blind to task cost it needed 5% to 37% more time than a rule that merely knew which tasks "
    "were heavy, and on Montage it was 48% slower than static use of the P cores. From this redo and from the literature survey we derive nine gaps and propose a *prediction-aware, work-conserving, rank-ordered dispatcher* "
    "driven by a generic runtime model learned from execution logs, evaluated with overhead accounting and paired statistics. Preliminary measured results (about 19% to 27% shorter makespan than the base idea on cost-skewed workloads, "
    "level with an informed rule, no gain where nothing is hidden) delimit the contribution honestly.",
    "base patent, reimplementation, heterogeneous scheduling, DAG, HEFT, runtime prediction, gap analysis, proposed work",
)

# ---------------------------------------------------------------- I
d.h1("Introduction")
d.para("Review 1 surveyed publications, patents and products on scheduling and offloading for heterogeneous resources and concluded that real-hardware evidence, overhead accounting, statistical reporting and informed baselines are "
       "missing. Review 2 has three aims: (i) *redo the base work*, i.e. rebuild and re-evaluate the dispatch concept of the base patent and of the classical list schedulers on our platform; (ii) *identify the gaps* "
       "that the redo and the survey expose; and (iii) state the *proposed work* that closes the gaps that can be closed on one laptop, leaving the Raspberry Pi stage as an explicit extension.")
d.para("We use the word \u201credo\u201d carefully. The patent describes a hardware/software system for FPGA-based neural-network accelerators; a laptop cannot reproduce it. What can be redone is its *scheduling idea*. An earlier "
       "project note recorded that B4 is a comparison baseline and not an implementation of the patent; this paper keeps that rule and adds what was missing: a mapping at the level of the granted claims, which we have now read, and "
       "a re-evaluation of the baseline on real workloads.")

# ---------------------------------------------------------------- II
d.h1("Base Work")
d.h2("The base patent")
d.para("US 11,561,826 B1 ({{p_xilinx}}) was filed by Xilinx on 12 Nov. 2020 and granted on 24 Jan. 2023 with 20 claims. Claim 1 recites instantiating kernel objects of kernel types that indicate compute circuits; "
       "generating a graph whose nodes are tasks assigned to kernel objects and whose edges are data dependencies; creating task queues and assigning kernel objects and tasks to them; enqueueing tasks by threads executing "
       "the kernel objects; and dequeueing tasks and activating the compute circuits. Dependent claims add blocking and non-blocking kernels (2), several graphs (3), shared queues (4\u20135), multi-threaded kernels with a "
       "configurable thread count (6\u20137), performance measurement that adjusts the thread count (8), output buffers and in-degree counters (9\u201310), utilisation-triggered scaling (11), a report function (12) and concurrent graphs (13); claims 14\u201320 "
       "restate the method as a system. No claim recites prediction of execution time, a transfer-cost model, or offloading to a remote device.")
d.h2("Base papers")
d.para("The 12 supplied papers ({{lachesis,dddqn,wang22,rodriguez,song23,gong23,sata,adprl,metarl,iov,nieto,tan25}}) define the research setting: DAG scheduling and dependent-task offloading with reinforcement learning, mostly in "
       "simulation. The closest is LACHESIS ({{lachesis}}): a GNN selects the next task and a duplication-based rule places it. We did not re-run these learned systems, because their code, simulators and training budgets are "
       "not part of the supplied material, and we say so; instead we redo the two *classical* algorithms that most of them use as baselines, HEFT and PEFT, and compare the learned-prediction approach "
       "against them on real executions.")

# ---------------------------------------------------------------- III
d.h1("Redoing the Base Work")
d.h2("Claim-level mapping")
d.table("Base patent concepts and their status in our runtime",
        ["Patent element (claims)", "Our runtime", "Status"],
        [["Kernel object of a kernel type = compute circuit (1, 14)", "Worker pools P, E, CUDA, remote; per-task eligible pools", "Mapped"],
         ["Graph: nodes = tasks, edges = data dependencies (1)", "DAG with dependency counters for every policy", "Mapped (all policies)"],
         ["Task queues per kernel; kernels assigned to queues (1)", "One global FIFO ready queue scanned for eligibility", "Approximated"],
         ["Threads enqueue/dequeue by assignment (1)", "Idle pinned worker process receives oldest eligible ready task", "Mapped (push model)"],
         ["In-degree counters decremented on completion (9\u201310)", "Readiness when all parents completed", "Mapped"],
         ["Blocking / non-blocking kernels (2, 15)", "Every task is a synchronous process call", "Not implemented"],
         ["Several graphs, shared queues (3, 4\u20135, 16\u201318)", "One DAG per run", "Not implemented"],
         ["Performance measurement adjusts thread count (8, 11)", "Fixed one worker per core; utilisation logged, not acted on", "Not implemented"],
         ["Report function with kernel statistics (12)", "Event log, run manifest, dashboard", "Partly"],
         ["FPGA compute circuits", "CPU P/E pools and a CUDA GPU worker", "Different hardware"]],
        [1.25, 1.6, 0.6], size=7)
d.para("The core of the mapping is the line between rows two and four: **a worker takes a task only if the task is declared eligible for it, and the choice among eligible idle workers uses no estimate of execution time.** "
       "We implement it as B4 with priority P, then E, then worker identifier. Its decision cost is therefore very small, which we measured (Section III-C).")
d.h2("Experimental setting of the redo")
d.para("All results are measured on one laptop (Intel Core i5-13500HX with 6 P and 8 E cores, RTX 3050 6 GB, 15.7 GB RAM, native Windows 11); workers are pinned processes, the coordinator has a reserved core, outputs "
       "are verified against a CPU reference, and conditions are run in interleaved, seeded blocks with a memory and power preflight. The effect of a policy is the paired geometric mean change of makespan against a "
       "reference within blocks with a percentile bootstrap interval (negative = faster). Workloads: the 59-task Montage mosaic (nine 160 s reprojection tasks, 36 difference fits; native Windows build, "
       "three identical sequential reference runs of 1459\u20131469 s); a uniform batch of 64 identical image chains; and *hidden-cost* batches in which 4 to 40 of 64 chains are 60 times heavier in one parameter. "
       "HEFT and PEFT ({{heft,peft}}) were reimplemented and reproduce the published worked examples (see Section III-D).")
d.figure(FIG + r"\fig_heterogeneity.png", "Measured heterogeneity of the redo platform: kernel time of three stages on a P and an E core (left) and GPU speed-up versus tile size (right).", 3.4)
d.h2("Baselines, estimators and the effect measure")
d.table("Policies and estimators of the redone runtime",
        ["Name", "Rule", "Uses prediction?"],
        [["B0", "static: all tasks on the P cores (or E cores)", "no"],
         ["B1 / B3", "round-robin / shortest queue over eligible workers", "no"],
         ["B2", "fixed task-type to pool map", "no"],
         ["B4", "first idle eligible worker, priority P, E (the patent-mapped base idea)", "no"],
         ["B5", "B4 with the ready queue ordered by bottom level (criticality)", "structure only"],
         ["EFT (E0–E4)", "earliest finish time = wait + transfer + execution; E0 constant, E1 solo profile, E2 analytic size model, E3 moving history, E4 ridge on occupancy", "yes"],
         ["HEFT, PEFT", "static list plans (upward rank / optimistic cost table)", "yes (cost matrix)"],
         ["Hand rule", "B4 with the ready queue sorted by the cost-relevant task parameter", "no (knowledge)"],
         ["Proposed", "rank-ordered, idle-worker-only dispatch with a learned generic model", "yes"]],
        [0.7, 2.15, 0.6], size=7)
d.para("The effect of a policy *c* against a reference *r* is computed per block *b* as *δ_b* = ln(*M_{c,b}* / *M_{r,b}*), where *M* is the makespan; the reported effect is (exp(mean *δ_b*) − 1) × 100%, with a "
       "percentile bootstrap interval stratified by workload instance and a sign-flip *p*-value adjusted by the Holm procedure over the confirmatory family. Equivalence claims use a ±2% margin on the interval.")
d.h2("Results of the redo")
d.table("Redo of the base dispatch idea (B4) and classical list schedulers; percentages are paired makespan changes with 95% intervals (negative = shorter)",
        ["Workload (blocks)", "Comparison", "Result", "Reading"],
        [["Montage, 59 tasks, 6P+7E (9)", "B4 vs static P-only", "+47.87% [+37.5, +54.6]", "greedy use of slow E cores hurts"],
         ["Montage", "EFT, HEFT vs static P-only", "+1.62%, +1.54% (intervals above 0)", "no headroom: every task prefers P"],
         ["Uniform batch + GPU (30)", "static P-only vs B4", "+35.9% [+34.8, +36.9]", "B4 uses all workers: 26% shorter"],
         ["Hidden cost, 16 heavy, 6P+7E (36)", "hand rule vs B4", "\u221219.85% [\u221220.7, \u221218.9]", "B4 blind to cost"],
         ["Hidden cost, 16 heavy, 6P+7E (24, 6 orders)", "HEFT, PEFT vs B4", "\u221218.08%; \u22122.58%", "HEFT strong; PEFT weak"],
         ["Hidden cost, 4 heavy (12)", "hand rule vs B4; static P-only vs B4", "\u221226.94%; \u221211.56%", "B4 worse than P-only"],
         ["Hidden cost, 40 heavy (12)", "hand rule vs B4", "\u22125.15% [\u22126.2, \u22124.0]", "gain shrinks"],
         ["Two-factor batch (40)", "hand rules vs B4", "\u22120.47%, +1.98% (n.s.)", "ties B4"]],
        [1.0, 0.95, 0.85, 0.65], span=True, size=6.5)
d.para("**B4 is a good baseline for keeping workers busy.** On the uniform batch it is 26% shorter than static use of the P cores, because it uses idle E workers and the GPU. Its decision cost is small: 7 ms of "
       "per-dispatch decision time per run for 257 tasks, 0.2 s of coordinator time (about 5% of a 4 s run). **B4 is a poor baseline when task cost differs and is invisible to the scheduler.** With 4 or 8 heavy chains "
       "among 64, B4 was 37% slower than the informed rule and even slower than P-only, because it hands a heavy chain to whichever worker is free first, including a slow E core, or starts it late. On Montage the "
       "result is the same in a different guise: every task prefers P cores by a factor of 2.3 to 3.6, so the only way to lose is to use E cores, and B4 loses 48%.")
d.para("**Why the base idea cannot do better.** Event logs of 20,046 B4 dispatches on the GPU workload show that 93.6% had exactly one eligible idle worker; only 6.4% offered a choice. An eligibility-gated dispatcher "
       "chooses the *order* implicitly (first come, first served) and the *worker* almost never. Order is exactly what the base idea does not control, and Section V shows that order is where the available gain lies.")
d.figure(FIG + r"\fig_makespan_policies.png", "Mean makespan per policy on the hidden-cost workload with 12 (left) and 8 (right) chain orders not used before; bars show geometric means with 95% intervals. B4 is the redone base idea.", 3.4)

d.h2("Redo of HEFT and PEFT")
d.para("HEFT ranks tasks by upward rank, *rank_u*(*n_i*) = *w̄_i* + max_{*n_j* ∈ succ(*n_i*)} (*c̄_{ij}* + *rank_u*(*n_j*)), and assigns each task, in rank order, to the processor with the earliest finish time using "
       "insertion into idle gaps ({{heft}}). PEFT replaces the rank by the mean of an *optimistic cost table*, *OCT*(*t_i*, *p_k*) = max_{*t_j* ∈ succ(*t_i*)} min_{*p_w*} [*OCT*(*t_j*, *p_w*) + *w*(*t_j*, *p_w*) + *c̄_{ij}*] "
       "(with *c̄_{ij}* = 0 when *p_w* = *p_k*), and picks the processor minimising the finish time plus *OCT* ({{peft}}). We implemented both as *static plans* from a cost matrix and, to compare like with like, fed them "
       "the same learned runtime model as our dispatcher. Both implementations reproduce the published worked examples through the repository code (the 10-task example of the HEFT paper, and the PEFT sample as printed in the author’s thesis chapter, "
       "where PEFT yields schedule length 122 and HEFT 133; the only tolerated difference is the tie-breaking of two equal ranks); the IEEE article of PEFT itself was not read. On 24 blocks of six unseen chain orders HEFT was 18.1% and PEFT 2.6% shorter than B4, against 19.0% for the proposed dispatcher; HEFT versus the dispatcher was +1.1% "
       "with an interval of [−0.5, +2.8] (not distinguishable), PEFT +20.2%.")
d.h2("Root cause of the base idea’s losses")
d.para("Two mechanisms explain B4’s losses. *Late start:* with a shuffled ready queue a heavy chain may be dispatched near the end of the run, so the makespan equals the time until it starts plus its own duration; the "
       "damage depends on the chain order (B4’s mean makespan varied by 0.27 s between two orders while the learned dispatcher’s did not) and is largest when few chains are heavy (Fig. 3). *Wrong core:* "
       "when all P workers are busy B4 gives the next task to an idle E worker, which is 2.8 to 3.6 times slower for these stages. A scheduler that knows or predicts task cost fixes both by serving heavy tasks first, "
       "which is why an informed hand rule and the learned dispatcher achieve the same gain.")
d.figure(FIG + r"\fig_per_order.png", "Per-order change of makespan of the proposed dispatcher against B4 (blue) and against the informed hand rule (green) for 12 orders (left) and 8 orders (right) not used before.", 3.4)
d.figure(FIG + r"\fig_dose_heavy.png", "Gain of the proposed dispatcher over B4 as the heavy:light cost ratio grows (left; 4 and 8 additional orders) and as the number of heavy chains among 64 changes (right).", 3.4)
d.h2("A defect found while redoing the baseline")
d.para("Instrumenting B4 explained a discrepancy between two overhead figures. The coordinator’s total scheduling time per run (0.19 s) was 28 times the sum of the per-dispatch decision times (7 ms). In one instrumented run "
       "B4 made 10,299 calls of its worker-selection function and 10,042 of them returned nothing: the worker pool always contained an idle CUDA worker that no task could use, so the dispatch loop never reached its early exit "
       "and scanned every ready task on every pass. A decision-preserving fix, tested in a separate adapter, cut coordinator time to 8 ms for B4 and 24 ms for the dispatcher and changed the dispatcher’s gain "
       "from 19.5% to 20.3% over B4, i.e. 0.8 percentage points. This is a reminder that any baseline redone on new infrastructure must be instrumented, not only timed.")
d.h2("Threats to the validity of the redo")
d.bullets([
    "B4 is the patent’s *idea* mapped to pools, not its FPGA system; no statement about the patent’s performance follows.",
    "HEFT and PEFT are static plans without re-planning and follow the formulas of the papers’ worked examples; the learned systems of the base papers were not rerun.",
    "One machine; runs took place with a dirty working tree and several source hashes, so sessions are never pooled in an analysis.",
    "Workloads were designed to contain a hidden cost; null workloads (Montage, uniform, two-factor) are reported with the same weight.",
])

# ---------------------------------------------------------------- IV
d.h1("Gap Identification")
d.para("Table IV merges the evidence of the survey (Review 1) with the evidence of the redo. A gap is listed only if it is supported by both a source and a measurement or a missing feature that we verified.")
d.table("Gaps identified and the contribution each motivates",
        ["Gap", "Evidence", "Addressed by the proposed work?"],
        [["G1 Real-hardware evidence is rare", "2 of 13 papers use physical devices; the base patent targets FPGAs", "Yes: P/E cores, CUDA GPU, real Montage; Pi later"],
         ["G2 Scheduler overhead rarely counted", "decision time in 4 of 13 papers; our coordinator time is 2\u20135% of a run", "Yes: two overhead metrics per run"],
         ["G3 No interval estimates", "no \u201cconfidence interval\u201d in 12 papers", "Yes: paired bootstrap, Holm, pre-registration"],
         ["G4 Missing informed baselines", "no paper tests a rule that knows the hidden cost", "Yes: hand rules, HEFT, PEFT"],
         ["G5 Base idea is cost-blind", "B4 5\u201337% slower than an informed rule", "Yes: predicted-rank ordering"],
         ["G6 Eligibility is static", "93.6% of dispatches have one idle eligible worker", "Partly: order, not worker choice, is exploited"],
         ["G7 Prediction accuracy \u2260 scheduling value", "accurate remote predictions gave no gain (emulation)", "Yes: reported separately"],
         ["G8 Generalisation untested", "one instance per setting is common", "Yes: 20 unseen orders, dose and heavy-count sweeps"],
         ["G9 Remote execution only simulated", "no real-network offloading result in the base set", "Prepared: external node path, runbook; not yet run"]],
        [1.1, 1.45, 0.9], span=True, size=6.5)

# ---------------------------------------------------------------- V
d.h1("Proposed Work")
d.h2("Objective and hypotheses")
d.para("**Objective.** Determine, by measurement on real heterogeneous hardware and with the scheduler\u2019s own cost counted, when execution-time prediction improves DAG scheduling over (a) the base idea B4, (b) static "
       "placement, (c) informed simple rules, and (d) HEFT/PEFT. The proposal is not a new learning algorithm and not a claim that prediction always wins. Falsifiable hypotheses, written before the experiments:")
d.numbered([
    "**H1** A rank-ordered, work-conserving dispatcher that uses predicted costs shortens makespan relative to B4 when task cost is hidden from size-keyed tables and several tasks compete for few fast workers.",
    "**H2** The dispatcher is not distinguishable from an informed rule that knows the cost-relevant parameter (it replaces that knowledge, it does not exceed it).",
    "**H3** Where no cost is hidden or no order can be changed, the dispatcher is equivalent to B4 within \u00b12% and does no harm.",
    "**H4** Accurate predictions are not sufficient for gain: offloading to a remote worker pays only if transfer cost is small relative to compute and the remote worker adds capacity.",
])
d.h2("Architecture of the proposal")
d.para("The proposal extends the redone runtime (Fig. 4): the coordinator keeps the dependency gating of the base idea and adds an estimator and a rank-ordered, idle-worker-only policy. A remote worker is reached through a "
       "proxy and a node process; the link is a delay shim for emulation or the real network for a Raspberry Pi. Every run writes an event log and a manifest with code and environment hashes.")
d.figure(FIG + r"\fig_architecture.png", "Architecture of the proposed system built on the redone runtime.", 3.3)
d.h2("Algorithm: predicted-rank, work-conserving dispatch")
d.para("Let *\u0177*_{s,p}(*x*) be the predicted kernel time of a task of stage *s* with numeric parameters *x* on pool *p*. The model is fitted per (stage, pool) from earlier execution logs by ridge regression on the "
       "parameters that actually vary in the logs and on their pairwise products; no stage or parameter name is coded. The rank of a task is its predicted cost plus the largest rank of its successors (HEFT-style upward rank):")
d.equation("rank(*t*) = *\u0177*(*t*) + max_{*c* \u2208 succ(*t*)} rank(*c*)", 1)
d.para("At every dispatch pass the coordinator proceeds as follows:")
d.numbered([
    "order the ready tasks by decreasing rank (ties first-come first-served);",
    "for each ready task *t* in that order, consider only *idle* workers eligible for *t*; if none exists, leave *t* queued (no early binding to a busy worker);",
    "send *t* to the idle eligible worker *w* minimising \u0177 on the pool of *w*;",
    "on completion, log the observed kernel time; an offline step refits the model from logs (one command, no code change for a new pool layout).",
])
d.para("Work conservation (step 2) and late binding are what distinguish it from earlier early-binding EFT variants that lost about 6% to a hand rule in preliminary runs; rank ordering (step 1) is the part that "
       "removes B4\u2019s late start of heavy tasks. The model\u2019s inference is a dot product of a few numbers, and the measured per-dispatch decision time is 15 ms per 257-task run.")
d.h2("Evaluation methodology")
d.bullets([
    "**Workloads:** Montage (real executables), uniform and hidden-cost image-chain batches, a contended mixed DAG, an image pipeline with an emulated remote pool; later a Raspberry Pi 5 worker.",
    "**Baselines:** B0 static P-only, B4 (base idea), informed hand rules, EFT ladder, HEFT, PEFT, an oracle replay used only as a reference.",
    "**Metrics:** makespan (primary), per-dispatch decision time, coordinator scheduling time, queue wait, transfer time, task time, output correctness.",
    "**Statistics:** paired log-ratio of makespan within interleaved blocks, percentile bootstrap, Holm correction over the confirmatory family, equivalence margin of \u00b12% for no-harm claims, designs and amendments written before runs, a claims registry re-checked against stored tables by tests.",
    "**Integrity:** memory and power preflight, one pool per session, exclusion rules written beforehand, failed runs kept and flagged, SHA-256 manifests, reproduction of tables from raw logs.",
])
d.h2("Requirements derived from the gaps")
d.table("Requirements, the gap each answers, and how it is verified",
        ["Requirement", "Gap", "Verification"],
        [["R1 run real task graphs on pinned P/E workers and a CUDA worker", "G1", "event logs record worker, pool, start and end of every task"],
         ["R2 verify every output against a CPU reference", "G1", "hash equality or stated tolerance; runs with mismatch are flagged"],
         ["R3 log two overhead metrics per run", "G2", "per-dispatch decision time and coordinator scheduling time"],
         ["R4 interleaved, seeded blocks with preflight and exclusion rules", "G3, G8", "design file hash stored in every run manifest"],
         ["R5 include informed rules, HEFT and PEFT", "G4", "policies in one registry with eligibility enforced for all"],
         ["R6 learn costs from logs without hard-coded stage names", "G5", "tests: unseen stage or pool raises instead of guessing"],
         ["R7 keep prediction accuracy and scheduling value separate", "G7", "separate offline and end-to-end analyses"],
         ["R8 provide an external-node path for a Raspberry Pi", "G9", "loopback rehearsal of the full command chain (25 runs ok)"]],
        [1.65, 0.35, 1.45], size=7)
d.h2("Run protocol and data flow")
d.para("One run builds the DAG from the workflow description, creates a fresh work directory, stages the inputs, builds the policy and estimator named by the condition, executes the graph on the shared worker pool and "
       "verifies the outputs. The coordinator writes one event per readiness, dispatch, submission, completion and failure, with the decision time attached to each dispatch. The experiment runner derives the block plan from the "
       "design seed, runs every condition once per block in random order, repeats the memory (and mains-power) preflight before every block, and writes a manifest per run with the code hash, environment hash, "
       "condition, seed, status and output hashes. Warm-up blocks are excluded by the only rule the design allows; failed or unverified runs stay in the raw data and are excluded from the primary analysis by a rule fixed in advance, "
       "with a sensitivity analysis that includes them. The analysis re-derives every table from the raw logs, and a registry test re-reads each cited number from its stored table.")
d.h2("Positioning against the closest work")
d.para("Three works are closest. IBM’s grant ({{p_ibm1}}) ranks DAG tasks with a learning agent and dispatches in rank order; our dispatcher differs by using a generic, parameter-discovering regression model, placing only on idle "
       "workers, and being evaluated against informed rules with intervals, but the overlap in *rank-ordered dispatch* is real and must be assessed by a patent professional before any filing. Lotaru ({{lotaru}}) and StarPU ({{starpu}}) "
       "supply runtime predictions to HEFT-type or StarPU schedulers; we use the same idea with a lighter model and test it on real executions, including the cases where it does not help. LACHESIS ({{lachesis}}) is the strongest "
       "learned DAG scheduler; we do not compete with it on simulated clusters and instead ask when a much cheaper model is enough.")
d.h2("Differentiation from the base patent and papers")
d.table("What is new relative to the base work",
        ["Aspect", "Base patent / papers", "Proposed work"],
        [["Execution-time prediction", "none in claims; learned policies in papers", "generic log-learned model; decision overhead measured"],
         ["Ordering of ready tasks", "FIFO per kernel queue", "predicted upward rank"],
         ["Worker choice", "eligibility + availability", "idle eligible worker with least predicted time"],
         ["Evaluation", "FPGA system (patent); simulation (papers)", "real laptop runs; paired intervals; unseen instances"],
         ["Baselines", "none stated; random/FIFO/HEFT", "adds informed hand rules and B4 as the base idea"],
         ["Claim scope", "system architecture", "empirical study of when prediction helps"]],
        [0.8, 1.2, 1.45], size=7)
d.h2("Expected contributions, novelty and risks")
d.para("We claim a measured methodology and map, not a new algorithm. Rank-ordered dispatch with a learning agent is disclosed in a granted IBM patent ({{p_ibm1}}) and HEFT-type ranks are classical, so novelty is limited to the "
       "combination, the generic parameter-discovering model, the work-conserving rule, and above all the evidence. Main risks: the headline gain comes from a workload that contains a designed hidden cost (mitigated by the "
       "no-harm and null workloads and by reporting that an informed rule performs equally); learned models were fitted on one machine; and the Raspberry Pi has not yet been measured.")
d.h2("Preliminary results and plan")
d.para("Preliminary measurements (Review 3 gives details) support H1\u2013H3: on twenty chain orders not used before the dispatcher was 19.3% (6P+7E) and 20.5% (2P+7E) shorter than B4, within \u00b11.6% of the informed rule, "
       "and within \u00b12% of B4 on the uniform batch. H4 was supported in emulation. The plan: (1) finish the paper drafts; (2) measure the Raspberry Pi 5 over a real link with the prepared runbook; (3) extend to a "
       "second workload family; (4) publish the code and data after the IPR decision.")
d.table("Hypotheses, the experiment that tests each, and the preliminary outcome",
        ["Hyp.", "Test", "Preliminary outcome (exploratory sessions)"],
        [["H1 gain over B4", "hidden-cost batches, 6P+7E and 2P+7E, unseen orders", "−19.3% [−20.0, −18.6] (12 orders); −20.5% [−21.2, −19.8] (8 orders)"],
         ["H2 equal to informed rule", "same sessions, dispatcher vs hand rule", "+0.66% [−0.2, +1.5]; +0.27% [−0.2, +0.8]"],
         ["H3 no harm", "uniform batch; two-factor batch; Montage", "uniform +0.45% [−0.3, +1.2]; two-factor +0.95% [−0.9, +2.8]; Montage no gain"],
         ["H4 accuracy is not value", "emulated remote pool, denoise level 30", "predicted vs measured remote time 0.1457 vs 0.1464 s; remote worker made EFT 3.8% slower"]],
        [0.75, 1.3, 1.4], size=7)
d.table("Work plan and status",
        ["Work package", "Status"],
        [["Runtime, estimators, policies, experiment framework, dashboard", "done; 488 automated tests pass"],
         ["Montage native build, reference runs, adapter", "done; null scheduling result reported"],
         ["Hidden-cost study, unseen orders, dose and heavy-count sweeps", "done (exploratory)"],
         ["Overhead diagnosis and dispatch-loop A/B", "done; source fix proposed, not applied"],
         ["Remote worker emulation, external-node path, Pi runbook", "done; Raspberry Pi not yet measured"],
         ["Raspberry Pi 5 real-link experiment", "planned (hardware pending)"],
         ["Second workload family; clean-tree rerun of the headline result", "planned"]],
        [2.3, 1.15], size=7)
d.h1("Conclusion")
d.para("Redoing the base work showed that eligibility-gated greedy dispatch is an economical way to keep heterogeneous workers busy but is blind to task cost, and that this blindness costs between 5% and 37% on "
       "cost-skewed workloads and 48% on Montage relative to the best simple alternative. Nine gaps were identified and a prediction-aware, work-conserving, rank-ordered dispatcher with overhead accounting and paired statistics was "
       "proposed. Its measured benefit is real but conditional, which is what the proposed study set out to quantify.")
d.references()
OUTD = OUT + r"\02_Review2_BasePaper_Gaps_ProposedWork_IEEE"
d.save(OUTD + ".docx")
pages, words = export_pdf(OUTD + ".docx", OUTD + ".pdf")
print("pages", pages, "words", words, "refs", len(d.cite_order))
