# Literature update (closure pass, 2026-10-11)

Scope: web research only, for the open items in [PROJECT_SPEC.md](PROJECT_SPEC.md) section 6-7 and [WORKLOAD_AND_DATA_PROVENANCE.md](WORKLOAD_AND_DATA_PROVENANCE.md) section 9. Nothing in the repository was changed except this file.

## 0. How to read the inspection levels

I used a fetch tool that returns a summarising model's answer to a prompt, not raw page text. That limits what "read" means here. Levels used below:

| Level | Meaning |
|---|---|
| FULL-DIRECT | The PDF was downloaded and I extracted the text myself (pypdf) and read the passages quoted or paraphrased. Highest fidelity. |
| FULL-VIA-FETCH | The page or XML was read through the fetch tool. Its answer is a model summary of the full page. Numbers and formulas should be re-checked against the source before they go into the thesis. Figures and images were not seen. |
| ABSTRACT | Abstract or landing-page metadata only (including OpenAlex and arXiv abstract pages). |
| SNIPPET | Only a web-search result summary. Treated as a pointer, not as evidence. |
| NOT REACHABLE | Page blocked, empty, errored, or image-only. |

Web-search summaries also contained the search tool's own background statements ("from my knowledge"). I did not use those as evidence. Anything that rests only on them is marked SNIPPET or UNVERIFIED.

## 1. US 11,561,826 B1 (Xilinx)

| Route | Result |
|---|---|
| patents.google.com/patent/US11561826B1/en | Reached. Page text is 148,335 characters. The claims are at the end. Read in two fetch passes (characters 0-100,000 and from 100,000). The fetch tool refused to give verbatim claim text and returned structured paraphrase only. |
| patentimages.storage.googleapis.com/US11561826B1.pdf | HTTP 403. NOT REACHABLE. |
| image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11561826 | Downloaded (1.5 MB), but the pages are scanned bitmap images (CCITT) with no text layer. No OCR tool is installed on this machine, so it could not be read. |
| patents.justia.com/patent/11561826 | HTTP 403. NOT REACHABLE. |

**Verbatim claim text: NOT obtained.** The paraphrase below is from the Google Patents page through the fetch tool. It matches the earlier paraphrase in PROJECT_SPEC section 7 on all points I could compare.

Title on the Google Patents page: "Scheduling processing of machine learning tasks on heterogeneous compute circuits". Inventors listed there: Sumit Nagpal, Abid Karumannil, Vishal Jain, Arun Kumar Patil (from a search summary, SNIPPET). Note that the title names machine-learning tasks as the workload. That is not the same as a claim to ML-based prediction. The description also uses ML platform language (for example Caffe and TensorFlow, seen in the fetched description text). CPC code G06F2209/509 carries the label "Offload". A CPC class is a classification label, not a claim.

Independent claims (paraphrase, not verbatim): claims 1 (method) and 14 (system). The other 18 of the 20 claims depend on claim 1 or 14.

Claim 1 elements, structured paraphrase:
1. Instantiate kernel objects from kernel definitions; each kernel object has a type that maps to a compute circuit in a heterogeneous set.
2. Generate a graph in memory: nodes are tasks, each node specifies an assignment to one or more kernel objects; edges are data dependencies.
3. Create task queues in memory and assign kernel objects to queues.
4. Threads enqueue and dequeue tasks according to the assignments, and thereby activate the matching compute circuits.

Claim 14: the same operations recast as a system with processor(s) and memory holding instructions.

Dependent claims (paraphrase): 2 blocking versus non-blocking kernels; 3 several graphs, one queue holding tasks from different graphs; 4 same-type kernels sharing a queue; 5 different-type kernels sharing a queue; 6 several threads on one kernel object; 7 configurable thread count; 8 performance measurement adjusts thread count; 9 per-graph output storage and addresses passed to the circuit; 10 in-degree counts so a task is enqueued only after all parents finish; 11 utilization above a threshold raises thread count; 12 a report function for statistics, debug data or metadata; 13 a second graph generated while the first is running; 15-20 system counterparts of 2-6 and 9.

Keyword check, run by the fetch tool on the claims section only (so it rests on the tool, not on my own reading of the raw text): none of "machine learning", "predict", "estimat", "offload", "model", "GPU", "CPU", "FPGA" appears in the claims. This agrees with PROJECT_SPEC section 7. It is still second-hand.

Status: claim paraphrase REACHED TWICE (consistent); verbatim text UNVERIFIED. What the owner must supply: the claims section copied as text from the Google Patents page, or a text-layer PDF of the patent. No freedom-to-operate opinion is implied.

## 2. HEFT/CPOP and PEFT originals

### 2.1 Reachability of the originals

| Paper | Result |
|---|---|
| Topcuoglu, Hariri, Wu, IEEE TPDS 13(3):260-274, 2002, DOI 10.1109/71.993206 | NOT REACHABLE. OpenAlex and Semantic Scholar list a green (submitted-version) copy at hdl.handle.net/11424/244213 (Marmara University repository). That server returned HTTP 500/503 on every attempt (Marmara pages, handle resolver, curl). A CiteSeerX-derived copy (meseec.ce.rit.edu .../l0260.pdf) refused the connection; web.archive.org is blocked for this tool. The IEEE version is closed. Only the abstract and bibliographic records were read. |
| Topcuoglu, Hariri, Wu, HCW 1999 (shorter version, DOI 10.1109/hcw.1999.765092) | NOT REACHABLE (records only). |
| Arabnejad and Barbosa, IEEE TPDS 25(3):682-694, 2014, DOI 10.1109/TPDS.2013.57 | NOT REACHABLE. OpenAlex and Semantic Scholar: closed. The Porto repository record (handle 10216/97674) is restricted and returned HTTP 503. ResearchGate returned 403. Abstract and metadata only (via search summaries and Crossref). |

### 2.2 Secondary sources read, and what they state

None of these is the original. Equation numbers below are those of the secondary paper, not of the originals.

**A. Dai and Zhang, Scientific World Journal 2014, DOI 10.1155/2014/465702 (PMC4165743). FULL-VIA-FETCH (PMC page and Europe PMC XML).**
- Upward rank: rank_u(t_i) = w̄_i + max over t_j in succ(t_i) of { c̄_ij + rank_u(t_j) }, Eq. (1); rank_u(t_exit) = w̄_exit, Eq. (2).
- EST(t_i, r_j) = max{ avail(t_i, r_j), max over t_m in pred(t_i) of { AFT(t_m) + c_mi } }, Eq. (4). EFT(t_i, r_j) = w_i,j + EST(t_i, r_j), Eq. (5). No insertion policy is defined there.
- PEFT OCT: OCT(t_i, r_j) = max over t_j in succ(t_i) of [ min over r_k of { OCT(t_j, r_k) + w_j,k + c_ij } ], Eq. (7). The edge cost here is written without an overline. No explicit exit-task base case in the formula; a table shows OCT = 0 for the exit task.
- Optimistic EFT: O_EFT(t_i, r_j) = EFT(t_i, r_j) + OCT(t_i, r_j), Eq. (10).
- rank_oct: not defined in this paper.
- Complexity stated: HEFT O(n^2 m); PEFT O(n^2 m) total (OCT part O(m(n^2+n))). The paper's own text for its new algorithm is internally inconsistent; ignore that part.

**B. Guo, Zhou, Gu, Micromachines 13(7):1067, 2022, DOI 10.3390/mi13071067 (PMC9323220). FULL-VIA-FETCH (Europe PMC XML; the PMC HTML page showed a bot check).** Cites its reference [3] for PEFT.
- OCT, Eq. (9): OCT(t_i, p_k) = max over t_j in succ(t_i) of [ min over p_w in P of { OCT(t_j, p_w) + w(t_j, p_w) + c̄_i,j } ]; OCT of the exit task is 0 on every processor.
- rank_oct, Eq. (10): the sum over the P processors of OCT, divided by P (the XML writes the task index as t_j; the context says t_i). So rank_oct is the average of the OCT row.
- Optimistic EFT, Eq. (11): O_EFT(t_i, p_j) = EFT(t_i, p_j) + OCT(t_i, p_j).
- EST, Eq. (4); EFT = EST + w_i,j, Eq. (5); average computation Eq. (1); average communication Eq. (2).
- HEFT upward rank: described in words only. Insertion: no formula.
- Complexity stated: HEFT O(v^2 p); PEFT O(v^2 p), the same as HEFT.

**C. Beaumont et al., "Scheduling on Two Types of Resources: a Survey", arXiv 1909.11365. FULL-DIRECT (pypdf), HEFT section 6.1.1.**
- HEFT in two steps: rank tasks, then select resources. Rank uses the average computation time over machines and the average communication time. The survey writes rank(j) = w_j + max over i in Gamma^-(j) of ( c_j,i + rank(i) ). I did not check the direction convention of Gamma^-.
- Tasks are sorted by decreasing rank, which gives a topological order. The first ready task is placed on the resource that completes it soonest (EFT), with an insertion-based strategy that considers all idle slots on all resources.
- Complexity O(n^2), from computing ranks plus the insertion step (in their setting, with communication assumed negligible). The survey also notes a non-constant approximation ratio and that StarPU's DMDA scheduler transposes HEFT's ordering to a dynamic setting.

**D. Wikipedia, "Heterogeneous earliest finish time". FULL-VIA-FETCH, encyclopedic.** Rank as average cost plus the max over successors of communication plus successor rank; insertion fills large-enough gaps; no complexity stated.

**E. MPEFT paper (Frontiers in Environmental Science 2022, DOI 10.3389/fenvs.2022.996483). FULL-VIA-FETCH, formula bodies missing from the extracted page.** Table lists O(v^2 p) for HEFT and PEFT. A fragment "if p_w != p_k" appears next to the OCT equation. This hints that the original PEFT formula may carry a same-processor condition on the communication term. Neither A nor B shows it. UNVERIFIED.

### 2.3 Summary for the baselines

- HEFT upward rank, insertion-based EFT and the stated O(v^2 p) or O(n^2) complexity are consistent across A, B, C. The original's own equation numbers and its own complexity statement (I have seen O(e x p) mentioned only in a search summary) are UNVERIFIED.
- PEFT: OCT recursion (A, B), rank_oct as the average of the OCT row (B only), O_EFT = EFT + OCT (A, B). The exact treatment of communication in the OCT term (average, and whether zero on the same processor) is not settled by the sources I read. The implementation in `src/caosched/schedulers/` should cite the original, which the owner must supply, before this is stated as "as in the paper".

## 3. Reachability of the other published versions

| Item | DOI | Result |
|---|---|---|
| LACHESIS, Luo et al., IEEE MDM 2022 | 10.1109/MDM55031.2022.00040 (IEEE Xplore document 9861109) | NOT REACHABLE. DOI redirects to IEEE Xplore, which returned an empty page. OpenAlex: closed, no repository copy of the IEEE version. Only the arXiv 2103.06980 preprint is open (already read). |
| Cao et al., IEEE IoT-J 2024 | 10.1109/JIOT.2024.3374969 | NOT REACHABLE as final version (OpenAlex: closed, one location, publisher only). Title there: "Dependent Task Offloading in Edge Computing Using GNN and Deep Reinforcement Learning". Not fetched from IEEE directly. arXiv 2303.17100 remains the only version read. |
| Liu et al., FGCS 2024 | 10.1016/j.future.2024.04.034 (Elsevier pii S0167739X24001638) | NOT REACHABLE. Elsevier redirect returned only "Redirecting". OpenAlex lists an SSRN accepted version (doi 10.2139/ssrn.4604459, open access flag true); SSRN returned HTTP 403. The arXiv 2309.10569 title is "Task Graph offloading via Deep Reinforcement Learning in Mobile Edge Computing" (abstract page read, ABSTRACT). |

## 4. Extended search

Queries are listed in section 7.

### 4a. WorkflowSim and simulation-based workflow-scheduling evaluation

| Source | Level | What it states (source-supported) | Meaning for us |
|---|---|---|---|
| Chen and Deelman, "WorkflowSim: A Toolkit for Simulating Scientific Workflows in Distributed Environments" (author-hosted PDF, scitech.group/files/publications/chen2012workflowsim.pdf, 8 pages; venue and year not printed in the extracted text, so I give none here) | FULL-DIRECT | Extends CloudSim with workflow-management layers. Argues ignoring layered overheads and failures gives significant runtime errors. Validated with real Pegasus traces of the 8-degree Montage workflow (10,422 tasks, 57 GB) on a 20-node FutureGrid site. Evaluates FCFS, MCT, MinMin, MaxMin (not HEFT) on Montage with half of the resources made twice as fast; finds relative scheduler ranking depends on the overhead type (clustering-delay estimation error can change relative performance). Names HEFT only as an example of algorithms that were evaluated by simulation. | Montage is a standard workload in this literature. Simulators model overhead; our real-run overhead accounting is therefore a comparison point. No GPU, no learned predictor in this paper. |
| Coleman et al., "WfCommons" (arXiv 2105.14352) | FULL-DIRECT | Table I lists WfInstances: 165 instances, 9 applications; Montage 17 instances, 37,619 tasks, all Pegasus on Chameleon. Realism tested by comparing simulated runs (WRENCH-based) with real executions. Synthetic Montage sizes used in the study include 180 to 9,807 tasks. | Source of Montage traces and recipe, simulation only. |
| Coleman et al., "WfBench" (arXiv 2210.03170) | FULL-DIRECT | Benchmarks generate CPU, memory and I/O work. Table III: real Montage versus benchmark makespans differ by at most about 14% for degrees 1.0 to 2.5, on 4 Haswell nodes with Pegasus/HTCondor. The conclusion lists GPU task support as planned future work. | Shows a Montage-shaped benchmark can be made; at the time of that paper GPU was not implemented. See 4d for the current code. |
| Rayej et al., WIDESim (arXiv 2206.03538) | ABSTRACT | Simulator for workflows on graph-topology distributed systems (IoT/edge). Abstract does not mention HEFT, GPU or Montage. | Peripheral. |
| Casanova et al., WRENCH (SC18 WORKS) | SNIPPET | Simulation framework on SimGrid; tested by simulating Pegasus. | Used by WfCommons for validation. Full text not read. |
| Ilyushkin and Epema, CCGrid 2018, "The impact of task runtime estimate accuracy on scheduling workloads of workflows" | ABSTRACT (reassembled from OpenAlex) | Simulation, homogeneous and heterogeneous systems; seven policies including a plan-based HEFT variant; at high utilization the workflow processing order matters more than accurate estimates; the plan-based HEFT variant adds complexity without much gain. Green open-access copy listed at TU Delft (resolver.tudelft.nl/uuid:bf5bf685-bf94-4619-9f83-b872b21d3659), not opened. | Directly relevant to "how much prediction accuracy matters". Simulation. Full text should be read. |

### 4b. Learned-HEFT / ML-predicted runtimes with HEFT

| Source | Level | What it states | Meaning for us |
|---|---|---|---|
| Bader, Lehmann, Thamsen, Leser, Kao, "Lotaru" (arXiv 2309.06918v1; page names Future Generation Computer Systems; extended from an SSDBM 2022 workshop paper) | FULL-VIA-FETCH (all but the last 7,343 characters, which were reference-list tail) | Per-task Bayesian linear regression on input size plus microbenchmark scaling to target nodes. Five nf-core bioinformatics workflows. Median prediction error: 6.93% homogeneous, 15.18% (Lotaru-A) and 17.33% (Lotaru-G) heterogeneous, versus about 30.7-30.9% for Online-P/M and 63.51% naive. HEFT is run only in simulation (WorkflowSim extension "WorkSim-PredError", 200 simulated 20-node clusters): mean makespan deviation from best 1.74% with accurate runtimes, 3.35% and 4.79% with Lotaru, 67.38% with Online-P. Lists GPUs as future work. | HEFT driven by predicted runtimes already exists in simulation. Undercuts novelty of "prediction-aware HEFT" in general. Supports our focus on real execution and CPU/GPU. |
| Bader et al., "Reshi" (arXiv 2208.07905v2; IEEE copyright and an IPCCC DOI prefix on the page, so likely IPCCC 2022, UNVERIFIED) | FULL-VIA-FETCH | Regression-tree node ranking from benchmark features; HEFT, MinMin, Round-Robin baselines; WorkflowSim fork with measured runtimes (27 AWS instance types) and injected normal or exponential prediction error. Abstract: mean makespan reduction versus HEFT of 7.18% and 18.01% at a mean 15% error. HEFT was better than one Reshi variant on one workflow. | Simulation, injected error. Same implication as Lotaru. |
| Bader et al., "Predicting the Performance of Scientific Workflow Tasks for Cluster Resource Management" (arXiv 2504.20867v1, book chapter) | FULL-VIA-FETCH | Compares 11 runtime-prediction methods and 11 memory-prediction methods (19 papers). Says plan-based schedulers (HEFT family named) are especially sensitive to prediction errors. Concludes that none of the runtime methods targets GPU execution. Most methods are evaluated by simulation, and integration into real systems is an open problem. Scheduling, energy and cost methods usually assume accurate predictions. Only 2 of 11 runtime methods are open source. | Strongest published support for the gap; it is a survey, so "not found" for the 19 papers it covers, not for the whole field. |
| Teodoro et al., arXiv 1505.03819 | carried over from PROJECT_SPEC (FULL, relevant section) | HEFT worse than FCFS above 50% injected error. | Unchanged. |
| Pham et al. (two-stage ML runtime prediction for workflow tasks, 2017); Nadeem et al. 2019; Monge et al. 2014; Chirkin et al. (stochastic runtimes into GA-HEFT) | SNIPPET only (titles and one-line descriptions via a search summary and a survey reference list) | Exist as runtime-prediction work, some linked to workflow scheduling. Details not verified. | Do not cite beyond title until full text is read. Owner should supply PDFs if they are to be used. |
| "Partition-Aware Scheduling for Mobile Heterogeneous Inference Co-Execution" (arXiv 2609.14213, Li, Paolieri, Golubchik) | ABSTRACT | Mobile CPU+GPU, static operator DAG, uses "latency predictors" in an online search. A search summary said HEFT is the schedule-only baseline; the abstract page I read does not say so. | HEFT baseline claim UNVERIFIED. Not a workflow system. |
| Agentic CPU-GPU scheduling (arXiv 2607.22242v1, Lu and Reda), see 4c | FULL-VIA-FETCH | HEFT baseline on real CPU/GPU hardware, no learned predictor. | See 4c. |

Negative result for (b): a study that trains a tabular model on CPU and GPU task runtimes and feeds the predictions as the cost matrix of HEFT/PEFT, and validates on real hardware with a real workflow, was not found in sources inspected.

### 4c. CPU/GPU heterogeneous workflow and DAG scheduling in real systems

| Source | Level | What it states | Meaning for us |
|---|---|---|---|
| Lu and Reda, "Agentic CPU-GPU Scheduling for Heterogeneous AI Workloads" (arXiv 2607.22242v1, Brown Univ.) | FULL-VIA-FETCH | Real hardware (RTX A5500 GPUs, EPYC 7713). 19 AI tools profiled; placement as immediate GPU, queued GPU or CPU under a VRAM budget; LLM plus runtime monitor. DAGs are small (four-tool diamond and fan-out). Beats a HEFT variant ("HEFT-CF", which reaches the oracle mapping in 2 of 10 scenarios), StarPU and all-GPU in 13 scenarios. No learned latency predictor: measured profiles and running averages. | Closest real-hardware CPU/GPU DAG paper found. Differs: tiny DAGs, AI tools, LLM, no learned predictor, not Montage. Preprint. |
| Wang et al., INSPIRIT (arXiv 2404.03226v1, Beihang) | FULL-VIA-FETCH | Priority scheduling on StarPU DMDAP; one node with Xeon, RTX 3090, V100; Cholesky, LU, Heat; speedups 1.03x-3.22x over DMDA. Uses offline per-task-type average times; no learned predictor. | Confirms DMDA-type scheduling with calibrated times is standard in StarPU. Preprint. |
| StarPU and HEFT-like `dmda` (Augonnet 2011) | carried over, FULL (preprint) | See PROJECT_SPEC. Beaumont survey (4a/2.2) confirms DMDA transposes HEFT ordering. | Unchanged. |
| John, Milthorpe, Hérault, Bosilca, "Multi-GPU work sharing in a task-based dataflow programming model", FGCS 2024, DOI 10.1016/j.future.2024.03.017 | ABSTRACT (OpenAlex) | PaRSEC maps tasks to GPUs from current load and does not rebalance afterwards; they study dynamic work sharing across GPUs in one node (BSpGEMM benchmark). Open access, not opened. | PaRSEC's GPU handling is load-based, not prediction-based (per this abstract only). |
| PaRSEC general design (ICL pages, OLCF slides) | SNIPPET | Fully distributed dynamic scheduler using NUMA and data-reuse features. | Pointer only. |
| Parsl HighThroughputExecutor docs (`available_accelerators`) | FULL-VIA-FETCH (official docs page) | One worker pinned per accelerator via CUDA_VISIBLE_DEVICES and equivalents; worker count capped by accelerator count; NVIDIA MPS oversubscription. No scheduling policy or prediction mentioned. | Resource pinning, not prediction. |
| Dask "Worker Resources" (distributed.dask.org) | FULL-VIA-FETCH | Resources are abstract labels; Dask does not know what a GPU is; throttling only; tasks request via `resources=`; no timing prediction. | As above. |
| Ray scheduling docs | FULL-VIA-FETCH | Resource requests are hard constraints; default strategy uses utilization and locality, no runtime prediction or cost model shown. | As above. |
| Pegasus Python API docs | FULL-VIA-FETCH (first 100,000 of 169,271 characters) | `request_gpus` (Condor profile) and a Pegasus `gpus` profile exist: resource requests only. A search summary mentions a kickstart GPU-monitoring extension (SNIPPET). | As above. |

Negative result for (c): in the runtimes above I found resource labels and pinning, not learned-runtime-driven placement. Legion was not inspected beyond a search summary that said it needs a performance model supplied by the user (SNIPPET, not used).

### 4d. WfCommons Montage recipe, WfBench GPU, WfInstances Montage

| Item | Level | Finding |
|---|---|---|
| Montage recipe | FULL-VIA-FETCH (GitHub directory listing and docs index) | `wfcommons/wfchef/recipes/montage` exists. Class `wfcommons.wfchef.recipes.montage.recipe.MontageRecipe` (documentation search summary, SNIPPET). The listing page said it might be incomplete. Release notes list Montage among recipes since v0.5. |
| WfBench GPU | FULL-VIA-FETCH | The 2022 WfBench paper lists GPU as future work (FULL-DIRECT). Current docs and `wfcommons/wfbench/bench.py` have a `gpu_work` parameter (per task or per task type); generated arguments include `--gpu-work`. Release v1.5 (PyPI date 2026-07-27) added AMD GPU support through HIP and detects NVIDIA/AMD GPUs with `nvidia-smi`/`amd-smi`; GPU kernels are built with CMake from `bin/cuda/` or `bin/hip/`. I did not read the kernel source or `wfbench` script (the raw path I guessed returned 404). So: GPU support in WfBench is present in current code; what its kernels do is UNVERIFIED. |
| WfCommons on Windows | mixed | README (fetched) says requires Python 3.11+ and "tested on Linux and macOS". PyPI classifier: OS Independent, Python 3.11 to 3.14. Release v1.4 and PR #127 (merged 2026-01-28) say "Windows support", but the PR text covers installation without make/g++ only (tested on Windows 11, Python 3.14.2). Whether WfBench tasks (which use stress-ng per the docs) run on Windows is UNVERIFIED. |
| WfInstances Montage traces | FULL-VIA-FETCH (GitHub README of `pegasus/montage`) | 17 instances (WfFormat 1.6), run on Chameleon, surveys 2MASS (degrees 0.05 to 20) and DSS (0.5 to 20); 8 task types (mProject, mDiffFit, mConcatFit, mBgModel, mBackground, mImgtbl, mAdd, mViewer). Task counts range from 58 to 9,805 (2MASS) and 58 to 6,448 (DSS) per the README table. Two rows (2MASS 0.2 and 0.25 degrees) show the same task count (619) with very different makespans; this looks odd and may be a fetch or README issue. UNVERIFIED. The archived `pegasus-instances` repo says 17 Montage instances and points to WfInstances. |
| WfFormat per-task content | ABSTRACT-level | Page says instances capture per-task runtime, CPU, memory, I/O and machine info. Not checked for Montage files specifically. |

### 4e. Montage on GPUs (negative search)

Result: no GPU-accelerated Montage found in sources inspected. Details:
- Montage GitHub README (Caltech-IPAC/Montage; FULL-VIA-FETCH): no mention of GPU, CUDA or OpenCL. It describes Windows support through Cygwin and cross-compiled native executables, and a Montage 7.0 section. The version labelling in the README is inconsistent (says 6.0 is tag v6.1); not resolved.
- Montage's own performance literature (IJCSE paper, SPIE, grid papers; SNIPPET) describes a CPU algorithmic speedup of about 30 times for tangent-plane reprojection (mProjectPP) and parallelism through MPI or grid jobs. No GPU port was found in their summaries.
- Separate tool, not Montage: "dfreproject" (arXiv 2505.03932v2, Rhea et al.; FULL-VIA-FETCH). PyTorch GPU reprojection with gnomonic projection and SIP distortion; headline "up to 20X" on GPU and 10X on CPU versus the `reproject` package; measured on one RTX 4060 laptop GPU and a Core i9-14900HX; the numeric results are in figures I could not read; Montage's mProject is not benchmarked. This is the closest GPU reprojection work found; it is not a Montage port and has no scheduling aspect.
- Berriman et al., "Astronomical Image Processing at Scale With Pegasus and Montage" (arXiv 2111.11624; ABSTRACT): no GPU.
- Pegasus/Montage/GPU scheduling search: the only GPU hit named "Pegasus" was an unrelated 2011 USENIX ATC hypervisor GPU-sharing paper (SNIPPET).

Implication (a statement of absence, not a claim of non-existence): a GPU mProject/mDiffFit/mBackground is not available from the Montage project as far as inspected. Any CPU/GPU Montage experiment would need our own CUDA stages (`src/caosched/apps/cuda_stages.py` exists in the repository) and should say so.

## 5. Gap statement update

### 5.1 Restated gap (wording kept at "not found in sources inspected")

Not found in sources inspected: a controlled study of how the level of runtime-prediction sophistication changes DAG scheduling outcomes on a real Montage execution across heterogeneous CPU resources (and a CUDA worker), with prediction, scheduling and transfer overheads all counted, using the published rank-based and predicted-EFT baselines (HEFT, PEFT).

Levels behind that statement: the survey chapter arXiv 2504.20867 (FULL-VIA-FETCH, covers 19 papers) reports no GPU-targeted runtime-prediction method and mostly simulation-based evaluation; Lotaru and Reshi (FULL-VIA-FETCH) are simulation-only for scheduling; Ilyushkin and Epema (ABSTRACT) is simulation; WorkflowSim, WfCommons and WfBench (FULL-DIRECT) are simulation or CPU benchmarks without GPU in the papers; the real-hardware CPU/GPU DAG paper found (2607.22242, FULL-VIA-FETCH) has no learned predictor and different workloads. The search is a bounded web search and several key papers remain unread (section 6). This is not proof that the gap exists.

### 5.2 Exact search queries and tools

Search tool: the session web search (US), standard or extended mode, 2026-10-11. Queries are in section 7.

### 5.3 What changed versus PROJECT_SPEC section 6

Undercuts or narrows the gap:
1. Lotaru (arXiv 2309.06918) and Reshi (arXiv 2208.07905): HEFT driven by predicted runtimes, and injected prediction error, are already evaluated in WorkflowSim-based simulation on nf-core workflows (CPU clusters). So "HEFT with predicted runtimes" is not new; novelty must rest on real execution, a prediction ladder, CPU/GPU and overhead accounting.
2. Ilyushkin and Epema (CCGrid 2018, ABSTRACT): estimate accuracy versus scheduling policy, including a HEFT-derived plan-based policy, in simulation; finds order of workflow processing matters more than accuracy at high utilization. A result we should test, not assume.
3. Lu and Reda (arXiv 2607.22242): a 2026 preprint with real CPU/GPU hardware, DAG workloads and a HEFT baseline. It narrows the claim that real-hardware CPU/GPU DAG scheduling with a HEFT baseline has not been done. It does not use a learned runtime predictor and its DAGs have four tasks.

Supports the gap:
4. Survey chapter arXiv 2504.20867: no runtime-prediction method targets GPUs; evaluation mostly in simulation; schedulers usually assume accurate predictions; low code availability.
5. Parsl, Dask, Ray, Pegasus: GPU handling is resource labels and pinning, no runtime prediction in the pages read.
6. No GPU-accelerated Montage found (4e); dfreproject is a separate GPU reprojection library.
7. WfBench GPU: absent in the 2022 paper (future work), present in current code (gpu_work, CUDA/HIP kernel directories). So the old note "WfBench GPU support unverified" is now: present in code, content unread.

Other changes to the evidence base:
8. WorkflowSim uses Montage with real Pegasus traces and layered overhead modelling; its scheduler study uses FCFS/MCT/MinMin/MaxMin, not HEFT.
9. The patent title names machine-learning tasks; claims paraphrase still has none of the keywords. The statement in section 7 stands, with the title caveat added.

## 6. Items still UNVERIFIED, and what the owner must provide

| # | Item | State after this pass | Access needed from owner |
|---|---|---|---|
| 1 | Verbatim claims of US 11,561,826 B1 | Paraphrase only, consistent across two reads; USPTO PDF image-only, Google PDF 403 | Claims text copied from the Google Patents page, or a text-layer PDF (or OCR output) of the grant |
| 2 | HEFT/CPOP original (TPDS 13(3), 2002): rank definition, EFT/insertion text, complexity statement, equation numbers | Not read; only secondary restatements (section 2.2) | PDF via IEEE Xplore or institution; or retry the Marmara green copy hdl.handle.net/11424/244213 when the server is up |
| 3 | PEFT original (TPDS 25(3), 2014): exact OCT (communication term), rank_oct, O_EFT, complexity, equation numbers | Not read; formulas from two open secondary papers; rank_oct from one only | PDF via IEEE Xplore (DOI 10.1109/TPDS.2013.57) or institution |
| 4 | LACHESIS IEEE MDM 2022 camera-ready | IEEE page empty; preprint only | PDF via IEEE Xplore document 9861109 |
| 5 | Cao 2024 IEEE IoT-J final | Not reachable; arXiv only | PDF via IEEE Xplore, DOI 10.1109/JIOT.2024.3374969 |
| 6 | Liu 2024 FGCS final | Not reachable; SSRN accepted version 403; arXiv only | Elsevier PDF (DOI 10.1016/j.future.2024.04.034) or SSRN 4604459 PDF |
| 7 | Song 2023 (Comput Electr Eng), Wang 2022 (IEEE TC) and other paywalled items from PROJECT_SPEC section 6 | Not retried in this pass | PDFs if they are to be used beyond the abstract |
| 8 | Ilyushkin and Epema CCGrid 2018 full text | Abstract only; green copy URL known (TU Delft resolver) but not opened | Open the TU Delft copy or supply the PDF |
| 9 | Pham 2017, Nadeem 2019, Monge 2014, Chirkin (GA-HEFT) | Snippet only | PDFs |
| 10 | Arabnejad claim of a same-processor condition in the OCT communication term | Hint only (fragment in the MPEFT paper) | Resolved by item 3 |
| 11 | Original HEFT complexity as stated by authors (O(e x p) was mentioned only in a search summary) | UNVERIFIED | Resolved by item 2 |
| 12 | WfBench GPU kernels (`bin/cuda`, `wfbench` script): what they compute, CUDA version needs, Windows behaviour; WfBench on Windows in general | Parameter names and release notes read; code not read | Either a read of the repository files by a later pass, or a local test by the owner |
| 13 | WfInstances Montage README table (the two rows with equal task counts) and per-instance file content (runtimes, files, machines) | Table read through fetch only | Download one Montage JSON (for example `montage-chameleon-2mass-05d-001.json`) and the README; confirm counts |
| 14 | WorkflowSim venue and year | Not printed in extracted PDF text | Owner or a later pass to confirm from the publisher record |
| 15 | dfreproject speedup numbers | Abstract/summary claims only; figures not readable | PDF figures if cited |
| 16 | "Partition-Aware Scheduling..." HEFT baseline claim | Abstract page does not state it | Full paper (arxiv.org/html/2609.14213v1) if cited |
| 17 | Reshi venue (IPCCC 2022 is inferred from a DOI prefix) | Inferred | Confirm from the publisher record |
| 18 | Legion, PaRSEC scheduling internals | Snippet and one abstract | Paper PDFs if cited |
| 19 | Montage input data volumes, Pegasus version requirements (already open in WORKLOAD_AND_DATA_PROVENANCE.md section 9) | Not addressed here | Unchanged; need local measurement or Pegasus docs for the chosen version |
| 20 | Arabnejad claim that PEFT complexity equals HEFT (O(v^2 p)) | Stated by two secondary papers and in a PEFT abstract snippet | Resolved by item 3 |

## 7. Search queries used

1. US11561826B1 Xilinx scalable multi-threaded kernel task graph claims
2. Topcuoglu Hariri Wu "Performance-effective and low-complexity task scheduling for heterogeneous computing" pdf
3. Arabnejad Barbosa "List Scheduling Algorithm for Heterogeneous Systems by an Optimistic Cost Table" pdf
4. PEFT "optimistic cost table" OCT rank_oct "optimistic EFT" O_EFT formula HEFT upward rank insertion-based policy arXiv
5. HEFT upward rank "rank_u" earliest finish time insertion-based policy O(e×p) complexity heterogeneous scheduling pdf lecture
6. "critical-path-on-a-processor" "heterogeneous earliest-finish-time" Topcuoglu pdf upward rank downward rank
7. arXiv PEFT Predict Earliest Finish Time "OCT" "rank_oct" definition optimistic cost table "O_EFT" HEFT comparison workflow scheduling
8. "A Synthesized Heuristic Task Scheduling Algorithm" Dai Scientific World Journal 2014 PMC
9. "Task scheduling algorithms for heterogeneous processors" Topcuoglu Hariri Wu HCW 1999 pdf upward rank "insertion-based"
10. PEFT algorithm "rank_oct" "average" "OCT" "O_EFT" restated open access mdpi OR frontiersin OR plos OR hindawi OR arxiv scheduling
11. LACHESIS Luo "Scheduling DAG" graph neural network DEFT IEEE MDM 2022 ieeexplore
12. Cao "DAG-based task scheduling" offloading graph attention PPO IEEE Internet of Things Journal 2024 doi
13. Liu SATA-DRL "Future Generation Computer Systems" 2024 deep reinforcement learning workflow scheduling edge Montage sciencedirect
14. WorkflowSim: a toolkit for simulating scientific workflows in distributed environments Chen Deelman 2012
15. WorkflowSim Montage CyberShake Epigenomics HEFT simulation overhead clustering failure workflow scheduling evaluation
16. HEFT with machine learning predicted task execution times workflow scheduling runtime prediction random forest gradient boosting
17. impact of runtime prediction error on workflow scheduling HEFT inaccurate task runtime estimates scientific workflows
18. "HEFT" "predicted" execution time neural network OR "XGBoost" OR "LightGBM" OR "random forest" heterogeneous CPU GPU DAG scheduling real system evaluation
19. learning-based performance models task runtime prediction HEFT dmda StarPU OR PaRSEC OR Legion OR Parsl OR Dask GPU heterogeneous task graph scheduler
20. Pegasus WMS GPU request_gpus profile HTCondor GPU jobs workflow documentation
21. Parsl GPU "available_accelerators" HighThroughputExecutor assign tasks to GPUs documentation
22. PaRSEC GPU scheduling heterogeneous task runtime dataflow DAG device selection "PaRSEC" accelerators paper
23. scientific workflow management system GPU-aware scheduling heterogeneous CPU GPU nodes task placement runtime estimates evaluation
24. Dask-CUDA OR "Dask" GPU scheduler worker resources tasks "resources=" GPU documentation distributed scheduling policy
25. WfCommons WfBench GPU benchmark tasks workflow benchmark generator GPU support
26. WfCommons Montage recipe wfcommons.wfchef.recipes MontageRecipe
27. wfcommons wfbench "gpu-work" gpu_benchmark CUDA release notes GPU support added
28. Montage workflow GPU accelerated image reprojection mProject CUDA
29. GPU-accelerated Montage astronomical image mosaic engine FPGA OR GPU reprojection mAdd mDiffFit performance
30. "Montage" astronomical mosaic "CUDA" OR "OpenCL" OR "GPU" image reprojection coadd implementation speedup
31. Montage workflow heterogeneous CPU GPU scheduling Pegasus accelerator mProject GPU cluster workflow
32. WRENCH: A Framework for Simulating Workflow Management Systems Casanova SimGrid arXiv abstract

Direct fetches (not searches): Google Patents, Justia, patentimages, USPTO PDF; OpenAlex and Semantic Scholar and Crossref metadata for DOIs 10.1109/71.993206, 10.1109/TPDS.2013.57, 10.1109/JIOT.2024.3374969, 10.1109/MDM55031.2022.00040, 10.1016/j.future.2024.04.034, 10.1109/CCGRID.2018.00048, 10.1016/j.future.2024.03.017; arXiv pages 2103.06980 (not reopened), 2309.06918, 2208.07905, 2504.20867, 2607.22242, 2404.03226, 2609.14213, 2508.09503, 2511.19832, 2505.03932, 2105.14352, 2210.03170, 2206.03538, 2111.11624, 1909.11365; GitHub wfcommons/wfcommons (README, releases v1.4, v1.5, PR 127, recipes directory, bin, wfbench directory, bench.py), wfcommons/WfInstances, wfcommons/pegasus-instances, Caltech-IPAC/Montage; docs.wfcommons.org; PyPI wfcommons; Parsl, Dask, Ray, Pegasus API documentation pages; Wikipedia HEFT; PMC4165743, Europe PMC XML for PMC9323220 and PMC4165743.

## 8. Ten-line summary

1. Patent: Google Patents text reached; verbatim claims NOT obtained (fetch tool paraphrases only, USPTO PDF is image-only, Google PDF 403). Independent claims are 1 (method) and 14 (system). Keyword check (claims only, via the fetch tool): no ML, prediction, offloading, model, CPU, GPU or FPGA. The patent title does name machine-learning tasks as the workload.
2. HEFT/CPOP and PEFT originals: NOT reachable (IEEE closed; the Marmara green copy of HEFT errored). Formulas for rank_u, EST/EFT, OCT, rank_oct, O_EFT and complexity are given from open secondary papers (Dai and Zhang 2014; Guo et al. 2022; Beaumont et al. survey), with their own equation numbers.
3. LACHESIS IEEE, Cao IoT-J and Liu FGCS final versions: all NOT reachable; DOIs recorded; arXiv versions remain the only ones read.
4. WorkflowSim, WfCommons and WfBench were read in full from PDFs; WorkflowSim uses Montage but evaluates FCFS/MCT/MinMin/MaxMin.
5. HEFT with predicted runtimes already exists in simulation (Lotaru, Reshi); Ilyushkin and Epema study estimate accuracy in simulation (abstract only).
6. The survey arXiv 2504.20867 says no runtime-prediction method it covers targets GPUs and that most are evaluated in simulation.
7. New near neighbour: arXiv 2607.22242 (real CPU/GPU hardware, DAGs of four tools, HEFT baseline, no learned predictor).
8. Parsl, Dask, Ray and Pegasus: GPU handling is resource labels and pinning; no runtime prediction in pages read. WfBench GPU is future work in the paper but `gpu_work` exists in current code (v1.5, kernels unread).
9. WfCommons has a Montage recipe; WfInstances has 17 Montage traces; Windows execution of WfBench is unverified.
10. No GPU-accelerated Montage found (only the separate dfreproject library); gap stays worded as not found in sources inspected, and section 6 lists 20 items with the access the owner must supply.
