import sys
sys.path.insert(0, r"D:\cao project\publications\_work")
from ieee_docx import IEEEDoc, export_pdf

FIG = r"D:\cao project\publications\figures"
OUT = r"D:\cao project\publications"


def build(anonymous: bool, name: str):
    d = IEEEDoc(
        "How Much Prediction Is Enough? A Measured Study of Rank-Ordered, Work-Conserving Dispatch for DAG Workloads on a Hybrid CPU/GPU Laptop",
        ["Lakshay S", "Arkkadu Bharath Reddy"],
        ["Reg. Nos. 26MAI0064, 26MAI0058", "[Institution, department, guide and e-mail to be filled by the authors]"],
        "Schedulers for heterogeneous resources are increasingly learned, but they are mostly evaluated in simulation, rarely report their own overhead, and are not compared with simple rules that know the same information. "
        "We study, on real executions, when run-time prediction improves the scheduling of task graphs on a laptop with performance (P) and efficiency (E) cores and a CUDA GPU, and what the prediction costs. "
        "We build an instrumented runtime that pins one worker process per core, verifies every output against a CPU reference and logs two overhead metrics per run, and compare eligibility-gated greedy dispatch (B4, the idea of a granted "
        "patent), static placement, informed rules, HEFT, PEFT and a proposed rank-ordered, work-conserving dispatcher driven by a generic runtime model learned from logs. Using interleaved seeded blocks, paired bootstrap intervals and "
        "Holm correction, we find: on workloads in which a hidden task parameter makes a few chains 60 times more expensive, the dispatcher shortens makespan by 19.3% (6P+7E; 12 unseen chain orders) and 20.5% (2P+7E; 8 orders) against B4, "
        "but is level with a hand-written rule that knows the parameter (+0.66%, +0.27%); the gain is largest (about 27%) with few heavy chains and small (about 4%) when most are heavy, and is absent where nothing is hidden (uniform batch +0.45%, "
        "Montage, two-factor batch). HEFT with the same model matches the dispatcher; PEFT does not. Scheduling overhead is 2%\u20135% of makespan, and an inefficiency we traced in the dispatch loop explains less than one point of the gain. "
        "In an emulated remote setting, accurate predictions (error below 1%) did not produce a gain. We release the protocol, a claims registry and 488 tests.",
        "heterogeneous computing, task scheduling, runtime prediction, HEFT, P/E cores, CUDA, empirical evaluation, reproducibility",
        anonymous=anonymous,
    )
    d.h1("Introduction")
    d.para("Modern machines combine core types, accelerators and remote nodes, and applications are task graphs whose edges are data dependencies. A scheduler decides in which *order* ready tasks are served and on which *worker* each runs; "
           "when the worker is on another device the decision is an *offloading* decision with a transfer cost. Classical list schedulers such as HEFT and PEFT ({{heft,peft}}) assume execution-time estimates are available; "
           "learned schedulers ({{lachesis,adprl,tan25}}) infer a policy; runtime systems such as StarPU ({{starpu}}) calibrate performance models. Reported improvements of 11% to 27% ({{lachesis,metarl,iov,tan25}}) come from simulators, "
           "none of the 12 papers we examined reports a confidence interval, measured decision time appears in few, and none compares against a rule that merely knows which tasks are expensive.")
    d.para("This paper asks a practical question: *how much prediction is enough to improve real scheduling once its cost is counted?* We make four contributions. (1) An instrumented, reproducible runtime and experiment framework for real task graphs "
           "on P/E cores, a CUDA worker and an external worker. (2) A set of policies spanning the base idea (eligibility-gated greedy dispatch, mapped from US 11,561,826 B1 ({{p_xilinx}})), informed rules, HEFT, PEFT and a "
           "rank-ordered, work-conserving dispatcher with a generic runtime model learned from logs. (3) A measured map of when the dispatcher helps, ties or cannot help, with intervals, unseen workload instances and informed baselines. "
           "(4) A diagnosis of scheduling overhead and of the gap between prediction accuracy and scheduling value. We do not claim a new learning algorithm or superiority over learned DRL schedulers, which we did not run.")
    d.h1("Background and Related Work")
    d.para("**Learned DAG scheduling.** LACHESIS ({{lachesis}}) combines a GNN-based task selector with a duplication-based placement rule; subsequent work uses GCN or Transformer encoders with PPO ({{song23,tan25}}) or end-to-end DQN, actor-critic and "
           "meta-RL formulations for edge offloading ({{dddqn,wang22,gong23,sata,cao24,nieto,adprl,metarl,iov}}). Only {{rodriguez}} (CPU+FPGA) and {{adprl}} (a three-board Jetson testbed) use physical devices. "
           "**Prediction-driven scheduling.** {{lotaru}} predicts task runtimes and drives HEFT in simulation; {{ilyushkin}} report that, under high utilisation, order matters more than estimate accuracy; {{lureda}} place AI tools with an LLM agent on real "
           "CPU/GPU hardware against HEFT and StarPU on small DAGs. **Patents and products.** The base patent ({{p_xilinx}}) claims task graphs, per-kernel queues and thread-based dispatch without prediction; IBM\u2019s grants ({{p_ibm1,p_ibm2}}) disclose a learning agent that ranks DAG tasks "
           "and schedules with execution estimates, Samsung\u2019s ({{p_samsung}}) predicts durations on heterogeneous cores, and Intel\u2019s ({{p_intel}}) profiles CPU/GPU throughput. Operating systems place threads using hardware feedback or energy models "
           "({{intel_td,linux_eas,ms_qos}}); cluster products schedule against declared resources ({{k8s,aws_batch,slurm,ray}}). None of the cited product pages describes execution-time prediction in the scheduler.")
    d.h1("System and Method")
    d.h2("Runtime")
    d.para("The coordinator converts a workflow (a Pegasus YAML for Montage ({{montage,wfcommons}}), or an in-memory image-chain generator) into a DAG, keeps a FIFO ready queue and dispatches tasks to worker processes, each pinned to one logical "
           "processor, with a reserved core for the coordinator (Fig. 1). A CUDA worker runs GPU variants of three image stages; a remote worker is a proxy process plus a node process reached over TCP, on a local core behind a delay shim (emulation) or on another machine. "
           "Every policy honours per-task eligible pools through one helper and a violation raises an error. Tasks become ready when all parents completed (the in-degree gating of the base patent). Montage jobs run as external commands "
           "without a shell, with timeouts, process-tree kill, declared-output checks and hashing. Every output is compared with a CPU reference; the event log records each dispatch with its decision time.")
    d.figure(FIG + r"\fig_architecture.png", "Architecture of the framework.", 3.3)
    d.h2("Policies and runtime model")
    d.para("B0 places all work on the P cores. **B4** gives each ready task, in FIFO order, to the first idle eligible worker (priority P, then E); it uses no estimate and is the mapping of the patent\u2019s dispatch idea ({{p_xilinx}}). A *hand rule* is B4 with the ready queue sorted by the "
           "cost-relevant parameter, i.e. it encodes knowledge a person has. EFT policies minimise wait + transfer + execution time; HEFT and PEFT are static list plans ({{heft,peft}}) that reproduce the published worked examples in our tests. "
           "The **proposed dispatcher** orders ready tasks by predicted upward rank, rank(*t*) = \u0177(*t*) + max_{*c* \u2208 succ(*t*)} rank(*c*), binds a task only to an *idle* eligible worker (work-conserving, no early binding) and chooses the idle worker with the smallest predicted time. "
           "The model fits, per (stage, pool), ridge regression on the numeric task parameters and size that vary in the logs and on their pairwise products; it names no stage or parameter, refuses an unseen stage or pool, and is refitted by one command for a new pool layout.")
    d.para("**Model fitting protocol.** The model is fitted from *coverage sessions*, runs of the workload on chain orders that are never used for evaluation, with every pool executed under varied occupancy so that each (stage, pool) pair has labels. "
           "Features are decision-time safe (task parameters are known when the task is ready); offline features are reconstructed from the logged decision context and a parity test enforces equality with the online features. "
           "On a held-out two-factor session the heavy classes were predicted within 8% of the measured time (0.605 s predicted versus 0.565 s measured; 0.122 s versus 0.112 s), the lightest class poorly (17.6 ms versus 4.1 ms), which does not affect makespan. "
           "Inference is a dot product of a few numbers.")
    d.figure(FIG + r"\dashboard_compare.jpg", "Dashboard view of two runs of the same chain order: B4 (3858.9 ms) and the dispatcher (3097.0 ms), with placement, scheduling time and output-hash check.", 3.4)
    d.table("Policies compared",
            ["Policy", "Rule", "Prediction"],
            [["B0", "all tasks on the P cores", "no"],
             ["B4 (base idea)", "first idle eligible worker, FIFO order, priority P then E", "no"],
             ["Hand rule", "B4 with ready queue sorted by the cost-relevant parameter", "no (human knowledge)"],
             ["EFT (E1–E4)", "earliest finish time with solo profile, history or ridge estimates; early binding", "yes"],
             ["HEFT, PEFT", "static list plans from a cost matrix (upward rank / optimistic cost table)", "yes"],
             ["Dispatcher (proposed)", "predicted-rank order; idle eligible worker with least predicted time", "yes (generic model)"]],
            [0.9, 1.9, 0.65], size=7)
    d.para("At each *dispatch pass* the coordinator (1) takes the ready tasks and lets the policy reorder them, (2) asks the policy for a worker for each task in turn (a late-binding policy may only name an idle eligible worker), (3) checks eligibility and idleness, binds the task and logs "
           "the elapsed decision time, and (4) stops when no worker is idle or all ready tasks were visited. The time spent in steps 1–2 is accumulated as *scheduling time*; the time of each successful call is the *decision time* of that dispatch.")
    d.h1("Experimental Setup")
    d.para("**Machine.** Intel Core i5-13500HX (6 P, 8 E cores), NVIDIA RTX 3050 6 GB, 15.7 GB RAM, native Windows 11; sessions record an environment hash and are never pooled across machines. **Workloads.** (i) The 59-task Montage mosaic (native build, nine DSS2 images; "
           "three sequential references 1459\u20131469 s with identical outputs, nine reprojections of about 160 s dominate). (ii) A uniform batch of 64 identical image chains. (iii) *Hidden-cost* batches: 64 chains of 512-pixel images in which *H* are heavy (120 denoise iterations) "
           "and the rest light (2); the heavy parameter is invisible to a size-keyed table. (iv) A two-factor batch and a contended mixed DAG. (v) An image pipeline with remote-eligible stages for the remote experiments.")
    d.figure(FIG + r"\fig_heterogeneity.png", "Measured heterogeneity: stage kernel time on a P and an E core (left); GPU speed-up versus tile size (right).", 3.4)
    d.table("Montage reference runs (three identical sequential runs; median wall time per task type)",
            ["Task type", "n", "Median (s)", "Range (s)"],
            [["mProject", "27", "160.57", "141.02–169.89"], ["mDiffFit", "108", "0.251", "0.041–1.036"], ["mBackground", "27", "0.336", "0.303–0.610"],
             ["mConcatFit, mBgModel, mImgtbl, mAdd, mViewer", "3 each", "0.207, 0.379, 0.094, 0.870, 4.157", "–"], ["Total (s)", "3 runs", "1459.4, 1467.1, 1469.3", "outputs identical"]],
            [1.5, 0.4, 0.9, 0.65], size=7)
    d.para("**Protocol and statistics.** Conditions run once per block in seeded random order, with free-memory and mains-power preflight, one worker pool for all conditions, a warm-up block, exclusion rules fixed in the design, and failed runs kept and flagged. "
           "The effect of a condition against a reference is (exp(mean ln(*M_c*/*M_r*)) \u2212 1) \u00d7 100% over paired blocks (negative = shorter), with a percentile bootstrap interval stratified by chain order, Holm-adjusted sign-flip *p*-values over the confirmatory family and "
           "a \u00b12% equivalence margin. Registered sessions were pre-registered with amendments; overnight sessions are exploratory, with plan and design hash written before each run and one execution per design. Evaluation orders are disjoint from the orders used to fit the model.")
    d.para("**Sensitivity.** With 36 paired blocks the 95% interval half-width of a contrast against B4 is about 1.5 points and the minimum detectable effect at 80% power about 2.2%; sessions of 12 blocks over four orders are less precise (half-widths from 0.7 to 6.5 points) and "
           "are used to show direction and order of magnitude, not to rank near-equal conditions. Because the 10 or 36 blocks of a session repeat a few workload instances, intervals describe run-to-run noise, not variation across workloads, which is why unseen orders were added.")
    d.h1("Results")
    d.figure(FIG + r"\fig_makespan_policies.png", "Mean makespan by policy on unseen chain orders (geometric means with 95% intervals): 12 orders on 6P+7E (left), 8 orders on 2P+7E (right).", 3.4)
    d.h2("Hidden cost: ordering is what matters")
    d.para("Table I gives the exploratory sessions on chain orders never used before; registered sessions with two orders each gave \u221220.39% (30 blocks, 6P+7E) and \u221221.10% (20 blocks, 2P+7E). The dispatcher beat B4 in all 12 and all 8 orders (Fig. 2). "
           "The hand rule that sorts by the heavy parameter, without any model, achieved the same gain, and the dispatcher differed from it by less than 1.6% in either direction (intervals inside \u00b12%). Static P-only was 3.7% slower than B4 on 6P+7E but 45.8% slower on 2P+7E, where fast cores are scarce.")
    d.table("Hidden-cost sessions on unseen chain orders (exploratory; effects vs B4; negative = shorter)",
            ["Session", "Blocks / orders", "Dispatcher", "Hand rule", "Disp. vs rule"],
            [["6P+7E, 16 heavy", "36 / 12", "\u221219.32% [\u221220.0, \u221218.6]", "\u221219.85%", "+0.66% [\u22120.2, +1.5]"],
             ["2P+7E, 16 heavy", "24 / 8", "\u221220.45% [\u221221.2, \u221219.8]", "\u221220.67%", "+0.27% [\u22120.2, +0.8]"],
             ["6P+7E, 4 heavy", "12 / 4", "\u221227.65% [\u221234.0, \u221218.7]", "\u221226.94%", "\u22120.98% [\u22123.1, +1.2]"],
             ["6P+7E, 8 heavy", "12 / 4", "\u221226.76% [\u221227.9, \u221225.7]", "\u221226.93%", "+0.24% [\u22120.4, +1.0]"],
             ["6P+7E, 40 heavy", "12 / 4", "\u22123.81% [\u22125.1, \u22121.9]", "\u22125.15%", "+1.42% [\u22120.7, +4.5]"]],
            [0.85, 0.55, 1.05, 0.55, 0.85], span=True, size=7)
    d.figure(FIG + r"\fig_per_order.png", "Change in makespan of the dispatcher against B4 (blue) and the hand rule (green) for each unseen chain order.", 3.4)
    d.para("**Cost ratio and heavy-chain count.** With 16 heavy chains the gain is about 1\u20133% for heavy:light denoise cost ratios of 3 to 20 (four orders per point plus a follow-up with eight further orders: \u22122.6%, \u22121.3%, \u22122.9%) and \u221219.9% at 60. "
           "With the ratio fixed at 60 it is largest with few heavy chains and falls as they become the majority (Fig. 3); with 4 or 8 heavy chains static P-only even beats blind B4 (\u221211.6%, \u221215.8%), because B4 hands heavy chains to slow cores. "
           "This is consistent with a tail effect: blind dispatch starts a heavy chain late or on an E core, which is 2.8\u20133.6 times slower for these stages.")
    d.figure(FIG + r"\fig_dose_heavy.png", "Gain over B4 versus heavy:light cost ratio (left) and number of heavy chains among 64 (right).", 3.4)
    d.h2("Where nothing can be won")
    d.para("On Montage predictive EFT variants and HEFT were 1.4%\u20131.7% slower than static P-only and B4 47.9% slower (9 blocks, registered): all tasks prefer P cores by 2.3\u20133.6\u00d7 and nine equal tasks dominate. On a uniform batch the dispatcher was equivalent to B4 (+0.45% [\u22120.25, +1.22]) and "
           "B4 itself was 26% shorter than static P-only. On a two-factor batch (size \u00d7 iterations) the dispatcher was not faster than B4 (+0.95% [\u22120.9, +2.8]) and informed hand rules also tied B4. In 20,046 stored B4 dispatches with the GPU worker, 93.6% had exactly one eligible "
           "idle worker, so placement was forced and only order could matter. A resource-state-aware variant with an oracle gate (\u22655% headroom required) failed the gate on a contended DAG.")
    d.h2("Published list schedulers and overhead")
    d.para("With the same learned model on six further orders (24 blocks), HEFT gave \u221218.08% and PEFT \u22122.58% against B4, early-binding rank-EFT \u221213.21%, the dispatcher \u221218.97%; HEFT versus dispatcher +1.10% [\u22120.53, +2.81], PEFT +20.23%. "
           "**Overhead** has two definitions: per-dispatch decision time (6.8 ms per run for B4, 15.5 ms for the dispatcher, about 0.5% of makespan) and coordinator scheduling time (0.197 s and 0.100 s). The difference came from calls that returned nothing: "
           "an idle CUDA worker that no task can use defeats the dispatch loop\u2019s early exit, and 10,042 of 10,299 selection calls of B4 returned nothing. A decision-preserving fix in a separate adapter cut coordinator time to 8 ms and 24 ms and moved the dispatcher\u2019s gain "
           "from \u221219.47% to \u221220.28%, i.e. 0.8 points (78 runs verified). Overhead therefore costs 2%\u20135% of these 3\u20139 s runs but does not explain the result.")
    d.figure(FIG + r"\fig_overhead.png", "Per-dispatch decision time versus coordinator scheduling time, before and after the dispatch-loop fix.", 3.4)
    d.h2("GPU and remote execution")
    d.para("At task level the GPU is up to 15.1\u00d7 faster for an edge-detection stage at 1024 px and 5.2\u00d7 for feature extraction (outputs equal within tolerance), 1.4\u00d7 for denoise; no workflow-level gain from CPU/GPU placement was established. "
           "For remote execution we used an emulated worker (a node on one local E core behind a loopback socket and a delay shim). At a compute level where transfer is small (denoise with 30 iterations) the predictive policy used the worker (1.7 tasks per run) with accurate predictions "
           "(predicted vs measured execution 0.1457 vs 0.1464 s; transfer 0.0937 vs 0.0943 s; 44 placements) and was nevertheless 3.78% [+2.27, +5.58] *slower* than without it (Fig. 4); at level 1 blind remote placement on a slow link cost 31%, which transfer-aware placement avoided. "
           "Prediction accuracy did not become scheduling value. The external-node path was validated over loopback (25 runs) and is ready for a Raspberry Pi 5.")
    d.figure(FIG + r"\fig_remote.png", "Emulated remote worker: effect on EFT makespan at compute levels 1 (registered) and 30 (overnight).", 3.4)
    d.table("Registered (pre-registered) results used as anchors; negative = shorter than the reference",
            ["Workload", "Comparison", "Effect", "Status"],
            [["Uniform batch + GPU (30 blocks)", "predictive EFT vs static P-only", "−27.56%", "supported"],
             ["Uniform batch", "dispatcher vs B4", "−0.45% (equivalent within ±2%)", "no harm"],
             ["Hidden cost 6P+7E (30 blocks)", "dispatcher vs B4; vs hand rule", "−20.39%; −1.54%", "supported; not resolved"],
             ["Hidden cost 2P+7E (20 blocks, model refit)", "dispatcher vs B4; vs hand rule", "−21.10%; +0.38%", "supported; equivalent"],
             ["Two-factor (40 blocks)", "dispatcher vs B4", "+0.95% [−0.9, +2.8]", "not supported"],
             ["Montage (9 blocks)", "B4; predictive EFT vs static P-only", "+47.87%; +1.62%", "null result"],
             ["Contended mixed DAG (12 blocks)", "oracle gate", "B4 1.24% faster than oracle", "gate failed"]],
            [1.3, 1.3, 0.85, 0.7], span=True, size=7)
    d.table("Guidance derived from the measurements",
            ["Situation", "Expected benefit of prediction-aware dispatch over blind greedy"],
            [["Few heavy tasks (about 6%–12% of tasks), large cost ratio (≥60×), scarce fast cores", "large (about 27% here); an informed rule gets the same"],
             ["Many heavy tasks (about 60%) or small cost ratio (3–20×)", "small (about 1%–5%)"],
             ["No hidden cost, identical tasks", "none; equivalent to B4 within ±2%"],
             ["Every task prefers the same core type (Montage)", "none; use the fast cores only"],
             ["Remote worker behind a link", "none in the emulated regimes tested; measure on the real link first"]],
            [2.2, 1.9], size=7)
    d.h1("Discussion")
    d.para("**What prediction buys.** The main effect is ordering: serving predicted-heavy work first removes the tail that blind dispatch creates. An informed rule gets the same gain, so the learned model\u2019s value is that it replaces knowledge a person would hard-code and is "
           "retrained by one command for a new pool layout, as shown for 2 P + 7 E. The result is consistent with the observation of {{ilyushkin}} that order can matter more than estimate accuracy, now on real executions, and with {{lotaru}} that cheap models suffice for list scheduling. "
           "**What it does not buy.** Not beyond an informed rule, not on workloads without a hidden or reorderable cost, and not through accurate remote predictions alone.")
    d.para("**Threats to validity.** The workload family was designed to contain a hidden cost; results are from one machine; runs were made with a dirty working tree and several source hashes, so sessions are never pooled; the overnight sessions are exploratory; the first run after the "
           "CPU reference computation of a new order is about 2% slower; HEFT and PEFT are static plans verified on the papers\u2019 worked examples; remote results are emulation; learned DRL schedulers were not rerun. "
           "**Reproducibility.** Every session stores design, environment and code hashes; a script re-derives each table from the raw logs; 50 claims are re-read from their tables by a test; 488 tests pass.")
    d.para("**Practical reading.** For an engineer choosing a scheduler for a small hybrid machine, the measurements suggest three steps: first check whether tasks differ in cost by a factor that size alone does not reveal, and how many tasks compete for the fast cores; "
           "if they do, order the queue by (predicted) cost before worrying about placement; and only then consider a learned model, because a one-line rule that sorts by the right parameter was as good in every setting we tried. A learned model is the right tool when the parameter "
           "is not known in advance or changes with the machine, since it is refitted from logs. **Baselines.** A fair evaluation of a learned scheduler needs an informed rule, HEFT-type plans, intervals and the scheduler’s own overhead; "
           "all four changed conclusions in this study (the rule removed the apparent benefit of learning; HEFT matched the dispatcher; overhead turned out to be 2%–5%).")
    d.para("**Ordering versus binding.** Two design choices are bundled in the dispatcher and the data separate them. Ordering by predicted rank with early binding to the earliest-finish worker (rank-ordered EFT) gave −13.21% against B4, whereas ordering plus idle-only (late) binding gave −18.97% on the same six orders, "
           "so late binding contributes about six of the nineteen points; the static HEFT plan reaches −18.08% with insertion into idle gaps, which explains why it is level with the dispatcher on a workload of independent chains where a plan can be exact. A plan is brittle when durations are mispredicted and a dispatcher is not; "
           "we did not test mispredicted durations in a timed session and make no claim about that case.")
    d.para("**Relation to the base work and to learned ranking.** The base patent {{p_xilinx}} gates dispatch on eligibility and dependency counters and recites no prediction; our B4 is a comparison baseline mapped from it, not an implementation of the patent. Learned ranking of DAG tasks on heterogeneous hardware is disclosed in {{p_ibm1}}; "
           "the contribution here is therefore not the idea of ranking but a measured, overhead-accounted comparison of a log-fitted generic model with an informed rule and with HEFT and PEFT on real executions. This framing is deliberate: it is what the evidence supports.")
    d.para("**Disclosure.** Software, analysis scripts and parts of the text were produced with the help of an AI coding assistant under the authors’ direction; every number was checked against stored result files. [Authors to confirm the wording required by the venue.]")
    d.h2("Reproduction")
    d.para("Each reported table can be re-derived from the raw logs with one command (`scripts/reproduce_subset.py --analysis-dir <dir> --log <file>`), which checks event-log and manifest hashes and recomputes the effects; "
           "a bounded reproduction of the headline comparison (11 blocks, about six minutes) runs from a design file with `scripts/run_experiment.py` and the study adapter, followed by `scripts/analyze_experiment.py`. "
           "The repository package lists the exact commands, the environment lock file and the evidence index with SHA-256 values.")
    d.h1("Conclusion")
    d.para("On a hybrid laptop, rank-ordered, work-conserving dispatch with a cheap learned model shortens makespan by about 19\u201327% relative to eligibility-gated greedy dispatch when a hidden cost makes ordering decisive, matches an informed rule, "
           "does no harm elsewhere and costs about 15 ms per run to decide. Its benefit shrinks with the cost ratio and with the number of heavy tasks, and accurate predictions alone do not justify offloading. Future work: a real Raspberry Pi worker over a real link, "
           "a second workload family, the dispatch-loop fix in the source, and a clean-tree rerun of the headline experiment.")
    if not anonymous:
        d.h1_plain("Availability")
        d.para("The code, protocols, claims registry and result tables are prepared for release after the authors\u2019 decision on intellectual-property protection; see the accompanying repository package. [Repository URL to be inserted by the authors.]")
    else:
        d.h1_plain("Availability")
        d.para("An anonymised artefact (code, protocols, claims registry and result tables) will be provided to reviewers on request.")
    d.references()
    o = OUT + "\\" + name
    d.save(o + ".docx")
    pages, words = export_pdf(o + ".docx", o + ".pdf")
    print(name, "pages", pages, "words", words, "refs", len(d.cite_order))


build(False, "06_Final_IEEE_Paper_Draft")
build(True, "06b_Final_IEEE_Paper_Anonymous_for_Double_Blind_Review")
