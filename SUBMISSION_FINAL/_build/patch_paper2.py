p = "build_paper_final.py"
s = open(p, encoding="utf-8").read()


def before(anchor, new):
    global s
    assert anchor in s, anchor[:70]
    s = s.replace(anchor, new + anchor, 1)


# ---- A. runtime details
before('    d.h2("Cost model")\n',
       '    d.para("Failed or timed-out tasks get a terminal status and their dependents are marked not-run; every run starts from a clean directory; failed runs are kept and flagged. External-command tasks (the Montage jobs of the earlier study) run as processes without a shell, with timeouts, process-tree kill and hashing of inputs and outputs. "\n'
       '           "A run produces an event log (one JSON line per event) and a manifest; the manifest ties the run to its design, code and environment (@tab:log).")\n'
       '    d.nextlabel = "log"\n'
       '    d.table("Event log and run manifest content",\n'
       '            ["Record", "Fields (selection)"],\n'
       '            [["task_ready, task_dispatched", "task id, worker, pool, queue wait, worker load, decision time, decision record"],\n'
       '             ["task_submitted, task_completed", "kernel time, start and end timestamps, transfer time, bytes moved, output size and SHA-256"],\n'
       '             ["worker_ready, run_started, run_finished", "pid, requested and actual affinity, capabilities; makespan, status, tasks per pool"],\n'
       '             ["run manifest", "condition, policy, seed, instance, warm-up flag, status, output verdict and hashes, event-log SHA-256, git commit and dirty flag, source and design SHA-256"],\n'
       '             ["session record", "design hash, machine id, environment hash, blocks completed, preflight log, final status"]],\n'
       '            [1.2, 2.2], size=7)\n')

# ---- B. static planning formulas
before('    d.h2("GPU eligibility from measurements")\n',
       '    d.para("**Static planning.** HEFT ({{heft}}) ranks tasks by upward rank and places each, in rank order, on the processor with the earliest finish time, inserting it into idle gaps:")\n'
       '    d.equation("rank_{u}(*i*) = *w*_{i} + max_{*j* \\u2208 succ(*i*)} ( *c*_{ij} + rank_{u}(*j*) )", 2)\n'
       '    d.para("PEFT ({{peft}}) replaces the rank by the mean of an optimistic cost table and chooses the processor that minimises the finish time plus that table:")\n'
       '    d.equation("OCT(*i*, *k*) = max_{*j* \\u2208 succ(*i*)} min_{*q*} [ OCT(*j*, *q*) + *t*(*j*, *q*) + *c*_{ij} ]", 3)\n'
       '    d.para("Both were reimplemented as static plans from a cost matrix filled by the cost model, and the repository tests reproduce the published worked examples (the 10-task example of the HEFT paper; the PEFT sample as printed in the author\\u2019s thesis chapter, where PEFT yields a schedule length of 122 and HEFT 133; the only tolerated difference is the tie-break of two equal ranks). "\n'
       '           "The plans are occupancy-blind, as registered in the protocol: they do not model contention for a worker beyond the plan itself, and are not re-planned during the run.")\n')

# ---- C. estimators tried
before('    d.nextlabel = "err"\n',
       '    d.para("**Features and fitting protocol.** Features are decision-time safe: task parameters are known when the task becomes ready. Offline features are reconstructed from the logged decision context and a parity test enforces equality with the online features, so that no feature uses information from the future. "\n'
       '           "Inference is a dot product of a few numbers. Over the project more elaborate predictors were tried (@tab:est); in the earlier phases none of them improved scheduling over the ridge model enough to justify its cost, so the final study uses the simple model.")\n'
       '    d.nextlabel = "est"\n'
       '    d.table("Estimators tried during the project (role in the final study)",\n'
       '            ["Estimator", "Description", "Role"],\n'
       '            [["E0", "constant time per task type and pool", "earlier phases"], ["E1", "solo-profile table keyed by stage and size", "earlier phases"],\n'
       '             ["E2", "analytic size model", "earlier phases"], ["E3", "moving history of observed times", "earlier phases"],\n'
       '             ["E1+rc", "E1 recalibrated online from completed tasks", "earlier phases"], ["E4 ridge", "ridge on task parameters and occupancy context", "earlier phases"],\n'
       '             ["CatBoost, MLP", "gradient-boosted trees and a small neural network on the same features", "evaluated, not adopted"],\n'
       '             ["ParamModel", "ridge per (stage, pool) on varying parameters, size and pairwise products", "**used in the final study**"],\n'
       '             ["E5 oracle", "offline replay of observed times", "reference only"]],\n'
       '            [0.8, 2.0, 0.8], size=6.5)\n')

# ---- D. heterogeneity and Montage
before('    d.para("**Data separation.**',
       '    d.para("**Measured heterogeneity.** A 512-pixel denoise task with 30 iterations takes 156 ms on a P core and 560 ms on an E core (3.6\\u00d7); the two shorter stages are 2.8\\u00d7 to 3.3\\u00d7 slower on an E core. On the GPU the edge-detection stage is up to 15\\u00d7 faster at 1024 px but only breaks even at small tiles because host-device copies dominate (@fig:het). "\n'
       '           "A scheduler that ignores these ratios sends heavy work to slow cores.")\n'
       '    d.nextlabel = "het"\n'
       '    d.figure(FIG + r"\\fig_heterogeneity.png", "Measured heterogeneity: stage kernel time on a P and an E core (left); GPU speed-up versus tile size (right).", 3.4)\n'
       '    d.para("**Earlier workloads.** The earlier study also used the 59-task Montage mosaic ({{montage,wfcommons}}; native Windows build, nine DSS2 images, three identical sequential references of 1459 s to 1469 s with identical output hashes) and a two-factor batch; @tab:montage lists the reference runs.")\n'
       '    d.nextlabel = "montage"\n'
       '    d.table("Montage reference runs: median wall time per task type (three identical sequential runs of 59 tasks)",\n'
       '            ["Task type", "n", "Median (s)", "Range (s)"],\n'
       '            [["mProject (reprojection)", "27", "160.57", "141.02\\u2013169.89"], ["mDiffFit (overlap fit)", "108", "0.251", "0.041\\u20131.036"], ["mBackground", "27", "0.336", "0.303\\u20130.610"],\n'
       '             ["mConcatFit / mBgModel / mImgtbl", "3 each", "0.207 / 0.379 / 0.094", "\\u2013"], ["mAdd / mViewer", "3 each", "0.870 / 4.157", "\\u2013"], ["Total sequential makespan", "3 runs", "1459.4, 1467.1, 1469.3", "outputs identical"]],\n'
       '            [1.5, 0.4, 0.9, 0.7], size=7)\n')

# ---- E. overhead and the dispatch-loop defect (earlier study)
before('    d.para("**Remote worker (emulated, not rerun).**',
       '    d.para("**Overhead and a defect found while measuring it.** Two overhead figures exist: the per-dispatch decision time (6.8 ms per run for B4 and 15.5 ms for the dispatcher, about 0.5% of makespan) and the coordinator scheduling time (0.197 s and 0.100 s). "\n'
       '           "The difference was traced with an instrumented run: an idle CUDA worker that no task can use defeats the early exit of the dispatch loop, and 10,042 of 10,299 selection calls of B4 returned nothing. A decision-preserving fix in a separate adapter cut the coordinator time to 8 ms and 24 ms and moved the dispatcher\\u2019s gain "\n'
       '           "from \\u221219.47% to \\u221220.28%, i.e. 0.8 points (78 runs verified; the fix is not applied to the source). Overhead therefore costs 2% to 5% of these 3 s to 9 s runs but does not explain the result. The final benchmark keeps the idle CUDA worker in the pool in the *cpu* configuration, "\n'
       '           "which is one candidate for the unresolved difference between the two sessions.")\n'
       '    d.nextlabel = "ovh_early"\n'
       '    d.figure(FIG + r"\\fig_overhead.png", "Earlier study: per-dispatch decision time versus coordinator scheduling time, before and after the dispatch-loop fix.", 3.4)\n')

# ---- F. discussion paragraphs
before('    d.nextlabel = "guide"\n',
       '    d.para("**Ordering versus binding.** Two design choices are bundled in the dispatcher and the earlier data separate them. Ordering by predicted rank with early binding to the earliest-finish worker gave \\u221213.21% against B4, whereas ordering plus idle-only (late) binding gave \\u221218.97% on the same six orders, "\n'
       '           "so late binding contributes about six of the nineteen points; the static HEFT plan reached \\u221218.08% by inserting tasks into idle gaps. A plan is brittle when durations are mispredicted and a dispatcher is not; the final benchmark supports this on the GPU sets, where the model error is largest, but does not test mispredicted durations in isolation.")\n'
       '    d.para("**Relation to the base patent and to learned ranking.** The base patent {{p_xilinx}} gates dispatch on eligibility and dependency counters and recites no prediction; our B4 is a comparison baseline mapped from it, not an implementation of the patent. Learned ranking of DAG tasks on heterogeneous hardware is disclosed in {{p_ibm1}}; "\n'
       '           "the contribution here is therefore not the idea of ranking but a measured comparison of static and dynamic scheduling with one cost model, end-to-end timing and an informed baseline. This framing is deliberate: it is what the evidence supports.")\n'
       '    d.para("**Practical reading.** For an engineer choosing a scheduler for a small hybrid machine the measurements suggest three steps: first check whether tasks differ in cost by a factor that size alone does not reveal; if they do, order the queue by (predicted) cost before worrying about placement, since a rule that sorts by the right parameter was as good as the learned model in every configuration; "\n'
       '           "and send only stages with a measured GPU speed-up to the GPU. A learned model is the right tool when the parameter is not known in advance or changes with the machine, since it is refitted from logs. **Baselines.** A fair evaluation of a learned scheduler needs an informed rule, static plans from the same model, intervals and the scheduler\\u2019s own cost; each of these changed a conclusion in this project.")\n')

# ---- G. related-work comparison table
before('    d.para("**Gap.** The literature leaves open',
       '    d.nextlabel = "rw"\n'
       '    d.table("This work compared with the closest published systems",\n'
       '            ["System", "Evaluation", "Hardware", "Overhead reported", "Intervals", "Informed baseline"],\n'
       '            [["{{lachesis}}", "simulation", "simulated cluster", "inference time", "no", "no"], ["{{adprl}}", "trace simulation + testbed", "3 Jetson boards", "no", "no", "no"],\n'
       '             ["{{rodriguez}}", "real", "Zynq CPU+FPGA", "yes", "no", "no"], ["{{lotaru}}", "simulation", "simulated heterogeneous cluster", "prediction error", "median errors", "HEFT with true runtimes"],\n'
       '             ["{{starpu}}", "real", "CPU+GPU nodes", "history models", "not assessed", "no"], ["{{lureda}}", "real, small DAGs", "CPU/GPU", "runtime monitor", "not stated", "HEFT, StarPU"],\n'
       '             ["This work", "real executions", "P/E cores, RTX 3050", "end-to-end and per-dispatch", "paired bootstrap, Holm", "yes (hand rule, static plans)"]],\n'
       '            [0.5, 0.75, 0.75, 0.65, 0.6, 0.7], size=6.5)\n')

# ---- H. appendix tables
before('    d.h1_plain("Appendix B. Placement of tasks (primary workload)")\n',
       '    d.h1_plain("Appendix B. Effects against static HEFT and blind B4, all workloads")\n'
       '    for ref, rname in (("heft", "static HEFT_param_model"), ("b4", "blind B4")):\n'
       '        for cfg, lab in (("cpu", "CPU only"), ("gpu", "strict GPU set"), ("ext", "extended GPU set")):\n'
       '            d.table(f"{lab}: effect on end-to-end makespan against {rname} (%, negative = faster; exploratory except h16_l120)",\n'
       '                    ["Workload", "B4 param-first", "PRED", "PRED-E2E"], fd.effects_vs(ref, cfg), [0.8, 1.05, 1.05, 1.05], size=6.5)\n')
s = s.replace('Appendix B. Placement of tasks (primary workload)', 'Appendix C. Placement of tasks (primary workload)')
open(p, "w", encoding="utf-8").write(s)
print("paper2 patched")
