# B4 — patent-mapped comparison baseline

**B4 is a comparison baseline mapped to one general idea of a patent. It is
not an implementation, reproduction, or evaluation of the patent, and no
result for B4 may be described as a result for the patent's system.**

## Reference

- **US 11,561,826 B1** — "Scheduling processing of machine learning tasks on
  heterogeneous compute circuits"
- Assignee: Xilinx, Inc. Inventors: S. Nagpal, A. Karumannil, V. Jain,
  A. K. Patil. Filed 2020-11-12, granted **2023-01-24**.
- Source consulted: Google Patents page for US11561826B1 (fetched
  2026-10-03). Quotations below are verbatim from that page's abstract and
  description. **The full text of the claims was not retrieved**, so no
  claim-level mapping is made or implied.

## What the patent describes (verbatim excerpts)

Abstract:
> "Scheduling work of a machine learning application includes instantiating
> kernel objects by a computer processor in response to input of kernel
> definitions. Each kernel object is of a kernel type indicating a compute
> circuit. The computer processor generates a graph in a memory. Each node
> represents a task and specifies an assignment of the task to one or more of
> the kernel objects, and each edge represents a data dependency. Task queues
> are created in the memory and assigned to queue tasks represented by the
> nodes. Kernel objects are assigned to the task queues, and the tasks are
> enqueued by threads executing the kernel objects, based on assignments of
> the kernel objects to the task queues and assignments of the tasks to the
> kernel objects. Tasks are dequeued by threads, and the compute circuits are
> activated to initiate processing of the dequeued tasks."

Description:
> "a thread will only dequeue a task from the assigned task queue if the node
> that represents that task has assigned the kernel of the kernel object being
> executed by the thread."

> "Each kernel is associated with one and only one task queue." ...
> "a task queue can be assigned to multiple kernels."

> "the system manager can automatically increase the number of worker threads
> for a compute circuit if the utilization level of that compute circuit is
> greater than a threshold."

## Mapping

| Patent concept | Our runtime | Status |
|---|---|---|
| Task node assigned to "one or more of the kernel objects"; kernel type indicates a compute circuit | Per-workload **eligible pools** (`policies.B4_greedy_eligible.eligibility` in `config/phase2.yaml`); pools P / E play the role of heterogeneous compute circuits | **Mapped** |
| Thread dequeues a task only if the task is assigned to that thread's kernel; dispatch driven by thread availability, no cost/performance model | An idle worker receives the oldest ready task it is eligible for; no execution-time estimate is consulted | **Mapped** (the core of B4) |
| Edges = data dependencies; children enqueued after parents complete | DAG dependency counters in `core/dag.py` | Present in our runtime **for every policy** — not a B4 feature |
| Task queues per kernel, shared by kernels with overlapping node assignments | One global FIFO ready queue, scanned for eligibility | **Approximated** (our interpretation; equivalent when every task is eligible everywhere, as in the Phase 2 config) |
| Which free thread takes a task when several could | Not stated in the patent text consulted | **Our choice:** pool priority P before E, then worker id order |
| Kernel objects instantiated from kernel definitions; per-node kernel parameters | — | Not implemented |
| FPGA / GPU / other accelerator compute circuits | Only CPU P-core and E-core pools | Not implemented |
| Blocking vs. non-blocking kernels; wait threads polling job completion | Every task is a synchronous CPU kernel in a worker process | Not implemented |
| In-action graphs, input/output buffers passed between tasks | Tasks exchange no data | Not implemented |
| Multiple jobs pipelined through shared task queues | One DAG per run | Not implemented |
| Utilization measurement and automatic increase of worker threads above a threshold | Fixed worker slots from the Phase 0 topology (utilization is derivable from our event logs but never acted on) | Not implemented |
| Worker threads | Persistent, affinity-pinned worker *processes* | Different mechanism |

## Why this mapping is the relevant comparison

The research question is how much execution-time prediction a heterogeneous
scheduler needs. The patent's dispatch idea assigns tasks by **declared
eligibility and availability, without predicting execution time**. B4
isolates exactly that behaviour on our P/E pools, so B4 against the EFT
family (B6/B7, P) measures the value of prediction over eligibility-gated
greedy dispatch. Nothing more is claimed.

## Configuration used in Phase 2

`eligibility: {}` (every workload eligible on both pools), `priority: [P, E]`.
B4's dispatch behaviour was not changed by this mapping (documentation and
the logged `scheduler_config.patent_mapping` field only), so the Phase 2
results for B4 (`phase2_20261003T115816`) stand as recorded.
