"""Real-process tests for the worker pool: actual spawn, actual affinity
calls + readback, actual queues. Uses logical processors 0 and 1, which
exist on any machine able to run this suite."""
import os
import sys

import pytest

from caosched.core.runtime_config import RuntimeConfig
from caosched.core.task import TaskMessage
from caosched.core.worker_pool import WorkerPool, WorkerPoolError


@pytest.fixture(scope="module")
def pool():
    p = WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=True)
    yield p
    p.shutdown()


def test_handshake_reports_verified_affinity_and_measured_warmup(pool):
    infos = {i.worker_id: i for i in pool.ready_infos()}
    assert set(infos) == {"P0", "E0"}
    assert infos["P0"].actual_affinity == (0,) and infos["E0"].actual_affinity == (1,)
    assert all(i.affinity_ok and i.affinity_error is None for i in infos.values())
    assert all(i.warmup_error is None and i.warmup_seconds > 0 for i in infos.values())
    assert len({i.pid for i in infos.values()}) == 2 and os.getpid() not in {i.pid for i in infos.values()}


def test_pools_are_partitioned(pool):
    assert pool.worker_ids("P") == ["P0"] and pool.worker_ids("E") == ["E0"]
    assert pool.pool_of("P0") == "P"


def test_submit_and_poll_roundtrip_marks_busy_then_idle(pool):
    pool.submit("P0", TaskMessage("x", "matmul", 16, 0))
    assert not pool.is_idle("P0") and pool.idle_workers() == ["E0"]
    r = pool.poll_result(timeout=30)
    assert r.task_id == "x" and r.worker_id == "P0" and r.error is None
    assert r.wall_time_seconds > 0 and r.t_started <= r.t_completed
    assert pool.is_idle("P0")


def test_submit_to_busy_or_unknown_worker_rejected(pool):
    pool.submit("E0", TaskMessage("y", "matmul", 16, 0))
    with pytest.raises(WorkerPoolError):
        pool.submit("E0", TaskMessage("z", "matmul", 16, 0))
    with pytest.raises(WorkerPoolError):
        pool.submit("NOPE", TaskMessage("z", "matmul", 16, 0))
    assert pool.poll_result(timeout=30).task_id == "y"


def test_workload_exception_is_reported_not_crashing_worker(pool):
    pool.submit("P0", TaskMessage("bad", "no_such_workload", 16, 0))
    r = pool.poll_result(timeout=30)
    assert r.error and "KeyError" in r.error and r.wall_time_seconds is None
    assert not pool.dead_workers()


def test_poll_timeout_returns_none(pool):
    assert pool.poll_result(timeout=0.05) is None


def test_impossible_affinity_is_detected_not_silently_accepted():
    bogus = (os.cpu_count() or 1) + 64
    with WorkerPool(p_core_slots=[], e_core_slots=[bogus], warmup=False) as p:
        info = p.ready_infos()[0]
        assert not info.affinity_ok and info.affinity_error
    with pytest.raises(WorkerPoolError, match="Affinity readback mismatch"):
        WorkerPool(p_core_slots=[], e_core_slots=[bogus], warmup=False, strict_affinity=True)


def test_dead_worker_is_detectable():
    p = WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False)
    try:
        p.workers["E0"].process.terminate()
        p.workers["E0"].process.join(5)
        assert p.dead_workers() == ["E0"]
    finally:
        p.shutdown()


@pytest.mark.parametrize("kw", [
    dict(p_core_slots=(0,), e_core_slots=(0,)),
    dict(p_core_slots=(0,), e_core_slots=(1,), coordinator_core=1),
    dict(p_core_slots=(), e_core_slots=()),
])
def test_runtime_config_rejects_overlapping_or_empty_slots(kw):
    with pytest.raises(ValueError):
        RuntimeConfig(**kw)


@pytest.mark.skipif(sys.platform != "win32", reason="Phase 0 topology discovery is Windows-only")
def test_runtime_config_from_phase0_topology_is_consistent():
    cfg = RuntimeConfig.from_topology()
    assert cfg.p_core_slots and cfg.e_core_slots and cfg.coordinator_core is not None
    assert len(cfg.p_core_slots) + len(cfg.e_core_slots) + 1 <= (os.cpu_count() or 0)
