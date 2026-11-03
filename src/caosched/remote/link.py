"""Link model for remote offloading (Phase 5).

``LinkConfig`` describes one direction-symmetric link:
    latency_s        one-way propagation latency
    bandwidth_Bps    payload rate in bytes/second (None = no shaping: the
                     real socket's own speed only)
    per_message_s    fixed serialization / protocol overhead per message

The *shim* (``shim_delay`` + ``precise_wait``) is what makes a localhost TCP
connection behave like that link: before a message of n bytes is sent the
sender waits latency + per_message + n / bandwidth, then really sends the n
bytes through the socket. Time spent is always *measured* around the whole
operation and logged; the configured value is never reported as if it were
the achieved one. With a physical remote device the shim is configured to
zero and the real network supplies the delay -- nothing else changes.

``payload_bytes`` defines the bytes that cross the link per task. Sizes are
derived from the workloads' actual data (see caosched.phase0.benchmarks.
workloads); the bytes sent are a buffer of that size whose *content* is a
stand-in -- the node regenerates the deterministic inputs from the task seed,
so results are unaffected.

``TransferModel`` is the scheduler-side analytic estimate of a remote task's
round-trip transfer time (both directions), used as EFT's transfer term.
"""
from __future__ import annotations

import dataclasses
import functools
import time
import zlib

from caosched.util import clock

SLEEP_SPIN_THRESHOLD_S = 0.0006  # time.sleep overshoots ~0.3-0.7 ms on CPython 3.11/Windows (measured)


@dataclasses.dataclass(frozen=True)
class LinkConfig:
    name: str
    latency_s: float = 0.0
    bandwidth_Bps: float | None = None
    per_message_s: float = 0.0

    def __post_init__(self) -> None:
        if self.latency_s < 0 or self.per_message_s < 0:
            raise ValueError("latency and per-message overhead must be >= 0")
        if self.bandwidth_Bps is not None and self.bandwidth_Bps <= 0:
            raise ValueError("bandwidth must be > 0 or None")

    def shim_delay(self, n_bytes: int) -> float:
        rate = 0.0 if self.bandwidth_Bps is None else n_bytes / self.bandwidth_Bps
        return self.latency_s + self.per_message_s + rate

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LinkConfig":
        return cls(**d)


def precise_wait(seconds: float) -> float:
    """Wait ``seconds`` (sleep, then spin the last < 0.6 ms); return the
    measured elapsed time."""
    t0 = clock.now()
    if seconds <= 0:
        return 0.0
    if seconds > SLEEP_SPIN_THRESHOLD_S:
        time.sleep(seconds - SLEEP_SPIN_THRESHOLD_S)
    while clock.now() - t0 < seconds:
        pass
    return clock.now() - t0


@functools.lru_cache(maxsize=None)
def _compressed_len(size: int) -> int:
    """Actual zlib output length for the compression workload's input of
    ``size`` bytes (seed 0). Input is a repeated random 4 KB chunk, so the
    length is essentially seed-independent."""
    from caosched.phase0.benchmarks.workloads import WORKLOADS

    return len(zlib.compress(WORKLOADS["compression"].prepare(size, 0), level=6))


def payload_bytes(workload: str, size: int) -> tuple[int, int]:
    """(bytes to the remote node, bytes back) for one task."""
    if workload == "matmul":          # two float64 NxN inputs, one NxN result
        return 2 * size * size * 8, size * size * 8
    if workload == "image_filter":    # RGB side x side in, blurred RGB image out
        return size * size * 3, size * size * 3
    if workload == "compression":     # raw bytes in, compressed bytes out
        return size, _compressed_len(size)
    if workload.startswith("img_"):   # application stages: exact .npy artifact sizes
        from caosched.apps.stages import stage_payload_bytes
        return stage_payload_bytes(workload, size)
    raise KeyError(f"No payload model for workload {workload!r}")


class TransferModel:
    """EFT transfer term: round trip over the pool's link, 0 for local pools.

        estimate = shim_delay(up) + shim_delay(down) + socket_a + socket_b * (up + down)

    The socket terms are the *measured* cost of the mechanism itself
    (serialization + TCP over the real socket with the shim at zero), fitted
    by scripts/profile_static.py --remote-node-core (``link_calibration``).
    Without a calibration they are 0 (pure configured link)."""

    def __init__(self, links: dict[str, LinkConfig], socket_a_s: float = 0.0, socket_b_s_per_byte: float = 0.0,
                 calibration_source: str | None = None):
        self.links = dict(links)
        self.socket_a_s = socket_a_s
        self.socket_b_s_per_byte = socket_b_s_per_byte
        self.calibration_source = calibration_source

    @classmethod
    def with_profile_calibration(cls, links: dict[str, LinkConfig], profile_path) -> "TransferModel":
        import json
        from pathlib import Path

        cal = json.loads(Path(profile_path).read_text(encoding="utf-8")).get("link_calibration")
        if not cal:
            raise ValueError(f"{profile_path} has no link_calibration (profile without a remote slot)")
        return cls(links, cal["socket_a_s"], cal["socket_b_s_per_byte"], str(profile_path))

    def estimate(self, task, pool: str) -> float:
        link = self.links.get(pool)
        if link is None:
            return 0.0
        up, down = payload_bytes(task.workload, task.size)
        return (link.shim_delay(up) + link.shim_delay(down)
                + self.socket_a_s + self.socket_b_s_per_byte * (up + down))

    def describe(self) -> dict:
        return {"name": "link_model", "links": {p: l.to_dict() for p, l in self.links.items()},
                "socket_a_s": self.socket_a_s, "socket_b_s_per_byte": self.socket_b_s_per_byte,
                "calibration_source": self.calibration_source}
