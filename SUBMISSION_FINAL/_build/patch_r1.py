p = "build_review1.py"
s = open(p, encoding="utf-8").read()


def rep(old, new, count=1):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, count)


rep('"overhead or a statistical interval, and none compares against an *informed* simple rule. These gaps motivate a measured, overhead-accounted study on real hardware.",',
    '"overhead or a statistical interval, and none compares against an *informed* simple rule. These gaps motivate a measured, overhead-accounted study on real hardware; "\n'
    '    "the closing section records how the project\\u2019s final benchmark of static plans against dynamic dispatch on a CPU+GPU laptop answers each gap.",')
rep('"statistics. Sections III to V compare publications, patents and company products. Section VI summarises technology trends and Section VII lists the gaps the project addresses.")',
    '"statistics. Sections III to V compare publications, patents and company products. Section VI summarises technology trends and their adoption status, and Section VII lists the gaps and records the status of each after the final benchmark. "\n'
    '       "The final benchmark asks a sharper version of the question: does a *dynamic* scheduler, which decides while the workflow runs, finish sooner than a *static* plan computed beforehand from the same cost model, on a hybrid CPU+GPU workstation?")')

rep('d.h2("Strengths and weaknesses by family")',
    'd.h2("Static versus dynamic scheduling")\n'
    'd.para("The classical list schedulers HEFT and PEFT ({{heft,peft}}) are *static*: they compute, before execution, a processor and a start time for every task from a cost matrix. A static plan commits to its estimates; "\n'
    '       "when a task finishes earlier or later than planned, the assignment does not change. *Dynamic* schedulers decide when a worker becomes idle or a task becomes ready. StarPU ({{starpu}}) is the established runtime "\n'
    '       "of this kind for CPU/GPU task graphs and calibrates history-based performance models; the learned schedulers of Section III are dynamic as well. Two observations from the survey matter for the project. First, HEFT is "\n'
    '       "used as a baseline in five of the 13 papers, always in simulation, so the cost of *planning itself* and the plan\\u2019s error against real execution are not observed. Second, we found no paper that gives the static and the dynamic scheduler "\n'
    '       "the *same* runtime model and measures both end to end, including start-up and scheduling time, which is the comparison needed to say what dynamic decisions add. The final benchmark of the project (Review 3) is designed for this comparison.")\n'
    'd.h2("Strengths and weaknesses by family")')

rep('# ------------------------------------------------------------------ VII',
    'd.table("Technology trends: introduction and adoption status (as documented in the cited sources)",\n'
    '        ["Trend", "Introduced / state", "Adoption status", "Relevance to the project"],\n'
    '        [["Hybrid P/E cores with hardware scheduling hints", "Thread Director listed for 12th\\u201314th generation Core ({{intel_td}})", "mainstream in client CPUs; OS-level use", "the test machine has 6 P and 8 E cores; core type changes task time by 2.8\\u20133.6 times"],\n'
    '         ["On-device accelerators (GPU, NPU)", "NPU of 40 TOPS or more required for Copilot+ PCs ({{copilot}})", "shipping in consumer laptops", "a laptop exposes three engine types; the project uses the CUDA GPU as one worker"],\n'
    '         ["Energy-aware scheduling", "Linux EAS for asymmetric CPUs ({{linux_eas}})", "production kernels, with stated limits", "context for a later energy metric; not measured here"],\n'
    '         ["Learned DAG scheduling (GNN, DRL)", "LACHESIS to GNN+PPO and meta-RL ({{lachesis,tan25,metarl}})", "research; evaluated in simulation (2 of 13 papers use hardware)", "the project tests a much cheaper model on real execution"],\n'
    '         ["LLM-agent schedulers", "2025\\u20132026 preprints ({{lureda,agentxpu}})", "early research, small DAGs", "not evaluated; noted as a direction"],\n'
    '         ["Runtime performance models for task graphs", "StarPU history models ({{starpu}}); Lotaru ({{lotaru}})", "established runtime; prediction results in simulation", "same idea, tested with a ridge model and overhead accounting"],\n'
    '         ["Edge boards as remote workers", "Raspberry Pi 5 ({{rpi5}})", "widely available", "emulated in the project; no real-link result"]],\n'
    '        [0.85, 1.0, 0.85, 0.95], size=6.5)\n\n'
    '# ------------------------------------------------------------------ VII')

rep('"(paired intervals, multiplicity control); **G4** baselines that include informed simple rules and the HEFT/PEFT family; **G5** generalisation across workload instances; **G6** separation of prediction accuracy "\n'
    '       "from scheduling value; **G7** real remote execution (Raspberry Pi) beyond simulation.")',
    '"(paired intervals, multiplicity control); **G4** baselines that include informed simple rules and the HEFT/PEFT family; **G5** generalisation across workload instances; **G6** separation of prediction accuracy "\n'
    '       "from scheduling value; **G7** real remote execution (Raspberry Pi) beyond simulation; **G8** a like-for-like comparison of static plans and dynamic dispatch with one cost model and end-to-end timing. "\n'
    '       "The table also states the status after the project\\u2019s final benchmark (Review 3).")')
rep('["Gap", "Evidence in the survey", "Project response"],', '["Gap", "Evidence in the survey", "Project response and status"],')
rep('"native Windows runtime, P/E pools, CUDA worker; real Montage and image workloads"]', '"closed on one laptop: native Windows runtime, P/E pools, CUDA worker; real Montage and image workloads; six workloads in the final benchmark"]')
rep('"per-dispatch and coordinator scheduling time logged in every run"]', '"closed: per-dispatch and coordinator scheduling time logged; end-to-end makespan includes start-up and policy set-up"]')
rep('"paired log-ratio bootstrap, Holm correction, pre-registered designs"]', '"closed: paired log-ratio bootstrap, Holm correction over ten pre-stated contrasts, frozen protocol"]')
rep('"B0–B5, EFT ladder, HEFT, PEFT and an informed hand rule"]', '"closed: B0–B5, EFT ladder, HEFT, PEFT, HEFT-E2E and a parameter-aware hand rule; the hand rule came within 1% of the dynamic policy"]')
rep('"twenty unseen chain orders, dose and heavy-count sweeps"]', '"partly closed: twenty unseen chain orders earlier, six workloads in the final benchmark; one workload family only"]')
rep('"accurate remote predictions that still gave no gain are reported"]', '"closed: accurate remote predictions that gave no gain; GPU model error 23\\u201331% reported next to scheduling results"]')
rep('"node/proxy path, loopback emulation labelled as such, Raspberry Pi runbook"]],',
    '"open: node/proxy path and loopback emulation only, labelled as such; no Raspberry Pi or real-network result"],\n'
    '         ["G8 static vs dynamic", "HEFT used as a baseline in 5 of 13 papers, all in simulation", "closed for this workload family: same ridge model on both sides; dynamic PRED faster than static HEFT by 5.2% (CPU) and 12.2% (strict GPU)"]],')
open(p, "w", encoding="utf-8").write(s)
print("patched")
