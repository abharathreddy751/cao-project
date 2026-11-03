# Updated 3 November 2026: this file supersedes the 1 November version; the bundle now also contains the final static-vs-dynamic study, dashboards v2 and v3, and the new SUBMISSION_FINAL folder.

# GitHub release: what is ready and how to push (nothing has been pushed)

The submission asks for a GitHub link with dataset, source code and other files. **No repository was created and nothing was pushed**, for two reasons that only the authors can resolve:

1. **Patentability.** Pushing the code makes the work public. In many jurisdictions public disclosure before a patent filing can destroy novelty. Decide the IPR question first (see `SUBMISSION_FINAL/07_Publication_and_IPR_Plan.pdf` and `08_IPR_Invention_Disclosure_Draft.pdf`).
2. **Permission and licence.** The institution may have rules on publication and ownership, and the repository contains third-party material (Montage, DSS2 images). Choosing a licence is the authors' decision.

If the authors decide to publish, the steps below take about 15 minutes. Use a **private** repository first and make it public only after the decision.

## What is in `cao_release_bundle_submission_20261103.zip` (about 216 MB, 8,300 files)

| Included | Notes |
|---|---|
| `src/`, `scripts/`, `tests/`, `config/`, `manifests/` | all source; 521 tests (520 pass; one RAM-gate test is environmental) |
| `docs/` | research-redesign registry (`claims.json`, 50 claims), architecture decisions, patent mapping |
| `data/results/final_20261101/` and `data/results/overnight_20261027/` | the final-study evidence (static vs dynamic benchmark) and the earlier overnight evidence: sessions (event logs, run manifests), analyses (effects, summaries, figures), per-order tables, verification, activity log (358 MB uncompressed) |
| root `*.md`, `*.csv`, `pyproject.toml`, `requirements*.txt`, `.gitignore` | reports, results table, feature matrix, runbook |
| `publications/` | reviews 1 to 3, final report, demo deck, paper drafts, plans, figures, document builders |

A scan of the text files in the bundle found no tokens, keys or passwords (patterns checked: GitHub and `sk-` style tokens, AWS key ids, private-key headers, `password=`).

## What is deliberately left out

| Excluded | Why |
|---|---|
| `.venv/` (5.4 GB), `.git/`, caches | rebuilt with `pip install -r requirements.txt`; git history is pushed by git, not by the zip |
| `data/` other than the overnight evidence (about 37 GB in total) | large raw results of earlier stages, Montage work directories and DSS2 images; the repository's own `.gitignore` already excludes them and records them by SHA-256 manifests instead |
| the Word/PDF render caches `_wordtest` | scratch |

If a reviewer wants the earlier stages' raw data, publish them on a data host (for example Zenodo or an institutional store) and link them from the README; do not put 37 GB in a git repository.

## Steps (PowerShell, project root)

1. **Check the working tree.** About 90 paths are uncommitted (the sprint committed nothing, by rule). Review them:

   ```powershell
   git status --short | Select-Object -First 40
   ```

2. **Do not commit large data.** The overnight evidence is 358 MB. Either keep it out of git and attach it as a release asset (`cao_release_bundle_submission_20261103.zip`), or use Git LFS for `*.jsonl`. GitHub rejects single files over 100 MB; the largest file in the evidence is far smaller, but the whole is better as a release asset.

3. **Create the repository** (private first) in the browser: github.com, New repository, no README (the project has one).

4. **Commit what you want to publish** on a new branch, for example:

   ```powershell
   git switch -c release/submission
   git add src scripts tests docs config manifests README.md pyproject.toml requirements.txt requirements-lock.txt *.md *.csv publications
   git commit -m "Submission package: source, reports, paper drafts"
   ```

   Review `git status` before committing; do not add `.venv`, `data/montage`, or raw result dumps.

5. **Add the remote and push:**

   ```powershell
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin release/submission
   ```

6. **Attach the bundle** as a release asset (Releases, Draft a new release, upload `cao_release_bundle_submission_20261103.zip`).

7. **For double-blind review**, do not use a personal repository: use an anonymised mirror (for example anonymous.4open.science) or upload the bundle as supplementary material, and remove author names from `README.md`, `pyproject.toml` and `publications/`.

## Suggested repository README (first lines)

> **caosched**: executing and comparing scheduling policies for task graphs on P/E cores, CUDA and remote workers, with paired statistics and overhead accounting.
> Quick start: `pip install -r requirements.txt`, `python -m pytest tests -q`, `python -m caosched.dashboard --port 8765 --open`.
> Evidence: `data/results/overnight_20261027/`; claims: `docs/research_redesign/claims.json`; reproduce a table: `python scripts/reproduce_subset.py <analysis dir>`.
> Limits: measured on one laptop; remote worker emulated; Raspberry Pi not yet tested; the headline result applies to a designed workload family.

## Licence

Left to the authors. Check the institution's rules, the third-party terms (Montage, DSS2) and the IPR decision before choosing.
