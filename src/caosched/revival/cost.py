"""End-to-end task cost as separately inspectable components (revival).

    total = compute + load_extra + setup + transfer

* ``compute``    the estimator's kernel time (task-parameter model, or the baseline profile), times the class-aware residual correction
                 (``StateProvider.bias_of``);
* ``load_extra`` compute x (worker load correction - 1): what the live resource state adds on this particular worker;
* ``setup``      measured per-task input generation + runtime IPC (``EndToEndTerms``), 0 and flagged if not measured;
* ``transfer``   link model of a remote pool (``FileTransferModel``/``TransferModel``), 0 for local pools.

Nothing here reads the actual runtime of the task being scheduled.
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class CostBreakdown:
    compute_s: float
    load_extra_s: float = 0.0
    setup_s: float = 0.0
    transfer_s: float = 0.0
    missing: tuple[str, ...] = ()

    @property
    def total_s(self) -> float:
        return self.compute_s + self.load_extra_s + self.setup_s + self.transfer_s

    def to_log(self) -> dict:
        d: dict = {"compute": round(self.compute_s, 6), "total": round(self.total_s, 6)}
        for k, v in (("load", self.load_extra_s), ("setup", self.setup_s), ("transfer", self.transfer_s)):
            if v:
                d[k] = round(v, 6)
        if self.missing:
            d["missing"] = list(self.missing)
        return d
