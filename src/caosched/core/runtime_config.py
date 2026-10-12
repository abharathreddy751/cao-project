"""Runtime configuration: which worker pools exist and what each can do.

``pools`` maps a pool name to a ``PoolSpec`` (AD-4). Pool names are arbitrary
labels; "P" and "E" are only the names ``from_topology`` gives the detected
performance and efficiency core classes. The older ``p_core_slots`` /
``e_core_slots`` arguments stay as shorthand for pools "P" and "E".

The core-to-worker mapping is never hardcoded: ``RuntimeConfig.from_topology``
calls Phase 0's ``discover_topology`` + ``planned_worker_pool_config`` (the same
function that produced the validated environment record), so the runtime and
the Phase 0 record can never disagree about which logical processors are P
vs. E slots.
"""
from __future__ import annotations

import dataclasses

POOL_KINDS = ("cpu", "cuda", "remote")


@dataclasses.dataclass(frozen=True)
class PoolSpec:
    """``slots``: one worker per entry -- a logical-processor id for kind "cpu"
    (the worker is pinned to it), a CUDA device index for "cuda" (no CPU
    pinning). "remote" pools come from ``RemoteSlot`` s, not from here.
    ``task_types``: workloads the pool accepts (None = any it can execute);
    ``memory_limit_bytes``: largest ``Task.memory_bytes`` it accepts."""
    slots: tuple[int, ...] = ()
    kind: str = "cpu"
    memory_limit_bytes: int | None = None
    task_types: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "slots", tuple(self.slots))
        if self.task_types is not None:
            object.__setattr__(self, "task_types", tuple(self.task_types))
        if self.kind not in POOL_KINDS:
            raise ValueError(f"Unknown pool kind {self.kind!r}; expected one of {POOL_KINDS}")

    def to_dict(self) -> dict:
        return {"slots": list(self.slots), "kind": self.kind, "memory_limit_bytes": self.memory_limit_bytes,
                "task_types": None if self.task_types is None else list(self.task_types)}


@dataclasses.dataclass(frozen=True)
class RuntimeConfig:
    p_core_slots: tuple[int, ...] = ()
    e_core_slots: tuple[int, ...] = ()
    coordinator_core: int | None = None
    pools: dict | None = dataclasses.field(default=None, hash=False)  # name -> PoolSpec (extra to P/E)

    def __post_init__(self) -> None:
        given, pools = dict(self.pools or {}), {}
        for name, slots in (("P", self.p_core_slots), ("E", self.e_core_slots)):  # P, E first: worker order
            if slots:
                spec = PoolSpec(tuple(slots))
                if given.setdefault(name, spec) != spec:
                    raise ValueError(f"Pool {name!r} given both as {name.lower()}_core_slots and in pools")
            if name in given:
                pools[name] = given.pop(name)
        pools.update(given)
        if "P" in pools:
            object.__setattr__(self, "p_core_slots", tuple(pools["P"].slots))
        if "E" in pools:
            object.__setattr__(self, "e_core_slots", tuple(pools["E"].slots))
        object.__setattr__(self, "pools", pools)
        if any(not name for name in pools):
            raise ValueError("Pool names must be non-empty")
        cpu_slots = [s for spec in pools.values() if spec.kind == "cpu" for s in spec.slots]
        if len(set(cpu_slots)) != len(cpu_slots):
            raise ValueError(f"A logical processor is assigned to more than one worker: {cpu_slots}")
        if self.coordinator_core is not None and self.coordinator_core in cpu_slots:
            raise ValueError(f"Coordinator core {self.coordinator_core} is also a worker slot")
        if not any(spec.slots for spec in pools.values()):
            raise ValueError("RuntimeConfig needs at least one worker slot")

    @classmethod
    def from_topology(cls, max_p_slots: int | None = 2) -> "RuntimeConfig":
        from caosched.phase0 import topology as topo
        from caosched.phase0.env_record import planned_worker_pool_config

        topology = topo.discover_topology()
        if not topology.available:
            raise RuntimeError(f"Topology discovery failed: {topology.error}")
        planned = planned_worker_pool_config(topology, max_p_slots)
        if not planned.get("available"):
            raise RuntimeError(f"Worker pool config unavailable: {planned.get('error')}")
        return cls(
            p_core_slots=tuple(planned["p_core_worker_slots"]),
            e_core_slots=tuple(planned["e_core_worker_slots"]),
            coordinator_core=planned["coordinator_reserved_core"],
        )

    def to_dict(self) -> dict:
        return {
            "p_core_slots": list(self.p_core_slots),
            "e_core_slots": list(self.e_core_slots),
            "coordinator_core": self.coordinator_core,
            "pools": {name: spec.to_dict() for name, spec in (self.pools or {}).items()},
        }
