# Submission package (built 3 November 2026)

Everything for the review submission is in this one folder. The files of 1 November in `D:\cao project\publications\` were **not changed or deleted**; this folder holds the updated versions, which describe the final static-versus-dynamic benchmark (CPU and RTX 3050 GPU).

## What the course asked for and where it is

| Required item | File here | Format and size (Word-rendered PDF) |
|---|---|---|
| Review 1: domain, problem statistics, survey of publications, patents, products, technology trends (and their adoption status) | `01_Review1_Survey_IEEE` (.docx and .pdf) | IEEE two-column, 8 pages |
| Review 2: redo of the base work, gaps, proposed work | `02_Review2_BasePaper_Gaps_ProposedWork_IEEE` | IEEE two-column, 8 pages |
| Review 3: implementation, architecture, methodology, results | `03_Review3_Implementation_Results_IEEE` | IEEE two-column, 10 pages |
| Project demo: existing implementation versus proposed work | `04_Project_Demo_Existing_vs_Proposed` (.pptx and .pdf); also `09_Final_Static_vs_Dynamic_Demo` (10 slides, the results deck) | 15 slides |
| Final project report, consolidated (one upload for DA1, DA2, DA3) | `05_Final_Project_Report` | 23 pages, Times New Roman 12 pt, 1.5 spacing, 1 inch margins (within the 20 to 30 page range) |
| IEEE two-column draft, at least 14 pages (Lab 10) | `06_Final_IEEE_Paper_Draft`; double-blind copy `06b_Final_IEEE_Paper_Anonymous_for_Double_Blind_Review` | IEEE two-column, 14 pages each |
| Venue, Scopus quartile and IPR route | `07_Publication_and_IPR_Plan` | 6 pages |
| IPR IDF draft (Lab 9) | `08_IPR_Invention_Disclosure_Draft` | 5 pages |
| Video of the demo | `10_Demo_Video_Script_and_Shotlist` (script and shot list; the recording is yours to make) | 2 pages |
| GitHub link: dataset, source, other files | `GITHUB_RELEASE_PACKAGE/` (zip bundle and push instructions) | about 216 MB, 8,300 files |
| Updated project guide | `CAO_Project_Complete_Explanation_UPDATED.pdf` (the 1 November guide is unchanged in `D:\cao_project_guide_output\`) | 24 pages; new Section 16 |

## What to upload on VTOP (folder `VTOP_UPLOAD`)

| VTOP item | File |
|---|---|
| DA1 | `DA1_Review1_Survey_and_Comparative_Analysis` |
| DA2 | `DA2_Review2_Base_Paper_Redo_and_Gaps` |
| DA3 | `DA3_Review3_Proposed_Work_Implementation` |
| Consolidated report (one upload for all three DAs) | `Consolidated_Report_for_DA1_DA2_DA3` |
| Lab 9, IPR IDF B draft | `Lab9_IPR_IDF_B_Draft` |
| Lab 10, IEEE two-column draft (14 pages) | `Lab10_IEEE_2column_Draft_14pages` |

Each exists as `.docx` (editable) and `.pdf`. The VTOP files are copies of the numbered files.

## What only you can do (nothing here was done on your behalf)

1. **Fill the placeholders:** institution, department, guide, e-mail, repository URL, signatures and dates. They are marked in square brackets in every document. Confirm names, registration numbers and author order.
2. **GitHub link:** nothing was pushed. Pushing makes the work public, which can end patentability. Decide the IPR question first; `GITHUB_RELEASE_PACKAGE\GITHUB_PUSH_INSTRUCTIONS.md` has the steps (private repository first).
3. **Demo video:** record it with the script in `10_...`; upload it as unlisted or as a restricted Drive link; no video exists yet.
4. **Lab 9 template:** the institution's IDF-B template was not available; `08_...` follows the usual IDF sections so the text can be pasted into the official form.
5. **Venue facts:** CCGrid 2027 dates were read again on 3 November 2026 (abstract 24 Nov. 2026, paper 1 Dec. 2026, 10 pages including references, double-blind). Journal quartiles come from aggregator pages that quote SCImago (FGCS Q1, IEEE TPDS Q1, JSA Q1, JPDC Q1; CCPE mixed); confirm each on scimagojr.com and Scopus before submitting. A 10-page cut of the 14-page paper is needed for CCGrid.

## What the documents say (headline, primary workload, 24 blocks, Holm-adjusted)

The dynamic dispatcher (PRED) is 17.8% [16.7, 18.8] faster than blind B4 on the CPU and 21.2% with the strict GPU set, and 5.2% [4.6, 5.9] (CPU) and 12.2% [11.1, 13.4] (strict GPU) faster than the static HEFT plan from the same cost model. The GPU helps PRED (2.6% strict set, 7.5% extended set) but not blind B4. Limits that every document states: a hand rule that knows the cost parameter is within 1% of PRED; no gain without spread in task cost; end-to-end cost terms and a hybrid selector add nothing; the GPU cost model has 23% to 31% median error; an earlier session found HEFT level with PRED; one machine, one workload family; the remote worker is emulated and **no Raspberry Pi or real-network result exists**.

## Checks done on this package

* The tables and figures of the final benchmark (primary table, ten contrasts, six workloads, GPU, timing, overhead, hold-out error, appendices) are generated from the stored result files (`RESULTS_TABLE_FINAL.csv` and the analysis folders) by scripts in `_build\`, not typed. Tables about the earlier study and the literature carry over from the 1 November documents (typed there from their evidence files).
* A layout audit (`_build\check_pdf.py`) found no text or image outside the margins, no unresolved cross-reference and no citation formatting fault in the IEEE documents; the pages were also looked at as images. Figures and tables are one column wide, citations use the IEEE form `[1], [2]`, page numbers are on every page.
* Tests: 520 of 521 pass. The one failure, `tests/test_profile_montage.py::test_profile_format_csv_fit_and_cleanup`, refuses to start because free RAM was 1.44 GB against its own 2 GB gate; it is environmental. The 521 tests were last all green on 2 November, before the dashboard v2 and v3 packages were added; those two packages have no unit tests.
* Not visually verified in a browser: the dashboard v2 and v3 screens after the last edits (checked through their endpoints only).

## Folder contents

`01`–`10` deliverables; `VTOP_UPLOAD\` exact upload set; `GITHUB_RELEASE_PACKAGE\` bundle; `supporting\` (final experiment report, results table, claims, evidence index, demo checklist and script); `figures\` (final-study figures, PNG); `_build\` (every script that produced the documents, re-runnable); `_draft\` (raw outputs of the last build); `_fig\` (figure sources).

To rebuild a document: `.\.venv\Scripts\python.exe SUBMISSION_FINAL\_build\run_build.py build_review3.py` (IEEE documents are built in two passes so that figure and table numbers resolve; Microsoft Word must be installed for the PDF export).
