# Overnight plan (written 2026-11-01 ~17:45 UTC, user asleep, deadline: submission-ready by morning)

The user asked for autonomous completion: results, final report, updated complete project guide, deck, all consistent. Standing rules still apply:
no fabricated numbers, label real / emulation / simulation / plan, never delete or overwrite evidence, RAM start gate 2.4 GB and 0.8 GB block floor unchanged,
no destructive git, no push, ≤30-page TNR report rebuild only on the user's say (the old 05 report stays as is; the new report is `CAO_FINAL_EXPERIMENT_REPORT.md`).

## State
* Stage 1 complete. Protocol frozen (hashes in ACTIVITY_LOG.md).
* Stage 2 (`scripts/final_stage2.ps1`, background) runs the six evaluation sessions in order: eval_h16_l120 (done), eval_uniform (done, analysed),
  eval_h04_l120 (running), eval_h40_l120, eval_h16_l40, eval_h16_l15.
* `analysis_h16_l120` is NOT yet created (script bug, fixed): run it by hand after stage 2 finishes:
  `.\.venv\Scripts\python.exe scripts\final_analyze.py --session data\results\final_20261101\eval\sessions\eval_h16_l120 --out data\results\final_20261101\eval\analysis_h16_l120 --confirmatory`

## When stage 2 is done (STAGE2_DONE.txt), in order
1. Analyse eval_h16_l120 (command above). Do not run analyses while a timed session is running.
2. `scripts/final_workload_features.py` for the six workloads; record the output BEFORE reading outcome tables for the hybrid decision (protocol section 10).
3. Hybrid decision per protocol section 10 (development vs frozen held-out; oracle best-of-two as reference). Run held-out sessions only if justified; new orders 9401+.
4. Optional, only if time permits: emulated remote worker secondary (not in the confirmatory family).
5. `scripts/final_results_table.py data\results\final_20261101\eval RESULTS_TABLE_FINAL.csv` (exclusive write; do not touch RESULTS_TABLE.csv).
6. Write `CAO_FINAL_EXPERIMENT_REPORT.md`; update `RESEARCH_CLAIMS_AND_LIMITATIONS.md`, `FACULTY_DEMO_CHECKLIST.md`, `FACULTY_DEMO_SCRIPT.md`, `PROJECT_MASTER_DOCUMENTATION.md` (new section 33), `EVIDENCE_INDEX.md`, `PROJECT_BACKBONE.md`; add concise contribution statement.
7. Rebuild the demo deck `publications/04_Project_Demo_Existing_vs_Proposed.pptx` as a NEW file (do not overwrite 04): add the final static-vs-dynamic results.
8. Full test suite; final verification pass over every number quoted in the documents against `policy_table.csv` / `contrasts.csv` / `confirmatory.csv`.
