"""Decision-time resource-state snapshot for the revival policy.

``StateProvider.snapshot(state)`` is called ONCE per dispatch pass (from ``order_ready``, which the coordinator calls before every pass)
and returns an immutable ``StateSnapshot``; ``select_worker`` only reads it. Everything in it is known before the task being
scheduled is dispatched:

* worker and pool occupancy (from the runtime state);
* a per-worker multiplicative LOAD CORRECTION (1.0 = none) built from two signals, each optional:
    - recent runtime residuals: after a task completes, actual kernel time / predicted time. A pool-level, class-aware ratio absorbs
      the model's bias (``bias``); the worker's own ratio relative to that, from tasks long enough to be affected by a shared core
      (``min_task_s``), is the worker's slowdown. It decays towards 1.0 with ``tau_s`` so stale information fades;
    - foreign load of an idle worker's logical core (per-core utilisation from ``psutil.cpu_percent(percpu=True)``, minus the worker's
      own busy share), used while no fresh residual exists. Needs the worker->core map (``core_of``); marked unavailable otherwise;
* host free RAM (``psutil``), and GPU busy fraction / free VRAM through an injected ``gpu_fn`` (NVML is not installed on the
  development machine: the signal is then reported as unavailable, never guessed).

Missing signals are listed in ``StateSnapshot.unavailable``. No signal reads the actual runtime of the task being scheduled; residuals
come only from tasks that completed earlier (``observe``).
"""
from __future__ import annotations

import dataclasses
import math
import types
from typing import Callable, Mapping


@dataclasses.dataclass(frozen=True)
class GpuTelemetry:
    busy_fraction: float | None
    free_vram_bytes: int | None


@dataclasses.dataclass(frozen=True)
class StateSnapshot:
    t: float
    idle: tuple[str, ...]
    n_busy: int
    slowdown: Mapping[str, float]            # worker -> load correction (>= 1.0); workers not listed: 1.0
    slowdown_source: Mapping[str, str]       # worker -> "residual" | "foreign_load"
    foreign_load: Mapping[str, float]        # idle workers with a reading
    host_free_ram_bytes: int | None
    gpu: GpuTelemetry | None
    unavailable: tuple[str, ...]

    def slowdown_of(self, worker_id: str) -> float:
        return self.slowdown.get(worker_id, 1.0)

    def to_log(self) -> dict:
        """Compact JSON form: only what deviates from 'nothing known'."""
        d: dict = {"t": round(self.t, 4), "n_idle": len(self.idle), "n_busy": self.n_busy}
        if self.slowdown:
            d["slowdown"] = {w: round(v, 3) for w, v in self.slowdown.items()}
            d["slowdown_src"] = dict(self.slowdown_source)
        if self.host_free_ram_bytes is not None:
            d["free_ram_mb"] = self.host_free_ram_bytes >> 20
        if self.gpu is not None:
            d["gpu"] = dataclasses.asdict(self.gpu)
        if self.unavailable:
            d["unavailable"] = list(self.unavailable)
        return d


def _bucket(seconds: float) -> int:
    """Log2 bucket of a predicted time in milliseconds: the 'class' a residual correction is keyed by."""
    return int(math.floor(math.log2(max(seconds, 1e-6) * 1000.0)))


class StateProvider:
    def __init__(self, *, core_of: Mapping[str, int] | None = None, cpu_fn: Callable[[], list[float]] | None = None,
                 ram_fn: Callable[[], int] | None = None, gpu_fn: Callable[[], GpuTelemetry | None] | None = None,
                 use_residual: bool = True, use_foreign: bool = True, foreign_k: float = 0.8, foreign_threshold: float = 0.7,
                 fresh_s: float = 0.6, tau_s: float = 1.0, alpha_worker: float = 0.5, alpha_bias: float = 0.3,
                 min_task_s: float = 0.02, sample_min_s: float = 0.05, ram_every_s: float = 0.25,
                 clamp: tuple[float, float] = (1.0, 6.0)):
        self.core_of = dict(core_of) if core_of else None
        self.cpu_fn = cpu_fn
        self.ram_fn = ram_fn
        self.gpu_fn = gpu_fn
        self.use_residual, self.use_foreign = use_residual, use_foreign
        self.foreign_k, self.foreign_threshold = foreign_k, foreign_threshold
        self.fresh_s, self.tau_s = fresh_s, tau_s
        self.alpha_worker, self.alpha_bias = alpha_worker, alpha_bias
        self.min_task_s, self.sample_min_s, self.ram_every_s = min_task_s, sample_min_s, ram_every_s
        self.clamp = clamp
        self.reset()

    def reset(self) -> None:
        self._bias: dict[tuple[str, str, int], float] = {}      # (workload, pool, predicted-time bucket) -> actual/predicted
        self._worker: dict[str, tuple[float, float]] = {}       # worker -> (log slowdown, time of last update)
        self._foreign: dict[str, float] = {}
        self._last_sample = -1e9
        self._last_ram: tuple[float, int | None] = (-1e9, None)
        self._pending_cpu = False

    # --- feedback (completed tasks only) ---------------------------------------------------------------------------------

    def bias_of(self, workload: str, pool: str, predicted_s: float) -> float:
        return self._bias.get((workload, pool, _bucket(predicted_s)), 1.0) if self.use_residual else 1.0

    def observe(self, workload: str, worker_id: str, pool: str, predicted_s: float, actual_s: float, now: float) -> None:
        if not self.use_residual or predicted_s <= 0 or actual_s <= 0:
            return
        r = actual_s / predicted_s
        key = (workload, pool, _bucket(predicted_s))
        old = self._bias.get(key)
        # the bias EMA is updated from the observation made BEFORE this one is folded in, so a contended worker cannot hide itself
        rel = r / old if old else 1.0
        self._bias[key] = r if old is None else old * math.exp(self.alpha_bias * math.log(r / old))
        if actual_s >= self.min_task_s:
            lo, hi = self.clamp
            x = math.log(min(max(rel, lo), hi))
            prev = self._worker.get(worker_id)
            lc = x if prev is None else self.alpha_worker * x + (1 - self.alpha_worker) * prev[0]
            self._worker[worker_id] = (lc, now)

    # --- snapshot ----------------------------------------------------------------------------------------------------------

    def _own_busy(self, state, wid: str, lo: float, now: float) -> float:
        w = state.workers[wid]
        busy = 0.0
        for t0, t1 in reversed(w.history):
            if t1 <= lo:
                break
            busy += max(0.0, min(t1, now) - max(t0, lo))
        if w.busy and w.current_submitted_at is not None:
            busy += max(0.0, now - max(w.current_submitted_at, lo))
        return min(1.0, busy / max(now - lo, 1e-9))

    def _sample_foreign(self, state, now: float, idle: tuple[str, ...]) -> None:
        window = now - self._last_sample
        if self._last_sample > 0 and window < self.sample_min_s:
            return
        assert self.cpu_fn is not None  # callers check
        util = self.cpu_fn()
        if self._last_sample > 0:
            for wid in idle:
                core = self.core_of.get(wid) if self.core_of else None
                if core is None or core >= len(util):
                    continue
                own = self._own_busy(state, wid, self._last_sample, now)
                if own < 0.5:
                    f = min(1.0, max(0.0, (util[core] / 100.0 - own) / (1.0 - own)))
                    self._foreign[wid] = 0.5 * f + 0.5 * self._foreign.get(wid, f)
        self._last_sample = now

    def snapshot(self, state) -> StateSnapshot:
        now = state.now()
        idle = tuple(state.idle_workers())
        unavailable: list[str] = []
        if self.use_foreign and self.cpu_fn is not None and self.core_of:
            self._sample_foreign(state, now, idle)
        elif self.use_foreign:
            unavailable.append("foreign_load")
        slow: dict[str, float] = {}
        src: dict[str, str] = {}
        if self.use_residual or self.use_foreign:
            for wid in idle:
                prev = self._worker.get(wid) if self.use_residual else None
                age = now - prev[1] if prev else None
                if prev is not None and age is not None and age <= self.fresh_s:
                    c, s = math.exp(prev[0]), "residual"
                else:
                    c, s = 1.0, ""
                    f = self._foreign.get(wid) if self.use_foreign else None
                    if f is not None and f >= self.foreign_threshold:
                        c, s = 1.0 + self.foreign_k * f, "foreign_load"
                    elif prev is not None and age is not None:
                        c = math.exp(prev[0] * math.exp(-(age - self.fresh_s) / self.tau_s))
                        s = "residual" if c > 1.001 else ""
                if c > 1.001:
                    slow[wid], src[wid] = c, s
        ram = None
        if self.ram_fn is not None:
            if now - self._last_ram[0] >= self.ram_every_s:
                self._last_ram = (now, self.ram_fn())
            ram = self._last_ram[1]
        else:
            unavailable.append("host_ram")
        gpu = self.gpu_fn() if self.gpu_fn is not None else None
        if self.gpu_fn is None:
            unavailable.append("gpu_telemetry")
        return StateSnapshot(now, idle, sum(1 for w in state.workers.values() if w.busy), types.MappingProxyType(slow),
                             types.MappingProxyType(src), types.MappingProxyType(dict(self._foreign)), ram, gpu, tuple(unavailable))


def default_cpu_fn() -> Callable[[], list[float]]:
    import psutil

    psutil.cpu_percent(percpu=True)
    return lambda: psutil.cpu_percent(percpu=True)


def default_ram_fn() -> Callable[[], int]:
    import psutil

    return lambda: int(psutil.virtual_memory().available)


def nvml_gpu_fn() -> Callable[[], GpuTelemetry | None] | None:
    """GPU busy fraction and free VRAM through NVML if ``pynvml`` is installed and a device answers; None otherwise (never guessed)."""
    try:
        import pynvml  # type: ignore[import-not-found]

        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
    except Exception:  # noqa: BLE001 - optional telemetry
        return None

    def read() -> GpuTelemetry | None:
        try:
            u, m = pynvml.nvmlDeviceGetUtilizationRates(h), pynvml.nvmlDeviceGetMemoryInfo(h)
            return GpuTelemetry(u.gpu / 100.0, int(m.free))
        except Exception:  # noqa: BLE001
            return None

    return read

