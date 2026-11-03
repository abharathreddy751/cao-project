# Related work and novelty (checked 2026-10-25; no novelty is claimed)

Verified against the primary page (title, authors, venue) in this session:

| Reference | What it is | Checked |
|---|---|---|
| Bader, Lehmann, Thamsen, Leser, Kao, "Lotaru: Locally Predicting Workflow Task Runtimes for Resource Management on Heterogeneous Infrastructures", arXiv 2309.06918 (published in Future Generation Computer Systems, 2024) | Predicts workflow task runtimes on heterogeneous clusters from microbenchmarks and small local runs; its predictions give scheduling results close to perfect runtime knowledge | arXiv abstract page read |
| Carvalho, Simitsis, Queralt, Romero, "Workload Placement on Heterogeneous CPU-GPU Systems", PVLDB 17(12), 2024, doi 10.14778/3685800.3685845 | A short tutorial that surveys placement strategies and runtime-prediction techniques for CPU-GPU systems; no new experiments | search result with venue and abstract; PDF not read |
| Ilyushkin, Epema, "The Impact of Task Runtime Estimate Accuracy on Scheduling Workloads of Workflows", CCGrid 2018, pp. 331-341, doi 10.1109/CCGRID.2018.00048 | Evaluates how missing or inaccurate task runtime estimates change slowdown in workflow scheduling | existence, venue and abstract confirmed; conclusions NOT read, so the project's earlier paraphrase of this paper ("order matters more than estimate accuracy at high utilisation") is unverified |
| Lu, Reda, "Agentic CPU-GPU Scheduling for Heterogeneous AI Workloads", arXiv 2607.22242 (submitted 24 July 2026) | Pairs an LLM agent with an algorithmic runtime monitor to choose between immediate GPU, queued GPU and CPU offload under a VRAM budget; reported to match brute-force optimal mapping in 13 scenarios and to beat HEFT, StarPU and all-GPU | arXiv abstract page read |
| "A Survey of Machine Learning-Driven Task Scheduling Approaches for Multiprocessor Systems", doi 10.1016/j.sysarc.2025.103628 | Survey | **not verified in this session** |

## Closest work and the difference

* Lu and Reda: the closest in spirit (resource-state aware device choice with a runtime monitor, evaluated against HEFT and an all-GPU policy). They decide between GPU, queued GPU and CPU
  under a VRAM budget with an LLM agent; this project's candidate is a deterministic, microsecond-scale cost model with a work-conserving rank order and a B4 fallback, evaluated
  first against an oracle that obeys the same constraints. They do not (in the abstract) address a oracle-headroom gate, work conservation, or a no-harm control.
* Lotaru: runtime prediction for heterogeneous nodes, used by existing schedulers; this project's model is much simpler (a few coefficients per stage and pool) and is retrained from
  its own logs by one command; Lotaru is the better reference for prediction quality.
* Ilyushkin and Epema: the relevant question (how much do estimates matter for workflow slowdown); the project's own finding that order matters more than a placement choice at high utilisation
  agrees with the direction of their title but their conclusions were not read.

## What can honestly be said

The contribution tested here (low-overhead resource-state-aware cost estimation + work-conserving rank dispatch + end-to-end cost terms, judged by an oracle gate first) did not show an
advantage on the workload designed for it: the oracle gate failed. What is specific and verified is the negative result and the method of establishing it. No claim of novelty is made until a
systematic search (beyond the five starting references) is done.
