# Prompt to continue the CAO research redesign (paste into a new session)

Repo `D:\cao project`, branch `redesign/montage` (HEAD `4df01e0`, E4 fix committed; ~94 files uncommitted). Machine: Windows, i5-13500HX, 15.7 GB RAM, RTX 3050 6 GB. Python: `.venv\Scripts\python.exe` (3.11.9). Contract: `docs/research_redesign/*.md` (PROJECT_SPEC, ARCHITECTURE_DECISIONS, FOUR_STAGE_IMPLEMENTATION_PLAN, WORKLOAD_AND_DATA_PROVENANCE, EVALUATION_PROTOCOL, RESEARCH_STATUS). Pi 5 is out of scope.

## Rules (unchanged)
No fabricated numbers; every value traces to an evidence file; labels real/replay/emulation/simulation/plan; never touch existing `data/` files or the 68-task pipeline; one commit per stage on `redesign/montage` (no push, amend, force, reset); memory preflight before long runs; timed runs one at a time on an idle machine, interleaved seeded blocks; STOP and ask for admin/reboot/WSL2, paid access, deleting anything, licence blocks, or a gate failing after its fallback. Do not tune the experiment until it shows the wanted result; null results are reportable.

## State (2026-10-12)
- Stage 1 evidence: `data/results/stage1_20261011/valid/stage1_gate.json` (3/3 sequential runs, identical output hashes, WCS ok, DAG edges 147=147). GPU spike in `.../gpu/`. Failed attempts are kept and excluded (see MONTAGE_WINDOWS_BUILD.md).
- Montage: native Windows build, binaries `data/montage/bin_win64/` (hashes in `docs/research_redesign/montage_build/`), primary instance `data/montage/instances/d1.1_dss2b_c56.7_24.0` (59 tasks, 9 `mProject` ~160 s each pinned on P core LP 2, everything else seconds).
- Code for Stages 2-4 is written and reviewed but the FULL test suite has not been run cleanly (a run was killed with exit 137, cause unknown: check memory, run test files in chunks, background, output to a file).
- Nothing since `4df01e0` is committed.

## Remaining work, in order
1. Diagnose the killed pytest; get the full suite green (`pytest -q`, in chunks if needed) and run `mypy` on `src/caosched` (fix real errors only). Fix failures; do not weaken tests.
2. Stage 1: finalize docs (RESEARCH_STATUS.md, WORKLOAD_AND_DATA_PROVENANCE.md `PENDING(stage1_gate.json)` markers filled from the gate file, build doc), commit Stage 1 (docs, scripts, GPU spike, lock file).
3. Stage 2: profile pools with `scripts/profile_montage.py` (idle machine, from `valid/seq1`), then run the Montage DAG under every policy (B0..B5, random, EFT E1/E3, HEFT, PEFT, rank-EFT) through `scripts/run_experiment.py` + `caosched.experiment.montage_adapter:factory`, outputs vs the Stage 1 reference hashes; failure-injection suite; GPU output equals CPU; commit Stage 2.
4. Stage 3: collect data on several Montage instances/sizes (`scripts/montage_prepare.py`, one sequential reference per new instance) and the GPU workload (tiles >= 512); build the leakage-safe dataset; pilot; write thresholds and the model-selection rule into the docs BEFORE the main run; fit Ridge/CatBoost/MLP (TabM only if the entry rule holds); commit Stage 3.
5. Stage 4: pre-register the design in EVALUATION_PROTOCOL.md (repeat counts from pilot variance), run interleaved seeded blocks for Montage and the GPU workload, analyse with `scripts/analyze_experiment.py`, hash manifests, dashboard demo, clean-checkout reproduction (`scripts/reproduce_clean_checkout.py`), FINAL_REPORT.md and presentation outline; commit Stage 4.
6. Final short report: per stage pass/fail with gate values and evidence paths, commits, documents changed, unverified items, decisions needed.

## Known risks to state, not hide
Workload dominated by 9 equal `mProject` tasks (little scheduling headroom; a null result is allowed); PC not idle (WSL VM, Chrome, VS Code); unverified literature (patent claims text, HEFT/PEFT originals); DSS image licence unverified; GPU stage `img_denoise` margin small; patched Montage build and generator copy are Windows-specific.
