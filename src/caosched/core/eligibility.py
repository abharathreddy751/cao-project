"""Build-time eligibility (AD-4..AD-6): which pools may run which task.

``resolve_eligibility`` runs once before a run starts. For every task it
works out the pool kinds that have an implementation of the task's workload
(extcmd: cpu; application stage: cpu, remote, and cuda only if a CUDA variant
exists; CUDA-only workload: cuda), then applies each pool's capabilities
(``task_types``, ``memory_limit_bytes``). An explicit ``eligible_pools`` that
names an incapable pool is an error; ``None`` ("any") is narrowed to the capable
pools. A task left with no pool raises ``EligibilityError`` instead of
deadlocking mid-run. Policies then only ever pick among
``scheduler_base.eligible_workers``.
"""
from __future__ import annotations

from caosched.core.runtime_config import PoolSpec


class EligibilityError(ValueError):
    pass


def supported_kinds(workload: str, pool_specs: dict[str, PoolSpec]) -> frozenset[str]:
    """Pool kinds that can execute ``workload`` (device is a property of the pool, not of the task)."""
    from caosched.apps.stages import STAGES, cuda_stages
    from caosched.core.extcmd import EXTCMD
    from caosched.phase0.benchmarks.workloads import WORKLOADS

    if workload == EXTCMD:
        return frozenset({"cpu"})
    known = workload in STAGES or workload in WORKLOADS
    # Only import the (torch-backed) CUDA variants when a cuda pool exists or the workload is unknown.
    cuda = cuda_stages() if (not known or any(s.kind == "cuda" for s in pool_specs.values())) else {}
    if workload in cuda and workload not in STAGES:
        return frozenset({"cuda"})  # CUDA-only variant: never eligible for a pool without CUDA
    # An unknown workload keeps cpu/remote and fails at run time, as before.
    return frozenset({"cpu", "remote"} | ({"cuda"} if workload in cuda else set()))


def resolve_eligibility(dag, pool_specs: dict[str, PoolSpec]) -> None:
    """Validate and narrow ``task.eligible_pools`` for every task of ``dag``.
    ``pool_specs``: the pools that actually have workers.
    Mutates the tasks, but only after every task validated (an ``EligibilityError`` leaves the DAG untouched).
    The narrowing persists on the tasks: ``Coordinator.run`` restores the declared values when the run ends,
    a direct caller reusing a DAG against different pools must do the same."""
    pools = list(pool_specs)
    narrowed: dict[str, tuple[str, ...]] = {}
    for tid, t in dag.tasks.items():
        kinds = supported_kinds(t.workload, pool_specs)

        def capable(p: str) -> bool:
            s = pool_specs[p]
            return (s.kind in kinds and (s.task_types is None or t.workload in s.task_types)
                    and (t.memory_bytes is None or s.memory_limit_bytes is None or t.memory_bytes <= s.memory_limit_bytes))

        eff = t.eligible_pools
        if eff is None:
            ok = tuple(p for p in pools if capable(p))
            if len(ok) < len(pools):
                eff = narrowed[tid] = ok
        else:
            bad = [p for p in eff if p in pool_specs and not capable(p)]
            if bad:
                raise EligibilityError(f"Task {tid!r} ({t.workload}) is eligible for pool(s) {bad} that cannot run it "
                                       f"(kind/task_types/memory; runnable kinds: {sorted(kinds)})")
        if not [p for p in (pools if eff is None else eff) if p in pool_specs]:
            raise EligibilityError(f"Task {tid!r} ({t.workload}) has no eligible worker: "
                                   f"eligible_pools={eff}, pools with workers={pools}")
    for tid, ok in narrowed.items():
        dag.tasks[tid].eligible_pools = ok
