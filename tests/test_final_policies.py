"""Final-study policies (PRED_RANK_GREEDY_E2E, HEFT_E2E, HEFT_ORACLE_REF) and the final adapter. Pure logic on hand-built DAGs, plus one
small real run. Numbers are chosen so the expected answer is obvious by hand."""
import itertools
import json

import pytest

from caosched.core.dag import DAG
from caosched.core.event_log import read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task
from caosched.estimators.e2e import EndToEndTerms
from caosched.estimators.profile import StaticProfileEstimator
from caosched.experiment.design import Condition
from caosched.final.adapter import FinalAdapter, build_final_policy
from caosched.final.policies import HeftE2E, HeftOracleReference, PredictedRankGreedyE2E
from caosched.schedulers.heft import HeftScheduler
from caosched.study2.policies import PredictedRankGreedy

KERNEL = {("a", "P"): 0.020, ("a", "E"): 0.040, ("a", "G"): 0.010,
          ("b", "P"): 0.020, ("b", "E"): 0.040,
          ("c", "P"): 0.050, ("c", "E"): 0.100, ("c", "G"): 0.020}
SETUP = {"P": 0.002, "E": 0.002, "G": 0.020}      # artifact I/O inside the worker: large on G in this toy case
OVERHEAD = {"P": 0.001, "E": 0.001, "G": 0.002}   # IPC


def _dag():
    return DAG({"A": Task("A", "a", 1, eligible_pools=("P", "E", "G")),
                "B": Task("B", "b", 1, eligible_pools=("P", "E")),
                "C": Task("C", "c", 1, eligible_pools=("P", "E", "G"))})


def _est():
    return StaticProfileEstimator({(w, 1, p): v for (w, p), v in KERNEL.items()})


def _terms(scale=1.0):
    setup = {(w, 1, p): SETUP[p] * scale for (w, p) in KERNEL}
    return EndToEndTerms(setup, {p: v * scale for p, v in OVERHEAD.items()})


def _state(dag, extra=None):
    return RuntimeState(dag, {"P0": "P", "E0": "E", "G0": "G", **(extra or {})})


def _both(scale):
    dag = _dag()
    pred = PredictedRankGreedy(_est(), "PRED")
    e2e = PredictedRankGreedyE2E(_est(), "PRED_E2E", _terms(scale))
    for pol in (pred, e2e):
        pol.on_run_start(dag, _state(dag))
    return dag, pred, e2e


def test_kernel_time_and_total_time_favour_different_workers():
    dag, pred, e2e = _both(1.0)
    st = _state(dag)
    # task A: kernel 10 ms on G, 20 ms on P; but G adds 22 ms of setup+IPC, P only 3 ms -> total 32 ms vs 23 ms
    assert pred.select_worker(dag.tasks["A"], st) == "G0"
    assert e2e.select_worker(dag.tasks["A"], st) == "P0"
    # task C: G is cheapest in both views (kernel 20 vs 50 ms; total 42 vs 53 ms) -> both agree
    assert pred.select_worker(dag.tasks["C"], st) == e2e.select_worker(dag.tasks["C"], st) == "G0"
    d = e2e.last_decision
    assert d["model"] == "e2e" and d["predicted_s"] == pytest.approx(0.020) and d["predicted_extra_s"] == pytest.approx(0.022)
    assert d["predicted_occupancy_s"] == pytest.approx(0.042)


def test_zero_overhead_equals_registered_pred_in_every_machine_state():
    dag, pred, e2e = _both(0.0)
    workers = ["P0", "E0", "G0"]
    for r in range(len(workers) + 1):
        for busy in itertools.combinations(workers, r):
            st = _state(dag)
            for i, w in enumerate(busy):
                st.mark_submitted(w, f"x{i}", 0.0)
            for tid, t in dag.tasks.items():
                assert e2e.select_worker(t, st) == pred.select_worker(t, st), (busy, tid)
            ready = ["A", "B", "C"]
            assert e2e.order_ready(ready, st) == pred.order_ready(ready, st)


def test_unsupported_pool_is_never_chosen_and_no_idle_worker_returns_none():
    dag, pred, e2e = _both(1.0)
    b = dag.tasks["B"]                       # not eligible for G (no CUDA variant)
    st = _state(dag)
    st.mark_submitted("P0", "x", 0.0)
    st.mark_submitted("E0", "y", 0.0)        # only G0 is idle
    assert e2e.select_worker(b, st) is None  # G0 is idle but B may not run there
    assert pred.select_worker(b, st) is None
    st2 = _state(dag)
    for w, t in (("P0", "x"), ("E0", "y"), ("G0", "z")):
        st2.mark_submitted(w, t, 0.0)
    assert e2e.select_worker(dag.tasks["A"], st2) is None


def test_missing_term_fails_before_the_run_not_in_the_middle():
    dag = _dag()
    terms = _terms()
    del terms.setup_s[("c", 1, "G")]
    pol = PredictedRankGreedyE2E(_est(), "PRED_E2E", terms)
    with pytest.raises(KeyError):
        pol.on_run_start(dag, _state(dag))
    with pytest.raises(ValueError, match="EndToEndTerms"):
        PredictedRankGreedyE2E(_est(), "x", None)


def test_transfer_term_keeps_a_slow_link_pool_out():
    class Link:                               # 1 s round trip to pool R, free elsewhere
        def estimate(self, task, pool):
            return 1.0 if pool == "R" else 0.0

        def describe(self):
            return {"stub": True}

    kernel = {**{(w, 1, p): v for (w, p), v in KERNEL.items()}, ("b", 1, "R"): 0.001}
    dag = DAG({"B": Task("B", "b", 1, eligible_pools=("P", "E", "R"))})
    terms = EndToEndTerms({k: 0.0 for k in kernel}, {"P": 0.0, "E": 0.0, "R": 0.0})
    e2e = PredictedRankGreedyE2E(StaticProfileEstimator(kernel), "E", terms, transfer=Link())
    pred = PredictedRankGreedy(StaticProfileEstimator(kernel), "P")
    st = RuntimeState(dag, {"P0": "P", "E0": "E", "R0": "R"})
    for pol in (e2e, pred):
        pol.on_run_start(dag, st) if pol is pred else None
    pred_choice = pred.select_worker(dag.tasks["B"], st)
    assert pred_choice == "R0"                # kernel-only placement is lured by the 1 ms remote kernel
    # on_run_start of the e2e variant needs the transfer: EarliestFinishTimeScheduler validates every pool
    e2e.on_run_start(dag, st)
    assert e2e.select_worker(dag.tasks["B"], st) == "P0"


def test_rank_and_placement_use_the_same_cost():
    kernel = {("x", 1, "P"): 0.010, ("y", 1, "P"): 0.050}
    dag = DAG({"X": Task("X", "x", 1, eligible_pools=("P",)), "Y": Task("Y", "y", 1, eligible_pools=("P",))})
    terms = EndToEndTerms({("x", 1, "P"): 0.100, ("y", 1, "P"): 0.0}, {"P": 0.0})
    st = RuntimeState(dag, {"P0": "P"})
    pred = PredictedRankGreedy(StaticProfileEstimator(kernel), "PRED")
    e2e = PredictedRankGreedyE2E(StaticProfileEstimator(kernel), "E2E", terms)
    for p in (pred, e2e):
        p.on_run_start(dag, st)
    assert pred.order_ready(["X", "Y"], st) == ["Y", "X"]     # kernel only: Y (50 ms) before X (10 ms)
    assert e2e.order_ready(["X", "Y"], st) == ["X", "Y"]      # X occupies a worker for 110 ms in total


def test_heft_e2e_plans_with_the_total_cost_and_the_oracle_is_labelled_reference():
    dag = DAG({"A": Task("A", "a", 1, eligible_pools=("P", "G"))})
    st = RuntimeState(dag, {"P0": "P", "G0": "G"})
    plain = HeftScheduler(_est(), "HEFT_param")
    e2e = HeftE2E(_est(), "HEFT_E2E", _terms())
    for p in (plain, e2e):
        p.on_run_start(dag, st)
    assert plain.plan.assign == {"A": "G0"}                    # 10 ms beats 20 ms
    assert e2e.plan.assign == {"A": "P0"}                      # 23 ms beats 32 ms
    assert e2e.plan.makespan == pytest.approx(0.023)
    rows = [{"run_id": "r", "task_id": "A", "seed": 0, "workload": "a", "size": 1, "pool": "P", "kernel_s": 0.5},
            {"run_id": "r", "task_id": "A", "seed": 0, "workload": "a", "size": 1, "pool": "G", "kernel_s": 0.01}]
    from caosched.study2.policies import CachedOracle
    orc = HeftOracleReference(CachedOracle.from_rows(rows), "HEFT_ORACLE_REF")
    orc.on_run_start(dag, st)
    assert orc.plan.assign == {"A": "G0"} and orc.describe()["reference_only"] is True and orc.describe()["plan"] == "static"


def test_bindings_are_built_from_files_and_registered_ones_fall_through(tmp_path):
    kern = {f"{w}|{p}": {"features": [], "coef": [v], "n": 3, "mae_s": 0.0} for (w, p), v in KERNEL.items()}
    pm = tmp_path / "pm.json"
    pm.write_text(json.dumps({"groups": kern}))
    terms = tmp_path / "terms.json"
    _terms().save(terms, {})
    rows = tmp_path / "rows.json"
    rows.write_text(json.dumps([{"run_id": "r", "task_id": "A", "seed": 0, "workload": "a", "size": 1, "pool": "P", "kernel_s": 0.1}]))
    kw = {"param_model": str(pm), "e2e_terms": str(terms), "oracle_rows": str(rows)}
    mk = lambda b, **x: build_final_policy(Condition("c", "EFT_E1", None, {}, {**kw, "binding": b, **x}, instance=None), 0)  # noqa: E731
    assert isinstance(mk("pred_rank_greedy_e2e"), PredictedRankGreedyE2E) and mk("pred_rank_greedy_e2e").name == "PRED_RANK_GREEDY_E2E"
    assert isinstance(mk("heft_e2e"), HeftE2E) and mk("heft_e2e").name == "HEFT_E2E"
    assert isinstance(mk("heft_oracle"), HeftOracleReference)
    reg = mk("pred_rank_greedy")                                # registered binding: untouched class and name
    assert type(reg) is PredictedRankGreedy and reg.name == "PRED_RANK_GREEDY"
    assert mk("param_model_heft").name == "HEFT_param_model"


@pytest.fixture
def adapter():
    a = FinalAdapter(runtime_config=RuntimeConfig(p_core_slots=(0,), e_core_slots=(1,)), timeout_s=120, run_timeout_s=300)
    yield a
    a.close()


def _tiny_files(tmp_path):
    stages = {"img_source": 4096, "img_denoise": 4096, "img_edges": 4096, "img_features": 4096, "img_aggregate": 3}  # aggregate size = k
    pm = {f"{s}|{p}": {"features": [], "coef": [0.002 if p == "P" else 0.004], "n": 3, "mae_s": 0.0} for s in stages for p in ("P", "E")}
    (tmp_path / "pm.json").write_text(json.dumps({"groups": pm}))
    _t = EndToEndTerms({(s, n, p): 0.001 for s, n in stages.items() for p in ("P", "E")}, {"P": 0.001, "E": 0.001})
    _t.save(tmp_path / "terms.json", {})
    return {"param_model": str(tmp_path / "pm.json"), "e2e_terms": str(tmp_path / "terms.json")}


def _run(adapter, tmp_path, name, **kw):
    cond = Condition(name, "EFT_E1", None, {}, {"k": 3, "tile": 64, "denoise_iterations": 2, **kw}, instance=None)
    wd = tmp_path / "session" / "runs" / f"b0000_00_{name}"
    wd.mkdir(parents=True)
    return adapter.run_one(cond, wd, seed=1), wd


def test_real_run_records_timing_and_static_plan(adapter, tmp_path):
    files = _tiny_files(tmp_path)
    rec, wd = _run(adapter, tmp_path, "HEFT_E2E", binding="heft_e2e", **files)
    assert rec.status == "ok" and rec.output_ok is True, rec.error
    x = rec.extra
    assert x["end_to_end_makespan_seconds"] >= x["makespan_seconds"] and x["policy_setup_s"] > 0 and x["init_s"] >= 0
    sp = x["static_plan"]
    assert sp["n_planned"] == 13 and sp["n_executed_elsewhere"] == 0 and sp["planned_makespan_s"] > 0   # a faithful static schedule
    fin = read_events(next(wd.glob("*.jsonl")))[-1]
    assert fin["event"] == "run_finished" and fin["policy_setup_seconds"] == pytest.approx(x["policy_setup_s"])
    rec2, _ = _run(adapter, tmp_path, "PRED_E2E", binding="pred_rank_greedy_e2e", **files)
    assert rec2.status == "ok" and rec2.output_ok is True and "static_plan" not in rec2.extra
    assert rec2.extra["policy"] == "PRED_RANK_GREEDY_E2E"
