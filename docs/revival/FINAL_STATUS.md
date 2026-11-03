# Revival: final status (2026-10-25)

Branch `revival/resource-state-aware` (base `study2/affinity` @ `ceae094`). Checkpoint outside the repo: `D:\cao_checkpoint_revival\` (git bundle of all refs, patch, status, copies of the untracked documents). No remote exists; nothing was pushed.

## 1. One-paragraph answer

The resource-state-aware policy is implemented, tested and runs correctly on the real worker pool (CPU, and with the real CUDA worker). The pre-registered **oracle gate failed**: on a mixed
DAG with controlled, changing CPU contention, a schedule-aware oracle that obeys the same rules (work-conserving, rank order, eligibility) was **not faster** than blind greedy B4
(B4 was 1.2% faster, interval -3.0% to +0.5%; the gate needed the oracle to be at least 5% faster). Result: **insufficient headroom for this workload**; per the protocol no pilot or
confirmatory study was run and nothing was tuned to change the verdict. On the uniform no-harm control the revival policies are level with B4 (+0.7% to +1.0%, all intervals inside +-2%) after
one measured, documented fix of the scheduling overhead. The original intuition "state-aware prediction beats static scheduling" holds only against static and naive rules (17% to 45%, earlier
studies); against blind greedy the evidence is level or null in every workload tested so far except the one-factor hidden-cost workloads of Study 2.

## 2. What was run (measured) and what was not

| Item | Status | Evidence |
|---|---|---|
| Baseline audit, tests, typing, reproduction of stored analyses | measured | `BASELINE_AUDIT.md`, `logs/baseline_*` |
| Contention calibration (spinner slowdown 1.77x / 2.72x for long tasks; none for short tasks; per-core sample cost 48 us) | measured | `data/results/revival_20261025/calibration_core0.json` |
| Offline model-form comparison (power law vs additive, leakage-safe) | measured | `model_eval.json` |
| Isolated coverage session + oracle table (9 blocks, 4720 rows) | measured | `cover_sessions/`, `oracle_rows_gate.json` |
| **Oracle gate** (13 blocks, 7 conditions, 2 held-out instances) | measured, **failed** | `gate_sessions/`, `analysis_gate_ref_B4`, `analysis_gate_ref_ORACLE_STATE` |
| Pilot and confirmatory study of the dynamic-contention workload | **not run** (gate failed; protocol section 5.4) | - |
| Engineering check v1 on the uniform batch with the CUDA worker (31 blocks) | measured, revival policies +2.2% to +2.6% (harm) | `uniform_sessions/`, `analysis_uniform_ref_B4_gpu` |
| Amendment A1 (lean hot path, lazy snapshot) and check v2 (31 blocks) | measured, revival policies +0.7% to +1.0% | `uniform2_sessions/`, `analysis_uniform2_ref_B4_gpu` |
| Demo trace of decisions under contention (one run, diagnostics on) | measured, **not** a result | `demo_run/`, `demo_trace.txt` |
| GPU contention / GPU telemetry | **not run**: `pynvml` is not installed, no GPU utilisation or VRAM signal exists; the GPU was used only as an ordinary fast worker in the uniform check | - |
| Remote-shim sweep of link delay and bandwidth | **not run** (loopback emulation only; the cost model accepts the existing `FileTransferModel` term, covered by the cost design but not exercised) | - |
| Raspberry Pi | not possible (no hardware) | - |

## 3. Results

**Oracle gate** (mean makespan in seconds over 12 analysed blocks, instances g1 and g2, 3 of 6 P cores shared with 2 spinners for 1 s, then another 3 cores for 1 s):

| Policy | Mean (s) | vs B4 |
|---|---:|---|
| PRED_RANK_GREEDY (learned, existing) | 2.662 | -1.9% (-3.9 to -0.2) |
| B4 blind greedy | 2.712 | reference |
| B4_param_first | 2.726 | +0.5% |
| ORACLE_STATE (schedule-aware, same rules) | 2.748 | +1.3% (-0.5 to +3.1) |
| B4_cost_first | 2.759 | +1.7% |
| B4_largest_first | 3.053 | +12.5% (11.1 to 13.8) |
| B0_P_only (static) | 3.105 | +14.5% (12.9 to 16.1) |

Headroom of the best simple rule over the oracle: -1.2% (-3.0 to +0.5). The contention was real (heavy tasks inside a hot window took 1.53x as long) but cost B4 only about 2.5% of its makespan: a
work-conserving rule already routes work to whoever is free, and a core slowed 1.5x to 2.7x is still about as fast as an E core.

**Uniform no-harm control, v2** (CUDA worker in the pool, 30 analysed blocks; effect = how much slower than B4_gpu): B0_P_only +37.3% (35.6 to 38.8); PRED_RANK_GREEDY_gpu +1.3% (-0.2 to +2.7, equivalence
not shown); RSA_TASK_ONLY_gpu +1.0% (0.05 to 1.9); RSA_STATE_ONLY_gpu +0.7% (-0.3 to +1.5); RSA_COMBINED_gpu +0.8% (-0.4 to +1.8). Scheduling time 1.0% to 1.1% of the makespan (B4 0.5%). All 186 runs verified. In v1 the same
policies were +2.2% to +2.6% slower (outside the margin): the per-pass state snapshot cost about 100 us on the E core the coordinator runs on, on every completion. That measurement, not a guess,
motivated amendment A1; v1 is kept and registered as claim V6.

**Why no headroom** (the data point to these causes; the first two are measured, the third is a reading): (1) a saturated pool leaves one idle worker at a time (only 18 of 295 dispatches
in the demo run had a choice), so placement is forced and only the order matters; (2) the contention changes speeds by less than the E/P speed gap, so B4 loses little; (3) the early heavy tasks
(1024 px sources) are dispatched at time 0, before any state signal exists.

## 4. Tests

`.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q`: **458 passed in 209 s** (`logs/final_pytest.txt`; baseline was 438; +13 in `tests/test_revival.py`, +7 registry checks for the new claims).
`mypy src scripts/revival_*.py --ignore-missing-imports`: no issues in 100 files (`logs/final_mypy.txt`). Output correctness: every run of every session above passed verification (all-CPU runs byte-identical to the sequential reference; CUDA runs within the recorded tolerances).

## 5. Claims registry

`docs/research_redesign/claims.json` gained V1 to V7 (oracle gate not supported; equivalence of the three revival ablations supported after A1; static P-only slower, supported; the v1 harm, not supported; the
existing PRED_RANK_GREEDY equivalence in this session, not resolved). `tests/test_claims.py` re-reads every number from its stored table.

## 6. Commands

```bash
# tests and typing
.venv/Scripts/python.exe -m pytest -p no:cacheprovider -q
.venv/Scripts/python.exe -m mypy src --ignore-missing-imports
# demo of the scheduler under contention (one run, prints the decision trace)
.venv/Scripts/python.exe scripts/revival_demo.py data/results/revival_demo2 data/results/revival_20261025/param_model_revival.json data/results/revival_20261025/blind_model_revival.json data/results/revival_20261025/calibration_core0.json
# reproduce the gate and the check tables from the raw logs
.venv/Scripts/python.exe scripts/reproduce_subset.py --analysis-dir data/results/revival_20261025/analysis_gate_ref_B4 --log /tmp/repro_gate.json
.venv/Scripts/python.exe scripts/reproduce_subset.py --analysis-dir data/results/revival_20261025/analysis_uniform2_ref_B4_gpu --log /tmp/repro_u2.json
# rerun the checks (mains power required; created exclusively, never overwrites)
CAO_REVIVAL_ADAPTER_CONFIG=data/results/revival_20261025/adapter_config_revival.json .venv/Scripts/python.exe scripts/run_experiment.py --design data/results/revival_20261025/designs/design_revival_gate.json --out data/results/revival_rerun/gate --adapter caosched.revival.adapter:factory
# roll back
git checkout study2/affinity            # the Study 2 state, untouched by the revival
git checkout baseline-null-result       # the stage 1-5 null result
git clone D:/cao_checkpoint_revival/repo_ceae094.bundle restored   # the full pre-revival repository
```

## 7. Not done / next, in order of value

1. A workload where placement is NOT forced: fewer ready tasks than workers is the only regime where a choice exists; the oracle gate on any such workload costs minutes (`revival_design.py gate`) and decides whether anything else is worth running.
2. GPU contention: install `pynvml` (an environment change, left to the owner), run a background CUDA spinner, and repeat the gate with the CUDA worker eligible for the three heavy stages.
3. Remote sweep: the existing `scripts/make_remote_design.py` and link calibration, now with `FileTransferModel` inside the revival cost.
4. Close the loop on the one-factor claim with the revival policies (they were only run in the no-harm control and the gate-free engineering check).

## 8. What the evidence says about the original intuition

Prediction-aware scheduling beats static and naive rules clearly and reproducibly. Adding live resource state to a work-conserving rank policy did not add measurable value on the workload built to need it,
because an oracle given perfect state knowledge could not beat blind greedy there. The honest status of the project's main claim is: **supported against static and naive scheduling; level with blind greedy where
placement has no freedom; not shown to beat the best simple rule anywhere except where a hidden task parameter makes ordering decisive.**
