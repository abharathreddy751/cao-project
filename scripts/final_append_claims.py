"""Final study: append section E (final-study claims) to RESEARCH_CLAIMS_AND_LIMITATIONS.md. The earlier sections A to D are not edited; the file is
backed up first. Numbers are read from the analysis files, not typed.

  python scripts/final_append_claims.py
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "data" / "results" / "final_20261101" / "eval"
DOC = ROOT / "RESEARCH_CLAIMS_AND_LIMITATIONS.md"
BAK = ROOT / "data" / "results" / "final_20261101" / "backups" / "docs"
BAK.mkdir(parents=True, exist_ok=True)
if not (BAK / DOC.name).exists():
    shutil.copy2(DOC, BAK / DOC.name)
text = DOC.read_text(encoding="utf-8")
if "## E. Final static-versus-dynamic study" in text:
    raise SystemExit("section E already present; nothing appended")

C = {r["id"]: r for r in csv.DictReader(open(EV / "analysis_h16_l120" / "confirmatory.csv", newline="", encoding="utf-8"))}
e = lambda i: f"{float(C[i]['effect_pct']):+.1f}% [{float(C[i]['ci_lo_pct']):+.1f}, {float(C[i]['ci_hi_pct']):+.1f}]"
X = {(r["cond"], r["ref"], r["kind"]): r for r in csv.DictReader(open(EV / "analysis_h16_l120" / "contrasts.csv", newline="", encoding="utf-8")) if r["metric"] == "makespan_e2e_s"}
x = lambda c, r, k: f"{float(X[(c, r, k)]['effect_pct']):+.1f}% [{float(X[(c, r, k)]['ci_lo_pct']):+.1f}, {float(X[(c, r, k)]['ci_hi_pct']):+.1f}]"
U = {(r["cond"], r["ref"]): r for r in csv.DictReader(open(EV / "analysis_uniform" / "contrasts.csv", newline="", encoding="utf-8")) if r["metric"] == "makespan_e2e_s" and r["kind"] == "within configuration"}
u = U[("PRED_RANK_GREEDY_E2E_gpu", "B4_gpu")]
uni = f"{float(u['effect_pct']):+.1f}% [{float(u['ci_lo_pct']):+.1f}, {float(u['ci_hi_pct']):+.1f}]"
hy = [ln for ln in (EV / "hybrid_check.md").read_text(encoding="utf-8").splitlines() if ln.startswith("cells:")][0]

S = f"""

## E. Final static-versus-dynamic study (2026-11-01 to 2026-11-02; sections A to D above are unchanged)

Evidence label: real measurements, one laptop (6 P + 7 E workers, one RTX 3050 CUDA worker). Metric: end-to-end makespan (amendment F1). Primary session `eval_h16_l120`, 24 included blocks, Holm over 10 contrasts. Full report: `CAO_FINAL_EXPERIMENT_REPORT.md`; flat table: `RESULTS_TABLE_FINAL.csv`. Negative effect = faster.

| # | Claim | Evidence | Scope | Competing explanation | Limitation |
|---|---|---|---|---|---|
| F1 | A dynamic policy built on the learned model finishes sooner than a static HEFT plan from the same model | C3 PRED vs HEFT_param_model CPU {e('C3')}; C5 strict GPU {e('C5')}; C4 PRED_E2E vs HEFT_E2E {e('C4')}; C6 {e('C6')}; Holm p {float(C['C3']['p_holm']):.3f} to {float(C['C6']['p_holm']):.3f} | primary workload (16 heavy chains), 512 px | on GPU configurations part of the gap may be model error (hold-out GPU error 23 to 31%) that a fixed plan cannot correct | other five workloads exploratory; the earlier overnight HEFT result (S11, +1.1% [-0.5,+2.8]) was level |
| F2 | The same dynamic policy is much faster than blind B4 | C1 CPU {e('C1')}; C8 strict GPU {e('C8')} | as F1 | most of the gain is available from a parameter-aware rule (F4) | |
| F3 | Adding setup and IPC terms (PRED_RANK_GREEDY_E2E) neither helps nor hurts on the primary workload | C2 {e('C2')} (equivalent), C7 {e('C7')} (equivalent) | primary workload | the terms are small (a few ms) next to task times | exploratory harm on the uniform workload (X8) |
| F4 | The hand-written parameter-aware rule B4_param_first is within 1% of PRED_RANK_GREEDY | CPU/extended/strict GPU, exploratory, in the report Section 1 | primary workload | | confirms S2; prediction adds almost nothing beyond knowing the parameter |
| F5 | Allowing the GPU only where the spike records verified a speed-up helps the dynamic policy | extended set vs CPU only {x('PRED_RANK_GREEDY_ext', 'PRED_RANK_GREEDY_cpu', 'configuration effect')} (exploratory); C9 strict set vs CPU only {e('C9')} | primary workload | | one CUDA worker; GPU model error 23 to 31% |
| F6 | A B4/PRED hybrid selector is not justified | {hy} | 17 workload x configuration cells | | descriptive; no held-out hybrid test was needed |

| # | Not established | Why |
|---|---|---|
| N9 | Remote worker with the final policies | not rerun; earlier emulated sessions (S7, S8, N6, X5) show no benefit on a fast link |
| N10 | Gain on other workflow families or machines | one image-pipeline family, one machine |
| N11 | Static plan with realised per-run times as an upper bound | HEFT_oracle uses class medians from calibration sessions |

| # | Not supported / null | Result |
|---|---|---|
| X6 | The GPU helps blind B4 | C10 B4 strict GPU vs B4 CPU {e('C10')} (inconclusive); B4 extended vs CPU {x('B4_ext', 'B4_cpu', 'configuration effect')} |
| X7 | The end-to-end terms improve the dynamic policy | C2 and C7 equivalent (F3) |
| X8 | PRED_RANK_GREEDY_E2E does no harm on a uniform workload with the strict GPU set | PRED_E2E vs B4 on `uniform` strict GPU {uni} (exploratory, unadjusted) |
| X9 | PEFT is competitive | PEFT_param_model is the slowest static plan in the primary session (report Section 8) |
"""
DOC.write_text(text.rstrip("\n") + S, encoding="utf-8")
print("appended section E to", DOC.name)
