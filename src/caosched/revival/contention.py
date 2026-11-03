"""Controlled CPU contention for the revival experiments (dynamic-contention workload).

A ``ContentionSchedule`` says which logical cores are shared with spinning "burner" processes during which time windows, relative to
the moment the run starts. ``ContentionRunner`` keeps persistent burner processes (one per burner slot, pinned to its core) and starts
a schedule on demand; every condition of a block gets the SAME schedule, so only the scheduling policy differs. The burners are a
measurement instrument (an emulated foreign load), not part of any scheduler: a policy may only learn about them through signals
available at decision time (completed-task residuals, per-core utilisation sampled by ``revival.state``).

``Window.burners`` = number of spinning processes sharing the core with the worker pinned there; with the operating system's fair share
the worker then runs at about 1/(1+burners) of its speed (the measured factors are recorded by ``scripts/revival_calibrate.py``).
"""
from __future__ import annotations

import dataclasses
import multiprocessing as mp
import random
import time
from typing import Any, Sequence

from caosched.util import clock


@dataclasses.dataclass(frozen=True)
class Window:
    core: int
    start_s: float
    end_s: float
    burners: int = 1


@dataclasses.dataclass(frozen=True)
class ContentionSchedule:
    name: str
    windows: tuple[Window, ...]

    def burners_at(self, core: int, t_rel: float) -> int:
        return sum(w.burners for w in self.windows if w.core == core and w.start_s <= t_rel < w.end_s)

    def duration_for(self, core: int, t_rel: float, work_s: float, slowdown: dict[int, float], min_affected_s: float = 0.03) -> float:
        """Wall time for ``work_s`` seconds of full-speed work started at ``t_rel`` on ``core`` when the speed is 1/slowdown[burners]
        in each window (``slowdown``: burners -> factor, measured by ``scripts/revival_calibrate.py``). Work shorter than
        ``min_affected_s`` is not slowed (a task shorter than the OS time slice is measured to run at full speed). The schedule is
        known to an offline ORACLE only; a deployable policy never calls this."""
        if work_s < min_affected_s:
            return work_s
        edges = sorted({0.0, *(w.start_s for w in self.windows if w.core == core), *(w.end_s for w in self.windows if w.core == core)})
        t, left = t_rel, work_s
        while left > 1e-12:
            nxt = next((e for e in edges if e > t + 1e-12), float("inf"))
            s = slowdown.get(self.burners_at(core, t), max(slowdown.values()))
            seg = (nxt - t) / s
            if seg >= left:
                t += left * s
                left = 0.0
            else:
                left -= seg
                t = nxt
        return t - t_rel

    def to_dict(self) -> dict:
        return {"name": self.name, "windows": [dataclasses.asdict(w) for w in self.windows]}

    @classmethod
    def from_dict(cls, d: dict) -> "ContentionSchedule":
        return cls(d["name"], tuple(Window(**w) for w in d["windows"]))

    @classmethod
    def phases(cls, name: str, cores: Sequence[int], seed: int, n_hot: int = 3, burners: int = 2, t0: float = 0.2,
               phase_s: float = 1.0, n_phases: int = 2) -> "ContentionSchedule":
        """``n_phases`` consecutive phases of ``phase_s`` seconds; in each, ``n_hot`` cores (disjoint between phases, chosen by a
        seeded shuffle of ``cores``) are shared with ``burners`` spinners. A different seed = a different (held-out) schedule."""
        order = list(cores)
        random.Random(seed).shuffle(order)
        if n_hot * n_phases > len(order):
            raise ValueError(f"need {n_hot * n_phases} cores for {n_phases} disjoint phases, got {len(order)}")
        ws = [Window(order[p * n_hot + j], t0 + p * phase_s, t0 + (p + 1) * phase_s, burners)
              for p in range(n_phases) for j in range(n_hot)]
        return cls(name, tuple(sorted(ws, key=lambda w: (w.start_s, w.core))))


def _burner(core: int, conn, stop) -> None:
    import psutil

    try:
        psutil.Process().cpu_affinity([core])
    except Exception:  # noqa: BLE001 - unpinned burner: the schedule is then only approximate; the parent records ``pinned``
        pass
    conn.send("ready")
    while True:
        msg = conn.recv()
        if msg is None:
            return
        t0, windows = msg
        for s, e in windows:
            while clock.now() < t0 + s - 0.003 and not stop.is_set():
                time.sleep(0.001)
            while clock.now() < t0 + e and not stop.is_set():
                for _ in range(2000):
                    pass


class ContentionRunner:
    """Persistent burner processes. ``start(schedule)`` returns the ``clock.now()`` instant the schedule's time 0 corresponds to."""

    def __init__(self, cores: Sequence[int], max_burners_per_core: int = 2):
        self.cores = list(cores)
        self._ctx = mp.get_context("spawn")
        self._slots: list[tuple[int, Any, Any, None]] = []  # (core, process, connection, unused)
        self._stop = self._ctx.Event()
        for core in self.cores:
            for _ in range(max_burners_per_core):
                parent, child = self._ctx.Pipe()
                proc = self._ctx.Process(target=_burner, args=(core, child, self._stop), daemon=True)
                proc.start()
                self._slots.append((core, proc, parent, None))
        for _, _, conn, _ in self._slots:
            if conn.recv() != "ready":
                raise RuntimeError("burner did not start")

    def start(self, schedule: ContentionSchedule) -> float:
        self._stop.set()  # a still-running previous schedule ends before this one starts
        time.sleep(0.02)
        self._stop.clear()
        plan: list[list[tuple[float, float]]] = [[] for _ in self._slots]
        for w in schedule.windows:
            slots = [i for i, (c, *_rest) in enumerate(self._slots) if c == w.core]
            if w.burners > len(slots):
                raise ValueError(f"window needs {w.burners} burners on core {w.core}, runner has {len(slots)}")
            for i in slots[:w.burners]:
                plan[i].append((w.start_s, w.end_s))
        t0 = clock.now() + 0.002
        for (core, _p, conn, _s), wins in zip(self._slots, plan):
            if wins:
                conn.send((t0, sorted(wins)))
        return t0

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self._stop.set()
        for _core, proc, conn, _s in self._slots:
            try:
                conn.send(None)
            except Exception:  # noqa: BLE001
                pass
            proc.join(timeout=2)
            if proc.is_alive():
                proc.terminate()
        self._slots = []
