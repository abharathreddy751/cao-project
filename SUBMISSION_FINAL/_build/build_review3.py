import sys
sys.path.insert(0, r"D:\cao project\SUBMISSION_FINAL\_build")
from ieee_docx2 import IEEEDoc, export_pdf
import final_data as fd

FIG = r"D:\cao project\publications\figures"
FF = r"D:\cao project\SUBMISSION_FINAL\_fig"
OUT = r"D:\cao project\SUBMISSION_FINAL\_draft"

d = IEEEDoc(
    "Prediction-Aware Dynamic Task Scheduling on a Hybrid CPU/GPU Laptop: Architecture, Implementation and Measured Results",
    ["Lakshay S", "Arkkadu Bharath Reddy"],
    ["Reg. Nos. 26MAI0064, 26MAI0058 \u2014 Course: Computer Architecture and Organization", "Guide: Dr. Yokesh Babu S, Associate Professor Grade 1. [Institution, department and e-mail to be filled by the authors]"],
    "This draft describes the implementation of the project and analyses its results. The framework (12,600 lines of Python in the runtime, 9,700 in scripts, 7,300 in tests) executes the tasks of a dependency graph on "
    "pinned performance-core and efficiency-core worker processes and one CUDA worker (RTX 3050), logs every dispatch with its decision time, verifies every output against a CPU reference and compares scheduling policies "
    "in interleaved, seeded blocks with paired bootstrap intervals. The final benchmark compares *static* plans (HEFT, PEFT, HEFT with end-to-end terms) with *dynamic* dispatch (blind B4, a parameter-aware rule, and a predicted-rank, "
    "idle-worker dispatcher with and without end-to-end cost terms), all built on one ridge cost model, on six workloads and three hardware sets; the primary metric is the end-to-end makespan from the start of the run to the last completion. "
    "On the primary workload (24 included blocks, ten Holm-adjusted contrasts) the dynamic dispatcher is 17.8% faster than B4 on the CPU and 21.2% faster with a strict GPU set, and 5.2% (CPU) and 12.2% (strict GPU) faster than the static HEFT plan. "
    "The GPU helps the dispatcher (2.6% strict set, 7.5% extended set) but not blind B4. A hand rule that knows the cost parameter is within 1% of the dispatcher in every configuration, the policies tie when task cost does not vary, "
    "end-to-end cost terms change nothing (equivalent within \u00b12%), and a hybrid selector is not justified (maximum headroom 1.1%). The GPU cost estimate has 23\u201331% median error. Earlier exploratory sessions "
    "(hidden-cost workloads, an emulated remote worker) are reported as a first study; a Raspberry Pi has not been measured.",
    "heterogeneous scheduling, DAG, runtime prediction, hybrid cores, CUDA, implementation, empirical evaluation, reproducibility",
)

d.h1("Introduction")
d.para("Reviews 1 and 2 surveyed the literature, patents and products and identified ten gaps, chiefly the lack of real-hardware evidence, overhead accounting, interval statistics, informed baselines and a like-for-like comparison "
       "of static plans with dynamic dispatch for DAG scheduling on heterogeneous resources. Review 3 reports the implementation built to close them and the results obtained with it. The contributions are: (1) a reproducible runtime and experiment framework "
       "for real task graphs on P/E cores, a CUDA GPU and an external worker; (2) a family of policies and estimators that includes the base idea B4, static HEFT and PEFT plans ({{heft,peft}}) and a predicted-rank dispatcher; "
       "(3) a final benchmark of static against dynamic scheduling with one cost model, end-to-end timing and per-task GPU eligibility taken from measurements; (4) a measured map of when prediction helps, including the cases where it does not; "
       "(5) a diagnosis of scheduling overhead; and (6) a prepared path for a Raspberry Pi worker, validated only by emulation.")

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
d.h2("Components added for the final benchmark")
d.figure(FF + r"\fig_final_architecture.png", "Final framework: one cost model and one GPU-eligibility table feed both the static planners and the dynamic dispatchers; the coordinator, event log and worker pools are shared.", 3.4)
d.bullets([
    "**End-to-end timing (amendment F1).** The end-to-end makespan runs from the start of `run()` to the last completion; initialisation and policy set-up are recorded separately, so the time a static plan needs to be computed is counted. The older makespan (first dispatch to last completion) is kept.",
    "**Static baselines.** HEFT_param_model, PEFT_param_model and HEFT_E2E give every task a fixed worker before the run; an oracle plan from class-median costs is a reference only. Planned and actual makespan are logged.",
    "**Dynamic policies.** B4_param_first sorts the ready queue by the cost parameter. PRED_RANK_GREEDY orders by predicted upward rank and binds only to an idle worker with the least predicted kernel time. PRED_RANK_GREEDY_E2E minimises predicted occupancy, i.e. transfer plus kernel plus set-up plus inter-process time.",
    "**No double counting.** The CUDA stage time already contains the host-to-device copy, the kernel and the device-to-host copy (checked in the stage code); the end-to-end variant adds only artifact I/O and inter-process overhead.",
    "**GPU eligibility.** `GpuRegion` makes a stage eligible for the CUDA worker only where a spike record shows a verified speed-up; a dropped row overrides a pass. Configurations: *cpu*, *gpu* (strict: the original record) and *ext* (strict plus denoise at verified iteration counts). No configuration is GPU-only.",
    "**Separate data.** The cost model and the end-to-end terms are fitted on calibration sessions and checked on hold-out sessions; evaluation sessions come afterwards with new chain orders; the protocol and design hashes were logged before the first evaluation session.",
])
d.h2("Dispatch pass of the coordinator")
d.para("Whenever a task becomes ready or a worker becomes idle the coordinator runs one *dispatch pass*. The pass is the same for all policies; only the two policy hooks differ:")
d.numbered([
    "take the ready tasks from the FIFO queue and call the policy’s *order_ready* hook (default: unchanged; hand rules sort by a parameter; the proposed policy sorts by predicted upward rank);",
    "for each task in the returned order, call *select_worker* (the policy returns a worker or nothing); a late-binding policy may only return an idle eligible worker;",
    "check eligibility and idleness (a violation raises a contract error), bind the task, log the dispatch with the elapsed decision time and the policy’s decision record;",
    "stop the pass when no worker is idle (late-binding policies) or all ready tasks were visited; on completion the coordinator logs the result, releases dependents and calls the policy’s feedback hook.",
])
d.para("The coordinator accumulates the time spent in steps 1 and 2 as its *scheduling time*; the time of each successful call is attached to its dispatch as the *decision time*. @sec:ovh shows why the two differ.")
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
       "against the stored tables by a test. A local web dashboard shows system state, a replay of runs and, on its last tab, any experiment session side by side (@fig:dash). Two later versions live in separate packages and leave the original unchanged: v2 shows the local GPU with live load, memory, temperature and power, and the final results with hover tooltips; v3 adds a tab that runs one live block of the final benchmark with any final policy on the CPU or CPU+GPU and shows the tasks per pool and the output check.")
d.nextlabel = "dash"
d.figure(FIG + r"\dashboard_compare.jpg", "Dashboard, tab \u201cMontage & GPU\u201d: one B4 run (3858.9 ms) and one run of the proposed dispatcher (3097.0 ms) of the same chain order, with placement, scheduling time and output-hash check.", 3.4)
d.h2("Code and test inventory")
d.table("Implementation inventory (measured by counting lines in the repository)",
        ["Part", "Files", "Python lines"],
        [["Runtime package (src/caosched)", "107", "12,578"],
         ["  core (coordinator, pools, DAG, tasks)", "", "2,026"],
         ["  estimators; schedulers; analysis; experiment", "", "1,197; 845; 1,037; 1,126"],
         ["  revival; study2 (earlier policies); final (static baselines, E2E dispatcher, GPU region)", "", "1,327; 680; 216"],
         ["  dashboard (original; v2; v3); remote; dataset", "", "774; 202; 266; 571; 692"],
         ["Scripts (experiments, analysis, profiling, runbooks)", "89", "9,709"],
         ["Tests", "52", "7,263 (521 tests passed)"],
         ["Version control", "71 commits", "branch revival/resource-state-aware; final-study files not committed"]],
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
d.table("Workloads of the final benchmark (image pipeline of 257 tasks, 512 px; evaluation runs per session, included runs in brackets)",
        ["Workload", "Heavy chains of 64 / iterations", "Runs"],
        [["h16_l120 (primary)", "16 heavy, 120 vs 2 iterations (ratio 60)", "600 (576)"],
         ["uniform", "none (no spread in task cost); cpu and gpu only", "208 (192)"],
         ["h04_l120", "4 heavy, 120 iterations", "312 (288)"],
         ["h40_l120", "40 heavy, 120 iterations", "312 (288)"],
         ["h16_l40", "16 heavy, 40 iterations (ratio 20)", "312 (288)"],
         ["h16_l15", "16 heavy, 15 iterations (ratio 7.5)", "312 (288)"]],
        [0.9, 1.9, 0.6], size=7)
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
d.para("Final benchmark: eight policies (four dynamic, four static of which the oracle plan is a reference) in three hardware sets, one run of every condition per block in seeded random order, the first block of a session a warm-up. "
       "Before every block the free memory had to exceed 2.4 GB at the start of a session and 0.8 GB per block, and the laptop had to be on mains power; these thresholds were never lowered, and attempts that failed the gate were kept on disk and never pooled. "
       "The confirmatory family is the ten contrasts C1\u2013C10 on the primary session under Holm correction with a \u00b12% equivalence margin; the other five sessions are exploratory and unadjusted.")
d.para("The effect of a condition against a reference is the paired geometric-mean change of makespan within interleaved blocks, with a percentile bootstrap interval stratified by workload instance (10,000 resamples) and a "
       "Holm-adjusted sign-flip *p*-value over the confirmatory family. Registered sessions were pre-registered with amendments. Overnight sessions are *exploratory*: plan and design hash were written before each run, each design was "
       "run once, and the plan fixed the reading of the result in advance. Chain orders are shuffles of the 64 chains seeded by an integer; orders used for model fitting (coverage) are disjoint from evaluation orders.")

d.h1("Results")
d.h2("Final benchmark: primary workload")
d.para("@tab:prim gives the end-to-end makespan (geometric mean over 24 included blocks) of every policy in the three hardware sets; @fig:mk adds the 95% intervals. In every set the three dynamic policies that use cost information "
       "(B4 param-first, PRED, PRED-E2E) are within about 1% of each other and clearly faster than blind B4; the static HEFT plan is 2% to 12% slower than PRED, and PEFT is the slowest static plan. All 576 included runs of the session had verified output.")
d.nextlabel = "prim"
d.table("Primary workload h16_l120: end-to-end makespan in seconds (geometric mean, 24 blocks)",
        ["Policy", "CPU only", "Strict GPU", "Extended GPU"], fd.primary_table_rows(), [1.5, 0.6, 0.6, 0.7], size=7)
d.nextlabel = "mk"
d.figure(FF + r"\fig_final_makespan.png", "End-to-end makespan of each policy in the three hardware sets on the primary workload (geometric mean, 95% interval, 24 blocks).", 3.4)
d.para("The ten confirmatory contrasts are in @tab:conf and @fig:forest. Predictions written before the data held for C1, C2, C7, C9 and C10. C3 and C4 had been predicted inconclusive or equivalent; the dynamic policy was about 5% faster, "
       "so that prediction was wrong. C5, C6 and C8 had no stated expectation.")
d.nextlabel = "conf"
d.table("Confirmatory contrasts (Holm family of ten; effect on end-to-end makespan, negative = first policy faster)",
        ["Id", "Contrast", "Effect % [95% CI]", "Holm p", "Result"], fd.confirmatory_rows(), [0.3, 1.4, 1.1, 0.4, 0.7], size=6.5)
d.nextlabel = "forest"
d.figure(FF + r"\fig_final_forest.png", "Confirmatory contrasts C1\u2013C10 with 95% intervals; the grey band is the \u00b12% equivalence margin.", 3.4)
d.h2("Final benchmark: six workloads")
d.para("The effect depends on how much task cost varies (@fig:wl, exploratory outside the primary session). Against static HEFT the dynamic policy gains 0.2% to 5.2% on the CPU and 3.7% to 17.1% with the strict GPU set; against blind B4 it gains almost 40% when only 4 of 64 chains are heavy, "
       "2.8% to 4.8% when 40 are heavy or the cost ratio is 20, and nothing on the uniform workload (+0.0% [\u22122.5, +2.3] on the CPU; \u22120.0% [\u22121.3, +1.1] with the strict GPU set). With the lowest cost ratio (7.5) the dynamic policy is slightly slower than B4 with the strict GPU set (+1.1% [+0.3, +1.9]).")
d.nextlabel = "wl"
d.figure(FF + r"\fig_final_workloads.png", "PRED against static HEFT (left) and blind B4 (right) on the six workloads, CPU only (blue) and with the strict GPU set (orange); exploratory except the first row.", 3.4)
d.h2("Final benchmark: GPU, cost-model error and end-to-end terms")
d.para("The GPU helps only where it is used with a cost model: for PRED the strict set is 2.6% [\u22123.3, \u22121.7] and the extended set 7.5% [\u22127.8, \u22127.2] faster than the CPU only, while blind B4 is 1.6% *slower* with the strict set (C10, inconclusive) and 2.8% slower with the extended set. "
       "Under the model-based policies the CUDA worker takes about 15% to 20% of the 257 tasks (@fig:place). One CUDA worker is a single narrow resource.")
d.nextlabel = "place"
d.figure(FF + r"\fig_final_placement.png", "Tasks run on the CPU and on the GPU per policy (extended set, primary workload) and the GPU busy fraction.", 3.4)
d.para("**Model error.** On hold-out sessions never used for fitting, CPU stages are predicted with a median error of 4% to 11%, GPU stages with 23% to 31% (@fig:err). The GPU estimate is the weakest part of the model: a static plan commits to it in advance, a dynamic policy uses it only when a worker is idle, "
       "so part of the dynamic-versus-static gap on the GPU sets may reflect model error and not only the timing of decisions; this was not separated experimentally. "
       "**End-to-end terms.** Adding set-up and inter-process terms changed nothing: PRED-E2E against PRED is +0.6% [+0.1, +1.3] on the CPU (C2) and \u22120.0% [\u22120.7, +0.5] with the strict GPU set (C7), both equivalent within \u00b12%; on the uniform workload with the strict set it was +2.9% [+0.4, +5.9] slower than B4. "
       "**Timing convention.** The difference between the end-to-end and the old makespan is 12.5 ms (B4), 29.2 ms (PRED), 40.7 ms (HEFT) and 81.3 ms (PEFT) on a makespan of about 3 to 4 s, so no conclusion flips between the two conventions.")
d.nextlabel = "err"
d.figure(FF + r"\fig_final_model_error.png", "Median absolute error of the cost model on hold-out tasks, by stage and pool.", 3.4)
d.h2("Final benchmark: what limits the claim")
d.bullets([
    "**A simple rule gets almost all of the gain.** PRED against B4 param-first (the queue sorted by the cost parameter) is \u22120.4% [\u22120.9, +0.1] on the CPU, \u22120.6% [\u22121.1, \u22120.0] with the extended set and \u22120.2% [\u22120.9, +0.7] with the strict set (exploratory): under 1% in every set.",
    "**A hybrid selector is not justified.** In 17 development cells the maximum headroom of a B4-or-PRED selector was 1.1%, the mean 0.08%, and no cell exceeded the 2% margin, so none was built.",
    "**Two sessions disagree.** The earlier overnight session found HEFT level with the dispatcher (+1.10% [\u22120.53, +2.81], old timing convention, other chain orders); the final session finds PRED about 5% faster. The timing convention does not explain it; the difference was not isolated and both results are reported.",
    "**Scope.** One machine, one workload family, 512 px, one CUDA worker; only the primary session is confirmatory; the remote worker was not rerun with the final policies.",
])
d.h2("Earlier study: Montage, a valid null result")
d.para("On the 59-task mosaic with 6 P and 7 E workers (9 blocks, registered), predictive EFT variants and HEFT were 1.4% to 1.7% *slower* than static use of the P cores (intervals above 0), learned models 9% to 14% slower, "
       "and B4 47.9% slower (95% interval +37.5 to +54.6). The profile explains it: every Montage task prefers P cores by a factor of 2.3 to 3.6 and nine equal tasks dominate, so no placement can beat \u201cuse the P cores\u201d and "
       "any use of E cores costs time.")
d.h2("Earlier study: hidden-cost workload")
d.para("Registered sessions with two chain orders each gave the proposed dispatcher \u221220.39% [\u221221.2, \u221219.3] (30 blocks, 6P+7E) and \u221221.10% [\u221221.5, \u221220.7] (20 blocks, 2P+7E, model refitted by one command) relative to B4. "
       "To test generalisation, exploratory sessions used chain orders never used before (@tab:unseen, @fig:perorder). The dispatcher was faster than B4 in all 12 and all 8 orders; the informed hand rule, which sorts chains by the "
       "heavy parameter without any model, gave the same gain, and the difference between dispatcher and rule had intervals inside \u00b12%.")
d.nextlabel = "unseen"
d.table("Unseen chain orders (exploratory); effects relative to B4 unless noted (negative = shorter)",
        ["Session", "Blocks / orders", "Dispatcher", "Hand rule", "P-only", "Dispatcher vs rule"],
        [["6P+7E, H=16", "36 / 12", "\u221219.32% [\u221220.0, \u221218.6]", "\u221219.85%", "+3.68%", "+0.66% [\u22120.2, +1.5]"],
         ["2P+7E, H=16", "24 / 8", "\u221220.45% [\u221221.2, \u221219.8]", "\u221220.67%", "+45.77%", "+0.27% [\u22120.2, +0.8]"],
         ["6P+7E, H=4", "12 / 4", "\u221227.65% [\u221234.0, \u221218.7]", "\u221226.94%", "\u221211.56%", "\u22120.98% [\u22123.1, +1.2]"],
         ["6P+7E, H=8", "12 / 4", "\u221226.76% [\u221227.9, \u221225.7]", "\u221226.93%", "\u221215.77%", "+0.24% [\u22120.4, +1.0]"],
         ["6P+7E, H=40", "12 / 4", "\u22123.81% [\u22125.1, \u22121.9]", "\u22125.15%", "+23.13%", "+1.42% [\u22120.7, +4.5]"]],
        [0.62, 0.45, 0.95, 0.5, 0.55, 0.85], span=True, size=6.5)
d.nextlabel = "perorder"
d.figure(FIG + r"\fig_per_order.png", "Per-order change in makespan of the dispatcher against B4 (blue) and the hand rule (green).", 3.4)
d.nextlabel = "dose"
d.figure(FIG + r"\fig_dose_heavy.png", "Gain over B4 versus heavy:light cost ratio (left) and number of heavy chains (right).", 3.4)
d.para("**Dose-response.** Holding 16 heavy chains and raising their cost ratio from about 3 to 60 gave \u22122.6%, +0.6% (not significant), \u22126.1% and \u221219.9% in a first pass of four orders; a follow-up with eight further orders gave "
       "\u22121.3% (ratio 7.5) and \u22122.9% (ratio 20). The first-pass irregularity was order-specific: the gain is small, about 1% to 3%, up to a ratio of 20 and large only near 60. **Heavy-chain count.** With the ratio fixed "
       "the gain is largest when few chains are heavy and falls as they become the majority (@fig:dose), consistent with a tail effect in which blind dispatch starts a heavy chain late or on a slow core.")
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
d.nextlabel = "ovh"
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
       "0.0943 s over 44 placements) yet was 3.78% [+2.27, +5.58] *slower* than without it (@fig:remote). Prediction accuracy did not become scheduling value in this regime. A loopback rehearsal of the complete Raspberry Pi command chain "
       "(profile, calibration with an external node, design generation, 25 runs, analysis) passed after a defect in the node (it served only one client) was fixed.")
d.nextlabel = "remote"
d.figure(FIG + r"\fig_remote.png", "Emulated remote worker: effect on EFT makespan at compute level 1 (registered) and level 30 (overnight); error bars are 95% intervals.", 3.4)
d.h2("Summary of claims")
d.table("Claim status after the project (50 registered claims of the earlier study plus the final benchmark; selection)",
        ["Status", "Claim"],
        [["Supported", "dynamic PRED beats blind B4 by 17.8% (CPU) and 21.2% (strict GPU); beats a static HEFT plan from the same model by 5.2% and 12.2%; the GPU helps PRED (2.6% strict, 7.5% extended); end-to-end terms are equivalent; earlier study: rank-ordered dispatch beats B4 by 19\u201328% on cost-skewed workloads"],
         ["Not established", "advantage over an informed rule (within 1%); a hybrid selector; GPU benefit for blind B4; remote offloading benefit; Raspberry Pi results; any claim beyond this machine and workload family"],
         ["Not supported / null", "gain on Montage; gain on the two-factor workload; gain on the uniform workload; remote worker helping EFT at level 30"]],
        [0.8, 2.6], size=7)

d.h2("Sessions executed and integrity checks")
d.table("Timed sessions (all included outputs verified; hashes of event logs checked)",
        ["Group", "Sessions", "Blocks", "Runs", "Label"],
        [["Unseen orders 6P+7E / 2P+7E", "2", "37 / 25", "148 / 100", "real"],
         ["Dose-response (ratio 3, 7.5, 20, 60) and follow-up (7.5, 20)", "6", "52 + 50", "208 + 200", "real"],
         ["HEFT/PEFT/rank-EFT vs dispatcher", "1", "25", "150", "real"],
         ["Heavy-chain count 4, 8, 40", "3", "39", "156", "real"],
         ["Dispatch-loop A/B", "1", "13", "78", "real"],
         ["Reproduction of the registered design", "1", "11", "55", "real"],
         ["Final study: calibration (cal_l15, cal_l40, cal_l120, cal_uniform) and hold-out (hold_l40, hold_l120), completed retries", "6", "\u2013", "99 + 28", "real"],
         ["Final study: evaluation, six workloads", "6", "25, 13 \u00d7 5", "600, 208, 312 \u00d7 4", "real"],
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
         ["Analysis tool labels the primary family “confirmatory” by default", "review", "documented; overnight sessions stay exploratory by plan"],
         ["Final-study stage 1 aborted when the laptop was unplugged, on retry-id collisions and on low free memory (antivirus, Docker, WSL)", "run logs", "mains wait and first-unused-id logic added; the 2.4 GB and 0.8 GB thresholds were never lowered; aborted attempts kept (_r2 \u2026 _r8), never pooled"],
         ["Static plans were timed from the first dispatch, hiding their planning time", "design review", "end-to-end makespan (amendment F1); old metric kept"]],
        [1.6, 0.8, 1.0], size=7)
d.h2("Raspberry Pi path (prepared, not measured)")
d.para("The stage needs no further code change. On the Pi: a Python 3.11 environment with numpy, Pillow and psutil, the package installed without its heavy dependencies, and the node started with a token and the persistent option. "
       "On the laptop: a base profile at the experiment’s compute level, link calibration against the Pi (kernel times, payload sizes, transfer time as a + b·bytes), a generated design with five conditions (static, B4 and EFT without remote; "
       "B4 and EFT with remote), 13 blocks per compute level, and the standard analysis with a decision rule fixed beforehand (the remote worker helps only if the interval of EFT with versus without it lies below zero). "
       "A runbook lists every command, the measurements to record on arrival (temperature, throttling flag, network throughput), and the rollback to the local demonstration.")

d.h1("Analysis and Discussion")
d.para("**Mechanism.** The dominant effect is ordering and informed placement: serving predicted-heavy work first removes the tail created by blind dispatch, and sending only verified stages to the GPU adds a smaller gain. "
       "That is why a rule that knows the cost parameter is within 1% of the dispatcher and why the effect depends on the spread of task cost. A dynamic policy also beats a static plan from the same model, "
       "by 5% on the CPU and 12% with a strict GPU set: the static plan cannot react to the actual completion order, and its GPU assignments inherit the 23\u201331% model error in advance. "
       "**Prediction accuracy is not enough:** remote predictions were accurate to under 1% yet gave no gain, in line with the finding of {{ilyushkin}} that order can matter more than estimate accuracy. "
       "**Overhead matters but did not decide the result.** Scheduling time is 2% to 5% of these 3 to 9 second runs for late-binding policies; in the final benchmark policy set-up is 19 ms (PRED), 30 ms (HEFT) and 71 ms (PEFT).")
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
         ["Worker choice", "first idle eligible worker (P before E)", "idle eligible worker with least predicted time (CPU or verified GPU stages)"],
         ["Cost knowledge", "none", "model learned from logs; retrained by one command"],
         ["Decision cost per run", "7 ms (coordinator 0.20 s)", "15 ms (coordinator 0.10 s); policy set-up 19 ms"],
         ["Makespan, primary workload", "reference", "\u221217.8% (CPU), \u221221.2% (strict GPU) vs B4; \u22125.2% and \u221212.2% vs static HEFT"],
         ["Makespan, nothing hidden", "reference", "+0.0% (equivalent within \u00b12%)"],
         ["Evidence", "\u2014", "real runs, end-to-end timing, paired intervals, ten Holm-adjusted contrasts, 521 tests"]],
        [0.9, 1.25, 1.3], size=7)
d.h1("Conclusion and Future Work")
d.para("The implementation delivers a reproducible framework and a measured account of static against dynamic scheduling on a hybrid CPU+GPU laptop: dynamic dispatch with a cheap cost model is 2% to 12% faster than a static plan "
       "from the same model and about 18% to 21% faster than blind dispatch when task cost varies; it ties blind dispatch when it does not; a rule that knows the cost parameter gets almost the same result; and the GPU helps only with a cost model. "
       "Next: (1) a second workload family; (2) a GPU cost model with lower error and a test that separates model error from decision timing; (3) the remote worker with the final policies, then a Raspberry Pi over a real link with the prepared runbook; "
       "(4) apply and test the dispatch-loop fix in the source and commit the final study; and (5) obtain a professional prior-art search before any IPR filing.")
d.references()
OUTD = OUT + r"\03_Review3_Implementation_Results_IEEE"
d.save(OUTD + ".docx")
pages, words = export_pdf(OUTD + ".docx", OUTD + ".pdf")
print("pages", pages, "words", words, "refs", len(d.cite_order))
