# Dashboard UI check (2026-10-27, via the built-in browser, port 8766)

Server: `.\.venv\Scripts\python.exe -m caosched.dashboard --port 8766 --events-dir data\results\overnight_20261027\phase3\sessions --events-dir data\results\demo_20261027\sessions`

Observed:
- `/` and `/app.js` return 200; the earlier probe `/static/app.js` returned 404 only because that path does not exist (`server.py` serves `/app.js`).
- API endpoints `/api/system`, `/api/sessions`, `/api/comparison`, `/api/hardware`, `/api/live`, `/api/montage/runs` (203 runs: 148 + 55), `/api/gpu` all returned 200.
- Tab "5 Montage & GPU": with Workload "Montage (external commands)" the page says "No runs with an event log found for this workload". With Workload "GPU workload" it lists the 203 hidden-cost runs (the dashboard treats every workload kind other than montage as the second option). Selecting Run "order_e . B4 . 3859 ms . output ok" and Compare with "order_e . PRED_RANK_GREEDY . 3097 ms . output ok" shows two cards side by side: makespan 3858.9 ms vs 3097.0 ms, placement P 202 / E 55 vs P 172 / E 85, "scheduling 184.46 ms" vs "95.43 ms" (the coordinator scheduling time, the second overhead definition), output hash match for both (sha256 326842de5dc16d1df96b661f75f2a28d4f82b4b28fd1659373abefc3f443f8e4), event-log hash matches the manifest.
- The page header still says tabs 1 to 4 replay data from an earlier laptop (i5-1235U); tab 5 states the i5-13500HX. Not changed.
Not checked: tabs 1 to 4 were not clicked through in this check; "Live execution" on tab 2 was not started.
