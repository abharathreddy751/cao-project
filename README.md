# Static Plan or Dynamic Dispatch? Task Scheduling on a Hybrid CPU/GPU Machine

Course project: *AI-Assisted Heterogeneous Computing Framework for Dynamic Task Offloading and Scheduling* (Computer Architecture and Organization). Authors: Lakshay S (26MAI0064) and Arkkadu Bharath Reddy (26MAI0058). Guide: Dr. Yokesh Babu S, Associate Professor Grade 1.

## Final version (3 November 2026)

The Python package `caosched` runs task graphs (DAGs) on a laptop with 6 performance cores, 7 efficiency cores and one CUDA worker (RTX 3050), and compares **static plans** (HEFT, PEFT, HEFT with end-to-end cost terms) with **dynamic dispatch** (blind greedy B4, a parameter-aware rule, and a predicted-rank dispatcher, PRED_RANK_GREEDY). Every policy uses the same ridge cost model, and the metric is the end-to-end makespan, so planning time is counted.

Headline result (primary workload: 16 heavy chains of 120 iterations, 24 blocks, Holm-adjusted):

* PRED is 17.8% [16.7, 18.8] faster than blind B4 on the CPU and 21.2% faster with the strict GPU set.
* PRED is 5.2% [4.6, 5.9] (CPU) and 12.2% [11.1, 13.4] (strict GPU set) faster than the static HEFT plan from the same model.

Limits, stated in every document: a hand rule that knows the cost parameter is within 1% of PRED; there is no gain when task cost does not vary; end-to-end cost terms and a hybrid selector add nothing; the GPU cost model has 23% to 31% median error; an earlier session found HEFT level with PRED; one machine and one workload family (the Montage workflow gave a null result); the remote worker is emulated and **no Raspberry Pi or real-network result exists**. This is a scheduler for the tasks of a program, not an operating-system scheduler.

## Where things are

| What | Where |
|---|---|
| All course deliverables (three IEEE review papers, 23-page report, 14-page IEEE paper, IDF draft, demo deck, video script) | `SUBMISSION_FINAL/` (start with `README_START_HERE.md`; upload set in `VTOP_UPLOAD/`) |
| Full experiment report and result table | `CAO_FINAL_EXPERIMENT_REPORT.md`, `RESULTS_TABLE_FINAL.csv`, `RESEARCH_CLAIMS_AND_LIMITATIONS.md`, `EVIDENCE_INDEX.md` |
| Final-study code | `src/caosched/final/`, `src/caosched/study2/`, `scripts/final_*.py`, `tests/test_final_*.py` |
| Protocols and amendments | `docs/final/`, `docs/research_redesign/` (claims registry `claims.json`) |
| Dashboards (original, v2, v3) | `src/caosched/dashboard/`, `dashboard_v2/`, `dashboard_v3/` |
| Small result files (analyses, models, manifests) | `data/results/` |
| Raw run logs and the full dataset (about 1.8 GB unpacked) | not in git (too large): Google Drive folder https://drive.google.com/drive/folders/1wOPOM7e8GOr36XvbjPTmlak9uYZQ48Bc , file `cao_dataset_raw_results_20261103.zip` (unzip into the repository root so the paths match) |
| Complete development history (older studies and their raw data) | same Drive folder, `cao_full_git_history_20261103.bundle` (`git clone cao_full_git_history_20261103.bundle cao-history`) |
| Data for dashboard tab 2 (replay of the earlier image-pipeline demo) | same Drive folder, `cao_tab2_demo_data_20261103.zip` (unzip into the repository root) |
| What was removed at the end of the project | `CLEANUP_RECORD.md` |

## Run it (Windows, Python 3.11)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .
.venv\Scripts\python -m pytest -p no:cacheprovider -q
.venv\Scripts\python -m caosched.dashboard_v3 --port 8770 --events-dir data\results\final_20261101\eval\sessions --open
```

Tab 3 of the dashboard shows the final results, tab 5 the DAG and worker timeline of any final run (type `PRED_RANK_GREEDY` in its filter), tab 6 runs one live block. The test suite has 521 tests; one test refuses to start when free RAM is below 2 GB, and a live run needs 2.4 GB free. The dashboard's tab 5 needs the raw run logs from the dataset zip on Google Drive, which are not in git.

---

# Earlier README (historical)

# Prediction-Aware Dynamic Task Scheduling for DAG Workloads on Heterogeneous Cores

Empirical study of how much execution-time prediction is needed to improve DAG task
scheduling across P-core / E-core / remote-worker pools, on real Intel 12th-gen
hybrid hardware (no emulation).

**Latest (2026-10-25):** see `docs/INDEX.md` for which documents are current. Study 2 (branch `study2/affinity`, `docs/research_redesign/STUDY2_REPORT.md`) confirmed that a learned, data-driven predictor beats blind and static scheduling where a task parameter hides the cost.

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

Revival (2026-10-25): resource-state-aware scheduling, oracle gate and results: `docs/revival/FINAL_STATUS.md`.
