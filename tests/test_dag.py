import pytest

from caosched.core.dag import DAG, build_chain_dag, build_fork_join_dag, build_independent_dag, build_mixed_dag
from caosched.core.task import Task


def test_independent_dag_all_tasks_initially_ready():
    dag = build_independent_dag(5)
    assert set(dag.initial_ready_tasks()) == set(dag.tasks.keys())


def test_chain_dag_only_first_task_initially_ready():
    dag = build_chain_dag(4)
    assert dag.initial_ready_tasks() == ["t0"]


def test_chain_dag_completion_unlocks_next_task_in_order():
    dag = build_chain_dag(3)
    assert dag.mark_completed("t0") == ["t1"]
    assert dag.mark_completed("t1") == ["t2"]
    assert dag.mark_completed("t2") == []
    assert dag.is_complete()


def test_fork_join_dag_join_task_waits_for_all_branches():
    dag = build_fork_join_dag(width=3)
    assert dag.initial_ready_tasks() == ["root"]
    newly_ready = dag.mark_completed("root")
    assert set(newly_ready) == {"branch0", "branch1", "branch2"}
    assert dag.mark_completed("branch0") == []
    assert dag.mark_completed("branch1") == []
    assert dag.mark_completed("branch2") == ["join"]
    assert not dag.is_complete()  # "join" is ready but not yet completed
    assert dag.mark_completed("join") == []
    assert dag.is_complete()


def test_mixed_dag_is_well_formed_and_eventually_completes():
    dag = build_mixed_dag()
    completed_order = []
    frontier = list(dag.initial_ready_tasks())
    while frontier:
        tid = frontier.pop()
        completed_order.append(tid)
        frontier.extend(dag.mark_completed(tid))
    assert dag.is_complete()
    assert len(completed_order) == len(dag)


def test_dag_rejects_unknown_dependency():
    with pytest.raises(ValueError):
        DAG({"a": Task(task_id="a", workload="matmul", size=8, dependencies=("missing",))})


# --- Phase 1 hardening: validation, cycles, dependency-tracking invariants ---

from caosched.core.dag import CycleError  # noqa: E402


def _t(tid, *deps):
    return Task(task_id=tid, workload="matmul", size=8, dependencies=deps)


def test_dag_rejects_two_node_cycle_at_construction():
    with pytest.raises(CycleError) as exc:
        DAG({"a": _t("a", "b"), "b": _t("b", "a")})
    assert "a" in str(exc.value) and "b" in str(exc.value)


def test_dag_rejects_cycle_hidden_behind_valid_prefix():
    # root is fine; x -> y -> z -> x is a cycle downstream of it.
    with pytest.raises(CycleError):
        DAG({"root": _t("root"), "x": _t("x", "root", "z"), "y": _t("y", "x"), "z": _t("z", "y")})


def test_dag_rejects_key_task_id_mismatch():
    with pytest.raises(ValueError):
        DAG({"a": _t("not_a")})


def test_dag_rejects_empty():
    with pytest.raises(ValueError):
        DAG({})


def test_mark_completed_rejects_double_completion_and_unknown_id():
    dag = build_chain_dag(2)
    dag.mark_completed("t0")
    with pytest.raises(ValueError):
        dag.mark_completed("t0")
    with pytest.raises(KeyError):
        dag.mark_completed("nope")


def test_mark_completed_rejects_task_whose_deps_are_unmet():
    dag = build_chain_dag(3)
    with pytest.raises(ValueError):
        dag.mark_completed("t2")


def test_topological_order_respects_every_edge_on_all_patterns():
    for dag in (build_independent_dag(4), build_chain_dag(5), build_fork_join_dag(3), build_mixed_dag()):
        pos = {tid: i for i, tid in enumerate(dag.topological_order())}
        assert set(pos) == set(dag.tasks)
        for tid, task in dag.tasks.items():
            for dep in task.dependencies:
                assert pos[dep] < pos[tid]


def test_critical_path_length_matches_known_shapes():
    assert build_independent_dag(4).critical_path_length() == 1
    assert build_chain_dag(5).critical_path_length() == 5
    assert build_fork_join_dag(3).critical_path_length() == 3
    assert build_mixed_dag().critical_path_length() == 5  # a-b-c*-d-f


def test_every_task_unlocked_exactly_once_under_any_completion_order():
    import random

    for seed in range(20):
        dag = build_mixed_dag()
        rng = random.Random(seed)
        unlocked = list(dag.initial_ready_tasks())
        frontier = list(unlocked)
        while frontier:
            tid = frontier.pop(rng.randrange(len(frontier)))
            new = dag.mark_completed(tid)
            unlocked.extend(new)
            frontier.extend(new)
        assert dag.is_complete()
        assert sorted(unlocked) == sorted(dag.tasks)  # no task unlocked twice or missed
