import sys
sys.path.insert(0, r"D:\cao project\SUBMISSION_FINAL\_build")
from ieee_docx2 import IEEEDoc, export_pdf

FIG = r"D:\cao project\publications\figures"
OUT = r"D:\cao project\SUBMISSION_FINAL\_draft"

d = IEEEDoc(
    "AI-Assisted Heterogeneous Computing for Dynamic Task Scheduling and Offloading: A Review of Publications, Patents, Products and Technology Trends",
    ["Lakshay S", "Arkkadu Bharath Reddy"],
    ["Reg. Nos. 26MAI0064, 26MAI0058 \u2014 Course: Computer Architecture and Organization", "Guide: Dr. Yokesh Babu S, Associate Professor Grade 1. [Institution, department and e-mail to be filled by the authors]"],
    "Modern processors, GPUs and edge devices differ in speed, power and availability, so deciding *where* and *in what order* the tasks of a dependency graph run "
    "has become a first-order performance problem. This review surveys the field for the project \u201cAI-assisted heterogeneous computing framework for dynamic task "
    "offloading and scheduling\u201d. We (i) define the domain and substantiate the problem with verified statistics on data-centre energy, accelerator adoption, "
    "edge growth and measured under-utilisation; (ii) compare 13 recent publications on DAG scheduling and dependent-task offloading ({{lachesis,dddqn,wang22,rodriguez,song23,gong23,sata,cao24,nieto,adprl,metarl,iov,tan25}}) "
    "along method, workload, platform, metric and limitation; (iii) analyse the base patent US 11,561,826 B1 at claim level and six related patents from IBM, Intel, "
    "Samsung, Apple and Google; (iv) compare ten company and open-source products that schedule work on heterogeneous resources; and (v) summarise technology "
    "trends. Three findings structure the remaining work: nearly all learned schedulers are evaluated in simulation, almost none reports its own decision "
    "overhead or a statistical interval, and none compares against an *informed* simple rule. These gaps motivate a measured, overhead-accounted study on real hardware; "
    "the closing section records how the project\u2019s final benchmark of static plans against dynamic dispatch on a CPU+GPU laptop answers each gap.",
    "heterogeneous computing, DAG scheduling, task offloading, edge computing, reinforcement learning, runtime prediction, patents, survey",
)

# ------------------------------------------------------------------ I
d.h1("Introduction: Domain and Scope")
d.para("*Heterogeneous computing* combines processing elements with different speeds, instruction sets, memories and power behaviour in one system: performance (P) and efficiency (E) "
       "cores in a laptop processor, a discrete GPU, an FPGA, a single-board computer such as a Raspberry Pi 5 {{rpi5}} (four Arm Cortex-A76 cores at 2.4 GHz), or a remote edge or cloud node. "
       "Applications are rarely a single kernel. They are *workflows* or *task graphs*: directed acyclic graphs (DAGs) whose nodes are tasks and whose edges are data dependencies, "
       "for example the Montage astronomy mosaic workflow ({{montage,wfcommons}}), image-analysis pipelines, or the job stages of a data-processing cluster ({{decima}}).")
d.para("A *scheduler* decides, whenever tasks become ready, (a) the **order** in which ready tasks are served and (b) the **placement** of each task on a worker. *Offloading* is the "
       "special case in which the candidate worker is on another device and a transfer cost must be paid. Both decisions depend on three kinds of information: the structure "
       "of the graph, the state of the resources (busy, idle, loaded, reachable), and an estimate of how long each task takes on each resource. Classical list schedulers such as "
       "HEFT and PEFT ({{heft,peft}}) assume the estimates are given; learned schedulers ({{lachesis,sata,adprl}}) try to infer a policy from interaction; runtime systems such as StarPU ({{starpu}}) "
       "calibrate per-task performance models.")
d.para("This review is the first deliverable of the project *AI-assisted heterogeneous computing framework for dynamic task offloading and scheduling*. Its research focus is how much "
       "prediction of task execution time is needed to improve real scheduling, once the cost of prediction and of the scheduler itself is counted. Section II substantiates the problem with "
       "statistics. Sections III to V compare publications, patents and company products. Section VI summarises technology trends and their adoption status, and Section VII lists the gaps and records the status of each after the final benchmark. "
       "The final benchmark asks a sharper version of the question: does a *dynamic* scheduler, which decides while the workflow runs, finish sooner than a *static* plan computed beforehand from the same cost model, on a hybrid CPU+GPU workstation?")

# ------------------------------------------------------------------ II
d.h1("Problem Substantiation with Statistics")
d.para("Four independent trends make scheduling on heterogeneous resources important. Each figure below was checked against its source; where only a secondary report was available it is marked.")
d.table("Verified statistics that motivate the problem",
        ["Indicator", "Value", "Source"],
        [["Data-centre electricity use", "about 415 TWh in 2024 (about 1.5% of global electricity); projected about 945 TWh by 2030 in the IEA base case; AI-optimised facilities more than quadruple", "{{iea}} (secondary reports of the IEA report)"],
         ["Accelerated HPC systems (TOP500, Jun. 2025)", "232 of 500 systems (46.4%) use accelerators; they hold 59.7% of cores and about 86.2% of peak FP64 flops", "{{top500}} (secondary analysis)"],
         ["Connected IoT devices", "18.5 billion at end-2024 (+12%); 21.1 billion in 2025 (+14%); about 39 billion forecast for 2030", "{{iotanalytics}}"],
         ["Under-utilised clusters", "Alibaba co-located cluster (1,313 machines): over 80% of the time at 10\u201330% CPU use; Google production traces: 20\u201340% most of the time", "{{cheng18}} (read in full text)"],
         ["Hybrid cores in client CPUs", "Intel Thread Director listed for 12th, 13th and 14th generation Core processors (11 product families)", "{{intel_td}}"]],
        [0.95, 1.55, 0.85], size=7)
d.para("The first three rows show that the *amount* of heterogeneous capacity is large and growing: electricity demand rises with AI workloads, accelerated systems dominate the peak performance of the "
       "largest machines, and tens of billions of edge devices produce data that may have to be processed close to where it is created. The fourth row shows that capacity is often *wasted*: a cluster "
       "that spends most of its time at 10\u201330% CPU use is not limited by hardware but by how work is placed. Scheduling quality therefore translates directly into energy, cost and latency.")
d.para("**Measured heterogeneity on our test machine.** The project test bed is a laptop with an Intel Core i5-13500HX (6 P cores, 8 E cores), an RTX 3050 6 GB GPU and 15.7 GB RAM running native Windows. "
       "Fig. 1 (left) shows the median kernel time of three image-pipeline stages pinned to one P and one E core: a 512-pixel denoise task with 30 iterations takes 156 ms on a P core and 560 ms on an E core, "
       "i.e. 3.6 times longer; the two shorter stages are 2.8\u20133.3 times slower. On the GPU (right) the same convolution-type stage is up to 15 times faster at 1024 pixels but only breaks even at small tiles, because host-device "
       "copies dominate. A scheduler that ignores these ratios sends heavy work to slow cores.")
d.figure(FIG + r"\fig_heterogeneity.png", "Measured heterogeneity on the project machine. Left: median kernel time of one stage task on a P and an E core (log scale). Right: GPU speed-up of three stages versus tile size (CPU/GPU outputs equal within tolerance). Source: project profile and GPU spike files.", 3.4)
d.para("**Measured cost of blind placement.** On a workload of 64 independent image chains in which 4 to 40 chains are 60 times more expensive in one parameter, a blind greedy dispatcher (first idle eligible worker) "
       "needed 5% to 37% more time than a rule that merely knew which chains were heavy (25% to 37% when 4 to 16 chains were heavy) (paired, 12\u201336 blocks per setting, 95% intervals in the project report). On the 59-task Montage mosaic the first nine "
       "reprojection tasks take about 98% of the 1.46 \u00d7 10^{3} s sequential run, so any placement error in those nine tasks dominates the result. Section III shows that the published learned schedulers do not "
       "measure situations of this kind on real hardware.")

# ------------------------------------------------------------------ III
d.h1("Survey: Comparative Analysis of Existing Solutions")
d.h2("Method of the survey")
d.para("We analysed the 12 papers supplied as base papers (full text read) and one further paper at abstract level ({{cao24}}), plus classical and related work used for positioning. For each paper we extracted the "
       "algorithm, workload, platform, metrics, reported result and limitations, and verified claims against the PDF. A keyword check over the 12 full texts found no occurrence of \u201cconfidence interval\u201d, "
       "HEFT appears in five papers and PEFT in two, and measured decision (inference) time is mentioned in only two.")
d.table("Comparison of recent solutions (DAG scheduling and dependent-task offloading)",
        ["Ref.", "Method", "Workload / data", "Platform", "Reported result", "Limitation for our goal"],
        [["{{lachesis}}", "GNN + RL selects task; DEFT with task duplication places it", "TPC-H DAG jobs", "Simulated cluster, 50 executors", "up to 26.7% makespan, 35.2% speedup vs. 7 baselines", "simulation; speed-only heterogeneity; no variance test"],
         ["{{dddqn}}", "Dueling double DQN, MDP", "Google Cloud Jobs, Alibaba trace", "Trace-driven simulation", "shorter response time, better load balance", "cluster level; DRL cost; no hardware"],
         ["{{wang22}}", "Off-policy RL + seq2seq", "Synthetic DAGs", "MEC simulation", "approaches optimal latency/energy", "synthetic; simulated edge"],
         ["{{rodriguez}}", "FastFit / MultiFastFit lightweight scheduling", "4 benchmarks", "Zynq UltraScale+ CPU+FPGA (real)", "up to 2x over an auto-tuned scheduler; overhead measured", "FPGA specific; no DAG, no prediction"],
         ["{{song23}}", "Bidirectional GCN + FC net; OCT + duplication", "heterogeneous DAG scenarios", "Simulation", "better than compared DAG schedulers", "heavy model; simulation"],
         ["{{gong23}}", "DTOS: parallel DNNs, priority replay", "Synthetic DAGs, dynamic channel", "MEC simulation", "lower delay and energy", "network simulation only"],
         ["{{sata}}", "SATA-DRL (DQN), MDP", "25-node Montage task graphs (simulated)", "Simulated MEC", "lower makespan and deadline misses", "simulation; no real Montage run"],
         ["{{cao24}} (abstract)", "GAT + DRL, multidiscrete actions", "Synthetic distributed data", "Simulated MEC", "adapts to simple and complex MEC", "synthetic; heavy model"],
         ["{{nieto}}", "Distributed actor-critic, binary offloading", "2 simulated scenarios", "5G edge-cloud (simulated)", "better QoE / energy", "no DAG dependencies"],
         ["{{adprl}}", "ADPRL: dependency-aware reward, joint bandwidth", "Alibaba trace + synthetic", "Simulation + testbed with 1 Jetson Xavier NX and 2 Jetson TX2", "lower completion time and energy", "network-flow focus; DRL cost"],
         ["{{metarl}}", "Meta-RL + seq2seq + NSGA-II", "Simulated DAG tasks", "Simulated edge", "21% less delay, 19% less energy", "simulation; complex model"],
         ["{{iov}}", "DAG-DQN", "Vehicular applications", "Simulated IoV", "16% less time, 19% less energy, 70% faster decisions vs. heuristic", "IoV simulation only"],
         ["{{tan25}}", "GCN-Transformer + PPO; ECT replication heuristic", "DAG applications", "Simulated multicore", "11.09% lower time and power cost", "simulation; heavy model"]],
        [0.28, 0.85, 0.7, 0.65, 0.72, 0.85], span=True, size=6.5)
d.h2("Taxonomy and comparison")
d.para("The papers fall into four families. (1) **Learned selection plus a placement heuristic** ({{lachesis,song23,tan25}}): a GNN or Transformer picks the next task, a classical rule "
       "(OCT, earliest completion time, task duplication) picks the processor; this shrinks the action space but keeps the heuristic as a crutch. (2) **End-to-end DRL for offloading** "
       "({{dddqn,wang22,gong23,sata,cao24,nieto,adprl,metarl,iov}}): MDP formulations with DQN, actor-critic or PPO; the focus is latency and energy under dynamic network conditions. (3) **Lightweight "
       "runtime scheduling** ({{rodriguez}}): low-overhead asynchronous chunk scheduling on a real CPU+FPGA board, without learning. (4) **Prediction-driven list scheduling** ({{lotaru,starpu,heft,peft}}): per-task runtime models feed "
       "HEFT-type or StarPU schedulers. Table III compares the survey on the properties that matter for a real prototype.")
d.table("Property matrix of the surveyed solutions (\u2713 = present in the paper, \u2013 = not found)",
        ["Property", "{{lachesis}}", "{{dddqn}}", "{{wang22}}", "{{rodriguez}}", "{{song23}}", "{{gong23}}", "{{sata}}", "{{nieto}}", "{{adprl}}", "{{metarl}}", "{{iov}}", "{{tan25}}"],
        [["DAG dependencies", "\u2713", "\u2013", "\u2713", "\u2013", "\u2713", "\u2713", "\u2713", "\u2013", "\u2713", "\u2713", "\u2713", "\u2713"],
         ["Physical hardware evaluated", "\u2013", "\u2013", "\u2013", "\u2713", "\u2013", "\u2013", "\u2013", "\u2013", "\u2713", "\u2013", "\u2013", "\u2013"],
         ["Learned model in decision loop", "\u2713", "\u2713", "\u2713", "\u2013", "\u2713", "\u2713", "\u2713", "\u2713", "\u2713", "\u2713", "\u2713", "\u2713"],
         ["Decision/inference time reported", "\u2713", "\u2013", "\u2713", "\u2713", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2713", "\u2013"],
         ["Compares HEFT-type list scheduler", "\u2713", "\u2713", "\u2713", "\u2013", "\u2713", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2713"],
         ["Reports confidence intervals", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013"],
         ["Informed simple-rule baseline", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013", "\u2013"]],
        [1.05, 0.3, 0.3, 0.3, 0.32, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3], span=True, size=6.5)
d.para("The matrix is derived from keyword and reading checks of the supplied PDFs (HEFT/PEFT mentions, \u201cconfidence interval\u201d, \u201cinference time\u201d, \u201ctestbed\u201d); the {{cao24}} column is "
       "filled from its abstract only. Two patterns stand out. First, **only two works touch physical hardware** (a CPU+FPGA board in {{rodriguez}}; a three-board Jetson testbed in {{adprl}}), and "
       "neither schedules a real scientific workflow. Second, **no work compares against an informed non-learning rule**, so the benefit that is attributed to learning cannot be separated from the benefit of "
       "simply knowing which tasks are expensive. Reported gains range from 11% to 27% (Fig. 2) but come from different baselines and simulators and are not comparable with one another.")
d.figure(FIG + r"\fig_reported_gains.png", "Best reported reductions in the surveyed papers (grey, all simulation) next to this project\u2019s measured values (blue, real hardware). Baselines differ between bars; the figure shows scale, not a ranking.", 3.4)
d.h2("Related prediction and positioning work")
d.para("Prediction-driven scheduling is not new. {{lotaru}} predicts workflow task runtimes with Bayesian regression and reports that HEFT driven by its predictions stays within a few percent of HEFT with perfect knowledge "
       "(simulation). {{ilyushkin}} study how runtime-estimate accuracy changes workflow scheduling and, according to their abstract, find that under high utilisation the order in which work is processed matters more than "
       "estimate accuracy; we consider this a result to test, not to assume. StarPU ({{starpu}}) has used history-based performance models for CPU/GPU DAG scheduling for over a decade. A 2026 preprint ({{lureda}}) places "
       "AI tools on GPU or CPU with an LLM agent and a runtime monitor on real hardware and compares against HEFT and StarPU, but on DAGs of about four tools.")

d.h2("Static versus dynamic scheduling")
d.para("The classical list schedulers HEFT and PEFT ({{heft,peft}}) are *static*: they compute, before execution, a processor and a start time for every task from a cost matrix. A static plan commits to its estimates; "
       "when a task finishes earlier or later than planned, the assignment does not change. *Dynamic* schedulers decide when a worker becomes idle or a task becomes ready. StarPU ({{starpu}}) is the established runtime "
       "of this kind for CPU/GPU task graphs and calibrates history-based performance models; the learned schedulers of Section III are dynamic as well. Two observations from the survey matter for the project. First, HEFT is "
       "used as a baseline in five of the 13 papers, always in simulation, so the cost of *planning itself* and the plan\u2019s error against real execution are not observed. Second, we found no paper that gives the static and the dynamic scheduler "
       "the *same* runtime model and measures both end to end, including start-up and scheduling time, which is the comparison needed to say what dynamic decisions add. The final benchmark of the project (Review 3) is designed for this comparison.")
d.h2("Strengths and weaknesses by family")
d.para("*Learned selection plus heuristic placement* is the most mature family for DAG scheduling: {{lachesis}} reports that its decision step fits inside tens of milliseconds, and {{tan25}} reduce the action space by "
       "separating task selection from processor allocation. Its weakness is dependence on the expert rule for placement and on training data from a simulator; neither paper shows the trained policy on a machine whose "
       "speed ratios were measured. *End-to-end DRL for offloading* optimises latency and energy under changing channels ({{gong23,adprl,metarl}}); it is well suited to wireless settings in which the network is the "
       "bottleneck, but the evaluated task graphs are small or synthetic and the cost of training and inference on the device that must decide is rarely quantified. *Lightweight runtime scheduling* ({{rodriguez}}) "
       "is the only family that measures overhead explicitly and shows why it matters: for fine-grained work the scheduler can cost more than it gains. *Prediction-driven list scheduling* shows that moderate prediction "
       "error is tolerable in simulation ({{lotaru}}) and that order can dominate accuracy ({{ilyushkin}}); what is missing is a real-execution test of that claim.")
d.h2("Evaluation practice")
d.para("Evaluation practice in the base set is uneven. Baselines are mostly random, round-robin, FIFO or greedy dispatchers and, in five papers, HEFT; none includes a rule that exploits the same information a learned model "
       "would learn. Results are reported as single percentages (e.g. 26.7%, 21%, 19%, 16%) obtained on simulators with different cost models, so that the numbers cannot be pooled or ranked. Repetition counts are seldom stated "
       "and no paper reports interval estimates. For a project whose aim is to say *how much prediction is enough*, these are the practices to improve: real execution, interleaved repetitions, paired intervals, "
       "overhead accounting and informed baselines.")

# ------------------------------------------------------------------ IV
d.h1("Survey: Comparative Analysis of IPRs (Patents)")
d.para("The base patent of the project is US 11,561,826 B1, *Scheduling processing of machine learning tasks on heterogeneous compute circuits*, assigned to Xilinx, Inc. (inventors S. Nagpal, A. Karumannil, V. Jain, "
       "A. K. Patil; application 17/096,136 filed 12 Nov. 2020; granted 24 Jan. 2023; 20 claims, 8 drawing sheets; CPC G06F 9/4881, G06F 16/9024, G06N 3/08) ({{p_xilinx}}). We read the granted document (images of the claims pages) and "
       "searched for related grants on Google Patents. Legal status and expiry dates quoted below are Google Patents assumptions, not legal conclusions, and no freedom-to-operate opinion is implied.")
d.h2("Claim-level analysis of the base patent")
d.para("Independent claim 1 (method) and claim 14 (system) recite: instantiating *kernel objects* of different *kernel types*, each type indicating a compute circuit of a heterogeneous plurality; generating a graph "
       "whose nodes are tasks assigned to one or more kernel objects and whose edges are data dependencies; creating task queues and assigning kernel objects to them; *enqueueing* tasks by threads executing the kernel "
       "objects; and *dequeueing* tasks by those threads and activating the compute circuits to process them. Dependent claims add blocking versus non-blocking kernels (claims 2, 15), several graphs feeding one queue "
       "(3, 16), two kernel objects of the same or different types sharing queues (4, 5, 17, 18), multi-threaded kernels with a configurable thread count (6\u20137), **measuring circuit performance and adjusting the "
       "number of threads** (8), output-buffer addresses and **in-degree counters decremented on parent completion** (9\u201310), utilisation-triggered thread increase (11), a report function for kernel statistics (12) "
       "and concurrently generated graphs (13). The claims do not recite machine learning, prediction of execution time, a transfer-cost model or offloading to a remote device; the title refers to machine-learning "
       "*workloads* being scheduled, not to a learned scheduler. Table IV places the project against this and six other grants.")
d.table("Comparative analysis of patents (IPRs)",
        ["Patent", "Assignee, dates", "What it claims or discloses", "Prediction?", "Relation to our work"],
        [["{{p_xilinx}} US 11,561,826 B1", "Xilinx; filed 2020-11-12; granted 2023-01-24", "Task graph; kernel objects tied to compute circuits; per-kernel task queues; threads enqueue/dequeue; in-degree gating; performance-based thread adjustment", "No", "Base work; mapped to eligibility-gated greedy dispatch (baseline B4)"],
         ["{{p_ibm1}} US 11,740,933 B2", "IBM; filed 2020-07-01; granted 2023-08-29", "Meta pre-processor receives a DAG; a *learning agent assigns a rank* to a task; scheduler runs tasks in rank order on a heterogeneous SoC", "Learned rank", "Closest: rank-ordered dispatch; no idle-worker-only placement or log-derived parameter model in the claim summary"],
         ["{{p_ibm2}} US 11,966,776 B2", "IBM; filed 2021-07-14; granted 2024-04-23", "ML mechanism learns DAG policies, decides whether to drop DAGs, schedules tasks using priorities and *task execution estimates*", "Yes (estimates)", "Learned DAG policy with drop decisions; deadline-oriented"],
         ["{{p_intel}} US 10,186,007 B2", "Intel; filed 2014-12-26; granted 2019-01-22", "CPU+GPU: profiling threads time a portion of work on each device, compute a distribution ratio, split the remaining work", "Online profiling", "Per-run profiling, no DAG, no learned model"],
         ["{{p_samsung}} US 10,162,671 B2", "Samsung; filed 2013-04-11; granted 2018-12-25 (lapsed 2022)", "Predict each task\u2019s duration when the state of a core changes, using solo-vs-concurrent duration ratios; schedule on heterogeneous cores", "Yes", "Contention-aware duration prediction; terminal devices"],
         ["{{p_apple}} US 11,775,811 B2", "Apple; filed 2019-01-08; granted 2023-10-03", "Order algorithms by temporal dependencies, build a graph whose nodes name a processor (CPU, GPU, neural processor), execute by traversing for concurrency", "No", "Static graph-to-processor mapping"],
         ["{{p_google}} US 11,544,113 B2", "Google; filed 2019-12-19; granted 2023-01-03", "Determine resources of an ML workload, number of hosts per accelerator, task specification per host NUMA topology", "No", "Cluster ML placement, not DAG runtime"]],
        [0.8, 0.8, 1.9, 0.5, 1.35], span=True, size=6.5)
d.para("**Observations.** (i) Task graphs, eligibility-gated queues and utilisation-based scaling are claimed by the base patent and cannot be presented as new. (ii) *Rank-ordered dispatch with a learned agent* is "
       "disclosed by IBM\u2019s 2023 grant; any claim to \u201clearning a task priority\u201d must be examined against it. (iii) *Duration prediction for heterogeneous cores* appears in Samsung\u2019s (lapsed) patent and, as task execution estimates, "
       "in IBM\u2019s second grant. (iv) None of the seven documents, as summarised, describes an empirical method for deciding *when prediction is worth its cost* or a decision-overhead accounting. The "
       "project therefore treats B4 as a comparison baseline, not as its own invention, and positions its contribution as an evaluation methodology and a measured study; any patent filing would need a "
       "professional prior-art search first.")

# ------------------------------------------------------------------ V
d.h1("Survey: Comparative Analysis of Company Products")
d.para("Ten products and platforms that decide where work runs were compared on documentation pages (Table V). We record only what the cited page states; where a page did not describe a feature we write \u201cnot stated\u201d.")
d.table("Company and open-source products that schedule on heterogeneous resources",
        ["Product (vendor)", "Scope", "Heterogeneity handled", "Dependencies", "Prediction / learning", "Note"],
        [["Intel Thread Director ({{intel_td}})", "Hybrid client CPU", "P vs E cores; hardware tracks instruction mix per thread at nanosecond granularity and feeds the OS", "No (threads)", "Hardware classification; Intel states it uses machine learning", "12th\u201314th gen Core; no benchmark figures on the page"],
         ["Windows QoS ({{ms_qos}})", "OS scheduler", "QoS levels may restrict threads to a subset of processors or prefer a class (e.g. EcoQoS to efficient cores)", "No", "Heuristics + developer hints", "Priority remains the main metric"],
         ["Linux EAS ({{linux_eas}})", "Kernel", "Asymmetric CPU capacity (big.LITTLE); energy model", "No", "None; energy-model lookup", "Disabled above 80% utilisation; no symmetric topologies"],
         ["AWS Batch ({{aws_batch}})", "Cloud batch", "EC2/Fargate/ECS/EKS compute, containerised jobs", "Not stated on page", "None stated", "Managed provisioning and queueing"],
         ["Kubernetes ({{k8s}})", "Cluster", "Extended resources via filtering/scoring plugins", "Not stated", "None stated", "Filter, score, bind phases"],
         ["Ray ({{ray}})", "Distributed Python", "Declared CPU/GPU resources; spread, node affinity, placement groups", "Task graph by futures (not on page)", "No runtime prediction stated", "Hybrid default policy"],
         ["Apache Spark ({{spark}})", "Data processing", "Executors; dynamic allocation", "Stages by shuffle dependencies (not on page)", "None stated", "FIFO or FAIR; pools"],
         ["Slurm ({{slurm}})", "HPC batch", "GRES: GPUs, MPS, MIG devices as resources", "Not on page", "None stated", "GPU requests by job script"],
         ["StarPU ({{starpu_web}})", "Task runtime (Inria)", "CPU/GPU tasks, heterogeneous scheduling, data transfers", "Task graph", "Performance models (not detailed on page)", "Research runtime"],
         ["Pegasus WMS ({{pegasus}})", "Workflow manager", "HTCondor pools, HPC, cloud; clustering of tasks", "DAG workflows", "None stated", "Generator for the Montage instance used here"]],
        [0.95, 0.55, 1.5, 0.6, 0.85, 0.9], span=True, size=6.5)
d.para("The comparison shows a division of labour. Operating-system and hardware features (Thread Director, Windows QoS, EAS) place *threads* on cores using hardware feedback or energy models but know nothing "
       "about application task graphs. Cluster and batch products (Kubernetes, AWS Batch, Slurm, Spark, Ray) schedule containers or jobs against declared resource requests; none of the cited pages describes "
       "execution-time prediction in the scheduler. Workflow and task runtimes (Pegasus, StarPU) understand DAGs; only StarPU is described as using performance models. NVIDIA Run:ai ({{runai}}) is positioned for "
       "GPU orchestration, but only its landing page was read, so we make no feature claims. **No surveyed product combines application-level DAG knowledge, learned per-resource runtime estimates, and "
       "published decision-overhead measurements on a laptop-class hybrid CPU/GPU system.**")

# ------------------------------------------------------------------ VI
d.h1("Technology Trends")
d.bullets([
    "**Hybrid and AI-accelerated client processors.** P/E cores are standard in recent client CPUs ({{intel_td}}) and Copilot+ PCs require an NPU of at least 40 TOPS ({{copilot}}), so a laptop already exposes three engine types (CPU classes, GPU, NPU) whose placement the application may have to guide.",
    "**Edge growth.** Connected IoT devices grow by about 12\u201314% per year ({{iotanalytics}}); low-cost boards such as the Raspberry Pi 5 {{rpi5}} (2.4 GHz Cortex-A76, Gigabit Ethernet, PCIe 2.0) are realistic remote workers for offloading experiments.",
    "**From heuristics to learning and back.** Learned schedulers progressed from DQN to GNN+PPO and meta-RL ({{lachesis,cao24,metarl,tan25}}), but a 2026 line of work replaces training with LLM agents plus runtime monitors ({{lureda,agentxpu}}); simultaneously, runtime-prediction work ({{lotaru}}) shows that cheap models can approach perfect-knowledge scheduling in simulation.",
    "**Sustainability.** Data-centre electricity is projected to more than double by 2030 ({{iea}}); energy-aware scheduling (Linux EAS {{linux_eas}}) is already in production kernels.",
    "**Reproducible workflow research.** WfCommons ({{wfcommons}}) provides traces and generators for workflows such as Montage; evaluation on real executions rather than traces remains rare.",
    "**Overhead-aware evaluation.** Lightweight schedulers whose cost is measured ({{rodriguez}}) are increasingly motivated by fine-grained tasks; we expect decision overhead and statistical rigour to become standard reporting items.",
])

d.table("Technology trends: introduction and adoption status (as documented in the cited sources)",
        ["Trend", "Introduced / state", "Adoption status", "Relevance to the project"],
        [["Hybrid P/E cores with hardware scheduling hints", "Thread Director listed for 12th\u201314th generation Core ({{intel_td}})", "mainstream in client CPUs; OS-level use", "the test machine has 6 P and 8 E cores; core type changes task time by 2.8\u20133.6 times"],
         ["On-device accelerators (GPU, NPU)", "NPU of 40 TOPS or more required for Copilot+ PCs ({{copilot}})", "shipping in consumer laptops", "a laptop exposes three engine types; the project uses the CUDA GPU as one worker"],
         ["Energy-aware scheduling", "Linux EAS for asymmetric CPUs ({{linux_eas}})", "production kernels, with stated limits", "context for a later energy metric; not measured here"],
         ["Learned DAG scheduling (GNN, DRL)", "LACHESIS to GNN+PPO and meta-RL ({{lachesis,tan25,metarl}})", "research; evaluated in simulation (2 of 13 papers use hardware)", "the project tests a much cheaper model on real execution"],
         ["LLM-agent schedulers", "2025\u20132026 preprints ({{lureda,agentxpu}})", "early research, small DAGs", "not evaluated; noted as a direction"],
         ["Runtime performance models for task graphs", "StarPU history models ({{starpu}}); Lotaru ({{lotaru}})", "established runtime; prediction results in simulation", "same idea, tested with a ridge model and overhead accounting"],
         ["Edge boards as remote workers", "Raspberry Pi 5 ({{rpi5}})", "widely available", "emulated in the project; no real-link result"]],
        [0.85, 1.0, 0.85, 0.95], size=6.5)

# ------------------------------------------------------------------ VII
d.h1("Conclusion and Gaps Carried Forward")
d.para("The survey supports four conclusions. (1) Heterogeneous resources are abundant, growing and under-used, so scheduling matters. (2) The literature on DAG scheduling and offloading is dominated by simulated, "
       "learning-heavy evaluations; physical evidence exists in only two of 13 papers. (3) Patents disclose task graphs, queues, learned task ranking and duration prediction, but not an empirical method that "
       "accounts for the cost of prediction. (4) Products schedule threads or containers; none was found that schedules application DAGs with learned runtime estimates on a hybrid laptop.")
d.para("The gaps carried into the next review are: **G1** real-hardware evidence for DAG scheduling on hybrid CPU+GPU(+remote) systems; **G2** accounting of the scheduler\u2019s own overhead; **G3** statistical reporting "
       "(paired intervals, multiplicity control); **G4** baselines that include informed simple rules and the HEFT/PEFT family; **G5** generalisation across workload instances; **G6** separation of prediction accuracy "
       "from scheduling value; **G7** real remote execution (Raspberry Pi) beyond simulation; **G8** a like-for-like comparison of static plans and dynamic dispatch with one cost model and end-to-end timing. "
       "The table also states the status after the project\u2019s final benchmark (Review 3).")
d.table("Gap analysis: evidence from the survey and what the project does",
        ["Gap", "Evidence in the survey", "Project response and status"],
        [["G1 real hardware", "2 of 13 papers use physical devices; none runs a real scientific workflow", "closed on one laptop: native Windows runtime, P/E pools, CUDA worker; real Montage and image workloads; six workloads in the final benchmark"],
         ["G2 overhead", "decision time reported in 4 of 13 papers", "closed: per-dispatch and coordinator scheduling time logged; end-to-end makespan includes start-up and policy set-up"],
         ["G3 statistics", "no paper reports a confidence interval", "closed: paired log-ratio bootstrap, Holm correction over ten pre-stated contrasts, frozen protocol"],
         ["G4 baselines", "HEFT in 5 papers, PEFT in 2, informed simple rule in 0", "closed: B0–B5, EFT ladder, HEFT, PEFT, HEFT-E2E and a parameter-aware hand rule; the hand rule came within 1% of the dynamic policy"],
         ["G5 generalisation", "single workload instance per setting is common", "partly closed: twenty unseen chain orders earlier, six workloads in the final benchmark; one workload family only"],
         ["G6 accuracy vs value", "accuracy and makespan rarely separated", "closed: accurate remote predictions that gave no gain; GPU model error 23\u201331% reported next to scheduling results"],
         ["G7 remote reality", "simulated networks; one Jetson testbed", "open: node/proxy path and loopback emulation only, labelled as such; no Raspberry Pi or real-network result"],
         ["G8 static vs dynamic", "HEFT used as a baseline in 5 of 13 papers, all in simulation", "closed for this workload family: same ridge model on both sides; dynamic PRED faster than static HEFT by 5.2% (CPU) and 12.2% (strict GPU)"]],
        [0.9, 1.3, 1.3], size=7)
d.para("**Threats to the survey.** The 13 papers are the project’s supplied base set, not a systematic review of the field; keyword counts approximate what a paper reports; patent summaries rely on Google Patents text and "
       "on our reading of the base patent’s claims pages, not on a legal analysis; product statements are limited to what the cited pages state. The figures in Section II were checked against their sources, but two are secondary reports "
       "(IEA, TOP500). These limits are why we speak of “not found in the sources inspected” rather than “does not exist”.")
d.references()
OUTD = OUT + r"\01_Review1_Survey_IEEE"
d.save(OUTD + ".docx")
pages, words = export_pdf(OUTD + ".docx", OUTD + ".pdf")
print("pages", pages, "words", words, "refs", len(d.cite_order))
