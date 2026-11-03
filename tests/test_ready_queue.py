import pytest

from caosched.core.ready_queue import ReadyQueue


def test_fifo_order_and_removal_from_middle():
    q = ReadyQueue()
    for tid in ("a", "b", "c"):
        q.push(tid)
    assert q.ordered() == ["a", "b", "c"]
    q.remove("b")
    assert q.ordered() == ["a", "c"] and len(q) == 2 and "b" not in q


def test_duplicate_push_rejected():
    q = ReadyQueue()
    q.push("a")
    with pytest.raises(ValueError):
        q.push("a")


def test_remove_missing_raises_and_returns_enqueue_time():
    q = ReadyQueue()
    q.push("a", t=123.0)
    assert q.remove("a") == 123.0
    with pytest.raises(KeyError):
        q.remove("a")
    assert not q


def test_ordered_is_a_snapshot_safe_to_mutate_during_iteration():
    q = ReadyQueue()
    for tid in ("a", "b", "c"):
        q.push(tid)
    for tid in q.ordered():
        q.remove(tid)
    assert len(q) == 0


def test_ordering_is_overridable_by_subclass():
    class Reverse(ReadyQueue):
        def ordered(self):
            return list(reversed(super().ordered()))

    q = Reverse()
    for tid in ("a", "b"):
        q.push(tid)
    assert q.ordered() == ["b", "a"]
