from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, Preformatted, KeepTogether)
from reportlab.lib.utils import ImageReader

D = r"D:\cao_project_guide_output"
ss = getSampleStyleSheet()
B = ParagraphStyle("B", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.6, leading=13.2, spaceAfter=4)
BL = ParagraphStyle("BL", parent=B, leftIndent=12, bulletIndent=2, spaceAfter=2)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=16, textColor=colors.HexColor("#12355b"), spaceBefore=4, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, textColor=colors.HexColor("#1f4e79"), spaceBefore=8, spaceAfter=4)
CODE = ParagraphStyle("C", fontName="Courier", fontSize=7.8, leading=9.6, backColor=colors.HexColor("#f4f4f4"), borderPadding=4, spaceAfter=6, leftIndent=4)
CELL = ParagraphStyle("CELL", parent=B, fontSize=8.2, leading=10.2, spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
NOTE = ParagraphStyle("N", parent=B, backColor=colors.HexColor("#fff4d6"), borderPadding=5, spaceBefore=3, spaceAfter=8, fontSize=9)
S = []


def p(t): S.append(Paragraph(t, B))
def h1(t): S.append(PageBreak()); S.append(Paragraph(t, H1))
def h1n(t): S.append(Paragraph(t, H1))
def h2(t): S.append(Paragraph(t, H2))
def bl(items):
    for i in items: S.append(Paragraph(i, BL, bulletText="\u2022"))
    S.append(Spacer(1, 3))
def note(t): S.append(Paragraph(t, NOTE))
def code(t): S.append(Preformatted(t.strip("\n"), CODE))


def table(rows, widths, head=True):
    data = [[Paragraph(str(c), CELLB if (head and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if head: st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")))
    for i in range(1, len(rows)):
        if i % 2 == 0: st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f1f6fb")))
    t.setStyle(TableStyle(st)); S.append(t); S.append(Spacer(1, 6))


def img(name, width_cm=17):
    ir = ImageReader(f"{D}\\diagrams\\{name}"); w, h = ir.getSize()
    S.append(Image(f"{D}\\diagrams\\{name}", width=width_cm * cm, height=width_cm * cm * h / w)); S.append(Spacer(1, 4))


# ---------------- title ----------------
S.append(Spacer(1, 3 * cm))
S.append(Paragraph("CAO: Prediction-Aware Task Scheduling for Heterogeneous Computing", ParagraphStyle("T", parent=H1, fontSize=22, leading=27, alignment=1)))
S.append(Paragraph("Project explanation and presentation guide (study material, not a research paper)", ParagraphStyle("T2", parent=B, fontSize=12, alignment=1, spaceAfter=18)))
table([["Source version", "Git branch <b>revival/resource-state-aware</b>, commit <b>9d8ea22</b> (committed baseline). The audit session's uncommitted edits were inspected read-only and are labelled <b>AUDIT WIP</b>."],
       ["Guide written", "2026-11-01. Nothing in the project was modified."],
       ["Result policy", "Only numbers found in the project's own records are used (mainly PROJECT_BACKBONE.md, docs/revival/*, data/results/*). Anything not finished is labelled <b>PENDING</b>."],
       ["Status labels", "<b>VERIFIED</b> = measured, raw logs stored. <b>ESTIMATE</b> = simulation/bound. <b>AUDIT WIP</b> = uncommitted, not final. <b>PENDING</b> = final experiments not finished."]],
      [3.4, 13.6], head=False)
S.append(Spacer(1, 6))
note("<b>One-sentence summary to memorise:</b> CAO is a Python framework that runs a workflow (a DAG of tasks) on a laptop's fast CPU cores, slow CPU cores, a GPU and an emulated remote worker, and tests whether a scheduler that <i>predicts</i> each task's runtime with a small ML model finishes the whole workflow sooner than simple rules. "
     "Honest result: it clearly beats static and naive schedulers (17% to 45% faster) and beats the simple greedy baseline B4 only when task cost is hidden inside task parameters; it never beat the best hand-written rule, and the GPU/live-state ideas were not shown to help.")
S.append(Paragraph("<b>Contents</b>", H2))
bl(["1 Introduction and objectives", "2 Fundamentals and terminology", "3 System architecture", "4 End-to-end workflow", "5 Methodology", "6 DAG, workloads, dependencies",
    "7 ML runtime estimator and metrics", "8 Scheduling algorithms", "9 CPU, GPU, CUDA, remote worker, offloading", "10 Directory and important files",
    "11 Code walkthrough (stage -> class/function)", "12 Frontend and demonstration", "13 Experiments, metrics and verified results", "14 Base papers and related work", "15 Limitations, future work, faculty Q&amp;A"])

# ---------------- 1 ----------------
h1("1. Introduction, problem and objectives")
h2("1.1 Real-world analogy")
p("Imagine a kitchen with <b>2 fast chefs</b>, <b>7 slow chefs</b>, 1 specialist machine (the GPU) and a helper in another building (the remote worker). Dinner is a recipe with dependent steps: you cannot plate before cooking. "
  "A <b>scheduler</b> is the head chef who decides, every time a step becomes possible, <i>which chef</i> does it and <i>in what order</i>. A lazy head chef gives each step to the first free chef. A smarter head chef "
  "<i>guesses how long each step will take on each chef</i> and gives the long, critical steps first to the right chef. CAO builds the kitchen, the recipes and several head chefs, then measures who finishes dinner first.")
h2("1.2 Problem and motivation")
bl(["Modern machines are <b>heterogeneous</b>: different cores and accelerators have different speeds, and moving data between them costs time.",
    "Static schedulers decide everything before the run using fixed rules; they ignore what actually happens at runtime.",
    "Goal: a scheduler that is <b>prediction-aware</b> and <b>dynamic</b> (decides during the run) and lowers <b>end-to-end makespan</b> (total time from start to finish of the workflow). Better prediction numbers alone are not the goal."])
h2("1.3 Objectives")
bl(["Build a real runtime: DAG, coordinator, worker pool with P-core, E-core, CUDA and remote workers, event logs.",
    "Build runtime estimators (constant table, analytic, history, ridge/ML, oracle) and many scheduling policies (B0 to B7, EFT, HEFT, PEFT, rank-based).",
    "Evaluate honestly: pre-registered protocols, paired comparisons, bootstrap confidence intervals, Holm correction, keep negative results."])
h2("1.4 Expected vs actual contribution")
table([["Intended", "What the evidence actually supports"],
       ["Prediction-aware heterogeneous offloading beats static scheduling", "<b>VERIFIED</b>: learned-prediction policy is 17% to 45% faster than static P-only / table-predictor policies on several pre-registered workloads."],
       ["...and beats simple dynamic greedy (B4)", "Only where cost is hidden in task parameters (about 20-21% faster). Level with B4 on uniform and two-factor workloads. Montage: valid <b>null</b> result."],
       ["GPU offloading speeds up workflows", "<b>Not established</b>. Single GPU tasks can be faster, but workflow-level headroom was ~0% in simulation; only 6.4% of dispatches had a real choice."],
       ["Remote/Raspberry Pi offloading", "Only <b>emulated</b> (loopback + delay shim). No real remote hardware tested."]], [6, 11])

# ---------------- 2 ----------------
h1("2. Fundamentals and terminology")
terms = [
 ("CPU / core", "The processor that runs general programs; a core executes one instruction stream at a time."),
 ("P-core / E-core", "Performance cores are fast; Efficiency cores are slower but numerous. Here: 6 P workers and 7 E workers (coordinator uses one reserved core). Measured P/E speed ratio is about 2.3x to 3.6x for tasks."),
 ("GPU / CUDA / kernel", "A GPU has thousands of small cores, good for big data-parallel work. CUDA is NVIDIA's programming platform. A <b>kernel</b> is the function that runs on the GPU. Here: RTX 3050 6 GB laptop GPU via PyTorch."),
 ("Heterogeneous computing", "Using different kinds of processors in one system (P, E, GPU, remote)."),
 ("Task / process / thread", "A <b>task</b> is one unit of work (one pipeline stage on one image). A <b>process</b> is a running program with its own memory; CAO workers are separate pinned processes. A thread is a lighter flow inside a process."),
 ("Workflow, DAG, node, edge", "A workflow is many tasks with ordering. A <b>DAG</b> (directed acyclic graph) draws tasks as <b>nodes</b> and dependencies as <b>edges</b> (arrows) with no cycles."),
 ("Dependency / ready task", "Task B depends on A if B needs A's output. A task is <b>ready</b> when all its dependencies are done."),
 ("Execution time / runtime prediction", "How long a task runs on a given worker. The estimator predicts it before the run (features -> seconds)."),
 ("Scheduling / placement / offloading", "Scheduling = choosing order and worker. Placement = choosing the worker. Offloading = sending work to another device (GPU or remote)."),
 ("Static vs dynamic", "Static: whole plan fixed before running (HEFT, PEFT, B0 P-only). Dynamic: decisions made as tasks become ready (B4, PRED_RANK_GREEDY)."),
 ("Early vs late binding", "Early: task is committed to a (possibly busy) worker's queue. Late: task is bound only to an <i>idle</i> worker. Early binding cost about 1.7% in the Montage study; late binding is work-conserving (no worker idles while work waits)."),
 ("Load balancing", "Spreading work so no worker idles while another is overloaded."),
 ("Data transfer / communication / scheduling overhead", "Time to move data (host to GPU, or over a network link); time for messages between coordinator and workers (IPC); time the scheduler spends deciding. Scheduling cost is guarded to stay below 25% of makespan."),
 ("Makespan", "Time from workflow start to the last task finishing. The main metric. Lower is better."),
 ("Critical path", "The longest chain of dependent tasks; it sets a lower bound on makespan."),
 ("Resource utilisation", "Fraction of time workers are busy. Uniform batch workload ran at about 95%."),
 ("Remote worker / emulation", "A worker in another process behind a delay shim (latency + per-message + bytes/bandwidth) that imitates a network. It is <b>not</b> a real second machine."),
]
table([["Term", "Simple meaning in this project"]] + [[a, b] for a, b in terms], [4.0, 13.0])

# ---------------- 3 ----------------
h1("3. Complete system architecture")
img("architecture.png")
p("<b>Reading the diagram.</b> The <b>workload builder</b> creates a DAG of Task objects. The <b>coordinator</b> is the single controller: it keeps tasks in states and a <b>ready queue</b>, and on every pass it asks the <b>scheduler policy</b> two questions: "
  "(1) <code>order_ready</code> - in what order should ready tasks be considered? (2) <code>select_worker</code> - which worker gets this task? The policy may consult an <b>estimator</b> for predicted seconds. "
  "The coordinator then binds and submits the task to a worker. Workers run the stage and write results to artifact files; every step is written to a JSONL <b>event log</b>, which the analysis scripts and dashboard read.")
note("<b>Logical vs real process architecture.</b> Logically there are 'pools' P, E, CUDA, R. In reality each worker is a separate OS process pinned to a CPU core (core/worker_pool.py <code>_worker_loop</code>); the coordinator runs in the main process pinned to a reserved core; the remote worker is a separate process (remote/node.py) reached through a socket proxy (remote/proxy.py) with an artificial link delay.")
h2("Task lifecycle (core/task.py: TaskState)")
code("PENDING --(all dependencies DONE)--> READY --(scheduler binds)--> DISPATCHED --(worker returns)--> DONE\n                                                                     \\--> FAILED\nIllegal transitions raise InvalidTransition (the coordinator refuses to corrupt the timeline).")

# ---------------- 4 ----------------
h1("4. End-to-end workflow, step by step")
img("workflow.png")
p("Numbered walkthrough of one run (Coordinator.run in core/coordinator.py):")
bl(["<b>1. Build.</b> A workload builder returns a DAG; every task starts PENDING with its dependencies and <code>eligible_pools</code> (which pools may run it).",
    "<b>2. Check.</b> <code>resolve_eligibility</code> verifies every task can run somewhere; the run refuses to start if workers are dead or busy.",
    "<b>3. Start.</b> <code>scheduler.on_run_start</code> runs once (HEFT/PEFT compute their static plan here). Tasks with no dependencies become READY.",
    "<b>4. Dispatch pass.</b> <code>_dispatch_ready_tasks</code>: ask <code>order_ready</code>, then for each task <code>select_worker</code>. If it returns <code>None</code> the task waits.",
    "<b>5. Bind + submit.</b> <code>_bind</code> marks the task DISPATCHED and logs the decision; <code>_submit</code> builds a TaskMessage (CPU variant for P/E, <code>device=cuda</code> for the CUDA worker) and sends it to the worker.",
    "<b>6. Execute.</b> The worker reads input artifacts, runs the stage kernel, writes the output artifact, returns a TaskResult.",
    "<b>7. Complete.</b> <code>_handle_completion</code> marks DONE, logs timings, tells the policy (<code>on_task_completed</code>), and makes newly unblocked dependents READY.",
    "<b>8. Finish.</b> Loop ends when <code>dag.is_complete()</code>; a RunSummary (makespan, scheduling time, tasks per pool) is returned and logged."])
h2("What happens in special situations")
table([["Situation", "What CAO does"],
       ["Task has unfinished dependencies", "Stays PENDING; not in the ready queue; no scheduler call."],
       ["Many tasks are ready", "<code>order_ready</code> ranks them (B4: FIFO; PRED_RANK_GREEDY: longest predicted remaining chain first)."],
       ["Worker is busy", "Late-binding policies only choose idle workers, so the task waits in the ready queue. Early-binding EFT may queue it behind a busy worker."],
       ["Task eligible for CPU only", "e.g. <code>img_source</code>: only P and E workers are candidates."],
       ["Task can run on CPU or GPU", "Policy compares idle eligible workers; PRED picks the smallest <i>predicted</i> time; B4 just takes the first idle by pool priority."],
       ["GPU transfer overhead is large", "Small inputs make GPU slower than a P core (e.g. edges 256 px: P 6.2 ms vs GPU 7.2 ms). The estimator must include copy/IO cost or the policy mis-places."],
       ["Task finishes", "State DONE; dependents checked; if all their dependencies are DONE they become READY."],
       ["Whole DAG completes", "<code>run_finished</code> event with the summary; artifacts are verified against a single-process reference output."]], [5, 12])
h2("Tiny worked example")
p("DAG A->B, A->C, B->D, C->D (see Section 8.3). t=0: only A is ready. A finishes: B and C become ready at the same time. Two idle workers: both are dispatched. D waits (PENDING) until both B and C are DONE, then it becomes READY and is dispatched. If only one worker is idle, ordering decides: the policy sends the longer-chain task (B) first.")

# ---------------- 5 ----------------
h1("5. Proposed methodology")
table([["Step", "What happens", "Component"],
       ["1 Workflow/DAG generation", "Image-analysis pipeline and synthetic chain workloads", "apps/image_pipeline.py, study2/workload.py, core/dag.py"],
       ["2 Tasks + dependencies", "Task objects with params, size, dependencies, eligible pools", "core/task.py, core/eligibility.py"],
       ["3 Profiling / training data", "A 'coverage session' runs every stage on every pool and logs kernel seconds", "scripts/study2_*.py, event logs in data/events"],
       ["4 Runtime estimation", "Per-(stage,pool) ridge regression on task parameters (ParamModelEstimator)", "study2/param_model.py"],
       ["5 Ready-task identification", "Coordinator marks tasks READY when dependencies are DONE", "Coordinator._mark_ready"],
       ["6 Scheduling policy", "order_ready ranks tasks (upward rank from predicted times)", "study2/policies.py PredictedRankGreedy"],
       ["7 Worker selection", "Idle eligible worker with the smallest predicted time", "PredictedRankGreedy.select_worker"],
       ["8 Dispatch", "Bind, log decision, send TaskMessage", "Coordinator._bind / _submit"],
       ["9 Execution", "Pinned worker process runs the stage (CPU/CUDA/remote)", "core/worker_pool.py, apps/stages.py, apps/cuda_stages.py"],
       ["10 Monitoring", "Event log per task, per-core load, scheduling-time accounting", "core/event_log.py, dashboard/data.py"],
       ["11 Result collection", "TaskResult -> DONE; RunSummary; output verified vs reference", "Coordinator._handle_completion, apps.verify_output"],
       ["12 Evaluation/feedback", "Paired blocks, bootstrap CI, Holm; retraining for a new machine", "analysis/*, scripts/study2_retrain.py"]], [3.6, 7.6, 5.8])
note("<b>Key design rule learned from failures:</b> order by predicted rank, place only on an idle worker (late, work-conserving binding). The earlier predictive EFT lost ~6% to a hand rule because of <i>early binding</i>, not bad predictions.")

# ---------------- 6 ----------------
h1("6. DAG, workload generation and dependencies")
h2("6.1 DAG implementation")
p("<code>core/dag.py: DAG</code> stores <code>tasks</code> (id -> Task), supports <code>topological_order()</code>, <code>dependents(tid)</code>, <code>initial_ready_tasks()</code>, <code>is_complete()</code>, and raises <code>CycleError</code> on cycles. "
  "Helper builders: <code>build_independent_dag</code>, <code>build_chain_dag</code>, <code>build_fork_join_dag</code>, <code>build_mixed_dag</code>.")
h2("6.2 The image-analysis application")
p("<code>apps/stages.py</code> defines stages: <b>source, tile, denoise, edges, features, mosaic, aggregate, package</b>. The dashboard's default DAG has 68 tasks over 8 stages (<code>dashboard/static/index.html</code>); "
  "workload levels k = 1, 4, 16, 64 (<code>dashboard/live.py LEVELS</code>). CUDA variants exist for denoise, edges, features (<code>apps/cuda_stages.py</code>). <code>img_source</code> is CPU-only. In the dashboard demo, denoise and edges may also run on the emulated remote pool R (<code>REMOTE</code> in live.py).")
h2("6.3 Workload families used in experiments (study2/workload.py)")
table([["Builder", "Shape", "Why it exists"],
       ["build_batch", "64 identical chains source->denoise->edges->features + aggregate", "Uniform control: tests 'do no harm'. No hidden cost, ~95% utilisation."],
       ["build_iters", "Chains differing only in hidden denoise iterations", "Cost hidden from size-keyed tables - where prediction can matter."],
       ["build_classes", "Two-factor chains [count, side, iterations]; classes 48x(256px,2), 12x(256px,300), 12x(1024px,3)", "Cost depends on size AND repeats; a size-only rule fails."],
       ["build_mixed", "256/1024 px mix", "Dropped."],
       ["Montage (workflow/adapter.py)", "Real astronomy mosaic workflow", "Stage-5 result: null (one dominant serial path, all tasks prefer P cores)."],
       ["revival/workload.py", "72 chains, 6 groups, two-level fan-in, 295 tasks", "Contention / live-state tests."]], [3.6, 7, 6.4])

# ---------------- 7 ----------------
h1("7. ML runtime estimator and its metrics")
h2("7.1 Why predict runtime?")
p("A scheduler cannot rank tasks or choose a worker without knowing how long each task will take on each worker. The estimator answers: <i>given this task and this pool, how many seconds?</i> "
  "<b>Feature</b> = an input number (image side in pixels, repeat count). <b>Target</b> = the measured kernel seconds. A model learns target from features.")
h2("7.2 Estimators in the repo (estimators/*, study2/param_model.py)")
table([["Name", "Class", "Idea"],
       ["E0 constant", "ConstantProfileEstimator", "One number per workload."],
       ["E1 static table", "StaticProfileEstimator", "Median time keyed by (stage, size, pool)."],
       ["E2 analytic", "AnalyticSizeEstimator", "Formula in size."],
       ["E3 history", "MovingHistoryEstimator", "Moving average of recent observed times."],
       ["E4 ridge", "InterferenceRidgeEstimator", "Ridge regression with occupancy/context features."],
       ["CatBoost / MLP", "CatBoostEstimator, MlpEstimator", "Tabular correction models (explored, not the final policy)."],
       ["E5 oracle", "ReplayOracleEstimator", "Replays known true times - an upper bound, not deployable."],
       ["<b>Param model (used by PRED_*)</b>", "ParamModelEstimator", "Per (stage, pool) ridge regression on numeric task parameters + size + pairwise products."],
       ["Recalibrated", "RecalibratedEstimator", "Corrects a base estimator using observed residuals."]], [3.6, 5.4, 8])
h2("7.3 How ParamModelEstimator works")
bl(["<b>Training data:</b> a coverage session runs each stage on each pool with varied parameters; kernel seconds are read from event logs.",
    "<b>Features (decided from the data, not typed):</b> numeric entries of <code>task.params</code> plus <code>size</code> that vary in the logs; if two or more vary, their pairwise products too (cost often = size x repeats). seed/width/height/device/timeout are ignored.",
    "<b>Fit:</b> <code>fit_group</code>: standardise columns, ridge least squares (<code>ridge=1e-9</code>, solved by lstsq), return coefficients in raw units: seconds = a + sum(b_i x_i). "
    "<b>Revival form:</b> <code>fit_group_log_power</code>: log(time) = a + sum b_i log(x_i), fixes big relative error on the cheapest tasks.",
    "<b>Predict:</b> <code>estimate(task, pool)</code> looks up group key '<code>workload|pool</code>' and takes a dot product (microseconds, no scheduling cost).",
    "<b>Unseen data:</b> unknown (workload, pool) raises <code>KeyError</code> - no silent fallback. New machine or pool -> one-command retrain (<code>scripts/study2_retrain.py</code>)."])
code("""# study2/param_model.py (simplified)
coef = lstsq(standardised_features + ridge_rows, measured_seconds)   # fit_group
seconds = max(1e-6, coef . [1, x1, x2, x1*x2])                       # predict_group""")
p("<b>Regularisation (ridge)</b> adds a small penalty on coefficient size so the fit stays stable when features are correlated (size, repeats and their product are).")
h2("7.4 Metrics (formulas with a tiny example)")
p("True times y = [10, 20, 30] ms; predicted p = [12, 18, 33] ms; errors e = [2, -2, 3].")
table([["Metric", "Formula", "Example", "Meaning"],
       ["MAE", "mean(|p - y|)", "(2+2+3)/3 = 2.33 ms", "Average miss in ms. Robust, easy to explain."],
       ["RMSE", "sqrt(mean((p - y)^2))", "sqrt((4+4+9)/3) = 2.38 ms", "Punishes big misses more."],
       ["R2", "1 - sum(p-y)^2 / sum(y-mean(y))^2", "1 - 17/200 = 0.915", "Share of variation explained (1 = perfect)."],
       ["Relative error", "|p - y| / y", "20%, 10%, 10%", "Matters for cheap tasks."]], [2.4, 5, 4.6, 5])
note("<b>Estimator accuracy is NOT scheduling performance.</b> A model can be accurate and still give no makespan gain (no headroom), or be rough and still order tasks correctly. Verified hold-out: heavy classes within 8% (P 256px x300: predicted 0.605 s vs 0.565 s measured; 1024px x3: 0.122 vs 0.112); lightest class badly off (17.6 ms vs 4.1 ms on P). "
     "Power-law form cut denoise median error from 3.4 (P) / 1.0 (E) to 0.19 / 0.02 (revival measurement). Final-audit prediction accuracy numbers: <b>PENDING</b>.")

# ---------------- 8 ----------------
h1("8. Scheduling algorithms and differences")
p("Two separate decisions: <b>task ranking</b> (which ready task first - <code>order_ready</code>) and <b>worker selection</b> (which worker - <code>select_worker</code>). Policies differ in how they do each.")
table([["Policy", "Class (file)", "Ranking", "Worker selection", "Type"],
       ["B0_P_only", "PoolOnlyScheduler (schedulers/simple.py)", "FIFO", "Idle P worker only; E and GPU never used", "Static pool, late binding"],
       ["B0_P_early", "PoolOnlyEarlyScheduler", "FIFO", "P workers, queued on busy ones", "Early binding control"],
       ["<b>B4</b> (B4_greedy_eligible)", "GreedyEligibleScheduler", "FIFO", "First idle eligible worker, pool priority P, E (, R); no estimates", "Dynamic, blind"],
       ["B4_param_first / cost_first / largest_first", "study2/policies.py (ParamFirstGreedy, CostFirstGreedy, LargestFirstGreedy)", "By repeats / pixels x repeats / size, largest first", "Same as B4", "Hand-written rules that know the cost driver; non-predictive"],
       ["EFT (EFT_E1_rc)", "EarliestFinishTimeScheduler (schedulers/eft.py)", "Ready order", "Worker with earliest predicted finish incl. busy ones (early binding)", "Dynamic, predictive"],
       ["Rank-EFT", "RankEftScheduler", "Upward rank", "EFT", "Dynamic, predictive"],
       ["HEFT", "HeftScheduler (schedulers/heft.py)", "Upward rank, whole DAG", "Earliest finish time, full plan made before the run", "<b>Static</b> plan"],
       ["PEFT", "PeftScheduler (schedulers/peft.py)", "Optimistic cost table", "Plan before the run", "<b>Static</b> plan"],
       ["HEFT_param_model, PEFT_param_model", "built in study2/adapter.py", "as HEFT / PEFT", "Plans use ParamModelEstimator", "Static, predictive"],
       ["<b>PRED_RANK_GREEDY</b>", "PredictedRankGreedy (study2/policies.py)", "Predicted upward rank (longest remaining chain first)", "Idle eligible worker with smallest predicted time", "<b>Dynamic, predictive, work-conserving</b>"],
       ["PRED_RANK_HOLD", "same class, hold_min_s set", "same", "May hold a task for a much faster busy worker", "Tested; no gain, 4x decision cost"],
       ["Revival policy", "revival/policy.py (ResourceStateAwareRankGreedy)", "Rank", "Adds live state (core load, residuals); falls back to B4 with logged reason", "Gate failed - no headroom"]],
      [3.3, 3.6, 3.0, 4.2, 2.9])
note("<b>_E2E variants (HEFT_E2E, PRED_RANK_GREEDY_E2E):</b> estimators/e2e.py defines <code>EndToEndTerms</code> (adds file I/O / transfer terms to predictions). These belong to the ongoing audit; treat them as <b>AUDIT WIP / PENDING</b> until the audit finishes.")
h2("8.1 Differences in one line each")
bl(["<b>B4 vs PRED:</b> B4 is blind and uses FIFO + first idle; PRED orders by predicted remaining chain and picks the fastest idle worker.",
    "<b>HEFT vs PRED:</b> HEFT fixes the whole plan before running (static, early binding); PRED decides at runtime and never queues behind a busy worker.",
    "<b>PEFT:</b> like HEFT but looks one step ahead with an optimistic cost table; ~20% behind in Study 2; in the overnight check HEFT with the learned model was indistinguishable from PRED (-18.1% vs -19.0% vs B4) and PEFT much weaker (-2.6%).",
    "<b>HEFT result:</b> ~3% behind the hand rule in Study 2; static-plan overhead and early binding hurt."])
h2("8.2 Pseudocode of PRED_RANK_GREEDY (from the real code)")
code("""order_ready(ready):  sort ready tasks by upward rank (predicted times), largest first
select_worker(task):
    idle = eligible workers that are idle
    if none: return None                      # task waits (work-conserving)
    return argmin over idle of estimator.estimate(task, pool_of(worker))
# binds_only_idle = True: coordinator rejects binding to a busy worker""")
h2("8.3 HEFT upward rank - numeric example")
img("sample_dag.png", 11)
p("<code>upward_rank</code> (schedulers/heft.py) walks the DAG in reverse topological order: <code>rank[t] = mean_cost(t) + max(edge(t,child) + rank[child])</code>. With costs A4, B6, C3, D5 and zero communication: D=5, B=11, C=8, A=15. Higher rank = more work still behind it = schedule first.")

# ---------------- 9 ----------------
h1("9. CPU, GPU, CUDA, remote worker and offloading")
img("cpu_gpu_remote.png", 15)
h2("9.1 Workers")
bl(["<b>P and E pools:</b> pinned processes (core/worker_pool.py), thread libraries pinned to 1 thread so tasks do not fight each other.",
    "<b>CUDA worker:</b> runs <code>apps/cuda_stages.py</code> via PyTorch; <code>_submit</code> sets <code>device=cuda</code> only when the chosen worker kind is cuda. A task is never forced onto a device it does not support: <code>core/eligibility.py</code>.",
    "<b>Remote worker (emulated):</b> remote/node.py (server), remote/proxy.py (client side), remote/protocol.py (framed messages with auth token), remote/link.py (<code>LinkConfig.shim_delay = latency + per_message + bytes/bandwidth</code>). All on one laptop; a Raspberry Pi is planned but <b>not tested</b>."])
h2("9.2 Why GPU can be faster or slower (VERIFIED, median ms incl. all costs, P / GPU)")
table([["Task", "P-core", "GPU", "Reading"],
       ["edges 256 px", "6.2", "7.2", "Too small: copy + I/O overhead eats the gain."],
       ["edges 1024 px", "45.0", "14.8", "GPU 3x faster (busy GPU: 18.8)."],
       ["features 2048 px", "52.4", "22.2", "Big data wins."],
       ["denoise x8, 1024 px", "215", "214", "Tie; GPU busy -> 515 (P wins)."],
       ["denoise x60, 1024 px", "1562", "1157", "GPU wins quiet; busy 3570 -> P wins."]], [4.5, 2.5, 2.5, 7.5])
p("Breakdown of a GPU edges task at 512 px: kernel + host/device copies 33%, file I/O and codec 51%, IPC 8%. Host-to-device copy of the input is only 0.29 ms, but the GPU worker is occupied 9.1 ms - so <b>file I/O and messaging, not the kernel, dominate</b>. "
  "These costs are inside the measured wall time (submit to result) and were split out separately for analysis, so they must not be added twice.")
note("<b>Verdict (VERIFIED + ESTIMATE):</b> single-task GPU speedups exist, but at workflow level 60% of the work is CPU-only (<code>img_source</code>), and in stored runs only 6.4% of dispatches had two or more idle workers (0.8% with both a GPU and CPU idle). Simulated oracle headroom was ~0.05%. So 'GPU offloading helps the whole workflow' is <b>not established</b>.")

# ---------------- 10 ----------------
h1("10. Project directory and important files")
code("""D:\\cao project
  src/caosched/
    core/        coordinator.py  dag.py  task.py  ready_queue.py  eligibility.py
                 scheduler_base.py  worker_pool.py  event_log.py  runtime_config.py
    schedulers/  simple.py (B0,B4,...)  eft.py  rank_eft.py  heft.py  peft.py
    estimators/  base.py  profile.py  analytic.py  history.py  learned.py  tabular.py
                 oracle.py  recalibrated.py  e2e.py
    study2/      workload.py  param_model.py  policies.py  adapter.py   (main research code)
    revival/     policy.py  state.py  contention.py  oracle.py  gpuprofile.py ...
    apps/        stages.py  cuda_stages.py  image_pipeline.py  artifacts.py
    remote/      node.py  proxy.py  protocol.py  link.py
    workflow/    adapter.py  (Montage workflows)
    experiment/  runner.py  design.py  *_adapter.py  manifest.py
    analysis/    paired statistics, bootstrap CI, accuracy metrics
    dashboard/   server.py  live.py  data.py  static/(index.html app.js app.css)
    phase0/      CPU topology (P/E core discovery)
  scripts/       run_experiment.py  study2_*.py  revival_*.py  analyze_experiment.py ...
  tests/         ~500 tests
  config/  data/{results,events,profiles,models,traces}  docs/  manifests/""")
table([["Open first", "Why"],
       ["PROJECT_BACKBONE.md", "Whole story, all results, errors."],
       ["src/caosched/core/coordinator.py", "The heart: dispatch loop."],
       ["src/caosched/study2/policies.py + param_model.py", "The final policy and its model."],
       ["src/caosched/schedulers/simple.py", "B0 and B4 baselines."],
       ["src/caosched/study2/workload.py", "Experiment workloads."],
       ["docs/research_redesign/claims.json + STUDY2_REPORT.md", "Claims with numbers."],
       ["docs/revival/FINAL_STATUS.md, GPU_CPU_OPPORTUNITY_REPORT.md", "Revival + GPU findings."]], [7, 10])

# ---------------- 11 ----------------
h1("11. Code walkthrough: workflow stage -> class/function")
table([["Workflow step", "File", "Class / function", "Responsibility"],
       ["Build DAG", "study2/workload.py; apps/image_pipeline.py", "build_batch / build_iters / build_classes; build_image_pipeline", "Create Task nodes with dependencies, params, eligible pools"],
       ["Eligibility", "core/eligibility.py", "resolve_eligibility, supported_kinds", "Which pools can run each task; error if none"],
       ["Run entry", "core/coordinator.py", "Coordinator.run", "Main loop, health checks, timeouts, deadlock detection"],
       ["Ready check", "core/dag.py; coordinator", "DAG.initial_ready_tasks; Coordinator._mark_ready", "PENDING -> READY, push to ReadyQueue"],
       ["Ordering", "core/scheduler_base.py; study2/policies.py", "SchedulerPolicy.order_ready; PredictedRankGreedy.order_ready", "Rank ready tasks"],
       ["Estimate", "study2/param_model.py", "ParamModelEstimator.estimate, predict_group", "Predicted seconds per (task, pool)"],
       ["Worker selection", "schedulers/simple.py; study2/policies.py", "GreedyEligibleScheduler.select_worker; PredictedRankGreedy.select_worker", "Choose an idle eligible worker"],
       ["Dispatch", "core/coordinator.py", "_dispatch_ready_tasks, _bind, _submit", "Validate choice, DISPATCHED, send TaskMessage"],
       ["Execution", "core/worker_pool.py; apps/stages.py", "_worker_loop; run_stage", "Run the stage on pinned process / CUDA"],
       ["Remote path", "remote/proxy.py, node.py, link.py", "proxy_loop; serve; LinkConfig.shim_delay", "Emulated remote worker with link delay"],
       ["Completion", "core/coordinator.py", "_handle_completion", "DONE, log, unblock dependents, policy feedback"],
       ["Monitoring/logging", "core/event_log.py", "EventLogger", "JSONL events with timestamps"],
       ["Evaluation", "experiment/runner.py; analysis/*", "run_session; paired stats", "Blocks of conditions, bootstrap CI, Holm"],
       ["Live demo", "dashboard/live.py; server.py", "execute; LiveManager; Handler.do_POST", "Start a real run from the web UI"]], [2.6, 4.2, 5.2, 5])
h2("Key excerpt: the dispatch contract (core/coordinator.py)")
code("""ordered = self.scheduler.order_ready(list(ready), self.state)
for task_id in ordered:
    if late and not self.state.idle_workers(): return
    worker_id = self.scheduler.select_worker(task, self.state)
    if worker_id is None: continue                # task keeps waiting
    if late and not self.state.is_idle(worker_id):
        raise SchedulerContractError(...)          # late-binding policies may not queue
    self._bind(task_id, worker_id, ...)""")
p("Line by line: ask the policy for an order; stop if nobody is idle; ask for a worker; <code>None</code> means wait; the coordinator <i>enforces</i> the policy's promises (eligible pool, idle worker) and fails loudly otherwise; then bind and submit.")
h2("Key excerpt: B4 worker selection (schedulers/simple.py)")
code("""ok = set(eligible_workers(task, state, idle_only=True))
for pool in self._eligible_pools(task.workload):      # priority order, e.g. P, E, R
    idle = [w for w in state.idle_workers(pool) if w in ok]
    if idle: return idle[0]
return None""")
p("B4 never asks how long anything takes. B4 is a <i>comparison baseline</i> inspired by the eligible-worker dispatch idea of US patent 11,561,826 B1 (see docs/B4_PATENT_MAPPING.md); it is not an implementation of the patent.")
note("<b>AUDIT WIP (uncommitted, not final):</b> the audit session has edits in core/coordinator.py (+15 lines), remote/node.py, experiment/remote_adapter.py, analysis/stats_paired.py, scripts/calibrate_link.py, study2/adapter.py and new remote tests. Treat remote-worker and statistics details as subject to change.")

# ---------------- 12 ----------------
h1("12. Frontend and complete demonstration")
h2("12.1 What the dashboard is")
p("A local web app (<code>src/caosched/dashboard/</code>): a Python <code>ThreadingHTTPServer</code> (<code>server.py</code>, default port 8765, bound to 127.0.0.1) serving <code>static/index.html, app.js, app.css</code>. "
  "State-changing requests need a per-server token and matching Host/Origin headers.")
table([["Tab", "What it shows"],
       ["1 System overview", "Live CPU load per logical processor; scheduler and application status; remote worker R0; Raspberry Pi and NVIDIA T4 panels (planned hardware, not real)."],
       ["2 Application workflow", "Replay an accepted run or press <b>Run live on this laptop</b>; the 68-task, 8-stage DAG, worker timeline, run summary, real application output image, selected-task details."],
       ["3 Scheduling comparison", "Makespan by workload level; EFT_E1_rc vs B4 paired change; when transfer dominates (denoise); remote path vs local compute."],
       ["4 Hardware expansion", "Intended architecture, why physical hardware is needed, implementation status."],
       ["5 Montage &amp; GPU", "Montage runs and the GPU spike data."]], [4, 13])
p("<b>Dashboard policy choices are only two:</b> B4 (<code>B4_greedy_eligible_R</code>) and EFT (<code>EFT_E1_rc_R</code>), at workload level k in {1, 4, 16, 64}. The dashboard does <b>not</b> expose PRED_RANK_GREEDY, HEFT or PEFT; those run through the experiment scripts.")
h2("12.2 What happens on 'Run live'")
bl(["Browser POSTs <code>/api/live/start</code> with {policy, k} and the token.", "<code>LiveManager.start</code> launches <code>python -m caosched.dashboard.live</code> as a subprocess (so core pinning never affects the server).",
    "<code>live.execute</code>: checks free RAM (>= 1.0 GiB), builds the pipeline, starts <code>WorkerPool</code> (P, E, remote slot), runs <code>Coordinator.run</code>, verifies the final artifact against a single-process reference, writes <code>status.json</code>.",
    "Browser polls <code>/api/live</code> and <code>/api/run</code> and animates the timeline. Output goes to <code>data/dashboard_runs/</code>, never into experiment records."])
h2("12.3 Demonstration script")
code("""1) Keep the charger plugged in; close heavy apps (need >= 1-2 GB free RAM).
2) cd "D:\\cao project"
3) .venv\\Scripts\\python.exe -m caosched.dashboard        # default port 8765
4) Open http://127.0.0.1:8765   (do not use another host name)
5) Tab 1: show P/E core load = the heterogeneous machine.
6) Tab 2: pick replay of B4, press Play: explain DAG, timeline, which pool each task used.
7) Run live: policy B4, k=4 -> then EFT, k=4. Compare makespan and tasks per pool.
8) Tab 3: show the stored paired comparison (EFT vs B4) and say what it means.
9) Tab 4/5: say clearly: Raspberry Pi / T4 / real remote are NOT tested.""")
note("Step 3 is verified against dashboard/__main__.py: <code>python -m caosched.dashboard [--port 8765] [--open]</code>. The team's own 3-5 minute talk script is FACULTY_DEMO_SCRIPT.md in the project root (untracked file).")

# ---------------- 13 ----------------
h1("13. Experiments, metrics and verified results")
h2("13.1 Setup")
bl(["Hardware (PROJECT_BACKBONE.md): Windows 11 laptop, 6 P cores + 7 E cores + 1 coordinator core, 15.7 GB RAM, RTX 3050 6 GB laptop GPU, torch 2.11+cu128. Remote = loopback emulation.",
    "Method: conditions run in random-order <b>blocks</b>; one worker pool reused for all conditions (an early pilot was confounded by pool rebuilds); pre-registered protocol written before each run; paired log-ratio bootstrap CI; Holm correction; guards: scheduling cost < 25% of makespan, AC power, >= 0.8 GB RAM.",
    "Training vs held-out: model fit on coverage logs, policy chosen on pilot logs, reported on confirmatory logs."])
h2("13.2 Metrics (what is recorded)")
table([["Metric", "Definition", "Recorded?"],
       ["Makespan", "last finish - run start", "Yes (RunSummary)"],
       ["Scheduling time", "time in order_ready + select_worker", "Yes (scheduling_time_seconds); ~1% of makespan"],
       ["Init / setup time", "init_s and setup_s measured in Coordinator.run", "Yes"],
       ["Queue wait", "t_dispatched - t_ready per task", "Yes (queue_wait_seconds)"],
       ["% improvement", "(T_base - T_new) / T_base x 100", "Computed in analysis; positive = new faster"],
       ["Paired CI / p-value", "Bootstrap on per-block log ratios; Holm across claims", "Yes (analysis/stats_paired.py)"],
       ["MAE / RMSE / R2", "Section 7.4", "Prediction accuracy analysis"],
       ["Utilisation", "busy time / makespan per worker", "Derivable from event logs"]], [3.2, 8.2, 5.6])
p("<b>Fair static vs dynamic comparison:</b> static planners (HEFT, PEFT) spend time planning before the run; dynamic ones decide during it. A fair comparison counts both inside the same end-to-end timing boundary and gives both the same eligible resources. This end-to-end boundary work is part of the ongoing audit: <b>PENDING</b>.")
h2("13.3 Verified results (from PROJECT_BACKBONE.md; raw logs under data/)")
img("results.png", 14)
table([["Experiment", "Result", "Status"],
       ["Montage (stage 5)", "Prediction-aware EFT 1.6% slower than static P-only (285 s); HEFT +1.5%, PEFT +1.7%", "VERIFIED null"],
       ["Hidden-cost, 6P+7E (30 blocks)", "PRED 20.4% faster than B4, 21.9% than P-only, 42.9% than table predictor; 1.6% behind hand rule that knows the parameter", "VERIFIED"],
       ["Hidden-cost, 2P+7E retrained (20 blocks)", "21.1% faster than B4, 45.1% than P-only, 36.6% than table predictor; level with hand rule (0.4%)", "VERIFIED"],
       ["Uniform batch no-harm (30 blocks)", "Level with B4 (+0.45%), 26.1% faster than P-only", "VERIFIED"],
       ["Two-factor (confirmatory 41 blocks)", "Size-only rule 17.4% slower, P-only 17.1% slower (supported). B4 0.9% slower, CI -0.9% to +2.8% (not significant). Equivalence to hand formulas not resolved", "VERIFIED"],
       ["Revival oracle gate (13 blocks)", "Headroom of best simple rule over oracle -1.24%; required >= 5% -> FAILED. Live-state idea not supported", "VERIFIED negative"],
       ["Revival no-harm (31 blocks, CUDA worker)", "v1 +2.2-2.6% slower than B4 (cause: snapshot per completion); v2 +0.7-1.0% after fix", "VERIFIED"],
       ["GPU/CPU profiling (Phase 1)", "Opportunity not established (G1 fails at 512 px, G2 fails, G3 only unattainable bound)", "VERIFIED + ESTIMATE"],
       ["Overnight check 2026-10-27 (quoted from FACULTY_DEMO_SCRIPT.md; raw files listed in RESULTS_TABLE.csv; not re-checked here)", "20 never-used chain orders: learned policy 19.3% / 20.5% faster than B4, faster in all 20 (exploratory). Dose-response: ~1-3% gain when heavy chains cost 7-20x a light one, ~20% at 60x. HEFT with the same learned model -18.1% vs ours -19.0% (indistinguishable); PEFT only -2.6%. Scheduling cost 3-5% of the run. Single GPU stages up to ~15x faster at large tiles, no workflow-level GPU gain shown.", "VERIFIED by project records (secondary)"],
       ["Hardware: Raspberry Pi / real remote", "Not tested", "NOT EVALUATED"],
       ["Final audit experiments (CPU-only vs CPU+GPU, static vs dynamic, E2E overhead, significance)", "Calibration run in data/results/final_20261101 failed to start (design file not found) and was being retried; no complete final result exists yet", "<b>PENDING</b>"]], [4.6, 9.2, 3.2])
note("<b>Do not say:</b> 'our scheduler is 20% better than everything'. The 19-22% gains over B4 came from workloads where hidden task parameters make ordering decisive (CPU-only P/E pools), not from CPU/GPU heterogeneity. Test status in the audit run: 515 passed, 1 failed (a RAM-guard test that refuses to run with <2 GB free RAM), 1 skipped - <b>AUDIT WIP</b>, final count pending.")

# ---------------- 14 ----------------
h1("14. Base papers and related work")
p("The code and docs name these sources. I did not do new literature research; check the project's own docs/revival/RELATED_WORK.md and PAPER_OUTLINE.md before quoting details.")
table([["Source", "What it is / what we take", "Difference in our work"],
       ["Topcuoglu, Hariri, Wu. Performance-effective and low-complexity task scheduling for heterogeneous computing. IEEE TPDS 13(3), 2002", "HEFT: upward rank + earliest finish time. We implement it (schedulers/heft.py) as a static baseline and reuse upward rank for PRED.", "We rank dynamically from <i>learned</i> predictions and bind late to idle workers."],
       ["Arabnejad, Barbosa. List scheduling algorithm for heterogeneous systems by an optimistic cost table. IEEE TPDS 25(3), 2014", "PEFT: optimistic cost table (schedulers/peft.py).", "Static plan; ~20% behind in Study 2, but only 2.6% gain over B4 in the overnight check (different experiments)."],
       ["US patent 11,561,826 B1 (Xilinx)", "Eligible-worker heterogeneous dispatch concept; basis for the B4 baseline (docs/B4_PATENT_MAPPING.md).", "B4 is a baseline only, not the patent's implementation."],
       ["Lotaru (arXiv 2309.06918, FGCS 2024); Lu and Reda (listed in RELATED_WORK.md); Ilyushkin and Epema CCGrid 2018", "Runtime prediction / workflow scheduling related work recorded by the project.", "No novelty claimed over these (docs/revival/RELATED_WORK.md)."]], [6, 6.2, 4.8])
table([["Aspect", "Base HEFT/PEFT", "Our implementation"],
       ["Timing of decisions", "Static, before run", "Dynamic (PRED) plus static baselines"],
       ["Runtime knowledge", "Assumed cost matrix", "Learned per-(stage, pool) ridge model"],
       ["Resources", "Abstract processors", "Real P/E pools, CUDA worker, emulated remote"],
       ["Evaluation", "Simulation, schedule length", "Real runs, paired blocks, bootstrap CI, Holm"],
       ["Performance evidence", "Superior in their simulations", "Beats naive/static; ties best simple rules; GPU/live-state not shown"]], [4, 5.5, 7.5])
p("NVIDIA already provides CUDA streams, graphs and libraries for work <i>inside</i> a GPU program. CAO operates one level higher: placing whole workflow tasks across heterogeneous workers. See NVIDIA_VS_CAO_AUDIT.md in the project root for the team's detailed comparison (not re-verified here).")

# ---------------- 15 ----------------
h1("15. Limitations, future work and faculty questions")
h2("15.1 Limitations (be upfront)")
bl(["Gains over blind greedy B4 appear only when cost is hidden in task parameters; none on uniform, two-factor or Montage workloads.",
    "Never beat the best hand-written rule that knows the cost driver (level or slightly behind).",
    "GPU: single-task speedups do not give workflow speedups; few real dispatch choices; NVML not installed so no per-decision GPU telemetry.",
    "Remote worker is emulated on one laptop; Raspberry Pi / NVIDIA T4 hardware not tested.",
    "Estimator poor on the cheapest tasks; unseen (stage, pool) is an error; retraining needed per machine.",
    "Limited by free RAM (WSL VM and background services); few repetitions in the GPU profile (8).",
    "Final audit (E2E timing, fair static baselines, CPU+GPU, significance) is <b>PENDING</b>."])
h2("15.2 Future work")
bl(["New workload with real choices (fewer ready tasks than workers, GPU-dominated work), screened by simulation first.", "Real Raspberry Pi / remote validation (one-command retraining exists).", "Better light-task prediction (power-law form exists).", "Finish audit and update the results chapter."])
h2("15.3 Likely faculty questions and answers")
qa = [
 ("What problem do you solve?", "Choosing order and worker for dependent tasks on a machine with unequal workers, to minimise total finish time (makespan)."),
 ("Why a DAG?", "Real workflows have dependencies; a DAG captures them and gives critical path and ready-task logic."),
 ("Why ML?", "Fixed tables cannot capture hidden parameters like repeat counts. A small regression predicts per-pool time cheaply (microseconds)."),
 ("Which ML model?", "Per-(stage,pool) ridge regression on task parameters and size, plus pairwise products; a log-power variant for cheap tasks. Not a neural network."),
 ("How is PRED different from B4?", "B4: FIFO and first idle worker, no estimates. PRED: orders by predicted remaining chain, picks the idle worker with smallest predicted time."),
 ("Why not only HEFT?", "HEFT plans statically and binds early; ~3% behind the hand rule in Study 2. In the overnight check HEFT with our learned model matched PRED (-18.1% vs -19.0%), so the real contribution is the learned model, not only the policy. Plans cannot correct errors at runtime."),
 ("How is worker selection done?", "Among idle eligible workers, the minimum of estimator.estimate(task, pool); eligibility comes from the task's allowed pools."),
 ("What is late binding and why does it matter?", "Binding a task only to an idle worker; keeps workers busy and avoids queueing behind slow workers (early binding cost ~1.7% on Montage)."),
 ("Why use a GPU if transfer is costly?", "Large tasks gain (edges 1024 px: 45 ms to 14.8 ms). Small ones lose. The scheduler/estimator must include copy and I/O cost."),
 ("What happens when the GPU is busy?", "Measured: GPU denoise gets 2.2-3.1x slower and the best device flips to P. The live-state policy that reacts to this showed no headroom."),
 ("What does NVIDIA already provide?", "Streams, graphs and libraries inside one GPU program. We schedule whole workflow tasks across CPU pools, GPU and remote workers."),
 ("How do you protect against a bad prediction?", "Late binding bounds the damage (no queueing); revival policy falls back to B4 with logged reasons; scheduling cost guard 25%; unseen groups raise an error."),
 ("How do you compare static and dynamic fairly?", "Same workload, same eligible resources, ONE ridge cost model on both sides, and the end-to-end makespan from the start of run() to the last completion, so the planning time of a static plan is counted. Done in the final benchmark (Section 16): PRED is 5.2% faster than static HEFT on the CPU and 12.2% with the strict GPU set."),
 ("Why end-to-end makespan?", "Users care about total time including setup and scheduling, not just kernel time."),
 ("Why bootstrap CI and Holm?", "Runs are noisy; paired blocks remove drift; bootstrap gives intervals; Holm controls false positives across many claims."),
 ("What is genuinely new?", "Be modest: no broad novelty claimed. Defensible: a generic, retrainable parameter-aware runtime model with rank + late-binding policy, evaluated with pre-registered negative and positive results on a real heterogeneous runtime."),
 ("What does the project prove?", "Prediction-aware scheduling beats static and naive policies by 17-45% where costs vary; it identifies when it does not help."),
 ("What does it not prove?", "Superiority over B4 in general, GPU workflow speedup, live-state benefit, real remote or Raspberry Pi benefit."),
 ("Limits of remote emulation?", "One machine, loopback; delay is a formula (latency + per-message + bytes/bandwidth). Real networks have jitter, loss and different CPUs."),
 ("What is makespan vs speedup?", "Makespan = total time. Speedup = T_base / T_new. 20% faster means T_new = 0.8 T_base."),
 ("Why did Montage fail?", "One dominant serial path and every task prefers P cores, so placement choices barely matter."),
 ("Is estimator accuracy the same as scheduling gain?", "No. Accurate predictions help only if there is headroom for a different decision."),
 ("What is still pending?", "Nothing in the final audit: it is complete (Section 16). Open by design: Raspberry Pi and real-network results, a better GPU cost model, a second workload family, the GitHub push and the IPR decision."),
]
for i, (q, a) in enumerate(qa, 1):
    S.append(KeepTogether([Paragraph(f"<b>Q{i}. {q}</b>", B), Paragraph(a, BL)]))
h2("15.4 Presentation order (10 minutes)")
p("Problem and analogy -> heterogeneous machine -> DAG and architecture -> workflow loop -> B4 vs PRED -> ML model -> live dashboard demo -> verified results (including the honest nulls) -> limitations -> conclusion: 'predictions help when cost is hidden; we know where it does not.'")
note("<b>Updated 3 November 2026:</b> the final audit is finished; Section 16 holds the final static-versus-dynamic results, the CPU/GPU conclusion, the new policies, the dashboards v2 and v3 and the test count. Earlier sections are unchanged and describe the earlier study; where they differ, Section 16 takes precedence.")

h1("16. Final static-versus-dynamic benchmark and dashboards v2 and v3 (update, 3 November 2026)")
note("<b>Read this first.</b> Sections 1 to 15 were written before the final benchmark. This section is the current state and takes precedence. All numbers below are read from the stored analysis files of data/results/final_20261101 (generated into CAO_FINAL_EXPERIMENT_REPORT.md).")
h2("16.1 The question and the answer in plain words")
p("Question: does a dynamic scheduler (decides while the workflow runs) finish sooner than a static plan (decided before the run) when both use the same cost model, once planning and start-up time are counted? Answer on the primary workload (16 heavy chains of 64, 24 blocks): <b>yes</b>. The dynamic policy PRED_RANK_GREEDY is 17.8% faster than blind B4 on the CPU, 21.2% with the strict GPU set, and 5.2% (CPU) and 12.2% (strict GPU) faster than the static HEFT plan. A simple rule that sorts the queue by the cost parameter (B4_param_first) is within 1% of PRED, so most of the gain comes from using the task parameter, not from the learned rank.")
h2("16.2 Policies added or changed")
table([["Policy", "Kind", "What it does"],
       ["B4", "dynamic", "first idle eligible worker, no estimate (the base idea)"],
       ["B4_param_first", "dynamic", "B4 with the queue sorted by the cost parameter (hand rule)"],
       ["PRED_RANK_GREEDY", "dynamic", "predicted upward rank order; idle worker with least predicted kernel time"],
       ["PRED_RANK_GREEDY_E2E", "dynamic", "as PRED, minimising predicted occupancy: transfer + kernel + set-up + inter-process time"],
       ["HEFT_param_model, PEFT_param_model", "static", "plan before the run from the same model"],
       ["HEFT_E2E", "static", "HEFT with the end-to-end terms in the costs"],
       ["HEFT_oracle", "static, reference", "plan from class-median costs; reference only, not a bound"]], [4.2, 2.3, 10.5])
p("Where in code: src/caosched/final/policies.py (policies), final/gpu_region.py (GPU eligibility from verified spike rows), final/adapter.py (run adapter), scripts/final_*.py (calibration, evaluation, analysis, report), tests/test_final_*.py. Timing rule: docs/final/AMENDMENT_F1_timing.md (end-to-end makespan = start of run() to last completion; init and policy set-up logged separately).")
h2("16.3 CPU only versus CPU + GPU (the three configurations)")
p("<b>cpu</b>: P and E cores only. <b>gpu</b> (strict): the CUDA worker may run only stages whose speed-up was verified on the original spike record (edges 7.68x, features 2.88x, denoise at 8 iterations 1.16x; denoise at 1 iteration dropped). <b>ext</b>: strict plus denoise at the iteration counts verified on the extended record (6, 15, 40, 120 iterations; 2 dropped). None is GPU-only. Static versus dynamic is independent of the hardware set: it is about when the decision is made.")
table([["Policy", "CPU only", "Strict GPU", "Extended GPU"]] + [['B4 (blind, dynamic)', '4.010', '4.075', '4.123'], ['B4 param-first (rule, dynamic)', '3.310', '3.218', '3.069'], ['PRED (dynamic)', '3.297', '3.213', '3.050'], ['PRED-E2E (dynamic)', '3.318', '3.212', '3.033'], ['HEFT (static)', '3.478', '3.660', '3.114'], ['HEFT-E2E (static)', '3.499', '3.512', '3.173'], ['PEFT (static)', '4.093', '4.050', '3.689']], [6.0, 3.3, 3.3, 3.4])
p("Makespan in seconds, geometric mean over 24 blocks. Effect of the GPU for PRED: strict set 2.6% faster than CPU only, extended set 7.5%. For blind B4 the GPU does not help (+1.6%, inconclusive). The GPU cost model has 23% to 31% median error (CPU stages 4% to 11%), so GPU placement is the weakest part.")
h2("16.4 The ten pre-stated contrasts (Holm-adjusted)")
table([["Id", "Contrast", "Effect % [95% CI]", "Holm p", "Result"]] + [list(r) for r in [['C1', 'PRED vs B4 (CPU)', '−17.8 [−18.8, −16.7]', '0.001', 'faster'], ['C2', 'PRED-E2E vs PRED (CPU)', '+0.6 [+0.1, +1.3]', '0.141', 'equivalent (within ±2%)'], ['C3', 'PRED vs HEFT (CPU)', '−5.2 [−5.9, −4.6]', '0.001', 'faster'], ['C4', 'PRED-E2E vs HEFT-E2E (CPU)', '−5.2 [−5.9, −4.5]', '0.001', 'faster'], ['C5', 'PRED vs HEFT (strict GPU)', '−12.2 [−13.4, −11.1]', '0.001', 'faster'], ['C6', 'PRED-E2E vs HEFT-E2E (strict GPU)', '−8.5 [−9.7, −7.6]', '0.001', 'faster'], ['C7', 'PRED-E2E vs PRED (strict GPU)', '0.0 [−0.7, +0.5]', '0.960', 'equivalent (within ±2%)'], ['C8', 'PRED vs B4 (strict GPU)', '−21.2 [−22.6, −19.7]', '0.001', 'faster'], ['C9', 'PRED, strict GPU vs CPU', '−2.6 [−3.3, −1.7]', '0.001', 'faster'], ['C10', 'B4, strict GPU vs CPU', '+1.6 [+0.2, +3.0]', '0.141', 'inconclusive']]], [1.1, 6.0, 4.3, 1.6, 4.0])
h2("16.5 What the results do not show")
bl(["A hand rule that knows the cost parameter is within 1% of PRED in every configuration.",
    "With no spread in task cost (uniform workload) all policies tie; with the smallest cost ratio and the strict GPU set PRED is 1.1% slower than B4.",
    "End-to-end cost terms change nothing (C2, C7 equivalent within 2%); a hybrid B4/PRED selector would gain at most 1.1% (maximum over 17 cells), so none was built.",
    "An earlier session found HEFT level with PRED (+1.10%); the final session finds PRED about 5% faster; the difference was not isolated and both are reported.",
    "One machine, one workload family, one CUDA worker; the remote worker was not rerun with the final policies; no Raspberry Pi result exists."])
h2("16.6 Dashboards (new files; the original dashboard is unchanged)")
table([["Version", "Command (project root)", "What is new"],
       ["original", ".\\.venv\\Scripts\\python.exe -m caosched.dashboard --port 8765 --open", "unchanged; CPU load bars stay 0 after the first request (old psutil baseline bug)"],
       ["v2", ".\\.venv\\Scripts\\python.exe -m caosched.dashboard_v2 --port 8766 --events-dir data\\results\\final_20261101\\eval\\sessions --open", "GPU CONNECTED with live load/memory/temperature/power, Pi card NOT CONNECTED, final results with hover tooltips on screen 3, CPU load fixed"],
       ["v3", ".\\.venv\\Scripts\\python.exe -m caosched.dashboard_v3 --port 8770 --events-dir data\\results\\final_20261101\\eval\\sessions --open", "v2 plus screen 6: run one live block of the final benchmark with any policy on CPU or CPU+GPU (1 to 2 minutes, needs 2.4 GB free RAM)"]], [1.8, 8.2, 7.0])
p("A live run on screen 6 is a demonstration of one block, not an experiment result: its makespan (about 4 s) is not comparable with the benchmark (about 3 s); the cause was not isolated (it includes pool and CUDA start-up).")
h2("16.7 Tests and reproducibility")
p("521 tests: 520 pass; one (tests/test_profile_montage.py::test_profile_format_csv_fit_and_cleanup) refuses to start when free RAM is below its own 2 GB gate and failed at 1.44 GB free; the test passed in the earlier full run. Pipeline: scripts/final_stage1.ps1, final_stage2.ps1, final_analyze.py, final_results_table.py, final_cross_workload.py, final_hybrid_check.py, final_build_report.py. Submission package: SUBMISSION_FINAL.")


def foot(c, d):
    c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(colors.grey)
    c.drawString(2 * cm, 1.1 * cm, "CAO project explanation - updated 3 Nov 2026 (final benchmark in Section 16)"); c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Page {d.page}"); c.restoreState()


doc = SimpleDocTemplate(r"D:\cao project\SUBMISSION_FINAL\CAO_Project_Complete_Explanation_UPDATED.pdf", pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                        title="CAO Project Complete Explanation", author="Generated study guide")
doc.build(S, onFirstPage=foot, onLaterPages=foot)
print("built")
