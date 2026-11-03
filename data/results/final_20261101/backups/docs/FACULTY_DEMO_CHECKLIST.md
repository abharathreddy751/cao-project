# Faculty demo checklist (known-working steps, checked 2026-10-27)

Verified items are marked VERIFIED with the evidence file; anything else is marked NOT CHECKED. Do not present the Raspberry Pi as tested.

## 0. Before the review (10 minutes, evening before or morning)
1. Plug in the laptop (the runner refuses timed runs on battery). Close the browser tabs you do not need, WSL and other heavy programs. Free RAM should be above 2 GB: `.\.venv\Scripts\python.exe scripts\memory_preflight.py --min-free-gb 2` prints `OK` (VERIFIED: 4.4 to 4.6 GB free during the sprint).
2. Open PowerShell in `D:\cao project`. Do **not** run `.venv\Scripts\activate` (script execution is disabled in your PowerShell); call the interpreter directly: `.\.venv\Scripts\python.exe`.
3. Optional sanity check of the code (about 4 minutes; run it the night before, not during the demo): `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q` expects `488 passed` (VERIFIED after the sprint's code changes: `dataesults\overnight_20261027	estsull_suite_final.txt`; the claims registry tests then grew from 42 to 51 entries, `tests	est_claims.py` 51 passed).

## 1. Dashboard (front end) VERIFIED: `data\results\overnight_20261027\phase5\dashboard_ui_check.md`
```powershell
.\.venv\Scripts\python.exe -m caosched.dashboard --port 8765 --events-dir data\results\overnight_20261027\phase3\sessions --events-dir data\results\demo_20261027\sessions --open
```
Expected: the browser opens `http://127.0.0.1:8765`; five tabs. If the port is busy use `--port 8770`. Stop with Ctrl+C.
Walk-through:
1. Tabs 1 to 4: replay of the earlier 68-task image pipeline (NOT CHECKED in this sprint beyond the page loading and the API answering). The header says these come from an earlier laptop. Say so.
2. **Tab 5 "Montage & GPU"** (the strongest result). Set **Workload = "GPU workload"** (the experiment runs of the hidden-cost workload are listed under this option; "Montage" shows none because those runs are not Montage). Choose Run `order_e . B4 . 3859 ms . output ok` and Compare with `order_e . PRED_RANK_GREEDY . 3097 ms . output ok`.
   Expected (VERIFIED): two cards, B4 makespan 3858.9 ms and PRED_RANK_GREEDY 3097.0 ms, placement P 202 / E 55 versus P 172 / E 85, scheduling 184.46 ms versus 95.43 ms, both with "hashes match reference" (same sha256 326842de...).
   What to say: one pair of runs, not the statistics; the statistics are in step 2 below. "Scheduling" is the coordinator's total time in the scheduler (about 3% to 5% of the run); the policy's own decision time is smaller (about 15 ms per run for PRED).
3. Tab 2 "Live execution" starts a real run of the old 68-task pipeline on this laptop: NOT CHECKED this sprint; use "Replay accepted run" instead.

## 2. Terminal evidence (no experiment needed) VERIFIED files exist
```powershell
Get-Content data\results\overnight_20261027\phase3\per_order_summary.csv
Get-Content data\results\overnight_20261027\phase3\analysis_ref_B4\effects.csv | Select -First 4
Get-Content data\results\overnight_20261027\phase3b\per_order_summary.csv
Get-Content RESULTS_TABLE.csv | Select -First 5
```
Expected: 12 new chain orders, PRED faster than B4 in 12 of 12; effect for PRED about -19.3% [-20.0, -18.6]; 8 new orders on the 2P+7E setup, 8 of 8, -20.5%.
Plots: `data\results\overnight_20261027\phase3\analysis_ref_B4\fig_makespan_by_policy.png`, `fig_effect_vs_baseline.png`.
Re-derive a table from the raw logs (VERIFIED exit 0, about a minute): `.\.venv\Scripts\python.exe scripts\reproduce_subset.py --analysis-dir data\results\overnight_20261027\phase3\analysis_ref_B4 --log data\results\demo_20261027\repro_live_<time>.json` (give a new file name each time; the log is created exclusively).

## 3. Optional live run (about 6 minutes; do it only if asked and only on mains power)
A bounded reproduction of the hidden-cost comparison (VERIFIED last night, 11 blocks, 55 runs, all verified, PRED -21.79% [-23.67,-19.87] vs B4):
```powershell
$env:CAO_STUDY2_ADAPTER_CONFIG = "data\results\study2_20261024\designs\adapter_config_study2.json"
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/results/demo_20261027/design_demo.json')); d['name']='demo_live_repro'; json.dump(d, open('data/results/demo_20261027/design_live.json','x'), indent=1)"
.\.venv\Scripts\python.exe scripts\run_experiment.py --design data\results\demo_20261027\design_live.json --out data\results\demo_20261027\sessions_live --adapter caosched.study2.adapter:factory
.\.venv\Scripts\python.exe scripts\analyze_experiment.py --sessions data\results\demo_20261027\sessions_live\<SESSION_ID> --out data\results\demo_20261027\analysis_live --reference B4
```
Expected: the run prints a JSON with `"status": "complete"`; `effects.csv` has PRED_RANK_GREEDY with a negative effect near -20%. Do not rerun repeatedly to get a better number. The first command writes a new design file and refuses to overwrite an existing one.

## 4. Fallbacks
- Dashboard will not start: use section 2 only (files and plots), or open the PNG figures.
- A live run fails or the memory preflight aborts: show section 2 and the stored session `data\results\overnight_20261027\phase3\sessions\gen_unseen_orders` (148 runs, 148 verified).
- The numbers differ a little from the files: say that makespans move a few percent with background load; the stored sessions are the evidence.

## 5. What not to claim
- Not a universal 21% improvement; it is one workload family, measured on this laptop.
- Not better than the hand-written rule that knows the hidden parameter; level with it.
- No Raspberry Pi, real-network or GPU-scheduling result. Remote results are emulation only.
