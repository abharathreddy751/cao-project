"""Final-study policies (new names; the registered ones are untouched).

What each cost term contains (checked in the source before this file was written; see docs/final/PROTOCOL_final.md, section 3):

* kernel prediction ``_exec`` = the model's estimate of ``wall_time_seconds`` = the timed ``compute`` of the stage. For a CUDA stage
  that call performs the host-to-device copy, the kernels and the device-to-host copy itself (``apps/cuda_stages.py``), so the
  copies are INSIDE this term. They are never added again here.
* ``EndToEndTerms.setup`` = median((t_completed - t_started) - wall_time_seconds) of the same stage on the same pool, measured from
  earlier logs by ``scripts/study2_e2e_terms.py``: artifact read/decode and encode/write inside the worker. Not in the kernel term.
* ``EndToEndTerms.overhead`` = coordinator-to-worker plus worker-to-coordinator message time per pool. Not in the kernel term.
* ``transfer`` = the link model of a REMOTE pool (``FileTransferModel``); 0 for P, E and G.

``PredictedRankGreedyE2E`` places with the sum of those terms (``EarliestFinishTimeScheduler._occupancy``), the same quantity its rank
already uses (``RankEftScheduler.on_run_start``: exec + extra), so ordering and placement no longer disagree.
"""
from __future__ import annotations

from caosched.core.scheduler_base import eligible_workers
from caosched.estimators.e2e import EndToEndTerms
from caosched.schedulers.heft import HeftScheduler
from caosched.study2.policies import PredictedRankGreedy


class PredictedRankGreedyE2E(PredictedRankGreedy):
    """PRED_RANK_GREEDY with end-to-end placement: upward-rank order (unchanged), late binding to an IDLE eligible worker, the one
    with the smallest predicted OCCUPANCY = transfer + kernel + setup + IPC overhead. With every e2e term and the transfer term at
    zero the decisions equal ``PredictedRankGreedy`` (tests/test_final_policies.py). Never holds a task (``hold_min_s`` is None)."""

    def __init__(self, estimator, name: str, e2e: EndToEndTerms, transfer=None, **kw):
        if e2e is None:
            raise ValueError("PredictedRankGreedyE2E needs EndToEndTerms; use PredictedRankGreedy for kernel-only placement")
        super().__init__(estimator, name, hold_min_s=None, e2e=e2e, transfer=transfer, **kw)

    def select_worker(self, task, state) -> str | None:
        idle = eligible_workers(task, state, idle_only=True)
        if self.allowed_pools is not None:
            idle = [w for w in idle if state.pool_of(w) in self.allowed_pools]
        if not idle:
            return None
        occ, best = min((self._occupancy(task, state.pool_of(w), None), w) for w in idle)  # ties: worker id, as PredictedRankGreedy
        pool = state.pool_of(best)
        self.last_decision = {"policy": self.name, "chosen": best, "predicted_s": self._exec(task, pool, None), "model": "e2e",
                              "predicted_occupancy_s": occ, "predicted_extra_s": self._extra(task, pool),
                              "predicted_transfer_s": self._transfer(task, pool)}
        return best

    def describe(self) -> dict:
        return {**super().describe(), "binding": "late, predicted rank order, end-to-end placement",
                "placement_cost": "transfer + kernel + setup + ipc (H2D/D2H already inside the kernel term)"}


class HeftE2E(HeftScheduler):
    """HEFT static plan whose cost matrix is kernel + setup + IPC overhead (the same occupancy ``PredictedRankGreedyE2E`` uses)."""

    def __init__(self, estimator, name: str, e2e: EndToEndTerms, comm=None):
        if e2e is None:
            raise ValueError("HeftE2E needs EndToEndTerms")
        super().__init__(estimator, name, comm)
        self.e2e = e2e

    def _cost(self, task, pool: str) -> float:
        return self.estimator.estimate(task, pool, None) + self.e2e.extra(task, pool)

    def describe(self) -> dict:
        return {**super().describe(), "cost": "kernel + setup + ipc", "e2e_terms": self.e2e.source}


class HeftOracleReference(HeftScheduler):
    """HEFT driven by ``CachedOracle`` costs. A REFERENCE ONLY: the costs are medians of measured times from calibration runs of the
    same stage, parameters, size and pool; no online policy has them. Never reported as a deployable static scheduler."""

    def describe(self) -> dict:
        return {**super().describe(), "reference_only": True, "note": "oracle-informed cost matrix; not a deployable scheduler"}
