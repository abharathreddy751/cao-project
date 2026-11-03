import sys
sys.path.insert(0, r"D:\cao project\publications\_work")
from ieee_docx import IEEEDoc, export_pdf

FIG = r"D:\cao project\publications\figures"
OUT = r"D:\cao project\publications"

d = IEEEDoc(
    "Prediction-Aware Dynamic Task Scheduling on a Hybrid CPU/GPU Laptop: Architecture, Implementation and Measured Results",
    ["Lakshay S", "Arkkadu Bharath Reddy"],
    ["Reg. Nos. 26MAI0064, 26MAI0058 \u2014 Course: Computer Architecture and Organization", "[Institution, department, guide and e-mail to be filled by the authors]"],
    "This draft describes the implementation of the project and analyses its results. The framework (about 11,900 lines of Python in the runtime, 8,200 in scripts, 488 automated tests) executes the tasks of a dependency graph on "
    "pinned performance-core and efficiency-core worker processes, a CUDA worker and an optional remote worker; logs every dispatch with its decision time; verifies every output against a CPU reference; and compares scheduling "
    "policies in interleaved, seeded blocks with paired bootstrap intervals. We evaluate eligibility-gated greedy dispatch (the base idea, B4), static placement, informed rules, HEFT, PEFT and a proposed rank-ordered, "
    "work-conserving dispatcher that uses a runtime model learned from logs. On a workload in which 16 of 64 image chains are 60 times more expensive in a parameter that size-keyed tables cannot see, the proposed dispatcher "
    "shortened makespan by 19.3% (6P+7E, 12 chain orders never used before) and 20.5% (2P+7E, 8 orders) relative to B4, was level with an informed hand rule (+0.66% and +0.27%), and was equivalent to B4 where nothing is hidden. "
    "The gain depends on the cost ratio and on the number of heavy chains (about 27% with 4 or 8 heavy chains, 4% with 40). HEFT with the same model matches it; PEFT does not. Scheduling overhead is measured two ways; "
    "an inefficiency in the dispatch loop was found and shown not to explain the gain. In emulation, accurate remote predictions did not translate into a gain. A Raspberry Pi has not yet been measured.",
    "heterogeneous scheduling, DAG, runtime prediction, hybrid cores, CUDA, implementation, empirical evaluation, reproducibility",
)

d.h1("Introduction")
d.para("Reviews 1 and 2 surveyed the literature, patents and products and identified nine gaps, chiefly the lack of real-hardware evidence, overhead accounting, interval statistics and informed baselines for DAG "
       "scheduling on heterogeneous resources. Review 3 reports the implementation built to close them and the results obtained with it. The contributions are: (1) a reproducible runtime and experiment framework "
       "for real task graphs on P/E cores, a CUDA GPU and an external worker; (2) a family of policies and estimators that includes the base idea B4, HEFT and PEFT ({{heft,peft}}) and a proposed predicted-rank dispatcher; "
       "(3) a measured map of when prediction helps; (4) a diagnosis of scheduling overhead; and (5) a validated path for a Raspberry Pi worker, so that the next stage can be run without further code changes.")

d.h1("System Architecture")
d.h2("Overview")
d.para("Fig. 1 shows the architecture. A workflow description (a Pegasus YAML file for Montage, or an in-memory image-chain generator) is converted into a DAG of tasks with declared inputs, outputs and eligible pools. "
       "The *coordinator* owns the ready queue, calls the scheduler policy whenever tasks become ready or workers become idle, and dispatches each task to a worker. Workers are separate processes pinned to one logical processor "
       "each (6 P workers or 2 P workers plus 7 E workers on the test machine); the coordinator runs on a reserved E core. A CUDA worker runs the GPU variants of three image stages, and a *remote worker* is a proxy process "
       "on the laptop plus a node process that serves tasks over TCP, on a local core behind a delay shim (emulation) or on another machine (real).")
d.figure(FIG + r"\fig_architecture.png", "Architecture of the implemented framework.", 3.3)
d.h2("Runtime components")
d.bullets([
    "**DAG and ready queue.** Tasks become ready when all parents completed (dependency counters, as in the base patent\u2019s in-degree gating); the ready queue is FIFO and policies may reorder it per dispatch pass.",
    "**Eligibility.** Every policy honours per-task eligible pools through one helper; the coordinator raises an error on an ineligible or non-idle placement (zero such errors in all reported sessions).",
    "**External-command tasks.** Montage jobs run as processes without a shell, with timeouts, process-tree kill, declared-output checks and hashing of inputs and outputs.",
    "**Failure semantics.** Per-task terminal status; dependents of a failed task are marked not-run; runs restart from a clean directory; failed or timed-out runs are kept and flagged.",
    "**Event log.** One JSON line per event (ready, dispatched, submitted, completed, failed); each dispatch carries the decision time and, for EFT-type policies, the candidate costs.",
    "**Remote path.** Frame-size caps, a token-based mutual HMAC handshake for non-loopback hosts, real artefact payloads, proxy-side timestamps for a foreign clock, and (added during this work) a persistent node and an adapter that connects to an already running node.",
])
d.h2("Estimators and policies")
d.para("Estimators implement one interface and can be swapped without touching the scheduler: a constant per type and pool (E0), a solo-profile lookup (E1), an analytic size model (E2), a moving history (E3), a ridge model on "
       "occupancy context (E4), CatBoost and a small MLP, and an offline replay oracle (E5, reference only). The proposed *ParamModel* fits, per (stage, pool), ridge regression on the numeric task parameters and the size "
       "that vary in the logs and on their pairwise products; it names no stage or parameter and refuses a stage or pool it has not seen. Policies include B0\u2013B5, random, EFT with each estimator, a rank-ordered EFT, "
       "HEFT, PEFT, informed hand rules, and *PredictedRankGreedy* (the proposed dispatcher): order ready tasks by predicted upward rank, bind only to an idle eligible worker, choose the one with the smallest predicted time.")
d.h2("Dispatch pass of the coordinator")
d.para("Whenever a task becomes ready or a worker becomes idle the coordinator runs one *dispatch pass*. The pass is the same for all policies; only the two policy hooks differ:")
d.numbered([
    "take the ready tasks from the FIFO queue and call the policy’s *order_ready* hook (default: unchanged; hand rules sort by a parameter; the proposed policy sorts by predicted upward rank);",
    "for each task in the returned order, call *select_worker* (the policy returns a worker or nothing); a late-binding policy may only return an idle eligible worker;",
    "check eligibility and idleness (a violation raises a contract error), bind the task, log the dispatch with the elapsed decision time and the policy’s decision record;",
    "stop the pass when no worker is idle (late-binding policies) or all ready tasks were visited; on completion the coordinator logs the result, releases dependents and calls the policy’s feedback hook.",
])
d.para("The coordinator accumulates the time spent in steps 1 and 2 as its *scheduling time*; the time of each successful call is attached to its dispatch as the *decision time*. Section IV-D shows why the two differ.")
d.table("Event log and run manifest content",
        ["Record", "Fields (selection)"],
        [["task_ready, task_dispatched", "task id, worker, pool, queue wait, worker load, decision time, decision record (candidate wait/transfer/exec/finish)"],
         ["task_submitted, task_completed", "kernel time, start/end timestamps, transfer time, bytes moved, output size and SHA-256"],
         ["worker_ready, run_started, run_finished", "pid, requested and actual affinity, capabilities; makespan, status, tasks per pool"],
         ["run manifest", "condition, policy, seed, instance, warm-up flag, status, error, output verdict and hashes, event-log SHA-256, git commit and dirty flag, source SHA-256, design SHA-256"],
         ["session record", "design hash, machine id, environment hash, blocks completed, preflight log, final status (complete, aborted, crashed)"]],
        [1.1, 2.3], size=7)
d.h2("Experiment framework and dashboard")
d.para("A design file lists conditions, seed, block count, warm-up rule and thresholds; the runner derives a reproducible block plan, runs every condition once per block in random order, checks free memory and mains power before "
       "every block, writes a manifest per run (condition, seed, code hash, environment hash, output hashes, status) and makes event logs read-only. The analysis refuses to pool sessions with different code, environment, label or "
       "design, excludes runs by rules fixed in the design, and computes paired effects with bootstrap intervals, Holm-adjusted *p*-values, minimum detectable effects and a sensitivity pass. A claims registry with 50 entries is re-read "
       "against the stored tables by a test. A local web dashboard shows system state, a replay of runs and, on its last tab, any experiment session side by side (Fig. 2).")
d.figure(FIG + r"\dashboard_compare.jpg", "Dashboard, tab \u201cMontage & GPU\u201d: one B4 run (3858.9 ms) and one run of the proposed dispatcher (3097.0 ms) of the same chain order, with placement, scheduling time and output-hash check.", 3.4)
d.h2("Code and test inventory")
d.table("Implementation inventory (measured by counting lines in the repository)",
        ["Part", "Files", "Lines of Python"],
        [["Runtime package (src/caosched)", "94", "11,863"],
         ["  core (coordinator, pools, DAG, tasks)", "", "2,011"],
         ["  estimators; schedulers; analysis; experiment", "", "1,197; 845; 1,023; 1,126"],
         ["  revival (resource-state policy); study2 (proposed dispatcher)", "", "1,327; 678"],
         ["  dashboard (plus 1,237 lines of HTML/JS); remote; dataset", "", "774; 571; 692"],
         ["Scripts (experiments, analysis, profiling, runbooks)", "72", "8,195"],
         ["Tests", "47", "6,770 (488 tests pass)"],
         ["Version control", "71 commits", "branch revival/resource-state-aware"]],
        [2.2, 0.55, 0.7], size=7)

d.h1("Methodology")
d.h2("Platform and workloads")
d.table("Workloads",
        ["Workload", "Tasks", "Purpose"],
        [["Montage mosaic (real, native Windows build, 9 DSS2 images)", "59", "real scientific DAG; nine 160 s reprojections dominate"],
         ["Uniform image-chain batch (+ CUDA worker)", "257", "no hidden cost; no-harm control"],
         ["Hidden-cost batch: H of 64 chains with 120 vs 2 denoise iterations", "257", "main study; H = 4, 8, 16, 40"],
         ["Dose batch: heavy chains of 6, 15, 40, 120 iterations", "257", "cost-ratio sweep"],
         ["Two-factor batch (size x iterations)", "about 200", "learned-model stress test"],
         ["Image pipeline with remote stages (tile 512, 16 branches)", "68", "emulated remote worker; Pi path"]],
        [2.0, 0.45, 1.0], size=7)
d.para("The machine is a laptop with an Intel Core i5-13500HX (6 P and 8 E cores), an NVIDIA RTX 3050 6 GB (CUDA 12.8 build of PyTorch 2.11), 15.7 GB RAM and native Windows 11. Each session records an environment hash; results from "
       "different machines are never pooled. Montage was built natively with a MinGW-w64 toolchain after ten documented workarounds; three sequential reference runs gave identical mosaic hashes (maximum absolute "
       "difference 0.0), correct WCS headers and 147 dependency edges equal to the generator\u2019s own.")
d.table("Montage reference runs: median wall time per task type (three identical sequential runs, 59 tasks each)",
        ["Task type", "n", "Median (s)", "Range (s)"],
        [["mProject (reprojection)", "27", "160.57", "141.02–169.89"],
         ["mDiffFit (overlap fit)", "108", "0.251", "0.041–1.036"],
         ["mBackground", "27", "0.336", "0.303–0.610"],
         ["mConcatFit / mBgModel / mImgtbl", "3 each", "0.207 / 0.379 / 0.094", "–"],
         ["mAdd / mViewer", "3 each", "0.870 / 4.157", "–"],
         ["Total sequential makespan", "3 runs", "1459.4, 1467.1, 1469.3", "outputs identical (SHA-256)"]],
        [1.5, 0.4, 0.8, 0.75], size=7)
d.h2("Procedure and statistics")
d.para("The effect of a condition against a reference is the paired geometric-mean change of makespan within interleaved blocks, with a percentile bootstrap interval stratified by workload instance (10,000 resamples) and a "
       "Holm-adjusted sign-flip *p*-value over the confirmatory family. Registered sessions were pre-registered with amendments. Overnight sessions are *exploratory*: plan and design hash were written before each run, each design was "
       "run once, and the plan fixed the reading of the result in advance. Chain orders are shuffles of the 64 chains seeded by an integer; orders used for model fitting (coverage) are disjoint from evaluation orders.")

d.h1("Results")
d.h2("Montage: a valid null result")
d.para("On the 59-task mosaic with 6 P and 7 E workers (9 blocks, registered), predictive EFT variants and HEFT were 1.4% to 1.7% *slower* than static use of the P cores (intervals above 0), learned models 9% to 14% slower, "
       "and B4 47.9% slower (95% interval +37.5 to +54.6). The profile explains it: every Montage task prefers P cores by a factor of 2.3 to 3.6 and nine equal tasks dominate, so no placement can beat \u201cuse the P cores\u201d and "
       "any use of E cores costs time.")
d.h2("Hidden-cost workload")
d.para("Registered sessions with two chain orders each gave the proposed dispatcher \u221220.39% [\u221221.2, \u221219.3] (30 blocks, 6P+7E) and \u221221.10% [\u221221.5, \u221220.7] (20 blocks, 2P+7E, model refitted by one command) relative to B4. "
       "To test generalisation, exploratory sessions used chain orders never used before (Table V, Fig. 3). The dispatcher was faster than B4 in all 12 and all 8 orders; the informed hand rule, which sorts chains by the "
       "heavy parameter without any model, gave the same gain, and the difference between dispatcher and rule had intervals inside \u00b12%.")
d.table("Unseen chain orders (exploratory); effects relative to B4 unless noted (negative = shorter)",
        ["Session", "Blocks / orders", "Dispatcher", "Hand rule", "P-only", "Dispatcher vs rule"],
        [["6P+7E, H=16", "36 / 12", "\u221219.32% [\u221220.0, \u221218.6]", "\u221219.85%", "+3.68%", "+0.66% [\u22120.2, +1.5]"],
         ["2P+7E, H=16", "24 / 8", "\u221220.45% [\u221221.2, \u221219.8]", "\u221220.67%", "+45.77%", "+0.27% [\u22120.2, +0.8]"],
         ["6P+7E, H=4", "12 / 4", "\u221227.65% [\u221234.0, \u221218.7]", "\u221226.94%", "\u221211.56%", "\u22120.98% [\u22123.1, +1.2]"],
         ["6P+7E, H=8", "12 / 4", "\u221226.76% [\u221227.9, \u221225.7]", "\u221226.93%", "\u221215.77%", "+0.24% [\u22120.4, +1.0]"],
         ["6P+7E, H=40", "12 / 4", "\u22123.81% [\u22125.1, \u22121.9]", "\u22125.15%", "+23.13%", "+1.42% [\u22120.7, +4.5]"]],
        [0.75, 0.55, 1.0, 0.5, 0.45, 0.85], span=True, size=6.5)
d.figure(FIG + r"\fig_per_order.png", "Per-order change in makespan of the dispatcher against B4 (blue) and the hand rule (green).", 3.4)
d.figure(FIG + r"\fig_dose_heavy.png", "Gain over B4 versus heavy:light cost ratio (left) and number of heavy chains (right).", 3.4)
d.para("**Dose-response.** Holding 16 heavy chains and raising their cost ratio from about 3 to 60 gave \u22122.6%, +0.6% (not significant), \u22126.1% and \u221219.9% in a first pass of four orders; a follow-up with eight further orders gave "
       "\u22121.3% (ratio 7.5) and \u22122.9% (ratio 20). The first-pass irregularity was order-specific: the gain is small, about 1% to 3%, up to a ratio of 20 and large only near 60. **Heavy-chain count.** With the ratio fixed "
       "the gain is largest when few chains are heavy and falls as they become the majority (Fig. 4), consistent with a tail effect in which blind dispatch starts a heavy chain late or on a slow core.")
d.h2("Registered results and model accuracy")
d.table("Selected registered claims (pre-registered designs; effect = paired makespan change, negative = shorter)",
        ["Claim", "Workload", "Comparison", "Effect", "Status"],
        [["U1", "uniform batch + GPU", "predictive EFT vs static P-only", "−27.56%", "supported"],
         ["U2", "uniform batch + GPU", "predictive EFT vs B4", "+0.25%", "equivalent (±2%)"],
         ["H1", "hidden cost (first run)", "rank EFT with learned model vs B4", "−13.78%", "supported"],
         ["G1, G3", "hidden cost 6P+7E", "dispatcher vs B4; table predictor vs dispatcher", "−20.39%; +75.19%", "supported"],
         ["G4", "hidden cost 6P+7E", "dispatcher vs hand rule", "−1.54% (rule faster)", "not resolved"],
         ["R1, R3", "hidden cost 2P+7E", "dispatcher vs B4; table predictor vs dispatcher", "−21.10%; +57.65%", "supported"],
         ["R4", "hidden cost 2P+7E", "dispatcher vs hand rule", "+0.38%", "equivalent"],
         ["N1", "uniform batch", "dispatcher vs B4", "−0.45%", "equivalent"],
         ["C1, C2", "two-factor", "size-only rule, static P-only vs dispatcher", "+17.44%; +17.13%", "supported"],
         ["C3", "two-factor", "dispatcher vs B4 (≥2% faster?)", "+0.95% [−0.9, +2.8]", "not supported"],
         ["V1", "contended mixed DAG", "oracle gate (≥5% headroom)", "B4 1.24% faster than oracle", "gate failed"]],
        [0.4, 0.95, 1.4, 0.7, 0.6], span=True, size=6.5)
d.para("The runtime model is accurate where it matters. On a held-out two-factor session the predictions for the heavy classes were within 8% of the measured time (0.605 s predicted versus 0.565 s measured for 256-pixel chains with 300 iterations on a P core; "
       "0.122 s versus 0.112 s for 1024-pixel chains) but the lightest class was poorly predicted (17.6 ms versus 4.1 ms on a P core), which does not matter for makespan because such tasks are short. Fitting uses a few coverage sessions "
       "on the same machine; a new pool layout is handled by the same command, as shown for the 2 P + 7 E configuration.")
d.h2("Established list schedulers and ablations")
d.para("Driven by the same learned model on six further unseen orders (24 blocks), HEFT gave \u221218.08% and PEFT \u22122.58% relative to B4, rank-ordered EFT with early binding \u221213.21%, and the dispatcher \u221218.97%; HEFT versus the dispatcher was "
       "+1.10% [\u22120.53, +2.81], PEFT +20.23%, early-binding EFT +7.11%. The ordering and the late (idle-only) binding both contribute; the static plan of HEFT is competitive on this workload.")
d.h2("Scheduling overhead")
d.para("Two overhead figures exist. *Per-dispatch decision time* (the time of the worker-selection call that bound a task) is 6.8 ms per run for B4 and 15.5 ms for the dispatcher (257 tasks, about 0.5% of makespan). *Coordinator scheduling time* "
       "(all calls of the policy, including those that returned nothing) is 0.197 s and 0.100 s. The difference was traced with an instrumented run: because a CUDA worker that no task can use is always idle, the dispatch loop "
       "never exits early, and 10,042 of 10,299 calls of B4\u2019s selection function returned nothing. A decision-preserving fix in a separate adapter reduced coordinator time to 8 ms (B4) and 24 ms (dispatcher) and moved the dispatcher\u2019s gain "
       "from \u221219.47% to \u221220.28% (0.8 percentage points) with all 78 runs verified; the fix is not applied to the source.")
d.figure(FIG + r"\fig_overhead.png", "Per-dispatch decision time and coordinator scheduling time per run, before and after the dispatch-loop fix.", 3.4)
d.h2("GPU and remote execution")
d.para("At task level the GPU is up to 15.1 times faster for the edge-detection stage at 1024 px and 5.2 times for feature extraction, with outputs equal within tolerance; the denoise stage gains only 1.4 times and not at small tiles. "
       "No workflow-level gain from CPU/GPU placement was established; in 20,046 stored B4 dispatches with the GPU worker, 93.6% had a single eligible idle worker. For remote execution, an emulated worker (a node on one local E core behind a loopback socket "
       "and a delay shim) was tested at two compute levels. At level 30 the predictive policy used the remote worker (1.7 tasks per run) with accurate predictions (predicted vs measured execution 0.1457 vs 0.1464 s and transfer 0.0937 vs "
       "0.0943 s over 44 placements) yet was 3.78% [+2.27, +5.58] *slower* than without it (Fig. 6). Prediction accuracy did not become scheduling value in this regime. A loopback rehearsal of the complete Raspberry Pi command chain "
       "(profile, calibration with an external node, design generation, 25 runs, analysis) passed after a defect in the node (it served only one client) was fixed.")
d.figure(FIG + r"\fig_remote.png", "Emulated remote worker: effect on EFT makespan at compute level 1 (registered) and level 30 (overnight); error bars are 95% intervals.", 3.4)
d.h2("Summary of claims")
d.table("Claim status after the project (50 registered claims; selection)",
        ["Status", "Claim"],
        [["Supported", "rank-ordered dispatch beats B4 by 19\u201328% on cost-skewed workloads; equals the informed rule; no harm where nothing is hidden; static P-only is worse; HEFT with the same model is level with it"],
         ["Not established", "advantage over an informed rule; resource-state-aware improvement; GPU-contention opportunity; workflow-level GPU scheduling gain; remote offloading benefit; Raspberry Pi results"],
         ["Not supported / null", "gain on Montage; gain on the two-factor workload (+0.95% [\u22120.9, +2.8]); remote worker helping EFT at level 30"]],
        [0.8, 2.6], size=7)

d.h2("Sessions executed and integrity checks")
d.table("Timed sessions of the final study (all outputs verified; hashes of event logs checked)",
        ["Group", "Sessions", "Blocks", "Runs", "Label"],
        [["Unseen orders 6P+7E / 2P+7E", "2", "37 / 25", "148 / 100", "real"],
         ["Dose-response (ratio 3, 7.5, 20, 60) and follow-up (7.5, 20)", "6", "52 + 50", "208 + 200", "real"],
         ["HEFT/PEFT/rank-EFT vs dispatcher", "1", "25", "150", "real"],
         ["Heavy-chain count 4, 8, 40", "3", "39", "156", "real"],
         ["Dispatch-loop A/B", "1", "13", "78", "real"],
         ["Reproduction of the registered design", "1", "11", "55", "real"],
         ["Emulated remote pool, level 30", "1", "13", "65", "emulation"],
         ["Loopback rehearsal of the Pi command chain", "1 (+1 failed)", "5", "25 (+25 failed)", "emulation"]],
        [1.8, 0.55, 0.5, 0.55, 0.45], size=7)
d.para("In every session of the table all runs finished with status ok and verified output, event-log hashes matched the manifests, the design hash matched, and a script re-derived each reported table from the raw logs "
       "(exit status 0 for every analysis). The only failed runs are the 24 of the first rehearsal attempt, kept as evidence of the node defect described below.")
d.h2("Defects found and corrected during the work")
d.table("Defects, how they were found and what was done",
        ["Defect", "Found by", "Action"],
        [["Learned model applied to a different profile than it was fitted on", "audit of earlier phases", "profile binding recorded in the model; refusal on mismatch; tests"],
         ["Worker-pool rebuild between conditions created cold workers (two-humped makespans)", "pilot analysis", "one pool for all conditions"],
         ["Decision-context logging cost 3% of makespan in EFT", "paired comparison", "no-context variants; scheduling-cost guard (25%)"],
         ["Remote node served one client then exited", "loopback rehearsal (24 runs failed)", "persistent mode and test"],
         ["Calibration ignored the compute level; no external host option", "code reading", "options added; test"],
         ["Idle CUDA worker defeats the dispatch loop’s early exit", "overhead diagnosis", "quantified; fix in a separate adapter; source fix proposed"],
         ["Analysis tool labels the primary family “confirmatory” by default", "review", "documented; overnight sessions stay exploratory by plan"]],
        [1.6, 0.8, 1.0], size=7)
d.h2("Readiness for the Raspberry Pi stage")
d.para("The stage needs no further code change. On the Pi: a Python 3.11 environment with numpy, Pillow and psutil, the package installed without its heavy dependencies, and the node started with a token and the persistent option. "
       "On the laptop: a base profile at the experiment’s compute level, link calibration against the Pi (kernel times, payload sizes, transfer time as a + b·bytes), a generated design with five conditions (static, B4 and EFT without remote; "
       "B4 and EFT with remote), 13 blocks per compute level, and the standard analysis with a decision rule fixed beforehand (the remote worker helps only if the interval of EFT with versus without it lies below zero). "
       "A runbook lists every command, the measurements to record on arrival (temperature, throttling flag, network throughput), and the rollback to the local demonstration.")

d.h1("Analysis and Discussion")
d.para("**Mechanism.** The dominant effect is ordering: serving predicted-heavy work first removes the tail created by blind dispatch. That is why an informed rule achieves the same result and why the effect depends on the "
       "share and cost ratio of heavy chains. The learned model matters because it supplies the knowledge a person would otherwise hard-code; its value is that it needs no such knowledge and is retrained by one command for a new "
       "pool layout (shown for 2 P + 7 E). **Prediction accuracy is not enough:** remote predictions were accurate to under 1% yet gave no gain, in line with the finding of {{ilyushkin}} that order can matter more than estimate "
       "accuracy, which we now see on real executions. **Overhead matters but did not decide the result.** Scheduling time is 2% to 5% of these 3 to 9 second runs for late-binding policies and 1% to 2% of makespan could be recovered by the loop fix; "
       "the gain over B4 changes by under one point.")
d.para("**Relation to the literature.** The surveyed learned schedulers report 11% to 27% improvements in simulation ({{lachesis,metarl,iov,tan25}}). Our figures are measured on real hardware with intervals and an informed "
       "baseline, are of the same order on cost-skewed workloads, and show that most of the gain is available to a much simpler rule. We therefore do not claim superiority over learned DRL schedulers, which we did not run.")
d.para("**Threats to validity.** The workload family is designed to have a hidden cost; one machine; runs with a dirty working tree and different source hashes (never pooled); overnight sessions exploratory; the first run after a "
       "reference computation is about 2% slower; HEFT and PEFT are static plans verified on the papers\u2019 worked examples; remote results are emulation. The Raspberry Pi stage will test whether a real remote worker that adds capacity changes the picture.")

d.table("This implementation compared with the closest published systems",
        ["System", "Evaluation", "Hardware", "Overhead reported", "Intervals", "Informed baseline"],
        [["{{lachesis}}", "simulation", "simulated cluster", "inference time", "no", "no"],
         ["{{adprl}}", "trace simulation + testbed", "3 Jetson boards", "no", "no", "no"],
         ["{{rodriguez}}", "real", "Zynq CPU+FPGA", "yes", "no", "no"],
         ["{{lotaru}}", "simulation", "simulated heterogeneous cluster", "prediction error", "median errors", "HEFT with true runtimes"],
         ["{{starpu}}", "real", "CPU+GPU nodes", "history models", "not assessed", "no"],
         ["This work", "real executions", "P/E cores, RTX 3050, emulated remote", "two metrics per run", "paired bootstrap, Holm", "yes (hand rules)"]],
        [0.55, 0.7, 0.8, 0.55, 0.55, 0.45], span=True, size=6.5)
d.h1("Existing versus Proposed Implementation")
d.table("Differentiation between the existing (base) implementation and the proposed one",
        ["Aspect", "Existing (B4 / base patent idea)", "Proposed"],
        [["Order of ready tasks", "first-come first-served", "predicted upward rank"],
         ["Worker choice", "first idle eligible worker (P before E)", "idle eligible worker with least predicted time"],
         ["Cost knowledge", "none", "model learned from logs; retrained by one command"],
         ["Decision cost per run", "7 ms (coordinator 0.20 s)", "15 ms (coordinator 0.10 s)"],
         ["Makespan, hidden cost, 16 heavy", "reference", "\u221219.3% (6P+7E), \u221220.5% (2P+7E)"],
         ["Makespan, nothing hidden", "reference", "+0.45% (equivalent within \u00b12%)"],
         ["Evidence", "—", "real runs, paired intervals, unseen orders, 50 claims, 488 tests"]],
        [0.9, 1.25, 1.3], size=7)
d.h1("Conclusion and Future Work")
d.para("The implementation delivers a reproducible framework and a measured account of when prediction-aware scheduling helps on a hybrid laptop: substantially when a hidden cost makes ordering decisive, not at all when it does not, "
       "and never beyond an informed rule. Next: (1) measure the Raspberry Pi 5 over a real link with the prepared runbook; (2) a second workload family; (3) apply and test the dispatch-loop fix in the source; (4) repeat the headline "
       "experiment on a clean, committed tree; and (5) obtain a professional prior-art search before any IPR filing.")
d.references()
OUTD = OUT + r"\03_Review3_Implementation_Results_IEEE"
d.save(OUTD + ".docx")
pages, words = export_pdf(OUTD + ".docx", OUTD + ".pdf")
print("pages", pages, "words", words, "refs", len(d.cite_order))
