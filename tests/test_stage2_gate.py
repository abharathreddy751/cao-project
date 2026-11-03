import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("stage2_gate", Path(__file__).resolve().parents[1] / "scripts" / "stage2_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def _events(second_start=5.0, pool="P", elig=("P",)):
    return [
        {"event": "run_started", "n_tasks": 2, "edges": [["a", "b"]],
         "tasks": {"a": {"eligible_pools": list(elig)}, "b": {"eligible_pools": list(elig)}}},
        {"event": "task_dispatched", "task_id": "a", "pool": "P"},
        {"event": "task_dispatched", "task_id": "b", "pool": pool},
        {"event": "task_completed", "task_id": "a", "worker_id": "P0", "t_started": 0.0, "t_completed": 4.0},
        {"event": "task_completed", "task_id": "b", "worker_id": "P1", "t_started": second_start, "t_completed": 9.0},
        {"event": "run_finished", "status": "completed", "n_completed": 2, "makespan_seconds": 9.0, "tasks_per_pool": {"P": 2}},
    ]


def test_clean_run_passes():
    r = gate.check_run(_events(), {"verification": {"passed": True}})
    assert r["completed"] and r["output_verified"] and not r["dependency_violations"] and not r["ineligible_placements"]


def test_violations_are_reported():
    assert gate.check_run(_events(second_start=3.0), {})["dependency_violations"] == [("a", "b")]
    assert gate.check_run(_events(pool="E"), {})["ineligible_placements"] == ["b"]
    assert gate.check_run(_events(), {})["output_verified"] is False
