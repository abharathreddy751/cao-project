"""Builds an UPDATED copy of the project guide (the original PDF and its builder stay unchanged)."""
import csv
import sys

src = open(r"D:\cao_project_guide_output\build\make_pdf.py", encoding="utf-8").read()
sys.path.insert(0, r"D:\cao project\SUBMISSION_FINAL\_build")
import final_data as fd


def rep(old, new):
    global src
    assert old in src, old[:70]
    src = src.replace(old, new, 1)


rep('("How do you compare static and dynamic fairly?", "Same workload, same eligible resources, same end-to-end timing boundary including planning time. Final version of this is under audit (PENDING)."),',
    '("How do you compare static and dynamic fairly?", "Same workload, same eligible resources, ONE ridge cost model on both sides, and the end-to-end makespan from the start of run() to the last completion, so the planning time of a static plan is counted. Done in the final benchmark (Section 16): PRED is 5.2% faster than static HEFT on the CPU and 12.2% with the strict GPU set."),')
rep('("What is still pending?", "Final audit: test count, CPU-only vs CPU+GPU, static vs dynamic with E2E timing, prediction accuracy, significance, hybrid policy decision."),',
    '("What is still pending?", "Nothing in the final audit: it is complete (Section 16). Open by design: Raspberry Pi and real-network results, a better GPU cost model, a second workload family, the GitHub push and the IPR decision."),')
rep('note("<b>Update points after the audit:</b> Section 13.3 final rows, Section 8 E2E policies, Section 11 audit note, test count, and the GPU conclusion.")',
    'note("<b>Updated 3 November 2026:</b> the final audit is finished; Section 16 holds the final static-versus-dynamic results, the CPU/GPU conclusion, the new policies, the dashboards v2 and v3 and the test count. Earlier sections are unchanged and describe the earlier study; where they differ, Section 16 takes precedence.")')

rows = fd.primary_table_rows()
conf = fd.confirmatory_rows()
sec16 = '''
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
table([["Policy", "CPU only", "Strict GPU", "Extended GPU"]] + PRIMROWS, [6.0, 3.3, 3.3, 3.4])
p("Makespan in seconds, geometric mean over 24 blocks. Effect of the GPU for PRED: strict set 2.6% faster than CPU only, extended set 7.5%. For blind B4 the GPU does not help (+1.6%, inconclusive). The GPU cost model has 23% to 31% median error (CPU stages 4% to 11%), so GPU placement is the weakest part.")
h2("16.4 The ten pre-stated contrasts (Holm-adjusted)")
table([["Id", "Contrast", "Effect % [95% CI]", "Holm p", "Result"]] + [list(r) for r in CONFROWS], [1.1, 6.0, 4.3, 1.6, 4.0])
h2("16.5 What the results do not show")
bl(["A hand rule that knows the cost parameter is within 1% of PRED in every configuration.",
    "With no spread in task cost (uniform workload) all policies tie; with the smallest cost ratio and the strict GPU set PRED is 1.1% slower than B4.",
    "End-to-end cost terms change nothing (C2, C7 equivalent within 2%); a hybrid B4/PRED selector would gain at most 1.1% (maximum over 17 cells), so none was built.",
    "An earlier session found HEFT level with PRED (+1.10%); the final session finds PRED about 5% faster; the difference was not isolated and both are reported.",
    "One machine, one workload family, one CUDA worker; the remote worker was not rerun with the final policies; no Raspberry Pi result exists."])
h2("16.6 Dashboards (new files; the original dashboard is unchanged)")
table([["Version", "Command (project root)", "What is new"],
       ["original", ".\\\\.venv\\\\Scripts\\\\python.exe -m caosched.dashboard --port 8765 --open", "unchanged; CPU load bars stay 0 after the first request (old psutil baseline bug)"],
       ["v2", ".\\\\.venv\\\\Scripts\\\\python.exe -m caosched.dashboard_v2 --port 8766 --events-dir data\\\\results\\\\final_20261101\\\\eval\\\\sessions --open", "GPU CONNECTED with live load/memory/temperature/power, Pi card NOT CONNECTED, final results with hover tooltips on screen 3, CPU load fixed"],
       ["v3", ".\\\\.venv\\\\Scripts\\\\python.exe -m caosched.dashboard_v3 --port 8770 --events-dir data\\\\results\\\\final_20261101\\\\eval\\\\sessions --open", "v2 plus screen 6: run one live block of the final benchmark with any policy on CPU or CPU+GPU (1 to 2 minutes, needs 2.4 GB free RAM)"]], [1.8, 8.2, 7.0])
p("A live run on screen 6 is a demonstration of one block, not an experiment result: its makespan (about 4 s) is not comparable with the benchmark (about 3 s); the cause was not isolated (it includes pool and CUDA start-up).")
h2("16.7 Tests and reproducibility")
p("521 tests: 520 pass; one (tests/test_profile_montage.py::test_profile_format_csv_fit_and_cleanup) refuses to start when free RAM is below its own 2 GB gate and failed at 1.44 GB free; the test passed in the earlier full run. Pipeline: scripts/final_stage1.ps1, final_stage2.ps1, final_analyze.py, final_results_table.py, final_cross_workload.py, final_hybrid_check.py, final_build_report.py. Submission package: SUBMISSION_FINAL.")
'''.replace("CONFROWS", repr([list(r) for r in conf])).replace("PRIMROWS", repr([list(r) for r in rows]))
rep("\n\ndef foot(c, d):", sec16 + "\n\ndef foot(c, d):")
rep('"CAO project explanation - commit 9d8ea22 + audit WIP (read-only)"', '"CAO project explanation - updated 3 Nov 2026 (final benchmark in Section 16)"')
rep('doc = SimpleDocTemplate(f"{D}\\\\CAO_Project_Complete_Explanation.pdf"', 'doc = SimpleDocTemplate(r"D:\\cao project\\SUBMISSION_FINAL\\CAO_Project_Complete_Explanation_UPDATED.pdf"')
open(r"D:\cao project\SUBMISSION_FINAL\_build\make_guide.py", "w", encoding="utf-8").write(src)
print("guide builder written")
