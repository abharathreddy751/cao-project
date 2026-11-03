p = "build_paper_final.py"
s = open(p, encoding="utf-8").read()


def before(anchor, new):
    global s
    assert anchor in s, anchor[:70]
    s = s.replace(anchor, new + anchor, 1)


# ---- design decisions (method)
before('    # ------------------------------------------------------------------ IV\n',
       '    d.h2("Design decisions")\n'
       '    d.bullets([\n'
       '        "**One cost model for both sides.** Static and dynamic policies use the same ridge model, so a difference between them is a difference in *when and how the estimates are used*, not in how good the estimates are.",\n'
       '        "**End-to-end makespan as the primary metric.** A static plan has a planning cost that the first-dispatch convention hides; the end-to-end metric charges it (12.5 ms to 81.3 ms here).",\n'
       '        "**A strict GPU gate.** A stage is allowed on the GPU only where a measured speed-up exists, which keeps the comparison from being decided by a bad GPU placement rule; the extended set adds only iteration counts verified on a second record.",\n'
       '        "**A parameter-aware baseline.** B4_param_first is the simplest policy that knows what the model knows; it tests whether learning is needed at all.",\n'
       '        "**An oracle only as a reference.** HEFT_oracle uses class-median costs and is not a bound; no policy is compared against hindsight.",\n'
       '        "**A decision rule for the hybrid.** A B4-or-PRED selector would be built only if its headroom exceeded the \\u00b12% margin in the development cells; it did not, so none was built and no held-out hybrid session was run.",\n'
       '    ])\n')

# ---- workload by workload + planned vs actual (results)
before('    d.h2("A simple rule and a hybrid selector")\n',
       '    d.h2("Workload by workload")\n'
       '    mk = fd.makespan\n'
       '    d.para(f"**Uniform (no spread in cost).** All policies are within a few percent: on the CPU B4 {mk(\'uniform\', \'cpu\', \'B4\', 2)} s, B4 param-first {mk(\'uniform\', \'cpu\', \'B4_param_first\', 2)} s, PRED {mk(\'uniform\', \'cpu\', \'PRED_RANK_GREEDY\', 2)} s, HEFT {mk(\'uniform\', \'cpu\', \'HEFT_param_model\', 2)} s; there is nothing to order and the dispatcher ties blind dispatch (+0.0% [\\u22122.5, +2.3]). "\n'
       '           f"**Four heavy chains (h04_l120).** The heavy chains decide the critical path; blind B4 starts them late or on a slow core and takes {mk(\'h04_l120\', \'cpu\', \'B4\', 2)} s against {mk(\'h04_l120\', \'cpu\', \'PRED_RANK_GREEDY\', 2)} s for PRED (\\u221239.4%); the static HEFT plan is also close ({mk(\'h04_l120\', \'cpu\', \'HEFT_param_model\', 2)} s). "\n'
       '           f"**Forty heavy chains (h40_l120).** Most work is heavy, so order matters less: B4 {mk(\'h40_l120\', \'cpu\', \'B4\', 2)} s, PRED {mk(\'h40_l120\', \'cpu\', \'PRED_RANK_GREEDY\', 2)} s, HEFT {mk(\'h40_l120\', \'cpu\', \'HEFT_param_model\', 2)} s. "\n'
       '           f"**Lower cost ratios (h16_l40, h16_l15).** With ratios of 20 and 7.5 the gaps shrink: on the CPU PRED is {mk(\'h16_l40\', \'cpu\', \'PRED_RANK_GREEDY\', 2)} s against B4 {mk(\'h16_l40\', \'cpu\', \'B4\', 2)} s at ratio 20 and {mk(\'h16_l15\', \'cpu\', \'PRED_RANK_GREEDY\', 2)} s against {mk(\'h16_l15\', \'cpu\', \'B4\', 2)} s at ratio 7.5, while the strict GPU set still separates the static plan from the dynamic policies "\n'
       '           f"(HEFT {mk(\'h16_l15\', \'gpu\', \'HEFT_param_model\', 2)} s against PRED {mk(\'h16_l15\', \'gpu\', \'PRED_RANK_GREEDY\', 2)} s at ratio 7.5): when the GPU model error matters, committing to the estimate in advance costs more than deciding late.")\n'
       '    lo, hi = fd.halfwidths()\n'
       '    d.para(f"**Precision.** With 24 paired blocks the half-width of the ten confirmatory intervals is {lo:.1f} to {hi:.1f} percentage points; the exploratory sessions use 12 blocks and are less precise, so they show direction and order of magnitude and are not used to rank near-equal policies. "\n'
       '           "The 10 or 24 blocks of a session repeat a few chain orders, so intervals describe run-to-run noise, not variation across workloads, which is why six workloads and, earlier, twenty unseen chain orders were used.")\n'
       '    d.para("**Planned versus actual.** The static plans are not far from reality in total (@tab:plan), yet a fixed assignment cannot react to the actual completion order. A ratio below 1 means that the plan was optimistic.")\n'
       '    d.nextlabel = "plan"\n'
       '    d.table("Planned over actual makespan of the static plans (primary workload)", ["Plan", "CPU only", "Strict GPU", "Extended GPU"], fd.plan_rows(), [1.5, 0.6, 0.6, 0.7], size=7)\n')

# ---- related work: patents and products
before('    d.nextlabel = "rw"\n',
       '    d.nextlabel = "pat"\n'
       '    d.table("Patents closest to the project (as summarised from Google Patents; legal status is an assumption, not an opinion)",\n'
       '            ["Patent", "Discloses", "Prediction"],\n'
       '            [["{{p_xilinx}} Xilinx, US 11,561,826 B1", "task graph; kernel objects tied to compute circuits; per-kernel task queues; in-degree gating; performance-based thread adjustment (base work)", "no"],\n'
       '             ["{{p_ibm1}} IBM, US 11,740,933 B2", "learning agent assigns a rank to DAG tasks; tasks run in rank order on a heterogeneous SoC", "learned rank"],\n'
       '             ["{{p_ibm2}} IBM, US 11,966,776 B2", "learning agent schedules DAGs with priorities and task execution estimates, may drop DAGs", "yes"],\n'
       '             ["{{p_intel}} Intel, US 10,186,007 B2", "CPU+GPU: profiling threads time part of the work on each device and split the rest", "online profiling"],\n'
       '             ["{{p_samsung}} Samsung, US 10,162,671 B2", "predicts a task\\u2019s duration when core state changes, from solo-versus-concurrent ratios", "yes"]],\n'
       '            [1.0, 2.0, 0.5], size=6.5)\n'
       '    d.para("None of the patents summarised describes an empirical method for deciding when prediction is worth its cost; rank-ordered dispatch with a learning agent is disclosed by {{p_ibm1}}, so the contribution of this paper is the measured comparison, not the idea of ranking. A professional prior-art search is needed before any filing.")\n')
open(p, "w", encoding="utf-8").write(s)
print("paper4 patched")
