# Document index (which file to trust)

Written 2026-10-25. Two lists: what is current, and what is history. Older documents are kept unchanged; where they disagree with a current document, the current one is right.

## Current (read these)

| Need | File |
|---|---|
| Plain-language study guide | `STUDY_MATERIAL_FINAL.md` |
| Newest result, in simple words | `docs/research_redesign/STUDY2_REPORT.md` |
| Exact rules, predictions and results of every Study 2 session | `docs/research_redesign/EVALUATION_PROTOCOL_study2.md` (sections 1 to 29) |
| Every claim and the stored number behind it | `docs/research_redesign/claims.json` (checked by `tests/test_claims.py`) |
| Montage results (the stage 1 to 5 null result) | `docs/research_redesign/FINAL_REPORT.md` |
| Audit of the whole code base at tag `baseline-null-result` | `PROJECT_MASTER_DOCUMENTATION.md` |
| How to reproduce stage 1 to 5 | `docs/research_redesign/REPRODUCE.md` (observed logs in sections 12, 14, 15) |
| Remote node notes (Raspberry Pi plan) | `docs/REMOTE_DEVICES.md` |

## How to retrain for a new machine or pool

`python scripts/study2_retrain.py <out_dir> <adapter_config.json> <profile.json>` runs two coverage sessions on that machine and writes `param_model.json`. The adapter config names the pools (for example `{"max_p_slots": 2}`). No code change. See `EVALUATION_PROTOCOL_study2.md` sections 21 and 25.

## Historical (kept, partly out of date)

| File | Why it is old |
|---|---|
| `README.md` sections below the first paragraph, `PROJECT_STATUS.md` | Written for the phases 0 to 6 on the i5-1235U |
| `PROGRESS.md` | Snapshot of 2026-10-10 (the E4 fix is committed since) |
| `docs/research_redesign/ARCHITECTURE_DECISIONS.md` "Implementation status" | Snapshot of 2026-10-12 |
| `docs/research_redesign/PROJECT_SPEC.md` section 10, `RESEARCH_STATUS.md` older sections | Superseded by the stage 3 to 5 reports |
| `scripts/calibrate_link.py` docstring "[not yet run]" | The calibration exists (`stage5_20261013/remote/`) |


## Revival (2026-10-25, branch `revival/resource-state-aware`)

- [revival/FINAL_STATUS.md](revival/FINAL_STATUS.md): what was built and run, the oracle-gate result (failed: insufficient headroom), the uniform no-harm check, commands. Folder guide: [revival/README.md](revival/README.md). Study 2 documents remain authoritative for the Study 2 sessions; stage 1-5 documents are historical.
