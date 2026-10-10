"""Pins the clock assumptions the runtime's interval measurements rely on
(see caosched/util/clock.py for the Phase 1 finding that motivated this)."""
import multiprocessing as mp

from caosched.util import clock


def _child_now(q):
    from caosched.util import clock as c
    q.put(c.now())


def test_clock_has_sub_microsecond_steps():
    vals = sorted({clock.now() for _ in range(50_000)})
    assert min(b - a for a, b in zip(vals, vals[1:])) < 1e-6


def test_clock_is_shared_across_spawned_processes():
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    for _ in range(3):
        before = clock.now()
        p = ctx.Process(target=_child_now, args=(q,))
        p.start()
        child = q.get(timeout=60)
        after = clock.now()
        p.join()
        assert before <= child <= after


def test_anchor_maps_perf_to_epoch():
    a = clock.anchor()
    assert set(a) == {"epoch_anchor", "perf_anchor"} and a["epoch_anchor"] > 1.6e9
