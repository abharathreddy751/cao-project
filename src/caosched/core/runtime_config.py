"""Runtime configuration derived from Phase 0's discovered topology.

The core-to-worker mapping is never hardcoded: ``RuntimeConfig.from_topology``
calls Phase 0's ``discover_topology`` + ``planned_worker_pool_config`` (the same
function that produced the validated environment record), so the runtime and
the Phase 0 record can never disagree about which logical processors are P
vs. E slots.
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class RuntimeConfig:
    p_core_slots: tuple[int, ...]
    e_core_slots: tuple[int, ...]
    coordinator_core: int | None = None

    def __post_init__(self) -> None:
        all_slots = list(self.p_core_slots) + list(self.e_core_slots)
        if len(set(all_slots)) != len(all_slots):
            raise ValueError(f"A logical processor is assigned to more than one worker: {all_slots}")
        if self.coordinator_core is not None and self.coordinator_core in all_slots:
            raise ValueError(f"Coordinator core {self.coordinator_core} is also a worker slot")
        if not all_slots:
            raise ValueError("RuntimeConfig needs at least one worker slot")

    @classmethod
    def from_topology(cls) -> "RuntimeConfig":
        from caosched.phase0 import topology as topo
        from caosched.phase0.env_record import planned_worker_pool_config

        topology = topo.discover_topology()
        if not topology.available:
            raise RuntimeError(f"Topology discovery failed: {topology.error}")
        planned = planned_worker_pool_config(topology)
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
        }
