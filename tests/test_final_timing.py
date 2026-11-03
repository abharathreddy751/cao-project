"""Amendment F1 (final study): end-to-end timing convention. Real worker pool and coordinator, as in test_coordinator.py.

* ``makespan_seconds`` keeps its old meaning (first dispatch -> last completion) and never contains ``on_run_start``;
* ``policy_setup_seconds`` = the duration of ``scheduler.on_run_start`` (static plan, upward rank, ...);
* ``end_to_end_makespan_seconds`` = start of ``run()`` -> last completion, so it contains init + policy set-up + execution.
"""
import time

import pytest

from caosched.analysis.stats_paired import exclusion_reason, run_metrics
from caosched.core.coordinator import Coordinator
from caosched.core.dag import build_independent_dag
from caosched.core.event_log import EventLogger, read_events
from caosched.core.scheduler_base import FirstIdleScheduler
from caosched.core.worker_pool import WorkerPool
from caosched.estimators.profile import StaticProfileEstimator
from caosched.schedulers.heft import HeftScheduler


@pytest.fixture(scope="module")
def pe_pool():
    pool = WorkerPool(p_core_slots=[0], e_core_slots=[1, 2])
    yield pool
    pool.shutdown()


class SlowSetup(FirstIdleScheduler):
    name = "test_slow_setup"

    def __init__(self, delay_s):
        self.delay_s = delay_s

    def on_run_start(self, dag, state):
        time.sleep(self.delay_s)


def _run(sched, pool, tmp_path, name):
    dag = build_independent_dag(4, workload="matmul", size=16)
    c = Coordinator(dag, pool, sched, EventLogger(run_id=name, output_dir=tmp_path))
    summary = c.run(run_timeout=60)
    c.logger.close()
    return summary, read_events(c.logger.path)


def test_policy_setup_time_is_recorded_and_outside_old_makespan(pe_pool, tmp_path):
    s, ev = _run(SlowSetup(0.30), pe_pool, tmp_path, "slow")
    assert 0.30 <= s.policy_setup_seconds < 0.60
    assert s.makespan_seconds is not None and s.makespan_seconds < 0.25          # old convention: setup NOT inside
    assert s.end_to_end_makespan_seconds >= s.policy_setup_seconds + s.makespan_seconds - 1e-3   # new convention: inside
    assert s.end_to_end_makespan_seconds >= s.init_seconds + s.policy_setup_seconds


def test_zero_setup_policy_has_small_setup_and_consistent_e2e(pe_pool, tmp_path):
    s, _ = _run(FirstIdleScheduler(), pe_pool, tmp_path, "fast")
    assert s.policy_setup_seconds < 0.05 and s.init_seconds >= 0.0
    assert s.end_to_end_makespan_seconds >= s.makespan_seconds
    # init + setup + execution account for the end-to-end time up to the (small) gap before the first dispatch
    gap = s.end_to_end_makespan_seconds - (s.init_seconds + s.policy_setup_seconds + s.makespan_seconds)
    assert -1e-3 <= gap < 0.25


def test_fields_are_logged_in_run_finished(pe_pool, tmp_path):
    s, ev = _run(SlowSetup(0.10), pe_pool, tmp_path, "logged")
    fin = ev[-1]
    assert fin["event"] == "run_finished"
    assert fin["policy_setup_seconds"] == pytest.approx(s.policy_setup_seconds)
    assert fin["init_seconds"] == pytest.approx(s.init_seconds)
    assert fin["end_to_end_makespan_seconds"] == pytest.approx(s.end_to_end_makespan_seconds)
    assert fin["makespan_seconds"] == pytest.approx(s.makespan_seconds)


def test_static_plan_time_is_recorded_for_heft(pe_pool, tmp_path):
    # HEFT computes its whole plan in on_run_start; that time is now visible and is inside the end-to-end makespan.
    prof = StaticProfileEstimator({("matmul", 16, "P"): 0.001, ("matmul", 16, "E"): 0.002})
    s, ev = _run(HeftScheduler(prof, "HEFT_test"), pe_pool, tmp_path, "heft")
    assert s.policy_setup_seconds > 0.0
    assert s.end_to_end_makespan_seconds >= s.policy_setup_seconds + s.makespan_seconds - 1e-3
    placed = {e["task_id"]: e["worker_id"] for e in ev if e["event"] == "task_dispatched"}
    assert set(placed) == {f"t{i}" for i in range(4)}


def test_analysis_metric_reads_new_fields_and_older_logs_give_none():
    new = [{"event": "run_finished", "status": "completed", "makespan_seconds": 1.0, "end_to_end_makespan_seconds": 1.3,
            "init_seconds": 0.1, "policy_setup_seconds": 0.2}]
    old = [{"event": "run_finished", "status": "completed", "makespan_seconds": 1.0}]
    m_new, m_old = run_metrics(new), run_metrics(old)
    assert (m_new["makespan_s"], m_new["makespan_e2e_s"], m_new["init_s"], m_new["policy_setup_s"]) == (1.0, 1.3, 0.1, 0.2)
    assert m_old["makespan_s"] == 1.0 and m_old["makespan_e2e_s"] is None and m_old["policy_setup_s"] is None


def test_exclusion_names_the_missing_metric():
    run = {"manifest": {"status": "ok", "warmup": False, "verification": {"passed": True}}, "log_ok": True, "session_problem": None,
           "metrics": {"makespan_s": 1.0, "makespan_e2e_s": None}}
    assert exclusion_reason(run) is None                              # old convention: fine
    assert "makespan_e2e_s" in exclusion_reason(run, "makespan_e2e_s")  # new convention: a pre-F1 log is excluded, not guessed
