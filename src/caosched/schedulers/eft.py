"""Earliest-Finish-Time scheduling: B6 (static profile), B7 (moving history),
and -- in Phase 4 -- P (learned estimator), all the same policy with a
different estimator plugged in.

For a ready task t and every worker w (early binding: busy workers count):

    F(t, w) = wait(w) + transfer(t, w) + exec(t, pool(w))

    wait(w)     = remaining estimated kernel time of w's executing task
                  (estimate minus time since it was submitted, floored at 0)
                  + sum of estimated kernel times of w's locally queued tasks
    transfer    = 0 for the local P/E pools (remote shim: Phase 5)
    exec        = estimator.estimate(task, pool(w), ctx(w))   [kernel-only]
                  ctx(w): occupancy snapshot excluding w (only built for
                  estimators with uses_context, e.g. E4)

The task is bound to argmin F (ties: worker order, P first). The ready queue
is FIFO (plain list-scheduling EFT, no rank ordering). Every candidate's
(wait, transfer, exec, finish) is recorded in ``last_decision`` and logged
with the ``task_dispatched`` event -- the raw material for Phase 4's
decision-regret analysis.

Feedback: on completion the estimator observes the actual kernel time
together with the context the chosen candidate was evaluated under at
decision time (needed by online recalibration, "+rc"). If the estimator
exposes ``calibration()``, its state is logged with each decision.

Known modelling gap (by the kernel-only decision): ``wait(w)`` ignores
``prepare()`` time and per-task runtime overhead, both measured in Phase 1,
so waits on busy workers are systematically underestimated.

Two optional, separately labelled extensions (defaults = the kernel-only
model above, unchanged):

* ``e2e`` (EndToEndTerms) -- END-TO-END ABLATION (project decision
  2026-10-03): every task's time becomes kernel estimate + measured setup
  (prepare) + measured per-task runtime overhead, in the exec term and in
  the wait of executing/queued tasks. Logged as ``"model": "e2e"``.
Decision context (audit D4 / AD-7, ``ctx_version`` 2): for EVERY candidate the
``EstimateContext`` actually used is logged (``log_context``, default on; off =
only for context-using estimators), the chosen candidate's context is the one
fed back to ``observe``, and tasks already executing or queued on a worker are
estimated under the context of THEIR own placement decision, not the new
task's. ``legacy_wait_context=True`` restores the pre-fix behaviour (queued
tasks re-estimated under the candidate's context, ``ctx_version`` 1) so old
runs stay reproducible. Candidates come from ``eligible_workers`` (D3).

* ``transfer`` (object with ``estimate(task, pool) -> seconds``) -- Phase 5
  remote offloading: the transfer term for pools behind a link (0 for local
  pools). A remote worker is busy for transfer + execution, so queued tasks
  contribute their transfer time to the wait as well.
"""
from __future__ import annotations

from caosched.core.scheduler_base import SchedulerPolicy, eligible_workers
from caosched.core.task import Task
from caosched.estimators.base import EstimateContext, ExecutionTimeEstimator


class EarliestFinishTimeScheduler(SchedulerPolicy):
    binds_only_idle = False

    def __init__(self, estimator: ExecutionTimeEstimator, name: str, e2e=None, transfer=None,
                 allowed_pools: list[str] | None = None, log_context: bool = True,
                 legacy_wait_context: bool = False):
        self.log_context = log_context
        self.legacy_wait_context = legacy_wait_context
        self.estimator = estimator
        self.name = name
        self.e2e = e2e
        self.transfer = transfer
        self.allowed_pools = None if allowed_pools is None else list(allowed_pools)
        self._decision_ctx: dict[str, EstimateContext | None] = {}

    def on_run_start(self, dag, state) -> None:
        self.estimator.reset()
        self._decision_ctx = {}
        for t in dag.tasks.values():  # fail before the run, not mid-run, on unprofiled keys
            for pool in state.pools():
                if (self.allowed_pools is None or pool in self.allowed_pools) and \
                        (t.eligible_pools is None or pool in t.eligible_pools):
                    self._occupancy(t, pool, EstimateContext())

    def _exec(self, task: Task, pool: str, ctx: EstimateContext | None) -> float:
        return self.estimator.estimate(task, pool, ctx)

    def _extra(self, task: Task, pool: str) -> float:
        return self.e2e.extra(task, pool) if self.e2e is not None else 0.0

    def _transfer(self, task: Task, pool: str) -> float:
        return self.transfer.estimate(task, pool) if self.transfer is not None else 0.0

    def _occupancy(self, task: Task, pool: str, ctx: EstimateContext | None) -> float:
        """How long a worker of ``pool`` is occupied by ``task`` under the model."""
        return self._transfer(task, pool) + self._exec(task, pool, ctx) + self._extra(task, pool)

    def _wait(self, w, state, now: float, ctx: EstimateContext | None) -> float:
        wait = 0.0
        if w.busy:
            cur = state.dag.tasks[w.current_task]
            wait += max(0.0, self._occupancy(cur, w.pool, self._ctx_of(w.current_task, ctx)) - (now - w.current_submitted_at))
        for tid in w.local_queue:
            wait += self._occupancy(state.dag.tasks[tid], w.pool, self._ctx_of(tid, ctx))
        return wait

    def _ctx_of(self, task_id: str, candidate_ctx: EstimateContext | None) -> EstimateContext | None:
        """Context under which an already-placed task is estimated: its own decision's."""
        return candidate_ctx if self.legacy_wait_context else self._decision_ctx.get(task_id, candidate_ctx)

    def select_worker(self, task: Task, state) -> str | None:
        now = state.now()
        candidates, ctxs = {}, {}
        for wid in eligible_workers(task, state):
            w = state.workers[wid]
            if self.allowed_pools is not None and w.pool not in self.allowed_pools:
                continue
            ctx = ctxs[wid] = (EstimateContext.from_state(state, wid)
                               if (self.estimator.uses_context or self.log_context) else None)
            wait, transfer, exe = self._wait(w, state, now, ctx), self._transfer(task, w.pool), self._exec(task, w.pool, ctx)
            c: dict = {"wait": wait, "transfer": transfer, "exec": exe}
            if self.e2e is not None:
                c["setup"] = self.e2e.setup(task.est_workload, task.est_size, w.pool)
                c["overhead"] = self.e2e.overhead(w.pool)
            c["finish"] = wait + transfer + exe + c.get("setup", 0.0) + c.get("overhead", 0.0)
            if ctx is not None:
                c["ctx"] = ctx.to_dict()
            candidates[wid] = c
        if not candidates:
            raise ValueError(f"{self.name}: no eligible worker for {task.task_id!r}")
        best = min(candidates, key=lambda wid: candidates[wid]["finish"])  # min() keeps first on ties
        self.last_decision = {"policy": self.name, "chosen": best, "candidates": candidates,
                              "model": "e2e" if self.e2e is not None else "kernel",
                              "ctx_version": 1 if self.legacy_wait_context else 2}
        if hasattr(self.estimator, "calibration"):
            self.last_decision["calibration"] = self.estimator.calibration()
        self._decision_ctx[task.task_id] = ctxs[best]  # the very context logged above (parity)
        return best

    def on_task_completed(self, task: Task) -> None:
        ctx = self._decision_ctx.pop(task.task_id, None)
        assert task.assigned_pool is not None and task.wall_time_seconds is not None  # a completed task
        self.estimator.observe(task, task.assigned_pool, task.wall_time_seconds, ctx)

    def describe(self) -> dict:
        d = {**super().describe(), "estimator": self.estimator.describe(),
             "model": "e2e" if self.e2e is not None else "kernel", "allowed_pools": self.allowed_pools,
             "log_context": self.log_context, "legacy_wait_context": self.legacy_wait_context}
        if self.e2e is not None:
            d["e2e_terms"] = self.e2e.source
        if self.transfer is not None:
            d["transfer"] = self.transfer.describe()
        return d
