p = "build_report_final.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


def before(anchor, new):
    global s
    assert anchor in s, anchor[:70]
    s = s.replace(anchor, new + anchor, 1)


rep("Table 12 gives the end-to-end makespan", "The first table below gives the end-to-end makespan")

HOLD = '''
import json, re
def holdout_rows():
    rows = []
    for ln in open(fd.ROOT / "data" / "results" / "final_20261101" / "models" / "train.stdout.txt", encoding="utf-8"):
        m = re.match(r"holdout (\\S+) (\\{.*\\})", ln.strip())
        if m:
            d = json.loads(m.group(2).replace("'", '"'))
            rows.append([m.group(1).replace("img_", "").replace("|", " on "), str(d["n"]), f"{d['mae_s'] * 1000:.2f}", f"{d['median_ape'] * 100:.1f}"])
    return sorted(rows)

'''
before("r = Report()\n", HOLD)

# ---- chapter 5 additions
before('r.para("**GPU eligibility.** A stage may run',
       'r.para("**Dispatch pass.** Whenever a task becomes ready or a worker becomes idle the coordinator runs one pass, identical for all policies except for two hooks:")\n'
       'r.numbered([\n'
       '    "take the ready tasks and let the policy reorder them (the proposed policy sorts by predicted upward rank, rank(t) = predicted time(t) + the largest rank among the successors of t);",\n'
       '    "for each task in that order ask the policy for a worker; a late-binding policy may name only an idle eligible worker, otherwise the task stays queued;",\n'
       '    "check eligibility and idleness (a violation raises a contract error), bind the task and log the dispatch with its decision time;",\n'
       '    "stop when no worker is idle or all ready tasks were visited; on completion log the result and release the dependents.",\n'
       '])\n'
       'r.table("Event log and run manifest content",\n'
       '        ["Record", "Fields (selection)"],\n'
       '        [["task_ready, task_dispatched", "task id, worker, pool, queue wait, worker load, decision time"],\n'
       '         ["task_submitted, task_completed", "kernel time, start and end timestamps, transfer time, output size and SHA-256"],\n'
       '         ["worker_ready, run_started, run_finished", "pid, requested and actual affinity; makespan, status, tasks per pool"],\n'
       '         ["run manifest", "condition, policy, seed, warm-up flag, output verdict, event-log hash, git commit and dirty flag, source and design hashes"]],\n'
       '        [2.2, 4.3], size=8.5)\n'
       'r.table("Cost-model error on hold-out tasks (E = efficiency core, P = performance core, G = CUDA worker)",\n'
       '        ["Stage on pool", "n", "MAE (ms)", "Median abs. error (%)"], holdout_rows(), [2.0, 1.0, 1.2, 2.0], size=8.5)\n'
       'r.figure(FF + r"\\fig_final_model_error.png", "Median absolute error of the cost model on hold-out tasks, by stage and pool.", 4.0)\n')

# ---- chapter 6: workload table
before('r.para("**Data separation and protocol.**',
       'r.table("Evaluation workloads (runs per session; included runs in brackets; the first block of each session is a warm-up)",\n'
       '        ["Workload", "Heavy chains / iterations", "Blocks", "Runs"],\n'
       '        [["h16_l120 (primary)", "16 heavy, 120 vs 2 iterations (ratio 60)", "25", "600 (576)"], ["uniform", "none; cpu and gpu only", "13", "208 (192)"],\n'
       '         ["h04_l120", "4 heavy, 120 vs 2", "13", "312 (288)"], ["h40_l120", "40 heavy, 120 vs 2", "13", "312 (288)"],\n'
       '         ["h16_l40", "16 heavy, 40 vs 2 (ratio 20)", "13", "312 (288)"], ["h16_l15", "16 heavy, 15 vs 2 (ratio 7.5)", "13", "312 (288)"]],\n'
       '        [1.6, 3.2, 0.8, 0.9], size=8.5)\n')

# ---- chapter 7 additions
before('r.section("Earlier study (exploratory) and the remote worker")',
       'r.figure(FF + r"\\fig_final_workloads.png", "PRED against static HEFT (left) and blind B4 (right) on the six workloads, CPU only (blue) and strict GPU set (orange).", 4.3)\n'
       'r.table("Effect of the hardware set within each policy on the primary workload (%, negative = faster)",\n'
       '        ["Policy", "Strict vs CPU", "Extended vs CPU", "Extended vs strict"], fd.gpu_rows(), [1.6, 1.6, 1.7, 1.6], size=8.5)\n'
       'r.figure(FF + r"\\fig_final_placement.png", "Tasks run on the CPU and on the GPU per policy (extended set, primary workload) and the GPU busy fraction.", 4.2)\n'
       'r.table("Static plans against HEFT_param_model on the primary workload (%, exploratory)",\n'
       '        ["Hardware set", "HEFT_E2E", "PEFT", "HEFT oracle (reference)"], fd.static_rows(), [1.4, 1.7, 1.7, 1.7], size=8.5)\n'
       'r.para("Adding the end-to-end terms to the static plan did not help consistently; PEFT is clearly the slowest static plan; the oracle plan, built from class-median costs, is a reference and not a bound. "\n'
       '       "Planned over actual makespan of the static plans was between 0.88 and 1.03, yet a fixed assignment cannot react to the actual completion order.")\n'
       'r.table("Primary workload, CPU only: old and end-to-end makespan (s) and the difference (ms)",\n'
       '        ["Policy", "Old convention", "End-to-end", "Difference (ms)"], fd.timing_rows(), [2.6, 1.3, 1.3, 1.3], size=8.5)\n'
       'r.table("Primary workload, CPU only: initialisation, policy set-up, total scheduling time (ms) and mean queue wait (s)",\n'
       '        ["Policy", "Init.", "Policy set-up", "Scheduling", "Queue wait"], fd.overhead_rows(), [2.4, 0.8, 1.2, 1.1, 1.0], size=8.5)\n')
before('r.chapter("Existing versus Proposed Implementation")',
       'r.table("Earlier exploratory sessions on unseen chain orders (effect against B4, negative = shorter)",\n'
       '        ["Session", "Blocks / orders", "Dispatcher", "Hand rule"],\n'
       '        [["6P+7E, 16 heavy", "36 / 12", MINUS + "19.32% [" + MINUS + "20.0, " + MINUS + "18.6]", MINUS + "19.85%"], ["2P+7E, 16 heavy", "24 / 8", MINUS + "20.45% [" + MINUS + "21.2, " + MINUS + "19.8]", MINUS + "20.67%"],\n'
       '         ["6P+7E, 4 heavy", "12 / 4", MINUS + "27.65% [" + MINUS + "34.0, " + MINUS + "18.7]", MINUS + "26.94%"], ["6P+7E, 8 heavy", "12 / 4", MINUS + "26.76% [" + MINUS + "27.9, " + MINUS + "25.7]", MINUS + "26.93%"],\n'
       '         ["6P+7E, 40 heavy", "12 / 4", MINUS + "3.81% [" + MINUS + "5.1, " + MINUS + "1.9]", MINUS + "5.15%"]],\n'
       '        [1.7, 1.3, 2.2, 1.3], size=8.5)\n'
       'r.table("Defects and incidents found during the work",\n'
       '        ["Item", "Found by", "Action"],\n'
       '        [["Static plans timed from the first dispatch, hiding planning time", "design review", "end-to-end makespan (amendment F1); old metric kept"],\n'
       '         ["Final-study stage 1 aborted: laptop unplugged, retry-id collision, low free memory (antivirus, Docker, WSL)", "run logs", "mains wait, first-unused-id logic; thresholds never lowered; attempts kept (_r2 to _r8)"],\n'
       '         ["Idle CUDA worker defeats the dispatch loop\\u2019s early exit", "overhead diagnosis", "quantified; fix in a separate adapter; not applied to the source"],\n'
       '         ["Learned model used on a profile it was not fitted on", "audit", "profile binding recorded in the model; refusal on mismatch"],\n'
       '         ["Remote node served one client then exited", "loopback rehearsal", "persistent mode and test"]],\n'
       '        [2.9, 1.2, 2.4], size=8.5)\n')
open(p, "w", encoding="utf-8").write(s)
print("ok")
