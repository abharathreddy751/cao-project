"""Scheduler policy interface.

Every scheduling policy -- Phase 2's baselines (B0-B7, in
``caosched.schedulers``), Phase 4's predictive policy (P), and the oracle
replay (O) -- implements ``SchedulerPolicy``. The coordinator has no idea
which concrete policy it is running, which is what lets the same DAG trace be
replayed under every policy (the project's core experimental requirement).

Hooks, in call order:
  ``on_run_start(dag, state)``      once, before any task is ready
  ``order_ready(ready_ids, state)`` each dispatch pass: priority order of the
                                    global ready queue (default FIFO)
  ``select_worker(task, state)``    worker id to bind ``task`` to, or None to
                                    leave it in the ready queue for now
  ``on_task_completed(task)``       after each successful completion
  ``retry_after(state)``            seconds until the policy wants another
                                    dispatch pass although it bound nothing
                                    (deliberate idling; default None)

Binding contract, enforced by the coordinator (violations raise
``SchedulerContractError``, never silently "fixed up"):
  * the returned id must be an existing worker;
  * if ``binds_only_idle`` is True (late binding) it must be an idle worker.
    Early-binding policies set it False and may bind to busy workers; the
    task then waits in that worker's local queue (see runtime_state.py).

A policy may set ``self.last_decision`` (a JSON-serialisable dict, e.g.
candidate finish times) inside ``select_worker``; the coordinator resets it
to None before each call and logs it with the ``task_dispatched`` event.
"""
from __future__ import annotations

import abc

from caosched.core.task import Task


class SchedulerContractError(RuntimeError):
    pass


class SchedulerPolicy(abc.ABC):
    name: str = "abstract"
    binds_only_idle: bool = True
    last_decision: dict | None = None

    def on_run_start(self, dag, state) -> None:
        """Called once per run (DAG-level precomputation, state reset)."""

    def order_ready(self, ready_ids: list[str], state) -> list[str]:
        return ready_ids

    @abc.abstractmethod
    def select_worker(self, task: Task, state) -> str | None:
        raise NotImplementedError

    def on_task_completed(self, task: Task) -> None:
        """Feedback hook after a task finishes (observed kernel time, pool,
        etc. are on ``task``). Default: no-op. History estimators use this."""

    def retry_after(self, state) -> float | None:
        """If the policy is deliberately holding ready tasks back (e.g. a data
        collection policy enforcing idle gaps), the delay in seconds after
        which the coordinator should run another dispatch pass. None (the
        default) means "nothing to wait for": an idle machine with ready tasks
        is then a deadlock."""
        return None

    def describe(self) -> dict:
        """Policy configuration, logged in ``run_started``."""
        return {"name": self.name, "binds_only_idle": self.binds_only_idle}


class FirstIdleScheduler(SchedulerPolicy):
    """Pipeline-exercise/test placeholder: first idle worker, P pool first.
    NOT one of the project's baselines B0-B7 (see ``caosched.schedulers``).
    (Named ``RoundRobinScheduler`` in session 1, which it never was.)"""

    name = "placeholder_first_idle"

    def select_worker(self, task: Task, state) -> str | None:
        idle = state.idle_workers("P") + state.idle_workers("E")
        return idle[0] if idle else None
