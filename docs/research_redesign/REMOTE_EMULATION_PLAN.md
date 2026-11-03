# Emulated remote-pool experiment: plan

Status (2026-10-13): **[plan]**. Code and tiny tests exist; nothing below has been run on the experiment scale. Every command is marked `[not yet run]`. All results of this experiment will carry the label **[emulation]** (PROJECT_SPEC section 2 and 5, supporting contribution 2: "transfer-aware placement to a remote pool, evidenced on this machine only as [emulation]").

Files: `src/caosched/experiment/remote_adapter.py` (adapter), `scripts/calibrate_link.py` (calibration step, writes its file), `scripts/make_remote_design.py` (design), `tests/test_remote_adapter.py` (tile 64 tests).

## 1. What is emulated

* Pool `R` is a real node process (`caosched.remote.node`) pinned to the last E core of this machine, reached through the real proxy and a real loopback TCP connection. The real input artifacts are sent and the real output bytes come back (op `stage`); the output is verified against the single-process CPU reference (`verify_output`: exact, else numeric).
* The link is the shim of `caosched.remote.link`: before each message of n bytes the sender waits `latency + per_message + n / bandwidth`, then really sends the bytes. `latency_ms` is the one-way delay applied to each message; a task sends one request and receives one reply, so the delay is paid twice per task plus the byte time in both directions.
* The scheduler sees R as a pool with a transfer term: EFT uses `FileTransferModel` = configured link delay both ways + the socket cost (`a + b * bytes`) measured with the shim at zero by `scripts/calibrate_link.py` (stored as `link_calibration` in the profile). B4 has no cost model; its priority is P, E, R.
* Every run stamps `RunRecord.extra['evidence_label'] = 'emulation'`, the link parameters (`link_kwargs` as configured, `link` as given to the shim), the node core, the pools, and the tasks that ran on R. The adapter sets `evidence_label_override = 'emulation'` so `session.json` and run manifests carry the label; the design file carries it too.

Links (EMULATED LABELS: numbers given to the shim, not measurements of any real network):

| name | latency_ms (one-way, per message) | bandwidth_mbps | per_message_ms | jitter_ms |
|---|---|---|---|---|
| `fast_lan` (LAN-like) | 0.2 | 1000 | 0.05 | 0 |
| `slow_wan` (WAN-like) | 30 | 20 | 0.1 | 0 |

## 2. What is NOT emulated and what is not claimed

* No real network: no loss, reordering, congestion, shared queues, or variable delay. **Jitter is not supported** by the shim; the adapter rejects `jitter_ms != 0` instead of ignoring it, so no jitter claim can be made.
* No foreign clock: the node shares this machine's clock (`same_clock=True`). The `same_clock=False` path is not exercised here.
* No security beyond the token handshake already covered by `tests/test_remote.py`; the loopback run uses the no-token development default. No claim about authentication or about a remote host.
* Not a faster or different device: R is one E core of this machine, so R computes at E-core speed. The node core is taken out of E in **every** condition (idle in the controls), so the remote conditions add no hardware relative to the controls; they only allow that core to be used through the link. Any benefit is therefore bounded by one E-core worth of capacity.
* Not Montage and not the GPU workload; no claim about real edge offloading, ARM or the Raspberry Pi (those stay **[plan]**).
* The E1 profile rows: P and E from a pinned solo process on the first core of each pool, R from the node on its core. Core-to-core differences within the E class are not modelled.

## 3. Design (written by `scripts/make_remote_design.py`)

* Workload: image pipeline, tile 512, 16 branches (2048 x 2048 source, 68 tasks). Remote-eligible stages: denoise, edges, features (the stages whose payload sizes the model knows; fan-in stages stay local). Why tile 512: transfer must be a visible share of a task for transfer-aware placement to be testable; for these O(pixels) stages bytes and compute both scale with the pixel count, so the ratio is set mainly by the link, and 512 keeps the per-message and per-decision costs small relative to a task. This is a design reason, not a measurement: the design file stores `analysis_plan.profile_check` (modelled transfer / R kernel time per stage and link, computed from the calibrated profile), and the analysis reports the measured transfer share.
* Pool (all conditions): 2 P + 6 E + R (`max_p_slots = 2`: with six fast workers local capacity is not scarce and an extra remote worker cannot matter; the scarce-P regime is the one used in section 12/13 of EVALUATION_PROTOCOL.md).
* Conditions (7), 12 blocks, seeded random order within each block, one persistent seed: `B0_P_only`, `B4_no_remote`, `EFT_E1_no_remote` (reference), `B4_remote_fast_lan`, `EFT_E1_remote_fast_lan`, `B4_remote_slow_wan`, `EFT_E1_remote_slow_wan`. The two link settings are in the same blocks, so link effects are paired within block.
* Holm threshold and minimum attainable p (as section 13 of EVALUATION_PROTOCOL.md): confirmatory family = makespan of the 6 other conditions vs `EFT_E1_no_remote`, Holm over sign-flip p-values (`analysis/stats_paired.py`). Smallest Holm threshold 0.05 / 6 = 0.00833. Smallest attainable sign-flip p with n blocks is 2 / 2^n: 2/2^12 = 0.000488 (below the threshold). The smallest n that can pass is 8 (2/2^8 = 0.0078 < 0.00833), so up to 4 of the 12 blocks may be lost to exclusion for a contrast; below 8 valid paired blocks a contrast cannot be significant by construction and is reported "not resolved by this design".
* Pre-stated directions (from the mechanism, before any data; sizes are not predicted): D1 on `slow_wan`, `B4_remote` is slower than `B4_no_remote` (exploratory contrast, section 5 step 2). D2 `EFT_E1_remote` places fewer tasks on R on `slow_wan` than on `fast_lan` (descriptive, `tasks_per_pool`). D3 no direction for `EFT_E1_remote_fast_lan` vs `EFT_E1_no_remote`. A null result is a reportable outcome.
* Per-run timeout 900 s: the runner then executes each run in a child process, so a fresh pool and a fresh node are built per run; first-use costs of a fresh process hit all pools alike (`warmup=False` everywhere, as in the GPU adapter).

## 4. Commands (run from `D:\cao project`; Python = `.venv\Scripts\python.exe`)

Run ONLY when the machine is otherwise idle (the calibration and the session are timing measurements). The load monitor used for the confirmatory sessions should run alongside: `scripts/load_monitor.py`.

1. P and E profile rows at the experiment tile (`data/profiles/remote_t512` must not exist). **[not yet run]**
   `.venv\Scripts\python.exe scripts\profile_gpu_workload.py --out data\profiles\remote_t512 --tile 512 --n-images 16 --no-gpu`
2. Link calibration and R rows; writes `data/profiles/remote_t512/remote_profile.json` and `remote_profile_raw.csv` (exclusive create). **[not yet run]**
   `.venv\Scripts\python.exe scripts\calibrate_link.py --base-profile data\profiles\remote_t512\<STAMP>_profile.json --out data\profiles\remote_t512\remote_profile.json --tile 512 --n-images 16 --calib-tiles 64 128 256 512 --reps 5 --warmup 2 --max-p-slots 2`
3. Design and adapter config (new directory; exclusive create; stops if the profile lacks P/E/R rows or `link_calibration`). **[not yet run]**
   `.venv\Scripts\python.exe scripts\make_remote_design.py data\results\stage5_20261013\designs\remote data\profiles\remote_t512\remote_profile.json 12`
4. Pre-register: copy the design SHA-256 (`Get-FileHash -Algorithm SHA256 <design_remote.json>`) and the contents of section 3 into a new section of EVALUATION_PROTOCOL.md BEFORE the first block. **[not yet run]**
5. Run the session (about 7 conditions x 12 blocks = 84 runs). **[not yet run]**
   PowerShell: `$env:CAO_REMOTE_ADAPTER_CONFIG = "D:\cao project\data\results\stage5_20261013\designs\remote\adapter_config_remote.json"`
   `.venv\Scripts\python.exe scripts\run_experiment.py --design data\results\stage5_20261013\designs\remote\design_remote.json --out data\results\stage5_20261013\remote_sessions --adapter caosched.experiment.remote_adapter:factory --session-id remote_confirm`

## 5. Analysis (after the session is complete)

1. Confirmatory, reference stated in the design. **[not yet run]**
   `.venv\Scripts\python.exe scripts\analyze_experiment.py --sessions data\results\stage5_20261013\remote_sessions\remote_confirm --out data\results\stage5_20261013\remote_analysis --reference EFT_E1_no_remote`
2. Exploratory (unadjusted, labelled as such; D1 and the effect of R within each policy). **[not yet run]**
   `.venv\Scripts\python.exe scripts\analyze_experiment.py --sessions data\results\stage5_20261013\remote_sessions\remote_confirm --out data\results\stage5_20261013\remote_analysis_vs_B4 --reference B4_no_remote`
3. Also report from the raw logs: tasks on R per condition (`tasks_per_pool`), measured transfer (`transfer_total_s`) against the model's prediction, utilisation, decision overhead, and every excluded run with its reason. Exclusion rules: section 12.5 of EVALUATION_PROTOCOL.md (unverified output, failed run, missing log). A remote run whose output is not exact/numeric is a failure of the mechanism and is reported before any makespan.

## 6. Outcome wording rules

* Say "emulated remote pool" or "[emulation]" next to every result. Never write "network", "edge", "offloading to a remote device" or "WAN/LAN performance" as a finding; `fast_lan` / `slow_wan` are the names of two shim settings.
* Each pre-stated direction is "supported" (direction as stated, Holm-significant for the confirmatory family), "not supported", or "not resolved by this design". No claim for an interval that includes zero. Non-significance is not evidence of equality.
* A benefit of R is claimed only as a paired makespan difference against `EFT_E1_no_remote` (same pool, node core idle) and only with its CI and the share of tasks that ran on R. A policy that never uses R has no remote effect to interpret.
* Link numbers are quoted as configured settings; calibration numbers (`a`, `b`) as the measured loopback socket cost of this machine.
* The result is not pooled with Montage or GPU sessions (different design hash and label).

## 7. What cannot be done now, and why

* Calibration and the session: the timed session chain is running; these are timing measurements and the session needs the CPU cores. Only the tile-64 tests were run (a few seconds each).
* Jitter: the shim (`remote/link.py`, `remote/proxy.py`) has no jitter; adding it means changing files outside this deliverable.
* Real network, foreign clock, ARM, other hosts: need a second machine (Raspberry Pi, later extension).
