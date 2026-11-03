"""HEFT and PEFT reproduced on the published worked examples, through the repo code.

Data come only from docs/research_redesign/SOURCES_VERBATIM.md:
  * HEFT paper (Topcuoglu, Hariri, Wu, IEEE TPDS 13(3), 2002): section 2.1 eq. (1), (8), (9), section 2.2
    (Fig. 3, Table 1, Fig. 4a).
  * PEFT sample (Arabnejad and Barbosa, TPDS 25(3), 2014, via the author's thesis chapter 3; equation numbers
    are the THESIS numbers): section 3, eq. (7) OCT, (8) rank_oct, (9) OEFT, thesis Fig. 1, Tables 5 and 6.
Communication enters through the injected ``comm`` callable (printed edge cost, used for rank and EST, since the
papers' cbar and c coincide on a uniform network). One worker per processor, cost = printed matrix.
Not weakened: the only tolerated difference is the tied HEFT pair n3/n4 (both rank_u 80.000), where the repo breaks
the tie by topological position instead of randomly (SOURCES_VERBATIM section 4.2, item 3).
"""
import pytest

from caosched.core.dag import DAG
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task
from caosched.estimators import StaticProfileEstimator
from caosched.schedulers.heft import Problem, heft_plan
from caosched.schedulers.peft import optimistic_cost_table, peft_plan

WORKERS = {"w1": "P1", "w2": "P2", "w3": "P3"}

# Edges (parent, child) -> cost; both papers use the same 10-task shape.
HEFT_EDGES = {(1, 2): 18, (1, 3): 12, (1, 4): 9, (1, 5): 11, (1, 6): 14, (2, 8): 19, (2, 9): 16, (3, 7): 23,
              (4, 8): 27, (4, 9): 23, (5, 9): 13, (6, 8): 15, (7, 10): 17, (8, 10): 11, (9, 10): 13}  # section 2.2
HEFT_W = [(14, 16, 9), (13, 19, 18), (11, 13, 19), (13, 8, 17), (12, 13, 10),
          (13, 16, 9), (7, 15, 11), (5, 11, 14), (18, 12, 20), (21, 7, 16)]  # section 2.2, n1..n10 on (P1,P2,P3)
PEFT_EDGES = {(1, 2): 17, (1, 3): 31, (1, 4): 29, (1, 5): 13, (1, 6): 7, (3, 7): 16, (2, 8): 3, (2, 9): 30,
              (4, 8): 11, (4, 9): 7, (5, 9): 57, (6, 8): 5, (7, 10): 9, (8, 10): 42, (9, 10): 7}  # section 3
PEFT_W = [(22, 21, 36), (22, 18, 18), (32, 27, 43), (7, 10, 4), (29, 27, 35),
          (26, 17, 24), (14, 25, 30), (29, 23, 36), (15, 21, 8), (13, 16, 33)]  # section 3, T1..T10


def _build(edges, w):
    deps = {i: [] for i in range(1, 11)}
    for (a, b) in edges:
        deps[b].append(a)
    dag = DAG({f"n{i}": Task(f"n{i}", f"n{i}", 1, dependencies=tuple(f"n{a}" for a in d)) for i, d in deps.items()})
    est = StaticProfileEstimator({(f"n{i + 1}", 1, f"P{j + 1}"): float(c) for i, row in enumerate(w) for j, c in enumerate(row)})
    cost = lambda task, pool: est.estimate(task, pool)  # noqa: E731
    comm = lambda p, c: float(edges[(int(p.task_id[1:]), int(c.task_id[1:]))])  # noqa: E731
    return dag, RuntimeState(dag, WORKERS), cost, comm


def _ids(seq):
    return [f"n{i}" for i in seq]


def test_heft_paper_example_fig3():
    dag, state, cost, comm = _build(HEFT_EDGES, HEFT_W)
    plan = heft_plan(dag, state, cost, comm)
    # Table 1, rank_u (eq. 8, 9), printed to 3 decimals
    table1 = [108.000, 77.000, 80.000, 80.000, 69.000, 63.333, 42.667, 35.667, 44.333, 14.667]
    assert [plan.rank[f"n{i + 1}"] for i in range(10)] == pytest.approx(table1, abs=5e-4)
    # Fig. 4a assignment
    on = {"P1": "n2 n8", "P2": "n4 n6 n9 n10", "P3": "n1 n3 n5 n7"}
    for pool, tasks in on.items():
        assert {t: WORKERS[plan.assign[t]] for t in tasks.split()} == {t: pool for t in tasks.split()}
    assert plan.makespan == 80   # Fig. 4a, eq. (7)
    # Order {n1, n3, n4, n2, n5, n6, n9, n7, n8, n10}: n3/n4 tie (rank_u 80) is the only tolerated difference
    assert set(plan.order[1:3]) == {"n3", "n4"}
    assert plan.order[0] == "n1" and plan.order[3:] == _ids([2, 5, 6, 9, 7, 8, 10])


def test_peft_sample_oct_rank_and_schedule():
    dag, state, cost, comm = _build(PEFT_EDGES, PEFT_W)
    oct_ = optimistic_cost_table(Problem(dag, state, cost, comm))
    # Table 5 (eq. 7), OCT rows on (P1, P2, P3)
    table5 = [(64, 68, 86), (42, 39, 42), (27, 41, 43), (42, 39, 50), (28, 37, 28),
              (42, 39, 44), (13, 16, 22), (13, 16, 33), (13, 16, 20), (0, 0, 0)]
    for i, row in enumerate(table5):
        assert [oct_[f"n{i + 1}"][w] for w in ("w1", "w2", "w3")] == list(row), f"OCT row T{i + 1}"
    plan = peft_plan(dag, state, cost, comm)
    # Table 5 rank_oct (eq. 8), printed to 1 decimal
    rank_oct = [72.7, 41, 37, 43.7, 31, 41.7, 17, 20.7, 16.3, 0]
    assert [plan.rank[f"n{i + 1}"] for i in range(10)] == pytest.approx(rank_oct, abs=0.05)
    # Table 6 order and processors
    assert plan.order == _ids([1, 4, 6, 2, 3, 5, 8, 7, 9, 10])
    pools = [WORKERS[plan.assign[t]] for t in plan.order]
    assert pools == ["P1", "P1", "P2", "P1", "P1", "P3", "P2", "P1", "P3", "P2"]
    assert plan.makespan == 122   # PEFT


def test_heft_on_peft_sample_133_and_rank_u():
    dag, state, cost, comm = _build(PEFT_EDGES, PEFT_W)
    plan = heft_plan(dag, state, cost, comm)
    printed_rank_u = [169, 114.3, 102.7, 110, 129.7, 119.3, 52.7, 92, 42.3, 20.7]  # thesis Table 5
    assert [plan.rank[f"n{i + 1}"] for i in range(10)] == pytest.approx(printed_rank_u, abs=0.05)
    assert plan.makespan == 133   # HEFT on the PEFT sample
