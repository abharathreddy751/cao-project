"""Study 2 hidden-cost workload (protocol section 18): a learned predictor that sees a task parameter, and the human heuristic.

``IterModelEstimator``: kernel time of ``img_denoise`` on a pool = a + b * iterations (one least-squares line per pool, fitted by
``scripts/study2_fit_iter_model.py`` from the logs of an EARLIER session); every other stage is the solo table (E1) lookup, exactly as
the blind predictor. Decision-time safe: ``iterations`` is a task parameter known when the task is ready.

``ParamFirstGreedy``: the informed non-predictive rule, B4 (first idle worker, P before E) with the ready queue ordered by the
chain's ``iterations`` (largest first). It uses the same parameter with no model: the hand heuristic the learned model has to be
compared with, so that "prediction beats rules that cannot see the parameter" is not confused with "prediction beats every rule".
"""
from __future__ import annotations

import json
from pathlib import Path

from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator
from caosched.estimators.profile import StaticProfileEstimator
from caosched.schedulers.simple import GreedyEligibleScheduler


class IterModelEstimator(ExecutionTimeEstimator):
    name = "IterModel"

    def __init__(self, base: StaticProfileEstimator, line: dict[str, list[float]], source: str | None = None):
        self.base, self.line, self.source = base, {p: (float(a), float(b)) for p, (a, b) in line.items()}, source

    @classmethod
    def load(cls, path: Path, profile: Path) -> "IterModelEstimator":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(StaticProfileEstimator.from_file(profile), d["denoise_line_by_pool"], str(path))

    def estimate(self, task, pool: str, ctx: EstimateContext | None = None) -> float:
        if task.est_workload == "img_denoise":
            if pool not in self.line:
                raise KeyError(f"IterModel has no denoise line for pool {pool!r}")
            a, b = self.line[pool]
            return max(1e-6, a + b * int(task.params["iterations"]))
        return self.base.estimate(task, pool, ctx)

    def describe(self) -> dict:
        return {"name": self.name, "source": self.source, "denoise_line_by_pool": {p: list(v) for p, v in self.line.items()},
                "base": self.base.describe()}


class ParamFirstGreedy(GreedyEligibleScheduler):
    def on_run_start(self, dag, state) -> None:
        super().on_run_start(dag, state)
        self._w = {t.task_id.rsplit("_", 1)[-1]: int(t.params["iterations"]) for t in dag.tasks.values()
                   if t.workload == "img_denoise"}

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        return sorted(ready_ids, key=lambda t: -self._w.get(t.rsplit("_", 1)[-1], 0))


class CostFirstGreedy(GreedyEligibleScheduler):
    """B4 with the ready queue ordered by a hand-written cost formula, largest first: chain pixels x denoise iterations (the formula a person
    would write after learning that both factors matter). NON-predictive and as informed as a rule can be about the two factors, so a
    learned model can at best match it (protocol section 30); it is the strict baseline, the one-factor rules are the naive ones."""

    def on_run_start(self, dag, state) -> None:
        super().on_run_start(dag, state)
        self._w = {t.task_id.rsplit("_", 1)[-1]: float(t.size) * int(t.params["iterations"])
                   for t in dag.tasks.values() if t.workload == "img_denoise"}

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        return sorted(ready_ids, key=lambda t: -self._w.get(t.rsplit("_", 1)[-1], 0.0))
