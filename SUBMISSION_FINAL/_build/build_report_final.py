"""Consolidated final project report (DA1+DA2+DA3 upload; at most 30 pages: Times New Roman 12 pt, 1.5 line spacing, 1 inch margins)."""
import sys
sys.path.insert(0, r"D:\cao project\SUBMISSION_FINAL\_build")
from report_docx2 import Report
from ieee_docx2 import export_pdf
import final_data as fd

FIG = r"D:\cao project\publications\figures"
FF = r"D:\cao project\SUBMISSION_FINAL\_fig"
OUT = r"D:\cao project\SUBMISSION_FINAL\_draft"
MINUS = "\u2212"


import json, re
def holdout_rows():
    rows = []
    for ln in open(fd.ROOT / "data" / "results" / "final_20261101" / "models" / "train.stdout.txt", encoding="utf-8"):
        m = re.match(r"holdout (\S+) (\{.*\})", ln.strip())
        if m:
            d = json.loads(m.group(2).replace("'", '"'))
            rows.append([m.group(1).replace("img_", "").replace("|", " on "), str(d["n"]), f"{d['mae_s'] * 1000:.2f}", f"{d['median_ape'] * 100:.1f}"])
    return sorted(rows)

r = Report()

# ------------------------------------------------------------------ front matter
r.center("", 12, after=36)
r.center("FINAL PROJECT REPORT", 14, bold=True, after=12)
r.center("Static versus Dynamic Task Scheduling on a Hybrid CPU/GPU Machine", 22, bold=True, after=10)
r.center("An AI-assisted heterogeneous computing framework: survey, base-work redo, gaps, implementation and measured evaluation", 13, italic=True, after=30)
r.center("Course: Computer Architecture and Organization", 12, after=4)
r.center("Submitted by", 11, italic=True, before=14, after=4)
r.center("Lakshay S (Reg. No. 26MAI0064)", 12, after=2)
r.center("Arkkadu Bharath Reddy (Reg. No. 26MAI0058)", 12, after=18)
r.center("Guide: Dr. Yokesh Babu S, Associate Professor Grade 1", 11, after=2)
r.center("Institution / Department: [to be filled by the authors]", 11, after=2)
r.center("Contact e-mail: [to be filled by the authors]", 11, after=18)
r.center("Date of this version: 3 November 2026", 11, after=2)
r.center("This one document is the consolidated upload for DA1 (survey), DA2 (base-work redo and gaps) and DA3 (proposed work).", 10, italic=True)
r.page_break()
r.center("Declaration", 14, bold=True, after=8)
r.para("We declare that this report describes the work carried out for the project named on the title page, that all measured numbers in it are read from result files stored in the project repository, "
       "that nothing in it is simulated unless labelled *simulation* or *emulation*, and that statements about literature, patents and products are limited to what the cited documents state. "
       "Items that were not measured are listed as *not established* and are not presented as results. Signatures of the authors and the guide are to be added before submission.")
r.table("Evidence labels used throughout",
        ["Label", "Meaning"],
        [["real", "executed on the project laptop (Intel Core i5-13500HX, RTX 3050 6 GB, Windows 11); outputs verified against a CPU reference"],
         ["emulation", "remote worker replaced by a local process behind a loopback socket and a delay shim; never presented as a real network or device"],
         ["plan", "written down but not run (the Raspberry Pi validation)"],
         ["confirmatory / exploratory", "confirmatory: the ten contrasts of the primary final session, fixed in the protocol and Holm-adjusted; exploratory: everything else, unadjusted"]],
        [1.5, 5.0])
r.center("Contents", 14, bold=True, before=6, after=4)
r.toc()
r.page_break()

# ------------------------------------------------------------------ 1
r.chapter("Introduction and Scope")
r.para("*Heterogeneous computing* combines processing elements of different speed in one system: performance (P) and efficiency (E) cores, a GPU, a single-board computer such as a Raspberry Pi 5 {{rpi5}}, or a remote node. "
       "Applications are *workflows*: directed acyclic graphs (DAGs) of tasks joined by data dependencies, such as the Montage mosaic {{montage,wfcommons}} or image pipelines. "
       "A *scheduler* decides the order in which ready tasks are served and the worker each one uses; *offloading* is the case in which the worker is on another device.")
r.para("The project asks a practical question: **does a dynamic scheduler, which decides while the workflow runs, finish sooner than a static plan computed beforehand from the same cost model, on a hybrid CPU+GPU machine, once planning and start-up time are counted, and under which conditions?** "
       "Static schedulers such as HEFT and PEFT {{heft,peft}} fix every assignment in advance; dynamic ones, such as StarPU {{starpu}} and learned schedulers {{lachesis,adprl,tan25}}, decide at run time.")
r.para("The deliverables of the course are covered in this report: domain and problem statistics (Chapter 2), surveys of publications, patents and products and technology trends (Chapter 3), redo of the base work and gap identification (Chapter 4), "
       "the proposed work with its architecture and methodology (Chapters 5 and 6), results (Chapter 7), the difference between the existing and the proposed implementation (Chapter 8), the demonstration guide and reproducibility (Chapter 9) "
       "and the publication and IPR route (Chapter 10). Scope: one laptop with six P cores, seven E cores and one CUDA worker (RTX 3050); the remote worker was emulated; **no Raspberry Pi or real-network result exists**.")
r.section("Contributions")
r.bullets([
    "A reproducible runtime and experiment framework that executes real task graphs on pinned P/E workers and a CUDA worker, verifies every output and logs every decision.",
    "A final benchmark of static plans (HEFT, PEFT, HEFT with end-to-end terms) against dynamic dispatch (blind B4, a parameter-aware rule, a predicted-rank dispatcher) with *one* cost model, end-to-end timing and per-task GPU eligibility taken from measurements.",
    "A pre-stated confirmatory family of ten contrasts, six workloads, and an honest account of limits: a simple rule gets almost all of the gain, there is no gain without cost spread, the GPU model has 23% to 31% error.",
])

# ------------------------------------------------------------------ 2
r.chapter("Domain and Problem Substantiation")
r.para("Four trends make scheduling on heterogeneous resources important; each figure was checked against its source, and two are secondary reports.")
r.table("Verified statistics that motivate the problem",
        ["Indicator", "Value", "Source"],
        [["Data-centre electricity", "about 415 TWh in 2024 (about 1.5% of global use); about 945 TWh projected for 2030", "{{iea}}"],
         ["Accelerated HPC systems", "232 of 500 TOP500 systems (46.4%) use accelerators, June 2025", "{{top500}}"],
         ["Connected IoT devices", "18.5 billion at end-2024 (+12%); about 39 billion forecast for 2030", "{{iotanalytics}}"],
         ["Under-used clusters", "Alibaba cluster: more than 80% of the time at 10% to 30% CPU use", "{{cheng18}}"],
         ["Hybrid client CPUs", "Intel Thread Director on 12th to 14th generation Core processors", "{{intel_td}}"]],
        [1.5, 3.9, 1.1])
r.para("The amount of heterogeneous capacity is large and growing, and it is often wasted, so placement quality turns into energy, cost and latency. On the project machine a 512-pixel denoise task with 30 iterations takes 156 ms on a P core and 560 ms on an E core (3.6 times longer), "
       "and the GPU is up to 15 times faster for edge detection at 1024 pixels but only breaks even at small tiles because host-device copies dominate. A scheduler that ignores these ratios sends heavy work to slow cores.")

# ------------------------------------------------------------------ 3
r.chapter("Survey: Publications, Patents, Products and Trends")
r.section("Publications")
r.para("We analysed 12 supplied papers in full and one at abstract level. The 13 solutions fall into four families: learned task selection with a heuristic placement rule {{lachesis,song23,tan25}}; end-to-end deep reinforcement learning for offloading "
       "{{dddqn,wang22,gong23,sata,cao24,nieto,adprl,metarl,iov}}; lightweight runtime scheduling {{rodriguez}}; and prediction-driven list scheduling {{lotaru,starpu,heft,peft}}.")
r.table("Comparison of the main published solutions",
        ["Ref.", "Method", "Platform", "Reported result", "Limitation for our goal"],
        [["{{lachesis}}", "GNN + RL selects the task, DEFT places it", "simulated cluster", "up to 26.7% shorter makespan", "simulation; no variance test"],
         ["{{rodriguez}}", "lightweight asynchronous scheduling", "real Zynq CPU+FPGA", "up to 2x; overhead measured", "FPGA specific; no DAG, no prediction"],
         ["{{adprl}}", "dependency-aware RL, bandwidth", "simulation + 3 Jetson boards", "lower time and energy", "network focus; DRL cost"],
         ["{{tan25}}", "GCN-Transformer + PPO", "simulated multicore", "11.09% lower time and power", "simulation; heavy model"],
         ["{{metarl}}", "meta-RL + seq2seq", "simulated edge", "21% less delay, 19% less energy", "simulation"],
         ["{{lotaru}}", "runtime prediction drives HEFT", "simulation", "close to perfect-knowledge HEFT", "no real execution"]],
        [0.5, 1.9, 1.3, 1.5, 1.3], size=8.5)
r.para("Three findings structure the work. Only two of 13 papers use physical hardware; no paper reports a confidence interval; and none compares against an *informed* simple rule or gives a static and a dynamic scheduler the same cost model and times both end to end. "
       "These are the gaps G1 to G10 of Chapter 4. The 13 papers are the supplied base set, not a systematic review, so we write \u201cnot found in the sources inspected\u201d.")
r.section("Patents (IPR)")
r.para("The base patent is US 11,561,826 B1 (Xilinx; granted 24 Jan. 2023) {{p_xilinx}}. Its independent claims recite kernel objects tied to compute circuits, a task graph, per-kernel task queues and thread-based enqueue and dequeue; dependent claims add in-degree counters (claims 9 and 10) and performance-based thread adjustment (claim 8). "
       "No claim recites prediction of execution time, a transfer-cost model or offloading to a remote device.")
r.table("Comparative analysis of patents (legal status is a Google Patents assumption, not an opinion)",
        ["Patent", "Discloses", "Prediction", "Relation to this work"],
        [["{{p_xilinx}} Xilinx, US 11,561,826 B1", "task graph, per-kernel queues, in-degree gating", "no", "base work; mapped to blind dispatch B4"],
         ["{{p_ibm1}} IBM, US 11,740,933 B2", "learning agent ranks DAG tasks; rank-ordered dispatch", "learned rank", "closest; ranking is not new"],
         ["{{p_ibm2}} IBM, US 11,966,776 B2", "learned DAG policy with execution estimates", "yes", "deadline oriented"],
         ["{{p_intel}} Intel, US 10,186,007 B2", "CPU+GPU online profiling and work split", "online", "no DAG, no learned model"],
         ["{{p_samsung}} Samsung, US 10,162,671 B2", "duration prediction on heterogeneous cores (lapsed)", "yes", "contention-aware"]],
        [1.7, 2.3, 0.8, 1.7], size=8.5)
r.para("Task graphs, queues and gating are claimed by the base patent; rank-ordered dispatch with a learning agent is disclosed by IBM. The project therefore treats B4 as a comparison baseline and positions its contribution as a measured study, not as a new patentable algorithm; "
       "a professional prior-art search is required before any filing.")
r.section("Company products")
r.table("Products that decide where work runs (only what the cited pages state)",
        ["Product", "Scope", "Heterogeneity handled", "Prediction / learning"],
        [["Intel Thread Director {{intel_td}}", "client CPU", "P versus E cores, hardware feedback", "hardware classification"],
         ["Windows QoS {{ms_qos}}; Linux EAS {{linux_eas}}", "OS scheduler", "QoS levels; asymmetric capacity and energy model", "heuristics / energy model"],
         ["Kubernetes {{k8s}}, AWS Batch {{aws_batch}}, Slurm {{slurm}}, Ray {{ray}}", "cluster, batch", "declared CPU/GPU resources", "none stated"],
         ["StarPU {{starpu}}", "task runtime", "CPU/GPU tasks, data transfers", "performance models"]],
        [2.2, 1.0, 2.0, 1.3], size=8.5)
r.para("Operating-system features place threads, cluster products place containers or jobs against declared requests, and only workflow runtimes such as StarPU understand task graphs. No page we read combines DAG knowledge, learned per-resource estimates and published decision-overhead measurements on a laptop-class CPU/GPU system.")
r.section("Technology trends: introduction and adoption status")
r.table("Trends, their state and relevance",
        ["Trend", "State (as documented)", "Relevance"],
        [["Hybrid P/E cores", "mainstream in client CPUs {{intel_td}}", "core type changes task time by 2.8 to 3.6 times here"],
         ["On-device GPU / NPU", "NPU of 40 TOPS or more required for Copilot+ PCs {{copilot}}", "the CUDA GPU is used as a worker"],
         ["Learned DAG scheduling", "research; simulation in most papers", "tested here with a much cheaper model"],
         ["LLM-agent schedulers", "2025 to 2026 preprints {{lureda,agentxpu}}", "noted as a direction, not evaluated"],
         ["Runtime performance models", "established in StarPU {{starpu}}", "same idea with overhead accounting"],
         ["Edge boards as remote workers", "Raspberry Pi 5 {{rpi5}}", "emulated only; no real-link result"]],
        [1.6, 2.7, 2.2], size=8.5)

# ------------------------------------------------------------------ 4
r.chapter("Redoing the Base Work and Identifying Gaps")
r.para("A laptop cannot reproduce the FPGA system of the base patent, so what can be redone is its *scheduling idea*: a worker takes a task only if the task is eligible for it, ready when all parents completed, with no estimate of execution time. "
       "We map it to policy B4 (first idle eligible worker, priority P then E) and reimplement HEFT and PEFT {{heft,peft}}; the repository tests reproduce the published worked examples.")
r.table("Redo of the base idea on real executions (paired makespan change, negative = shorter; earlier study)",
        ["Workload", "Comparison", "Result", "Reading"],
        [["Montage, 59 tasks (9 blocks)", "B4 vs static P-only", "+47.87% [+37.5, +54.6]", "greedy use of slow E cores hurts"],
         ["Uniform batch + GPU (30)", "static P-only vs B4", "+35.9%", "B4 keeps all workers busy"],
         ["Hidden cost, 16 heavy (36)", "hand rule vs B4", MINUS + "19.85%", "B4 is blind to cost"],
         ["Hidden cost, 4 heavy (12)", "hand rule vs B4", MINUS + "26.94%", "B4 worse than P-only"]],
        [1.7, 1.5, 1.7, 1.6], size=8.5)
r.para("B4 is a good way to keep workers busy and a poor one when task cost differs and is invisible to the scheduler: in 93.6% of 20,046 stored B4 dispatches only one eligible worker was idle, so order, which B4 leaves to first-come first-served, is where the gain lies. "
       "Instrumenting B4 also exposed a defect: an idle CUDA worker that no task can use defeats the early exit of the dispatch loop, so 10,042 of 10,299 selection calls returned nothing; a decision-preserving fix moved the dispatcher\u2019s gain by 0.8 points only.")
r.table("Gaps identified and the project response",
        ["Gap", "Evidence", "Response"],
        [["G1 real hardware", "2 of 13 papers use devices", "P/E pools, CUDA worker, real workloads"],
         ["G2 scheduler overhead", "decision time in 4 of 13 papers", "per-dispatch and end-to-end timing logged"],
         ["G3 statistics", "no confidence intervals", "paired bootstrap, Holm, frozen protocol"],
         ["G4 informed baselines", "no informed rule in any paper", "hand rule, HEFT, PEFT, HEFT-E2E"],
         ["G5 cost-blind base idea", "B4 5% to 37% slower than a rule", "predicted-rank dispatcher"],
         ["G6 accuracy is not value", "accurate remote predictions, no gain", "reported separately"],
         ["G7 generalisation", "one instance per setting", "six workloads, 20 unseen orders earlier"],
         ["G8 remote reality", "simulated networks", "emulation labelled; Pi not measured"],
         ["G9 / G10 static vs dynamic", "HEFT baseline only in simulation", "final benchmark, one model, end-to-end timing, CPU and GPU"]],
        [1.7, 2.4, 2.4], size=8.5)

# ------------------------------------------------------------------ 5
r.chapter("System Design and Implementation")
r.para("The coordinator converts a workflow into a DAG, keeps the ready queue with dependency counters, and dispatches each task to a worker process pinned to one logical processor (six P workers, seven E workers, one CUDA worker G); a reserved core runs the coordinator. "
       "Every policy honours per-task eligible pools through one helper, every output is compared with a CPU reference, and an event log records each dispatch with its decision time. "
       "One cost model and one GPU-eligibility table feed both the static planners and the dynamic dispatchers (Figure 1).")
r.figure(FF + r"\fig_final_architecture.png", "Framework of the final study: shared cost model and GPU eligibility; static and dynamic policy families; shared coordinator, event log and worker pools.", 4.3)
r.table("Policies compared (all share eligibility rules and, where they predict, the same ridge cost model)",
        ["Policy", "Kind", "Rule"],
        [["B4", "dynamic", "first idle eligible worker per ready task in FIFO order; no estimate"],
         ["B4_param_first", "dynamic", "B4 with the queue sorted by the cost-relevant task parameter (a hand rule)"],
         ["PRED_RANK_GREEDY", "dynamic", "order by predicted upward rank; bind only to an idle worker with the least predicted kernel time"],
         ["PRED_RANK_GREEDY_E2E", "dynamic", "as PRED, minimising predicted occupancy: transfer + kernel + set-up + inter-process time"],
         ["HEFT / PEFT / HEFT_E2E", "static", "plan before the run from the same model (HEFT_E2E adds the end-to-end terms); fixed worker per task"],
         ["HEFT_oracle", "static, reference", "plan from class-median costs of the calibration sessions; not a bound"]],
        [1.7, 1.0, 3.8], size=8.5)
r.para("**Cost model.** A ridge regression per (stage, pool) on the numeric task parameters and size that vary in the logs and on their pairwise products; it names no stage or parameter, refuses an unseen stage or pool, and is refitted by one command. "
       "More elaborate predictors (constant, table, analytic, moving history, ridge with context, CatBoost, a small MLP, an oracle replay) were tried in earlier phases and did not improve scheduling enough to justify their cost. "
       "On hold-out tasks the median error is 4% to 11% for CPU stages and 23% to 31% for GPU stages.")
r.para("**Dispatch pass.** Whenever a task becomes ready or a worker becomes idle the coordinator runs one pass, identical for all policies except for two hooks:")
r.numbered([
    "take the ready tasks and let the policy reorder them (the proposed policy sorts by predicted upward rank, rank(t) = predicted time(t) + the largest rank among the successors of t);",
    "for each task in that order ask the policy for a worker; a late-binding policy may name only an idle eligible worker, otherwise the task stays queued;",
    "check eligibility and idleness (a violation raises a contract error), bind the task and log the dispatch with its decision time;",
    "stop when no worker is idle or all ready tasks were visited; on completion log the result and release the dependents.",
])
r.table("Event log and run manifest content",
        ["Record", "Fields (selection)"],
        [["task_ready, task_dispatched", "task id, worker, pool, queue wait, worker load, decision time"],
         ["task_submitted, task_completed", "kernel time, start and end timestamps, transfer time, output size and SHA-256"],
         ["worker_ready, run_started, run_finished", "pid, requested and actual affinity; makespan, status, tasks per pool"],
         ["run manifest", "condition, policy, seed, warm-up flag, output verdict, event-log hash, git commit and dirty flag, source and design hashes"]],
        [2.2, 4.3], size=8.5)
r.table("Cost-model error on hold-out tasks (E = efficiency core, P = performance core, G = CUDA worker)",
        ["Stage on pool", "n", "MAE (ms)", "Median abs. error (%)"], holdout_rows(), [2.0, 1.0, 1.2, 2.0], size=8.5)
r.figure(FF + r"\fig_final_model_error.png", "Median absolute error of the cost model on hold-out tasks, by stage and pool.", 4.0)
r.para("**GPU eligibility.** A stage may run on the CUDA worker only where a recorded spike measurement shows a verified speed-up at that size and iteration count (for example edges 7.68x, features 2.88x, denoise 1.20x to 1.77x at 15 to 120 iterations; denoise at 1 or 2 iterations is dropped). "
       "The configurations are *cpu* (P+E only), *gpu* (strict: original record) and *ext* (strict plus denoise at the extended record\u2019s iteration counts); none is GPU-only. "
       "**Timing.** The end-to-end makespan runs from the start of `run()` to the last completion; initialisation and policy set-up are logged separately, so a static plan\u2019s planning time is counted.")
r.para("**Code and tests.** The runtime package has 107 files and 12,578 lines of Python, the scripts 9,709 lines and the tests 7,263 lines; 520 of 521 tests pass (the one failure is a test of the Montage profiler that refuses to start when free RAM is below its own 2 GB gate and is environmental). "
       "A local dashboard shows system state, run replays and the stored final results; two later versions, in separate packages, show the GPU with live load and run one live block of the final benchmark with any final policy.")

# ------------------------------------------------------------------ 6
r.chapter("Methodology")
r.para("**Machine and workloads.** Intel Core i5-13500HX (6 P, 8 E cores), RTX 3050 6 GB, 15.7 GB RAM, native Windows 11. The image pipeline (source, denoise, edges, features, aggregate; 512 px, 64 chains, 257 tasks) has *H* heavy chains (denoise 120 iterations) among light ones (2 iterations). "
       "The primary workload h16_l120 has 16 heavy chains (24 included blocks, 576 included runs); five exploratory workloads use 4 or 40 heavy chains, cost ratios 20 and 7.5, and a uniform workload (13 blocks each).")
r.table("Evaluation workloads (runs per session; included runs in brackets; the first block of each session is a warm-up)",
        ["Workload", "Heavy chains / iterations", "Blocks", "Runs"],
        [["h16_l120 (primary)", "16 heavy, 120 vs 2 iterations (ratio 60)", "25", "600 (576)"], ["uniform", "none; cpu and gpu only", "13", "208 (192)"],
         ["h04_l120", "4 heavy, 120 vs 2", "13", "312 (288)"], ["h40_l120", "40 heavy, 120 vs 2", "13", "312 (288)"],
         ["h16_l40", "16 heavy, 40 vs 2 (ratio 20)", "13", "312 (288)"], ["h16_l15", "16 heavy, 15 vs 2 (ratio 7.5)", "13", "312 (288)"]],
        [1.6, 3.2, 0.8, 0.9], size=8.5)
r.para("**Data separation and protocol.** Calibration sessions fitted the model and the end-to-end terms, hold-out sessions checked them, and the evaluation sessions came afterwards with new chain orders; the protocol and design hashes were logged before the first evaluation session. "
       "Conditions run once per block in seeded random order; free memory must exceed 2.4 GB at the start and 0.8 GB per block and the laptop must be on mains power (thresholds were never lowered; aborted attempts are kept and never pooled).")
r.para("**Statistics.** The effect of a condition against a reference is (exp(mean ln(M_c/M_r)) \u2212 1) \u00d7 100% over paired blocks, with a percentile bootstrap interval (10,000 resamples) stratified by chain order, sign-flip *p*-values, Holm correction over the ten contrasts C1 to C10 of the primary session and a \u00b12% equivalence margin. "
       "Expected outcomes were written before the data; they held for C1, C2, C7, C9 and C10 and were wrong for C3 and C4.")

# ------------------------------------------------------------------ 7
r.chapter("Results")
r.section("Primary workload and confirmatory contrasts")
r.para("The first table below gives the end-to-end makespan (geometric mean, 24 blocks). In every hardware set the cost-aware dynamic policies are within about 1% of each other and clearly faster than blind B4; the static HEFT plan is slower than PRED and PEFT is the slowest static plan. All included runs had verified output.")
r.table("Primary workload h16_l120: end-to-end makespan in seconds",
        ["Policy", "CPU only", "Strict GPU", "Extended GPU"], fd.primary_table_rows(), [2.6, 1.3, 1.3, 1.3], size=9)
r.table("Confirmatory contrasts (Holm family of ten; negative = first policy faster)",
        ["Id", "Contrast", "Effect % [95% CI]", "Holm p", "Result"], fd.confirmatory_rows(), [0.5, 2.3, 1.7, 0.7, 1.3], size=8.5)
r.figure(FF + r"\fig_final_forest.png", "Confirmatory contrasts C1 to C10 with 95% intervals; the grey band is the \u00b12% margin.", 4.2)
r.para("The dynamic dispatcher beats blind B4 by 17.8% on the CPU (C1) and 21.2% with the strict GPU set (C8), and beats the static HEFT plan from the same model by 5.2% on the CPU (C3) and 12.2% with the strict GPU set (C5). "
       "End-to-end cost terms change nothing (C2, C7: equivalent within \u00b12%). The GPU helps the dispatcher by 2.6% (C9) but not blind B4 (C10: +1.6%, inconclusive); with the extended set the gain over the CPU is 7.5% [7.2, 7.8].")
r.section("Six workloads, GPU and limits")
rows = []
for w in fd.WL:
    row = [w]
    for cfg in ("cpu", "gpu"):
        row.append(fd.eff(fd.contrast(w, f"PRED_RANK_GREEDY_{cfg}", f"HEFT_param_model_{cfg}")))
    for cfg in ("cpu", "gpu"):
        row.append(fd.eff(fd.contrast(w, f"PRED_RANK_GREEDY_{cfg}", f"B4_{cfg}")))
    rows.append(row)
r.table("Effect of PRED (%, negative = PRED faster; exploratory except h16_l120)",
        ["Workload", "vs HEFT, CPU", "vs HEFT, strict GPU", "vs B4, CPU", "vs B4, strict GPU"], rows, [1.0, 1.4, 1.4, 1.4, 1.4], size=8)
r.para("The advantage depends on how much task cost varies: it is largest when 4 of 64 chains are heavy (about 40% against B4), shrinks with cost ratios of 20 and 7.5 and with 40 heavy chains, and is zero on the uniform workload (+0.0% [\u22122.5, +2.3] on the CPU). "
       "With ratio 7.5 and the strict GPU set PRED is slightly slower than B4 (+1.1% [+0.3, +1.9]). Under the model-based policies the CUDA worker takes roughly 15% to 20% of the 257 tasks; blind B4 sends about 32% to the GPU with the strict set and is slower for it.")
r.bullets([
    "**A simple rule gets almost all of the gain.** PRED against B4_param_first is " + MINUS + "0.4% [" + MINUS + "0.9, +0.1] (CPU), " + MINUS + "0.2% [" + MINUS + "0.9, +0.7] (strict GPU) and " + MINUS + "0.6% [" + MINUS + "1.1, " + MINUS + "0.0] (extended GPU), exploratory.",
    "**A hybrid selector is not justified:** the maximum headroom in 17 development cells was 1.1% (mean 0.08%), none above the 2% margin.",
    "**The cost model is weakest on the GPU** (23% to 31% median error); part of the dynamic-versus-static gap on GPU sets may reflect model error and not only decision timing, which was not separated.",
    "**Timing convention:** the end-to-end and old makespan differ by 12.5 ms (B4) to 81.3 ms (PEFT) on 3 to 4 s runs; no conclusion flips.",
    "**Two sessions disagree:** an earlier session found HEFT level with the dispatcher (+1.10% [" + MINUS + "0.53, +2.81]); the final session finds PRED about 5% faster. The difference was not isolated; both are reported.",
])
r.figure(FF + r"\fig_final_makespan.png", "End-to-end makespan of each policy in the three hardware sets (primary workload; geometric mean, 95% interval).", 4.3)
r.figure(FF + r"\fig_final_workloads.png", "PRED against static HEFT (left) and blind B4 (right) on the six workloads, CPU only (blue) and strict GPU set (orange).", 4.3)
r.table("Effect of the hardware set within each policy on the primary workload (%, negative = faster)",
        ["Policy", "Strict vs CPU", "Extended vs CPU", "Extended vs strict"], fd.gpu_rows(), [1.6, 1.6, 1.7, 1.6], size=8.5)
r.figure(FF + r"\fig_final_placement.png", "Tasks run on the CPU and on the GPU per policy (extended set, primary workload) and the GPU busy fraction.", 4.2)
r.table("Static plans against HEFT_param_model on the primary workload (%, exploratory)",
        ["Hardware set", "HEFT_E2E", "PEFT", "HEFT oracle (reference)"], fd.static_rows(), [1.4, 1.7, 1.7, 1.7], size=8.5)
r.para("Adding the end-to-end terms to the static plan did not help consistently; PEFT is clearly the slowest static plan; the oracle plan, built from class-median costs, is a reference and not a bound. "
       "Planned over actual makespan of the static plans was between 0.88 and 1.03, yet a fixed assignment cannot react to the actual completion order.")
r.table("Primary workload, CPU only: old and end-to-end makespan (s) and the difference (ms)",
        ["Policy", "Old convention", "End-to-end", "Difference (ms)"], fd.timing_rows(), [2.6, 1.3, 1.3, 1.3], size=8.5)
r.table("Primary workload, CPU only: initialisation, policy set-up, total scheduling time (ms) and mean queue wait (s)",
        ["Policy", "Init.", "Policy set-up", "Scheduling", "Queue wait"], fd.overhead_rows(), [2.4, 0.8, 1.2, 1.1, 1.0], size=8.5)
r.section("Earlier study (exploratory) and the remote worker")
r.para("On twenty chain orders never used before, the dispatcher was 19.3% (6P+7E) and 20.5% (2P+7E) faster than B4 and level with the hand rule; the gain was about 27% with few heavy chains and about 4% when most were heavy. "
       "There was no gain on Montage (every task prefers the P cores by 2.3 to 3.6 times), on a uniform batch or on a two-factor batch. In **emulation** the remote worker gave no benefit on a fast link although predicted and measured times matched (0.1457 s against 0.1464 s; "
       "the predictive policy was 3.78% [+2.27, +5.58] slower with it) and blind remote placement on a slow link cost 31%. These were not rerun with the final policies.")

# ------------------------------------------------------------------ 8
r.table("Earlier exploratory sessions on unseen chain orders (effect against B4, negative = shorter)",
        ["Session", "Blocks / orders", "Dispatcher", "Hand rule"],
        [["6P+7E, 16 heavy", "36 / 12", MINUS + "19.32% [" + MINUS + "20.0, " + MINUS + "18.6]", MINUS + "19.85%"], ["2P+7E, 16 heavy", "24 / 8", MINUS + "20.45% [" + MINUS + "21.2, " + MINUS + "19.8]", MINUS + "20.67%"],
         ["6P+7E, 4 heavy", "12 / 4", MINUS + "27.65% [" + MINUS + "34.0, " + MINUS + "18.7]", MINUS + "26.94%"], ["6P+7E, 8 heavy", "12 / 4", MINUS + "26.76% [" + MINUS + "27.9, " + MINUS + "25.7]", MINUS + "26.93%"],
         ["6P+7E, 40 heavy", "12 / 4", MINUS + "3.81% [" + MINUS + "5.1, " + MINUS + "1.9]", MINUS + "5.15%"]],
        [1.7, 1.3, 2.2, 1.3], size=8.5)
r.table("Defects and incidents found during the work",
        ["Item", "Found by", "Action"],
        [["Static plans timed from the first dispatch, hiding planning time", "design review", "end-to-end makespan (amendment F1); old metric kept"],
         ["Final-study stage 1 aborted: laptop unplugged, retry-id collision, low free memory (antivirus, Docker, WSL)", "run logs", "mains wait, first-unused-id logic; thresholds never lowered; attempts kept (_r2 to _r8)"],
         ["Idle CUDA worker defeats the dispatch loop\u2019s early exit", "overhead diagnosis", "quantified; fix in a separate adapter; not applied to the source"],
         ["Learned model used on a profile it was not fitted on", "audit", "profile binding recorded in the model; refusal on mismatch"],
         ["Remote node served one client then exited", "loopback rehearsal", "persistent mode and test"]],
        [2.9, 1.2, 2.4], size=8.5)
r.chapter("Existing versus Proposed Implementation")
r.table("Differentiation between the existing (base) idea and the proposed work",
        ["Aspect", "Existing (B4 / base patent idea)", "Proposed"],
        [["Order of ready tasks", "first-come first-served", "predicted upward rank"],
         ["Worker choice", "first idle eligible worker", "idle eligible worker with least predicted time; GPU only for verified stages"],
         ["Cost knowledge", "none", "ridge model learned from logs; refitted by one command"],
         ["Planning", "none (dynamic)", "compared against static HEFT/PEFT plans from the same model"],
         ["Timing", "dispatch to last completion", "end-to-end, including start-up and planning"],
         ["Primary workload", "reference", MINUS + "17.8% (CPU), " + MINUS + "21.2% (strict GPU) vs B4; " + MINUS + "5.2% and " + MINUS + "12.2% vs static HEFT"],
         ["No cost spread", "reference", "+0.0% (equivalent within \u00b12%)"],
         ["Evidence", "FPGA system (patent); simulation (papers)", "real runs, paired intervals, ten Holm-adjusted contrasts, 521 tests"]],
        [1.5, 2.2, 2.8], size=8.5)
r.para("What prediction buys is ordering and informed placement; what it does not buy is anything beyond a rule that knows the cost parameter, anything where task cost does not vary, or an end-to-end benefit from accurate remote predictions alone. "
       "This agrees with {{ilyushkin}} that order can matter more than estimate accuracy, now on real executions.")

# ------------------------------------------------------------------ 9
r.chapter("Testing, Reproducibility and Demonstration Guide")
r.para("Every session stores design, environment and code hashes; the tables of the final report are generated from the stored analysis files by scripts; 520 of 521 tests pass. The pipeline is `scripts/final_stage1.ps1` (calibration, models, designs), `scripts/final_stage2.ps1` (six evaluation sessions), "
       "`scripts/final_analyze.py`, `scripts/final_results_table.py` and `scripts/final_build_report.py`. Commands assume the project root and the virtual environment (call `.\\.venv\\Scripts\\python.exe` directly if PowerShell blocks activation).")
r.code(r".\.venv\Scripts\python.exe -m caosched.dashboard_v3 --port 8770 --events-dir data\results\final_20261101\eval\sessions --open" "\n"
       r".\.venv\Scripts\python.exe -m caosched.dashboard_v2 --port 8766 --events-dir data\results\final_20261101\eval\sessions --open" "\n"
       r".\.venv\Scripts\python.exe -m pytest -q")
r.para("The dashboard shows the GPU (RTX 3050) as connected, the Raspberry Pi as *not connected*, the final results with hover details on screen 3, and, on screen 6 of v3, one live block of the final benchmark (about one to two minutes; needs 2.4 GB of free RAM). "
       "Five-minute narrative: a workflow is a task graph and a scheduler decides where and in what order; a static plan fixes this beforehand, a dynamic policy decides while running; with one cost model the dynamic policy is 2% to 12% faster than the static plan and about 18% to 21% faster than blind dispatch when task cost varies; "
       "a rule that knows the cost parameter is almost as good; there is no gain without cost spread; the Raspberry Pi is not measured.")

# ------------------------------------------------------------------ 10
r.chapter("Publication and IPR Route")
r.bullets([
    "**Primary candidate:** IEEE/ACM CCGrid 2027, full paper of 10 pages in IEEE two-column format, double-blind, abstract 24 Nov. 2026 and paper 1 Dec. 2026 as read from the call {{ccgrid27}}; re-check the dates. Scopus indexing and quartile of every candidate must be verified on the publisher and Scopus pages before submission.",
    "**Alternatives:** a parallel/distributed-computing or future-generation-systems journal after adding real-link results; a workshop; a book chapter (no call verified).",
    "**IPR:** the base patent claims graph, queue and gating; rank-ordered learned dispatch is disclosed by {{p_ibm1}}. The Invention Disclosure Form draft (document 08) must be filed *before* any public disclosure; a professional prior-art search is required. This is not legal advice.",
    "**Disclosure timing:** publishing the code or paper first can defeat novelty; the GitHub release is prepared but not pushed.",
])

# ------------------------------------------------------------------ 11
r.chapter("Conclusion, Limitations and Future Work")
r.para("On a hybrid CPU+GPU laptop and one workload family, dynamic dispatch driven by a cheap cost model finishes a workflow 2% to 12% sooner than a static HEFT plan from the same model (5% on the CPU, 12% with the strict GPU set) and about 18% to 21% sooner than blind dispatch when task cost varies; "
       "it ties blind dispatch when it does not. A rule that knows the cost parameter reaches almost the same result, end-to-end terms and a hybrid selector add nothing, and the GPU helps only where a speed-up was measured and the model chooses the tasks.")
r.table("Claim status",
        ["Status", "Claims"],
        [["Supported", "dynamic PRED beats blind B4 and the static HEFT plan from the same model (C1, C3, C5, C8); the GPU helps PRED (C9); end-to-end terms are equivalent (C2, C7)"],
         ["Not established", "advantage over a rule that knows the cost parameter; a hybrid selector; GPU benefit for blind B4; remote offloading benefit; any Raspberry Pi or real-network result; generality beyond this machine and workload family"],
         ["Not supported / null", "gain on Montage, on uniform and light workloads, on the two-factor workload; a remote worker helping EFT at level 30"]],
        [1.4, 5.1], size=8.5)
r.para("**Limitations.** One machine, one image-pipeline family at 512 px, one CUDA worker; only the primary session is confirmatory; static plans are occupancy-blind and the oracle plan uses class medians; features of the hybrid check were computed after the primary results were read; "
       "the source tree has uncommitted changes and sessions are never pooled across code hashes. **Future work:** a GPU cost model with lower error and an experiment that separates model error from decision timing; a second workload family; the remote worker with the final policies and a real link; a clean-tree rerun; a professional prior-art search.")

r.references()
r.chapter_plain("Appendix A. File Map")
r.table("Key locations (repository root D:\\cao project)",
        ["What", "Where"],
        [["Source, tests, scripts", "`src/caosched/`, `tests/`, `scripts/`"],
         ["Final study data and evidence", "`data/results/final_20261101/` (eval, calibration, models, preservation, ACTIVITY_LOG.md)"],
         ["Final experiment report and table", "`CAO_FINAL_EXPERIMENT_REPORT.md`, `RESULTS_TABLE_FINAL.csv`"],
         ["Protocol and amendment", "`docs/final/PROTOCOL_final.md`, `docs/final/AMENDMENT_F1_timing.md`"],
         ["Dashboards", "`src/caosched/dashboard/` (original), `dashboard_v2/`, `dashboard_v3/`"],
         ["Submission package", "`SUBMISSION_FINAL/` (this report, reviews, paper, deck, IPR documents, release bundle)"]],
        [2.0, 4.5], size=9)

o = OUT + r"\05_Final_Project_Report"
r.save(o + ".docx")
pages, words = export_pdf(o + ".docx", o + ".pdf")
print("report pages", pages, "words", words, "refs", len(r.cite_order))
