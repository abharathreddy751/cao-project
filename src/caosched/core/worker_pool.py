"""Persistent, affinity-pinned P-core / E-core worker pools.

Unlike Phase 0's benchmark harness (which spawns one process per measurement
for maximum isolation), the runtime uses long-lived worker processes -- one
per configured core slot -- that receive tasks over a queue and run until
told to stop. This avoids per-task process-spawn overhead, which matters once
the coordinator is dispatching many small tasks.

Startup handshake: each worker (1) sets its CPU affinity, (2) *reads it back*
and reports requested vs. actual, and (3) optionally runs a warmup pass over
every workload so the one-time numpy/Pillow import cost (observed at ~2s in
the first Phase 1 validation run) is paid -- and measured -- before any timed
task. The pool blocks until every worker has reported in. A worker whose
affinity readback does not match is either rejected (``strict_affinity``) or
recorded as such; it is never silently treated as pinned.

``pin_single_thread()`` is called at module import time, same rationale as
Phase 0's benchmark worker: with the ``spawn`` start method a fresh
interpreter re-imports this module before invoking ``_worker_loop``, so the
BLAS thread-count env vars are set before any task imports numpy.

Output-queue messages are tagged tuples: ``("ready", WorkerReady)`` or
``("result", TaskResult)``.
"""
from __future__ import annotations

import dataclasses
import multiprocessing as mp
import os
import queue
import time
import traceback

from caosched.core.task import TaskMessage, TaskResult
from caosched.util import clock
from caosched.util.threadpin import pin_single_thread

pin_single_thread()

# Tiny per-workload sizes used only to trigger imports / first-call costs.
_WARMUP_SIZES = {"matmul": 16, "image_filter": 16, "compression": 1024}


@dataclasses.dataclass(frozen=True)
class WorkerReady:
    worker_id: str
    pid: int
    requested_affinity: tuple[int, ...]
    actual_affinity: tuple[int, ...] | None
    affinity_error: str | None
    warmup_seconds: float | None
    warmup_error: str | None
    capabilities: dict | None = None  # remote nodes: platform / devices / supported stages

    @property
    def affinity_ok(self) -> bool:
        if not self.requested_affinity:
            return True
        return self.actual_affinity is not None and set(self.actual_affinity) == set(self.requested_affinity)


def _worker_loop(worker_id: str, affinity: list[int], warmup: bool, input_queue, output_queue) -> None:
    import psutil

    from caosched.phase0.benchmarks.workloads import WORKLOADS

    proc = psutil.Process()
    affinity_error = None
    if affinity:
        try:
            proc.cpu_affinity(affinity)
        except Exception as exc:  # noqa: BLE001 - reported in handshake, not swallowed
            affinity_error = f"{type(exc).__name__}: {exc}"
    try:
        actual = tuple(proc.cpu_affinity())
    except Exception as exc:  # noqa: BLE001
        actual = None
        affinity_error = affinity_error or f"readback failed: {type(exc).__name__}: {exc}"

    warmup_seconds = warmup_error = None
    if warmup:
        start = time.perf_counter()
        try:
            for name, workload in WORKLOADS.items():
                workload.run(workload.prepare(_WARMUP_SIZES.get(name, 16), 0))
            warmup_seconds = time.perf_counter() - start
        except Exception:  # noqa: BLE001
            warmup_error = traceback.format_exc()

    output_queue.put(("ready", WorkerReady(
        worker_id, os.getpid(), tuple(affinity), actual, affinity_error, warmup_seconds, warmup_error,
    )))

    while True:
        message = input_queue.get()
        if message is None:
            break
        t_started = clock.now()
        error = None
        wall_time = None
        out_bytes = io_s = None
        try:
            if message.params is not None:  # application stage: real data in / out
                from caosched.apps.artifacts import read_artifacts, write_artifact
                from caosched.apps.stages import run_stage

                t_io = time.perf_counter()
                blobs = read_artifacts(message.input_refs)
                t_read = time.perf_counter() - t_io
                blob, wall_time, codec = run_stage(message.workload, blobs, message.params)
                t_w = time.perf_counter()
                write_artifact(message.output_ref, blob)
                io_s = t_read + codec + (time.perf_counter() - t_w)
                out_bytes = len(blob)
            else:  # benchmark kernel (unchanged path)
                workload = WORKLOADS[message.workload]
                inputs = workload.prepare(message.size, message.seed)
                start = time.perf_counter()
                workload.run(inputs)
                wall_time = time.perf_counter() - start
        except Exception:  # noqa: BLE001 - report to coordinator, never crash silently
            error = traceback.format_exc()
        t_completed = clock.now()
        output_queue.put(("result", TaskResult(message.task_id, worker_id, wall_time, error, t_started, t_completed,
                                               output_bytes=out_bytes, io_s=io_s)))


class WorkerPoolError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class RemoteSlot:
    """One remote worker (Phase 5). ``node_core`` set -> a local node process
    is spawned on that logical processor behind the link shim; ``port`` set
    instead -> connect to an already-running node at host:port (e.g. a
    physical device). ``proxy_core``: where the lightweight proxy runs."""
    link: object                      # caosched.remote.link.LinkConfig
    node_core: int | None = None
    proxy_core: int | None = None
    host: str = "127.0.0.1"
    port: int | None = None
    pool: str = "R"                   # pool label, e.g. "R_PI" / "R_T4" for distinct devices
    same_clock: bool | None = None    # None -> True iff the node is spawned on this machine


@dataclasses.dataclass
class WorkerHandle:
    worker_id: str
    pool: str  # "P" or "E"
    affinity: list[int]
    process: object
    input_queue: object
    ready_info: WorkerReady | None = None
    current_task: str | None = None

    @property
    def busy(self) -> bool:
        return self.current_task is not None


class WorkerPool:
    """Manages persistent worker processes across the P-core and E-core
    pools. Worker-to-core assignment comes from the caller (normally
    ``RuntimeConfig.from_topology()``), never hardcoded here.
    """

    def __init__(
        self,
        p_core_slots: list[int],
        e_core_slots: list[int],
        *,
        warmup: bool = True,
        strict_affinity: bool = False,
        startup_timeout: float = 120.0,
        remote_slots: list[RemoteSlot] | None = None,
    ):
        self.ctx = mp.get_context("spawn")
        self.output_queue = self.ctx.Queue()
        self.workers: dict[str, WorkerHandle] = {}
        self._closed = False
        self._node_processes: list = []
        # worker_id -> recent (t_started, t_completed) busy intervals, kept
        # across runs (see RuntimeState activity history).
        self.activity: dict = {}

        try:
            for i, core in enumerate(p_core_slots):
                self._spawn_worker(f"P{i}", "P", [core], warmup)
            for i, core in enumerate(e_core_slots):
                self._spawn_worker(f"E{i}", "E", [core], warmup)
            counters: dict[str, int] = {}
            for slot in remote_slots or []:
                k = counters.get(slot.pool, 0)
                counters[slot.pool] = k + 1
                self._spawn_remote(f"{slot.pool}{k}", slot, startup_timeout)
            self._await_ready(startup_timeout)
            if strict_affinity:
                bad = {wid: w.ready_info for wid, w in self.workers.items() if not w.ready_info.affinity_ok}
                if bad:
                    raise WorkerPoolError(f"Affinity readback mismatch: {bad}")
        except BaseException:
            self.shutdown()
            raise

    def _spawn_remote(self, worker_id: str, slot: RemoteSlot, timeout: float) -> None:
        from caosched.remote.node import serve
        from caosched.remote.proxy import proxy_loop

        port = slot.port
        if slot.node_core is not None:
            port_q = self.ctx.Queue()
            node = self.ctx.Process(target=serve, args=(slot.host, 0, [slot.node_core], port_q),
                                    name=f"caosched-node-{worker_id}", daemon=True)
            node.start()
            self._node_processes.append(node)
            try:
                port = port_q.get(timeout=timeout)
            except queue.Empty:
                raise WorkerPoolError(f"Remote node for {worker_id} did not start within {timeout}s") from None
        if port is None:
            raise WorkerPoolError(f"{worker_id}: RemoteSlot needs node_core or port")
        input_queue = self.ctx.Queue()
        same_clock = slot.same_clock if slot.same_clock is not None else slot.node_core is not None
        proxy = self.ctx.Process(
            target=proxy_loop,
            args=(worker_id, slot.host, port, slot.link, [slot.proxy_core] if slot.proxy_core is not None else [],
                  input_queue, self.output_queue, 60.0, same_clock),
            name=f"caosched-proxy-{worker_id}", daemon=True)
        proxy.start()
        affinity = [slot.node_core] if slot.node_core is not None else []
        self.workers[worker_id] = WorkerHandle(worker_id, slot.pool, affinity, proxy, input_queue)

    @classmethod
    def from_config(cls, config, **kwargs) -> "WorkerPool":
        return cls(list(config.p_core_slots), list(config.e_core_slots), **kwargs)

    def _spawn_worker(self, worker_id: str, pool: str, affinity: list[int], warmup: bool) -> None:
        input_queue = self.ctx.Queue()
        process = self.ctx.Process(
            target=_worker_loop, args=(worker_id, affinity, warmup, input_queue, self.output_queue),
            name=f"caosched-worker-{worker_id}", daemon=True,
        )
        process.start()
        self.workers[worker_id] = WorkerHandle(worker_id, pool, affinity, process, input_queue)

    def _await_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while any(w.ready_info is None for w in self.workers.values()):
            dead = self.dead_workers()
            if dead:
                raise WorkerPoolError(f"Worker(s) died during startup: {dead}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                missing = [wid for wid, w in self.workers.items() if w.ready_info is None]
                raise WorkerPoolError(f"Workers did not report ready within {timeout}s: {missing}")
            try:
                kind, payload = self.output_queue.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if kind != "ready":
                raise WorkerPoolError(f"Unexpected {kind!r} message during startup")
            self.workers[payload.worker_id].ready_info = payload

    # --- introspection -------------------------------------------------

    def pool_of(self, worker_id: str) -> str:
        return self.workers[worker_id].pool

    def worker_ids(self, pool: str | None = None) -> list[str]:
        return [wid for wid, w in self.workers.items() if pool is None or w.pool == pool]

    def idle_workers(self, pool: str | None = None) -> list[str]:
        return [wid for wid, w in self.workers.items() if not w.busy and (pool is None or w.pool == pool)]

    def is_idle(self, worker_id: str) -> bool:
        w = self.workers.get(worker_id)
        return w is not None and not w.busy

    def dead_workers(self) -> list[str]:
        return [wid for wid, w in self.workers.items() if not w.process.is_alive()]

    def ready_infos(self) -> list[WorkerReady]:
        return [w.ready_info for w in self.workers.values() if w.ready_info is not None]

    # --- dispatch / completion -----------------------------------------

    def set_link(self, worker_id: str, link) -> None:
        """Switch a remote worker's link shim (Phase 6B: link conditions are
        interleaved run by run on one pool). Only between tasks: the proxy
        applies it before the next task message, in queue order."""
        w = self.workers.get(worker_id)
        if w is None or not w.pool.startswith("R"):
            raise WorkerPoolError(f"{worker_id!r} is not a remote worker")
        if w.busy:
            raise WorkerPoolError(f"Cannot change the link of busy worker {worker_id!r}")
        w.input_queue.put(link)

    def submit(self, worker_id: str, message: TaskMessage) -> None:
        if worker_id not in self.workers:
            raise WorkerPoolError(f"Unknown worker {worker_id!r}")
        w = self.workers[worker_id]
        if w.busy:
            raise WorkerPoolError(f"Worker {worker_id!r} is busy with {w.current_task!r}")
        w.current_task = message.task_id
        w.input_queue.put(message)

    def poll_result(self, timeout: float | None = None) -> TaskResult | None:
        """Block up to ``timeout`` seconds for one task result; None on timeout.
        Validates that the result matches what that worker was actually given."""
        try:
            kind, payload = self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None
        if kind != "result":
            raise WorkerPoolError(f"Unexpected {kind!r} message after startup")
        w = self.workers.get(payload.worker_id)
        if w is None:
            raise WorkerPoolError(f"Result from unknown worker {payload.worker_id!r}")
        if w.current_task != payload.task_id:
            raise WorkerPoolError(
                f"Worker {payload.worker_id!r} returned {payload.task_id!r} but was assigned {w.current_task!r}"
            )
        w.current_task = None
        return payload

    # --- lifecycle ------------------------------------------------------

    def shutdown(self, timeout: float = 10.0) -> None:
        if self._closed:
            return
        self._closed = True
        for w in self.workers.values():
            if w.process.is_alive():
                try:
                    w.input_queue.put(None)
                except Exception:  # noqa: BLE001 - best-effort during teardown
                    pass
        for w in self.workers.values():
            w.process.join(timeout=timeout)
            if w.process.is_alive():
                w.process.terminate()
                w.process.join(timeout=timeout)
        for node in self._node_processes:
            node.join(timeout=timeout)
            if node.is_alive():
                node.terminate()
                node.join(timeout=timeout)

    def __enter__(self) -> "WorkerPool":
        return self

    def __exit__(self, *exc_info) -> None:
        self.shutdown()
