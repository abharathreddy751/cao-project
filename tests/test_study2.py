"""Study 2 workload and adapter on tiny batches (tile 64). CUDA-dependent tests skip without a GPU."""
import hashlib

import pytest

from caosched.apps.cuda_stages import cuda_available
from caosched.core.event_log import read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.experiment.design import Condition
from caosched.study2.adapter import Study2Adapter
from caosched.study2.workload import build_batch

ALL3 = {"img_denoise": True, "img_edges": True, "img_features": True}


def test_batch_shape_and_eligibility():
    dag = build_batch(k=5, side=64, iterations=3, gpu_stages={"img_edges"})
    assert len(dag) == 5 * 4 + 1
    assert dag.tasks["aggregate"].dependencies == tuple(f"features_{i}" for i in range(5))
    for t in dag.tasks.values():
        assert ("G" in t.eligible_pools) == (t.workload == "img_edges"), t.task_id
        assert {"P", "E"} <= set(t.eligible_pools)
    assert dag.tasks["denoise_2"].params["iterations"] == 3 and dag.tasks["denoise_2"].dependencies == ("source_2",)
    assert len({t.params["seed"] for t in dag.tasks.values() if t.workload == "img_source"}) == 5  # distinct scenes
    assert all(t.eligible_pools == ("P", "E") for t in build_batch(k=2, side=64).tasks.values())
    with pytest.raises(ValueError):
        build_batch(k=0)


@pytest.fixture
def adapter():
    a = Study2Adapter(runtime_config=RuntimeConfig(p_core_slots=(0,), e_core_slots=(1,)), timeout_s=120, run_timeout_s=300)
    yield a
    a.close()


def _cond(name="B4", policy="B4", **kw):
    return Condition(name, policy, None, {}, {"k": 4, "tile": 64, "denoise_iterations": 2, **kw}, instance=None)


def _run(adapter, cond, tmp_path, n):
    wd = tmp_path / "session" / "runs" / f"b0000_0{n}_{cond.name}"
    wd.mkdir(parents=True)
    return adapter.run_one(cond, wd, seed=1), wd


def test_cpu_run_is_exactly_the_reference(adapter, tmp_path):
    rec, wd = _run(adapter, _cond(), tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True, rec.error
    assert rec.extra["n_tasks"] == 17 and rec.extra["cuda_tasks"] == [] and "G" not in rec.extra["tasks_per_pool"]
    assert rec.extra["output_verdict"]["match"] == "exact" and set(rec.output_hashes) == {"aggregate"}
    assert rec.input_hashes["reference_aggregate"] == rec.output_hashes["aggregate"]
    assert read_events(wd / rec.event_log)[-1]["status"] == "completed" and not (wd / "artifacts").exists()


def test_a_wrong_output_is_not_verified(adapter, tmp_path):
    key = (2, 64, 0, 2)   # k, tile, seed, denoise_iterations of _cond(k=2)
    rec, _ = _run(adapter, _cond(k=2), tmp_path, 0)
    assert rec.output_ok is True and key in adapter._ref
    adapter._ref[key]["aggregate"] = b"tampered"      # a reference the run cannot reproduce
    rec2, _ = _run(adapter, _cond("B4_bad", k=2), tmp_path, 1)
    assert rec2.status == "ok" and rec2.output_ok is False and rec2.extra["output_verdict"]["match"] == "MISMATCH"
    assert rec2.input_hashes["reference_aggregate"] == hashlib.sha256(b"tampered").hexdigest()


def test_static_map_policy_runs_without_gpu(adapter, tmp_path):
    cfg = {"B2_static_mapping": {"mapping": {"img_source": "P", "img_denoise": "P", "img_edges": "P",
                                             "img_features": "P", "img_aggregate": "P"}}}
    rec, _ = _run(adapter, _cond("B2", "B2", policy_cfg=cfg), tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True, rec.error
    assert set(rec.extra["tasks_per_pool"]) == {"P"}


def test_e2e_policy_is_built_from_a_terms_file(tmp_path):
    import json

    from caosched.estimators.e2e import EndToEndTerms
    from caosched.study2.adapter import build_study2_policy

    prof = tmp_path / "x_profile.json"
    prof.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": [
        {"workload": "img_source", "size": 4096, "pool": p, "median_s": 0.1} for p in ("P", "E")]}))
    terms = tmp_path / "terms.json"
    EndToEndTerms({("img_source", 4096, "P"): 0.004, ("img_source", 4096, "E"): 0.006}, {"P": 0.002, "E": 0.003}).save(terms, {})
    kw = {"profile": str(prof), "e2e_terms": str(terms)}
    pol = build_study2_policy(Condition("e", "EFT_E1", None, {}, kw, instance=None), 0)
    assert pol.name == "EFT_E1_e2e" and pol.describe()["model"] == "e2e" and pol.e2e.overhead("P") == 0.002
    assert build_study2_policy(Condition("p", "EFT_E1", None, {}, {"profile": str(prof)}, instance=None), 0).describe()["model"] == "kernel"
    with pytest.raises(ValueError, match="EFT_"):
        build_study2_policy(Condition("b", "B4", None, {}, kw, instance=None), 0)


@pytest.mark.skipif(not cuda_available(), reason="no CUDA device")
def test_one_pool_serves_gpu_and_no_gpu_conditions(adapter, tmp_path):
    cfg = {"B4_greedy_eligible": {"priority": ["G", "P", "E"]}}
    table = {"img_edges": True, "img_features": True}
    rec1, _ = _run(adapter, _cond("cpu", "B4", gpu_stage_table=table, no_gpu=True), tmp_path, 0)
    pool = adapter._pool
    rec2, _ = _run(adapter, _cond("gpu", "B4", gpu_stage_table=table, policy_cfg=cfg), tmp_path, 1)
    rec3, _ = _run(adapter, _cond("cpu2", "B4", gpu_stage_table=table, no_gpu=True), tmp_path, 2)
    assert adapter._pool is pool                                     # never rebuilt between conditions
    assert rec1.extra["gpu_pool"] is False and rec1.extra["cuda_tasks"] == [] and "G" not in rec1.extra["tasks_per_pool"]
    assert rec2.extra["cuda_tasks"] and rec3.extra["cuda_tasks"] == []
    assert all(r.status == "ok" and r.output_ok is True for r in (rec1, rec2, rec3))


@pytest.mark.skipif(not cuda_available(), reason="no CUDA device")
def test_g_pool_run_is_within_tolerance_and_confined(adapter, tmp_path):
    cfg = {"B4_greedy_eligible": {"priority": ["G", "P", "E"]}}
    rec, _ = _run(adapter, _cond("b4g", "B4", gpu_stage_table={"img_edges": True, "img_features": True}, policy_cfg=cfg),
                  tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True, (rec.error, rec.extra.get("output_verdict"))
    assert rec.extra["gpu_pool"] is True and rec.extra["cuda_tasks"]
    assert all(t.startswith(("edges_", "features_")) for t in rec.extra["cuda_tasks"])   # sources / denoise never on G
    rec2, _ = _run(adapter, _cond("rnd3", "random", gpu_stage_table=ALL3), tmp_path, 1)
    assert rec2.status == "ok" and rec2.output_ok is True, (rec2.error, rec2.extra.get("output_verdict"))


def _late_fixture():
    from caosched.core.dag import DAG
    from caosched.core.runtime_state import RuntimeState
    from caosched.core.task import Task
    from caosched.estimators.profile import StaticProfileEstimator
    from caosched.study2.policies import LateEftScheduler

    dag = DAG({t: Task(t, "w", 1) for t in ("run", "new")})
    state = RuntimeState(dag, {"P0": "P", "E0": "E"})
    est = StaticProfileEstimator({("w", 1, "P"): 0.010, ("w", 1, "E"): 0.100})
    pol = LateEftScheduler(est, "EFT_E1_late")
    pol.on_run_start(dag, state)
    return dag, state, pol


def test_late_eft_takes_an_idle_best_worker():
    dag, state, pol = _late_fixture()
    assert pol.binds_only_idle is True
    assert pol.select_worker(dag.tasks["new"], state) == "P0" and pol.last_decision["chosen"] == "P0"


def test_late_eft_holds_for_a_busy_fast_worker_but_not_for_a_far_better_idle_one():
    from caosched.util import clock

    dag, state, pol = _late_fixture()
    state.mark_submitted("P0", "run", clock.now())      # P0 busy for about 10 ms more; E0 would need 100 ms
    assert pol.select_worker(dag.tasks["new"], state) is None            # waiting for P0 finishes earlier than starting on E0
    assert pol.last_decision is None and "new" not in pol._decision_ctx  # a held task leaves no decision behind
    dag2, state2, pol2 = _late_fixture()
    state2.mark_submitted("P0", "run", clock.now() - 0.0)
    pol2.estimator.table[("w", 1, "P")] = 5.0                            # now P0 is predicted busy for 5 s: E0 (0.1 s) is better
    assert pol2.select_worker(dag2.tasks["new"], state2) == "E0"


def test_no_context_eft_decides_like_eft():
    from caosched.schedulers.eft import EarliestFinishTimeScheduler
    from caosched.study2.policies import EftNoContext, LateEftScheduler

    dag, state, _ = _late_fixture()
    from caosched.estimators.profile import StaticProfileEstimator

    est = StaticProfileEstimator({("w", 1, "P"): 0.010, ("w", 1, "E"): 0.100})
    ref, nc = EarliestFinishTimeScheduler(est, "a"), EftNoContext(est, "b")
    for p in (ref, nc):
        p.on_run_start(dag, state)
    assert ref.select_worker(dag.tasks["new"], state) == nc.select_worker(dag.tasks["new"], state) == "P0"
    assert "ctx" in ref.last_decision["candidates"]["P0"] and "ctx" not in nc.last_decision["candidates"]["P0"]
    assert LateEftScheduler(est, "c").log_context is False


def test_oracle_policy_uses_the_logged_task_times(tmp_path):
    import json

    from caosched.study2.adapter import build_study2_policy

    rows = [{"run_id": "r", "task_id": t, "seed": 0, "workload": "w", "size": 1, "pool": p, "kernel_s": k}
            for t in ("run", "new") for p, k in (("P", 0.01), ("E", 0.1))]
    f = tmp_path / "rows.json"
    f.write_text(json.dumps(rows))
    pol = build_study2_policy(Condition("o", "EFT_E1", None, {}, {"binding": "oracle", "oracle_rows": str(f)}, instance=None), 0)
    assert pol.name == "O_EFT_E5" and pol.log_context is False and pol.estimator.describe()["n_keys"] == 4
    dag, state, _ = _late_fixture()
    pol.on_run_start(dag, state)
    assert pol.select_worker(dag.tasks["new"], state) == "P0"


def test_cached_oracle_gives_the_same_numbers_as_the_replay_oracle():
    from caosched.estimators.oracle import ReplayOracleEstimator
    from caosched.study2.policies import CachedOracle

    rows = [{"run_id": f"r{i}", "task_id": "t", "seed": 0, "workload": "w", "size": 1, "pool": "P", "kernel_s": v}
            for i, v in enumerate((0.3, 0.1, 0.2, 0.9))]
    task = _late_fixture()[0].tasks["run"].__class__("t", "w", 1)
    assert CachedOracle.from_rows(rows).estimate(task, "P") == ReplayOracleEstimator.from_rows(rows).estimate(task, "P")
    with pytest.raises(KeyError):
        CachedOracle.from_rows(rows).estimate(task, "E")


def test_mixed_batch_shape_order_and_largest_first():
    from caosched.study2.policies import LargestFirstGreedy
    from caosched.study2.workload import build_mixed

    a, b = build_mixed([3, 32], [1, 64], order_seed=1), build_mixed([3, 32], [1, 64], order_seed=2)
    assert len(a) == 4 * 4 + 1 and a.tasks["aggregate"].size == 4
    sizes = lambda d: [d.tasks[f"source_{i}"].size for i in range(4)]  # noqa: E731
    assert sorted(sizes(a)) == [1024, 1024, 1024, 4096] and sizes(a) != sizes(b) or sorted(sizes(b)) == sorted(sizes(a))
    pol = LargestFirstGreedy(None, ["P", "E"], name="x")
    ids = [f"source_{i}" for i in range(4)]
    state = _late_fixture()[1]
    state.dag = a
    assert [a.tasks[t].size for t in pol.order_ready(ids, state)] == sorted(sizes(a), reverse=True)


def test_mixed_batch_run_is_verified(adapter, tmp_path):
    cond = Condition("mixed", "B4", None, {}, {"mix": {"small": [3, 32], "big": [1, 64]}, "denoise_iterations": 2,
                                               "order_seeds": {"a": 1}, "binding": "largest_first"}, instance="a")
    rec, _ = _run(adapter, cond, tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True, rec.error
    assert rec.extra["n_tasks"] == 17 and rec.extra["policy"] == "B4_largest_first" and "G" not in rec.extra["tasks_per_pool"]


def test_iters_batch_hidden_cost_and_model():
    from caosched.estimators.profile import StaticProfileEstimator
    from caosched.study2.model import IterModelEstimator, ParamFirstGreedy
    from caosched.study2.workload import build_iters

    d = build_iters([3, 2], [1, 50], side=32, order_seed=5)
    assert len(d) == 4 * 4 + 1 and d.tasks["aggregate"].size == 4
    its = [d.tasks[f"denoise_{i}"].params["iterations"] for i in range(4)]
    assert sorted(its) == [2, 2, 2, 50] and len({t.size for t in d.tasks.values() if t.workload == "img_denoise"}) == 1
    assert all(d.tasks[f"{s}_{i}"].seed == its[i] for i in range(4) for s in ("source", "denoise", "edges", "features"))
    base = StaticProfileEstimator({(w, 1024, p): 0.01 for w in ("img_source", "img_edges", "img_features") for p in ("P", "E")}
                                  | {("img_denoise", 1024, p): 0.05 for p in ("P", "E")})
    est = IterModelEstimator(base, {"P": [0.001, 0.002], "E": [0.002, 0.006]})
    big = next(d.tasks[f"denoise_{i}"] for i in range(4) if its[i] == 50)
    assert abs(est.estimate(big, "P") - 0.101) < 1e-9 and abs(est.estimate(big, "E") - 0.302) < 1e-9
    assert est.estimate(d.tasks["edges_0"], "P") == 0.01                   # other stages: the solo table
    pol = ParamFirstGreedy(None, ["P", "E"], name="x")
    state = _late_fixture()[1]
    state.dag = d
    pol.on_run_start(d, state)
    first = pol.order_ready([f"edges_{i}" for i in range(4)] + [f"source_{i}" for i in range(4)], state)[0]
    assert its[int(first.rsplit("_", 1)[1])] == 50                          # the big chain's tasks come first


def test_param_model_finds_its_own_features_and_never_guesses():
    from caosched.study2.param_model import ParamModelEstimator, feature_names, fit_group

    rows = [{"iterations": n, "radius": 2.0, "seed": s, "width": 8} for n, s in ((2, 1), (50, 2), (120, 3), (2, 4), (120, 5))]
    assert feature_names(rows) == ["iterations"]                      # radius is constant, seed and width are never features
    g = fit_group(rows, [0.001 + 0.002 * r["iterations"] for r in rows])
    assert abs(g["coef"][0] - 0.001) < 1e-6 and abs(g["coef"][1] - 0.002) < 1e-6 and g["mae_s"] < 1e-9
    est = ParamModelEstimator({"w|P": g})
    task = _late_fixture()[0].tasks["run"].__class__("t", "w", 1, params={"iterations": 10})
    assert abs(est.estimate(task, "P") - 0.021) < 1e-6
    with pytest.raises(KeyError, match="retrain"):
        est.estimate(task, "R_PI")                                   # a pool the model never saw is an error, not a guess


def test_policy_decision_time_stays_inside_the_budget():
    """Every study 2 policy must decide in well under a millisecond per task on 14 workers and a full activity history. This test
    would have failed the three implementation costs found in study 2 (context logging with long worker histories, the replay
    oracle's per-call median, and a heavy model such as CatBoost called once per candidate)."""
    import time

    from caosched.core.dag import DAG
    from caosched.core.runtime_state import RuntimeState
    from caosched.core.task import Task
    from caosched.estimators.profile import StaticProfileEstimator
    from caosched.study2.policies import EftNoContext, PredictedRankGreedy, RankEftNoContext
    from caosched.util import clock

    tasks = {f"t{i}": Task(f"t{i}", "w", 1, eligible_pools=("P", "E")) for i in range(60)}
    dag = DAG(tasks)
    workers = {**{f"P{i}": "P" for i in range(6)}, **{f"E{i}": "E" for i in range(7)}, "G0": "G"}
    state = RuntimeState(dag, workers)
    now = clock.now()
    for w in state.workers.values():                                  # a full 256-interval history per worker
        for k in range(256):
            w.history.append((now - 5 - k * 0.01, now - 5 - k * 0.01 + 0.005))
    for i in range(6):
        state.mark_submitted(f"P{i}", f"t{i}", now)
    est = StaticProfileEstimator({("w", 1, "P"): 0.05, ("w", 1, "E"): 0.15})
    for pol in (EftNoContext(est, "a"), RankEftNoContext(est, "b"), PredictedRankGreedy(est, "c"),
                PredictedRankGreedy(est, "d", hold_min_s=0.010)):
        pol.on_run_start(dag, state)
        t0 = time.perf_counter()
        for i in range(6, 60):
            pol.select_worker(dag.tasks[f"t{i}"], state)
        per_call = (time.perf_counter() - t0) / 54
        assert per_call < 5e-4, f"{pol.name}: {per_call * 1e3:.2f} ms per decision (budget 0.5 ms)"


def test_scheduling_cost_guard_flags_a_run_dominated_by_the_policy(adapter, tmp_path):
    rec, _ = _run(adapter, _cond("guard", max_scheduling_fraction=1e-9), tmp_path, 0)
    assert rec.status == "failed" and "scheduling time" in (rec.error or "") and rec.extra["scheduling_fraction"] > 1e-9


def test_session_aborts_on_battery_when_the_design_requires_mains(tmp_path):
    import json

    from caosched.experiment.runner import run_session
    from caosched.experiment.stub import StubAdapter

    design = tmp_path / "d.json"
    design.write_text(json.dumps({"name": "x", "evidence_label": "plan", "seed": 1, "n_blocks": 2, "min_free_ram_gb": 0.0,
                                  "require_ac_power": True, "conditions": [{"name": "a", "policy": "p"}]}))
    s = run_session(design, tmp_path / "out", StubAdapter(), session_id="s", free_fn=lambda: 99.0, power_fn=lambda: False)
    assert s["status"] == "aborted" and "mains" in s["reason"]
    ok = run_session(design, tmp_path / "out", StubAdapter(), session_id="s2", free_fn=lambda: 99.0, power_fn=lambda: True)
    assert ok["status"] == "complete"


def test_hold_policy_waits_for_a_much_faster_busy_worker_only(monkeypatch):
    from caosched.estimators.profile import StaticProfileEstimator
    from caosched.study2.policies import PredictedRankGreedy
    from caosched.util import clock

    dag, state, _ = _late_fixture()
    est = StaticProfileEstimator({("w", 1, "P"): 0.100, ("w", 1, "E"): 0.400})
    pol = PredictedRankGreedy(est, "hold", hold_min_s=0.010)
    pol.on_run_start(dag, state)
    state.mark_submitted("P0", "run", clock.now())                    # P0 busy, predicted free in about 0.1 s; E0 idle
    pol.order_ready(["new"], state)                                   # the per-pass cache (the coordinator calls this first)
    assert pol.select_worker(dag.tasks["new"], state) is None         # waiting 0.1 + 0.1 s beats 0.4 s on E0 by far more than 10 ms
    est.table[("w", 1, "E")] = 0.105                                  # now E0 is only 5 ms worse than waiting for P0: take it
    pol.order_ready(["new"], state)
    assert pol.select_worker(dag.tasks["new"], state) == "E0"
    nohold = PredictedRankGreedy(est, "greedy")
    nohold.on_run_start(dag, state)
    assert nohold.select_worker(dag.tasks["new"], state) == "E0"      # the work-conserving variant never holds


def test_classes_batch_and_two_factor_model():
    from caosched.study2.model import CostFirstGreedy
    from caosched.study2.param_model import ParamModelEstimator, feature_names, fit_group
    from caosched.study2.workload import build_classes

    d = build_classes([[3, 32, 2], [1, 64, 50]], order_seed=4)
    assert len(d) == 4 * 4 + 1 and d.tasks["aggregate"].size == 4
    pairs = sorted((d.tasks[f"source_{i}"].size, d.tasks[f"denoise_{i}"].params["iterations"]) for i in range(4))
    assert pairs == [(1024, 2)] * 3 + [(4096, 50)]

    # the model finds size, iterations AND their product, and recovers cost = a + b*size*iterations exactly
    rows = [{"iterations": n, "size": s, "seed": 1} for s in (1024, 4096, 16384) for n in (2, 20, 100)]
    y = [0.002 + 3e-9 * r["size"] * r["iterations"] for r in rows]
    assert feature_names(rows) == ["iterations", "size", "iterations*size"]
    g = fit_group(rows, y)
    assert g["mae_s"] < 1e-9
    est = ParamModelEstimator({"w|P": g})
    task = d.tasks["denoise_0"].__class__("t", "w", 8192, params={"iterations": 40})   # a combination between grid points
    assert abs(est.estimate(task, "P") - (0.002 + 3e-9 * 8192 * 40)) < 1e-6

    pol = CostFirstGreedy(None, ["P", "E"], name="x")
    state = _late_fixture()[1]
    state.dag = d
    pol.on_run_start(d, state)
    first = pol.order_ready([f"edges_{i}" for i in range(4)], state)[0]
    assert (d.tasks[f"source_{first.rsplit('_', 1)[1]}"].size, d.tasks[f"denoise_{first.rsplit('_', 1)[1]}"].params["iterations"]) == (4096, 50)
