import pickle

import pytest

from caosched.core.task import InvalidTransition, Task, TaskMessage, TaskResult, TaskState


def _task(**kw):
    return Task(**{"task_id": "t", "workload": "matmul", "size": 8, **kw})


def test_happy_path_lifecycle_transitions():
    t = _task()
    for s in (TaskState.READY, TaskState.DISPATCHED, TaskState.DONE):
        t.transition(s)
    assert t.state == TaskState.DONE


@pytest.mark.parametrize("path", [
    (TaskState.DISPATCHED,),                         # skip READY
    (TaskState.READY, TaskState.DONE),               # skip DISPATCHED
    (TaskState.READY, TaskState.DISPATCHED, TaskState.DONE, TaskState.READY),  # resurrect
])
def test_illegal_transitions_are_rejected(path):
    t = _task()
    with pytest.raises(InvalidTransition):
        for s in path:
            t.transition(s)


@pytest.mark.parametrize("kw", [
    {"task_id": ""}, {"size": 0}, {"dependencies": ("t",)}, {"dependencies": ("a", "a")},
])
def test_invalid_task_construction_rejected(kw):
    with pytest.raises(ValueError):
        _task(**kw)


def test_dependencies_list_is_normalised_to_tuple():
    assert _task(dependencies=["a", "b"]).dependencies == ("a", "b")


def test_derived_durations():
    t = _task()
    assert t.queue_wait_seconds is None and t.response_time_seconds is None
    t.t_ready, t.t_dispatched, t.t_completed = 10.0, 10.5, 12.0
    assert t.queue_wait_seconds == pytest.approx(0.5)
    assert t.response_time_seconds == pytest.approx(2.0)


def test_messages_survive_pickling_for_spawn_ipc():
    m = TaskMessage("t", "matmul", 8, 1)
    r = TaskResult("t", "P0", 0.001, None, 1.0, 2.0)
    assert pickle.loads(pickle.dumps(m)) == m
    assert pickle.loads(pickle.dumps(r)) == r
