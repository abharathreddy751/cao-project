# Prediction-Aware Dynamic Task Scheduling for DAG Workloads on Heterogeneous Cores

Empirical study of how much execution-time prediction is needed to improve DAG task
scheduling across P-core / E-core / remote-worker pools, on real Intel 12th-gen
hybrid hardware (no emulation).

**Current state (2026-10-14):** the redesign on branch `redesign/montage` (Montage workflow, 14 policies, six predictors, GPU workload, emulated remote pool; i5-13500HX, not the i5-1235U below) has no implementation left open except the Raspberry Pi 5 extension (no hardware); the other open items (paywalled papers, project licence, emulated remote pool, one machine) are listed in `FINAL_REPORT.md` section 14.3. Start with `docs/research_redesign/FINAL_REPORT.md` and `docs/research_redesign/RESEARCH_STATUS.md`; reproduction steps are in `docs/research_redesign/REPRODUCE.md`. The sections below and `PROJECT_STATUS.md` describe the earlier i5-1235U phases 0-6 and are historical.

See `ARCHITECTURE.md` for the system design and `PROJECT_STATUS.md` for current
progress, phase-by-phase results, and known limitations.

## Setup (Windows, native Python — no Docker/WSL required)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .
```

## Phase 0: hardware characterization

```powershell
.venv\Scripts\python scripts\phase0_characterize.py
.venv\Scripts\python scripts\phase0_benchmark.py --quick
.venv\Scripts\python scripts\phase0_gate_report.py
```

Outputs land in `data/environment/`, `data/benchmarks/`, and `data/reports/`
respectively. Nothing in this repository is a fabricated or manually typed
benchmark number — every CSV/JSON row is produced by running the above scripts.

## Phase 1: core runtime

```powershell
.venv\Scripts\python scripts\run_dag.py --size 256
```

Runs independent / chain / fork-join / mixed DAGs through the real coordinator
and affinity-pinned P/E worker pools (core mapping from Phase 0 topology).
Per-run event logs land in `data/events/` (never overwritten).

## Phase 2: baseline schedulers (B0-B7)

```powershell
.venv\Scripts\python scripts\profile_static.py     # measure the static profile (E1) on this machine
.venv\Scripts\python scripts\run_baselines.py      # replay every trace under every policy
```

Settings live in `config/phase2.yaml`. The project brief is in
`docs/PROJECT_BRIEF.md`.

## Phase 3: estimator ladder (E0-E5)

```powershell
.venv\Scripts\python scripts\collect_campaign.py        # randomized interference campaign
.venv\Scripts\python scripts\train_e4.py --campaign data\events\campaign_<stamp>
.venv\Scripts\python scripts\evaluate_estimators.py --e4 data\models\e4_<...>.json --phase2 data\events\phase2_<stamp>
```

Settings live in `config/phase3.yaml`.

## Phase 4: predictive scheduling (EFT ladder, P, O) and decision regret

```powershell
.venv\Scripts\python scripts\run_phase4.py                       # experiment + regret analysis
.venv\Scripts\python scripts\run_phase4.py --analyze-only <exp>  # re-analyse existing logs
```

Settings live in `config/phase4.yaml`.

## Phase 5: remote offloading (local link shim) and the end-to-end EFT ablation

```powershell
.venv\Scripts\python scripts\profile_static.py --remote-node-core 11 --proxy-core 4   # profile incl. R
.venv\Scripts\python scripts\derive_e2e_terms.py --profile <profile.json> --overhead-from-profile
.venv\Scripts\python scripts\run_phase5.py
```

Settings live in `config/phase5.yaml` (links, node/proxy cores, policies).
A physical remote device runs `python -m caosched.remote.node --host 0.0.0.0 --port N`.

## Tests

```powershell
.venv\Scripts\pytest
```

## Demonstration dashboard

```powershell
.venv\Scripts\python -m caosched.dashboard --open   # http://127.0.0.1:8765/
```

Local browser dashboard: system overview, the image-analysis DAG (replay of
accepted runs or a new live run through the real runtime), the B4 vs EFT_E1_rc
comparison from the verified sessions, and the Raspberry Pi / T4 expansion
status (not connected). Details, limitations and a five-minute demo script:
`docs/DASHBOARD.md`.
