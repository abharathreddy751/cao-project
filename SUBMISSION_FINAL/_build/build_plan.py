import sys
sys.path.insert(0, r"D:\cao project\SUBMISSION_FINAL\_build")
from report_docx1 import Report
from ieee_docx2 import export_pdf

OUT = r"D:\cao project\SUBMISSION_FINAL\_draft"


def title(r, t, sub):
    r.center("", 12, after=20)
    r.center(t, 22, bold=True, after=8)
    r.center(sub, 12, italic=True, after=6)
    r.center("Lakshay S (26MAI0064), Arkkadu Bharath Reddy (26MAI0058) | Version of 3 November 2026", 10, after=14)


# =====================================================================  07 Publication and IPR plan
r = Report(11)
title(r, "Publication and IPR Plan", "Where to publish the project, in what order, and what to decide first")
r.para("**Reading guide.** This plan separates what was verified from what was not. Dates and rules that were read on a call-for-papers page are marked *read*; everything else is marked *unverified* and must be confirmed "
       "by the authors on the venue's own page before any commitment. Nothing here is legal advice; patent matters need a registered patent professional.")

r.chapter("Recommendation in one page", new_page=False)
r.numbered([
    "**Decide the IPR question first (this week).** Publishing the paper or pushing the code makes the work public. In many jurisdictions public disclosure before filing destroys novelty. The institution's IPR cell, the guide, "
    "or a patent professional should decide whether any element is worth filing. The invention disclosure draft (`08_IPR_Invention_Disclosure_Draft`) is ready for that conversation. Until the decision, do not push to GitHub and do not post a preprint.",
    "**If no filing is wanted: submit the paper to IEEE/ACM CCGrid 2027** (double-blind, full paper up to 10 pages including references, IEEE two-column format; abstract due 24 Nov. 2026 and paper due 1 Dec. 2026, as *read* on the call page; re-check). "
    "The anonymous Lab-10 draft `06b` has 14 pages; CCGrid allows 10 pages including references, so a 10-page conference cut (drop the appendices, the earlier-study details and the long tables) must be made first. Weakness the reviewers will raise: one machine, one workload family, a hand rule within 1% of the dispatcher, emulated remote. State these limits in the paper (the draft does).",
    "**If the Raspberry Pi result is wanted first:** target a journal (Future Generation Computer Systems, Journal of Parallel and Distributed Computing, IEEE Transactions on Parallel and Distributed Systems, or Journal of Systems Architecture, all *unverified* for current scope, fees and turnaround) "
    "with an extended version that includes real-device results and the second workload family.",
    "**Book chapter:** only if a specific call exists (*unverified*; none was found in this work). Do not select one by guess.",
    "**Whatever the route:** fill author, institution, guide and e-mail placeholders; confirm authorship order and the guide's consent; check that the institution permits publication of the project.",
])
r.table("Route comparison",
        ["Route", "Fit", "Effort before submission", "Main risk", "Status of facts"],
        [["CCGrid 2027 (full paper)", "high: cluster, cloud and grid scheduling; empirical systems papers; double-blind", "low: 06b ready; polish and anonymise artefacts", "reviewers want real remote hardware and a second workload; tight deadline", "dates read on the call page; confirm"],
         ["Workshop co-located with a major systems conference", "medium: lower bar, shorter paper", "low to medium", "workshop list and dates unknown", "unverified"],
         ["Journal (extended version, after Pi measurement)", "high: room for 12+ pages, statistics, appendices", "high: Pi runs, second workload, clean-tree rerun", "longer review; fees at some journals", "unverified; check scope pages"],
         ["Book chapter", "medium: survey-style content (Review 1) suits it", "medium", "no verified call; publisher terms", "unverified"],
         ["Patent / IPR (India or US)", "low to medium: base patent and IBM grant occupy the obvious ideas", "medium: IDF, prior-art search", "publication-before-filing bar; cost; weak claims", "needs professional advice"]],
        [1.3, 1.4, 1.3, 1.3, 1.0], size=8.5)

r.chapter("Conference route: CCGrid 2027")
r.section("What was read")
r.para("The call for papers at {{ccgrid27}} was read in November 2026. It specifies IEEE two-column format, a limit of 10 pages including references for full papers, double-blind review, an abstract deadline of 24 Nov. 2026 "
       "and a paper deadline of 1 Dec. 2026. These dates were captured on the day of reading; call pages are updated, so **re-open the page and confirm the dates, page limits, artifact-evaluation rules and anonymity rules before submitting.**")
r.section("Fit and framing")
r.bullets([
    "Fit: scheduling of workflows on heterogeneous resources, edge-cloud continuum, performance evaluation, reproducibility.",
    "Frame the contribution as a measured, overhead-accounted study of when prediction helps, with a proposed dispatcher, not as a claim of a new learning algorithm. This matches the evidence and avoids the IBM-grant overlap.",
    "Lead with the final benchmark: with one cost model on both sides the dynamic dispatcher beats a static HEFT plan by 5.2% (CPU) and 12.2% (strict GPU set) and blind dispatch by 17.8% and 21.2%; then give the limits (a hand rule within 1%, a tie without cost spread, 23% to 31% GPU model error, an earlier session that found HEFT level).",
    "Anonymity: use `06b`; the repository link must be replaced by an anonymised artefact link or a statement; remove names from file metadata, figure captions and the dashboard screenshot.",
])
r.section("Checklist before 24 Nov. 2026")
r.numbered([
    "Authors, affiliations, guide permission and e-mail in the non-anonymous version; confirm the IPR decision.",
    "Re-read the call page; confirm abstract and paper dates, page limit and double-blind rules.",
    "Regenerate figures only from stored result files; confirm every number against `RESULTS_TABLE.csv` and `claims.json`.",
    "Decide whether to run a quick second workload family or the Pi before 1 Dec.; if not, keep the limitations paragraph as is.",
    "Prepare an anonymised artefact (zip of the reproducibility subset) if the call allows an artefact link.",
    "Register the abstract by 24 Nov., upload the PDF by 1 Dec.",
])
r.section("Realistic reviewer comments and answers")
r.table("Anticipated reviewer comments",
        ["Comment", "Answer available in the paper"],
        [["Gain is not larger than an informed rule", "Agreed and stated; the contribution is a generic learned model, overhead accounting and a map of when it helps"],
         ["Workload is designed to favour the method", "Stated as a threat; Montage, uniform and two-factor nulls are reported; dose and heavy-count sweeps show where it fails"],
         ["No real remote device", "Labelled emulation; runbook and rehearsal; Pi measurement planned"],
         ["Only one machine", "Stated; environment hash recorded; results never pooled across machines"],
         ["No comparison with learned DRL schedulers", "Not run; stated; surveyed gains are simulation-only and not comparable"],
         ["Sessions have different code hashes and a dirty tree", "Disclosed; never pooled; sprint changes do not touch the scheduler path"]],
        [2.4, 3.9], size=9)

r.chapter("Journal and workshop routes")
r.para("These are candidates based on where the surveyed papers appeared and on venue scope. Impact factors, fees, scope statements and turnaround times were **not verified** in this work; check each journal's own page.")
r.table("Candidate journals",
        ["Journal", "Why a candidate", "Evidence in this work"],
        [["Future Generation Computer Systems", "published workflow-runtime prediction ({{lotaru}}) and edge-offloading DRL work ({{sata}})", "appears in the survey"],
         ["Journal of Systems Architecture", "published lightweight heterogeneous scheduling on a real board ({{rodriguez}})", "appears in the survey"],
         ["IEEE Transactions on Parallel and Distributed Systems", "published HEFT and PEFT ({{heft,peft}})", "appears in the references"],
         ["Concurrency and Computation: Practice and Experience", "published the StarPU journal paper ({{starpu}})", "appears in the references"],
         ["Journal of Cloud Computing", "published several offloading papers ({{nieto,iov}})", "appears in the survey"]],
        [2.2, 3.0, 1.1], size=9)
r.table("Indexing and quartile status of the candidates (checked 3 Nov. 2026 on aggregator pages that quote SCImago; the quartile is category-specific and changes yearly, so confirm on scimagojr.com and Scopus before choosing)",
        ["Venue", "Reported quartile (SJR best quartile)", "How certain"],
        [["IEEE/ACM CCGrid 2027 (conference)", "conference; IEEE proceedings; Scopus indexing of the 2027 volume not yet verifiable", "dates verified on the call page: abstract 24 Nov. 2026, paper 1 Dec. 2026 (AoE), notification 1 Feb. 2027, camera-ready 16 Mar. 2027; 10 pages including references; double-blind; conference 24 to 27 May 2027, Dallas Fort-Worth"],
         ["Future Generation Computer Systems", "Q1 (several computer science categories)", "aggregators agree; SJR value varies by source"],
         ["IEEE Trans. Parallel and Distributed Systems", "Q1", "aggregators agree; SJR value varies by source"],
         ["Journal of Systems Architecture", "Q1 (Hardware and Architecture; Software)", "one aggregator; confirm"],
         ["Journal of Parallel and Distributed Computing", "Q1 (several categories)", "one aggregator; confirm"],
         ["Concurrency and Computation: Practice and Experience", "mixed: CiteScore Q1 or Q2 by category, JCR Q3", "no clear SJR quartile found; weakest candidate"]],
        [2.0, 2.2, 2.1], size=8.5)
r.para("**Recommended order.** (1) CCGrid 2027 with a 10-page cut of the Lab-10 paper if the IPR decision allows public submission; (2) otherwise or afterwards a Q1 journal (Future Generation Computer Systems or IEEE TPDS) with the extended version and real-device results. A book chapter needs a specific call (none verified).")
r.para("A journal paper should add: real Pi results, a second workload family, a rerun of the headline experiment on a clean committed tree, and the dispatch-loop fix applied in the source. That makes the claim "
       "of generality testable and removes three of the four threats a reviewer will raise.")

r.chapter("IPR route")
r.section("What the prior art already covers")
r.bullets([
    "Task graphs, eligibility-gated queues, in-degree counters and utilisation-based scaling: claimed by US 11,561,826 B1 ({{p_xilinx}}).",
    "Learned rank assigned to tasks of a DAG and rank-ordered execution on a heterogeneous SoC: disclosed by IBM US 11,740,933 B2 ({{p_ibm1}}); task execution estimates in IBM US 11,966,776 B2 ({{p_ibm2}}).",
    "Per-run profiling for CPU+GPU work split: Intel US 10,186,007 B2 ({{p_intel}}); duration prediction under core contention: Samsung US 10,162,671 B2 ({{p_samsung}}), lapsed.",
    "Runtime performance models for CPU/GPU DAG scheduling: StarPU ({{starpu}}), published; list scheduling: HEFT and PEFT ({{heft,peft}}), published.",
])
r.section("Candidate elements and their weaknesses")
r.table("Candidate inventive elements (not claims; for discussion with a professional)",
        ["Element", "Possible novelty", "Main weakness"],
        [["A: a late-binding dispatcher that orders ready tasks by predicted upward rank using a model fitted per (stage, pool) from execution logs on whichever numeric parameters vary, with no stage- or parameter-specific code", "generic parameter discovery from logs; refusal for unseen stage/pool; one-command refit for a new pool layout", "IBM rank-ordered learned dispatch; HEFT-type upward rank; ridge regression is standard; the result equals an informed rule"],
         ["B: a pre-deployment headroom gate: replay logs with an oracle estimator and enable predictive scheduling only if the headroom exceeds a threshold (5% in our design)", "decision method for when prediction is worth its cost", "method of evaluation may be treated as an abstract idea; weak technical effect; one gate failure shown (V1)"],
         ["C: two-metric overhead accounting (per-dispatch decision time versus coordinator scheduling time) with a detector for an idle ineligible worker defeating the dispatch loop's early exit", "diagnosis and fix of a dispatch-loop inefficiency", "software engineering detail; small effect (under one point on the gain)"],
         ["D: transfer-aware placement with remote-worker predictions", "avoids harm of blind remote placement", "no offloading gain was established; emulation only"]],
        [3.0, 1.8, 1.5], size=8.5)
r.para("**Assessment.** On the evidence read, element A is the only one with a plausible technical effect, and it sits close to the IBM grant; a patent on it would be narrow and uncertain. The measured result "
       "(level with an informed rule) weakens an argument of non-obviousness. A copyright/open-source release of the code and a publication are likely to deliver more value than a patent. The decision belongs to the "
       "authors, the guide and the institution.")
r.section("Timing rules")
r.numbered([
    "Do not publish a paper, preprint, poster, public repository, talk slide or demo video describing elements A to D before a filing decision is made. Public disclosure may bar patentability in many jurisdictions; grace periods differ by country and are not safe to rely on.",
    "If filing is wanted, give the invention disclosure draft to the institution's IPR cell or a patent agent, commission a prior-art search, and file (a provisional, where available) before submitting the paper.",
    "A paper under double-blind review is not yet public, but its content may be disclosed to reviewers; ask the professional whether filing before submission is needed.",
    "Keep the authors' contribution records (who conceived which element, with dates); the git history and ACTIVITY_LOG.md help.",
])
r.section("Software licence")
r.para("Choosing a licence is left to the authors: the repository contains third-party material (Montage, DSS2 images) with their own terms. For the GitHub package, exclude large or unlicensed data; choose a licence "
       "only after the IPR decision and check the institution's rules on ownership.")

r.chapter("Decisions needed from the authors")
r.table("Decision list",
        ["#", "Decision", "Default if undecided"],
        [["1", "File any IPR? (IDF draft ready)", "do not push, do not post a preprint; submit nothing public"],
         ["2", "Submit to CCGrid 2027 by 24 Nov. / 1 Dec. 2026?", "no submission; keep 06b ready"],
         ["3", "Run the Pi and second workload for a journal version?", "journal route deferred"],
         ["4", "Authors' names, order, institution, guide, e-mail", "placeholders remain"],
         ["5", "Repository licence and visibility", "private, unpushed"]],
        [0.4, 3.6, 2.3])
r.references()
o = OUT + r"\07_Publication_and_IPR_Plan"
r.save(o + ".docx")
print("07", export_pdf(o + ".docx", o + ".pdf"), len(r.cite_order))

# =====================================================================  08 Invention disclosure draft
r = Report(11)
title(r, "Invention Disclosure Form (Draft)", "Prediction-aware, rank-ordered, work-conserving task dispatch with a log-fitted generic runtime model")
r.para("**Template note (Lab 9).** The institution\u2019s IDF-B template was not available in this work; the sections below follow the usual IDF structure (administrative data, field, background, problem, summary, embodiments, prior art, advantages, inventor contributions) so that the text can be moved into the official form.")
r.para("**Status of this draft.** This is a working draft for discussion with the institution's IPR cell or a patent professional. It states what the project built and measured. It does not claim that the described "
       "elements are novel or non-obvious; the prior-art section lists documents that may anticipate or render obvious parts of them. All fields in square brackets are to be completed by the authors.")
r.chapter("Administrative data", new_page=False)
r.table("Form fields",
        ["Field", "Entry"],
        [["Title of the invention (working)", "Dispatch of dependent tasks on heterogeneous workers using a runtime model fitted from execution logs"],
         ["Inventors", "Lakshay S (26MAI0064); Arkkadu Bharath Reddy (26MAI0058); guide Dr. Yokesh Babu S, Associate Professor Grade 1 (whether the guide is a co-inventor depends on his contribution to the inventive concept and is for the IPR cell to decide)"],
         ["Guide / supervisor", "Dr. Yokesh Babu S, Associate Professor Grade 1"],
         ["Institution, department", "[to be filled]"],
         ["Funding / sponsor / third-party material", "[none known; third-party: Montage workflow software, DSS2 images, open-source Python libraries]"],
         ["Date of conception; dates of first reduction to practice", "[authors to confirm from the git history; the repository has 71 commits on branch revival/resource-state-aware]"],
         ["Any public disclosure so far?", "[none known to the assistant; the authors must confirm: talks, reports submitted to the course, public repositories, preprints]"],
         ["Intended publications", "see 07_Publication_and_IPR_Plan; none before a filing decision"]],
        [2.2, 4.1], size=9)
r.chapter("Technical field and background")
r.para("The invention relates to scheduling the tasks of a dependency graph on a heterogeneous computing system that includes at least two kinds of processor cores (for example performance and efficiency cores), "
       "optionally a graphics processing unit and optionally a remote worker reached over a network.")
r.para("**Background.** In eligibility-gated dispatch (the idea mapped from US 11,561,826 B1 {{p_xilinx}}), a ready task is handed to the first idle worker for which it is eligible, using no estimate of execution time. "
       "Where the cost of tasks differs in a way that the scheduler cannot see (for example, a task parameter that does not appear in the input size), such dispatch can start expensive tasks late or on slow workers. List "
       "schedulers such as HEFT and PEFT ({{heft,peft}}) order tasks using rank values from a given cost matrix. Learned schedulers ({{lachesis,tan25}}) train policies in simulation. IBM {{p_ibm1}} describes a learning "
       "agent that assigns a rank to tasks of a DAG on a heterogeneous system on a chip.")
r.para("**Problem.** To obtain an ordering that accounts for hidden task cost without (a) hard-coding which task parameters matter, (b) training a neural policy in simulation, or (c) relying on a person to sort the tasks, while keeping the scheduler's own decision cost low and measured.")
r.chapter("Summary of the implemented system")
r.para("The system comprises a coordinator, a set of worker processes pinned to processor cores (and optionally a GPU worker and a remote worker), a dependency graph of tasks with declared eligible worker types, and a scheduler "
       "policy with two hooks: ordering the ready tasks and selecting a worker.")
r.numbered([
    "**Model fitting.** From logs of earlier executions (each record: task stage, worker type, numeric task parameters, input size, measured kernel time, and the occupancy context), fit for each (stage, worker type) pair a regularised linear regression whose features are those numeric parameters that vary in the logs and their pairwise products. No stage name or parameter name appears in the code that selects features.",
    "**Guard.** If a stage or worker type was not present in the fitting data, the model raises an error instead of returning an estimate; a profile identifier recorded at fitting time is compared with the profile in use and a mismatch is refused.",
    "**Ranking.** For the ready tasks, compute the predicted upward rank: the predicted time of the task plus the longest path of predicted times (and predicted transfer times, where a remote worker is a candidate) to an exit task.",
    "**Dispatch.** Order the ready tasks by decreasing predicted rank. For each task in that order, consider only workers that are idle at that moment and for which the task is eligible; choose the one with the smallest predicted execution time (plus predicted transfer time); never place a task in the queue of a busy worker.",
    "**Accounting.** Record for each dispatch the elapsed decision time and, separately, the total time the coordinator spent in policy calls; flag the case in which an idle worker that no ready task can use prevents the dispatch loop from exiting early.",
    "**Refit.** For a new pool layout, rerun the fitting command on logs gathered under that layout.",
])
r.para("An optional pre-deployment gate replays recorded logs with an oracle estimator and enables predictive scheduling only if the achievable makespan reduction exceeds a configured threshold.")
r.chapter("Embodiments and evidence")
r.para("The embodiment was implemented in Python (about 12,600 lines runtime, 521 automated tests) and executed on an Intel Core i5-13500HX laptop with 6 performance cores, 8 efficiency cores and an NVIDIA RTX 3050 GPU, and, in "
       "emulation, with a remote worker behind a loopback socket. Measured results (real executions, paired makespan changes against B4):")
r.table("Measured results supporting the description",
        ["Workload", "Result", "Note"],
        [["64 image chains, 16 heavy (60x), 6P+7E, 12 unseen chain orders", "\u221219.32% [\u221220.0, \u221218.6]", "faster in 12 of 12 orders; exploratory"],
         ["same, 2P+7E, 8 unseen orders (model refitted by one command)", "\u221220.45% [\u221221.2, \u221219.8]", "faster in 8 of 8"],
         ["4 or 8 heavy chains of 64", "\u221227.65%; \u221226.76%", "gain largest with few heavy tasks"],
         ["40 heavy chains of 64", "\u22123.81% [\u22125.1, \u22121.9]", "gain shrinks"],
         ["cost ratio 7.5 / 20 / 60", "\u22121.3% / \u22122.9% / about \u221220%", "small below a ratio of about 20"],
         ["uniform batch (nothing hidden)", "+0.45%", "equivalent within 2%"],
         ["Montage mosaic", "no gain; B4 +47.9% vs static P-only", "no headroom"],
         ["informed hand rule vs proposed", "+0.66%, +0.27% (hand rule)", "level: the dispatcher does not beat a person who knows the parameter"],
         ["HEFT with the same model vs proposed", "+1.10% [\u22120.53, +2.81]", "level"],
         ["emulated remote worker, level 30", "EFT +3.78% slower with remote", "no offloading gain"],
         ["final benchmark, primary workload, CPU (24 blocks, Holm)", "PRED vs B4 \u221217.8% [\u221218.8, \u221216.7]; vs static HEFT \u22125.2% [\u22125.9, \u22124.6]", "confirmatory; end-to-end makespan"],
         ["final benchmark, strict GPU set", "PRED vs B4 \u221221.2% [\u221222.6, \u221219.7]; vs static HEFT \u221212.2% [\u221213.4, \u221211.1]", "GPU used only where a speed-up was measured"],
         ["final benchmark, PRED vs hand rule B4_param_first", "\u22120.4% [\u22120.9, +0.1] (CPU)", "within 1% in every configuration (exploratory)"]],
        [2.6, 1.9, 1.8], size=8.5)
r.chapter("Prior art located (not exhaustive)")
r.table("Documents to be considered by the examiner or professional",
        ["Document", "Relevance"],
        [["{{p_xilinx}}", "task graph, kernel queues, in-degree gating, thread adjustment; no prediction"],
         ["{{p_ibm1}}", "learning agent assigns rank to DAG tasks; rank-ordered dispatch on heterogeneous SoC"],
         ["{{p_ibm2}}", "learned DAG policy, task execution estimates, drop decisions"],
         ["{{p_intel}}", "CPU+GPU work-split by online profiling"],
         ["{{p_samsung}}", "task duration prediction for heterogeneous cores (lapsed)"],
         ["{{p_apple}}, {{p_google}}", "static graph-to-processor mapping; ML workload placement"],
         ["{{heft}}, {{peft}}", "list scheduling by upward rank and optimistic cost table"],
         ["{{starpu}}, {{lotaru}}", "history-based performance models; runtime prediction for workflows"],
         ["{{lachesis}}", "learned task selection with duplication-based placement"]],
        [1.4, 4.9], size=9)
r.para("The search was limited to Google Patents pages and the project's literature set; a professional search is required.")
r.chapter("Possible advantages (to be argued by the authors, not asserted)")
r.bullets([
    "No hard-coded stage or parameter knowledge; the model discovers varying parameters from logs.",
    "Low decision cost (15 ms of decision time per run of 257 tasks) and measured overhead.",
    "One-command refit for a new pool layout, demonstrated for two layouts.",
    "Reported gain where task cost varies (17% to 40% against blind dispatch; 2% to 12% against a static plan from the same model); no harm where it does not.",
    "Limits that a reviewer will note: equal to an informed hand rule; emulated remote; one machine; designed workload.",
])
r.chapter("Inventor contributions and signatures")
r.table("To be completed",
        ["Item", "Entry"],
        [["Conception of the dispatcher and model (who, when)", "[authors]"],
         ["Implementation and experiments (who, when)", "[authors]; assistant-generated code and analysis were used in the project: record the extent of AI assistance as the institution's policy requires"],
         ["Signatures and dates", "[authors, guide, witness as required]"]],
        [3.0, 3.3], size=9)
r.references()
o = OUT + r"\08_IPR_Invention_Disclosure_Draft"
r.save(o + ".docx")
print("08", export_pdf(o + ".docx", o + ".pdf"), len(r.cite_order))
