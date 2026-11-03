# Sources, verbatim extracts and checks (2026-10-13)

Companion to [LITERATURE_UPDATE.md](LITERATURE_UPDATE.md). Web research only; no repository code was changed. Every entry states URL, access date, inspected level and exactly what was copied.

Levels used here:

| Level | Meaning |
|---|---|
| FULL-DIRECT | Full text read by me from the source itself, exact text copied. |
| RENDERED-DOM | Text taken from the page as the built-in browser delivered it (rendered DOM or the page's own served HTML parsed in the browser), not through a summarising model. |
| ABSTRACT | Abstract or landing page only. |
| NOT REACHABLE | Blocked, empty or error. |

## 1. US 11,561,826 B1 claims (Xilinx)

- URL: https://patents.google.com/patent/US11561826B1/en
- Accessed: 2026-10-13, built-in browser (mcp__Claude_Browser), page title "US11561826B1 - Scheduling processing of machine learning tasks on heterogeneous compute circuits - Google Patents".
- Level: RENDERED-DOM, with one caveat on method. The Polymer front end did not render a body in the pane (document.body.innerText was empty; get_page_text returned only the title). I therefore fetched the same URL from inside the page (same origin, HTTP 200, 412,013 characters), parsed the returned HTML with the browser's DOMParser, and read `section[itemprop=claims]`. So the text below is the markup Google serves for that URL, read by the browser, not a summary by a model. Heading in that section: "Claims (20)" / "What is claimed is:". 20 top-level claim elements found (ids CLM-00002 ... CLM-00020; claims 1 and 14 have no id attribute).
- What was copied: all 20 claims, one block per claim, as the text content of each claim element with blank lines removed and each line trimmed. Line breaks inside a claim are the page's own sub-element breaks. Typographical errors in the source are kept as they are (claim 6 "based assignment"; claim 13 "the the enqueing", "tasks the tasks"). Claim text was transcribed from the tool output into this file by hand-copy; the keyword counts in 1.3 were computed in the browser on the original strings, not on this file.
- Bibliographic data on the same page (from `meta` tags and the page's timeline): title as above; inventors Sumit Nagpal, Abid Karumannil, Vishal Jain, Arun Kumar Patil; assignee Xilinx Inc; application filed 2020-11-12 (US17/096,136); granted/published 2023-01-24; page shows "Status Active" and "2041-07-07 Adjusted expiration" (catalogue data, not a legal opinion). Page abstract begins "Scheduling work of a machine learning application includes instantiating kernel objects...".

### 1.1 Claims, as served by Google Patents (data block)

```
1. A method comprising:
instantiating a plurality of kernel objects by a computer processor in response to input of a plurality of kernel definitions, respectively, wherein each kernel object is of a kernel type of a plurality of kernel types, and each kernel type indicates a compute circuit of a heterogeneous plurality of compute circuits;
generating a graph in a memory by the computer processor, wherein the graph has nodes and edges, each node represents a task and specifies an assignment of the task to one or more of the kernel objects, and each edge represents a data dependency between the nodes;
creating a plurality of task queues in the memory, and assigning each task queue to queue tasks represented by one or more of the nodes;
assigning each of the kernel objects to one of the task queues;
enqueuing the tasks represented by the nodes in the plurality of task queues by threads executing the kernel objects on the computer processor, based on assignments of the kernel objects to the task queues and assignments of the tasks to the kernel objects; and
dequeuing the tasks from the plurality of task queues by the threads executing the kernel objects based on the assignments of the kernel objects to the task queues and the assignments of the tasks to the kernel objects, and activating ones of the compute circuits by the threads executing the kernel objects to initiate processing of the dequeued tasks.

2. The method of claim 1, further comprising:
waiting, in response to definition of a kernel object of the plurality of kernel objects being blocking, to dequeue another task from a task queue of the plurality of task queues by the thread executing the kernel object, until processing of a previous task dequeued by the thread executing the kernel object is complete; and
continuing to the dequeuing, in response to definition of a kernel object of the plurality of kernel objects being non-blocking, of another task from a task queue of the plurality of task queues by the thread executing the kernel object without waiting for processing of the previous task dequeued by the thread executing the kernel object to complete.

3. The method of claim 1, further comprising:
generating a plurality of graphs in the memory, wherein the tasks represented by each graph are independent of data processed by the tasks represented by each other graph, and each graph has nodes and edges, each node represents a task and specifies an assignment of the task to one or more of the kernel objects, and each edge represents a data dependency between the nodes; and
wherein the enqueuing includes enqueuing in at least one task queue of the plurality of task queues, a first task represented by a node in a first graph of the plurality of graphs and a second task represented by a node in a second graph of the plurality of graphs.

4. The method of claim 1, wherein:
the respective kernel types include a first kernel type, and the plurality of kernel objects includes a first kernel object and a second kernel object of the first kernel type;
the dequeuing includes:
dequeuing a first task from a first task queue of the plurality of task queues by a thread executing the first kernel object, and activating a first compute circuit of the plurality of compute circuits indicated by the first kernel type to initiate processing of the first task; and
dequeuing a second task from the first task queue by a thread executing the second kernel object, and activating the first compute circuit to initiate processing of the second task.

5. The method of claim 1, wherein:
the respective kernel types include a first kernel type and a second kernel type, and the plurality of kernel objects includes a first kernel object of the first kernel type and a second kernel object of the second kernel type;
the dequeuing includes:
dequeuing a first task from a first task queue of the plurality of task queues by a thread executing the first kernel object, and activating a first compute circuit of the plurality of compute circuits indicated by the first kernel type to initiate processing of the first task; and
dequeuing a second task from the first task queue by a thread executing the second kernel object, and activating a second compute circuit indicated by the second kernel type to initiate processing of the second task.

6. The method of claim 1, wherein:
the instantiating the plurality of kernel objects includes executing at least one of the kernel objects by two or more threads; and
the dequeuing includes dequeuing, based assignment of at least one of the kernel objects to one of the task queues, tasks from the one of the task queues by the two or more threads, and activating the compute circuit indicated by the kernel type of the at least one of the kernel objects by the two or more threads to initiate processing of the dequeued tasks.

7. The method of claim 6, wherein the instantiating the plurality of kernel objects includes selecting a number of threads to execute by the at least one kernel object in response to a configurable parameter associated with the at least one kernel object.

8. The method of claim 7, further comprising:
measuring performance of the plurality of compute circuits by the kernel objects; and
adjusting the configurable parameter to adjust the number of threads to execute in response to the performance measured for the compute circuit associated with the at least one kernel object.

9. The method of claim 1, further comprising:
generating a plurality of graphs in the memory, wherein the tasks represented by each graph are independent of data processed by the tasks represented by each other graph, each graph includes respective storage areas for output data generated by the nodes of the graph, each graph has nodes and edges, each node represents a task and specifies an assignment of the task to one or more of the kernel objects, and each edge represents a data dependency between the nodes;
wherein the activating of a compute circuit of the ones of the compute circuits to initiate processing of a dequeued task includes:
communicating one or more memory addresses of one or more of the respective storage areas to the compute circuit, wherein each of the one or more of the respective storage areas has output data produced in processing a task represented by a parent node of the node of the dequeued task, and the dequeued task is dependent on the output data; and
communicating to the compute circuit, a memory address of the respective storage area for output data generated in processing of the dequeued task.

10. The method of claim 9, wherein:
each graph includes storage for respective in-degree counts of the nodes of the graph, and each in-degree count indicates a number of parent nodes of a node of the graph on which the task represented by the node is dependent on output data;
decrementing an in-degree count of a node of a graph by thread executing a kernel object in response to completion of a task represented by a parent node of the node; and
wherein the enqueuing includes enqueuing the task represented by the node of the graph in response to the in-degree count indicating completion of each task of each parent node of the node.

11. The method of claim 1, wherein:
the instantiating the plurality of kernel objects includes executing each of the kernel objects by one or more threads;
determining respective utilization levels of the kernel objects; and
automatically increasing a number of threads executing a kernel object in response to the respective utilization level of the kernel object being greater than a threshold.

12. The method of claim 1, further comprising executing a report function of a system manager on-demand during processing of the graph, wherein the system manager calls a report function of each kernel object, and the report function outputs one or more of kernel statistics, kernel debug data, or kernel metadata at time of the call.

13. The method of claim 1, further comprising:
concurrent with the the enqueing and the dequeuing of tasks, generating another graph in the memory by the computer processor, wherein the other graph has nodes and edges, wherein each node represents a task and specifies an assignment of the task to one or more of the kernel objects, and each edge represents a data dependency between the nodes; and
performing the enqueuing and dequeuing of tasks the tasks represented by the nodes of the other graph.

14. A system comprising:
one or more processors;
a memory arrangement configured with instructions that when executed by the one or more processors cause the one or more processors to perform operations including:
instantiating a plurality of kernel objects in response to input of a plurality of kernel definitions, respectively, wherein each kernel object is of a kernel type of a plurality of kernel types, and each kernel type indicates a compute circuit of a heterogeneous plurality of compute circuits;
generating a graph in the memory arrangement, wherein the graph has nodes and edges, each node represents a task and specifies an assignment of the task to one or more of the kernel objects, and each edge represents a data dependency between the nodes;
creating a plurality of task queues in the memory arrangement, and assigning each task queue to queue tasks represented by one or more of the nodes;
assigning each of the kernel objects to one of the task queues;
enqueuing the tasks represented by the nodes in the plurality of task queues by threads executing the kernel objects, based on assignments of the kernel objects to the task queues and assignments of the tasks to the kernel objects; and
dequeuing the tasks from the plurality of task queues by the threads executing the kernel objects based on the assignments of the kernel objects to the task queues and the assignments of the tasks to the kernel objects, and activating ones of the compute circuits by the threads executing the kernel objects to initiate processing of the dequeued tasks.

15. The system of claim 14, wherein the memory arrangement is further configured with instructions that when executed cause the one or more processors to:
wait, in response to definition of a kernel object of the plurality of kernel objects being blocking, to dequeue another task from a task queue of the plurality of task queues by the thread executing the kernel object, until processing of a previous task dequeued by the thread executing the kernel object is complete; and
continue to the dequeuing, in response to definition of a kernel object of the plurality of kernel objects being non-blocking, of another task from a task queue of the plurality of task queues by the thread executing the kernel object without waiting for processing of the previous task dequeued by the thread executing the kernel object to complete.

16. The system of claim 14, wherein the memory arrangement is further configured with instructions that when executed cause the one or more processors to:
generate a plurality of graphs in the memory arrangement, wherein the tasks represented by each graph are independent of data processed by the tasks represented by each other graph, and each graph has nodes and edges, each node represents a task and specifies an assignment of the task to one or more of the kernel objects, and each edge represents a data dependency between the nodes; and
wherein the instructions for enqueuing include instructions for enqueuing in at least one task queue of the plurality of task queues, a first task represented by a node in a first graph of the plurality of graphs and a second task represented by a node in a second graph of the plurality of graphs.

17. The system of claim 14, wherein:
the respective kernel types include a first kernel type, and the plurality of kernel objects includes a first kernel object and a second kernel object of the first kernel type;
the instructions for dequeuing include instructions for:
dequeuing a first task from a first task queue of the plurality of task queues by a thread executing the first kernel object, and activating a first compute circuit of the plurality of compute circuits indicated by the first kernel type to initiate processing of the first task; and
dequeuing a second task from the first task queue by a thread executing the second kernel object, and activating the first compute circuit to initiate processing of the second task.

18. The system of claim 14, wherein:
the respective kernel types include a first kernel type and a second kernel type, and the plurality of kernel objects includes a first kernel object of the first kernel type and a second kernel object of the second kernel type;
the instructions for dequeuing include instructions for:
dequeuing a first task from a first task queue of the plurality of task queues by a thread executing the first kernel object, and activating a first compute circuit of the plurality of compute circuits indicated by the first kernel type to initiate processing of the first task; and
dequeuing a second task from the first task queue by a thread executing the second kernel object, and activating a second compute circuit indicated by the second kernel type to initiate processing of the second task.

19. The system of claim 14, wherein:
the instructions for instantiating the plurality of kernel objects include instructions for executing at least one of the kernel objects by two or more threads; and
the instructions for dequeuing include instructions for dequeuing, based assignment of at least one of the kernel objects to one of the task queues, tasks from the one of the task queues by the two or more threads, and activating the compute circuit indicated by the kernel type of the at least one of the kernel objects by the two or more threads to initiate processing of the dequeued tasks.

20. The system of claim 14, wherein the memory arrangement is further configured with instructions that when executed cause the one or more processors to:
generate a plurality of graphs in the memory arrangement, wherein the tasks represented by each graph are independent of data processed by the tasks represented by each other graph, each graph includes respective storage areas for output data generated by the nodes of the graph, each graph has nodes and edges, each node represents a task and specifies an assignment of the task to one or more of the kernel objects, and each edge represents a data dependency between the nodes;
wherein the instructions for activating of a compute circuit of the ones of the compute circuits to initiate processing of a dequeued task include instructions for:
communicating one or more memory addresses of one or more of the respective storage areas to the compute circuit, wherein each of the one or more of the respective storage areas has output data produced in processing a task represented by a parent node of the node of the dequeued task, and the dequeued task is dependent on the output data; and
communicating to the compute circuit, a memory address of the respective storage area for output data generated in processing of the dequeued task.
```

### 1.2 Structure

Independent claims: 1 (method) and 14 (system). Claims 2-13 depend on 1 (claim 7 on 6, claim 8 on 7, claim 10 on 9); claims 15-20 depend on 14. Dependent-claim subject: 2/15 blocking vs non-blocking kernels; 3/16 several independent graphs and one queue holding tasks from different graphs; 4/17 two kernel objects of the same type sharing one queue; 5/18 different types sharing one queue; 6/19 one kernel object run by two or more threads; 7 thread count from a configurable parameter; 8 measuring performance and adjusting that parameter; 9/20 per-graph output storage, addresses passed to the compute circuit; 10 in-degree counts; 11 utilization above a threshold raises thread count; 12 on-demand report function; 13 second graph generated concurrently.

### 1.3 Keyword check (my own, regular expressions run in the browser on the 20 claim strings above, case-insensitive)

Total claim text: 15,125 characters (after trimming and joining). Patterns: `machine[\s-]*learning`, `predict`, `estimat`, `model`, `offload`, `\bGPU`, `\bCPU`, `\bFPGA`, plus `learn`, `neural`.

| Keyword | Count in claims 1-20 (each claim 1..20 individually) |
|---|---|
| machine learning | 0 in every claim |
| predict* | 0 in every claim |
| estimat* | 0 in every claim |
| model | 0 in every claim |
| offload* | 0 in every claim |
| GPU | 0 in every claim |
| CPU | 0 in every claim |
| FPGA | 0 in every claim |
| learn* (extra) | 0 in every claim |
| neural (extra) | 0 in every claim |

Independent claims 1 and 14: none of the keywords appears. The closest vocabulary is "heterogeneous plurality of compute circuits" and "kernel type indicates a compute circuit" (claims 1, 14), and in dependent claim 8 "measuring performance of the plurality of compute circuits ... adjusting the configurable parameter to adjust the number of threads" (a thread-count adjustment, not a runtime prediction). Dependent claim 11 uses a utilization threshold. The word "machine learning" appears in the TITLE and ABSTRACT of the patent, not in the claims.

Scope note: this is a text-level check of the claims. It is not a claim-construction or freedom-to-operate opinion. Absence of a word does not decide whether a feature is within a claim's scope.

Closes: LITERATURE_UPDATE item 1 (verbatim claims) and confirms the earlier paraphrase and the second-hand keyword check.

## 2. HEFT and CPOP: Topcuoglu, Hariri, Wu, IEEE TPDS 13(3):260-274, March 2002 (DOI 10.1109/71.993206)

- Source: the Marmara University open-access repository, record https://openaccess.marmara.edu.tr/entities/publication/feba5344-0457-405a-8cb2-1d26f8963e33/full (rights field "info:eu-repo/semantics/openAccess"; handle https://hdl.handle.net/11424/244213), file https://openaccess.marmara.edu.tr/bitstreams/d1584f1e-5066-47a6-8c04-15607a53960f/download (application/pdf, 789,096 bytes, %PDF-1.3, 15 pages). The two other bitstream links on the record return an HTML page, not a PDF. The earlier pass found this server returning HTTP 500/503; on 2026-10-13 it answered HTTP 200.
- Accessed: 2026-10-13. Downloaded once into a scratch directory outside the repository, text extracted with pdftotext, and the pages with equations and algorithm figures (PDF pages 3, 5, 6, 7) rendered to images and read by eye, because the equation glyphs are garbled in the text layer.
- Level: FULL-DIRECT. The PDF carries the IEEE journal running header ("IEEE TRANSACTIONS ON PARALLEL AND DISTRIBUTED SYSTEMS, VOL. 13, NO. 3, MARCH 2002", pages 260-274), so it appears to be the published layout; I make no claim about its licence beyond the repository's openAccess label.
- What is recorded below: mathematical statements restated (not copied prose), with the paper's equation numbers as printed (verified on the page images). One short quote is used where wording matters.

### 2.1 Definitions (equation numbers as printed)

| Eq. | Statement (restated) |
|---|---|
| (1) | Mean computation cost: wbar_i = (sum over j=1..q of w_{i,j}) / q, q = number of processors. |
| (2) | Edge cost when n_i runs on p_m and n_k on p_n: c_{i,k} = L_m + data_{i,k} / B_{m,n}. Zero when both tasks are on the same processor (intraprocessor cost treated as negligible). |
| (3) | Average edge cost used to label edges before scheduling: cbar_{i,k} = Lbar + data_{i,k} / Bbar (Lbar average startup time, Bbar average transfer rate). |
| (4) | EST(n_entry, p_j) = 0. |
| (5) | EST(n_i, p_j) = max{ avail[j], max over n_m in pred(n_i) of ( AFT(n_m) + c_{m,i} ) }. avail[j] is the earliest time p_j is ready; for the non-insertion reading it is the finish time of the last task on p_j. The inner max is the data-ready time. |
| (6) | EFT(n_i, p_j) = w_{i,j} + EST(n_i, p_j). (The sentence introducing (5) and (6) says "EFT and EST ... (5) and (6), respectively", while the displayed order is EST (5) then EFT (6); the paper is internally inconsistent here, the displayed order is used.) |
| (7) | makespan = max{ AFT(n_exit) }. |
| (8) | Upward rank: rank_u(n_i) = wbar_i + max over n_j in succ(n_i) of ( cbar_{i,j} + rank_u(n_j) ). |
| (9) | rank_u(n_exit) = wbar_exit. |
| (10) | Downward rank: rank_d(n_i) = max over n_j in pred(n_i) of { rank_d(n_j) + wbar_j + cbar_{j,i} }; rank_d(n_entry) = 0. |

### 2.2 HEFT (Section 4.2, Fig. 2) and CPOP (Section 4.3, Fig. 5), restated

- Fig. 2 steps: (1) set computation costs of tasks and communication costs of edges to mean values; (2) compute rank_u for all tasks traversing upward from the exit task; (3) sort the tasks in a scheduling list by non-increasing rank_u; (4-9) while unscheduled tasks exist: take the first task of the list, compute EFT on every processor with the insertion-based policy, assign it to the processor that minimises EFT.
- Task ordering: sort by decreasing rank_u. Tie-breaking: the paper says it is done randomly, and says alternative policies (for example preferring a task whose successors have higher upward ranks) were rejected because they increase time complexity. Decreasing rank_u is a topological order.
- Insertion-based policy (words, no equation): the earliest idle slot between two already-scheduled tasks on a processor is considered. The slot must be at least as long as the task's computation cost and must preserve precedence. The search for a slot on p_j starts at the ready time of n_i on p_j (when all input data from immediate predecessors have arrived at p_j) and takes the first slot that can hold the task.
- Complexity statement in the paper: HEFT is O(e x q) for e edges and q processors; for a dense graph (e proportional to v^2) it is O(v^2 x p). CPOP is O(e x p) (priority-queue operations O(log v) insert/delete, O(1) retrieve).
- CPOP: priority = rank_u + rank_d (Fig. 5 step 4); critical path found from the entry task by following the successor whose priority equals |CP| (ties: first such successor); the critical-path processor minimises the sum of w_{i,j} over the critical-path tasks; critical-path tasks go to that processor, other tasks to the EFT-minimising processor, both with insertion.
- Worked example, Fig. 3 (10 tasks, 3 processors) and Table 1: rank_u = n1 108.000, n2 77.000, n3 80.000, n4 80.000, n5 69.000, n6 63.333, n7 42.667, n8 35.667, n9 44.333, n10 14.667. HEFT schedule length 80 (Fig. 4a), scheduling order {n1, n3, n4, n2, n5, n6, n9, n7, n8, n10}; CPOP schedule length 86 (Fig. 4b). Inputs read from the page image: edge costs (1,2)=18, (1,3)=12, (1,4)=9, (1,5)=11, (1,6)=14, (2,8)=19, (2,9)=16, (3,7)=23, (4,8)=27, (4,9)=23, (5,9)=13, (6,8)=15, (7,10)=17, (8,10)=11, (9,10)=13; computation costs (P1, P2, P3) for n1..n10: (14,16,9), (13,19,18), (11,13,19), (13,8,17), (12,13,10), (13,16,9), (7,15,11), (5,11,14), (18,12,20), (21,7,16).

## 3. PEFT: Arabnejad and Barbosa, IEEE TPDS 25(3):682-694, March 2014 (DOI 10.1109/TPDS.2013.57)

- Direct route to the journal PDF: closed. Porto repository record https://repositorio-aberto.up.pt/handle/10216/97674 (full metadata read in the browser, 2026-10-13) lists file 64753.pdf, 624.71 kB, with rights "restrictedAccess" and a "Restricted Access" tag. I did not attempt to get around that restriction.
- Route that worked: Chapter 3 of the author's PhD thesis reproduces the paper under its own title and abstract and gives the TPDS citation. Thesis: Hamid Arabnejad, "QoS based workflow scheduling on heterogeneous resources", University of Porto (FCUP), 2016, DOI 10.34626/xjem-x888, record https://hdl.handle.net/10216/92290 (rights "openAccess"), file https://repositorio-aberto.up.pt/bitstream/10216/92290/2/129782.pdf (3,432,569 bytes, HTTP 200). Chapter 3 begins at thesis page 61 (PDF page index 74); thesis pages 61-75 carry the formulation, related work, PEFT and the complexity statement.
- Accessed: 2026-10-13. Downloaded once to a scratch directory outside the repository; text extracted with pdftotext, and the figure page (thesis p. 64) rendered at 420 dpi to read the sample DAG.
- Level: FULL-DIRECT for the thesis chapter. NOT the IEEE-typeset article. The chapter repeats the article's content under thesis numbering; equation numbers below are the THESIS numbers and may differ from the IEEE numbers (evidence of renumbering: the chapter says "as expressed by equation 1" for the makespan, which the chapter itself numbers (3)). Cite equation numbers only after checking them against the IEEE PDF.
- Restated, with thesis equation numbers:

| Eq. (thesis) | Statement |
|---|---|
| (1) | wbar_i = (sum over j in P of w_{i,j}) / p. |
| (2) | cbar_{i,j} = Lbar + data_{i,j} / Bbar; real communication cost is zero when v_i and v_j run on the same processor. |
| (5) | EST(n_i, p_j) = max{ T_Available(p_j), max over n_m in pred(n_i) of ( AFT(n_m) + c_{m,i} ) }; c_{m,i} = 0 if n_m is on p_j. |
| (6) | EFT(n_i, p_j) = EST(n_i, p_j) + w_{i,j}. |
| (7) | OCT(t_i, p_k) = max over t_j in succ(t_i) of [ min over p_w in P of { OCT(t_j, p_w) + w(t_j, p_w) + cbar_{i,j} } ], where cbar_{i,j} = 0 if p_w = p_k. OCT(n_exit, p_k) = 0 for every processor. Only the first level of children is used because the children's OCT is already recursive. |
| (8) | rank_oct(t_i) = ( sum over k = 1..P of OCT(t_i, p_k) ) / P, the average of the OCT row over all processors. |
| (9) | OEFT(t_i, p_j) = EFT(t_i, p_j) + OCT(t_i, p_j). |

- Algorithm 1: (1) compute the OCT table and rank_oct for all tasks; (2) create an empty ready-list and put n_entry in it; (3-11) while the ready-list is not empty: take the task with the highest rank_oct; for every processor compute EFT with the insertion-based scheduling policy and OEFT = EFT + OCT; assign the task to the processor with minimum OEFT; update the ready-list.
- Complexity, as stated: OCT table O(p(e+v)); processor assignment O(v^2 p); total O(p(e+v) + v^2 p); for dense DAGs e = O(v^2) so O(v^2 p), the same order as HEFT. The abstract states O(v^2 p) for v tasks and p processors.
- Ties: the chapter says generally that equal-priority tasks are resolved by picking one randomly (list-scheduling description in Section 3.3.1). No PEFT-specific tie rule is given.
- Statement on ranking: the authors say ranking matters less than the OCT-based processor selection, and that using rank_u instead of rank_oct was on average about 0.5 percent better on their random-graph tests.
- Worked example (thesis Fig. 1, Tables 5 and 6): 10 tasks, 3 processors. Edge costs read from the 420-dpi image: (1,2)=17, (1,3)=31, (1,4)=29, (1,5)=13, (1,6)=7, (3,7)=16, (2,8)=3, (2,9)=30, (4,8)=11, (4,9)=7, (5,9)=57, (6,8)=5, (7,10)=9, (8,10)=42, (9,10)=7. Computation costs (P1, P2, P3) for T1..T10: (22,21,36), (22,18,18), (32,27,43), (7,10,4), (29,27,35), (26,17,24), (14,25,30), (29,23,36), (15,21,8), (13,16,33). Printed OCT (Table 5): T1 64 68 86; T2 42 39 42; T3 27 41 43; T4 42 39 50; T5 28 37 28; T6 42 39 44; T7 13 16 22; T8 13 16 33; T9 13 16 20; T10 0 0 0. Printed rank_oct: 72.7, 41, 37, 43.7, 31, 41.7, 17, 20.7, 16.3, 0. Printed rank_u: 169, 114.3, 102.7, 110, 129.7, 119.3, 52.7, 92, 42.3, 20.7. Printed makespans: PEFT 122, Lookahead 127, HEFT 133, HCPT 142, PETS 147. Printed PEFT step order (Table 6): T1, T4, T6, T2, T3, T5, T8, T7, T9, T10 on P1, P1, P2, P1, P1, P3, P2, P1, P3, P2.

## 4. Check of src/caosched/schedulers/heft.py and peft.py against the originals

Files read in full: `D:\cao project\src\caosched\schedulers\heft.py`, `peft.py`. Method: formula comparison by reading, then both worked examples above executed through the repository code (`heft_plan`, `peft_plan`, `upward_rank`, `optimistic_cost_table`) using the project virtual environment, in scripts kept outside the repository (`...\scratchpad\verify\heft_paper_example.py`, `peft_paper_example.py`). Cost callable = the printed matrix by processor; comm callable = the printed edge cost, used for both rank and EST (the papers' cbar and c coincide for a uniform network).

### 4.1 Executed results

| Check | Paper | Code |
|---|---|---|
| HEFT rank_u, Fig. 3 / Table 1 (HEFT paper) | 108.000, 77.000, 80.000, 80.000, 69.000, 63.333, 42.667, 35.667, 44.333, 14.667 | identical (printed to 3 decimals) |
| HEFT makespan, Fig. 3 | 80 | 80.0 |
| HEFT processor assignment, Fig. 4a | n1,n3,n5,n7 on P3; n4,n6,n9,n10 on P2; n2,n8 on P1 | same assignment |
| HEFT order | n1, n3, n4, n2, n5, n6, n9, n7, n8, n10 | n1, n4, n3, n2, n5, n6, n9, n7, n8, n10 (only the tied pair n3/n4 swapped; both have rank_u 80.000) |
| PEFT OCT table, all 30 entries (PEFT paper Table 5) | as printed in section 3 | identical |
| PEFT rank_oct | 72.7, 41, 37, 43.7, 31, 41.7, 17, 20.7, 16.3, 0 | identical |
| rank_u on the PEFT sample | 169, 114.3, 102.7, 110, 129.7, 119.3, 52.7, 92, 42.3, 20.7 | identical |
| PEFT order and processors (Table 6) | T1,T4,T6,T2,T3,T5,T8,T7,T9,T10 on P1,P1,P2,P1,P1,P3,P2,P1,P3,P2 | identical |
| PEFT makespan | 122 | 122.0 |
| HEFT makespan on the PEFT sample | 133 | 133.0 |

So the core formulas (rank_u, EST/EFT with insertion, OCT with the same-processor zero-communication condition, rank_oct as row average, OEFT = EFT + OCT, ready-list selection by rank_oct) reproduce every printed number in both papers' examples. This replaces the earlier statement that the code follows secondary sources only.

### 4.2 Differences between the papers and the code (none changes the examples)

1. Eligibility. The paper averages over all q processors (wbar, rank_oct, OCT inner min, processor choice). The code restricts every set to `eligible_workers` (uniform eligibility, D3). With no restriction (examples) they coincide. With pool restrictions (the CUDA stages, if a pool is excluded) wbar, rank_oct and OCT change by design.
2. Communication. Paper: cbar = Lbar + data/Bbar for ranks and c = L_m + data/B_{m,n} for EST. Code: one injected `comm(parent, child)` callable for both, default 0. `src/caosched/experiment/montage_adapter.py:86` calls `plan_factories(profile, est_cfg)` without `comm`, so in the Montage runs communication is 0 and HEFT's rank is the paper's "static upward rank" variant in effect (computation costs only), and PEFT's OCT has no communication term. This matches the paper only for zero-communication settings. Local pools share files, so this is a modelling choice; it should be stated as such, not as "HEFT as in the paper" with communication.
3. Tie-breaking. HEFT and PEFT papers: random. Code: deterministic, `DAG.topological_order()` position (HEFT sort key (-rank, topo index); PEFT `min` key (-rank, topo index)); processor ties: first in worker order. This swaps n3/n4 in the HEFT example. Deterministic ties are a documented choice, not the paper's.
4. Initial ready set in PEFT. Paper: ready-list starts with n_entry (single entry; a dummy zero-cost entry is added when there are several). Code: all tasks with no dependencies start ready. On a multi-entry DAG this is the same schedule as with a zero-cost dummy entry for the purposes of ranks and placement, but I did not run a multi-entry check against a paper example.
5. Execution wrapper (outside both papers). `StaticPlanScheduler` computes the plan once at run start and dispatches ready tasks in planned-start order to their planned workers; a late task is not re-planned. This is not part of the published algorithms (they output a schedule). It resembles the plan-driven WHEFT adaptation of Ilyushkin and Epema (section 5.1), which that paper reports as fragile under estimate error.
6. Processors are workers (not pools); two workers of one pool have identical cost rows, so the processor-selection min picks the first worker on equal EFT. The papers do not define this case.

Closes: LITERATURE_UPDATE items 2, 3, 10, 11, 20 (the original definitions are now read, from the Marmara PDF for HEFT/CPOP and from the author's thesis chapter for PEFT; the IEEE PDF of PEFT with its own equation numbers is still not read).

## 5. Other sources the project cites

### 5.1 Ilyushkin and Epema, CCGrid 2018 (DOI 10.1109/CCGRID.2018.00048)

- URL: https://repository.tudelft.nl/file/File_48c766d6-16ba-4f45-bbeb-48576036aab4 (link found via the TU Delft repository record for uuid bf5bf685-bf94-4619-9f83-b872b21d3659; the resolver https://resolver.tudelft.nl/uuid:bf5bf685-bf94-4619-9f83-b872b21d3659 loads that record). Accessed 2026-10-13. PDF 1,448,964 bytes, text extracted with pdftotext.
- Level: FULL-DIRECT of the accepted author manuscript (the cover page says "Document Version Accepted author manuscript", pp. 331-341; cite the final version where it differs).
- What it says on the point the project cites it for (restated):
  - Seven policies: GBF (greedy backfilling, no estimates), CPP, OWM, FDWS, HR, FWP and WHEFT, a plan-based adaptation of HEFT to workloads of workflows (one global plan rebuilt on every workflow arrival, combined with the Alternating DAGs approach; between arrivals dispatch follows the plan strictly, and a planned task that is not eligible is skipped, leaving the processor idle).
  - Setting: simulation (modified DGSim), 100 single-processor nodes; homogeneous system, and one heterogeneous system of two equal groups (average speeds 1.5 and 0.5 workflow/hour); data transfer between tasks neglected (shared file system assumed). Workload I mixes Montage, LIGO and SIPHT synthetic workflows from the Pegasus workflow generator; Workload II is random DAGs. Estimate-error factor fe in {0.1, 2, 5, 10}, with three error methods (static, random per workflow, random per task).
  - Findings: at high utilization the order in which workflows are processed matters more than correct estimates; at low utilization even the estimate-free policy works well. WHEFT: "ineffective with workloads of workflows"; stable at 97% utilization only without errors; with errors stable only at about 40% utilization; it does build the shortest schedule for a single batch submission (1000 workflows, homogeneous). The stated reason for the instability is plan-driven dispatch that cannot adapt to wrong estimates.
  - Limits that matter for us: online streams and slowdown as the metric (we study single-workflow makespan); no data-transfer cost; speed-only heterogeneity; no learned predictor; simulation only. The authors list validation in a real cloud environment as future work.
- Closes: LITERATURE_UPDATE item 8.

### 5.2 LACHESIS (IEEE MDM 2022, DOI 10.1109/MDM55031.2022.00040)

- URLs: https://ieeexplore.ieee.org/document/9861109 (browser, 2026-10-13); https://arxiv.org/abs/2103.06980.
- Level: IEEE page RENDERED-DOM, ABSTRACT only (introduction first paragraph visible, then "Sign in to Continue Reading"; references "not available"). arXiv abs page: version metadata only; v1 9 Mar 2021, v2 19 Feb 2022; no journal reference or comment field shown.
- What the IEEE page says (restated): title "Learning to Optimize DAG Scheduling in Heterogeneous Environment"; conference 2022 23rd IEEE International Conference on Mobile Data Management (MDM), 6-9 June 2022, Paphos, Cyprus; added to Xplore 25 August 2022. Abstract: a task-duplication based learning algorithm; reinforcement learning with a purpose-built GNN selects the most promising task; the task is then assigned to an executor with duplication of all its precedent tasks by expert-designed rules; experiments over standard workloads report at most 26.7 percent reduction of makespan and 35.2 percent improvement of speedup ratio over seven strong baselines (heuristics and deep-RL methods).
- Two points for the project text: (a) the abstract itself uses "at most", so the workbook's 26.7 and 35.2 are upper figures as the spec already says; (b) the IEEE author order is Yunfan Zhou, Xijun Li, Jinhong Luo, Mingxuan Yuan, Jia Zeng, Jianguo Yao, whereas arXiv lists Luo first. The project's "Luo et al." follows arXiv; for the MDM paper the citation should follow the IEEE record ("Zhou et al."), or say explicitly that the arXiv preprint is meant.
- What stays unverified: whether the published 2022 text matches arXiv v2 on the simulation setup, inference-latency numbers and limitations (full text paywalled).

### 5.3 Cao et al., IEEE Internet of Things Journal 2024 (DOI 10.1109/JIOT.2024.3374969)

- URLs: https://doi.org/10.1109/JIOT.2024.3374969 redirected to https://ieeexplore.ieee.org/document/10463608 (browser, 2026-10-13); https://arxiv.org/abs/2303.17100.
- Level: IEEE page RENDERED-DOM, ABSTRACT plus first introduction paragraph; full text behind sign-in. arXiv abs page: v1 only (30 Mar 2023), two authors (Zequn Cao, Xiaoheng Deng).
- What the IEEE page says (restated): IEEE IoT-J vol. 11 no. 12, 15 June 2024, pp. 21632-21646, published 12 March 2024; six authors (Zequn Cao, Xiaoheng Deng, Sheng Yue, Ping Jiang, Ju Ren, Jinsong Gui). Abstract: dependent task offloading as a DAG, GAT plus DRL, multidiscrete action choosing the subtask and whether to offload it, GAT encoder pretrained unsupervised, single-user single-edge and multiuser multiedge scenarios, "outperforms prior methods".
- Note: the arXiv v1 that the project read has two authors and the journal version has six, so the text differs. The project's statements (simulation-only, HEFT among baselines, no inference-latency figure) rest on arXiv v1 and are not confirmed for the journal version. The abstract does not say "simulation" or name HEFT.

### 5.4 Liu et al., Future Generation Computer Systems 2024 (DOI 10.1016/j.future.2024.04.034)

- URLs tried: https://doi.org/10.1016/j.future.2024.04.034 (redirects to linkinghub.elsevier.com then www.sciencedirect.com/science/article/pii/S0167739X24001638: a bot-check page "Are you a robot?", captcha, nothing read; I stopped there); https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4604459 (Cloudflare "Just a moment..." challenge; stopped); https://api.crossref.org/works/10.1016/j.future.2024.04.034 (metadata read); https://arxiv.org/abs/2309.10569 (version metadata read).
- Level: ABSTRACT-level metadata only: Crossref says title "Task graph offloading via deep reinforcement learning in mobile edge computing", authors Jiagang Liu, Yun Mi, Xinyu Zhang, Xiaocui Li, FGCS vol. 158, pp. 545-555, September 2024; no abstract in the Crossref record. Crossref lists Elsevier text-and-data-mining links (api.elsevier.com ... PII:S0167739X24001638) that need an API key; not used. arXiv 2309.10569: v1 19 Sep 2023, v2 2 Oct 2023, v3 9 Oct 2023, v4 21 Mar 2024 (current), comment "13 figures". v4 (March 2024) is the closest preprint to the April 2024 FGCS acceptance; which version the earlier pass read is not recorded.
- The project's claims (25-node Montage workflows in CloudSim simulation, 4 edge devices) therefore remain at "arXiv only".

### 5.5 Song et al., Computers and Electrical Engineering 2023

- Identified: Yutao Song, Chen Li, Lihua Tian, Hui Song, "A reinforcement learning based job scheduling algorithm for heterogeneous computing environment", Computers and Electrical Engineering vol. 107, article 108653, April 2023, DOI 10.1016/j.compeleceng.2023.108653 (Crossref search result and the Xi'an Jiaotong University scholar page https://scholar.xjtu.edu.cn/zh/publications/a-reinforcement-learning-based-job-scheduling-algorithm-for-heter/, 2026-10-13).
- Level: ABSTRACT. Content (restated): two stages; task selection by a bidirectional GCN plus a fully connected network; processor allocation by a heuristic using the optimistic cost table and task duplication; better than the compared heterogeneous DAG schedulers in several scheduling scenarios. The DOI redirects to sciencedirect.com (pii S0045790623000782), which showed the same captcha page; nothing further read.

### 5.6 Wang et al., IEEE Transactions on Computers

- Identified: J. Wang, J. Hu, G. Min, W. Zhan, A. Y. Zomaya, N. Georgalas, "Dependent task offloading for edge computing based on deep reinforcement learning", IEEE Trans. Computers, DOI 10.1109/TC.2021.3131040, published online 26 November 2021 (the print issue year of 2022 in the project text is not confirmed by what I read). The abstract describes an off-policy RL method with a sequence-to-sequence network, dependent tasks as DAGs, simulation with synthetic DAGs, results "approximate the optimal solution in latency and energy consumption". Page: https://ore.exeter.ac.uk/articles/journal_contribution/Dependent_task_offloading_for_edge_computing_based_on_deep_reinforcement_learning/29783753 (University of Exeter repository, handle https://hdl.handle.net/10871/127931, "Accepted Manuscript", 1.77 MB, rights "All rights reserved").
- Level: ABSTRACT (rendered page). The accepted-manuscript file https://ore.exeter.ac.uk/ndownloader/files/56819486 answered HTTP 202 with an empty body and the header `x-amzn-waf-action: challenge` (an anti-bot challenge); I did not try to defeat it. NOT REACHABLE as full text.

## 6. STScI Digitized Sky Survey: terms of use, copyright, acknowledgement

The project fetches DSS2 blue plates (survey keyword `poss2ukstu_blue`) through archive.stsci.edu. All accessed 2026-10-13 in the built-in browser (RENDERED-DOM, full page text). Pages are official MAST/STScI pages.

### 6.1 Which survey and copyright holder the downloaded files actually carry

Read from the FITS headers of the 9 files in `D:\cao project\data\montage\instances\d1.1_dss2b_c56.7_24.0\inputs\` (header cards only; no repository file changed): ORIGIN 'STScI/MAST', SURVEY 'POSSII-J', REGION 'XJ482', PLATEID 'A1ET', TELESCOP 'Oschin Schmidt - D', EMULSION 'IIIaJ', FILTER 'GG395', PLTLABEL 'SJ00930', and the card `COPYRGHT= 'Caltech/Palomar' /GSSS: Copyright Holder`. All 9 files report the same survey and plate. So the applicable provision is the POSS-II Northern Hemisphere one (California Institute of Technology), not the UK Schmidt or AUI provisions. (The DSS acknowledgement page says plate-specific copyright is in the FITS header; the header card above is that statement.)

### 6.2 Permitted use and restrictions (MAST Data Use Policy)

- URL: https://archive.stsci.edu/data_use.html, which redirects to https://archive.stsci.edu/publishing/data-use. Level: RENDERED-DOM, full page.
- The page names the Digitized Sky Survey and the Guide Star Catalogs (derived from the DSS images) as copyrighted collections. Its permitted-use statement, restated: scientists and educators doing research, teaching (including textbooks) or other non-profit activities may use data from the copyrighted collections freely and without restriction, other than that users are requested to acknowledge the source in publications resulting from that use. The restriction, as one short quotation: "Commercial, for-profit use of the copyrighted collections is prohibited without written permission" from the copyright holder(s); contact archive@stsci.edu. For colour DSS images not covered by this policy, contact archive@stsci.edu.
- The page does not state a rule on redistributing copies of the image files themselves. The copyright text describes the images as "distributed herein by agreement" (restated from the notice below), which gives STScI's own distribution a basis but does not speak to a third party redistributing them. For publishing the raw FITS in a repository or thesis annex, ask the holder (see contacts); until then keep them out of public repositories, as WORKLOAD_AND_DATA_PROVENANCE.md already does.
- Holder list on that page, for POSS-II Northern Hemisphere surveys, restated: the compressed files of the Palomar Observatory - STScI Digital Sky Survey, based on scans of the Second Palomar Sky Survey, are copyright 1993-2003 by the California Institute of Technology; all rights reserved; contact bode@astro.caltech.edu. Other provisions on the same page: UK Schmidt southern surveys before 1993 (copyright 1976-1993, UK SERC/PPARC now STFC, represented by the Wide Field Astronomy Unit, ROE; contact fgw@aao.gov.au); southern Second Epoch (1993-2004, Anglo-Australian Observatory Board; contact fgw@aao.gov.au); POSS-I / Quick-V and all other material (1984-2004, Association of Universities for Research in Astronomy; contact archive@stsci.edu).

### 6.3 Older DSS-specific copyright page

- URL: https://archive.stsci.edu/dss/copyright.html ("MAST DSS Copyright Information", footer "Last Modified: Jul 23, 2024 17:38"). Level: RENDERED-DOM, full page. It says each file is copyright under one of the listed provisions, identified from the FITS header. For the northern survey it gives copyright 1993-1995 by the California Institute of Technology (the current Data Use page says 1993-2003; the two pages differ in years, the current Data Use page is the later statement). Everything else: copyright 1995 by AURA; produced under NASA contract NAS5-26555. The page also refers to a separate acknowledgements page.

### 6.4 Acknowledgement text (verbatim, copied from the two pages below; the page asks users to include it in publications as appropriate)

Source A, https://archive.stsci.edu/publishing/mission-acknowledgements (section "DSS", current MAST page; text selected "as appropriate"):

```
The Digitized Sky Survey was produced at the Space Telescope Science Institute under U.S. Government grant NAG W–2166. The images of these surveys are based on photographic data obtained using the Oschin Schmidt Telescope on Palomar Mountain and the UK Schmidt Telescope. The plates were processed into the present compressed digital form with the permission of these institutions.

The Second Palomar Observatory Sky Survey (POSS-II) was made by the California Institute of Technology with funds from the National Science Foundation, NASA, the National Geographic Society, the Sloan Foundation, the Samuel Oschin Foundation, and the Eastman Kodak Corporation. The Oschin Schmidt Telescope is operated by the California Institute of Technology and Palomar Observatory.
```

Source B, https://archive.stsci.edu/dss/acknowledging.html (older DSS page, "Last Modified: Jul 23, 2024"; opening sentence: "Investigators using these scans are requested to include these acknowledgments in any publications as appropriate."). Its first paragraph is the same as the first paragraph above except "The Digitized Sky Surveys were produced" (plural) and its POSS-II paragraph omits "NASA" from the funder list and ends at "Eastman Kodak Corporation." with the Oschin Schmidt sentence as a separate paragraph. Its closing statement, restated: all data are subject to the copyright summary, plate-specific copyright is in the FITS headers, and supplemental funding for sky-survey work at STScI is provided by the European Southern Observatory.

For the 9 files used here (POSS-II, plate A1ET) the first paragraph and the POSS-II paragraph of Source A apply. The UK Schmidt paragraph in Source A refers to southern plates and is not needed for these files. Which of Source A or B is "the" required text is not stated by STScI; Source A is the page labelled for mission acknowledgements. Not legal advice.

Closes: WORKLOAD_AND_DATA_PROVENANCE.md section 9 item on DSS terms and acknowledgement text, and the "licence not verified" statement in FINAL_REPORT.md for the input images (recorded here; this pass changed neither file).

## 7. Attempt log for this pass (2026-10-13)

| Target | Attempt | Outcome |
|---|---|---|
| US 11,561,826 B1 | Built-in browser to https://patents.google.com/patent/US11561826B1/en | Page loaded (title read) but the Polymer app body was empty: `document.body.innerText` empty, `get_page_text` returned only the title |
| same | In-page `fetch` of the same URL, DOMParser, `section[itemprop=claims]` | HTTP 200, 412,013 characters; 20 claims; all claim text extracted (section 1) |
| same | Other mirrors (FreePatentsOnline, ppubs, Espacenet, glgoo) | Not needed once Google Patents text was read; not attempted |
| HEFT/CPOP | https://openaccess.marmara.edu.tr/entities/publication/3f7aa175-... (the 1999 HCW record) | "404 Page not found" |
| HEFT/CPOP | https://openaccess.marmara.edu.tr/entities/publication/feba5344-0457-405a-8cb2-1d26f8963e33/full | Record read, file.pdf 770.6 KB listed |
| HEFT/CPOP | bitstreams d1584f1e..., b343f6e3..., 3a2bb3b8... via in-page fetch | First is application/pdf, 789,096 bytes; the other two return HTML |
| HEFT/CPOP | `curl` download of the d1584f1e bitstream | HTTP 200, 789,096 bytes, valid PDF, 15 pages |
| HEFT/CPOP | https://surface.syr.edu/eecs_etd/167 (Topcuoglu PhD dissertation, Syracuse, 1999) | Record only; "Full text is available to ProQuest subscribers"; not used |
| PEFT | https://repositorio-aberto.up.pt/handle/10216/97674?mode=full | Record read; file 64753.pdf "Restricted Access" (624.71 kB); not circumvented |
| PEFT | Web search for open copies (two queries) | No open journal PDF found; led to the Porto thesis record |
| PEFT | https://repositorio-aberto.up.pt/handle/10216/92290?mode=full, then bitstream 129782.pdf | Open access thesis, HTTP 200, 3,432,569 bytes; chapter 3 reproduces the paper (section 3) |
| LACHESIS | https://ieeexplore.ieee.org/document/9861109 in the browser | First load empty body; after a short wait the page rendered; abstract and intro paragraph read; full text behind sign-in |
| LACHESIS | https://arxiv.org/abs/2103.06980 | Version dates read (v1 2021-03-09, v2 2022-02-19); no journal reference |
| Cao 2024 | https://doi.org/10.1109/JIOT.2024.3374969 in the browser | Redirected to Xplore 10463608; abstract and intro read; full text behind sign-in |
| Cao 2024 | https://arxiv.org/abs/2303.17100 | v1 only, two authors |
| Liu 2024 | https://doi.org/10.1016/j.future.2024.04.034 in the browser | linkinghub, then sciencedirect captcha page; stopped |
| Liu 2024 | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4604459 | Cloudflare "Just a moment..." challenge; stopped |
| Liu 2024 | Crossref API; arXiv abs 2309.10569 | Metadata and four arXiv versions read; no abstract text from Crossref |
| Song 2023 | Crossref bibliographic search; XJTU scholar page; DOI in the browser | Metadata and abstract read; ScienceDirect captcha page |
| Wang 2022 | Web search; Exeter ORE record in the browser; `curl -I` and in-page fetch of the file | Abstract and "accepted manuscript" label read; file download answered 202 with `x-amzn-waf-action: challenge`; in-page fetch blocked; stopped |
| Ilyushkin and Epema | TU Delft resolver in the browser; web search; `curl` of repository file | HTTP 200, 1,448,964 bytes, accepted manuscript; read (section 5.1) |
| DSS terms | archive.stsci.edu/dss/copyright.html, /dss/acknowledging.html, /data_use.html, /publishing/mission-acknowledgements | Full text read in the browser (section 6) |
| DSS plate | Header cards of the 9 local FITS files, read-only | Survey POSSII-J, plate A1ET, COPYRGHT Caltech/Palomar |
| Not tried | Unpaywall API (it needs an email address in the query, and the account email is not to be sent to unrelated services); Semantic Scholar and OpenAlex were checked in the earlier pass and listed these papers as closed | n/a |
