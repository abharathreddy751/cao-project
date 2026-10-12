"""HEFT / PEFT / rank-EFT on hand-built DAGs whose answers were derived by hand
(see the comments); no textbook numbers are used. Pure logic, no processes."""
import pytest

from caosched.core.dag import DAG
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task
from caosched.estimators import StaticProfileEstimator
from caosched.remote.link import LinkConfig
from caosched.schedulers import plan_factories, rank_eft_factories
from caosched.schedulers.heft import HeftScheduler, earliest_slot, heft_plan
from caosched.schedulers.peft import PeftScheduler, optimistic_cost_table, peft_plan
from caosched.schedulers.heft import Problem
from caosched.schedulers.rank_eft import FileTransferModel, RankEftScheduler


def _dag(edges, eligible=None):
    """edges: {task: [deps]}; workload = task id, size 1 (profile keys are (task, 1, pool))."""
    eligible = eligible or {}
    return DAG({t: Task(t, t, 1, dependencies=tuple(d), eligible_pools=eligible.get(t)) for t, d in edges.items()})


def _cost(table):
    est = StaticProfileEstimator({(t, 1, pool): v for (t, pool), v in table.items()})
    return lambda task, pool: est.estimate(task, pool)


def test_earliest_slot_insertion():
    busy = [(0, 2), (6, 9)]
    assert earliest_slot(busy, 0, 3) == 2      # fits the gap [2, 6]
    assert earliest_slot(busy, 0, 5) == 9      # gap too small -> after the last task
    assert earliest_slot(busy, 3, 3) == 3
    assert earliest_slot(busy, 4, 3) == 9      # 4 + 3 > 6
    assert earliest_slot([], 1.5, 2) == 1.5


DIAMOND = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}
DIAMOND_COST = {("A", "F"): 2, ("B", "F"): 3, ("C", "F"): 4, ("D", "F"): 2,
                ("A", "S"): 4, ("B", "S"): 6, ("C", "S"): 8, ("D", "S"): 4}  # S is 2x slower


def test_heft_diamond_two_speeds():
    # wbar: A 3, B 4.5, C 6, D 3 -> rank_u: D 3, B 7.5, C 9, A 12 -> order A, C, B, D
    # A: F0 [0,2]; C: F0 [2,6] (S0 would end at 10); B: S0 [2,8] beats F0 [6,9]; D: F0 [8,10]
    dag = _dag(DIAMOND)
    plan = heft_plan(dag, RuntimeState(dag, {"F0": "F", "S0": "S"}), _cost(DIAMOND_COST))
    assert plan.rank == pytest.approx({"A": 12, "C": 9, "B": 7.5, "D": 3})
    assert plan.order == ["A", "C", "B", "D"]
    assert plan.assign == {"A": "F0", "C": "F0", "B": "S0", "D": "F0"}
    assert (plan.start["B"], plan.finish["B"], plan.start["D"], plan.finish["D"]) == (2, 8, 8, 10)
    assert plan.makespan == 10


def test_heft_insertion_fills_idle_gap():
    # X (only pool A, 10), Y (only pool B, 3, after X), Z (only pool B, 2, no deps).
    # rank_u: X 13, Y 3, Z 2 -> order X, Y, Z. Y waits for X -> WB idle in [0,10]; Z is inserted at [0,2].
    dag = _dag({"X": [], "Y": ["X"], "Z": []}, eligible={"X": ("A",), "Y": ("B",), "Z": ("B",)})
    cost = _cost({("X", "A"): 10, ("Y", "B"): 3, ("Z", "B"): 2})
    plan = heft_plan(dag, RuntimeState(dag, {"WA": "A", "WB": "B"}), cost)
    assert plan.order == ["X", "Y", "Z"]
    assert (plan.start["Y"], plan.finish["Y"]) == (10, 13)
    assert (plan.start["Z"], plan.finish["Z"]) == (0, 2)   # without insertion: [13, 15]
    assert plan.makespan == 13


COMM_DAG = {"A": [], "B": ["A"], "C": ["A"], "D": ["B"]}
COMM_COST = {("A", "P0"): 2, ("B", "P0"): 3, ("C", "P0"): 5, ("D", "P0"): 1,
             ("A", "P1"): 4, ("B", "P1"): 9, ("C", "P1"): 6, ("D", "P1"): 2}


def _comm_problem():
    dag = _dag(COMM_DAG)
    state = RuntimeState(dag, {"w0": "P0", "w1": "P1"})
    return dag, state


def test_heft_with_edge_communication():
    # comm 1 per edge when workers differ. rank_u: D 1.5, C 5.5, B 6+1+1.5 = 8.5, A 3+max(1+8.5, 1+5.5) = 12.5
    # A: w0 [0,2]; B: w0 [2,5] (w1: 3..12); C: w0 would end 10, w1 [3,9]; D: w0 [5,6] (w1 ends 11)
    dag, state = _comm_problem()
    plan = heft_plan(dag, state, _cost(COMM_COST), lambda a, b: 1.0)
    assert plan.rank == pytest.approx({"A": 12.5, "B": 8.5, "C": 5.5, "D": 1.5})
    assert plan.assign == {"A": "w0", "B": "w0", "C": "w1", "D": "w0"}
    assert (plan.start["C"], plan.finish["C"], plan.finish["D"]) == (3, 9, 6)
    assert plan.makespan == 9


def test_peft_optimistic_cost_table_and_plan():
    # OCT(B)= {w0: 1, w1: 2}, OCT(A) = {w0: 5, w1: 6}, exits 0 -> rank_oct A 5.5, B 1.5, C 0, D 0
    dag, state = _comm_problem()
    prob = Problem(dag, state, _cost(COMM_COST), lambda a, b: 1.0)
    oct_ = optimistic_cost_table(prob)
    assert oct_["B"] == {"w0": 1, "w1": 2} and oct_["A"] == {"w0": 5, "w1": 6}
    assert oct_["C"] == {"w0": 0, "w1": 0} and oct_["D"] == {"w0": 0, "w1": 0}
    plan = peft_plan(dag, state, _cost(COMM_COST), lambda a, b: 1.0)
    assert plan.rank == pytest.approx({"A": 5.5, "B": 1.5, "C": 0, "D": 0})
    assert plan.order == ["A", "B", "C", "D"]
    assert plan.assign == {"A": "w0", "B": "w0", "C": "w1", "D": "w0"}
    assert plan.makespan == 9


def test_peft_lookahead_differs_from_heft():
    # A -> B, comm 10. A: w0 3 / w1 4; B: w0 100 / w1 1.
    # HEFT: A on w0 (EFT 3 < 4), then B on w1 after the transfer: 3 + 10 + 1 = 14.
    # PEFT: OCT(A) = {w0: 11, w1: 1} -> O_EFT w0 14, w1 5 -> A on w1, B on w1: makespan 5.
    dag = _dag({"A": [], "B": ["A"]})
    state = RuntimeState(dag, {"w0": "P0", "w1": "P1"})
    cost = _cost({("A", "P0"): 3, ("A", "P1"): 4, ("B", "P0"): 100, ("B", "P1"): 1})
    heft, peft = heft_plan(dag, state, cost, lambda a, b: 10.0), peft_plan(dag, state, cost, lambda a, b: 10.0)
    assert heft.assign == {"A": "w0", "B": "w1"} and heft.makespan == 14
    assert peft.assign == {"A": "w1", "B": "w1"} and peft.makespan == 5


def test_plan_schedulers_follow_plan_and_stay_eligible():
    dag = _dag(DIAMOND, eligible={"C": ("S",)})
    state = RuntimeState(dag, {"F0": "F", "S0": "S"})
    est = StaticProfileEstimator({(t, 1, pool): v for (t, pool), v in DIAMOND_COST.items()})
    for cls in (HeftScheduler, PeftScheduler):
        p = cls(est, cls.__name__)
        p.on_run_start(dag, state)
        picks = {t: p.select_worker(dag.tasks[t], state) for t in dag.tasks}
        assert picks["C"] == "S0"                       # restricted task never planned elsewhere
        assert picks == p.plan.assign and p.last_decision["plan_makespan"] == p.plan.makespan
        assert p.order_ready(["D", "A", "B"], state)[0] == "A"
        assert not p.binds_only_idle


def test_factories_register_plan_and_rank_policies(tmp_path):
    import json
    prof = tmp_path / "x_profile.json"
    prof.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": [
        {"workload": "matmul", "size": 64, "pool": p, "median_s": 0.01} for p in "PE"]}))
    f = plan_factories(prof)
    assert set(f) == {"HEFT_E1", "PEFT_E1"} and f["HEFT_E1"]() is not f["HEFT_E1"]()
    r = rank_eft_factories(["E1", "E1+rc"], prof)
    assert set(r) == {"EFT_E1_rank", "EFT_E1_rc_rank"} and isinstance(r["EFT_E1_rank"](), RankEftScheduler)


def test_rank_eft_orders_by_upward_rank_and_counts_transfer():
    dag = _dag(DIAMOND)
    state = RuntimeState(dag, {"F0": "F", "S0": "S"})
    est = StaticProfileEstimator({(t, 1, pool): v for (t, pool), v in DIAMOND_COST.items()})
    p = RankEftScheduler(est, "rank")
    p.on_run_start(dag, state)
    assert p.rank == pytest.approx({"A": 12, "C": 9, "B": 7.5, "D": 3})
    assert p.order_ready(["B", "D", "C"], state) == ["C", "B", "D"]

    # transfer-aware: remote pool R is faster (3.5 vs 5) but its transfer costs bytes / bandwidth
    one = _dag({"A": []})
    st = RuntimeState(one, {"L0": "L", "R0": "R"})
    e = StaticProfileEstimator({("A", 1, "L"): 5.0, ("A", 1, "R"): 3.5})
    link = {"R": LinkConfig("link", bandwidth_Bps=1000.0)}
    for nbytes, expect in ((1000, "R0"), (3000, "L0")):    # 3.5 + 1 < 5  <  3.5 + 3
        s = RankEftScheduler(e, "rank", transfer=FileTransferModel(link, lambda t, n=nbytes: (n, 0)))
        s.on_run_start(one, st)
        assert s.select_worker(one.tasks["A"], st) == expect
        assert s.last_decision["candidates"]["R0"]["transfer"] == pytest.approx(nbytes / 1000)
