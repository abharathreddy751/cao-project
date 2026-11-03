import pytest

from caosched.core.dag import build_independent_dag
from caosched.core.runtime_state import RuntimeState


def test_bind_submit_finish_local_queue_fifo():
    s = RuntimeState(build_independent_dag(3), {"P0": "P", "E0": "E"})
    assert s.bind("t0", "P0") is True
    s.mark_submitted("P0", "t0", 1.0)
    assert not s.is_idle("P0") and s.idle_workers() == ["E0"]
    assert s.bind("t1", "P0") is False and s.bind("t2", "P0") is False
    assert s.workers["P0"].load == 3
    assert s.finish("P0", "t0") == "t1"
    s.mark_submitted("P0", "t1", 2.0)
    assert s.finish("P0", "t1") == "t2"


def test_finish_wrong_task_and_double_submit_rejected():
    s = RuntimeState(build_independent_dag(2), {"P0": "P"})
    s.mark_submitted("P0", "t0", 0.0)
    with pytest.raises(RuntimeError):
        s.mark_submitted("P0", "t1", 0.0)
    with pytest.raises(RuntimeError):
        s.finish("P0", "t1")
