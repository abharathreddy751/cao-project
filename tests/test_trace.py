import json

import pytest

from caosched.core.trace import dag_from_trace, generate_trace, load_or_create_trace

MIX = {"matmul": 1, "image_filter": 1, "compression": 1}
SIZES = {"matmul": [64, 128], "image_filter": [64], "compression": [4096]}


def _spec(gen="layered", **kw):
    base = {"name": f"t_{gen}", "generator": gen, "seed": 7, "workload_mix": MIX, "sizes": SIZES,
            "n_layers": 5, "width_min": 2, "width_max": 6, "max_parents": 3, "n_tasks": 10, "width": 4, "stages": 2}
    return {**base, **kw}


@pytest.mark.parametrize("gen", ["layered", "independent", "fork_join"])
def test_generation_is_deterministic_and_yields_valid_dag(gen):
    a, b = generate_trace(_spec(gen)), generate_trace(_spec(gen))
    assert a == b
    dag = dag_from_trace(a)  # DAG() validates ids, deps, acyclicity
    assert len(dag) == len(a["tasks"])
    for t in dag.tasks.values():
        assert t.size in SIZES[t.workload]


def test_different_seed_gives_different_trace():
    assert generate_trace(_spec(seed=1)) != generate_trace(_spec(seed=2))


def test_layered_edges_only_point_to_previous_layer():
    for t in generate_trace(_spec())["tasks"]:
        layer = int(t["id"].split("_")[0][1:])
        assert all(int(d.split("_")[0][1:]) == layer - 1 for d in t["deps"])
        assert (layer == 0) == (not t["deps"])


def test_fork_join_shape():
    tr = generate_trace(_spec("fork_join", width=3, stages=2))
    dag = dag_from_trace(tr)
    assert len(dag) == 1 + 2 * (3 + 1)
    assert dag.critical_path_length() == 1 + 2 * 2


def test_replay_builds_independent_fresh_dags():
    tr = generate_trace(_spec())
    d1, d2 = dag_from_trace(tr), dag_from_trace(tr)
    d1.mark_completed(d1.initial_ready_tasks()[0])
    assert d2.num_completed == 0


def test_load_or_create_persists_and_detects_stale_trace(tmp_path):
    spec = _spec()
    tr, path = load_or_create_trace(spec, tmp_path)
    assert path.exists() and json.loads(path.read_text()) == tr
    assert load_or_create_trace(spec, tmp_path)[0] == tr
    with pytest.raises(ValueError, match="does not match"):
        load_or_create_trace({**spec, "width_max": 9}, tmp_path)
