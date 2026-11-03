# Submission package index (built 1 November 2026)

All files are in `D:\cao project\publications\`. Every document exists as `.docx` (editable) and `.pdf` (Word-rendered; the page counts below are from that rendering). Builders are in `_work/` (Python); figures are in `figures/`, generated only from stored result files.

| # | Required item | File | Format | Size |
|---|---|---|---|---|
| a | Review 1: domain, problem statistics, survey of publications, patents, products, trends | `01_Review1_Survey_IEEE` | IEEE two-column | 8 pages |
| b | Review 2: redo of base work, gaps, proposed work | `02_Review2_BasePaper_Gaps_ProposedWork_IEEE` | IEEE two-column | 7 pages |
| c | Review 3: implementation, architecture, methodology, results | `03_Review3_Implementation_Results_IEEE` | IEEE two-column | 7 pages |
| d | Project demo: existing versus proposed | `04_Project_Demo_Existing_vs_Proposed` (.pptx and .pdf), plus Chapter 13 of the report for the live-demo steps | slides | 14 slides |
| e | Final project report (consolidated) | `05_Final_Project_Report` | single column, TOC, appendices | 43 pages |
| f | IEEE two-column paper draft | `06_Final_IEEE_Paper_Draft` (with names) and `06b_..._Anonymous_for_Double_Blind_Review` | IEEE two-column | 7 pages each (about 6.5 pages text + references) |
| g | GitHub link: dataset, source, other files | `GITHUB_RELEASE_PACKAGE/` : `cao_release_bundle.zip` (source, tests, docs, final-study evidence, all deliverables) and `GITHUB_PUSH_INSTRUCTIONS.md` | zip + guide | 74 MB |
| h | Right conference / chapter / journal / IPR | `07_Publication_and_IPR_Plan` and `08_IPR_Invention_Disclosure_Draft` (IDF template draft) | report | 9 and 8 pages |

## Read these caveats before submitting

1. **No GitHub link exists yet.** Nothing was pushed or created online. Reason: pushing makes the work public, which can end patentability, and the licence and institutional permission are the authors' decisions. The bundle and step-by-step instructions are ready; creating a private repository and pushing takes about 15 minutes.
2. **Placeholders to fill:** institution, department, guide, e-mail, repository URL, signatures, licence. The names and registration numbers on the title pages (Lakshay S, 26MAI0064; Arkkadu Bharath Reddy, 26MAI0058) come from the project documents; confirm them and the author order.
3. **Venue dates are only partly verified.** CCGrid 2027 (abstract 24 Nov. 2026, paper 1 Dec. 2026, 10 pages including references, double-blind) was read on the call page; re-check it. Journals, workshops and any book-chapter call are listed as candidates, not verified.
4. **Results are exploratory and limited.** One laptop; a designed workload family; the remote worker was emulated (loopback plus delay shim); **no Raspberry Pi or real-network result exists**. The proposed dispatcher is level with an informed hand rule and with HEFT, and shows no gain on Montage, on the uniform batch or on the two-factor batch. These nulls are reported in every document.
5. **Statistics and patents** were checked against their sources; two statistics (IEA, TOP500) come from secondary reports; patent legal status is a Google Patents assumption; this is not legal advice and not a freedom-to-operate opinion. A professional prior-art search is needed before any filing.
6. **Do not publish before the IPR decision** (public repository, preprint, talk). See `07_Publication_and_IPR_Plan`.
7. **AI assistance** was used for code, analysis and drafting; the paper draft contains a disclosure sentence that the authors must adapt to the venue's rule.
8. **Source tree state:** the repository has about 90 uncommitted paths and nothing was committed during the final sprint. The sessions behind the numbers carry code hashes `f27b56f3`, `41a8f43b`, `ed70c36d` with a dirty flag; they were never pooled.

## Where the numbers come from

Headline numbers are read from `data/results/overnight_20261027/**/effects.csv` and `per_order_summary.csv`, listed with SHA-256 values in `EVIDENCE_INDEX.md`, summarised in `RESULTS_TABLE.csv` and `OVERNIGHT_FINAL_REPORT.md`, and re-derivable from raw logs with `scripts/reproduce_subset.py`.

## Suggested order of reading

Report (`05`) for the whole story; deck (`04`) and report Chapter 13 for the demonstration; `06` for the paper; `07` for what to do next.
