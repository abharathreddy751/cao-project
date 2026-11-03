"""Final study: append the final-study update to the project guide (PROJECT_MASTER_DOCUMENTATION.md section 33), the backbone
(PROJECT_BACKBONE.md part 12), the faculty demo checklist and script, and the evidence index. Earlier text is not edited (appended only; the
originals are backed up first). Numbers are read from the analysis files.

  python scripts/final_append_guides.py [--tests "<one-line pytest summary>"]
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIN = ROOT / "data" / "results" / "final_20261101"
EV = FIN / "eval"
BAK = FIN / "backups" / "docs"
BAK.mkdir(parents=True, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument("--tests", default="see data/results/final_20261101/preservation/pytest_final.stdout.txt")
a = ap.parse_args()

C = {r["id"]: r for r in csv.DictReader(open(EV / "analysis_h16_l120" / "confirmatory.csv", newline="", encoding="utf-8"))}
e = lambda i: f"{float(C[i]['effect_pct']):+.1f}% [{float(C[i]['ci_lo_pct']):+.1f}, {float(C[i]['ci_hi_pct']):+.1f}]"
hy = [ln for ln in (EV / "hybrid_check.md").read_text(encoding="utf-8").splitlines() if ln.startswith("cells:")][0]
P = {r["condition"]: r for r in csv.DictReader(open(EV / "analysis_h16_l120" / "policy_table.csv", newline="", encoding="utf-8"))}
mk = lambda n: f"{float(P[n]['e2e_geo_mean_s']):.2f}"

SUMMARY = (f"Final static-versus-dynamic study (real measurements, one laptop: 6 P + 7 E workers + one RTX 3050 CUDA worker). Primary workload, "
           f"end-to-end makespan, Holm over 10 contrasts: dynamic PRED_RANK_GREEDY vs static HEFT_param_model {e('C3')} (CPU) and {e('C5')} (strict GPU); "
           f"vs blind B4 {e('C1')} (CPU) and {e('C8')} (strict GPU); the end-to-end variant is equivalent to PRED (C2 {e('C2')}, C7 {e('C7')}). "
           f"Best configuration (extended verified GPU set) PRED_E2E {mk('PRED_RANK_GREEDY_E2E_ext')} s against HEFT_param_model {mk('HEFT_param_model_ext')} s and B4 {mk('B4_ext')} s. "
           f"A hybrid is not justified ({hy}). The simple parameter-aware rule B4_param_first is within 1% of PRED. Remote worker: not rerun (earlier emulation: no benefit).")


def backup(p: Path):
    if not (BAK / p.name).exists():
        shutil.copy2(p, BAK / p.name)


def append(p: Path, marker: str, body: str):
    t = p.read_text(encoding="utf-8")
    if marker in t:
        print("skip (already present):", p.name)
        return
    backup(p)
    p.write_text(t.rstrip("\n") + "\n\n" + body.strip("\n") + "\n", encoding="utf-8")
    print("appended:", p.name)


# ---- master documentation (the complete project guide)
mp = ROOT / "PROJECT_MASTER_DOCUMENTATION.md"
body = f"""---

## 33. Update 2026-11-02: final static-versus-dynamic benchmark (supersedes the status and pending lists above where they differ)

{SUMMARY}

**What was added.** Timing accounting amendment F1 (end-to-end makespan = start of `run()` to last completion, with init, policy setup and scheduling reported separately); fair static baselines HEFT_param_model, PEFT_param_model, HEFT_E2E and HEFT_oracle (reference only); the dynamic policy PRED_RANK_GREEDY_E2E; per-task GPU eligibility from recorded speed-up measurements (`final/gpu_region.py`, original record plus an extended denoise-iteration record); calibration and hold-out sessions kept separate from the evaluation sessions; six evaluation sessions (primary 25 blocks, five of 13 blocks); analysis, results table, hybrid check and the final report. Code `src/caosched/final/`, scripts `scripts/final_*`, tests `tests/test_final_*.py`, protocol `docs/final/PROTOCOL_final.md` (frozen before the first evaluation session; hashes in `data/results/final_20261101/ACTIVITY_LOG.md`), amendment `docs/final/AMENDMENT_F1_timing.md`.

**Where the results are.** `CAO_FINAL_EXPERIMENT_REPORT.md` (answers, tables, limitations), `RESULTS_TABLE_FINAL.csv` (flat table, 146 rows; the earlier `RESULTS_TABLE.csv` is unchanged), `data/results/final_20261101/eval/` (sessions, `analysis_*`, `cross_workload.md`, `hybrid_check.md`, `workload_features.csv`), `RESEARCH_CLAIMS_AND_LIMITATIONS.md` section E (claims F1 to F6, N9 to N11, X6 to X9).

**How to run.** Keep the charger plugged in; quit Docker Desktop (`docker desktop stop`) and run `wsl --shutdown` first; a session needs about 3.5 GB free RAM at start (worker pool about 1.8 GB, 0.8 GB per-block floor). `scripts/final_stage1.ps1` (calibration, models, designs, smoke), `scripts/final_stage2.ps1` (evaluation sessions and analyses). Both are idempotent and never overwrite; an aborted attempt stays on disk and the design is rerun under a new id.

**Status changes.** Done: the final benchmark above. Still not done: Raspberry Pi and real-network remote validation (out of scope), the remote worker with the final policies, a second workflow family, a second machine. Test status: {a.tests}.

**Lessons recorded.** Running the pipeline needed mains power and enough free RAM; a security product holding several GB, a Docker VM and a browser each caused aborted attempts (all kept as evidence). The first calibration attempt `cal_l120` aborted at block 7 of 9 on RAM, `cal_l40` several times on RAM and power; they were rerun under new ids with identical designs.
"""
append(mp, "## 33. Update 2026-11-02", body)
t = mp.read_text(encoding="utf-8")
toc = "31. [Final checklist](#31-final-checklist)"
if "[Update 2026-11-02" not in t and toc in t:
    t = t.replace(toc, toc + "\n32. [Update 2026-10-24: Study 2](#32-update-2026-10-24-study-2-branch-study2affinity)\n33. [Update 2026-11-02: final static-versus-dynamic benchmark](#33-update-2026-11-02-final-static-versus-dynamic-benchmark-supersedes-the-status-and-pending-lists-above-where-they-differ)", 1) if "32. [Update 2026-10-24" not in t else t.replace(toc, toc, 1)
    mp.write_text(t, encoding="utf-8")

# ---- backbone
bp = ROOT / "PROJECT_BACKBONE.md"
append(bp, "# PART 12. FINAL STATIC-VERSUS-DYNAMIC BENCHMARK", f"""
# PART 12. FINAL STATIC-VERSUS-DYNAMIC BENCHMARK (2026-11-01 to 2026-11-02)
{SUMMARY}

Chronology: audit and improvement plan (`NVIDIA_VS_CAO_AUDIT.md`, `CAO_IMPROVEMENT_PLAN.md`) -> implementation of amendment F1, static baselines, PRED_RANK_GREEDY_E2E, GpuRegion, tests -> extended GPU spike -> protocol written -> blocked for hours by free RAM (a security product holding several GB; removed by the user) -> unplugged laptop and a session-id collision in my own retry script (both fixed, attempts kept) -> Docker's WSL VM holding 2.5 GB (stopped by the user) -> calibration, hold-out, models, smoke -> protocol frozen -> six evaluation sessions -> analysis, hybrid check (not justified), report, claims, guide, deck.

Errors found and fixed during the run (all logged in `data/results/final_20261101/ACTIVITY_LOG.md`): nested f-string syntax error under Python 3.11 in `final_analyze.py`; PowerShell string splatted per character in `final_stage2.ps1` (primary analysis rerun by hand); smoke rows leaked into the first `RESULTS_TABLE_FINAL.csv` (renamed, kept, regenerated); two earlier report drafts superseded after number checks (kept in `eval/`).
""")

# ---- faculty docs
append(ROOT / "FACULTY_DEMO_CHECKLIST.md", "## 6. Final study", f"""
## 6. Final study (static versus dynamic), added 2026-11-02
- Open `CAO_FINAL_EXPERIMENT_REPORT.md` section 1 (one page) and `RESULTS_TABLE_FINAL.csv`.
- Show `data/results/final_20261101/eval/analysis_h16_l120/summary.md` and `confirmatory.csv` (10 Holm-adjusted contrasts).
- Show the GPU eligibility table (report section 6) and `hybrid_check.md`.
- Keep the laptop on mains power; quit Docker Desktop and run `wsl --shutdown` before any live run (free RAM).
- Do not claim: a universal gain; any remote-worker benefit (earlier emulation showed none on a fast link; the final policies were not run with it); that prediction beats the hand-written parameter-aware rule (it is within 1%).
""")
append(ROOT / "FACULTY_DEMO_SCRIPT.md", "## Final study", f"""
## Final study (added 2026-11-02, 90 seconds)
We compared dynamic scheduling with a static plan built from the same cost model, on CPU cores plus one GPU, with end-to-end time including planning. On the main workload the dynamic policy was faster than the static plan by {e('C3')} on CPU and {e('C5')} when the verified GPU stages are allowed, and much faster than blind greedy ({e('C1')}). Honest parts: a hand-written parameter-aware rule gets almost the same gain; with no spread in task cost the policies tie; adding end-to-end cost terms changed nothing; a hybrid selector would gain at most 1.1%, so we did not build one; the remote worker was not rerun, and earlier emulation showed no benefit on a fast link.

Likely questions: "Is the static baseline fair?" Same model, same pools, same GPU rules, planning time included in its makespan, an oracle-cost reference reported. "Is it general?" No: one workflow family, one machine; five further workloads are exploratory.
""")

# ---- evidence index
append(ROOT / "EVIDENCE_INDEX.md", "## Final study (2026-11-01", f"""
## Final study (2026-11-01 to 2026-11-02), all real measurements, one laptop
| Path | What |
|---|---|
| `data/results/final_20261101/calibration/sessions/` | calibration and hold-out sessions; complete: `cal_l120_r2`, `cal_l40_r8`, `cal_l15_r5`, `cal_uniform_r5`, `hold_l120_r5`, `hold_l40_r5`; earlier attempts aborted (RAM or mains power) and kept |
| `data/results/final_20261101/models/` | `param_model_final.json`, `e2e_terms_final.json` and training logs |
| `data/results/final_20261101/eval/sessions/` | `smoke` (sanity), `eval_h16_l120` (primary), `eval_uniform`, `eval_h04_l120`, `eval_h40_l120`, `eval_h16_l40`, `eval_h16_l15` |
| `data/results/final_20261101/eval/analysis_*` | per-session `policy_table.csv`, `contrasts.csv`, `summary.md`, `meta.json`; `analysis_h16_l120/confirmatory.csv` (Holm family) |
| `data/results/final_20261101/eval/cross_workload.md`, `hybrid_check.md`, `workload_features.csv`, `exploratory_pf_*` | digest, hybrid headroom, pre-execution features, PRED vs B4_param_first (exploratory) |
| `data/results/final_20261101/gpu_spike_iters/` | extended GPU spike record (denoise iteration counts) |
| `data/results/final_20261101/preservation/`, `backups/` | state before changes, hashes, tests, backups of edited files and documents |
| `data/results/final_20261101/ACTIVITY_LOG.md` | chronological log with frozen-protocol hashes and every failure |
| `RESULTS_TABLE_FINAL.csv`, `CAO_FINAL_EXPERIMENT_REPORT.md` | flat results table (146 rows) and final report |
Superseded files kept as evidence: `eval/RESULTS_TABLE_FINAL_with_smoke_rows_superseded.csv`, `eval/cross_workload_with_smoke_superseded.md`, `eval/CAO_FINAL_EXPERIMENT_REPORT_draft*_superseded.md`.
""")
