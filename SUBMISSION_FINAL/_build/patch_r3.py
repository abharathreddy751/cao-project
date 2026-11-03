p = "build_review3.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


def between(a, b, new, include_b=True):
    global s
    i = s.index(a)
    j = s.index(b, i) + (len(b) if include_b else 0)
    s = s[:i] + new + s[j:]


rep("from ieee_docx2 import IEEEDoc, export_pdf\n", "from ieee_docx2 import IEEEDoc, export_pdf\nimport final_data as fd\n")
rep('FIG = r"D:\\cao project\\publications\\figures"', 'FIG = r"D:\\cao project\\publications\\figures"\nFF = r"D:\\cao project\\SUBMISSION_FINAL\\_fig"')

# ---- abstract
between('"This draft describes the implementation of the project and analyses its results.', 'A Raspberry Pi has not yet been measured.",',
        '"This draft describes the implementation of the project and analyses its results. The framework (12,600 lines of Python in the runtime, 9,700 in scripts, 7,300 in tests) executes the tasks of a dependency graph on "\n'
        '    "pinned performance-core and efficiency-core worker processes and one CUDA worker (RTX 3050), logs every dispatch with its decision time, verifies every output against a CPU reference and compares scheduling policies "\n'
        '    "in interleaved, seeded blocks with paired bootstrap intervals. The final benchmark compares *static* plans (HEFT, PEFT, HEFT with end-to-end terms) with *dynamic* dispatch (blind B4, a parameter-aware rule, and a predicted-rank, "\n'
        '    "idle-worker dispatcher with and without end-to-end cost terms), all built on one ridge cost model, on six workloads and three hardware sets; the primary metric is the end-to-end makespan from the start of the run to the last completion. "\n'
        '    "On the primary workload (24 included blocks, ten Holm-adjusted contrasts) the dynamic dispatcher is 17.8% faster than B4 on the CPU and 21.2% faster with a strict GPU set, and 5.2% (CPU) and 12.2% (strict GPU) faster than the static HEFT plan. "\n'
        '    "The GPU helps the dispatcher (2.6% strict set, 7.5% extended set) but not blind B4. A hand rule that knows the cost parameter is within 1% of the dispatcher in every configuration, the policies tie when task cost does not vary, "\n'
        '    "end-to-end cost terms change nothing (equivalent within \\u00b12%), and a hybrid selector is not justified (maximum headroom 1.1%). The GPU cost estimate has 23\\u201331% median error. Earlier exploratory sessions "\n'
        '    "(hidden-cost workloads, an emulated remote worker) are reported as a first study; a Raspberry Pi has not been measured.",')

# ---- introduction
between('d.para("Reviews 1 and 2 surveyed the literature, patents and products and identified nine gaps', 'so that the next stage can be run without further code changes.")',
        'd.para("Reviews 1 and 2 surveyed the literature, patents and products and identified ten gaps, chiefly the lack of real-hardware evidence, overhead accounting, interval statistics, informed baselines and a like-for-like comparison "\n'
        '       "of static plans with dynamic dispatch for DAG scheduling on heterogeneous resources. Review 3 reports the implementation built to close them and the results obtained with it. The contributions are: (1) a reproducible runtime and experiment framework "\n'
        '       "for real task graphs on P/E cores, a CUDA GPU and an external worker; (2) a family of policies and estimators that includes the base idea B4, static HEFT and PEFT plans ({{heft,peft}}) and a predicted-rank dispatcher; "\n'
        '       "(3) a final benchmark of static against dynamic scheduling with one cost model, end-to-end timing and per-task GPU eligibility taken from measurements; (4) a measured map of when prediction helps, including the cases where it does not; "\n'
        '       "(5) a diagnosis of scheduling overhead; and (6) a prepared path for a Raspberry Pi worker, validated only by emulation.")')

# ---- final-study components (before the dispatch pass)
rep('d.h2("Dispatch pass of the coordinator")',
    'd.h2("Components added for the final benchmark")\n'
    'd.figure(FF + r"\\fig_final_architecture.png", "Final framework: one cost model and one GPU-eligibility table feed both the static planners and the dynamic dispatchers; the coordinator, event log and worker pools are shared.", 3.4)\n'
    'd.bullets([\n'
    '    "**End-to-end timing (amendment F1).** The end-to-end makespan runs from the start of `run()` to the last completion; initialisation and policy set-up are recorded separately, so the time a static plan needs to be computed is counted. The older makespan (first dispatch to last completion) is kept.",\n'
    '    "**Static baselines.** HEFT_param_model, PEFT_param_model and HEFT_E2E give every task a fixed worker before the run; an oracle plan from class-median costs is a reference only. Planned and actual makespan are logged.",\n'
    '    "**Dynamic policies.** B4_param_first sorts the ready queue by the cost parameter. PRED_RANK_GREEDY orders by predicted upward rank and binds only to an idle worker with the least predicted kernel time. PRED_RANK_GREEDY_E2E minimises predicted occupancy, i.e. transfer plus kernel plus set-up plus inter-process time.",\n'
    '    "**No double counting.** The CUDA stage time already contains the host-to-device copy, the kernel and the device-to-host copy (checked in the stage code); the end-to-end variant adds only artifact I/O and inter-process overhead.",\n'
    '    "**GPU eligibility.** `GpuRegion` makes a stage eligible for the CUDA worker only where a spike record shows a verified speed-up; a dropped row overrides a pass. Configurations: *cpu*, *gpu* (strict: the original record) and *ext* (strict plus denoise at verified iteration counts). No configuration is GPU-only.",\n'
    '    "**Separate data.** The cost model and the end-to-end terms are fitted on calibration sessions and checked on hold-out sessions; evaluation sessions come afterwards with new chain orders; the protocol and design hashes were logged before the first evaluation session.",\n'
    '])\n'
    'd.h2("Dispatch pass of the coordinator")')

# ---- dashboard
rep('on its last tab, any experiment session side by side (Fig. 2).")',
    'on its last tab, any experiment session side by side (Fig. 2). Two later versions live in separate packages and leave the original unchanged: v2 shows the local GPU with live load, memory, temperature and power, '
    'and the final results with hover tooltips; v3 adds a tab that runs one live block of the final benchmark with any final policy on the CPU or CPU+GPU and shows the tasks per pool and the output check.")')

# ---- inventory table
between('d.table("Implementation inventory', '[2.2, 0.55, 0.7], size=7)',
        'd.table("Implementation inventory (measured by counting lines in the repository)",\n'
        '        ["Part", "Files", "Lines of Python"],\n'
        '        [["Runtime package (src/caosched)", "107", "12,578"],\n'
        '         ["  core (coordinator, pools, DAG, tasks)", "", "2,026"],\n'
        '         ["  estimators; schedulers; analysis; experiment", "", "1,197; 845; 1,037; 1,126"],\n'
        '         ["  revival; study2 (earlier policies); final (static baselines, E2E dispatcher, GPU region)", "", "1,327; 680; 216"],\n'
        '         ["  dashboard (original; v2; v3); remote; dataset", "", "774; 202; 266; 571; 692"],\n'
        '         ["Scripts (experiments, analysis, profiling, runbooks)", "89", "9,709"],\n'
        '         ["Tests", "52", "7,263 (521 tests passed)"],\n'
        '         ["Version control", "71 commits", "branch revival/resource-state-aware; final-study files not committed"]],\n'
        '        [2.2, 0.55, 0.7], size=7)')

# ---- methodology: final workloads
rep('d.para("The machine is a laptop with an Intel Core i5-13500HX',
    'd.table("Workloads of the final benchmark (image pipeline of 257 tasks, 512 px; evaluation runs per session, included runs in brackets)",\n'
    '        ["Workload", "Heavy chains of 64 / iterations", "Runs"],\n'
    '        [["h16_l120 (primary)", "16 heavy, 120 vs 2 iterations (ratio 60)", "600 (576)"],\n'
    '         ["uniform", "none (no spread in task cost); cpu and gpu only", "208 (192)"],\n'
    '         ["h04_l120", "4 heavy, 120 iterations", "312 (288)"],\n'
    '         ["h40_l120", "40 heavy, 120 iterations", "312 (288)"],\n'
    '         ["h16_l40", "16 heavy, 40 iterations (ratio 20)", "312 (288)"],\n'
    '         ["h16_l15", "16 heavy, 15 iterations (ratio 7.5)", "312 (288)"]],\n'
    '        [0.9, 1.9, 0.6], size=7)\n'
    'd.para("The machine is a laptop with an Intel Core i5-13500HX')
rep('d.h2("Procedure and statistics")',
    'd.h2("Procedure and statistics")\n'
    'd.para("Final benchmark: eight policies (four dynamic, four static of which the oracle plan is a reference) in three hardware sets, one run of every condition per block in seeded random order, the first block of a session a warm-up. "\n'
    '       "Before every block the free memory had to exceed 2.4 GB at the start of a session and 0.8 GB per block, and the laptop had to be on mains power; these thresholds were never lowered, and attempts that failed the gate were kept on disk and never pooled. "\n'
    '       "The confirmatory family is the ten contrasts C1\\u2013C10 on the primary session under Holm correction with a \\u00b12% equivalence margin; the other five sessions are exploratory and unadjusted.")')

# ---- results: final benchmark first
rep('d.h2("Montage: a valid null result")',
    'd.h2("Final benchmark: primary workload")\n'
    'd.para("Table V gives the end-to-end makespan (geometric mean over 24 included blocks) of every policy in the three hardware sets; Fig. 3 adds the 95% intervals. In every set the three dynamic policies that use cost information "\n'
    '       "(B4 param-first, PRED, PRED-E2E) are within about 1% of each other and clearly faster than blind B4; the static HEFT plan is 5% to 12% slower than PRED, and PEFT is the slowest static plan. All 576 included runs of the session had verified output.")\n'
    'd.table("Primary workload h16_l120: end-to-end makespan in seconds (geometric mean, 24 blocks)",\n'
    '        ["Policy", "CPU only", "Strict GPU", "Extended GPU"], fd.primary_table_rows(), [1.5, 0.6, 0.6, 0.7], size=7)\n'
    'd.figure(FF + r"\\fig_final_makespan.png", "End-to-end makespan of each policy in the three hardware sets on the primary workload (geometric mean, 95% interval, 24 blocks).", 3.4)\n'
    'd.para("The ten confirmatory contrasts are in Table VI and Fig. 4. Predictions written before the data held for C1, C2, C7, C9 and C10. C3 and C4 had been predicted inconclusive or equivalent; the dynamic policy was about 5% faster, "\n'
    '       "so that prediction was wrong. C5, C6 and C8 had no stated expectation.")\n'
    'd.table("Confirmatory contrasts (Holm family of ten; effect on end-to-end makespan, negative = first policy faster)",\n'
    '        ["Id", "Contrast", "Effect % [95% CI]", "Holm p", "Result"], fd.confirmatory_rows(), [0.3, 1.4, 1.1, 0.4, 0.7], size=6.5)\n'
    'd.figure(FF + r"\\fig_final_forest.png", "Confirmatory contrasts C1\\u2013C10 with 95% intervals; the grey band is the \\u00b12% equivalence margin.", 3.4)\n'
    'd.h2("Final benchmark: six workloads")\n'
    'd.para("The effect depends on how much task cost varies (Fig. 5, exploratory outside the primary session). Against static HEFT the dynamic policy gains 0.2% to 5.2% on the CPU and 3.7% to 17.1% with the strict GPU set; against blind B4 it gains almost 40% when only 4 of 64 chains are heavy, "\n'
    '       "2.8% to 4.8% when 40 are heavy or the cost ratio is 20, and nothing on the uniform workload (+0.0% [\\u22122.5, +2.3] on the CPU; \\u22120.0% [\\u22121.3, +1.1] with the strict GPU set). With the lowest cost ratio (7.5) the dynamic policy is slightly slower than B4 with the strict GPU set (+1.1% [+0.3, +1.9]).")\n'
    'd.figure(FF + r"\\fig_final_workloads.png", "PRED against static HEFT (left) and blind B4 (right) on the six workloads, CPU only (blue) and with the strict GPU set (orange); exploratory except the first row.", 3.4)\n'
    'd.h2("Final benchmark: GPU, cost-model error and end-to-end terms")\n'
    'd.para("The GPU helps only where it is used with a cost model: for PRED the strict set is 2.6% [\\u22123.3, \\u22121.7] and the extended set 7.5% [\\u22127.8, \\u22127.2] faster than the CPU only, while blind B4 is 1.6% *slower* with the strict set (C10, inconclusive) and 2.8% slower with the extended set. "\n'
    'u\'\'\n'
    '       "Under the model-based policies the CUDA worker takes about 15% to 20% of the 257 tasks (Fig. 6). One CUDA worker is a single narrow resource.")\n'
    'd.figure(FF + r"\\fig_final_placement.png", "Tasks run on the CPU and on the GPU per policy (extended set, primary workload) and the GPU busy fraction.", 3.4)\n'
    'd.para("**Model error.** On hold-out sessions never used for fitting, CPU stages are predicted with a median error of 4% to 11%, GPU stages with 23% to 31% (Fig. 7). The GPU estimate is the weakest part of the model: a static plan commits to it in advance, a dynamic policy uses it only when a worker is idle, "\n'
    '       "so part of the dynamic-versus-static gap on the GPU sets may reflect model error and not only the timing of decisions; this was not separated experimentally. "\n'
    '       "**End-to-end terms.** Adding set-up and inter-process terms changed nothing: PRED-E2E against PRED is +0.6% [+0.1, +1.3] on the CPU (C2) and \\u22120.0% [\\u22120.7, +0.5] with the strict GPU set (C7), both equivalent within \\u00b12%; on the uniform workload with the strict set it was +2.9% [+0.4, +5.9] slower than B4. "\n'
    '       "**Timing convention.** The difference between the end-to-end and the old makespan is 12.5 ms (B4), 29.2 ms (PRED), 40.7 ms (HEFT) and 81.3 ms (PEFT) on a makespan of about 3 to 4 s, so no conclusion flips between the two conventions.")\n'
    'd.figure(FF + r"\\fig_final_model_error.png", "Median absolute error of the cost model on hold-out tasks, by stage and pool.", 3.4)\n'
    'd.h2("Final benchmark: what limits the claim")\n'
    'd.bullets([\n'
    '    "**A simple rule gets almost all of the gain.** PRED against B4 param-first (the queue sorted by the cost parameter) is \\u22120.4% [\\u22120.9, +0.1] on the CPU, \\u22120.6% [\\u22121.1, \\u22120.0] with the extended set and \\u22120.2% [\\u22120.9, +0.7] with the strict set (exploratory): under 1% in every set.",\n'
    '    "**A hybrid selector is not justified.** In 17 development cells the maximum headroom of a B4-or-PRED selector was 1.1%, the mean 0.08%, and no cell exceeded the 2% margin, so none was built.",\n'
    '    "**Two sessions disagree.** The earlier overnight session found HEFT level with the dispatcher (+1.10% [\\u22120.53, +2.81], old timing convention, other chain orders); the final session finds PRED about 5% faster. The timing convention does not explain it; the difference was not isolated and both results are reported.",\n'
    '    "**Scope.** One machine, one workload family, 512 px, one CUDA worker; only the primary session is confirmatory; the remote worker was not rerun with the final policies.",\n'
    '])\n'
    'd.h2("Earlier study: Montage and hidden-cost workloads")\n'
    'd.h2("Montage: a valid null result")')

# the stray marker line above is removed (placeholder used to keep the text readable in the patch)
s = s.replace("u''\n", "")

# ---- summary of claims table
between('d.table("Claim status after the project (50 registered claims; selection)",', '[0.8, 2.6], size=7)',
        'd.table("Claim status after the project (50 registered claims of the earlier study plus the final benchmark; selection)",\n'
        '        ["Status", "Claim"],\n'
        '        [["Supported", "dynamic PRED beats blind B4 by 17.8% (CPU) and 21.2% (strict GPU); beats a static HEFT plan from the same model by 5.2% and 12.2%; the GPU helps PRED (2.6% strict, 7.5% extended); end-to-end terms are equivalent; earlier study: rank-ordered dispatch beats B4 by 19\\u201328% on cost-skewed workloads"],\n'
        '         ["Not established", "advantage over an informed rule (within 1%); a hybrid selector; GPU benefit for blind B4; remote offloading benefit; Raspberry Pi results; any claim beyond this machine and workload family"],\n'
        '         ["Not supported / null", "gain on Montage; gain on the two-factor workload; gain on the uniform workload; remote worker helping EFT at level 30"]],\n'
        '        [0.8, 2.6], size=7)')

# ---- sessions table
rep('d.table("Timed sessions of the final study (all outputs verified; hashes of event logs checked)",',
    'd.table("Timed sessions (all included outputs verified; hashes of event logs checked)",')
rep('["Emulated remote pool, level 30", "1", "13", "65", "emulation"],',
    '["Final study: calibration (cal_l15, cal_l40, cal_l120, cal_uniform) and hold-out (hold_l40, hold_l120), completed retries", "6", "\\u2013", "99 + 28", "real"],\n'
    '         ["Final study: evaluation, six workloads", "6", "25, 13 \\u00d7 5", "600, 208, 312 \\u00d7 4", "real"],\n'
    '         ["Emulated remote pool, level 30", "1", "13", "65", "emulation"],')
rep('["Analysis tool labels the primary family “confirmatory” by default", "review", "documented; overnight sessions stay exploratory by plan"]],',
    '["Analysis tool labels the primary family “confirmatory” by default", "review", "documented; overnight sessions stay exploratory by plan"],\n'
    '         ["Final-study stage 1 aborted when the laptop was unplugged, on retry-id collisions and on low free memory (antivirus, Docker, WSL)", "run logs", "mains wait and first-unused-id logic added; the 2.4 GB and 0.8 GB thresholds were never lowered; aborted attempts kept (_r2 \\u2026 _r8), never pooled"],\n'
    '         ["Static plans were timed from the first dispatch, hiding their planning time", "design review", "end-to-end makespan (amendment F1); old metric kept"]],')
rep('d.h2("Readiness for the Raspberry Pi stage")', 'd.h2("Raspberry Pi path (prepared, not measured)")')

# ---- discussion
between('d.para("**Mechanism.** The dominant effect is ordering', 'the gain over B4 changes by under one point.")',
        'd.para("**Mechanism.** The dominant effect is ordering and informed placement: serving predicted-heavy work first removes the tail created by blind dispatch, and sending only verified stages to the GPU adds a smaller gain. "\n'
        '       "That is why a rule that knows the cost parameter is within 1% of the dispatcher and why the effect depends on the spread of task cost. A dynamic policy also beats a static plan from the same model, "\n'
        '       "by 5% on the CPU and 12% with a strict GPU set: the static plan cannot react to the actual completion order, and its GPU assignments inherit the 23\\u201331% model error in advance. "\n'
        '       "**Prediction accuracy is not enough:** remote predictions were accurate to under 1% yet gave no gain, in line with the finding of {{ilyushkin}} that order can matter more than estimate accuracy. "\n'
        '       "**Overhead matters but did not decide the result.** Scheduling time is 2% to 5% of these 3 to 9 second runs for late-binding policies; in the final benchmark policy set-up is 19 ms (PRED), 30 ms (HEFT) and 71 ms (PEFT).")')

# ---- existing vs proposed table
between('d.table("Differentiation between the existing (base) implementation and the proposed one",', '[0.9, 1.25, 1.3], size=7)',
        'd.table("Differentiation between the existing (base) implementation and the proposed one",\n'
        '        ["Aspect", "Existing (B4 / base patent idea)", "Proposed"],\n'
        '        [["Order of ready tasks", "first-come first-served", "predicted upward rank"],\n'
        '         ["Worker choice", "first idle eligible worker (P before E)", "idle eligible worker with least predicted time (CPU or verified GPU stages)"],\n'
        '         ["Cost knowledge", "none", "model learned from logs; retrained by one command"],\n'
        '         ["Decision cost per run", "7 ms (coordinator 0.20 s)", "15 ms (coordinator 0.10 s); policy set-up 19 ms"],\n'
        '         ["Makespan, primary workload", "reference", "\\u221217.8% (CPU), \\u221221.2% (strict GPU) vs B4; \\u22125.2% and \\u221212.2% vs static HEFT"],\n'
        '         ["Makespan, nothing hidden", "reference", "+0.0% (equivalent within \\u00b12%)"],\n'
        '         ["Evidence", "\\u2014", "real runs, end-to-end timing, paired intervals, ten Holm-adjusted contrasts, 521 tests"]],\n'
        '        [0.9, 1.25, 1.3], size=7)')

# ---- conclusion
between('d.para("The implementation delivers a reproducible framework', 'and (5) obtain a professional prior-art search before any IPR filing.")',
        'd.para("The implementation delivers a reproducible framework and a measured account of static against dynamic scheduling on a hybrid CPU+GPU laptop: dynamic dispatch with a cheap cost model is 5% to 12% faster than a static plan "\n'
        '       "from the same model and about 18% to 21% faster than blind dispatch when task cost varies; it ties blind dispatch when it does not; a rule that knows the cost parameter gets almost the same result; and the GPU helps only with a cost model. "\n'
        '       "Next: (1) a second workload family; (2) a GPU cost model with lower error and a test that separates model error from decision timing; (3) the remote worker with the final policies, then a Raspberry Pi over a real link with the prepared runbook; "\n'
        '       "(4) apply and test the dispatch-loop fix in the source and commit the final study; and (5) obtain a professional prior-art search before any IPR filing.")')
open(p, "w", encoding="utf-8").write(s)
print("patched r3")
