"""Final IEEE two-column paper (Lab 10 draft, at least 14 pages). Numbers come from the stored result files through final_data.py."""
import json
import re
import sys
sys.path.insert(0, r"D:\cao project\SUBMISSION_FINAL\_build")
from ieee_docx2 import IEEEDoc, export_pdf
import final_data as fd

FIG = r"D:\cao project\publications\figures"
FF = r"D:\cao project\SUBMISSION_FINAL\_fig"
OUT = r"D:\cao project\SUBMISSION_FINAL\_draft"
FIN = fd.ROOT / "data" / "results" / "final_20261101"


def holdout_rows():
    rows = []
    for ln in open(FIN / "models" / "train.stdout.txt", encoding="utf-8"):
        m = re.match(r"holdout (\S+) (\{.*\})", ln.strip())
        if m:
            d = json.loads(m.group(2).replace("'", '"'))
            rows.append([m.group(1).replace("img_", "").replace("|", " on "), str(d["n"]), f"{d['mae_s'] * 1000:.2f}", f"{d['median_ape'] * 100:.1f}"])
    return sorted(rows)


TITLE = "Static Plan or Dynamic Dispatch? A Measured Comparison of Scheduling DAG Workloads on a Hybrid CPU/GPU Laptop with One Cost Model and End-to-End Timing"


def build(anonymous: bool, name: str):
    d = IEEEDoc(
        TITLE,
        ["Lakshay S", "Arkkadu Bharath Reddy"],
        ["Reg. Nos. 26MAI0064, 26MAI0058", "Guide: Dr. Yokesh Babu S, Associate Professor Grade 1. [Institution, department and e-mail to be filled by the authors]"],
        "Schedulers for heterogeneous machines are mostly evaluated in simulation, rarely report their own cost, and are seldom compared fairly with the oldest alternative: a *static* plan computed before the run. "
        "We compare static plans (HEFT, PEFT and HEFT with end-to-end cost terms) with *dynamic* dispatch (blind greedy dispatch, a parameter-aware rule, and a predicted-rank dispatcher that binds a task only to an idle worker) on real executions of an image-processing task graph "
        "on a laptop with six performance cores, seven efficiency cores and one CUDA worker (RTX 3050). Every policy uses the same ridge cost model; GPU eligibility is taken per task from recorded speed-up measurements; the primary metric is the end-to-end makespan, from the start of the run to the last completion, so planning and start-up time are counted. "
        "On the primary workload (24 included blocks, ten Holm-adjusted contrasts) the dynamic dispatcher is 17.8% [16.7, 18.8] faster than blind dispatch on the CPU and 21.2% faster with a strict GPU set, and it is 5.2% [4.6, 5.9] (CPU) and 12.2% [11.1, 13.4] (strict GPU set) faster than the static HEFT plan built from the same model. "
        "Using the GPU only where a speed-up was measured helps the dispatcher by 2.6% to 7.5% and does not help blind dispatch. The claim has limits: a hand rule that knows the cost-relevant task parameter is within 1% of the dispatcher in every configuration; "
        "the policies tie when task cost does not vary; end-to-end cost terms change nothing (equivalent within \u00b12%); a hybrid selector would gain at most 1.1%; the GPU cost estimate has a median error of 23% to 31%; and an earlier session found HEFT level with the dispatcher. "
        "We release the protocol, the data and 521 tests.",
        "task scheduling, static versus dynamic scheduling, HEFT, runtime prediction, CPU/GPU, hybrid cores, empirical evaluation, reproducibility",
        anonymous=anonymous,
    )
    # ------------------------------------------------------------------ I
    d.h1("Introduction")
    d.para("Modern machines combine core types and accelerators, and applications are task graphs whose edges are data dependencies. A scheduler decides in which *order* ready tasks are served and on which *worker* each one runs. "
           "Two designs are available. A *static* scheduler such as HEFT or PEFT ({{heft,peft}}) computes a complete plan before the run from a cost estimate for every task on every worker. A *dynamic* scheduler decides when a worker becomes idle or a task becomes ready, "
           "as runtime systems such as StarPU ({{starpu}}) and most learned schedulers ({{lachesis,adprl,tan25}}) do. The static plan pays a planning cost once and cannot react; the dynamic scheduler can react but pays a decision cost throughout and may bind work with less information.")
    d.para("Published comparisons rarely isolate this choice. Reported improvements of 11% to 27% ({{lachesis,metarl,iov,tan25}}) come from simulators; none of the 12 papers we examined reports a confidence interval; measured decision time appears in few; and, to our knowledge, none gives the static and the dynamic scheduler the *same* cost model and measures both end to end, including the time a plan takes to compute. "
           "A simple question follows: **does dynamic dispatch finish a workflow sooner than a static plan built from the same model, on a real hybrid CPU+GPU machine, once planning, start-up and scheduling time are counted, and under which conditions?**")
    d.para("We answer it with an instrumented runtime on a laptop and make five contributions. (1) A reproducible end-to-end timing convention and benchmark that gives static and dynamic policies one cost model. (2) A fair set of static baselines (HEFT, PEFT, HEFT with end-to-end terms, an oracle reference) and a dynamic dispatcher with and without end-to-end cost terms. "
           "(3) Per-task GPU eligibility derived from recorded speed-up measurements, so that the GPU is used only where it was shown to help. (4) A pre-stated confirmatory family of ten contrasts with Holm correction, six workloads, and a calibration/hold-out/evaluation split. "
           "(5) An honest account of the limits: a parameter-aware rule that captures almost all of the gain, ties where task cost does not vary, a GPU model with large error, and a hybrid selector that is not justified. We claim neither a new learning algorithm nor superiority over learned schedulers, which we did not run.")
    # ------------------------------------------------------------------ II
    d.h1("Background and Related Work")
    d.para("**Static list scheduling.** HEFT ranks tasks by upward rank and assigns each, in rank order, to the processor with the earliest finish time, inserting it into idle gaps; PEFT replaces the rank by an optimistic cost table ({{heft,peft}}). "
           "Both need a cost matrix and are usually evaluated in simulation. **Learned DAG scheduling.** LACHESIS ({{lachesis}}) combines a GNN task selector with a duplication-based placement rule; later work uses GCN or Transformer encoders with PPO ({{song23,tan25}}), or DQN, actor-critic and meta-RL formulations for edge offloading "
           "({{dddqn,wang22,gong23,sata,cao24,nieto,adprl,metarl,iov}}). Only {{rodriguez}} (CPU+FPGA) and {{adprl}} (a three-board Jetson testbed) use physical devices.")
    d.para("**Prediction-driven scheduling.** {{lotaru}} predicts task runtimes and drives HEFT in simulation; {{ilyushkin}} report that, under high utilisation, order matters more than estimate accuracy; {{lureda}} place AI tools with an LLM agent on real CPU/GPU hardware against HEFT and StarPU on small DAGs; StarPU ({{starpu}}) has long used history-based performance models. "
           "**Patents.** The base patent ({{p_xilinx}}) claims task graphs, per-kernel queues and thread-based dispatch without prediction; IBM\u2019s grants ({{p_ibm1,p_ibm2}}) disclose a learning agent that ranks DAG tasks and schedules with execution estimates, Samsung\u2019s ({{p_samsung}}) predicts durations on heterogeneous cores, and Intel\u2019s ({{p_intel}}) profiles CPU/GPU throughput. "
           "**Products.** Operating systems place threads using hardware feedback or energy models ({{intel_td,linux_eas,ms_qos}}); cluster products schedule against declared resources ({{k8s,aws_batch,slurm,ray}}); none of the cited product pages describes execution-time prediction in the scheduler.")
    d.nextlabel = "pat"
    d.table("Patents closest to the project (as summarised from Google Patents; legal status is an assumption, not an opinion)",
            ["Patent", "Discloses", "Prediction"],
            [["{{p_xilinx}} Xilinx, US 11,561,826 B1", "task graph; kernel objects tied to compute circuits; per-kernel task queues; in-degree gating; performance-based thread adjustment (base work)", "no"],
             ["{{p_ibm1}} IBM, US 11,740,933 B2", "learning agent assigns a rank to DAG tasks; tasks run in rank order on a heterogeneous SoC", "learned rank"],
             ["{{p_ibm2}} IBM, US 11,966,776 B2", "learning agent schedules DAGs with priorities and task execution estimates, may drop DAGs", "yes"],
             ["{{p_intel}} Intel, US 10,186,007 B2", "CPU+GPU: profiling threads time part of the work on each device and split the rest", "online profiling"],
             ["{{p_samsung}} Samsung, US 10,162,671 B2", "predicts a task\u2019s duration when core state changes, from solo-versus-concurrent ratios", "yes"]],
            [1.0, 2.0, 0.5], size=6.5)
    d.para("None of the patents summarised describes an empirical method for deciding when prediction is worth its cost; rank-ordered dispatch with a learning agent is disclosed by {{p_ibm1}}, so the contribution of this paper is the measured comparison, not the idea of ranking. A professional prior-art search is needed before any filing.")
    d.nextlabel = "prod"
    d.table("Products that decide where work runs (only what the cited documentation pages state)",
            ["Product", "Scope", "Heterogeneity handled", "Prediction / learning"],
            [["Intel Thread Director {{intel_td}}", "hybrid client CPU", "P versus E cores; hardware tracks instruction mix per thread and informs the OS", "hardware classification"],
             ["Windows QoS {{ms_qos}}", "OS scheduler", "QoS levels may restrict threads to a subset of processors", "heuristics and developer hints"],
             ["Linux EAS {{linux_eas}}", "kernel", "asymmetric CPU capacity; energy model", "none; energy-model lookup"],
             ["Kubernetes {{k8s}}", "cluster", "extended resources through filter and score plugins", "none stated"],
             ["AWS Batch {{aws_batch}}", "cloud batch", "EC2, Fargate, ECS and EKS compute", "none stated"],
             ["Slurm {{slurm}}", "HPC batch", "GPUs, MPS and MIG devices as generic resources", "none stated"],
             ["Ray {{ray}}", "distributed Python", "declared CPU and GPU resources; placement groups", "none stated"],
             ["StarPU {{starpu}}", "task runtime", "CPU and GPU tasks, data transfers", "performance models"]],
            [0.9, 0.55, 1.3, 0.7], size=6.5)
    d.para("The products split the work: operating-system features place threads, cluster products place containers or jobs against declared requests, and only workflow runtimes such as StarPU understand task graphs. No product page we read combines application-level DAG knowledge, learned per-resource runtime estimates and published decision-overhead measurements on a laptop-class hybrid CPU/GPU system.")
    d.nextlabel = "rw"
    d.table("This work compared with the closest published systems",
            ["System", "Evaluation", "Hardware", "Overhead reported", "Intervals", "Informed baseline"],
            [["{{lachesis}}", "simulation", "simulated cluster", "inference time", "no", "no"], ["{{adprl}}", "trace simulation + testbed", "3 Jetson boards", "no", "no", "no"],
             ["{{rodriguez}}", "real", "Zynq CPU+FPGA", "yes", "no", "no"], ["{{lotaru}}", "simulation", "simulated heterogeneous cluster", "prediction error", "median errors", "HEFT with true runtimes"],
             ["{{starpu}}", "real", "CPU+GPU nodes", "history models", "not assessed", "no"], ["{{lureda}}", "real, small DAGs", "CPU/GPU", "runtime monitor", "not stated", "HEFT, StarPU"],
             ["This work", "real executions", "P/E cores, RTX 3050", "end-to-end and per-dispatch", "paired bootstrap, Holm", "yes (hand rule, static plans)"]],
            [0.5, 0.75, 0.75, 0.65, 0.6, 0.7], size=6.5)
    d.para("**Gap.** The literature leaves open a like-for-like comparison of static and dynamic scheduling with one cost model, real execution, end-to-end timing and interval statistics, including a baseline that merely knows which tasks are expensive. This paper supplies that comparison for one workload family on one machine.")
    # ------------------------------------------------------------------ III
    d.h1("System and Method")
    d.h2("Runtime")
    d.para("The coordinator converts a workflow into a DAG, keeps a ready queue and dispatches tasks to worker processes, each pinned to one logical processor, with a reserved core for the coordinator (@fig:arch). Tasks become ready when all parents completed (the in-degree gating of the base patent {{p_xilinx}}). "
           "The workers are six P-core processes, seven E-core processes and one CUDA worker G, which runs GPU variants of three image stages. Every policy honours per-task eligible pools through one helper and a violation raises an error. Every output is compared with a CPU reference, "
           "and the event log records each dispatch with its decision time, so that planned and actual times can be compared.")
    d.nextlabel = "arch"
    d.figure(FF + r"\fig_final_architecture.png", "Framework of the final study: one cost model and one GPU-eligibility table feed both the static planners and the dynamic dispatchers; coordinator, event log and worker pools are shared.", 3.4)
    d.para("Failed or timed-out tasks get a terminal status and their dependents are marked not-run; every run starts from a clean directory; failed runs are kept and flagged. External-command tasks (the Montage jobs of the earlier study) run as processes without a shell, with timeouts, process-tree kill and hashing of inputs and outputs. "
           "A run produces an event log (one JSON line per event) and a manifest; the manifest ties the run to its design, code and environment (@tab:log).")
    d.nextlabel = "log"
    d.table("Event log and run manifest content",
            ["Record", "Fields (selection)"],
            [["task_ready, task_dispatched", "task id, worker, pool, queue wait, worker load, decision time, decision record"],
             ["task_submitted, task_completed", "kernel time, start and end timestamps, transfer time, bytes moved, output size and SHA-256"],
             ["worker_ready, run_started, run_finished", "pid, requested and actual affinity, capabilities; makespan, status, tasks per pool"],
             ["run manifest", "condition, policy, seed, instance, warm-up flag, status, output verdict and hashes, event-log SHA-256, git commit and dirty flag, source and design SHA-256"],
             ["session record", "design hash, machine id, environment hash, blocks completed, preflight log, final status"]],
            [1.2, 2.2], size=7)
    d.h2("Cost model")
    d.para("The model fits, per (stage, pool), a ridge regression on the numeric task parameters and the size that vary in the logs and on their pairwise products; it names no stage or parameter, refuses an unseen stage or pool, and is refitted by one command. "
           "An *end-to-end* term adds the artifact set-up time and the inter-process overhead per pool. The CUDA stage time measured by the runtime already contains the host-to-device copy, the kernel and the device-to-host copy (checked in the stage code), so the end-to-end variant never adds them again; for local pools the modelled transfer is zero. "
           "The model and the end-to-end terms were fitted on calibration sessions and checked on hold-out sessions that were never used for fitting (@tab:hold).")
    d.nextlabel = "hold"
    d.table("Cost-model error on hold-out tasks (never used for fitting); E = efficiency core, P = performance core, G = CUDA worker",
            ["Stage on pool", "n", "MAE (ms)", "Median abs. error (%)"], holdout_rows(), [1.3, 0.5, 0.7, 1.0], size=7)
    d.para("CPU stages are predicted within 4% to 11% median error, GPU stages within 23% to 31%. The GPU estimate is the weakest part of the model, and it limits what model-based GPU placement can do.")
    d.para("**Features and fitting protocol.** Features are decision-time safe: task parameters are known when the task becomes ready. Offline features are reconstructed from the logged decision context and a parity test enforces equality with the online features, so that no feature uses information from the future. "
           "Inference is a dot product of a few numbers. Over the project more elaborate predictors were tried (@tab:est); in the earlier phases none of them improved scheduling over the ridge model enough to justify its cost, so the final study uses the simple model.")
    d.nextlabel = "est"
    d.table("Estimators tried during the project (role in the final study)",
            ["Estimator", "Description", "Role"],
            [["E0", "constant time per task type and pool", "earlier phases"], ["E1", "solo-profile table keyed by stage and size", "earlier phases"],
             ["E2", "analytic size model", "earlier phases"], ["E3", "moving history of observed times", "earlier phases"],
             ["E1+rc", "E1 recalibrated online from completed tasks", "earlier phases"], ["E4 ridge", "ridge on task parameters and occupancy context", "earlier phases"],
             ["CatBoost, MLP", "gradient-boosted trees and a small neural network on the same features", "evaluated, not adopted"],
             ["ParamModel", "ridge per (stage, pool) on varying parameters, size and pairwise products", "**used in the final study**"],
             ["E5 oracle", "offline replay of observed times", "reference only"]],
            [0.8, 2.0, 0.8], size=6.5)
    d.nextlabel = "err"
    d.figure(FF + r"\fig_final_model_error.png", "Median absolute error of the cost model on hold-out tasks, by stage and pool.", 3.4)
    d.h2("Static and dynamic policies")
    d.nextlabel = "pol"
    d.table("Policies compared (all use the same eligibility rules and, where they predict, the same cost model)",
            ["Policy", "Kind", "Rule"],
            [["B4", "dynamic", "first idle eligible worker for each ready task in FIFO order, priority P then E; no estimate (the mapping of the base patent\u2019s dispatch idea {{p_xilinx}})"],
             ["B4_param_first", "dynamic", "B4 with the ready queue sorted by the cost-relevant task parameter (a hand rule: human knowledge)"],
             ["PRED_RANK_GREEDY (PRED)", "dynamic", "order ready tasks by predicted upward rank; bind only to an *idle* eligible worker with the least predicted kernel time"],
             ["PRED_RANK_GREEDY_E2E (PRED-E2E)", "dynamic", "as PRED, choosing the idle worker with the least predicted occupancy = transfer + kernel + set-up + inter-process time"],
             ["HEFT_param_model", "static", "HEFT plan from the model, computed before the run; fixed worker per task"],
             ["PEFT_param_model", "static", "PEFT plan (optimistic cost table) from the same model"],
             ["HEFT_E2E", "static", "HEFT plan with the end-to-end terms added to the costs"],
             ["HEFT_oracle", "static (reference)", "HEFT plan from class-median costs of the calibration sessions; reference only, not a bound"]],
            [1.0, 0.55, 2.0], size=6.5)
    d.para("The proposed dispatcher orders ready tasks by predicted upward rank, rank(*t*) = \u0177(*t*) + max_{*c* \u2208 succ(*t*)} rank(*c*), and at every dispatch pass proceeds as follows: (1) sort the ready tasks by decreasing rank; (2) for each task consider only idle eligible workers, and leave the task queued if there is none (late binding, work conserving); "
           "(3) send the task to the idle worker with the least predicted time; (4) on completion log the observed time and release the dependents. A static plan instead fixes every assignment in advance; its planned and actual makespan are both logged. "
           "Policy set-up time (building the plan or the model tables) is recorded separately and is part of the end-to-end makespan.")
    d.para("**Static planning.** HEFT ({{heft}}) ranks tasks by upward rank and places each, in rank order, on the processor with the earliest finish time, inserting it into idle gaps:")
    d.equation("rank_{u}(*i*) = *w*_{i} + max_{*j* \u2208 succ(*i*)} ( *c*_{ij} + rank_{u}(*j*) )", 2)
    d.para("PEFT ({{peft}}) replaces the rank by the mean of an optimistic cost table and chooses the processor that minimises the finish time plus that table:")
    d.equation("OCT(*i*, *k*) = max_{*j* \u2208 succ(*i*)} min_{*q*} [ OCT(*j*, *q*) + *t*(*j*, *q*) + *c*_{ij} ]", 3)
    d.para("Both were reimplemented as static plans from a cost matrix filled by the cost model, and the repository tests reproduce the published worked examples (the 10-task example of the HEFT paper; the PEFT sample as printed in the author\u2019s thesis chapter, where PEFT yields a schedule length of 122 and HEFT 133; the only tolerated difference is the tie-break of two equal ranks). "
           "The plans are occupancy-blind, as registered in the protocol: they do not model contention for a worker beyond the plan itself, and are not re-planned during the run.")
    d.h2("GPU eligibility from measurements")
    d.para("A stage may run on the CUDA worker only if a recorded spike measurement shows a verified speed-up at that size and iteration count; a dropped row overrides a pass. @tab:spike lists the rows. Three configurations result: *cpu* (P and E cores only), *gpu* (strict: only stages verified on the original record) and *ext* (strict plus denoise at the iteration counts verified on the extended record). "
           "No configuration is GPU-only: the GPU is one narrow resource, and one CUDA worker was used throughout.")
    d.nextlabel = "spike"
    d.table("GPU spike records: time per task on the CPU and on the GPU (including host-device copies) and the verdict",
            ["Record", "Stage (denoise iterations)", "CPU ms", "GPU ms", "Speed-up", "Verdict"],
            [["original", "denoise (1)", "6.4", "6.7", "0.96\u00d7", "dropped"], ["original", "denoise (8)", "48.8", "41.9", "1.16\u00d7", "pass"],
             ["original", "edges", "5.8", "0.8", "7.68\u00d7", "pass"], ["original", "features", "2.3", "0.8", "2.88\u00d7", "pass"],
             ["extended", "denoise (2)", "11.5", "11.6", "0.99\u00d7", "dropped"], ["extended", "denoise (6)", "33.9", "31.9", "1.06\u00d7", "pass"],
             ["extended", "denoise (15)", "92.5", "77.5", "1.19\u00d7", "pass"], ["extended", "denoise (40)", "359.4", "203.3", "1.77\u00d7", "pass"],
             ["extended", "denoise (120)", "721.6", "603.6", "1.20\u00d7", "pass"]],
            [0.6, 1.0, 0.45, 0.45, 0.5, 0.5], size=6.5)
    d.h2("End-to-end timing convention")
    d.para("The end-to-end makespan runs from the start of `run()` to the last completion; initialisation and policy set-up are recorded separately (amendment F1 of the protocol). The older convention, first dispatch to last completion, hides the time a static plan needs to be computed and is kept for comparison. "
           "Adding the two conventions to the analysis changed no conclusion on this workload size (@tab:timing).")
    d.h2("Design decisions")
    d.bullets([
        "**One cost model for both sides.** Static and dynamic policies use the same ridge model, so a difference between them is a difference in *when and how the estimates are used*, not in how good the estimates are.",
        "**End-to-end makespan as the primary metric.** A static plan has a planning cost that the first-dispatch convention hides; the end-to-end metric charges it (12.5 ms to 81.3 ms here).",
        "**A strict GPU gate.** A stage is allowed on the GPU only where a measured speed-up exists, which keeps the comparison from being decided by a bad GPU placement rule; the extended set adds only iteration counts verified on a second record.",
        "**A parameter-aware baseline.** B4_param_first is the simplest policy that knows what the model knows; it tests whether learning is needed at all.",
        "**An oracle only as a reference.** HEFT_oracle uses class-median costs and is not a bound; no policy is compared against hindsight.",
        "**A decision rule for the hybrid.** A B4-or-PRED selector would be built only if its headroom exceeded the \u00b12% margin in the development cells; it did not, so none was built and no held-out hybrid session was run.",
    ])
    # ------------------------------------------------------------------ IV
    d.h1("Experimental Setup")
    d.para("**Machine.** Intel Core i5-13500HX (6 P, 8 E cores), NVIDIA RTX 3050 6 GB (driver 581.83, CUDA 12.8 build of PyTorch 2.11), 15.7 GB RAM, native Windows 11; sessions record an environment hash and are never pooled across machines. "
           "**Workloads.** The image pipeline (source, denoise, edges, features, aggregate; 512 px, 64 chains, 257 tasks) in which *H* chains are heavy (120 denoise iterations) and the rest light (2); the heavy parameter is invisible to a size-keyed table (@tab:wlds). "
           "The *primary* workload h16_l120 has 16 heavy chains. Others vary the heavy count (4, 40), the cost ratio (heavy 40 or 15 iterations: ratio 20 and 7.5) and include a uniform workload with no spread in cost.")
    d.nextlabel = "wlds"
    d.table("Evaluation workloads (runs per session, included runs in brackets; the first block of each session is a warm-up)",
            ["Workload", "Heavy chains / iterations", "Blocks", "Runs"],
            [["h16_l120 (primary)", "16, 120 vs 2 (ratio 60)", "25", "600 (576)"], ["uniform", "none; cpu and gpu only", "13", "208 (192)"],
             ["h04_l120", "4, 120 vs 2", "13", "312 (288)"], ["h40_l120", "40, 120 vs 2", "13", "312 (288)"],
             ["h16_l40", "16, 40 vs 2 (ratio 20)", "13", "312 (288)"], ["h16_l15", "16, 15 vs 2 (ratio 7.5)", "13", "312 (288)"]],
            [0.9, 1.3, 0.4, 0.6], size=7)
    d.para("**Measured heterogeneity.** A 512-pixel denoise task with 30 iterations takes 156 ms on a P core and 560 ms on an E core (3.6\u00d7); the two shorter stages are 2.8\u00d7 to 3.3\u00d7 slower on an E core. On the GPU the edge-detection stage is up to 15\u00d7 faster at 1024 px but only breaks even at small tiles because host-device copies dominate (@fig:het). "
           "A scheduler that ignores these ratios sends heavy work to slow cores.")
    d.nextlabel = "het"
    d.figure(FIG + r"\fig_heterogeneity.png", "Measured heterogeneity: stage kernel time on a P and an E core (left); GPU speed-up versus tile size (right).", 3.4)
    d.para("**Earlier workloads.** The earlier study also used the 59-task Montage mosaic {{montage,wfcommons}} (native Windows build, nine DSS2 images, three identical sequential references of 1459 s to 1469 s with identical output hashes) and a two-factor batch; @tab:montage lists the reference runs.")
    d.nextlabel = "montage"
    d.table("Montage reference runs: median wall time per task type (three identical sequential runs of 59 tasks)",
            ["Task type", "n", "Median (s)", "Range (s)"],
            [["mProject (reprojection)", "27", "160.57", "141.02\u2013169.89"], ["mDiffFit (overlap fit)", "108", "0.251", "0.041\u20131.036"], ["mBackground", "27", "0.336", "0.303\u20130.610"],
             ["mConcatFit / mBgModel / mImgtbl", "3 each", "0.207 / 0.379 / 0.094", "\u2013"], ["mAdd / mViewer", "3 each", "0.870 / 4.157", "\u2013"], ["Total sequential makespan", "3 runs", "1459.4, 1467.1, 1469.3", "outputs identical"]],
            [1.5, 0.4, 0.9, 0.7], size=7)
    d.para("**Data separation.** Calibration sessions (cal_l15, cal_l40, cal_l120, cal_uniform: 99 runs in their completed retries) fitted the model and the end-to-end terms; hold-out sessions (hold_l40, hold_l120: 28 runs) checked them; the evaluation sessions came afterwards with new chain orders. "
           "The protocol and the hashes of the evaluation designs were logged as frozen before the first evaluation session. **Protocol.** Conditions run once per block in seeded random order with one worker pool for all conditions. Before every block free memory had to exceed 2.4 GB at the start of a session and 0.8 GB per block, "
           "and the laptop had to be on mains power; these thresholds were never lowered, and attempts that failed the gate were kept on disk (suffix _r2 ... _r8) and never pooled. Output correctness was verified for every included run.")
    d.para("**Statistics.** The effect of a condition *c* against a reference *r* is computed per block *b* from the makespans *M*, with a percentile bootstrap interval (10,000 resamples) stratified by chain order and a sign-flip *p*-value:")
    d.equation("effect = (exp( mean_{*b*} ln( *M*_{*c*,*b*} / *M*_{*r*,*b*} ) ) \u2212 1) \u00d7 100%", 1)
    d.para("Negative values mean that *c* is faster. The confirmatory family is the ten contrasts C1\u2013C10 on the primary session under Holm correction with a \u00b12% equivalence margin; everything else, including the other five workloads and the comparison with the hand rule, is exploratory and unadjusted. "
           "For each contrast the expected outcome was written before the data (stated in the protocol) so that wrong predictions can be reported: the expectations held for C1, C2, C7, C9 and C10, and were wrong for C3 and C4 (we expected an inconclusive or equivalent result; the dynamic policy was about 5% faster).")
    d.nextlabel = "expect"
    d.table("Expectations written in the protocol before the evaluation data, and what the data showed",
            ["Id", "Expected before the data", "Outcome", "Held?"],
            [["C1", "faster (earlier sessions: about 19%)", "faster, \u221217.8%", "yes"], ["C2", "equivalent", "equivalent, +0.6%", "yes"],
             ["C3", "inconclusive or equivalent", "faster, \u22125.2%", "**no**"], ["C4", "inconclusive or equivalent", "faster, \u22125.2%", "**no**"],
             ["C5", "none stated", "faster, \u221212.2%", "\u2013"], ["C6", "none stated", "faster, \u22128.5%", "\u2013"],
             ["C7", "faster or equivalent", "equivalent, \u22120.0%", "yes"], ["C8", "none stated", "faster, \u221221.2%", "\u2013"],
             ["C9", "small gain", "faster, \u22122.6%", "yes"], ["C10", "small", "inconclusive, +1.6%", "yes"]],
            [0.3, 1.4, 1.2, 0.4], size=6.5)
    # ------------------------------------------------------------------ V
    d.h1("Results")
    d.h2("Primary workload", label="prim_sec")
    d.para("@tab:prim gives the end-to-end makespan of every policy in the three hardware sets and @fig:mk adds the 95% intervals. In every set, the three cost-aware dynamic policies (B4 param-first, PRED, PRED-E2E) are within about 1% of each other and clearly faster than blind B4; the static HEFT plan is slower than PRED, and PEFT is the slowest static plan. "
           "All 576 included runs of the session had verified output.")
    d.nextlabel = "prim"
    d.table("Primary workload h16_l120: end-to-end makespan in seconds (geometric mean over 24 included blocks)",
            ["Policy", "CPU only", "Strict GPU", "Extended GPU"], fd.primary_table_rows(), [1.5, 0.6, 0.6, 0.7], size=7)
    d.nextlabel = "mk"
    d.figure(FF + r"\fig_final_makespan.png", "End-to-end makespan of each policy in the three hardware sets on the primary workload (geometric mean, 95% interval, 24 blocks).", 3.4)
    d.h2("Confirmatory contrasts")
    d.para("@tab:conf and @fig:forest give the ten pre-stated contrasts. The dynamic dispatcher beats blind B4 by 17.8% on the CPU (C1) and 21.2% with the strict GPU set (C8). Against the static HEFT plan built from the *same* model it is faster by 5.2% on the CPU (C3) and by 12.2% with the strict GPU set (C5); the end-to-end variants give 5.2% (C4) and 8.5% (C6). "
           "Adding the end-to-end cost terms to the dynamic policy changes nothing (C2, C7: equivalent within \u00b12%). Using the strict GPU set helps the dispatcher by 2.6% (C9) but not blind B4 (C10, +1.6%, inconclusive).")
    d.nextlabel = "conf"
    d.table("Confirmatory contrasts (Holm family of ten; effect on end-to-end makespan, negative = first policy faster)",
            ["Id", "Contrast", "Effect % [95% CI]", "Holm p", "Result"], fd.confirmatory_rows(), [0.3, 1.4, 1.1, 0.4, 0.7], size=6.5)
    d.nextlabel = "forest"
    d.figure(FF + r"\fig_final_forest.png", "Confirmatory contrasts C1\u2013C10 with 95% intervals; the grey band is the \u00b12% equivalence margin.", 3.4)
    d.h2("Six workloads")
    d.para("The advantage depends on how much task cost varies (@fig:wl; @tab:wcpu and @tab:wgpu, exploratory outside the primary session). Against the static HEFT plan the dynamic dispatcher gains 0.2% to 5.2% on the CPU and 3.7% to 17.1% with the strict GPU set. Against blind B4 it gains almost 40% when only four of 64 chains are heavy, "
           "2.8% to 4.8% on the CPU (6.0% to 7.9% with the strict set) when 40 are heavy or the cost ratio is 20, and nothing on the uniform workload; with the lowest cost ratio (7.5) it is slightly *slower* than B4 with the strict GPU set (+1.1% [+0.3, +1.9]). With little spread in task cost there is little to order, and the dispatcher\u2019s own cost (about 9 ms more scheduling time than B4) is no longer paid back.")
    d.nextlabel = "wl"
    d.figure(FF + r"\fig_final_workloads.png", "PRED against static HEFT (left) and blind B4 (right) on the six workloads, CPU only (blue) and with the strict GPU set (orange); exploratory except the first row.", 3.4)
    d.nextlabel = "wcpu"
    d.table("CPU only: effect of PRED on end-to-end makespan against static HEFT and against blind B4 (%, negative = PRED faster; exploratory except h16_l120)",
            ["Workload", "vs HEFT [95% CI]", "vs B4 [95% CI]"], fd.workload_effect_rows("cpu"), [0.8, 1.4, 1.4], size=7)
    d.nextlabel = "wgpu"
    d.table("Strict GPU set: effect of PRED on end-to-end makespan against static HEFT and against blind B4 (%, exploratory except h16_l120)",
            ["Workload", "vs HEFT [95% CI]", "vs B4 [95% CI]"], fd.workload_effect_rows("gpu"), [0.8, 1.4, 1.4], size=7)
    d.h2("GPU use")
    d.para("@tab:gpu shows the effect of the hardware set within each policy. The GPU helps the model-driven dispatcher (strict set 2.6%, extended set 7.5% faster than the CPU only) and the static HEFT plan on the extended set (10.5%), but not blind B4, which sends work to the GPU without a cost model "
           "(32% of its tasks with the strict set) and is slower with it. Under the model-based policies the CUDA worker takes roughly 15% to 20% of the 257 tasks (@fig:place); its busy fraction is higher with the extended set. "
           "One CUDA worker is a single narrow resource, so the benefit comes from putting the right tasks on it, which needs the cost model.")
    d.nextlabel = "gpu"
    d.table("Effect of the hardware set within each policy on the primary workload (%, negative = faster)",
            ["Policy", "Strict vs CPU", "Extended vs CPU", "Extended vs strict"], fd.gpu_rows(), [0.9, 1.05, 1.05, 1.05], size=6.5)
    d.nextlabel = "place"
    d.figure(FF + r"\fig_final_placement.png", "Tasks run on the CPU and on the GPU per policy (extended set, primary workload) and the GPU busy fraction.", 3.4)
    d.h2("End-to-end terms, timing convention and overhead")
    d.para("Adding set-up and inter-process terms did not improve the dynamic policy (C2: +0.6% [+0.1, +1.3]; C7: \u22120.0% [\u22120.7, +0.5]) and on the uniform workload with the strict set the end-to-end variant was +2.9% [+0.4, +5.9] slower than B4: the terms are not free of cost when the extra decision work has nothing to gain. "
           "Adding them to the static plan did not help consistently (@tab:static). PEFT is clearly the slowest static plan. The oracle HEFT plan, built from class-median costs of the calibration sessions, is a reference, not a bound: with realised per-run times a static plan could be better.")
    d.nextlabel = "static"
    d.table("Static plans against HEFT_param_model on the primary workload (%, exploratory)",
            ["Hardware set", "HEFT_E2E", "PEFT", "HEFT oracle (reference)"], fd.static_rows(), [0.9, 1.05, 1.05, 1.15], size=6.5)
    d.para("The two timing conventions differ by the initialisation plus the policy set-up (@tab:timing). The difference is 12.5 ms for B4 and 81.3 ms for PEFT on a makespan of about 3 to 4 s, so no conclusion flips; on the old convention PRED against HEFT on the CPU is \u22124.9% [\u22125.6, \u22124.3] against \u22125.2% on the end-to-end convention. "
           "Policy set-up costs 19 ms (PRED), 30 ms (HEFT) and 71 ms (PEFT); total scheduling time is 16, 29 and 31 ms.")
    d.nextlabel = "timing"
    d.table("Primary workload, CPU only: makespan under the old convention (first dispatch to last completion) and the end-to-end convention (s) and the difference (ms)",
            ["Policy", "Old", "End-to-end", "Diff. (ms)"], fd.timing_rows(), [1.7, 0.5, 0.6, 0.6], size=7)
    d.nextlabel = "ovh"
    d.table("Primary workload, CPU only: initialisation, policy set-up and total scheduling time per run (ms) and mean queue wait (s)",
            ["Policy", "Init.", "Policy set-up", "Scheduling", "Queue wait"], fd.overhead_rows(), [1.6, 0.4, 0.6, 0.6, 0.5], size=7)
    d.h2("Workload by workload")
    mk = fd.makespan
    d.para(f"**Uniform (no spread in cost).** All policies are within a few percent: on the CPU B4 {mk('uniform', 'cpu', 'B4', 2)} s, B4 param-first {mk('uniform', 'cpu', 'B4_param_first', 2)} s, PRED {mk('uniform', 'cpu', 'PRED_RANK_GREEDY', 2)} s, HEFT {mk('uniform', 'cpu', 'HEFT_param_model', 2)} s; there is nothing to order and the dispatcher ties blind dispatch (+0.0% [\u22122.5, +2.3]). "
           f"**Four heavy chains (h04_l120).** The heavy chains decide the critical path; blind B4 starts them late or on a slow core and takes {mk('h04_l120', 'cpu', 'B4', 2)} s against {mk('h04_l120', 'cpu', 'PRED_RANK_GREEDY', 2)} s for PRED (\u221239.4%); the static HEFT plan is also close ({mk('h04_l120', 'cpu', 'HEFT_param_model', 2)} s). "
           f"**Forty heavy chains (h40_l120).** Most work is heavy, so order matters less: B4 {mk('h40_l120', 'cpu', 'B4', 2)} s, PRED {mk('h40_l120', 'cpu', 'PRED_RANK_GREEDY', 2)} s, HEFT {mk('h40_l120', 'cpu', 'HEFT_param_model', 2)} s. "
           f"**Lower cost ratios (h16_l40, h16_l15).** With ratios of 20 and 7.5 the gaps shrink: on the CPU PRED is {mk('h16_l40', 'cpu', 'PRED_RANK_GREEDY', 2)} s against B4 {mk('h16_l40', 'cpu', 'B4', 2)} s at ratio 20 and {mk('h16_l15', 'cpu', 'PRED_RANK_GREEDY', 2)} s against {mk('h16_l15', 'cpu', 'B4', 2)} s at ratio 7.5, while the strict GPU set still separates the static plan from the dynamic policies "
           f"(HEFT {mk('h16_l15', 'gpu', 'HEFT_param_model', 2)} s against PRED {mk('h16_l15', 'gpu', 'PRED_RANK_GREEDY', 2)} s at ratio 7.5): when the GPU model error matters, committing to the estimate in advance costs more than deciding late.")
    lo, hi = fd.halfwidths()
    d.para(f"**Precision.** With 24 paired blocks the half-width of the ten confirmatory intervals is {lo:.1f} to {hi:.1f} percentage points; the exploratory sessions use 12 blocks and are less precise, so they show direction and order of magnitude and are not used to rank near-equal policies. "
           "The 10 or 24 blocks of a session repeat a few chain orders, so intervals describe run-to-run noise, not variation across workloads, which is why six workloads and, earlier, twenty unseen chain orders were used.")
    d.para("**Planned versus actual.** The static plans are not far from reality in total (@tab:plan), yet a fixed assignment cannot react to the actual completion order. A ratio below 1 means that the plan was optimistic.")
    d.nextlabel = "plan"
    d.table("Planned over actual makespan of the static plans (primary workload)", ["Plan", "CPU only", "Strict GPU", "Extended GPU"], fd.plan_rows(), [1.5, 0.6, 0.6, 0.7], size=7)
    d.h2("A simple rule and a hybrid selector")
    d.para("Against B4 param-first, the queue sorted by the cost parameter, PRED is \u22120.4% [\u22120.9, +0.1] on the CPU, \u22120.6% [\u22121.1, \u22120.0] with the extended set and \u22120.2% [\u22120.9, +0.7] with the strict set (exploratory): under 1% in every configuration. "
           "Most of the improvement over blind B4 therefore comes from using the task parameter to choose the order and the place, not from rank ordering and late binding as such. A hybrid selector between B4 and PRED would be worth building only if its headroom exceeded the \u00b12% margin; "
           "in 17 development cells the maximum headroom was 1.1%, the mean 0.08%, and no cell exceeded the margin, so none was built.")
    d.h2("Earlier exploratory study")
    d.para("An earlier study used the same runtime on a different cost-skewed family. With 16 heavy chains among 64, the dispatcher shortened makespan by 19.3% (6P+7E, 12 chain orders never used before) and 20.5% (2P+7E, 8 orders) against B4, and was level with the hand rule (+0.66%, +0.27%); the gain was about 27% with few heavy chains and about 4% when most were heavy (@tab:early, @fig:early_f). "
           "There was no gain on the 59-task Montage mosaic (B4 was 47.9% slower than static P-only, because every task prefers the P cores by 2.3\u00d7 to 3.6\u00d7), on a uniform batch (+0.45%) or on a two-factor batch. In that session HEFT with the same model was level with the dispatcher (+1.10% [\u22120.53, +2.81]) and PEFT was not; "
           "the final session finds the dispatcher about 5% faster than HEFT on the CPU. The timing convention does not explain the difference (@tab:timing); the sessions differ in chain orders, block count and code state, and the difference was not isolated, so both results are reported.")
    d.nextlabel = "early"
    d.table("Earlier exploratory sessions on unseen chain orders (effect against B4, negative = shorter)",
            ["Session", "Blocks / orders", "Dispatcher", "Hand rule"],
            [["6P+7E, 16 heavy", "36 / 12", "\u221219.32% [\u221220.0, \u221218.6]", "\u221219.85%"], ["2P+7E, 16 heavy", "24 / 8", "\u221220.45% [\u221221.2, \u221219.8]", "\u221220.67%"],
             ["6P+7E, 4 heavy", "12 / 4", "\u221227.65% [\u221234.0, \u221218.7]", "\u221226.94%"], ["6P+7E, 8 heavy", "12 / 4", "\u221226.76% [\u221227.9, \u221225.7]", "\u221226.93%"],
             ["6P+7E, 40 heavy", "12 / 4", "\u22123.81% [\u22125.1, \u22121.9]", "\u22125.15%"]], [0.9, 0.6, 1.1, 0.6], size=7)
    d.nextlabel = "early_f"
    d.figure(FIG + r"\fig_dose_heavy.png", "Earlier study: gain over B4 versus heavy:light cost ratio (left) and number of heavy chains among 64 (right).", 3.4)
    d.nextlabel = "perorder"
    d.figure(FIG + r"\fig_per_order.png", "Earlier study: change in makespan of the dispatcher against B4 (blue) and the hand rule (green) for each chain order not used before (12 orders left, 8 orders right).", 3.4)
    d.nextlabel = "mkearly"
    d.figure(FIG + r"\fig_makespan_policies.png", "Earlier study: mean makespan by policy on unseen chain orders (geometric means with 95% intervals): 12 orders on 6P+7E (left), 8 orders on 2P+7E (right).", 3.4)
    d.para("**Overhead and a defect found while measuring it.** Two overhead figures exist: the per-dispatch decision time (6.8 ms per run for B4 and 15.5 ms for the dispatcher, about 0.5% of makespan) and the coordinator scheduling time (0.197 s and 0.100 s). "
           "The difference was traced with an instrumented run: an idle CUDA worker that no task can use defeats the early exit of the dispatch loop, and 10,042 of 10,299 selection calls of B4 returned nothing. A decision-preserving fix in a separate adapter cut the coordinator time to 8 ms and 24 ms and moved the dispatcher\u2019s gain "
           "from \u221219.47% to \u221220.28%, i.e. 0.8 points (78 runs verified; the fix is not applied to the source). Overhead therefore costs 2% to 5% of these 3 s to 9 s runs but does not explain the result. The final benchmark keeps the idle CUDA worker in the pool in the *cpu* configuration, "
           "which is one candidate for the unresolved difference between the two sessions.")
    d.nextlabel = "ovh_early"
    d.figure(FIG + r"\fig_overhead.png", "Earlier study: per-dispatch decision time versus coordinator scheduling time, before and after the dispatch-loop fix.", 3.4)
    d.para("**Remote worker (emulated, not rerun).** In earlier registered sessions on an emulated link (a node on one local E core behind a loopback socket and a delay shim), blind remote placement on a slow link cost 31% and transfer-aware placement avoided that harm; on a fast link the remote worker gave no benefit although the predicted execution and transfer times matched the measured ones "
           "(0.1457 s against 0.1464 s, and 0.0937 s against 0.0943 s; the predictive policy was 3.78% [+2.27, +5.58] slower with the remote worker). These are emulation results and were not repeated with the final policies; a real remote benefit remains unproven, and no Raspberry Pi or real-network measurement exists.")
    # ------------------------------------------------------------------ VI
    d.h1("Discussion")
    d.para("**What dynamic dispatch buys.** On the CPU the dynamic dispatcher beats the static plan by about 5%, with the strict GPU set by 8% to 12%, and with the extended set by 2% to 3%. The static plan is not wrong in total (planned over actual makespan was between 0.88 and 1.03), but the fixed assignment cannot react to the actual completion order, "
           "and its GPU assignments inherit the 23% to 31% model error in advance; a dynamic policy uses the estimate only when a worker is idle. Part of the gap on the GPU sets may therefore reflect model error and not only the timing of decisions; this was not separated experimentally. "
           "The dominant effect against blind dispatch is ordering and informed placement: serving predicted-heavy work first removes the tail that blind dispatch creates and keeps heavy chains off the slow cores.")
    d.para("**What it does not buy.** Not beyond a rule that knows the cost parameter (within 1%); not where task cost does not vary (uniform, and the light workloads); not through end-to-end cost terms; not through a hybrid selector; and not on the GPU for blind dispatch. "
           "The dispatcher\u2019s value is that it replaces knowledge a person would hard-code and is refitted from logs for a new pool layout. This agrees with the observation of {{ilyushkin}} that order can matter more than estimate accuracy, now on real executions, and with {{lotaru}} that cheap models suffice for list scheduling.")
    d.para("**Ordering versus binding.** Two design choices are bundled in the dispatcher and the earlier data separate them. Ordering by predicted rank with early binding to the earliest-finish worker gave \u221213.21% against B4, whereas ordering plus idle-only (late) binding gave \u221218.97% on the same six orders, "
           "so late binding contributes about six of the nineteen points; the static HEFT plan reached \u221218.08% by inserting tasks into idle gaps. A plan is brittle when durations are mispredicted and a dispatcher is not; the final benchmark supports this on the GPU sets, where the model error is largest, but does not test mispredicted durations in isolation.")
    d.para("**Relation to the base patent and to learned ranking.** The base patent {{p_xilinx}} gates dispatch on eligibility and dependency counters and recites no prediction; our B4 is a comparison baseline mapped from it, not an implementation of the patent. Learned ranking of DAG tasks on heterogeneous hardware is disclosed in {{p_ibm1}}; "
           "the contribution here is therefore not the idea of ranking but a measured comparison of static and dynamic scheduling with one cost model, end-to-end timing and an informed baseline. This framing is deliberate: it is what the evidence supports.")
    d.para("**Practical reading.** For an engineer choosing a scheduler for a small hybrid machine the measurements suggest three steps: first check whether tasks differ in cost by a factor that size alone does not reveal; if they do, order the queue by (predicted) cost before worrying about placement, since a rule that sorts by the right parameter was as good as the learned model in every configuration; "
           "and send only stages with a measured GPU speed-up to the GPU. A learned model is the right tool when the parameter is not known in advance or changes with the machine, since it is refitted from logs. **Baselines.** A fair evaluation of a learned scheduler needs an informed rule, static plans from the same model, intervals and the scheduler\u2019s own cost; each of these changed a conclusion in this project.")
    d.nextlabel = "guide"
    d.table("Guidance derived from the measurements (this workload family and machine)",
            ["Situation", "Expected benefit of dynamic, model-driven dispatch"],
            [["Task cost varies and a few heavy tasks compete for fast workers", "large against blind dispatch (17% to 40%); 2% to 12% against a static plan; a rule that knows the parameter gets almost the same"],
             ["Little or no spread in task cost", "none; equal to blind dispatch within \u00b12%; a small loss is possible with the strict GPU set"],
             ["A GPU is available for some stages", "worth 3% to 8% for the dispatcher if the GPU is used only where a speed-up was measured; harmful for blind dispatch"],
             ["Model error is large (GPU: 23% to 31%)", "prefer dynamic decisions, which use the estimate only when a worker is idle; improve the model before adding complexity"],
             ["A remote worker behind a link", "none in the emulated regimes tested; measure on the real link first"]],
            [1.5, 2.0], size=6.5)
    d.para("**Threats to validity.** One machine, one workload family (an image pipeline of 257 tasks at 512 px), one CUDA worker; the workload family was designed to contain a hidden cost. Only the primary session is confirmatory; the other five sessions and the comparison with the hand rule are exploratory and unadjusted. "
           "HEFT, PEFT and the oracle plan are occupancy-blind static plans without re-planning; a plan with perfect knowledge of realised task times was not computed. The features of the hybrid check were computed after the primary results had been read (the model and the DAG alone determine them). "
           "Runs were made with a dirty working tree and several source hashes, so sessions are never pooled. The remote worker was not rerun and learned DRL schedulers were not run. **Disclosure.** Software, analysis scripts and parts of the text were produced with the help of an AI coding assistant under the authors\u2019 direction; "
           "every number was checked against stored result files. [Authors to confirm the wording required by the venue.]")
    # ------------------------------------------------------------------ VII
    d.h1("Reproducibility and Availability")
    d.para("Every session stores its design, environment and code hashes. The protocol, the amendment, the preservation record (git state, source hashes, backups) and the activity log of the final study are in the repository package; the tables of this paper are generated from the stored analysis files by scripts, and 521 automated tests pass. "
           "The pipeline runs as `scripts/final_stage1.ps1` (calibration, models, designs), `scripts/final_stage2.ps1` (six evaluation sessions and analyses), `scripts/final_analyze.py`, `scripts/final_results_table.py` and `scripts/final_build_report.py`. "
           "The runs need mains power and at least 2.4 GB of free memory.")
    d.h2("Implementation and tests")
    d.para("The framework is Python on Windows. @tab:inv lists its size; the 521 automated tests (run before the dashboard variants were added) cover the coordinator contract, the estimators, the static planners (including the published worked examples), the final policies, GPU eligibility, the statistics and the claims registry, which is re-read against the stored tables by a test. "
           "A local web dashboard shows the system state, a replay of runs and the stored results; two later versions in separate packages show the GPU with live load and add a tab that runs one live block of the final benchmark.")
    d.nextlabel = "inv"
    d.table("Implementation inventory (lines of Python counted in the repository)",
            ["Part", "Files", "Lines"],
            [["Runtime package (src/caosched)", "107", "12,578"], ["  core: coordinator, pools, DAG, tasks", "13", "2,026"], ["  estimators; schedulers; analysis; experiment", "", "1,197; 845; 1,037; 1,126"],
             ["  final study: static baselines, E2E dispatcher, GPU region", "4", "216"], ["  dashboard (original; v2; v3)", "", "774; 202; 266"],
             ["Scripts", "89", "9,709"], ["Tests", "52", "7,263"]], [2.2, 0.5, 0.9], size=7)
    d.h2("Incidents and defects")
    d.para("Defects and operational incidents are recorded rather than hidden (@tab:inc). None of them changed a reported number: runs that failed a gate were kept on disk and never pooled.")
    d.nextlabel = "inc"
    d.table("Defects and incidents found during the work and what was done",
            ["Item", "Found by", "Action"],
            [["Static plans were timed from the first dispatch, hiding their planning time", "design review", "end-to-end makespan (amendment F1); old metric kept"],
             ["Stage 1 aborted when the laptop was unplugged, on retry-id collisions and on low free memory (antivirus, Docker, WSL)", "run logs", "mains wait and first-unused-id logic; the 2.4 GB and 0.8 GB thresholds were never lowered; aborted attempts kept (_r2 \u2026 _r8)"],
             ["Learned model applied to a profile it was not fitted on", "audit of earlier phases", "profile binding recorded in the model; refusal on mismatch"],
             ["Worker-pool rebuild between conditions created cold workers", "pilot analysis", "one pool for all conditions"],
             ["Idle CUDA worker defeats the dispatch loop\u2019s early exit", "overhead diagnosis", "quantified; fix in a separate adapter; not applied to the source"],
             ["Remote node served one client then exited", "loopback rehearsal", "persistent mode and test"]],
            [1.7, 0.7, 1.1], size=6.5)
    d.h2("Status of the claims")
    d.nextlabel = "claims"
    d.table("Claim status after the project (selection)",
            ["Status", "Claim"],
            [["Supported", "dynamic PRED beats blind B4 by 17.8% (CPU) and 21.2% (strict GPU); beats a static HEFT plan from the same model by 5.2% and 12.2%; the GPU helps PRED (2.6% strict, 7.5% extended); end-to-end terms are equivalent"],
             ["Not established", "advantage over a rule that knows the cost parameter (within 1%); a hybrid selector; GPU benefit for blind B4; a remote-offloading benefit; Raspberry Pi results; any claim beyond this machine and workload family"],
             ["Not supported / null", "gain on Montage, on the uniform and light workloads and on the two-factor workload; a remote worker helping EFT at compute level 30"]],
            [0.8, 2.7], size=6.5)
    d.h1("Conclusion")
    d.para("On a hybrid CPU+GPU laptop and one workload family, dynamic dispatch driven by a cheap ridge cost model finishes a workflow 2% to 12% sooner than a static HEFT plan from the same model (5% on the CPU, 12% with the strict GPU set) and about 18% to 21% sooner than blind dispatch, when task cost varies; "
           "it ties blind dispatch when it does not. A rule that knows the cost parameter reaches almost the same result, end-to-end cost terms and a hybrid selector add nothing, and the GPU helps only when it is used where a speed-up was measured and the model chooses the tasks. "
           "Future work: a GPU cost model with lower error and an experiment that separates model error from decision timing, a second workload family, the remote worker with the final policies and a real link, and a clean-tree rerun of the headline session.")
    if not anonymous:
        d.h1_plain("Availability")
        d.para("The code, protocols, claims registry and result tables are prepared for release after the authors\u2019 decision on intellectual-property protection; see the accompanying repository package. [Repository URL to be inserted by the authors.]")
    else:
        d.h1_plain("Availability")
        d.para("An anonymised artefact (code, protocols, claims registry and result tables) will be provided to reviewers on request.")
    # ------------------------------------------------------------------ appendix
    d.h1_plain("Appendix A. End-to-end makespan of all policies and workloads (s)")
    hdr = ["Workload", "B4", "B4 param-first", "PRED", "PRED-E2E", "HEFT", "HEFT-E2E", "PEFT"]
    wd = [0.7, 0.4, 0.55, 0.4, 0.5, 0.4, 0.5, 0.4]
    for cfg, lab, key in (("cpu", "CPU only", "acpu"), ("gpu", "strict GPU set", "agpu"), ("ext", "extended GPU set", "aext")):
        d.nextlabel = key
        d.table(f"All workloads, {lab}: end-to-end makespan in seconds (geometric mean; 24 blocks for h16_l120, 12 for the others)", hdr, fd.all_workloads_rows(cfg), wd, size=6.5)
    d.h1_plain("Appendix B. Effects against static HEFT and blind B4, all workloads")
    for ref, rname in (("heft", "static HEFT_param_model"), ("b4", "blind B4")):
        for cfg, lab in (("cpu", "CPU only"), ("gpu", "strict GPU set"), ("ext", "extended GPU set")):
            d.table(f"{lab}: effect on end-to-end makespan against {rname} (%, negative = faster; exploratory except h16_l120)",
                    ["Workload", "B4 param-first", "PRED", "PRED-E2E"], fd.effects_vs(ref, cfg), [0.8, 1.05, 1.05, 1.05], size=6.5)
    d.h1_plain("Appendix B2. PRED against the hand rule B4_param_first")
    d.nextlabel = "pf"
    d.table("PRED against B4_param_first on the primary workload, end-to-end makespan (%, negative = PRED faster; exploratory, 24 blocks)",
            ["Hardware set", "Effect [95% CI]"], [[lab, fd.eff(fd.pf_effect(c))] for c, lab in (("cpu", "CPU only"), ("gpu", "strict GPU set"), ("ext", "extended GPU set"))],
            [1.2, 1.6], size=7)
    d.h1_plain("Appendix C. Placement of tasks (primary workload)")
    d.nextlabel = "plc"
    d.table("Tasks per run on CPU / GPU, GPU busy fraction and mean CPU utilisation", ["Set", "Policy", "Tasks CPU / GPU", "GPU busy", "CPU util."], fd.placement_rows(), [0.5, 1.5, 0.7, 0.5, 0.5], size=6.5)
    d.references()
    d.h1_plain("Appendix D. Environment and commands")
    d.para("**Environment.** Intel Core i5-13500HX, NVIDIA GeForce RTX 3050 6 GB (driver 581.83), 15.7 GB RAM, Windows 11, Python 3.11.9, PyTorch 2.11 with the CUDA 12.8 build; sessions need mains power and at least 2.4 GB of free memory (0.8 GB per block). "
           "**Commands (PowerShell, repository root).** `scripts/final_stage1.ps1` (calibration sessions, models, designs, smoke test); `scripts/final_stage2.ps1` (six evaluation sessions and their analyses); `scripts/final_analyze.py <session> --confirmatory` (primary session); "
           "`scripts/final_results_table.py`, `scripts/final_cross_workload.py`, `scripts/final_hybrid_check.py`, `scripts/final_build_report.py`; tests: `python -m pytest -q`. "
           "Hashes of the protocol, the designs and the models are in `data/results/final_20261101/ACTIVITY_LOG.md`.")
    o = OUT + "\\" + name
    d.save(o + ".docx")
    pages, words = export_pdf(o + ".docx", o + ".pdf")
    print(name, "pages", pages, "words", words, "refs", len(d.cite_order))


build(False, "06_Final_IEEE_Paper_Draft")
build(True, "06b_Final_IEEE_Paper_Anonymous_for_Double_Blind_Review")
