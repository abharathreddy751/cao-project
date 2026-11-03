# Dashboard tutorial (simple front-end guide)

## Start it

1. Open PowerShell in `D:\cao project`.
2. Run:

```bash
.\.venv\Scripts\python.exe -m caosched.dashboard --port 8765 --open
```

3. The browser opens at `http://127.0.0.1:8765`. If it does not, open that address yourself.
4. To stop it, press `Ctrl+C` in the PowerShell window.

Top bar (on every page):
- **Mode badge**: shows what kind of data is on screen. `HISTORICAL REPLAY` = old recorded runs. `LIVE` = a run started from this page.
- **Theme** button: switches light and dark colours. Only changes looks.

Five tabs at the top, numbered 1 to 5. Click a tab to switch page.

---

## Page 1: System overview

Shows the state of this laptop's scheduler at a glance.

- **Top tiles**: summary numbers (for example, number of tasks, workers, makespan of the last run). Read-only.
- **Logical processors, live CPU load**: one box per CPU thread. Bar height = how busy it is. Updates while a run is live.
- **Scheduler & application status**: text list: which policy is active, how many tasks are done, running or waiting.
- **Remote worker R0**: marked `SIMULATED`. It is not a real second computer. Read-only.
- **Raspberry Pi** and **NVIDIA T4**: marked `NOT CONNECTED`. Not part of this project yet. Ignore them in the demo.

---

## Page 2: Application workflow

Shows one run of the 68-task image-analysis application as a graph.

**Top controls: choose the data source**
- **Replay accepted run** (default): shows an old run that was recorded earlier. Safe for the demo, always works.
  - **Workload level**: size of the workload (how many images or tasks).
  - **Run**: which recorded run to show.
- **Live execution**: starts a new run on this laptop now.
  - **Workload level**: 1, 4, 16 or 64. Bigger = longer run.
  - **Policy**: `EFT_E1_rc (transfer-aware)` = the proposed scheduler. `B4 (greedy)` = the simple baseline.
  - **Run live on this laptop** button: starts the run. Wait until it says it finished. Takes time with a large level.
  - **or reopen**: pick an earlier live run from the list, without running again.
  - The grey text next to them shows messages such as errors or progress.

**Main area**
- **Image-analysis DAG** (graph): each box is one task; arrows = which task must finish first. Colours = stage type (legend below the graph).
  - Click a box to show its details in **Selected task** at the bottom.
- **Play** button: replays the run as an animation. Starts from the beginning.
- **Time slider**: drag it to jump to any moment of the run. The label next to it shows the time.
- **Worker timeline** (Gantt chart): one row per worker (CPU core). Each coloured bar = one task on that worker. Gaps = idle time. Click a bar to see that task.
- **Run summary**: text table: makespan, number of tasks, policy, and similar numbers.
- **Real application output**: image results produced by the run (for example, denoised pictures). Shows the **verify** line: whether the output matches the reference.
- **Selected task**: details of the clicked task (which worker, start time, end time, duration).

---

## Page 3: Scheduling comparison

Compares policies on the same workload. Charts are read-only.

- **Takeaways** (top box): short text summary of the main result.
- **Application makespan by workload level**: average total run time per policy, with a 95% range. Shorter bar = faster. Compare policies only inside the same level.
- **EFT_E1_rc vs B4, paired makespan change**: percentage change of the proposed scheduler against the simple baseline. Above zero = proposed one is slower. A range that crosses zero = no clear difference.
- **When does transfer dominate?**: shows when moving data to another worker costs more time than computing. Below 1 = moving costs more.
- **Remote path vs computing locally**: per task, is the remote path slower? Above zero = yes.
- **Remote placements per run**: how often each policy sent work to the simulated remote worker.
- **Reading these results**: plain-language explanation of the charts.
- **All values (table view)**: the same numbers as a table. Use it when a faculty member asks for exact values.

---

## Page 4: Hardware expansion

Plans, not results.

- **Intended architecture**: diagram of the planned multi-device setup.
- **Why physical hardware is needed**: text explanation.
- **Implementation status**: table of what is built, simulated, or not started.

---

## Page 5: Montage & GPU

Shows the real scientific-workflow runs.

- **Workload** dropdown:
  - `Montage (external commands)`: the astronomy image-mosaic workflow.
  - `GPU workload`: the separate CPU-versus-GPU image test.
- **Run** dropdown: which run to show.
- **Compare with** dropdown: pick a second run to compare. `none` = show one run only.
- Cards below show per-run results (for example, output hash and per-task times).
- For the GPU workload, a separate card shows CPU versus GPU timing and whether the outputs are equal.

Important: this page reads only run files with a `run_manifest.json`. The Stage 1 Montage runs are stored as `run.json` and may **not** appear here. Use `data\results\stage1_20261011\valid\stage1_gate.json` as the source for those numbers.

---

## Safe demo order

1. Page 1: show the overview and say the Raspberry Pi and T4 are not connected.
2. Page 2: keep **Replay accepted run**, press **Play**, click one task.
3. Page 3: show the makespan chart and the **table view**.
4. Page 5: show the GPU card.
5. Say clearly: the Montage scheduling comparison is not finished yet.

## Known limits

- The **Live execution** button starts a real run on this laptop. It uses CPU and memory. Close other heavy programs first.
- Charts on page 3 are from recorded data. They are not produced by pressing a button.
- The remote worker is simulated; do not present it as real hardware.
- Not checked: this guide was written from the page code (`static/index.html` and the API list in `server.py`). I did not click through the running dashboard in this session, so confirm the labels on screen before the demo.
