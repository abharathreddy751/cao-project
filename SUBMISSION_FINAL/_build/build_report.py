import sys
sys.path.insert(0, r"D:\cao project\publications\_work")
from report_docx import Report
from ieee_docx import export_pdf

FIG = r"D:\cao project\publications\figures"
OUT = r"D:\cao project\publications"

r = Report()

# ------------------------------------------------------------------ title page
r.center("", 12, after=40)
r.center("FINAL PROJECT REPORT", 14, bold=True, after=14)
r.center("Prediction-Aware Dynamic Task Scheduling and Offloading on Heterogeneous Hardware", 22, bold=True, after=10)
r.center("An AI-assisted heterogeneous computing framework: design, implementation, measured evaluation and reproducible evidence", 13, italic=True, after=36)
r.center("Course: Computer Architecture and Organization", 12, after=4)
r.center("Submitted by", 11, italic=True, before=16, after=4)
r.center("Lakshay S (Reg. No. 26MAI0064)", 12, after=2)
r.center("Arkkadu Bharath Reddy (Reg. No. 26MAI0058)", 12, after=22)
r.center("Guide: [name and designation to be filled by the authors]", 11, after=2)
r.center("Institution / Department: [to be filled by the authors]", 11, after=2)
r.center("Contact e-mail: [to be filled by the authors]", 11, after=24)
r.center("Date of this version: 1 November 2026", 11, after=2)
r.center("Repository: branch revival/resource-state-aware (not pushed; see GITHUB_PUSH_INSTRUCTIONS.md)", 10, italic=True)

r.page_break()
r.center("Declaration", 14, bold=True, after=10)
r.para("We declare that this report describes the work carried out for the project named on the title page, that all measured numbers in it are read from the result files stored in the project repository "
       "(each table and figure names the source), that nothing in it is simulated unless labelled *simulation* or *emulation*, and that statements about literature, patents and products are limited to what the "
       "cited documents state. Items that were not measured are listed as *not established* or *not tested* and are not presented as results.")
r.para("Signatures of the authors and of the guide, and the institutional certificate, are to be added by the authors before submission.")
r.center("", 12, after=20)
r.center("Evidence labels used throughout", 12, bold=True, after=6)
r.table("Meaning of the evidence labels",
        ["Label", "Meaning"],
        [["real", "executed on the project laptop (Intel Core i5-13500HX, RTX 3050 6 GB, Windows 11); outputs verified against a CPU reference"],
         ["emulation", "executed on the laptop with a remote worker replaced by a local process behind a loopback socket and a delay shim; never presented as a real network or device"],
         ["simulation", "computed from a model without executing tasks (used only for opportunity bounds, labelled where used)"],
         ["plan", "written down but not run (e.g., the Raspberry Pi validation)"],
         ["exploratory / registered", "registered sessions have a design hash and hypotheses fixed before the run; exploratory sessions have the plan and design hash written before the run but are not part of the registered set"]],
        [1.3, 5.0])

r.page_break()
r.center("Abstract", 14, bold=True, after=10)
r.para("Modern laptops, edge boards and servers combine fast and slow cores, GPUs and remote nodes. Deciding where, and in what order, the tasks of a dependency graph (DAG) run is a first-order performance problem, and a "
       "large literature trains learned schedulers for it, nearly always in simulation. This project builds a framework that executes real task graphs on pinned performance-core and efficiency-core worker processes, a CUDA "
       "worker and an optional remote worker; logs every dispatch together with its decision time; verifies every output against a CPU reference; and compares scheduling policies in interleaved, seeded blocks with "
       "paired bootstrap intervals. The base idea, mapped from US 11,561,826 B1 (Xilinx), is eligibility-gated greedy dispatch (policy B4). We re-implement it, the list schedulers HEFT and PEFT and several informed "
       "rules, and propose a rank-ordered, work-conserving dispatcher that uses a runtime model learned from the execution logs.")
r.para("On a workload in which 16 of 64 image chains are 60 times more expensive in a parameter that size-keyed tables cannot see, the proposed dispatcher shortened the makespan by 19.3% on 12 chain orders never used "
       "before (6 P + 7 E workers) and by 20.5% on 8 orders (2 P + 7 E) relative to B4, was faster in every one of the 20 orders, and was level with an informed hand rule (+0.66% and +0.27%). Where nothing is hidden it is "
       "equivalent to B4 (+0.45%), on the Montage mosaic no policy can beat static use of the P cores and B4 is 47.9% slower, and an emulated remote worker gave no gain despite accurate predictions. The gain depends on the "
       "cost ratio (about 1% to 3% up to a ratio of 20, about 20% at 60) and on the number of heavy chains (about 27% with 4 or 8 of 64, 4% with 40). A scheduling-overhead discrepancy was traced to an idle CUDA worker "
       "defeating the dispatch loop's early exit; fixing it moves the result by under one percentage point. The framework has 488 passing tests, a registry of 50 claims checked against stored tables, and a validated "
       "path for a Raspberry Pi 5 worker whose measurement is the next step. The report states precisely what is established, what is not, and why.")
r.para("**Keywords:** heterogeneous computing, DAG scheduling, task offloading, runtime prediction, HEFT, PEFT, P/E cores, CUDA, reproducibility, patents.")

r.page_break()
r.center("Contents", 14, bold=True, after=10)
r.toc()

# ------------------------------------------------------------------ 1
r.chapter("Introduction")
r.section("Background")
r.para("*Heterogeneous computing* combines processing elements with different speeds, memories and power behaviour in one system: performance (P) and efficiency (E) cores in a laptop processor, a discrete GPU, "
       "an FPGA, a single-board computer such as a Raspberry Pi 5 ({{rpi5}}), or a remote edge or cloud node. Applications are rarely one kernel. They are workflows or task graphs: directed acyclic graphs whose nodes are "
       "tasks and whose edges are data dependencies, for example the Montage astronomy mosaic workflow ({{montage,wfcommons}}) or image-analysis pipelines.")
r.para("A *scheduler* decides, whenever tasks become ready, the **order** in which ready tasks are served and the **placement** of each task on a worker. *Offloading* is the case where the candidate worker is on another "
       "device and a transfer cost is paid. Both decisions rest on three kinds of information: the structure of the graph, the state of the resources (busy, idle, reachable) and an estimate of how long each task takes on each "
       "resource. Classical list schedulers such as HEFT and PEFT ({{heft,peft}}) assume the estimates are given; learned schedulers ({{lachesis,sata,adprl}}) infer a policy from interaction; runtime systems such as StarPU ({{starpu}}) "
       "calibrate performance models per task.")
r.section("Problem statement")
r.para("Existing work leaves a gap that matters for anyone who wants to build such a scheduler on real hardware. Of the 13 recent papers surveyed in Chapter 3, only two touch physical devices, none reports a confidence "
       "interval, decision overhead is reported in four, and none compares with an *informed* simple rule, so the benefit attributed to learning cannot be separated from the benefit of merely knowing which tasks are expensive. "
       "The project therefore asks one question: **how much prediction of task execution time is enough to improve real scheduling on a hybrid CPU/GPU(+remote) system, once the cost of prediction and of the scheduler "
       "itself is counted, and compared with the base dispatch idea and with informed baselines?**")
r.section("Objectives")
r.numbered([
    "Build a reproducible framework that executes real task graphs on P cores, E cores, a CUDA GPU and a remote worker, and logs every scheduling decision and its cost.",
    "Reimplement the base idea (eligibility-gated greedy dispatch, B4), HEFT, PEFT and informed rules as baselines.",
    "Propose and evaluate a prediction-aware dispatcher with a generic runtime model learned from logs.",
    "Measure when prediction helps, when it does not, and what the scheduler itself costs, with paired statistics and chain orders not used for fitting.",
    "Prepare and rehearse the path for a real remote worker (Raspberry Pi) and report honestly what has not been measured.",
    "Document the result as reviews, a paper, a report and a demonstration, and identify suitable publication and IPR routes.",
])
r.section("Scope and non-goals")
r.para("The work covers one laptop, two workload families (a real Montage mosaic and designed image-chain batches), and an emulated remote worker. It does not claim superiority over deep-reinforcement-learning "
       "schedulers, which were not run; it does not claim a general percentage gain; it does not report Raspberry Pi results; and it is not a freedom-to-operate analysis of any patent.")
r.section("Contributions")
r.bullets([
    "A framework of about 11,900 lines of Python in the runtime, 8,200 in scripts and 488 automated tests that runs and verifies real task graphs on P/E cores, CUDA and a remote path.",
    "A policy and estimator family including the base idea B4, the EFT ladder, HEFT, PEFT, informed rules and the proposed *PredictedRankGreedy* with a log-fitted *ParamModel*.",
    "A measured map of when prediction helps: ordering decides; the gain depends on cost ratio and on the number of heavy tasks; it is level with an informed rule; it vanishes where nothing is hidden.",
    "A diagnosis of scheduling overhead with two metrics, including a defect (idle CUDA worker defeats the dispatch loop's early exit) quantified and shown not to explain the gain.",
    "A claims registry (50 claims) tied to stored result tables by a test, and a validated Raspberry Pi path.",
])
r.section("Organisation of the report")
r.para("Chapter 2 substantiates the problem with statistics; Chapters 3 and 4 compare publications, patents, products and trends; Chapter 5 redoes the base work; Chapter 6 states the gaps and the proposed work; "
       "Chapters 7 and 8 describe the implementation and the methodology; Chapter 9 gives the results; Chapter 10 discusses them; Chapter 11 contrasts the existing and proposed implementations; Chapter 12 covers testing and "
       "reproducibility; Chapter 13 explains how to demonstrate the project; Chapter 14 summarises publication and IPR options; Chapter 15 concludes. Appendices list the file map, glossary and claim status.")

# ------------------------------------------------------------------ 2
r.chapter("Domain and Problem Substantiation")
r.section("Why scheduling on heterogeneous resources matters")
r.para("Four independent trends make the problem important. Each figure was checked against its source; where only a secondary report was available it is marked.")
r.table("Verified statistics that motivate the problem",
        ["Indicator", "Value", "Source"],
        [["Data-centre electricity use", "about 415 TWh in 2024 (about 1.5% of global electricity); about 945 TWh by 2030 in the IEA base case", "{{iea}} (secondary reports of the IEA report)"],
         ["Accelerated HPC systems (TOP500, June 2025)", "232 of 500 systems (46.4%) use accelerators; they hold 59.7% of cores and about 86.2% of peak FP64 flops", "{{top500}} (secondary analysis)"],
         ["Connected IoT devices", "18.5 billion at end-2024 (+12%); 21.1 billion in 2025 (+14%); about 39 billion forecast for 2030", "{{iotanalytics}}"],
         ["Under-utilised clusters", "Alibaba co-located cluster (1,313 machines): over 80% of the time at 10 to 30% CPU use; Google traces: 20 to 40% most of the time", "{{cheng18}} (full text read)"],
         ["Hybrid cores in client CPUs", "Intel Thread Director listed for 12th, 13th and 14th generation Core processors", "{{intel_td}}"]],
        [1.6, 3.4, 1.3])
r.para("The first three rows show that the amount of heterogeneous capacity is large and growing. The fourth shows that capacity is often wasted: a cluster that spends most of its time at 10 to 30% CPU use is limited "
       "not by hardware but by how work is placed. Scheduling quality therefore translates into energy, cost and latency.")
r.section("Measured heterogeneity on the project machine")
r.para("The test bed is a laptop with an Intel Core i5-13500HX (6 P cores, 8 E cores), an RTX 3050 6 GB GPU and 15.7 GB RAM running native Windows 11. A 512-pixel denoise task with 30 iterations takes 156 ms on a "
       "pinned P core and 560 ms on an E core, 3.6 times longer; the two shorter stages are 2.8 to 3.3 times slower. On the GPU the same convolution-type stage is up to 15 times faster at 1024 pixels but only breaks even at "
       "small tiles because host-to-device copies dominate (Figure 1). A scheduler that ignores these ratios sends heavy work to slow cores or the wrong device.")
r.figure(FIG + r"\fig_heterogeneity.png", "Measured heterogeneity on the project machine. Left: median kernel time of one stage task on a P and an E core (log scale). Right: GPU speed-up of three stages versus tile size.", 5.6)
r.section("Measured cost of blind placement")
r.para("On a workload of 64 independent image chains in which 4 to 40 chains are 60 times more expensive in one parameter, a blind greedy dispatcher (first idle eligible worker) needed 5% to 37% more time than a rule "
       "that merely knew which chains were heavy (25% to 37% when 4 to 16 chains were heavy; paired, 12 to 36 blocks per setting). On the 59-task Montage mosaic the first nine reprojection tasks take about 98% of the "
       "sequential run of about 1,460 s, so any placement error there dominates. These two measurements, rather than the market statistics, are the direct evidence that the problem is real on commodity hardware.")

# ------------------------------------------------------------------ 3
r.chapter("Literature Survey: Comparative Analysis of Publications")
r.section("Method")
r.para("The survey analysed 12 supplied base papers (full text read) and one further paper at abstract level ({{cao24}}), plus classical and related work used for positioning. For each paper the algorithm, workload, "
       "platform, metrics, reported result and limitation were extracted and claims were checked against the PDF. A keyword check over the 12 full texts found no occurrence of \u201cconfidence interval\u201d; HEFT appears in "
       "five papers and PEFT in two; measured decision (inference) time is mentioned in only two.")
r.table("Comparison of recent solutions for DAG scheduling and dependent-task offloading",
        ["Ref.", "Method", "Workload / data", "Platform", "Reported result", "Limitation for our goal"],
        [["{{lachesis}}", "GNN + RL selects task; DEFT with duplication places it", "TPC-H DAG jobs", "Simulated cluster", "up to 26.7% makespan vs 7 baselines", "simulation; no variance test"],
         ["{{dddqn}}", "Dueling double DQN", "Google, Alibaba traces", "Trace simulation", "shorter response time, better balance", "cluster level; no hardware"],
         ["{{wang22}}", "Off-policy RL + seq2seq", "Synthetic DAGs", "MEC simulation", "near-optimal latency/energy", "synthetic; simulated edge"],
         ["{{rodriguez}}", "FastFit lightweight scheduling", "4 benchmarks", "Zynq CPU+FPGA (real)", "up to 2x vs auto-tuned scheduler; overhead measured", "FPGA specific; no DAG, no prediction"],
         ["{{song23}}", "Bidirectional GCN + FC net; OCT", "heterogeneous DAGs", "Simulation", "better than compared DAG schedulers", "heavy model; simulation"],
         ["{{gong23}}", "DTOS: parallel DNNs", "Synthetic DAGs", "MEC simulation", "lower delay and energy", "network simulation only"],
         ["{{sata}}", "SATA-DRL (DQN)", "25-node Montage graphs (simulated)", "Simulated MEC", "lower makespan, fewer misses", "no real Montage run"],
         ["{{cao24}} (abstract)", "GAT + DRL", "Synthetic data", "Simulated MEC", "adapts to simple and complex MEC", "synthetic; heavy model"],
         ["{{nieto}}", "Distributed actor-critic", "2 simulated scenarios", "5G edge-cloud (simulated)", "better QoE / energy", "no DAG dependencies"],
         ["{{adprl}}", "Dependency-aware RL reward", "Alibaba trace + synthetic", "Simulation + 1 Jetson Xavier NX + 2 TX2", "lower completion time and energy", "network-flow focus"],
         ["{{metarl}}", "Meta-RL + seq2seq + NSGA-II", "Simulated DAG tasks", "Simulated edge", "21% less delay, 19% less energy", "complex model"],
         ["{{iov}}", "DAG-DQN", "Vehicular applications", "Simulated IoV", "16% less time, 70% faster decisions", "IoV simulation only"],
         ["{{tan25}}", "GCN-Transformer + PPO", "DAG applications", "Simulated multicore", "11.09% lower time and power", "heavy model"]],
        [0.55, 1.2, 1.0, 1.1, 1.2, 1.2], size=8)
r.section("Taxonomy and findings")
r.para("The papers fall into four families. (1) **Learned selection plus a placement heuristic** ({{lachesis,song23,tan25}}): a GNN or Transformer picks the next task and a classical rule picks the processor. "
       "(2) **End-to-end DRL for offloading** ({{dddqn,wang22,gong23,sata,cao24,nieto,adprl,metarl,iov}}): MDP formulations that optimise latency and energy under changing networks. (3) **Lightweight runtime scheduling** "
       "({{rodriguez}}): low-overhead asynchronous scheduling on a real CPU+FPGA board without learning. (4) **Prediction-driven list scheduling** ({{lotaru,starpu,heft,peft}}): runtime models feed HEFT-type or StarPU schedulers.")
r.table("Property matrix of the surveyed solutions (count of papers with the property, out of 13)",
        ["Property", "Papers", "Meaning for this project"],
        [["Dependency graphs (DAG)", "9 of 13", "the problem class is well covered"],
         ["Physical hardware evaluated", "2 of 13", "{{rodriguez}} (CPU+FPGA) and {{adprl}} (three Jetson boards); neither schedules a real scientific workflow"],
         ["Learned model in the decision loop", "12 of 13", "learning is the norm, its cost is rarely measured"],
         ["Decision time reported", "4 of 13", "overhead accounting is a gap"],
         ["HEFT-type baseline", "5 of 13", "PEFT in only 2"],
         ["Confidence intervals", "0 of 13", "statistical reporting is a gap"],
         ["Informed simple-rule baseline", "0 of 13", "benefit of learning not separated from benefit of knowledge"]],
        [2.0, 0.9, 3.4])
r.para("Reported gains range from 11% to 27% (Figure 2) but come from different baselines and simulators and cannot be pooled or ranked. Prediction-driven scheduling is not new: {{lotaru}} reports that HEFT driven by "
       "predicted runtimes stays within a few percent of HEFT with perfect knowledge (simulation); {{ilyushkin}} study how estimate accuracy changes workflow scheduling and, according to their abstract, find that order can "
       "matter more than accuracy under high utilisation, a claim we test on real executions. A 2026 preprint ({{lureda}}) places AI tools on CPU or GPU with an LLM agent on real hardware, on DAGs of about four tools.")
r.figure(FIG + r"\fig_reported_gains.png", "Best reported reductions in the surveyed papers (grey, all simulation) next to this project's measured values (blue, real hardware). Baselines differ between bars: the figure shows scale, not a ranking.", 5.2)
r.section("Strengths and weaknesses by family")
r.para("*Learned selection plus heuristic placement* is the most mature family for DAGs: {{lachesis}} reports that its decision step fits inside tens of milliseconds and {{tan25}} reduce the action space by separating "
       "task selection from processor allocation. Its weakness is dependence on an expert placement rule and on simulator-trained policies. *End-to-end DRL* suits wireless settings where the network is the bottleneck, but "
       "the evaluated task graphs are small or synthetic and the cost of inference on the deciding device is rarely quantified. *Lightweight runtime scheduling* is the only family that measures its own overhead and shows "
       "why it matters. *Prediction-driven list scheduling* shows in simulation that moderate prediction error is tolerable; what is missing is the real-execution test.")
r.section("Evaluation practice")
r.para("Baselines are mostly random, round-robin, FIFO or greedy dispatchers and, in five papers, HEFT; none includes a rule exploiting the same information a learned model would learn. Results are single "
       "percentages from simulators with different cost models, repetition counts are seldom stated, and no paper reports an interval. For a project whose aim is to say how much prediction is enough, the practices "
       "to improve are real execution, interleaved repetitions, paired intervals, overhead accounting and informed baselines. These become the methodology of Chapter 8.")

# ------------------------------------------------------------------ 4
r.chapter("Patents, Products and Technology Trends")
r.section("Patents (IPRs)")
r.para("The base patent is US 11,561,826 B1, *Scheduling processing of machine learning tasks on heterogeneous compute circuits*, assigned to Xilinx, Inc. (inventors S. Nagpal, A. Karumannil, V. Jain, A. K. Patil; filed "
       "12 Nov. 2020; granted 24 Jan. 2023; 20 claims) ({{p_xilinx}}). The granted claims pages were read and related grants were searched on Google Patents. Legal-status and expiry data are Google Patents assumptions, not legal conclusions.")
r.para("Independent claims 1 (method) and 14 (system) recite instantiating *kernel objects* of different kernel types, each indicating a compute circuit of a heterogeneous plurality; generating a graph whose nodes are tasks "
       "assigned to kernel objects and whose edges are data dependencies; creating task queues; enqueueing tasks by threads executing the kernel objects; and dequeueing tasks and activating the compute circuits. Dependent "
       "claims add blocking and non-blocking kernels, several graphs, shared queues, multi-threaded kernels, performance-based adjustment of the thread count (8), output buffers and in-degree counters (9 to 10), "
       "utilisation-triggered scaling (11), a report function (12) and concurrent graphs (13). **No claim recites machine learning, prediction of execution time, a transfer-cost model or offloading to a remote device.**")
r.table("Comparative analysis of patents",
        ["Patent", "Assignee, dates", "Claims or discloses", "Prediction?", "Relation to this work"],
        [["{{p_xilinx}}", "Xilinx; filed 2020-11-12; granted 2023-01-24", "Task graph, kernel objects tied to compute circuits, per-kernel queues, in-degree gating, performance-based thread adjustment", "No", "Base work; mapped to eligibility-gated greedy dispatch (B4)"],
         ["{{p_ibm1}}", "IBM; granted 2023-08-29", "Learning agent assigns a rank to a task; scheduler runs tasks in rank order on a heterogeneous SoC", "Learned rank", "Closest: rank-ordered dispatch"],
         ["{{p_ibm2}}", "IBM; granted 2024-04-23", "ML learns DAG policies, decides dropping, uses task execution estimates", "Yes", "Learned DAG policy, deadlines"],
         ["{{p_intel}}", "Intel; granted 2019-01-22", "CPU+GPU: profile a portion of work on each device, compute a distribution ratio", "Online profiling", "Per-run profiling, no DAG"],
         ["{{p_samsung}}", "Samsung; granted 2018-12-25 (lapsed 2022)", "Predict task duration when core state changes using solo vs concurrent ratios", "Yes", "Contention-aware prediction"],
         ["{{p_apple}}", "Apple; granted 2023-10-03", "Graph whose nodes name a processor (CPU, GPU, neural processor), executed by traversal", "No", "Static graph-to-processor mapping"],
         ["{{p_google}}", "Google; granted 2023-01-03", "Resources of an ML workload, hosts per accelerator, per-host task specification", "No", "Cluster ML placement"]],
        [1.1, 1.2, 2.1, 0.7, 1.2], size=8)
r.para("**Observations.** Task graphs, eligibility-gated queues and utilisation-based scaling are claimed by the base patent and cannot be presented as new. Rank-ordered dispatch with a learned agent is disclosed by "
       "IBM's 2023 grant, so any claim to \u201clearning a task priority\u201d must be examined against it. Duration prediction for heterogeneous cores appears in Samsung's (lapsed) patent and, as execution estimates, in IBM's "
       "second grant. None of the seven documents, as summarised, describes an empirical method for deciding when prediction is worth its cost or an overhead accounting. The project therefore treats B4 as a comparison "
       "baseline, not as its own invention, and positions its contribution as a method and a measured study. A professional prior-art search is required before any filing (Chapter 14).")
r.section("Company products")
r.table("Company and open-source products that schedule on heterogeneous resources (what the cited page states)",
        ["Product", "Scope", "Heterogeneity handled", "Dependencies", "Prediction / learning"],
        [["Intel Thread Director {{intel_td}}", "hybrid client CPU", "P vs E cores; hardware tracks instruction mix per thread", "no (threads)", "hardware classification"],
         ["Windows QoS {{ms_qos}}", "OS scheduler", "QoS levels may restrict threads to a processor subset (e.g. EcoQoS)", "no", "heuristics + hints"],
         ["Linux EAS {{linux_eas}}", "kernel", "asymmetric CPU capacity; energy model", "no", "none; energy-model lookup"],
         ["AWS Batch {{aws_batch}}", "cloud batch", "EC2/Fargate/ECS/EKS compute", "not stated", "none stated"],
         ["Kubernetes {{k8s}}", "cluster", "extended resources via filter/score plugins", "not stated", "none stated"],
         ["Ray {{ray}}", "distributed Python", "declared CPU/GPU resources; placement groups", "futures", "none stated"],
         ["Apache Spark {{spark}}", "data processing", "executors; dynamic allocation", "stages", "none stated"],
         ["Slurm {{slurm}}", "HPC batch", "GRES: GPUs, MPS, MIG", "not on page", "none stated"],
         ["StarPU {{starpu_web}}", "task runtime", "CPU/GPU tasks, transfers", "task graph", "performance models"],
         ["Pegasus WMS {{pegasus}}", "workflow manager", "HTCondor, HPC, cloud; task clustering", "DAG workflows", "none stated"]],
        [1.4, 0.9, 2.2, 0.8, 1.0], size=8)
r.para("There is a division of labour. OS and hardware features place *threads* using hardware feedback or energy models but know nothing about application task graphs. Cluster and batch products schedule containers "
       "or jobs against declared resources; none of the cited pages describes execution-time prediction in the scheduler. Workflow and task runtimes understand DAGs, and only StarPU is described as using performance "
       "models. **No surveyed product combines application-level DAG knowledge, learned per-resource runtime estimates and published decision-overhead measurements on a laptop-class hybrid CPU/GPU system.** NVIDIA Run:ai "
       "({{runai}}) was not assessed beyond its landing page.")
r.section("Technology trends")
r.bullets([
    "**Hybrid and AI-accelerated client processors:** P/E cores are standard ({{intel_td}}) and Copilot+ PCs require an NPU of at least 40 TOPS ({{copilot}}), so a laptop already exposes three engine types.",
    "**Edge growth:** IoT devices grow 12 to 14% per year ({{iotanalytics}}); boards such as the Raspberry Pi 5 ({{rpi5}}) are realistic remote workers.",
    "**From heuristics to learning and back:** DQN gave way to GNN+PPO and meta-RL ({{lachesis,cao24,metarl,tan25}}), while 2026 work replaces training with LLM agents and runtime monitors ({{lureda,agentxpu}}); runtime-prediction work ({{lotaru}}) shows cheap models can approach perfect-knowledge scheduling in simulation.",
    "**Sustainability:** data-centre demand is projected to more than double by 2030 ({{iea}}); energy-aware scheduling is already in production kernels ({{linux_eas}}).",
    "**Reproducible workflow research:** WfCommons ({{wfcommons}}) supplies traces and generators; evaluation on real executions is rare.",
    "**Overhead-aware evaluation:** lightweight schedulers whose cost is measured ({{rodriguez}}) are motivated by fine-grained tasks; overhead and statistical rigour are likely to become standard reporting items.",
])

# ------------------------------------------------------------------ 5
r.chapter("Redoing the Base Work")
r.section("What can be redone")
r.para("The patent describes a hardware/software system for FPGA-based accelerators; a laptop cannot reproduce it. What can be redone is its *scheduling idea*. The project note that B4 is a comparison baseline and not an "
       "implementation of the patent is kept; this report adds a mapping at the level of the granted claims.")
r.table("Base patent concepts and their status in the runtime",
        ["Patent element (claims)", "Runtime", "Status"],
        [["Kernel object of a kernel type = compute circuit (1, 14)", "worker pools P, E, CUDA, remote; per-task eligible pools", "Mapped"],
         ["Graph: nodes = tasks, edges = data dependencies (1)", "DAG with dependency counters for every policy", "Mapped"],
         ["Task queues per kernel (1)", "one global FIFO ready queue scanned for eligibility", "Approximated"],
         ["Threads enqueue/dequeue by assignment (1)", "idle pinned worker process receives oldest eligible ready task", "Mapped (push model)"],
         ["In-degree counters decremented on completion (9, 10)", "readiness when all parents completed", "Mapped"],
         ["Blocking / non-blocking kernels (2, 15)", "every task is a synchronous process call", "Not implemented"],
         ["Several graphs, shared queues (3 to 5, 16 to 18)", "one DAG per run", "Not implemented"],
         ["Performance measurement adjusts thread count (8, 11)", "one worker per core; utilisation logged, not acted on", "Not implemented"],
         ["Report function (12)", "event log, run manifest, dashboard", "Partly"],
         ["FPGA compute circuits", "CPU P/E pools and a CUDA worker", "Different hardware"]],
        [2.4, 2.9, 1.0])
r.para("The core of the mapping: **a worker takes a task only if the task is declared eligible for it, and the choice among eligible idle workers uses no estimate of execution time.** It is implemented as B4 with priority P, then E, then worker identifier.")
r.section("Policies compared")
r.table("Policies and estimators of the runtime",
        ["Name", "Rule", "Uses prediction?"],
        [["B0", "static: all tasks on the P cores (or E cores)", "no"],
         ["B1 / B3", "round-robin / shortest queue over eligible workers", "no"],
         ["B2", "fixed task-type to pool map", "no"],
         ["B4", "first idle eligible worker, priority P, E (the patent-mapped base idea)", "no"],
         ["B5", "B4 with the ready queue ordered by bottom level", "structure only"],
         ["EFT (E0 to E4)", "earliest finish time = wait + transfer + execution; E0 constant, E1 solo profile, E2 analytic size model, E3 moving history, E4 ridge on occupancy", "yes"],
         ["HEFT, PEFT", "static list plans (upward rank / optimistic cost table)", "yes (cost matrix)"],
         ["Hand rule (B4_param_first)", "B4 with the ready queue sorted by the cost-relevant task parameter", "no (knowledge)"],
         ["Proposed (PredictedRankGreedy)", "rank-ordered, idle-worker-only dispatch with a learned generic model", "yes"]],
        [1.7, 3.6, 1.0])
r.section("Results of the redo")
r.table("Redo of B4 and classical list schedulers; paired makespan changes with 95% intervals (negative = shorter)",
        ["Workload (blocks)", "Comparison", "Result", "Reading"],
        [["Montage, 59 tasks, 6P+7E (9)", "B4 vs static P-only", "+47.87% [+37.5, +54.6]", "greedy use of slow E cores hurts"],
         ["Montage", "EFT, HEFT vs static P-only", "+1.62%, +1.54%", "no headroom: every task prefers P"],
         ["Uniform batch + GPU (30)", "static P-only vs B4", "+35.9% [+34.8, +36.9]", "B4 uses all workers"],
         ["Hidden cost, 16 heavy, 6P+7E (36)", "hand rule vs B4", "\u221219.85% [\u221220.7, \u221218.9]", "B4 blind to cost"],
         ["Hidden cost, 16 heavy (24, 6 orders)", "HEFT, PEFT vs B4", "\u221218.08%; \u22122.58%", "HEFT strong; PEFT weak"],
         ["Hidden cost, 4 heavy (12)", "hand rule vs B4; static P-only vs B4", "\u221226.94%; \u221211.56%", "B4 worse than P-only"],
         ["Hidden cost, 40 heavy (12)", "hand rule vs B4", "\u22125.15% [\u22126.2, \u22124.0]", "gain shrinks"],
         ["Two-factor batch (40)", "hand rules vs B4", "\u22120.47%, +1.98% (n.s.)", "ties B4"]],
        [1.8, 1.7, 1.5, 1.3], size=8)
r.para("**B4 is a good baseline for keeping workers busy.** On the uniform batch it is 26% shorter than static use of the P cores, because it uses idle E workers and the GPU, and its decision cost is small: 7 ms of "
       "per-dispatch decision time per run for 257 tasks. **B4 is a poor baseline when task cost differs and is invisible to the scheduler.** With 4 or 8 heavy chains among 64 it was 37% slower than the informed rule and "
       "even slower than P-only, because it hands a heavy chain to whichever worker is free first, including a slow E core, or starts it late. On Montage every task prefers P cores by a factor of 2.3 to 3.6, so the only way to lose is "
       "to use E cores, and B4 loses 48%.")
r.para("Event logs of 20,046 B4 dispatches on the GPU workload show that 93.6% had exactly one eligible idle worker, so an eligibility-gated dispatcher chooses the *order* implicitly (first come, first served) and the *worker* "
       "almost never. Order is exactly what the base idea does not control.")
r.section("HEFT and PEFT")
r.para("HEFT ranks tasks by upward rank and assigns each, in rank order, to the processor with the earliest finish time with insertion into idle gaps ({{heft}}). PEFT replaces the rank by the mean of an optimistic cost "
       "table and picks the processor minimising finish time plus the table value ({{peft}}). Both were implemented as static plans from a cost matrix and fed the same learned model as the proposed dispatcher. They "
       "reproduce the published worked examples through the repository code (HEFT 10-task example; PEFT sample as printed in the author's thesis chapter: PEFT schedule length 122, HEFT 133; the IEEE article of PEFT itself was "
       "not read). On 24 blocks of six unseen chain orders HEFT was 18.1% and PEFT 2.6% shorter than B4, against 19.0% for the proposed dispatcher; HEFT versus the dispatcher was +1.1% with an interval of [\u22120.5, +2.8] "
       "(not distinguishable) and PEFT +20.2%.")

# ------------------------------------------------------------------ 6
r.chapter("Gap Analysis and Proposed Work")
r.section("Gaps")
r.table("Gap analysis: evidence from the survey and the redo, and the project's response",
        ["Gap", "Evidence", "Project response"],
        [["G1 real hardware", "2 of 13 papers use physical devices; none runs a real scientific workflow", "native Windows runtime, P/E pools, CUDA worker; real Montage and image workloads"],
         ["G2 overhead", "decision time reported in 4 of 13 papers", "per-dispatch and coordinator scheduling time logged in every run"],
         ["G3 statistics", "no paper reports an interval", "paired log-ratio bootstrap, Holm correction, registered designs"],
         ["G4 baselines", "HEFT in 5, PEFT in 2, informed rule in 0", "B0 to B5, EFT ladder, HEFT, PEFT and an informed hand rule"],
         ["G5 generalisation", "single instance per setting is common", "twenty unseen chain orders, dose and heavy-count sweeps"],
         ["G6 accuracy vs value", "accuracy and makespan rarely separated", "accurate remote predictions that gave no gain are reported"],
         ["G7 remote reality", "simulated networks; one Jetson testbed", "node/proxy path, loopback emulation labelled as such, Raspberry Pi runbook"],
         ["G8 base-idea limits", "B4 chooses order by arrival and worker almost never", "rank-ordered, work-conserving dispatcher"],
         ["G9 generic prediction", "tables keyed on size miss hidden parameters", "ParamModel learned from logs; names no stage or parameter"]],
        [1.2, 2.5, 2.6], size=8.5)
r.section("Proposed work")
r.para("The proposal has two parts. The **dispatcher** (*PredictedRankGreedy*): (1) order the ready tasks by predicted upward rank, i.e. the predicted time of the task plus the longest predicted path to the exit; "
       "(2) bind each task only to an idle eligible worker (never queue behind a busy one: *work-conserving* or late binding); (3) among the idle eligible workers choose the one with the smallest predicted execution "
       "plus transfer time. The **estimator** (*ParamModel*): per (stage, pool), ridge regression on the numeric task parameters and the size that vary in the logs, plus their pairwise products; it names no stage or parameter "
       "and refuses a stage or pool it has not seen; a new pool layout is handled by refitting with one command.")
r.section("Research questions and hypotheses")
r.numbered([
    "RQ1: Does rank-ordered, work-conserving dispatch with a learned model shorten makespan against B4 on a cost-skewed workload, on chain orders never used for fitting? (Expected: yes.)",
    "RQ2: Is it better than an informed hand rule? (Expected: no; the value of learning is that nobody must know the parameter.)",
    "RQ3: Is there harm where nothing is hidden? (Expected: none, within a \u00b12% equivalence margin.)",
    "RQ4: How does the gain depend on the cost ratio and on the number of heavy tasks?",
    "RQ5: What does the scheduler itself cost, and does that cost explain the gain?",
    "RQ6: Does a remote worker with accurate predictions help? (Not assumed; tested in emulation, to be tested on a Raspberry Pi.)",
])
r.section("Differentiation from the base work and prior art")
r.para("Against the base patent, the proposal adds prediction, ordering by predicted rank and idle-worker-only placement chosen by predicted time; against IBM's learned-rank grant ({{p_ibm1}}) the contribution "
       "is not the idea of ranking but the evaluation: a log-fitted generic model, an explicit comparison with an informed rule, with HEFT and PEFT, and an overhead accounting. We therefore claim a measured, reproducible "
       "study and a method, not novelty of the ranking idea.")

# ------------------------------------------------------------------ 7
r.chapter("System Design and Implementation")
r.section("Architecture")
r.para("A workflow description (a Pegasus YAML file for Montage, or an in-memory image-chain generator) is converted into a DAG of tasks with declared inputs, outputs and eligible pools. The *coordinator* owns the ready "
       "queue, calls the scheduler policy whenever tasks become ready or workers become idle, and dispatches each task to a worker. Workers are separate processes pinned to one logical processor each (6 P workers, or 2 P and "
       "7 E workers on the test machine); the coordinator runs on a reserved E core. A CUDA worker runs the GPU variants of three image stages, and a *remote worker* is a proxy process on the laptop plus a node process that "
       "serves tasks over TCP, on a local core behind a delay shim (emulation) or on another machine (real).")
r.figure(FIG + r"\fig_architecture.png", "Architecture of the implemented framework.", 5.4)
r.section("Runtime components")
r.bullets([
    "**DAG and ready queue.** Tasks become ready when all parents completed (dependency counters); the queue is FIFO and policies may reorder it per dispatch pass.",
    "**Eligibility.** Every policy honours per-task eligible pools through one helper; the coordinator raises an error on an ineligible or non-idle placement (zero such errors in all reported sessions).",
    "**External-command tasks.** Montage jobs run as processes without a shell, with timeouts, process-tree kill, declared-output checks and hashing of inputs and outputs.",
    "**Failure semantics.** Per-task terminal status; dependents of a failed task are marked not-run; runs restart from a clean directory; failed or timed-out runs are kept and flagged.",
    "**Event log.** One JSON line per event (ready, dispatched, submitted, completed, failed); each dispatch carries its decision time and, for EFT-type policies, the candidate costs.",
    "**Remote path.** Frame-size caps, a token-based mutual HMAC handshake for non-loopback hosts, real artefact payloads, proxy-side timestamps for a foreign clock, a persistent node and an adapter that connects to an already running node.",
])
r.section("Estimators and policies")
r.para("Estimators implement one interface and can be swapped without touching the scheduler: a constant per type and pool (E0), a solo-profile lookup (E1), an analytic size model (E2), a moving history (E3), a ridge "
       "model on occupancy context (E4), CatBoost and a small MLP, and an offline replay oracle (E5, reference only). The proposed *ParamModel* is fitted from *coverage sessions*, runs on chain orders never used for "
       "evaluation, with every pool executed under varied occupancy. Features are decision-time safe, and a parity test enforces equality between offline and online features. On a held-out two-factor session the heavy "
       "classes were predicted within 8% (0.605 s predicted versus 0.565 s measured; 0.122 s versus 0.112 s), the lightest class poorly (17.6 ms versus 4.1 ms), which does not affect makespan.")
r.section("The dispatch pass")
r.para("Whenever a task becomes ready or a worker becomes idle the coordinator runs one dispatch pass, the same for all policies; only two hooks differ:")
r.numbered([
    "take the ready tasks from the FIFO queue and call the policy's *order_ready* hook (default: unchanged; hand rules sort by a parameter; the proposed policy sorts by predicted upward rank);",
    "for each task in the returned order, call *select_worker* (the policy returns a worker or nothing); a late-binding policy may only return an idle eligible worker;",
    "check eligibility and idleness (a violation raises a contract error), bind the task and log the dispatch with the decision time and the decision record;",
    "stop when no worker is idle (late-binding policies) or all ready tasks were visited; on completion log the result, release dependents and call the policy's feedback hook.",
])
r.section("Experiment framework")
r.para("A design file lists conditions, seed, block count, warm-up rule and thresholds. The runner derives a reproducible block plan, runs every condition once per block in random order, checks free memory and mains "
       "power before every block, writes a manifest per run (condition, seed, code hash, environment hash, output hashes, status) and makes event logs read-only. The analysis refuses to pool sessions with different code, "
       "environment, label or design, excludes runs by rules fixed in the design, and computes paired effects with bootstrap intervals, Holm-adjusted p-values, minimum detectable effects and a sensitivity pass.")
r.table("Event log and run-manifest content",
        ["Record", "Fields (selection)"],
        [["task_ready, task_dispatched", "task id, worker, pool, queue wait, worker load, decision time, decision record (candidate wait/transfer/exec/finish)"],
         ["task_submitted, task_completed", "kernel time, start/end timestamps, transfer time, bytes moved, output size and SHA-256"],
         ["worker_ready, run_started, run_finished", "pid, requested and actual affinity, capabilities; makespan, status, tasks per pool"],
         ["run manifest", "condition, policy, seed, instance, warm-up flag, status, output verdict and hashes, event-log SHA-256, git commit and dirty flag, source SHA-256, design SHA-256"],
         ["session record", "design hash, machine id, environment hash, blocks completed, preflight log, final status"]],
        [2.0, 4.3])
r.section("Dashboard")
r.para("A local web dashboard shows system state, a replay of runs and, on its last tab, any experiment session side by side (Figure 4). It is started with one command (Chapter 13) and reads the stored result files; "
       "the side-by-side view for B4 and the proposed dispatcher on the same chain order is the quickest way to show the effect to an audience.")
r.figure(FIG + r"\dashboard_compare.jpg", "Dashboard comparison tab: one B4 run (3858.9 ms) and one run of the proposed dispatcher (3097.0 ms) of the same chain order, with placement, scheduling time and output-hash check.", 5.2)
r.section("Code and test inventory")
r.table("Implementation inventory (lines counted in the repository)",
        ["Part", "Files", "Lines of Python"],
        [["Runtime package (src/caosched)", "94", "11,863"],
         ["  core (coordinator, pools, DAG, tasks)", "", "2,011"],
         ["  estimators; schedulers; analysis; experiment", "", "1,197; 845; 1,023; 1,126"],
         ["  revival (resource-state policy); study2 (proposed dispatcher)", "", "1,327; 678"],
         ["  dashboard (plus 1,237 lines of HTML/JS); remote; dataset", "", "774; 571; 692"],
         ["Scripts (experiments, analysis, profiling, runbooks)", "72", "8,195"],
         ["Tests", "47", "6,770 (488 tests pass)"],
         ["Version control", "71 commits", "branch revival/resource-state-aware"]],
        [3.6, 1.0, 1.7])
r.section("Changes made in the final sprint")
r.table("Code changes of the final sprint (all uncommitted; the originals are backed up)",
        ["File", "Change", "Why"],
        [["src/caosched/experiment/remote_adapter.py", "connect to an already running node by host and port; label real only for a non-loopback host; refuse a delay shim on a real host", "a Raspberry Pi run was impossible: the adapter could only spawn the node locally"],
         ["src/caosched/remote/node.py", "--persistent: keep serving after a client says bye or disconnects", "first rehearsal failed: the node served one client then exited"],
         ["scripts/calibrate_link.py", "--remote-host/--remote-port, --denoise-iterations", "R rows were measured at the default level; no way to target a Pi"],
         ["scripts/make_pi_design.py (new)", "generates design and adapter config for the real-device experiment", "needed by the runbook"],
         ["docs/research_redesign/claims.json", "20 descriptive claims O1 to O20 appended", "registry convention; no existing claim changed"]],
        [2.0, 2.6, 1.7], size=8.5)

# ------------------------------------------------------------------ 8
r.chapter("Methodology")
r.section("Platform and workloads")
r.table("Workloads",
        ["Workload", "Tasks", "Purpose"],
        [["Montage mosaic (real, native Windows build, 9 DSS2 images)", "59", "real scientific DAG; nine 160 s reprojections dominate"],
         ["Uniform image-chain batch (+ CUDA worker)", "257", "no hidden cost; no-harm control"],
         ["Hidden-cost batch: H of 64 chains with 120 vs 2 denoise iterations", "257", "main study; H = 4, 8, 16, 40"],
         ["Dose batch: heavy chains of 6, 15, 40, 120 iterations", "257", "cost-ratio sweep"],
         ["Two-factor batch (size x iterations)", "about 200", "learned-model stress test"],
         ["Image pipeline with remote stages (tile 512, 16 branches)", "68", "emulated remote worker; Pi path"]],
        [3.6, 0.8, 1.9])
r.para("Montage was built natively with a MinGW-w64 toolchain after ten documented workarounds; three sequential reference runs gave identical mosaic hashes (maximum absolute difference 0.0), correct WCS headers and "
       "147 dependency edges equal to the generator's own.")
r.table("Montage reference runs: median wall time per task type (three identical sequential runs, 59 tasks each)",
        ["Task type", "n", "Median (s)", "Range (s)"],
        [["mProject (reprojection)", "27", "160.57", "141.02 to 169.89"],
         ["mDiffFit (overlap fit)", "108", "0.251", "0.041 to 1.036"],
         ["mBackground", "27", "0.336", "0.303 to 0.610"],
         ["mConcatFit / mBgModel / mImgtbl", "3 each", "0.207 / 0.379 / 0.094", "-"],
         ["mAdd / mViewer", "3 each", "0.870 / 4.157", "-"],
         ["Total sequential makespan", "3 runs", "1459.4, 1467.1, 1469.3", "outputs identical (SHA-256)"]],
        [2.4, 0.8, 1.7, 1.4])
r.section("Statistics")
r.para("The effect of a condition against a reference is computed per block *b* as the log ratio of makespans; the reported effect is (exp(mean of the log ratios) \u2212 1) \u00d7 100%, with a percentile bootstrap interval "
       "stratified by workload instance (10,000 resamples) and a Holm-adjusted sign-flip p-value over the confirmatory family. Equivalence claims use a \u00b12% margin on the interval. With 36 paired blocks the 95% interval "
       "half-width of a contrast is about 1.5 points and the minimum detectable effect at 80% power about 2.2%; sessions of 12 blocks over four orders are less precise and show direction and order of magnitude only.")
r.section("Procedure and controls")
r.bullets([
    "Conditions are interleaved within blocks in random order; a warm-up block is excluded; the first run after a new reference computation is about 2% slower (11 cases) and is reported as a limitation.",
    "Memory and mains-power preflight before every block; sessions abort rather than run under pressure.",
    "Every run's output is verified against a CPU reference; event-log hashes and design hashes are checked against the manifests.",
    "Registered sessions carry a design hash and amendments; overnight sessions are exploratory, with the plan and design hash written before the run and the reading of the result fixed in advance.",
    "Chain orders are shuffles of the 64 chains seeded by an integer; orders used for model fitting (coverage) are disjoint from evaluation orders.",
    "Sessions with different code, environment or label are never pooled.",
])

# ------------------------------------------------------------------ 9
r.chapter("Results")
r.section("Montage: a valid null result")
r.para("On the 59-task mosaic with 6 P and 7 E workers (9 blocks, registered), predictive EFT variants and HEFT were 1.4% to 1.7% slower than static use of the P cores (intervals above 0), learned models 9% to 14% slower, "
       "and B4 47.9% slower (95% interval +37.5 to +54.6). Every Montage task prefers P cores by a factor of 2.3 to 3.6 and nine equal tasks dominate, so no placement can beat \u201cuse the P cores\u201d and any use of E cores costs time.")
r.section("Hidden-cost workload")
r.para("Registered sessions with two chain orders each gave the proposed dispatcher \u221220.39% [\u221221.2, \u221219.3] (30 blocks, 6P+7E) and \u221221.10% [\u221221.5, \u221220.7] (20 blocks, 2P+7E, model refitted by one command) relative "
       "to B4. To test generalisation, exploratory sessions used chain orders never used before (Table 16, Figure 5). The dispatcher was faster than B4 in all 12 and all 8 orders. The informed hand rule gave the same gain "
       "and the difference between dispatcher and rule had intervals inside \u00b12%.")
r.table("Unseen chain orders (exploratory); effects relative to B4 unless noted (negative = shorter)",
        ["Session", "Blocks / orders", "Dispatcher", "Hand rule", "P-only", "Dispatcher vs rule"],
        [["6P+7E, H=16", "36 / 12", "\u221219.32% [\u221220.0, \u221218.6]", "\u221219.85%", "+3.68%", "+0.66% [\u22120.2, +1.5]"],
         ["2P+7E, H=16", "24 / 8", "\u221220.45% [\u221221.2, \u221219.8]", "\u221220.67%", "+45.77%", "+0.27% [\u22120.2, +0.8]"],
         ["6P+7E, H=4", "12 / 4", "\u221227.65% [\u221234.0, \u221218.7]", "\u221226.94%", "\u221211.56%", "\u22120.98% [\u22123.1, +1.2]"],
         ["6P+7E, H=8", "12 / 4", "\u221226.76% [\u221227.9, \u221225.7]", "\u221226.93%", "\u221215.77%", "+0.24% [\u22120.4, +1.0]"],
         ["6P+7E, H=40", "12 / 4", "\u22123.81% [\u22125.1, \u22121.9]", "\u22125.15%", "+23.13%", "+1.42% [\u22120.7, +4.5]"]],
        [1.0, 0.8, 1.6, 0.8, 0.8, 1.3], size=8.5)
r.figure(FIG + r"\fig_per_order.png", "Per-order change in makespan of the dispatcher against B4 (blue) and the hand rule (green).", 5.4)
r.figure(FIG + r"\fig_makespan_policies.png", "Mean makespan by policy on unseen chain orders (geometric means with 95% intervals): 12 orders on 6P+7E (left), 8 orders on 2P+7E (right).", 5.4)
r.section("Dose-response and heavy-chain count")
r.para("Holding 16 heavy chains and raising their cost ratio from about 3 to 60 gave \u22122.6%, +0.6% (not significant), \u22126.1% and \u221219.9% in a first pass of four orders; a follow-up with eight further orders gave "
       "\u22121.3% (ratio 7.5) and \u22122.9% (ratio 20). The first-pass irregularity was order-specific: the gain is small, about 1% to 3%, up to a ratio of 20 and large only near 60. With the ratio fixed, the gain is largest "
       "when few chains are heavy and falls as they become the majority (Figure 7), consistent with a tail effect in which blind dispatch starts a heavy chain late or on a slow core.")
r.figure(FIG + r"\fig_dose_heavy.png", "Gain over B4 versus heavy:light cost ratio (left) and number of heavy chains (right).", 5.4)
r.section("Registered results and model accuracy")
r.table("Selected registered claims (pre-registered designs; effect = paired makespan change, negative = shorter)",
        ["Claim", "Workload", "Comparison", "Effect", "Status"],
        [["U1", "uniform batch + GPU", "predictive EFT vs static P-only", "\u221227.56%", "supported"],
         ["U2", "uniform batch + GPU", "predictive EFT vs B4", "+0.25%", "equivalent (\u00b12%)"],
         ["H1", "hidden cost (first run)", "rank EFT with learned model vs B4", "\u221213.78%", "supported"],
         ["G1, G3", "hidden cost 6P+7E", "dispatcher vs B4; table predictor vs dispatcher", "\u221220.39%; +75.19%", "supported"],
         ["G4", "hidden cost 6P+7E", "dispatcher vs hand rule", "\u22121.54% (rule faster)", "not resolved"],
         ["R1, R3", "hidden cost 2P+7E", "dispatcher vs B4; table predictor vs dispatcher", "\u221221.10%; +57.65%", "supported"],
         ["R4", "hidden cost 2P+7E", "dispatcher vs hand rule", "+0.38%", "equivalent"],
         ["N1", "uniform batch", "dispatcher vs B4", "\u22120.45%", "equivalent"],
         ["C1, C2", "two-factor", "size-only rule, static P-only vs dispatcher", "+17.44%; +17.13%", "supported"],
         ["C3", "two-factor", "dispatcher vs B4 (at least 2% faster?)", "+0.95% [\u22120.9, +2.8]", "not supported"],
         ["V1", "contended mixed DAG", "oracle gate (at least 5% headroom)", "B4 1.24% faster than oracle", "gate failed"]],
        [0.6, 1.3, 2.2, 1.3, 0.9], size=8.5)
r.section("Established list schedulers")
r.para("Driven by the same learned model on six further unseen orders (24 blocks), HEFT gave \u221218.08% and PEFT \u22122.58% relative to B4, rank-ordered EFT with early binding \u221213.21% and the dispatcher \u221218.97%; HEFT "
       "versus the dispatcher was +1.10% [\u22120.53, +2.81], PEFT +20.23%, early-binding EFT +7.11%. Both the ordering and the late (idle-only) binding contribute; the static plan of HEFT is competitive on this workload.")
r.section("Scheduling overhead")
r.para("Two overhead figures exist. *Per-dispatch decision time* (the time of the worker-selection call that bound a task) is 6.8 ms per run for B4 and 15.5 ms for the dispatcher (257 tasks, about 0.5% of makespan). "
       "*Coordinator scheduling time* (all policy calls, including those that returned nothing) is 0.197 s and 0.100 s. The difference was traced with an instrumented run: because a CUDA worker that no task can use is "
       "always idle, the dispatch loop never exits early, and 10,042 of 10,299 calls of B4's selection function returned nothing. A decision-preserving fix in a separate adapter reduced coordinator time to 8 ms (B4) and "
       "24 ms (dispatcher) and moved the dispatcher's gain from \u221219.47% to \u221220.28% (0.8 percentage points) with all 78 runs verified. The fix is not applied to the source.")
r.figure(FIG + r"\fig_overhead.png", "Per-dispatch decision time and coordinator scheduling time per run, before and after the dispatch-loop fix.", 5.4)
r.section("GPU and remote execution")
r.para("At task level the GPU is up to 15.1 times faster for the edge-detection stage at 1024 px and 5.2 times for feature extraction, with outputs equal within tolerance; the denoise stage gains only 1.4 times "
       "and not at small tiles. No workflow-level gain from CPU/GPU placement was established.")
r.para("For remote execution, an emulated worker (a node on one local E core behind a loopback socket and a delay shim) was tested at two compute levels. At level 30 the predictive policy used the remote worker "
       "(1.7 tasks per run) with accurate predictions (execution 0.1457 s predicted vs 0.1464 s measured; transfer 0.0937 s vs 0.0943 s over 44 placements) yet was 3.78% [+2.27, +5.58] slower than without it (Figure 9). "
       "Prediction accuracy did not become scheduling value in this regime. A loopback rehearsal of the complete Raspberry Pi command chain (profile, calibration with an external node, design generation, 25 runs, "
       "analysis) passed after a defect in the node (it served only one client) was fixed.")
r.figure(FIG + r"\fig_remote.png", "Emulated remote worker: effect on EFT makespan at compute level 1 (registered) and level 30 (overnight); error bars are 95% intervals.", 5.2)
r.section("Sessions executed")
r.table("Timed sessions of the final study (all outputs verified; event-log hashes checked)",
        ["Group", "Sessions", "Blocks", "Runs", "Label"],
        [["Unseen orders 6P+7E / 2P+7E", "2", "37 / 25", "148 / 100", "real"],
         ["Dose-response (3, 7.5, 20, 60) and follow-up (7.5, 20)", "6", "52 + 50", "208 + 200", "real"],
         ["HEFT/PEFT/rank-EFT vs dispatcher", "1", "25", "150", "real"],
         ["Heavy-chain count 4, 8, 40", "3", "39", "156", "real"],
         ["Dispatch-loop A/B", "1", "13", "78", "real"],
         ["Reproduction of the registered design", "1", "11", "55", "real"],
         ["Emulated remote pool, level 30", "1", "13", "65", "emulation"],
         ["Loopback rehearsal of the Pi command chain", "1 (+1 failed)", "5", "25 (+25 failed)", "emulation"]],
        [3.0, 0.9, 0.8, 0.9, 0.7], size=8.5)

# ------------------------------------------------------------------ 10
r.chapter("Discussion")
r.section("Mechanism")
r.para("The dominant effect is ordering: serving predicted-heavy work first removes the tail created by blind dispatch. That is why an informed rule achieves the same result and why the effect depends on the "
       "share and cost ratio of heavy chains. The learned model matters because it supplies the knowledge a person would otherwise hard-code; its value is that it needs no such knowledge and is retrained by one command "
       "for a new pool layout (shown for 2 P + 7 E). **Prediction accuracy is not enough:** remote predictions were accurate to under 1% yet gave no gain, in line with the finding of {{ilyushkin}} that order can matter more "
       "than estimate accuracy, now seen on real executions. **Overhead matters but did not decide the result:** scheduling time is 2% to 5% of these 3 to 9 second runs for late-binding policies and 1% to 2% of makespan "
       "could be recovered by the loop fix, yet the gain over B4 changes by under one point.")
r.section("Relation to the literature")
r.para("The surveyed learned schedulers report 11% to 27% improvements in simulation ({{lachesis,metarl,iov,tan25}}). The figures here are measured on real hardware with intervals and an informed baseline, are of the same "
       "order on cost-skewed workloads, and show that most of the gain is available to a much simpler rule. No claim of superiority over DRL schedulers is made; they were not run.")
r.table("This implementation compared with the closest published systems",
        ["System", "Evaluation", "Hardware", "Overhead reported", "Intervals", "Informed baseline"],
        [["{{lachesis}}", "simulation", "simulated cluster", "inference time", "no", "no"],
         ["{{adprl}}", "trace simulation + testbed", "3 Jetson boards", "no", "no", "no"],
         ["{{rodriguez}}", "real", "Zynq CPU+FPGA", "yes", "no", "no"],
         ["{{lotaru}}", "simulation", "simulated heterogeneous cluster", "prediction error", "median errors", "HEFT with true runtimes"],
         ["{{starpu}}", "real", "CPU+GPU nodes", "history models", "not assessed", "no"],
         ["This work", "real executions", "P/E cores, RTX 3050, emulated remote", "two metrics per run", "paired bootstrap, Holm", "yes (hand rules)"]],
        [0.8, 1.2, 1.5, 1.0, 1.0, 0.9], size=8.5)
r.section("Threats to validity")
r.numbered([
    "The hidden-cost workload is designed: it shows when prediction or knowledge helps, not how common that is.",
    "One machine; one workload family for the headline; the learned model was fitted at compute levels 2 and 120, so levels 6, 15 and 40 are interpolation.",
    "Sessions have different source hashes and a dirty working tree; they are never pooled. The sprint's code changes do not touch the scheduler, estimator or coordinator.",
    "The overnight sessions are exploratory; the analysis tool labels the primary family \u201cconfirmatory\u201d by default, which the plans override.",
    "HEFT and PEFT follow secondary descriptions verified on worked examples; the IEEE PEFT article was not read.",
    "Remote results are emulation: one local E core behind a loopback socket and a delay shim; the hypothesis that the proxy shares the coordinator's core was not tested.",
    "The literature check is bounded: 13 papers, not a systematic review; patent summaries rely on Google Patents text; two statistics are secondary reports.",
])

# ------------------------------------------------------------------ 11
r.chapter("Existing versus Proposed Implementation")
r.para("This chapter is the differentiation required for the project demonstration: what the existing (base) implementation does, what the proposed implementation adds, and what the measurements show.")
r.table("Differentiation between the existing (base) implementation and the proposed one",
        ["Aspect", "Existing (B4 / base patent idea)", "Proposed (PredictedRankGreedy + ParamModel)"],
        [["Order of ready tasks", "first-come first-served", "predicted upward rank"],
         ["Worker choice", "first idle eligible worker (P before E)", "idle eligible worker with least predicted time"],
         ["Queueing behind a busy worker", "never (push to idle)", "never (work-conserving), by design"],
         ["Cost knowledge", "none", "model learned from logs; retrained by one command; names no stage or parameter"],
         ["Unseen stage or pool", "n/a", "refuses (raises) rather than guessing"],
         ["Decision cost per run", "7 ms (coordinator 0.20 s)", "15 ms (coordinator 0.10 s)"],
         ["Makespan, hidden cost, 16 heavy", "reference", "\u221219.3% (6P+7E, 12 unseen orders), \u221220.5% (2P+7E, 8 orders)"],
         ["Makespan, heavy count 4 / 8 / 40", "reference", "\u221227.7% / \u221226.8% / \u22123.8%"],
         ["Makespan, nothing hidden", "reference", "+0.45% (equivalent within \u00b12%)"],
         ["Makespan, Montage", "+47.9% vs static P-only", "no policy beats static P-only; EFT +1.6%"],
         ["Versus informed hand rule", "\u2014", "level (+0.66%, +0.27%)"],
         ["Versus HEFT with the same model", "\u2014", "level (HEFT vs dispatcher +1.10% [\u22120.5, +2.8])"],
         ["Evidence", "\u2014", "real runs, paired intervals, unseen orders, 50 registered claims, 488 tests"]],
        [1.7, 2.1, 2.5], size=8.5)
r.section("What is new and what is not")
r.bullets([
    "**Not new:** task graphs, eligibility gating and utilisation scaling (base patent); ranked dispatch with a learned agent (IBM grant); list scheduling (HEFT, PEFT); runtime performance models (StarPU).",
    "**New in this project:** a log-fitted generic model with no hard-coded stage or parameter, used inside an idle-only rank-ordered dispatcher; an evaluation that separates ordering from prediction by an informed hand rule; two overhead metrics and the diagnosis of their discrepancy; unseen-order, dose and heavy-count generalisation tests; a claims registry bound to stored tables; a rehearsed real-device path.",
    "**Negative and null findings reported:** no gain on Montage, none on the two-factor workload, none from the emulated remote worker, none for workflow-level CPU/GPU placement, no advantage over an informed rule.",
])

# ------------------------------------------------------------------ 12
r.chapter("Testing, Verification and Reproducibility")
r.section("Automated tests")
r.para("The full suite passed with 488 tests (244 s) before the last claims were added; `tests/test_claims.py` alone gave 51 passed afterwards; the focused remote tests gave 22 passed. Tests cover the coordinator contract "
       "(eligibility and idleness), dependency handling, failure semantics, estimators (including parity of offline and online features), HEFT and PEFT on the published worked examples, the remote protocol, the "
       "experiment runner and analysis, and the claims registry.")
r.section("Evidence verification")
r.para("Every session's runs were verified against the CPU reference output; event-log hashes match the manifests; design hashes match; and `scripts/reproduce_subset.py` re-derives each analysis table from the raw "
       "logs (exit status 0 for every analysis: two for unseen orders on each configuration, eight for the dose sweeps, two for the dispatch-loop A/B and six for HEFT/PEFT and the follow-ups). The first attempt of the last "
       "group failed because the session manifests did not exist yet; the log is kept and the check was rerun after the manifests were written.")
r.section("Defects found and corrected")
r.table("Defects, how they were found and what was done",
        ["Defect", "Found by", "Action"],
        [["Learned model applied to a different profile than it was fitted on", "audit of earlier phases", "profile binding recorded; refusal on mismatch; tests"],
         ["Worker-pool rebuild between conditions created cold workers (two-humped makespans)", "pilot analysis", "one pool for all conditions"],
         ["Decision-context logging cost 3% of makespan in EFT", "paired comparison", "no-context variants; scheduling-cost guard (25%)"],
         ["Remote node served one client then exited", "loopback rehearsal (24 runs failed)", "persistent mode and test"],
         ["Calibration ignored the compute level; no external host option", "code reading", "options added; test"],
         ["Idle CUDA worker defeats the dispatch loop's early exit", "overhead diagnosis", "quantified; fix in a separate adapter; source fix proposed"],
         ["Diagnostic script spawned workers without a __main__ guard", "first diagnostic run failed", "guard added; failed run kept"],
         ["reproduce_subset failed before manifests existed", "first reproduction attempt", "manifests written, rerun passed; failed log kept"]],
        [2.8, 1.5, 2.0], size=8.5)
r.section("Safeguards for the evidence")
r.para("No existing result, design or document was overwritten; new evidence is in unique directories; no commit, push, amend or reset was made by the sprint; backups of edited files are in the snapshot directory; "
       "a blocked action (a background start with an execution-policy bypass) was not retried and no policy was changed.")

# ------------------------------------------------------------------ 13
r.chapter("Project Demonstration Guide")
r.para("The demonstration has two modes: through the front end (dashboard) and through code in a terminal. Commands assume the project root `D:\\cao project` and the virtual environment `.venv`. If PowerShell blocks "
       "`Activate.ps1` because of the execution policy, do not change the policy: call the interpreter directly as `.\\.venv\\Scripts\\python.exe`.")
r.section("Mode 1: front end")
r.code(r".\.venv\Scripts\python.exe -m caosched.dashboard --port 8765 --open")
r.para("The browser opens the dashboard. The last tab compares experiment runs side by side: choose a B4 run and a run of the proposed dispatcher of the same chain order; the view shows the makespan (for example "
       "3858.9 ms against 3097.0 ms), the placement per pool, the scheduling time and the output-hash check. The first four tabs show system state and replays; their interaction was not part of the final verification and "
       "should be rehearsed before a live demonstration.")
r.section("Mode 2: terminal")
r.code(r".\.venv\Scripts\python.exe -m pytest tests -q" "\n"
       r".\.venv\Scripts\python.exe scripts\reproduce_subset.py data\results\overnight_20261027\phase3\analysis_ref_B4")
r.para("The first command runs the 488 tests (about four minutes). The second re-derives an analysis table from the raw logs and checks event-log and manifest hashes (about one minute); see the script's `--help` for its "
       "exact arguments. The stored evidence to show is `data\\results\\overnight_20261027\\phase3\\per_order_summary.csv` and the effect plots in each `analysis_ref_*` folder.")
r.section("Where the latency metric is")
r.para("If a faculty member asks how much extra time the scheduler costs: the *per-dispatch decision time* is logged in each `task_dispatched` event (about 7 ms per run in total for B4 and 15 ms for the dispatcher) and the "
       "*coordinator scheduling time* is in the run record (0.197 s and 0.100 s per run; about 2% to 5% of a 3 to 9 second run). The two differ for a documented reason (Section 9.6). Makespan is the headline metric; "
       "overhead is reported beside it, never subtracted from it.")
r.section("Five-minute narrative")
r.numbered([
    "A workflow is a graph of tasks; a scheduler decides where and in what order. The framework runs real tasks and checks every output.",
    "Blind greedy dispatch (B4) is the base idea; the proposed dispatcher learns task costs from logs and serves heavy work first.",
    "On 64 image chains with 16 heavy ones the proposed dispatcher is about 19% to 21% faster than B4 on chain orders never used before, and level with a hand rule that knows the parameter.",
    "Where nothing is hidden, or on Montage, there is no gain and no harm beyond the equivalence margin; the report says so.",
    "Remote offloading was tested only in emulation; the Raspberry Pi is the next step and its runbook is ready.",
])

# ------------------------------------------------------------------ 14
r.chapter("Publication and IPR Route")
r.para("The detailed plan is in the separate document `07_Publication_and_IPR_Plan`. In brief:")
r.bullets([
    "**Primary venue candidate:** IEEE/ACM CCGrid 2027 (full paper up to 10 pages including references in IEEE two-column format; double-blind; abstract deadline 24 Nov. 2026 and paper deadline 1 Dec. 2026 as read from the call at {{ccgrid27}}; the dates must be re-checked on the call page before submission).",
    "**Alternatives:** a journal route (for example a parallel/distributed computing or future-generation systems journal after adding the Raspberry Pi results), a workshop route, and a book-chapter route that is unverified and must be confirmed with a publisher's call.",
    "**IPR:** the base patent claims the graph, queue and gating concepts; rank-ordered learned dispatch is disclosed by an IBM grant. Patentability of any new element is uncertain; if an IPR filing is considered, the Invention Disclosure Form must be filed *before* any public disclosure, and a professional prior-art search is required. This report is not legal advice.",
    "**Disclosure timing:** publishing the code and the paper first would defeat novelty in many jurisdictions; the GitHub release is therefore prepared but not pushed.",
])

# ------------------------------------------------------------------ 15
r.chapter("Conclusion, Limitations and Future Work")
r.section("Conclusion")
r.para("The project delivers a reproducible framework and a measured account of when prediction-aware scheduling helps on a hybrid laptop. Ordering decides: where a hidden cost makes ordering decisive, a rank-ordered, "
       "work-conserving dispatcher with a log-fitted generic model shortens makespan by about 19% to 21% against the base dispatch idea on chain orders never used before, matches an informed rule and HEFT, "
       "and does no harm where nothing is hidden; where there is no headroom (Montage), it cannot help. Accurate prediction alone is not sufficient: it gave no remote-offloading gain in emulation. Scheduling "
       "overhead is measured two ways, and an inefficiency in the dispatch loop was found, quantified and shown not to explain the gain.")
r.section("What is established and what is not")
r.table("Claim status after the project",
        ["Status", "Claims"],
        [["Supported", "rank-ordered dispatch beats B4 by 19% to 28% on cost-skewed workloads; it equals the informed rule; no harm where nothing is hidden; static P-only is worse; HEFT with the same model is level with it; task-level GPU speed-ups; transfer-aware placement avoids the harm of blind remote placement"],
         ["Not established", "advantage over an informed rule; resource-state-aware improvement; GPU-contention opportunity; workflow-level GPU scheduling gain; remote offloading benefit; any Raspberry Pi or real-network result; generality to other workload families"],
         ["Not supported / null", "gain on Montage; gain on the two-factor workload (+0.95% [\u22120.9, +2.8]); remote worker helping EFT at level 30"]],
        [1.3, 5.0])
r.section("Future work")
r.numbered([
    "Measure a Raspberry Pi 5 over a wired link with the prepared runbook (decision rule fixed beforehand: the remote worker helps only if the interval of EFT with versus without it lies below zero).",
    "Add a second workload family to test generality beyond designed image chains.",
    "Apply and test the dispatch-loop fix in the source (worth 1% to 2% of makespan).",
    "Repeat the headline experiment on a clean, committed tree.",
    "Test learned-DRL baselines if code and budgets become available.",
    "Obtain a professional prior-art search before any IPR filing.",
])

# ------------------------------------------------------------------ appendices
r.chapter_plain("Appendix A. File Map")
r.para("Key locations in the repository (`D:\\cao project`).")
r.table("File map",
        ["Path", "Content"],
        [["src/caosched/core/", "coordinator, worker pools, DAG, tasks, dispatch pass"],
         ["src/caosched/schedulers/, estimators/", "policies B0 to B5, EFT ladder, HEFT, PEFT, hand rules; estimators E0 to E5, ParamModel"],
         ["src/caosched/study2/", "PredictedRankGreedy and its estimator"],
         ["src/caosched/revival/", "resource-state-aware policy (not established)"],
         ["src/caosched/experiment/", "runner, designs, manifests, adapters (including remote_adapter.py)"],
         ["src/caosched/analysis/", "paired effects, bootstrap, Holm, equivalence, sensitivity"],
         ["src/caosched/remote/", "node, proxy, protocol, handshake"],
         ["src/caosched/dashboard/", "local web dashboard (server and static HTML/JS)"],
         ["scripts/", "experiment drivers, calibrate_link.py, make_pi_design.py, reproduce_subset.py, make_manifest.py"],
         ["tests/", "47 test files, 488 tests"],
         ["docs/research_redesign/claims.json", "registry of 50 claims"],
         ["docs/B4_PATENT_MAPPING.md", "mapping of the base patent to B4"],
         ["data/results/overnight_20261027/", "sessions, analyses, per-order tables, verification, activity log"],
         ["OVERNIGHT_FINAL_REPORT.md, RESULTS_TABLE.csv, EVIDENCE_INDEX.md", "sprint summary, result table, evidence hashes"],
         ["FACULTY_DEMO_SCRIPT.md, FACULTY_DEMO_CHECKLIST.md", "demonstration script and checklist"],
         ["RASPBERRY_PI_VALIDATION_RUNBOOK.md", "step-by-step real-device plan"],
         ["publications/", "this submission package (reviews, report, paper, plans, figures, builders)"]],
        [2.8, 3.5], size=8.5)
r.chapter_plain("Appendix B. Glossary")
r.table("Terms",
        ["Term", "Meaning"],
        [["DAG", "directed acyclic graph of tasks and data dependencies"],
         ["Makespan", "wall time from start of a run to completion of the last task"],
         ["P / E core", "performance / efficiency core of a hybrid CPU"],
         ["Eligible pool", "set of worker types on which a task is allowed to run"],
         ["B4", "eligibility-gated greedy dispatch: first idle eligible worker (the base idea)"],
         ["EFT", "earliest finish time placement (wait + transfer + execution)"],
         ["HEFT / PEFT", "list schedulers using upward rank / an optimistic cost table"],
         ["Work-conserving / late binding", "a task is bound only to a worker that is idle now"],
         ["Hand rule", "B4 with the ready queue sorted by a parameter a person knows to be costly"],
         ["Decision time", "time of the worker-selection call that bound one task"],
         ["Coordinator scheduling time", "total time of all policy calls in a run, including calls that returned nothing"],
         ["Paired effect", "geometric-mean change of makespan between two conditions within the same blocks"],
         ["Holm correction", "step-down adjustment of p-values over a family of tests"],
         ["Equivalence margin", "\u00b12%: an interval inside it supports \u201cno meaningful difference\u201d"]],
        [1.9, 4.4], size=8.5)
r.chapter_plain("Appendix C. Raspberry Pi Validation Plan (summary)")
r.numbered([
    "Record device and OS; connect by cable; check ping and optionally iperf3.",
    "Create the Python environment on the Pi (numpy, Pillow, psutil); copy `src` and `pyproject.toml`; install the package without its heavy dependencies; start the node with a token and `--persistent`.",
    "Check the handshake from the laptop; run the laptop base profile at the experiment's compute level.",
    "Run `scripts/calibrate_link.py --remote-host <PI_HOST> --remote-port <PI_PORT> --denoise-iterations <LEVEL>` and read the Pi kernel times, payload sizes and transfer time.",
    "Generate the design with `scripts/make_pi_design.py`; run 13 blocks of 5 conditions per level, recording `vcgencmd` temperature and throttling before and after.",
    "Analyse with the standard tool and apply the fixed decision rule. If the Pi kernel time is more than an order of magnitude slower than a laptop E core, record that as the result.",
])
r.para("Until this is done, no statement about a real remote device, real network or the Raspberry Pi may be made as a result.")
r.references()

OUTD = OUT + r"\05_Final_Project_Report"
r.save(OUTD + ".docx")
pages, words = export_pdf(OUTD + ".docx", OUTD + ".pdf")
print("pages", pages, "words", words, "refs", len(r.cite_order))
