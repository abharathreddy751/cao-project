"""Proposed instrument: rank priority + predicted, queue-aware, transfer-aware EFT.

= ``EarliestFinishTimeScheduler`` (predicted exec + wait of the worker's
executing/queued tasks under their own decision contexts + transfer, with any
estimator incl. '+rc' online recalibration) with ONE change: the ready queue is
ordered by upward rank (HEFT's rank_u, computed once per run from the
estimator's idle-machine times) instead of FIFO, so tasks on the critical
path are placed first. Placement still uses ``eligible_workers``.

The rank's communication term is an approximation: ``on_run_start`` averages the child's
transfer cost over ALL pools instead of over processor pairs as in the HEFT/PEFT papers
(the originals were not checked against their text here), so ranks are HEFT-like, not
HEFT-exact.

``FileTransferModel`` is the transfer term for workflows whose data are files:
the bytes moved to / from a pool come from an injected ``bytes_fn(task) ->
(bytes_in, bytes_out)`` (declared file sizes, Stage 2) and the pool's
``LinkConfig``; local pools (no link) cost 0, like ``TransferModel``.
"""
from __future__ import annotations

import statistics

from caosched.remote.link import LinkConfig, TransferModel, payload_bytes
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.heft import Problem, upward_rank


def _payload(t) -> tuple[int, int]:
    """(bytes in, bytes out): extcmd tasks move their declared files (output size is known only after the
    task completes, so 0 before), anything else the benchmark payload."""
    if t.workload == "extcmd":
        return t.input_bytes or 0, t.output_bytes or 0
    return payload_bytes(t.workload, t.size)


class FileTransferModel(TransferModel):
    def __init__(self, links: dict[str, LinkConfig], bytes_fn=None, **kw):
        super().__init__(links, **kw)
        self.bytes_fn = bytes_fn or _payload

    def estimate(self, task, pool: str) -> float:
        link = self.links.get(pool)
        if link is None:
            return 0.0
        up, down = self.bytes_fn(task)
        return link.shim_delay(up) + link.shim_delay(down) + self.socket_a_s + self.socket_b_s_per_byte * (up + down)


class RankEftScheduler(EarliestFinishTimeScheduler):
    def on_run_start(self, dag, state) -> None:
        super().on_run_start(dag, state)
        pools = state.pools()

        # Approximation (see module docstring): mean over all pools, not HEFT/PEFT's exact average (unverified).
        def comm(parent, child) -> float:  # child's input shipped to a remote pool; mean over pools
            return statistics.fmean(self._transfer(child, p) for p in pools)

        prob = Problem(dag, state, lambda t, p: self._exec(t, p, None) + self._extra(t, p), comm)
        self.rank = upward_rank(prob)

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        return sorted(ready_ids, key=lambda t: -self.rank[t])  # stable: FIFO among equal ranks

    def describe(self) -> dict:
        return {**super().describe(), "ready_order": "upward_rank"}
