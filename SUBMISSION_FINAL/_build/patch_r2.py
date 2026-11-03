p = "build_review2.py"
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


# (a) abstract
between('From this redo and from the literature survey we derive nine gaps', 'delimit the contribution honestly.",',
        'From this redo and from the literature survey we derive ten gaps and propose a *prediction-aware, work-conserving, rank-ordered dispatcher* "\n'
        '    "driven by a generic runtime model learned from execution logs, evaluated with overhead accounting and paired statistics against static HEFT and PEFT plans built from the same model. "\n'
        '    "The proposed work has since been executed as a final benchmark (frozen protocol, ten Holm-adjusted contrasts, 24 included blocks on the primary workload, CPU and RTX 3050 GPU): the dynamic dispatcher is 17.8% faster than blind B4 on the CPU "\n'
        '    "and 5.2% (CPU) to 12.2% (strict GPU set) faster than a static HEFT plan from the same model, but within 1% of a hand rule that knows the cost-relevant parameter, and equal to B4 where task cost does not vary. "\n'
        '    "These measured limits delimit the contribution honestly.",')

# (b) introduction
rep('leaving the Raspberry Pi stage as an explicit extension.")',
    'leaving the Raspberry Pi stage out of scope (it was never measured). Since the first version of this review the proposed work has been executed as a final static-versus-dynamic benchmark; Section V-H gives its design and Review 3 its results.")')

# (c) gap table
rep('"Prepared: external node path, runbook; not yet run"]],',
    '"Prepared; emulation only, no Raspberry Pi or real-network result"],\n'
    '         ["G10 Static plan vs dynamic dispatch not compared end to end", "HEFT is a baseline in 5 of 13 papers, all in simulation; earlier session: HEFT level with the dispatcher (+1.10%, old timing convention)", "Yes: final benchmark, one cost model on both sides, end-to-end timing, CPU and GPU"]],')
rep('Table IV merges the evidence', 'Table IV merges the evidence')

# (d) hypotheses
rep('"**H4** Accurate predictions are not sufficient for gain: offloading to a remote worker pays only if transfer cost is small relative to compute and the remote worker adds capacity.",\n])',
    '"**H4** Accurate predictions are not sufficient for gain: offloading to a remote worker pays only if transfer cost is small relative to compute and the remote worker adds capacity.",\n'
    '    "**H5** With the *same* cost model on both sides, the dynamic dispatcher is not slower than a static HEFT plan on the CPU and is faster when a CUDA worker is added (stated before the data: CPU result inconclusive or equivalent).",\n'
    '    "**H6** Using the GPU only for stages whose speed-up was verified helps the model-driven dispatcher, but does not help blind B4.",\n'
    '    "**H7** A hybrid selector between B4 and the dispatcher is worth building only if its headroom exceeds the \\u00b12% margin in the development cells.",\n])')

# (e) final benchmark design, before the requirements subsection
rep('d.h2("Requirements derived from the gaps")',
    'd.h2("Final benchmark design (executed)")\n'
    'd.para("The final benchmark fixes the protocol before the evaluation sessions. *Static* policies compute a complete plan before the run: HEFT and PEFT with the learned model (HEFT_param_model, PEFT_param_model), HEFT with end-to-end cost terms (HEFT_E2E), and an oracle plan from class-median costs used only as a reference. "\n'
    '       "*Dynamic* policies decide when a worker is idle: B4, B4 with the queue sorted by the cost parameter (B4_param_first), the predicted-rank dispatcher (PRED_RANK_GREEDY) and a variant that minimises predicted occupancy, transfer plus kernel plus set-up plus inter-process time (PRED_RANK_GREEDY_E2E). "\n'
    '       "Hardware sets are CPU only (6 P and 7 E workers), a strict GPU set (the CUDA worker takes only stages whose speed-up was verified on the original spike record) and an extended set (denoise at further verified iteration counts). "\n'
    '       "The primary workload has 16 heavy chains of 64; five further workloads vary the heavy count, the cost ratio and the uniform case. The end-to-end makespan runs from the start of the run to the last completion, so start-up and policy set-up are inside the number (amendment F1). "\n'
    '       "Ten contrasts on the primary session (C1\\u2013C10) form the confirmatory family under Holm correction; everything else is exploratory.")\n'
    'd.table("Confirmatory contrasts fixed in the protocol and their outcome (primary workload, 24 blocks)",\n'
    '        ["Id", "Contrast", "Effect % [95% CI]", "Result"],\n'
    '        [["C1", "PRED vs B4 (CPU)", "\\u221217.8 [\\u221218.8, \\u221216.7]", "faster"],\n'
    '         ["C2", "PRED-E2E vs PRED (CPU)", "+0.6 [+0.1, +1.3]", "equivalent"],\n'
    '         ["C3", "PRED vs HEFT (CPU)", "\\u22125.2 [\\u22125.9, \\u22124.6]", "faster"],\n'
    '         ["C4", "PRED-E2E vs HEFT-E2E (CPU)", "\\u22125.2 [\\u22126.0, \\u22124.5]", "faster"],\n'
    '         ["C5", "PRED vs HEFT (strict GPU)", "\\u221212.2 [\\u221213.4, \\u221211.1]", "faster"],\n'
    '         ["C6", "PRED-E2E vs HEFT-E2E (strict GPU)", "\\u22128.5 [\\u22129.7, \\u22127.6]", "faster"],\n'
    '         ["C7", "PRED-E2E vs PRED (strict GPU)", "\\u22120.0 [\\u22120.7, +0.5]", "equivalent"],\n'
    '         ["C8", "PRED vs B4 (strict GPU)", "\\u221221.2 [\\u221222.6, \\u221219.7]", "faster"],\n'
    '         ["C9", "PRED strict GPU vs PRED CPU", "\\u22122.6 [\\u22123.3, \\u22121.7]", "faster"],\n'
    '         ["C10", "B4 strict GPU vs B4 CPU", "+1.6 [+0.2, +3.0]", "inconclusive"]],\n'
    '        [0.3, 1.6, 1.0, 0.55], size=7)\n'
    'd.h2("Requirements derived from the gaps")')

# (f) results to date
rep('d.h2("Preliminary results and plan")', 'd.h2("Results to date and plan")')
between('d.para("Preliminary measurements (Review 3 gives details)', 'd.table("Hypotheses, the experiment that tests each',
        'd.para("Measurements (Review 3 gives details) support H1\\u2013H3: on twenty chain orders not used before the dispatcher was 19.3% (6P+7E) and 20.5% (2P+7E) shorter than B4, within \\u00b11.6% of the informed rule, "\n'
        '       "and within \\u00b12% of B4 on the uniform batch. H4 was supported in emulation. The final benchmark adds H5\\u2013H7: the dispatcher is faster than a static HEFT plan from the same model (5.2% on the CPU, 12.2% with the strict GPU set), "\n'
        '       "the GPU helps the dispatcher by 2.6% (strict set) to 7.5% (extended set) but not blind B4, and a hybrid selector is not justified. Two results limit the claim: a hand rule that sorts by the cost parameter is within 1% of the dispatcher "\n'
        '       "in every configuration, and the earlier overnight session found HEFT level with the dispatcher (+1.10%, different orders and timing convention); the difference was not isolated. The remaining plan: (1) finish the paper drafts; "\n'
        '       "(2) a second workload family; (3) publish code and data after the IPR decision. The Raspberry Pi stage is out of scope.")\n', include_b=False)
rep('"predicted vs measured remote time 0.1457 vs 0.1464 s; remote worker made EFT 3.8% slower"]],',
    '"predicted vs measured remote time 0.1457 vs 0.1464 s; remote worker made EFT 3.8% slower"],\n'
    '         ["H5 dynamic vs static, same model", "C3, C5 (primary workload, 24 blocks)", "\\u22125.2% [\\u22125.9, \\u22124.6] CPU; \\u221212.2% [\\u221213.4, \\u221211.1] strict GPU; stated expectation for the CPU contrast (inconclusive or equivalent) was wrong"],\n'
    '         ["H6 GPU where verified", "C9, C10", "PRED \\u22122.6% [\\u22123.3, \\u22121.7]; B4 +1.6% [+0.2, +3.0], inconclusive"],\n'
    '         ["H7 hybrid selector", "headroom in 17 development cells", "maximum 1.1%, none above 2%: not justified, not built"]],')
rep('["Runtime, estimators, policies, experiment framework, dashboard", "done; 488 automated tests pass"],',
    '["Runtime, estimators, policies, experiment framework, dashboard", "done; 521 automated tests pass"],')
rep('["Raspberry Pi 5 real-link experiment", "planned (hardware pending)"],\n         ["Second workload family; clean-tree rerun of the headline result", "planned"]],',
    '["Final static-vs-dynamic benchmark (calibration, hold-out, six workloads, CPU and GPU)", "done; confirmatory family reported"],\n'
    '         ["Raspberry Pi 5 real-link experiment", "out of scope; emulation only"],\n'
    '         ["Second workload family; clean-tree rerun of the headline result", "planned"]],')

# (g) conclusion
rep('Nine gaps were identified and a prediction-aware', 'Ten gaps were identified and a prediction-aware')
rep('"proposed. Its measured benefit is real but conditional, which is what the proposed study set out to quantify.")',
    '"proposed. Its measured benefit is real but conditional, which is what the proposed study set out to quantify: it beats blind dispatch by about 18% and a static plan from the same model by 5% to 12% when task cost varies, "\n'
    '       "and a simple rule that knows the cost parameter gets almost the same result.")')
open(p, "w", encoding="utf-8").write(s)
print("patched r2")
