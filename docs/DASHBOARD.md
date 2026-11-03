# Demonstration dashboard

A local, browser-based view of the implemented base framework. It reads the
project's own event logs, artifacts and verified results, and can start one
new live execution of the image-analysis DAG through the real runtime.

* Code: `src/caosched/dashboard/` (`data.py` read-only data layer, `live.py`
  live runner, `server.py` standard-library HTTP server, `static/` page).
* No new dependencies: Python standard library + numpy/Pillow/psutil (already
  required), plain HTML/CSS/JS/SVG. Binds to `127.0.0.1` only.

## Launch

```powershell
.venv\Scripts\python -m caosched.dashboard --open        # http://127.0.0.1:8765/
.venv\Scripts\python -m caosched.dashboard --port 8800   # another port
```

Stop it with Ctrl+C. Each screen also has its own URL (`#overview`,
`#workflow`, `#compare`, `#hardware`), and a finished live run reopens with
`#live=<session>`.

## Screens

| screen | shows | data source |
|---|---|---|
| 1 System overview | logical-processor roles (P workers, E workers, coordinator, simulated remote node), live per-LP CPU load and free memory, scheduler/application status, the remote node's self-reported capabilities, Raspberry Pi and T4 marked **NOT CONNECTED** with no metrics | `RuntimeConfig.from_topology()`, psutil (live); `worker_ready` event of a run |
| 2 Application workflow | the 68-task DAG with each task's state, assigned pool and worker; replay slider and Play; per-worker timeline (start/end/duration; remote row = node execution inside hand-off→result span); observed critical path after completion; per-task details including EFT's predicted wait/transfer/exec/finish for every candidate worker; real input scene and output edge mosaic; output verification | event log (`data/events/<accepted session>/…jsonl` for replay, `data/dashboard_runs/…` for live), run artifacts |
| 3 Scheduling comparison | B4 vs EFT_E1_rc for the four accepted sessions: makespan (mean, 95% CI), paired % change, compute÷transfer ratio (when transfer dominates), remote-path minus local per denoise task, remote placements per run, decision latency, full table | `data/results/phaseB_appdemo_sweep_20261004/supplementary_summary.json` |
| 4 Hardware expansion | intended laptop + Raspberry Pi + T4 architecture with executed / shim / not-tested markings; implementation status table; why physical hardware is needed (measured remote ≈ E-core compute; per-task break-even estimate) | `docs/REMOTE_DEVICES.md` (parsed at request time), Phase B summary |

Modes are labelled throughout. **HISTORICAL REPLAY** reads accepted, verified
sessions unchanged. **LIVE EXECUTION** is a new run started from the page.
The comparison screen is always historical.

## Live execution: what actually runs

The "Run live on this laptop" button starts `python -m caosched.dashboard.live`
as a subprocess (one run at a time). It refuses to start below 1.0 GiB free
memory, the experiment runner's own preflight threshold.

The subprocess builds the run exactly as `scripts/run_app_demo.py` does:
* `build_image_pipeline` with 1024×1024, grid 4, seed 11 and the chosen
  k ∈ {1, 4, 16, 64};
* `WorkerPool` with the topology's P and E workers plus one `RemoteSlot` node
  on LP11 behind `lan_1g`;
* `Coordinator` with the unchanged `GreedyEligibleScheduler` (B4) or
  `EarliestFinishTimeScheduler` + `RecalibratedEstimator` (EFT_E1_rc).

It then verifies the final package against `run_reference` with
`verify_output`. `test_live_configuration_matches_the_accepted_sessions` checks
that this configuration equals an accepted session's manifest.

There are two deliberate differences from the experiment runner:
* Output goes to `data/dashboard_runs/live_<stamp>_<policy>_k<k>/`, never into
  `data/events`, `data/artifacts` or `data/results`. A live run is a
  demonstration, not an experiment record, and its single makespan is not
  comparable to the accepted means.
* There is no stage profiling. EFT's E1 estimator reads the stage profile
  measured by the accepted session of the same k (read only).

## Verified (2026-10-04)

* EXECUTED and VERIFIED: a live EFT_E1_rc run at k=16 through the server API
  (`live_20261004T200103_EFT_k16`). It completed 68/68 tasks (21 P, 43 E, 4 on
  the simulated remote) and its output was **exact**: sha256 `6acdbb7c…`, the
  same as the verified output of accepted session k=16. The experiment
  evidence was still unchanged afterwards (12,512 files re-hashed).
* EXECUTED: every API endpoint, including rejection of path traversal,
  non-accepted sessions and invalid live parameters. The four screens were
  rendered in headless Chrome in dark and light mode with no console errors.
* Tests: `tests/test_dashboard.py`, 12 passed and 1 skipped. The skipped test
  is the end-to-end live-run test, which skips itself below 1.5 GiB free
  memory; this machine had 1.14 GiB. The full suite gave 178 passed and
  1 skipped.

## Known limitations

* The remote worker is **simulated**: a node process on an E-core of this
  laptop behind a software link shim. No Raspberry Pi or NVIDIA T4 is
  connected, executed or validated, and the dashboard shows no device
  metrics for them.
* The run takes about one second, so live mode mostly shows workers starting
  and then the finished run. Use Play to step through any finished run.
* Live runs need about 0.65 GiB for 10 worker processes. With Chrome open on
  8 GB they may be refused (below 1.0 GiB free).
* CPU load is psutil's per-logical-processor sample every 2 s.
* The edge-mosaic preview is contrast-stretched for display; the artifact
  itself is unchanged.
* Cross-level comparisons are descriptive. Levels are separate sessions,
  and B4 ran first in 8 of 10 pairs at every level.

## Five-minute faculty demonstration

1. **Overview (≈45 s).** Point to the LP grid: 2 P workers, 6 E workers, a
   reserved coordinator core and the simulated remote node on LP11. Show the
   node's own report (`Windows · AMD64 · CUDA not available`) and the Pi/T4
   cards marked NOT CONNECTED.
2. **Workflow, replay (≈90 s).** k=16 EFT run is preselected. Press **Play**:
   tasks fan out from `source` into 16 tile lanes and turn the colour of
   their pool. Click a green `dn·R` task to show EFT's prediction table (the
   remote candidate wins by a few ms including its modelled transfer). At the
   end the critical path is highlighted, and the input and output images and
   the "exact" verification appear.
3. **Workflow, live (≈60 s).** Switch to *Live execution* and run EFT at k=16.
   The badge turns LIVE, and within seconds the run completes on this laptop
   with an exact output identical to the accepted k=16 result.
4. **Comparison (≈60 s).** Transfer dominates at k=1 (ratio 0.49×) and
   compute dominates at k=64 (38×). Yet the remote path is slower per task at
   every level, and EFT is 4.7–8.8% slower than B4. No speed-up is claimed.
5. **Hardware (≈45 s).** Implemented and verified today versus shim versus
   untested hardware. The break-even column shows why a Pi and a T4 are
   needed: the current "remote" is the same silicon, so the question
   "when does offloading pay?" can only be answered on real devices.
