"""Profiling-only helpers for the CPU/GPU opportunity audit (docs/revival/PROTOCOL_gpu_cpu_profile.md). Nothing here is imported by a scheduler.

* ``NvidiaSmiMonitor``  low-frequency GPU telemetry through ``nvidia-smi`` (NVML is not installed); unavailable fields are None with a reason.
* ``GpuBurner``         a spawned process that keeps the GPU busy; ready / pause / stop events, a hard timeout, guaranteed cleanup.
* ``summarize``         summary rows recomputed from raw sample records (the only place that defines the statistics).
* ``dispatch_choices``  eligible-idle-worker counts reconstructed from an event log.
* ``lp_lower_bound``    fluid makespan lower bound over measured per-(stage, pool) costs (an ESTIMATE, not a schedule).

Importing this module must not import torch (the burner target imports it inside the child).
"""
from __future__ import annotations

import atexit
import dataclasses
import hashlib
import json
import multiprocessing as mp
import random
import statistics
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from caosched.util import clock

SCHEMA = "gpuprofile/1"
SMI_FIELDS = ("utilization.gpu", "memory.used", "memory.total", "power.draw", "temperature.gpu", "clocks.sm")
SMI_KEYS = ("gpu_util_pct", "mem_used_mib", "mem_total_mib", "power_w", "temp_c", "sm_clock_mhz")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(directory: Path) -> list[str]:
    """Problems found when re-hashing every file listed in SHA256_MANIFEST.tsv (header: relpath, size, [mtime_ns,] sha256). Empty list = valid."""
    d = Path(directory)
    lines = (d / "SHA256_MANIFEST.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    problems = []
    for line in lines[1:]:
        cols = dict(zip(head, line.split("\t")))
        f = d / cols["relpath"]
        if not f.is_file():
            problems.append(f"missing {cols['relpath']}")
        elif sha256_file(f) != cols["sha256"]:
            problems.append(f"hash mismatch {cols['relpath']}")
    return problems


# --- telemetry ------------------------------------------------------------------------------------------------------------------

def parse_smi_line(line: str) -> dict[str, float | None]:
    """One CSV line of ``nvidia-smi --format=csv,noheader,nounits``; '[N/A]' or an unparsable field becomes None."""
    parts = [p.strip() for p in line.strip().split(",")]
    out: dict[str, float | None] = {}
    for key, part in zip(SMI_KEYS, parts + [""] * len(SMI_KEYS)):
        try:
            out[key] = float(part)
        except ValueError:
            out[key] = None
    return out


def smi_sample(run: Callable[..., Any] = subprocess.run, timeout_s: float = 5.0) -> dict:
    """One telemetry sample: ``{"t": clock.now(), "available": bool, "reason": str | None, <fields or None>, "call_s": float}``."""
    t0 = clock.now()
    try:
        r = run(["nvidia-smi", f"--query-gpu={','.join(SMI_FIELDS)}", "--format=csv,noheader,nounits"], capture_output=True, text=True,
                timeout=timeout_s)
    except FileNotFoundError:
        return {"t": t0, "available": False, "reason": "nvidia-smi not found", **{k: None for k in SMI_KEYS}, "call_s": clock.now() - t0}
    except Exception as exc:  # noqa: BLE001 - timeout or OS error: reported, not raised
        return {"t": t0, "available": False, "reason": f"{type(exc).__name__}: {exc}", **{k: None for k in SMI_KEYS}, "call_s": clock.now() - t0}
    if r.returncode != 0 or not r.stdout.strip():
        return {"t": t0, "available": False, "reason": f"nvidia-smi exit {r.returncode}: {(r.stderr or '').strip()[:120]}",
                **{k: None for k in SMI_KEYS}, "call_s": clock.now() - t0}
    vals = parse_smi_line(r.stdout.strip().splitlines()[0])
    return {"t": t0, "available": any(v is not None for v in vals.values()), "reason": None, **vals, "call_s": clock.now() - t0}


class NvidiaSmiMonitor:
    """Samples ``smi_sample`` every ``interval_s`` in a daemon thread and appends each sample to ``out_path`` (JSON lines).
    Never called from a task path; ``latest()`` returns the newest sample without touching ``nvidia-smi``."""

    def __init__(self, interval_s: float = 0.5, out_path: Path | None = None, sample_fn: Callable[[], dict] = smi_sample):
        self.interval_s, self.out_path, self.sample_fn = interval_s, out_path, sample_fn
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "NvidiaSmiMonitor":
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="nvidia-smi-monitor")
        self._thread.start()
        return self

    def _loop(self) -> None:
        fh = Path(self.out_path).open("a", encoding="utf-8") if self.out_path else None
        try:
            while not self._stop.is_set():
                s = self.sample_fn()
                self.samples.append(s)
                if fh:
                    fh.write(json.dumps(s) + "\n")
                    fh.flush()
                self._stop.wait(self.interval_s)
        finally:
            if fh:
                fh.close()

    def latest(self) -> dict | None:
        return self.samples[-1] if self.samples else None

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def __enter__(self) -> "NvidiaSmiMonitor":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


# --- GPU contention -------------------------------------------------------------------------------------------------------------

def _burner_main(ready, stop, run, cpu: int | None, max_s: float, size: int) -> None:
    """Child process: continuous matrix products on the GPU while ``run`` is set; exits on ``stop`` or after ``max_s`` seconds."""
    try:
        import psutil

        if cpu is not None:
            psutil.Process().cpu_affinity([cpu])
    except Exception:  # noqa: BLE001 - unpinned burner is reported by the parent through the telemetry, not fatal
        pass
    import torch

    a = torch.randn(size, size, device="cuda")
    b = torch.randn(size, size, device="cuda")
    torch.cuda.synchronize()
    ready.set()
    t_end = time.monotonic() + max_s
    while not stop.is_set() and time.monotonic() < t_end:
        if not run.is_set():
            time.sleep(0.005)
            continue
        for _ in range(8):
            a = (a @ b).clamp_(-1, 1)
        torch.cuda.synchronize()


def _dummy_burner(ready, stop, run, cpu, max_s, size) -> None:  # noqa: ARG001 - CPU-only stand-in with the same protocol (tests)
    ready.set()
    t_end = time.monotonic() + max_s
    while not stop.is_set() and time.monotonic() < t_end:
        time.sleep(0.005)


def _never_ready_burner(ready, stop, run, cpu, max_s, size) -> None:  # noqa: ARG001 - test stand-in: never signals ready
    time.sleep(max_s)


class GpuBurner:
    """Spawned GPU load. ``with GpuBurner(...) as b: b.resume(); ...; b.pause()``. The child is spawned with the ``spawn`` context and a module-level
    target, so an unguarded caller script cannot recurse (the child imports this module, not the caller's ``__main__`` code). ``max_s`` bounds its
    lifetime even if the parent dies; ``close`` joins, then terminates, then kills; ``atexit`` calls ``close`` too."""

    def __init__(self, cpu: int | None = None, max_s: float = 3600.0, size: int = 4096, ready_timeout_s: float = 60.0,
                 target: Callable[..., None] = _burner_main):
        ctx = mp.get_context("spawn")
        self._stop, self._ready, self._run = ctx.Event(), ctx.Event(), ctx.Event()
        self._proc = ctx.Process(target=target, args=(self._ready, self._stop, self._run, cpu, max_s, size), daemon=True,
                                 name="caosched-gpu-burner")
        self.ready_timeout_s = ready_timeout_s
        self._closed = False
        atexit.register(self.close)

    def start(self) -> "GpuBurner":
        self._proc.start()
        if not self._ready.wait(self.ready_timeout_s):
            self.close()
            raise TimeoutError(f"GPU burner not ready after {self.ready_timeout_s}s")
        return self

    def resume(self) -> None:
        self._run.set()

    def pause(self) -> None:
        self._run.clear()

    def alive(self) -> bool:
        return self._proc.is_alive()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        self._run.clear()
        if self._proc.pid is not None:
            self._proc.join(timeout=5)
            if self._proc.is_alive():
                self._proc.terminate()
                self._proc.join(timeout=5)
            if self._proc.is_alive():
                self._proc.kill()
                self._proc.join(timeout=5)

    def __enter__(self) -> "GpuBurner":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()


# --- statistics -----------------------------------------------------------------------------------------------------------------

def bootstrap_median_ci(x: Sequence[float], seed: int = 0, n: int = 2000) -> tuple[float, float]:
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    meds = sorted(statistics.median(rng.choices(x, k=len(x))) for _ in range(n))
    return meds[int(0.025 * n)], meds[int(0.975 * n) - 1]


def bootstrap_median_diff_ci(a: Sequence[float], b: Sequence[float], seed: int = 0, n: int = 2000) -> tuple[float, float]:
    """95% interval of median(a) - median(b) for independent samples."""
    if len(a) < 2 or len(b) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    d = sorted(statistics.median(rng.choices(a, k=len(a))) - statistics.median(rng.choices(b, k=len(b))) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n) - 1]


METRICS = ("occupation_s", "kernel_s", "io_s", "ipc_in_s", "ipc_out_s", "worker_other_s", "worker_span_s")


def valid_rows(rows: Iterable[dict]) -> list[dict]:
    """Rule fixed before the sweep: a sample counts iff it is not warm-up, returned without error and passed verification."""
    return [r for r in rows if r.get("phase") in ("quiet", "contended") and not r.get("warmup") and r.get("valid")]


def summarize(rows: Iterable[dict]) -> list[dict]:
    """One row per (case, side, device, gpu_load): n, failed, median and IQR and bootstrap interval of every time component."""
    rows = list(rows)
    groups: dict[tuple, list[dict]] = {}
    allg: dict[tuple, list[dict]] = {}
    for r in rows:
        if r.get("phase") not in ("quiet", "contended") or r.get("warmup"):
            continue
        k = (r["case"], r["side"], r["device"], r["gpu_load"])
        allg.setdefault(k, []).append(r)
        if r.get("valid"):
            groups.setdefault(k, []).append(r)
    out = []
    for k in sorted(allg):
        g = groups.get(k, [])
        row: dict = {"case": k[0], "side": k[1], "device": k[2], "gpu_load": k[3], "n_valid": len(g), "n_failed": len(allg[k]) - len(g)}
        for m in METRICS:
            xs = [x[m] for x in g if x.get(m) is not None]
            if len(xs) >= 2:
                q = statistics.quantiles(xs, n=4)
                lo, hi = bootstrap_median_ci(xs)
                row.update({f"{m}_median": statistics.median(xs), f"{m}_q1": q[0], f"{m}_q3": q[2], f"{m}_ci_lo": lo, f"{m}_ci_hi": hi,
                            f"{m}_mean": statistics.fmean(xs), f"{m}_sd": statistics.stdev(xs)})
            else:
                row.update({f"{m}_median": None})
        out.append(row)
    return out


def best_device(summary: Sequence[dict], rows: Sequence[dict]) -> list[dict]:
    """Per (case, side) and gpu_load: the device with the lowest median occupation, the runner-up and whether their bootstrap intervals of the
    median difference exclude 0; plus whether the best device FLIPS between quiet and contended."""
    by: dict[tuple, dict[str, list[float]]] = {}
    for r in valid_rows(rows):
        by.setdefault((r["case"], r["side"], r["gpu_load"]), {}).setdefault(r["device"], []).append(r["occupation_s"])
    res: dict[tuple, dict] = {}
    for (case, side, load), devs in by.items():
        meds = {d: statistics.median(v) for d, v in devs.items() if len(v) >= 2}
        if len(meds) < 2:
            continue
        order = sorted(meds, key=meds.__getitem__)
        lo, hi = bootstrap_median_diff_ci(devs[order[0]], devs[order[1]])
        res[(case, side, load)] = {"best": order[0], "second": order[1], "best_s": meds[order[0]], "second_s": meds[order[1]],
                                   "separated": bool(hi < 0), "diff_ci": (lo, hi)}
    out = []
    for (case, side) in sorted({(k[0], k[1]) for k in res}):
        q, c = res.get((case, side, "quiet")), res.get((case, side, "contended"))
        if q is None or c is None:
            continue
        out.append({"case": case, "side": side, "best_quiet": q["best"], "best_contended": c["best"], "quiet_separated": q["separated"],
                    "contended_separated": c["separated"], "flip": q["best"] != c["best"], "flip_firm": q["best"] != c["best"] and (q["separated"] or c["separated"]),
                    "best_quiet_s": q["best_s"], "best_contended_s": c["best_s"]})
    return out


# --- opportunity audit ---------------------------------------------------------------------------------------------------------

def dispatch_choices(events: Sequence[dict]) -> dict:
    """Eligible idle workers at every dispatch of one run, reconstructed from its event log. A worker is busy from its task's ``task_dispatched``
    event to the matching ``task_completed`` event (late binding: submitted at dispatch). The count includes the chosen worker."""
    pool_of: dict[str, str] = {}
    elig: dict[str, list[str] | None] = {}
    for e in events:
        if e["event"] == "run_started":
            elig = {tid: spec.get("eligible_pools") for tid, spec in e["tasks"].items()}
        elif e["event"] == "worker_ready":
            pool_of[e["worker_id"]] = e["pool"]
    busy: set[str] = set()
    n = {"dispatches": 0, "one": 0, "multi": 0, "g_and_cpu": 0, "waited": 0}
    for e in events:
        if e["event"] == "task_dispatched":
            pools = elig.get(e["task_id"])
            idle = [w for w, p in pool_of.items() if w not in busy and (pools is None or p in pools)]
            n["dispatches"] += 1
            n["one" if len(idle) <= 1 else "multi"] += 1
            kinds = {pool_of[w] == "G" for w in idle}
            if len(idle) >= 2 and kinds == {True, False}:
                n["g_and_cpu"] += 1
            if (e.get("queue_wait_seconds") or 0.0) > 0.0005:
                n["waited"] += 1
            busy.add(e["worker_id"])
        elif e["event"] in ("task_completed", "task_failed"):
            busy.discard(e.get("worker_id"))
    return n


def lp_lower_bound(count: dict[str, int], cost: dict[tuple[str, str], float], capacity: dict[str, int]) -> dict:
    """min T s.t. each stage's tasks are split over the pools that can run it, sum over stages of count x share x cost <= T x workers(pool).
    ``cost[(stage, pool)]`` seconds of worker occupation; a missing (stage, pool) means the pool cannot run the stage. Ignores precedence,
    startup and the coordinator: a LOWER BOUND on the makespan of any schedule that respects those costs (an estimate, not a schedule)."""
    from scipy.optimize import linprog

    stages = sorted(count)
    pools = sorted(capacity)
    var = [(s, p) for s in stages for p in pools if (s, p) in cost]
    nv = len(var) + 1
    c = [0.0] * len(var) + [1.0]
    a_eq, b_eq = [], []
    for s in stages:
        a_eq.append([1.0 if v[0] == s else 0.0 for v in var] + [0.0])
        b_eq.append(1.0)
    a_ub, b_ub = [], []
    for p in pools:
        a_ub.append([count[v[0]] * cost[v] if v[1] == p else 0.0 for v in var] + [-float(capacity[p])])
        b_ub.append(0.0)
    r = linprog(c, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=[(0, None)] * nv, method="highs")
    if not r.success:
        raise ValueError(f"LP infeasible: {r.message}")
    share = {v: float(r.x[i]) for i, v in enumerate(var)}
    return {"T_s": float(r.x[-1]), "share": {f"{s}|{p}": x for (s, p), x in share.items() if x > 1e-9}}


def headroom(best_simple_s: float, lp_s: float, r: float = 1.0) -> float:
    """Percent by which the strongest simple baseline exceeds the (overhead-corrected) lower bound."""
    return (best_simple_s / (lp_s * r) - 1.0) * 100.0


@dataclasses.dataclass(frozen=True)
class ProfileConfig:
    blocks: int = 20
    seed: int = 20262601
    sides: tuple[int, ...] = (256, 512, 1024, 2048)
    interval_s: float = 0.5
    monitor: bool = True
    max_minutes: float = 90.0
    min_free_gb: float = 1.0
    max_cpu_pct: float = 20.0
    max_temp_c: float = 85.0

    def validate(self) -> None:
        if self.blocks < 3:
            raise ValueError("blocks must be >= 3 (block 0 is warm-up)")
        if any(s < 8 for s in self.sides) or not self.sides:
            raise ValueError("sides must be >= 8")
        if self.interval_s < 0.1:
            raise ValueError("monitor interval must be >= 0.1 s")


def block_order(items: Sequence[Any], seed: int, block: int, phase: str) -> list[Any]:
    """Deterministic shuffle of ``items`` for one (block, phase)."""
    out = list(items)
    random.Random(f"{seed}:{block}:{phase}").shuffle(out)
    return out



# --- list-scheduling simulation (an ESTIMATE; validated against stored measurements where they exist) ------------------------------

STAGE_ORDER = ("img_source", "img_denoise", "img_edges", "img_features")


def simulate_list_schedule(n_chains: int, cost: dict[tuple[str, str], float], eligible: dict[str, Sequence[str]], pools: dict[str, int],
                           policy: str, coord_s: float = 0.0) -> dict:
    """Deterministic discrete-event simulation of a work-conserving list scheduler on independent 4-stage chains.

    ``cost[(stage, device)]``: measured complete occupation of a worker (seconds); ``eligible[stage]``: devices in B4 priority order; ``policy``:
    ``greedy`` (B4: first idle worker of the first device in priority order that has one) or ``oracle`` (the idle eligible worker with the lowest
    cost; never waits for a busy faster worker, so it is as work-conserving as B4). The coordinator is serial: every dispatch starts ``coord_s``
    after the previous dispatch and after the event that enabled it. Returns the makespan and counts of dispatches with 1, >=2 and G-and-CPU
    eligible idle workers. Chain order is FIFO by readiness. Costs are medians (no noise), so only differences between policies are meaningful."""
    import heapq

    workers = [(d, i) for d, n in pools.items() for i in range(n)]
    free = {w: True for w in workers}
    ready: list[tuple[float, int, int]] = []          # (ready time, chain, stage index)
    for c in range(n_chains):
        heapq.heappush(ready, (0.0, c, 0))
    events: list[tuple[float, int, tuple, int, int]] = []   # (finish, tiebreak, worker, chain, stage)
    seq = 0
    coord_free = 0.0
    now = 0.0
    n = {"dispatches": 0, "one": 0, "multi": 0, "g_and_cpu": 0}
    makespan = 0.0

    def dispatch(t: float) -> None:
        nonlocal coord_free, seq, makespan
        while ready and ready[0][0] <= t + 1e-12:
            rt, c, si = ready[0]
            stage = STAGE_ORDER[si]
            devs = list(eligible[stage])
            idle = [w for w in workers if free[w] and w[0] in devs]
            if not idle:
                return
            heapq.heappop(ready)
            if policy == "greedy":
                w = min(idle, key=lambda w: (devs.index(w[0]), w[1]))
            else:
                w = min(idle, key=lambda w: (cost[(stage, w[0])], devs.index(w[0]), w[1]))
            n["dispatches"] += 1
            n["one" if len(idle) == 1 else "multi"] += 1
            if len(idle) >= 2 and {x[0] == "G" for x in idle} == {True, False}:
                n["g_and_cpu"] += 1
            start = max(t, coord_free) + coord_s
            coord_free = start
            free[w] = False
            fin = start + cost[(stage, w[0])]
            seq += 1
            heapq.heappush(events, (fin, seq, w, c, si))
            makespan = max(makespan, fin)

    dispatch(0.0)
    while events:
        fin, _s, w, c, si = heapq.heappop(events)
        now = fin
        free[w] = True
        if si + 1 < len(STAGE_ORDER):
            heapq.heappush(ready, (fin, c, si + 1))
        dispatch(now)
    return {"makespan_s": makespan, **n}


def fit_coord_s(target_s: float, run: Callable[[float], float], lo: float = 0.0, hi: float = 0.05) -> float:
    """Bisection for the serial coordinator cost per dispatch that makes ``run(coord_s)`` equal ``target_s`` (monotone in coord_s)."""
    if run(lo) >= target_s:
        return lo
    for _ in range(40):
        mid = (lo + hi) / 2
        if run(mid) < target_s:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
