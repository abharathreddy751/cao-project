# Raspberry Pi validation runbook

Status: **plan (nothing here has been run on a Pi).** Written 2026-10-27 from the repository at branch `revival/resource-state-aware`. Every command was checked against the code by reading it; the commands that need the device are marked `[needs Pi]`, the ones rehearsed on this laptop over loopback are marked `[rehearsed locally]` where the evidence file exists (see section 13). Placeholders are in angle brackets and must be replaced by real values; no IP address, link speed, Pi performance figure or dependency state is assumed.

What this runbook can establish: whether one extra remote worker (the Pi) behind a real network link changes the end-to-end makespan of the image-pipeline workload, for blind greedy B4 and for the transfer-aware predictive policy EFT_E1. What it cannot establish: GPU behaviour, the hidden-cost workload on the Pi (the remote adapter runs the image pipeline), Montage on ARM, or anything about a second real network.

Four claims stay separate and must never be substituted for one another: kernel-level speed on the Pi, local end-to-end scheduling benefit (already measured on the laptop), remote-transfer cost (measured in step 5), real-network end-to-end offloading benefit (the experiment in step 8).

## 0. Code state this runbook depends on

The remote adapter and the link calibration script accept a node that is already running on another host. This was added during the overnight sprint (see `OVERNIGHT_FINAL_REPORT.md`, section "Code changes"): `RemoteAdapter(remote_host=..., remote_port=...)` in `src/caosched/experiment/remote_adapter.py`, options `--remote-host` and `--remote-port` in `scripts/calibrate_link.py`, and `scripts/make_pi_design.py`. If those files are not present in your checkout, stop: the unmodified code can only spawn the node on the laptop.

## 1. Record on arrival (before any measurement) `[needs Pi]`

On the Pi, save to `data/pi_arrival/pi_info_<date>.txt` on the laptop (copy by `scp`):

```bash
date -u; hostname; uname -a; cat /etc/os-release
cat /proc/cpuinfo | grep -E "model name|Model|Hardware|Revision" | sort -u
nproc; free -m; df -h /; vcgencmd measure_temp; vcgencmd get_throttled
vcgencmd get_config arm_freq 2>/dev/null; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
python3 --version; pip3 --version
```

Record: power supply used (official 27 W supply or not), cooling (case/fan), `get_throttled` value (0x0 means no throttling or under-voltage since boot), CPU governor, ambient situation. Rerun `vcgencmd measure_temp; vcgencmd get_throttled` after every experiment session and attach the output to the session notes; a throttled or under-voltage Pi invalidates its timings.

On the laptop run `.\.venv\Scripts\python.exe -c "from caosched.experiment.runner import environment_manifest; import json; print(json.dumps(environment_manifest(), indent=1, default=str))" > data\pi_arrival\laptop_env_<date>.json` (needs the `data\pi_arrival` folder created first).

## 2. Network setup and connectivity `[needs Pi]`

1. Prefer a wired connection (Ethernet cable laptop to Pi or both to the same switch) for the first experiment; record the medium. A Wi-Fi run is a separate, labelled condition.
2. Give the Pi a fixed address or note its current one: `<PI_HOST>`. Pick a port: `<PI_PORT>` (the examples use 5555).
3. From the laptop: `ping -n 20 <PI_HOST>` and keep the output (round-trip statistics). `Test-NetConnection <PI_HOST> -Port <PI_PORT>` after the node is started (step 4).
4. Throughput probe, if `iperf3` is available on both ends (install on the Pi with `sudo apt install iperf3`; on Windows it must be downloaded separately and is not part of this project): `iperf3 -s` on the Pi, `iperf3 -c <PI_HOST> -t 20` and `iperf3 -c <PI_HOST> -t 20 -R` on the laptop. Keep the raw output. These are network properties and are reported next to, never instead of, the transfer times that the project measures itself in step 5.
5. Firewall: the Windows firewall only needs to allow outgoing connections. On the Pi allow the chosen port only from the laptop's address (`sudo ufw allow from <LAPTOP_IP> to any port <PI_PORT> proto tcp`, if `ufw` is used). Do not expose the port to other hosts.

## 3. Pi software `[needs Pi]`

The node needs only `numpy`, `Pillow` and `psutil` plus the `caosched` source (verified by reading the imports of `remote/node.py`, `apps/stages.py`, `apps/artifacts.py`, `util/threadpin.py`; torch is only imported by CUDA stages). Do not install the full `pyproject.toml` dependency list on the Pi (astropy, catboost and others are not needed and may not have ARM wheels).

```bash
python3 -m venv ~/cao-venv && source ~/cao-venv/bin/activate     # Python >= 3.11 is declared in pyproject.toml; check step 1 output
pip install numpy pillow psutil
# copy the repository to the Pi (from the laptop):  scp -r "src" "pyproject.toml" <PI_USER>@<PI_HOST>:~/cao/
cd ~/cao && pip install -e . --no-deps
python -c "import caosched.remote.node, caosched.apps.stages; print('imports ok')"
```

If Python 3.11 is not available, record the version found: the code declares `requires-python >=3.11`, and running on an older interpreter is **untested**. Record the numpy and Pillow versions (`pip list`) in the arrival file: ARM floating-point rounding may make results `numeric` rather than `exact` against the laptop reference; the verification (`verify_output`) accepts the project's numeric tolerance and the run manifest records which case occurred.

## 4. Smoke test and node health test `[needs Pi]`

Choose a token of at least the minimum length enforced by the node (`MIN_TOKEN_BYTES` in `src/caosched/remote/protocol.py`; the node refuses to listen on a non-loopback address without one). Generate it on the laptop and copy it to the Pi through a channel you trust; never put it in a file in the repository or in the logs.

On the Pi (pin to one core to match the single-worker model; core 3 is an example, take the number from step 1):

```bash
export CAO_REMOTE_TOKEN='<TOKEN>'
python -m caosched.remote.node --host 0.0.0.0 --port <PI_PORT> --affinity 3 --persistent
```

`--persistent` is required: without it the node serves one client and exits, and the experiment runner builds a new connection for every run (the first loopback rehearsal failed for exactly this reason: runs 2 to 25 died with `Worker(s) died during startup: ['R0']`; evidence in `data/results/overnight_20261027/phase4/rehearsal_sessions/rehearsal_loopback`).

On the laptop:

```powershell
$env:CAO_REMOTE_TOKEN = '<TOKEN>'
Test-NetConnection <PI_HOST> -Port <PI_PORT>
```

Health check of the node, the handshake and one real stage task (writes only under a new folder; use the calibration script in step 5 with `--reps 1 --warmup 0 --calib-tiles 64 --tile 64` for the quickest end-to-end exchange). A node that fails the token handshake, drops the connection, or reports an affinity mismatch must be fixed before any timing is done; save the error text in the session notes.

## 5. Measure kernel time, payload sizes and transfer on the real link `[needs Pi]`

Order matters: the laptop base profile first (idle laptop, plugged in, background programs closed), then the calibration through the real link.

```powershell
.\.venv\Scripts\python.exe scripts\profile_gpu_workload.py --out data\profiles\pi_t512_it1 --tile 512 --n-images 16 --denoise-iterations 1 --no-gpu
.\.venv\Scripts\python.exe scripts\calibrate_link.py --base-profile data\profiles\pi_t512_it1\<STAMP>_profile.json --out data\profiles\pi_t512_it1\pi_profile.json --tile 512 --n-images 16 --calib-tiles 64 128 256 512 --reps 5 --warmup 2 --max-p-slots 2 --remote-host <PI_HOST> --remote-port <PI_PORT>
```

Outputs: `pi_profile.json` (P and E rows from the laptop, R rows = kernel times on the Pi, and `link_calibration` = transfer time as `a + b * bytes` measured through the real network with the shim at zero) and `pi_profile_raw.csv` (every measurement, per stage, tile, repetition: kernel time, transfer time, payload bytes). From the raw CSV report for each stage: payload bytes (up plus down), kernel time on the Pi, measured transfer time, and the ratio transfer/kernel. Compare the Pi kernel time with the laptop E-core kernel time of the same stage from the base profile: that ratio is "Pi performance relative to a laptop E core" and is the first real Pi number of the project. Repeat for the compute-heavy level (`--denoise-iterations 30`, output folder `pi_t512_it30`) because a denoise with more iterations raises compute without changing the bytes moved: this is the only way the existing workload can reach a regime where remote execution could pay off. Expectation from the emulated sessions (not a prediction of the Pi): at level 1 transfer time was about as long as the remote kernel time for edges and features, and at level 30 on a fast emulated link the remote worker was used (about 1.7 tasks per run) with accurate predictions yet made EFT 3.78% slower (`data/results/overnight_20261027/phase4/e3_analysis_ref_EFT_no_remote`); in those emulated sessions the node ran on one local E core that is idle in the control conditions, so the remote conditions added no capacity beyond using that core through the link, whereas a Pi adds a machine, so a different outcome is possible and must be measured. The value 30 is a starting level for the sweep, chosen because it is the same order as the heavy chains in the hidden-cost workload; the actual choice may be changed here, before any experiment, but not after seeing experiment results.

Save `ping`/`iperf3` output of step 2 and `vcgencmd get_throttled` next to the profile files.

## 6. Coverage data and estimator calibration (supported workflow)

The remote policy EFT_E1 uses the static E1 profile plus the measured transfer model, so "retraining" for the Pi means the profile in step 5: no learned model is needed and none exists for the remote adapter. If the learned `PRED_RANK_GREEDY` model is to be used with a Pi pool later, it requires the `study2` workflow (`scripts/study2_retrain.py`, one command per pool layout) and a workload that the study2 adapter can send to a remote pool; **the study2 adapter has no remote pool, so this is not supported today.** Do not claim learned-model results on the Pi.

## 7. Rehearsal on the laptop (loopback), before touching the Pi `[rehearsed locally]`

Start a node on the laptop as a separate process and run the same commands against `127.0.0.1`. The adapter then labels the evidence `emulation`, not `real`, because the host is a loopback address. This checks the commands, file names and analysis chain, nothing about a network.

```powershell
Start-Process -FilePath .\.venv\Scripts\python.exe -ArgumentList "-m","caosched.remote.node","--host","127.0.0.1","--port","5555","--affinity","19","--persistent"
```

(Core 19 is an example; take a core that is not used by `RuntimeConfig` for P or E workers or the coordinator, or accept that it is shared. Stop the node afterwards through Task Manager or `Stop-Process -Id <PID>`.)

## 8. The experiment `[needs Pi]`

Design: image pipeline, tile 512, 16 branches (68 tasks), local pools 2 P + all E workers, remote pool R = the Pi, remote-eligible stages denoise, edges, features; shim at zero. Conditions: `B0_P_only` (local static floor), `B4_no_remote`, `EFT_E1_no_remote` (reference), `B4_remote`, `EFT_E1_remote`. Block 0 is a warm-up (excluded by the existing design rule), then at least 12 analysed blocks, randomised order within each block by the existing planner. A higher number of blocks is allowed only if fixed before the first run (see step 9). Two compute levels, run as two separate sessions: `--denoise-iterations 1` and `--denoise-iterations 30`, each with its own profile from step 5.

```powershell
.\.venv\Scripts\python.exe scripts\make_pi_design.py data\results\pi_<date>\designs_it1 data\profiles\pi_t512_it1\pi_profile.json --host <PI_HOST> --port <PI_PORT> --n-blocks 13 --denoise-iterations 1 --name pi_remote_it1
.\.venv\Scripts\python.exe scripts\memory_preflight.py --min-free-gb 2
$env:CAO_REMOTE_TOKEN = '<TOKEN>'
$env:CAO_REMOTE_ADAPTER_CONFIG = "data\results\pi_<date>\designs_it1\adapter_config_pi.json"
.\.venv\Scripts\python.exe scripts\run_experiment.py --design data\results\pi_<date>\designs_it1\design_pi.json --out data\results\pi_<date>\sessions --adapter caosched.experiment.remote_adapter:factory --session-id pi_it1
```

Then the same with `it30`. Hash the design file (`Get-FileHash -Algorithm SHA256 ...\design_pi.json`) and write the plan (conditions, blocks, seed, decision rule of step 10) into a plan file with its own hash **before** the first block. Record `vcgencmd measure_temp; vcgencmd get_throttled` before and after each session. Do not use the laptop for anything else during a session; keep it on mains power.

## 9. Integrity, timeouts, failures

The runner already: refuses to start below `min_free_ram_gb` (2.0 in the generated design), keeps every run directory, marks failed and timed-out runs (`run_timeout_s` 900) without discarding them, verifies the output of each run against the CPU reference (exact or numeric) and marks the run failed if it does not match, hashes every event log and makes it read-only. If the Pi node dies, the next run fails with a connection error and the adapter rebuilds the pool; the failed run stays in the data. Rules to fix before the first block: a session with more than 25% failed runs in any one condition is reported as "incomplete" and not pooled with another session; a node restart mid-session ends that session (start a new session ID, never edit a session); a run that is slower than the others because `get_throttled` changed is reported, not removed.

## 10. Measurements and criteria

Taken from the raw logs by the existing analysis (`runs.csv`, `summary.csv`, `effects.csv`): end-to-end makespan; transfer time (`transfer_total_s`); scheduling overhead (`sched_overhead_total_s`, the per-dispatch decision time) plus the coordinator total in each run manifest (`extra.decision_time_total_s`), reported as two different quantities (see the overhead note in `OVERNIGHT_FINAL_REPORT.md`); tasks per pool (`extra.tasks_per_pool`) and the list of tasks placed on R (`extra.remote_tasks`); failure counts; for resource use, the Pi temperature, throttling flag and, if the Pi has `top`/`vmstat`, a periodic sample saved with the session (the project does not collect Pi resource use itself, so this is manual and marked "not measured by the framework" in the report).

Decision rule (fixed here, so it cannot change after the data): the primary contrast is `EFT_E1_remote` versus `EFT_E1_no_remote`, and a second contrast is `B4_remote` versus `B4_no_remote`, paired within block, log ratio, stratified bootstrap, Holm adjustment over all conditions against the reference (the existing analysis).
- Remote offloading **helps**: the 95% interval of the primary contrast lies entirely below 0 (Holm-adjusted p below 0.05).
- **No measurable advantage**: the interval includes 0. State the interval width, because this is "not resolved", not "equal"; equivalence may be claimed only if the interval lies inside +-2%, the margin used elsewhere in the project.
- **Too costly**: the interval lies entirely above 0, or `B4_remote` is significantly slower than `B4_no_remote`.
Also report `tasks_on_R`: a policy that never places a task on R has no remote effect to interpret (this happened for EFT in the emulated experiment).

## 11. Saving evidence and analysis (existing framework)

```powershell
.\.venv\Scripts\python.exe scripts\analyze_experiment.py --sessions data\results\pi_<date>\sessions\pi_it1 --out data\results\pi_<date>\analysis_it1 --reference EFT_E1_no_remote
.\.venv\Scripts\python.exe scripts\analyze_experiment.py --sessions data\results\pi_<date>\sessions\pi_it1 --out data\results\pi_<date>\analysis_it1_vs_B4 --reference B4_no_remote
.\.venv\Scripts\python.exe scripts\make_manifest.py data\results\pi_<date>\sessions\pi_it1
```

(`make_manifest.py` writes the SHA-256 manifest; check its usage text for the verify option used elsewhere in the project.) Copy `vcgencmd` and `ping` outputs into the same folder and hash them. Never overwrite a session; a repeat is a new session ID. Sessions at different iteration levels or on different network media are never pooled.

## 12. Rollback to the known working local demonstration

Nothing in this runbook edits existing results. If the Pi integration fails or leaves the repository in a doubtful state:

1. Stop the node on the Pi (Ctrl+C) and unset the laptop variables: `Remove-Item Env:CAO_REMOTE_TOKEN, Env:CAO_REMOTE_ADAPTER_CONFIG`.
2. The local demonstration does not use the remote adapter: `.\.venv\Scripts\python.exe -m caosched.dashboard --port 8765 --open` and the commands in `FACULTY_DEMO_CHECKLIST.md` work without the Pi.
3. Compare the working tree with the sprint snapshot: `data\results\overnight_20261027\snapshot\git_status.txt` and `git_diff_stat.txt`. The files changed during the sprint are listed in `OVERNIGHT_FINAL_REPORT.md`; reverting one of them is `git diff <file>` to inspect and a manual restore from the diff (do not use `git checkout --` or `git reset` on the whole tree: it holds uncommitted evidence).
4. Re-run the focused tests: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q tests\test_remote_adapter.py tests\test_remote.py tests\test_study2.py tests\test_claims.py`.

## 13. Rehearsal evidence, first two hours after the Pi arrives

The local rehearsal (loopback external node, label `emulation`, 5 conditions x 5 blocks, 25 of 25 runs ok and verified) is in `data/results/overnight_20261027/phase4/rehearsal_sessions/rehearsal_loopback2`, its analysis in `phase4/rehearsal_analysis`; the first attempt `rehearsal_loopback` failed (see step 4) and is kept. Hour 1: steps 1 to 4 (arrival record, network, software, smoke test) and step 5 for the `it1` level. Hour 2: step 5 for `it30`, then start the `it1` session (about 13 blocks x 5 conditions; the duration depends on the measured remote transfer, so take the estimate from the rehearsal timing and the first Pi block). Stop and ask for a decision if the Pi kernel time is more than an order of magnitude slower than a laptop E core (offloading cannot pay under the current workload; record the number and report it as a result).
