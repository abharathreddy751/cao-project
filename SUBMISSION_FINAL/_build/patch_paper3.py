p = "build_paper_final.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


def before(anchor, new):
    global s
    assert anchor in s, anchor[:70]
    s = s.replace(anchor, new + anchor, 1)


rep("the 59-task Montage mosaic ({{montage,wfcommons}}; native Windows build,", "the 59-task Montage mosaic {{montage,wfcommons}} (native Windows build,")

# more figures of the earlier study
before('    d.para("**Overhead and a defect found while measuring it.**',
       '    d.nextlabel = "perorder"\n'
       '    d.figure(FIG + r"\\fig_per_order.png", "Earlier study: change in makespan of the dispatcher against B4 (blue) and the hand rule (green) for each chain order not used before (12 orders left, 8 orders right).", 3.4)\n'
       '    d.nextlabel = "mkearly"\n'
       '    d.figure(FIG + r"\\fig_makespan_policies.png", "Earlier study: mean makespan by policy on unseen chain orders (geometric means with 95% intervals): 12 orders on 6P+7E (left), 8 orders on 2P+7E (right).", 3.4)\n')

# implementation, incidents, claims: before the Conclusion
before('    d.h1("Conclusion")\n',
       '    d.h2("Implementation and tests")\n'
       '    d.para("The framework is Python on Windows. @tab:inv lists its size; the 521 automated tests (run before the dashboard variants were added) cover the coordinator contract, the estimators, the static planners (including the published worked examples), the final policies, GPU eligibility, the statistics and the claims registry, which is re-read against the stored tables by a test. "\n'
       '           "A local web dashboard shows the system state, a replay of runs and the stored results; two later versions in separate packages show the GPU with live load and add a tab that runs one live block of the final benchmark.")\n'
       '    d.nextlabel = "inv"\n'
       '    d.table("Implementation inventory (lines of Python counted in the repository)",\n'
       '            ["Part", "Files", "Lines"],\n'
       '            [["Runtime package (src/caosched)", "107", "12,578"], ["  core: coordinator, pools, DAG, tasks", "13", "2,026"], ["  estimators; schedulers; analysis; experiment", "", "1,197; 845; 1,037; 1,126"],\n'
       '             ["  final study: static baselines, E2E dispatcher, GPU region", "4", "216"], ["  dashboard (original; v2; v3)", "", "774; 202; 266"],\n'
       '             ["Scripts", "89", "9,709"], ["Tests", "52", "7,263"]], [2.2, 0.5, 0.9], size=7)\n'
       '    d.h2("Incidents and defects")\n'
       '    d.para("Defects and operational incidents are recorded rather than hidden (@tab:inc). None of them changed a reported number: runs that failed a gate were kept on disk and never pooled.")\n'
       '    d.nextlabel = "inc"\n'
       '    d.table("Defects and incidents found during the work and what was done",\n'
       '            ["Item", "Found by", "Action"],\n'
       '            [["Static plans were timed from the first dispatch, hiding their planning time", "design review", "end-to-end makespan (amendment F1); old metric kept"],\n'
       '             ["Stage 1 aborted when the laptop was unplugged, on retry-id collisions and on low free memory (antivirus, Docker, WSL)", "run logs", "mains wait and first-unused-id logic; the 2.4 GB and 0.8 GB thresholds were never lowered; aborted attempts kept (_r2 \\u2026 _r8)"],\n'
       '             ["Learned model applied to a profile it was not fitted on", "audit of earlier phases", "profile binding recorded in the model; refusal on mismatch"],\n'
       '             ["Worker-pool rebuild between conditions created cold workers", "pilot analysis", "one pool for all conditions"],\n'
       '             ["Idle CUDA worker defeats the dispatch loop\\u2019s early exit", "overhead diagnosis", "quantified; fix in a separate adapter; not applied to the source"],\n'
       '             ["Remote node served one client then exited", "loopback rehearsal", "persistent mode and test"]],\n'
       '            [1.7, 0.7, 1.1], size=6.5)\n'
       '    d.h2("Status of the claims")\n'
       '    d.nextlabel = "claims"\n'
       '    d.table("Claim status after the project (selection)",\n'
       '            ["Status", "Claim"],\n'
       '            [["Supported", "dynamic PRED beats blind B4 by 17.8% (CPU) and 21.2% (strict GPU); beats a static HEFT plan from the same model by 5.2% and 12.2%; the GPU helps PRED (2.6% strict, 7.5% extended); end-to-end terms are equivalent"],\n'
       '             ["Not established", "advantage over a rule that knows the cost parameter (within 1%); a hybrid selector; GPU benefit for blind B4; a remote-offloading benefit; Raspberry Pi results; any claim beyond this machine and workload family"],\n'
       '             ["Not supported / null", "gain on Montage, on the uniform and light workloads and on the two-factor workload; a remote worker helping EFT at compute level 30"]],\n'
       '            [0.8, 2.7], size=6.5)\n')

# appendix D: environment and commands
before('    o = OUT + "\\\\" + name\n',
       '    d.h1_plain("Appendix D. Environment and commands")\n'
       '    d.para("**Environment.** Intel Core i5-13500HX, NVIDIA GeForce RTX 3050 6 GB (driver 581.83), 15.7 GB RAM, Windows 11, Python 3.11.9, PyTorch 2.11 with the CUDA 12.8 build; sessions need mains power and at least 2.4 GB of free memory (0.8 GB per block). "\n'
       '           "**Commands (PowerShell, repository root).** `scripts/final_stage1.ps1` (calibration sessions, models, designs, smoke test); `scripts/final_stage2.ps1` (six evaluation sessions and their analyses); `scripts/final_analyze.py <session> --confirmatory` (primary session); "\n'
       '           "`scripts/final_results_table.py`, `scripts/final_cross_workload.py`, `scripts/final_hybrid_check.py`, `scripts/final_build_report.py`; tests: `python -m pytest -q`. "\n'
       '           "Hashes of the protocol, the designs and the models are in `data/results/final_20261101/ACTIVITY_LOG.md`.")\n')
open(p, "w", encoding="utf-8").write(s)
print("paper3 patched")
