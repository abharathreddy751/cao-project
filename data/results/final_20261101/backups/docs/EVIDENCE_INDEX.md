# Evidence index (overnight sprint, 2026-10-27)

SHA-256 values were computed when this file was written. Sessions carry their own `SHA256_MANIFEST.tsv` (verify with `scripts\make_manifest.py <dir> --verify`).

## Timed sessions (real hardware unless stated)

| session dir | design | label | blocks | runs | code hash(es) | manifest sha256 |
|---|---|---|---|---|---|---|
| `data/results/overnight_20261027/phase3/sessions/gen_unseen_orders` | overnight_unseen_orders_exploratory `a9a8353d9893` | real | 37/37 (complete) | 148 | 41a8f43b+dirty | 72c1bd7e8d71766b |
| `data/results/overnight_20261027/phase3b/sessions/gen_unseen_p2` | overnight_unseen_orders_p2_exploratory `115448f48fbf` | real | 25/25 (complete) | 100 | 41a8f43b+dirty | 492cece05b305a30 |
| `data/results/overnight_20261027/phase3c/sessions/dose_h006` | overnight_dose_h006 `93fd164cde05` | real | 13/13 (complete) | 52 | ed70c36d+dirty | ba592252d31ddb76 |
| `data/results/overnight_20261027/phase3c/sessions/dose_h015` | overnight_dose_h015 `90e442ebc663` | real | 13/13 (complete) | 52 | ed70c36d+dirty | 05c67a2a1e5df31b |
| `data/results/overnight_20261027/phase3c/sessions/dose_h040` | overnight_dose_h040 `4beb72831197` | real | 13/13 (complete) | 52 | ed70c36d+dirty | 968b850d080217b6 |
| `data/results/overnight_20261027/phase3c/sessions/dose_h120` | overnight_dose_h120 `a679b2e7632f` | real | 13/13 (complete) | 52 | ed70c36d+dirty | 69cf8aec77a8b9ab |
| `data/results/overnight_20261027/phase3d/sessions/exit_fix` | overnight_early_exit_fix `7d31bca0d7d8` | real | 13/13 (complete) | 78 | ed70c36d+dirty | a39d5d8fc67c0891 |
| `data/results/overnight_20261027/phase3d/smoke_sessions/smoke1` | smoke_exit_fix `7ad72b43497c` | real | 2/2 (complete) | 4 | ed70c36d+dirty | NONE |
| `data/results/overnight_20261027/phase3e/sessions/dose2_h015` | overnight_dose_followup_h015 `c0b7f991e98d` | real | 25/25 (complete) | 100 | ed70c36d+dirty | 7a9e6260b04cfbef |
| `data/results/overnight_20261027/phase3e/sessions/dose2_h040` | overnight_dose_followup_h040 `90a8709224df` | real | 25/25 (complete) | 100 | ed70c36d+dirty | ca6337684c3a36a9 |
| `data/results/overnight_20261027/phase3e/sessions/heft_peft` | overnight_heft_peft_unseen `be90e90b3dc6` | real | 25/25 (complete) | 150 | ed70c36d+dirty | b279cbd241d42164 |
| `data/results/overnight_20261027/phase3g/sessions/heavy04` | overnight_heavycount_h04 `09d7329b3ca9` | real | 13/13 (complete) | 52 | ed70c36d+dirty | f92b25cb099dd9d7 |
| `data/results/overnight_20261027/phase3g/sessions/heavy08` | overnight_heavycount_h08 `b781f8583911` | real | 13/13 (complete) | 52 | ed70c36d+dirty | 582e843c52e23739 |
| `data/results/overnight_20261027/phase3g/sessions/heavy40` | overnight_heavycount_h40 `8ebed8ac2ee6` | real | 13/13 (complete) | 52 | ed70c36d+dirty | 0a23b194941aefae |
| `data/results/overnight_20261027/phase4/e3_sessions/e3_remote_it30` | overnight_remote_emulation_it30 `09b12ab0e5c2` | emulation | 13/13 (complete) | 65 | ed70c36d+dirty | f5bbd98165b751ca |
| `data/results/overnight_20261027/phase4/rehearsal_sessions/rehearsal_loopback2` | rehearsal_loopback `5559ae0c8e0c` | emulation | 5/5 (complete) | 25 | ed70c36d+dirty | d8907cce60f26fb7 |
| `data/results/overnight_20261027/phase4/rehearsal_sessions/rehearsal_loopback` | rehearsal_loopback `5559ae0c8e0c` | emulation | 5/5 (complete) | 25 | 489d34a5+dirty | NONE |

## Analyses (effects.csv, summary.csv, runs.csv, figures; re-derived from raw logs by reproduce_subset.py where a repro_*.json exists)

| analysis dir | reference | sessions | effects.csv sha256 | reproduction log |
|---|---|---|---|---|
| `data/results/overnight_20261027/phase3/analysis_ref_B4` | B4 | gen_unseen_orders | 3eb9a22b8dedc047 | data/results/overnight_20261027/phase3/repro_analysis_ref_B4.json |
| `data/results/overnight_20261027/phase3/analysis_ref_B4_param_first` | B4_param_first | gen_unseen_orders | e026f144dad7e721 | data/results/overnight_20261027/phase3/repro_analysis_ref_B4_param_first.json |
| `data/results/overnight_20261027/phase3/analysis_ref_PRED` | PRED_RANK_GREEDY | gen_unseen_orders | 4b3f50ce51ea5779 | - |
| `data/results/overnight_20261027/phase3b/analysis_ref_B4` | B4 | gen_unseen_p2 | 21b11926194b912a | data/results/overnight_20261027/phase3b/repro_analysis_ref_B4.json |
| `data/results/overnight_20261027/phase3b/analysis_ref_B4_param_first` | B4_param_first | gen_unseen_p2 | 3a7837e1f3144cf2 | data/results/overnight_20261027/phase3b/repro_analysis_ref_B4_param_first.json |
| `data/results/overnight_20261027/phase3b/analysis_ref_PRED` | PRED_RANK_GREEDY | gen_unseen_p2 | 43e69864fafa3fae | - |
| `data/results/overnight_20261027/phase3c/analysis_h006_ref_B4` | B4 | dose_h006 | e00dc65a78c191f0 | - |
| `data/results/overnight_20261027/phase3c/analysis_h006_ref_B4_param_first` | B4_param_first | dose_h006 | d68af9aaf7fd7f08 | - |
| `data/results/overnight_20261027/phase3c/analysis_h015_ref_B4` | B4 | dose_h015 | c4511e3d3ed508e6 | - |
| `data/results/overnight_20261027/phase3c/analysis_h015_ref_B4_param_first` | B4_param_first | dose_h015 | d9bbfb4f85fbf1aa | - |
| `data/results/overnight_20261027/phase3c/analysis_h040_ref_B4` | B4 | dose_h040 | 25fdeb350e450bea | - |
| `data/results/overnight_20261027/phase3c/analysis_h040_ref_B4_param_first` | B4_param_first | dose_h040 | 06545b4f70aa623a | - |
| `data/results/overnight_20261027/phase3c/analysis_h120_ref_B4` | B4 | dose_h120 | ada1fb54f15d0903 | - |
| `data/results/overnight_20261027/phase3c/analysis_h120_ref_B4_param_first` | B4_param_first | dose_h120 | 99deb1a31cdfe8b1 | - |
| `data/results/overnight_20261027/phase3d/analysis_ref_B4` | B4 | exit_fix | d99203972958527e | data/results/overnight_20261027/phase3d/repro_analysis_ref_B4.json |
| `data/results/overnight_20261027/phase3d/analysis_ref_B4_fix` | B4_fix | exit_fix | 2c8f2567e6651a45 | data/results/overnight_20261027/phase3d/repro_analysis_ref_B4_fix.json |
| `data/results/overnight_20261027/phase3e/analysis_dose2_h015_ref_B4` | B4 | dose2_h015 | b73cc0863fcdbcab | - |
| `data/results/overnight_20261027/phase3e/analysis_dose2_h015_ref_B4_param_first` | B4_param_first | dose2_h015 | 990d9a8ef130d03d | - |
| `data/results/overnight_20261027/phase3e/analysis_dose2_h040_ref_B4` | B4 | dose2_h040 | 573a571ef95ed580 | - |
| `data/results/overnight_20261027/phase3e/analysis_dose2_h040_ref_B4_param_first` | B4_param_first | dose2_h040 | 59a4b52d7b2f0a85 | - |
| `data/results/overnight_20261027/phase3e/analysis_heft_peft_ref_B4` | B4 | heft_peft | a4bd46bf843f645b | - |
| `data/results/overnight_20261027/phase3e/analysis_heft_peft_ref_PRED_RANK_GREEDY` | PRED_RANK_GREEDY | heft_peft | d87bfdf18e2b7a60 | - |
| `data/results/overnight_20261027/phase3g/analysis_heavy04_ref_B4` | B4 | heavy04 | 4c5321164895a18c | - |
| `data/results/overnight_20261027/phase3g/analysis_heavy04_ref_B4_param_first` | B4_param_first | heavy04 | aa9bc9c00205e668 | - |
| `data/results/overnight_20261027/phase3g/analysis_heavy08_ref_B4` | B4 | heavy08 | f46fbbf84c90564e | - |
| `data/results/overnight_20261027/phase3g/analysis_heavy08_ref_B4_param_first` | B4_param_first | heavy08 | c2b2f5dd1a163659 | - |
| `data/results/overnight_20261027/phase3g/analysis_heavy40_ref_B4` | B4 | heavy40 | fc0e3ef443527acc | - |
| `data/results/overnight_20261027/phase3g/analysis_heavy40_ref_B4_param_first` | B4_param_first | heavy40 | 4253bf92d68d1e99 | - |
| `data/results/overnight_20261027/phase4/e3_analysis_ref_B4_no_remote` | B4_no_remote | e3_remote_it30 | 1ff0ee3b6b981fc4 | - |
| `data/results/overnight_20261027/phase4/e3_analysis_ref_EFT_no_remote` | EFT_E1_no_remote | e3_remote_it30 | e72d9edec3a4b8f1 | - |
| `data/results/overnight_20261027/phase4/rehearsal_analysis` | EFT_E1_no_remote | rehearsal_loopback2 | 03002549482ea807 | - |

## Plans, designs and scripts written before the runs (pre-run provenance)

| file | sha256 |
|---|---|
| `data/results/overnight_20261027/phase3/PLAN_unseen_orders.md` | e9a34fa0bc79b7d8 |
| `data/results/overnight_20261027/phase3b/PLAN_unseen_orders_p2.md` | 6cdbc759207c126a |
| `data/results/overnight_20261027/phase3c/PLAN_dose_response.md` | f93fd95ffe4d8a1c |
| `data/results/overnight_20261027/phase3d/PLAN_early_exit_fix.md` | b494e8e9ff009e5e |
| `data/results/overnight_20261027/phase3e/PLAN_phase3e.md` | b2ded30c089f5c33 |
| `data/results/overnight_20261027/phase3g/PLAN_heavy_count.md` | c8ed9a4515103631 |
| `data/results/overnight_20261027/phase4/PLAN_remote_emulation_it30.md` | 8f9b0f998af3d619 |
| `data/results/overnight_20261027/phase3/design_unseen_orders.json` | a9a8353d9893ae2b |
| `data/results/overnight_20261027/phase3b/design_unseen_orders_p2.json` | 115448f48fbf0260 |
| `data/results/overnight_20261027/phase3c/design_dose_h006.json` | 93fd164cde05b8f9 |
| `data/results/overnight_20261027/phase3c/design_dose_h015.json` | 90e442ebc66340a6 |
| `data/results/overnight_20261027/phase3c/design_dose_h040.json` | 4beb7283119799e3 |
| `data/results/overnight_20261027/phase3c/design_dose_h120.json` | a679b2e7632fddf7 |
| `data/results/overnight_20261027/phase3d/design_exit_fix.json` | 7d31bca0d7d89c4c |
| `data/results/overnight_20261027/phase3e/design_dose2_h015.json` | c0b7f991e98ddeb3 |
| `data/results/overnight_20261027/phase3e/design_dose2_h040.json` | 90a8709224df9f5c |
| `data/results/overnight_20261027/phase3e/design_heft_peft.json` | be90e90b3dc655e0 |
| `data/results/overnight_20261027/phase3g/design_heavy04.json` | 09d7329b3ca96c24 |
| `data/results/overnight_20261027/phase3g/design_heavy08.json` | b781f85839119ceb |
| `data/results/overnight_20261027/phase3g/design_heavy40.json` | 8ebed8ac2ee6950e |
| `data/results/overnight_20261027/phase4/e3_designs/design_remote_it30.json` | 09b12ab0e5c2e376 |
| `data/results/overnight_20261027/phase4/e3_designs_raw/design_remote.json` | cd1dbaaf39272e15 |
| `data/results/overnight_20261027/phase4/rehearsal_designs/design_pi.json` | 5559ae0c8e0cea78 |
| `data/results/overnight_20261027/phase3/make_design.py` | e30962a6fe3b8986 |
| `data/results/overnight_20261027/phase3b/make_design_p2.py` | 666fbe2272682ba2 |
| `data/results/overnight_20261027/phase3c/make_designs_dose.py` | eb1dd87444db4302 |
| `data/results/overnight_20261027/phase3d/make_design_exit.py` | eeb7e388cc5fa7c8 |
| `data/results/overnight_20261027/phase3e/make_designs.py` | 4b033025973bae3e |
| `data/results/overnight_20261027/phase3g/make_designs.py` | 060b92930d93de39 |
| `data/results/overnight_20261027/phase4/make_e3_design.py` | fe457e180fe2fcd4 |
| `data/results/overnight_20261027/phase3d/cao_overnight_adapter.py` | 86a2b284cf90812d |
| `data/results/overnight_20261027/phase3/per_order.py` | 5ca8becbc313d537 |
| `data/results/overnight_20261027/phase1/diag_sched_time.py` | 649b8fe5c8247547 |
| `data/results/overnight_20261027/phase3c/analyze_dose.ps1` | 13e24d7aee09968f |
| `data/results/overnight_20261027/phase3c/repro_dose.ps1` | 7444e09ea3f29219 |
| `data/results/overnight_20261027/phase3c/run_dose.ps1` | 60e97b5f386f74d3 |
| `data/results/overnight_20261027/phase3d/analyze_exit.ps1` | ecc2bcf66515bd70 |
| `data/results/overnight_20261027/phase3d/run_exit.ps1` | fd4c34adb48c8a17 |
| `data/results/overnight_20261027/phase3e/analyze_3e.ps1` | 4838190396283203 |
| `data/results/overnight_20261027/phase3e/repro_3e.ps1` | 5ab23fd3781b7a8c |
| `data/results/overnight_20261027/phase3e/run_3e.ps1` | 10b8a0116b5ca296 |
| `data/results/overnight_20261027/phase3g/analyze_3g.ps1` | 89c57cb60873c55a |
| `data/results/overnight_20261027/phase3g/run_3g.ps1` | 258da7ed613fa380 |
| `data/results/overnight_20261027/phase5/check_dashboard.ps1` | df239e8cfae63c92 |
| `data/results/overnight_20261027/run_results_table.ps1` | 49a2b585078c4576 |

## Reports and root documents

| file | sha256 |
|---|---|
| `OVERNIGHT_FINAL_REPORT.md` | e7bf219be4ae63db |
| `RESULTS_TABLE.csv` | 8e4fdbf0ec0b87de |
| `FEATURE_VERIFICATION_MATRIX.csv` | 0413df6cebb7143d |
| `FACULTY_DEMO_CHECKLIST.md` | df5282550ebbf407 |
| `FACULTY_DEMO_SCRIPT.md` | c25a239049dc2efb |
| `RASPBERRY_PI_VALIDATION_RUNBOOK.md` | 67d1d875e15660ab |
| `RESEARCH_CLAIMS_AND_LIMITATIONS.md` | 4caaf480503a1188 |
| `CAO_HANDOFF_AUDIT.md` | 592dc68ebe7f02a9 |
| `PAPER_OUTLINE.md` | 3c69cb52f414bd8d |
| `data/results/overnight_20261027/ACTIVITY_LOG.md` | 6e09cc6dc2d6dbed |
| `data/results/overnight_20261027/phase1/PHASE1_FINDINGS.md` | 568e8d4081161caf |
| `data/results/overnight_20261027/tests/full_suite.txt` | 55be944f80c75bc0 |
| `data/results/overnight_20261027/tests/full_suite_after_changes.txt` | ebfc0b90c3f8bc58 |
| `docs/research_redesign/claims.json` | a7f654c0811199c3 |

## Cited registered sessions (not modified)

- `data/results/study2_20261024/iters_confirm2_sessions/20261024T235431`
- `data/results/study2_20261024/iters_p2_confirm_sessions`
- `data/results/study2_20261024/classes_confirm_sessions`
- `data/results/study2_20261024/analysis_iters_confirm2_ref_B4`
- `data/results/study2_20261024/analysis_iters_p2_confirm_ref_B4`
- `data/results/stage5_20261013/remote_sessions/remote_confirm`
- `data/results/demo_20261027/sessions/20261026T220714`
- `data/results/revival_20261025/analysis_gate_ref_B4`

## Notes on specific entries
- `phase4/rehearsal_sessions/rehearsal_loopback`: session status says `complete` but 24 of its 25 runs FAILED (`Worker(s) died during startup: ['R0']`, node exited after the first client). Kept as evidence of the defect that led to `--persistent`; excluded from every analysis. `rehearsal_loopback2` is the valid rehearsal (25 of 25 ok, label emulation, rehearsal only).
- `phase3d/smoke_sessions/smoke1`: smoke test of the adapter, not evidence. `phase1/diag_run`: first diagnostic attempt that failed (kept); `phase1/diag_run2` is the valid one.
- Sessions with code hash `41a8f43b` ran before the code changes of 2026-10-27; `ed70c36d` after. They are never pooled.
- `phase3e/repro_*.json` (first attempt, exit 1) failed only because the session manifests had not been written yet; `repro2_*.json` are the valid reproduction checks.
- The `tier` column in analysis files says `confirmatory` for the primary family by tool default; every overnight session is exploratory by its written plan.
- Not in the index: `data/profiles/overnight_*` (profiles and calibrations used by the remote sessions and the rehearsal).
