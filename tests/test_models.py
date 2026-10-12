"""Stage 3 predictors (CatBoost, MLP), evaluation helpers, splits and the model-selection rule.
Synthetic rows are test fixtures with a KNOWN interference law, not data."""
import csv
import json
import math
import random
import tracemalloc

import numpy as np
import pytest

from caosched.analysis.model_eval import (
    accuracy_metrics, calibration_deciles, evaluate, latency_distribution, load_rows, measured, replay_online,
    select_model,
)
from caosched.dataset.build import build_dataset, make_splits
from caosched.dataset.splits import folds
from caosched.estimators import (
    BaseProfileMismatchError, CatBoostEstimator, EstimateContext, MlpEstimator, MovingHistoryEstimator,
    StaticProfileEstimator, build_estimator, load_tabular,
)
from caosched.estimators.base import TaskSpec

BASE_S = {("matmul", 64, "P"): 0.010, ("matmul", 64, "E"): 0.020, ("matmul", 128, "P"): 0.080, ("matmul", 128, "E"): 0.160}


@pytest.fixture
def profile(tmp_path):
    p = tmp_path / "20261003T100000_profile.json"
    p.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": [
        {"workload": w, "size": s, "pool": pool, "median_s": v} for (w, s, pool), v in BASE_S.items()]}))
    return p


def _rows(n, instance, seed):
    """kernel = E1 * exp(0.25 * busy_E + 0.15 * busy_R + 0.4 * (1 - target_busy_frac)) exactly (noise-free)."""
    r = random.Random(seed)
    out = []
    for i in range(n):
        wl, size, pool = "matmul", r.choice([64, 128]), r.choice(["P", "E"])
        be, br, frac = r.randint(0, 6), r.randint(0, 2), r.choice([0.0, 0.5, 1.0])
        ctx = EstimateContext.build(r.randint(0, 2), be, ["matmul"] * be, frac, {"R": br})
        k = BASE_S[(wl, size, pool)] * math.exp(0.25 * be + 0.15 * br + 0.4 * (1 - frac))
        t0 = i * 0.01
        out.append({"workload": wl, "size": size, "pool": pool, "kernel_s": k, "ctx": ctx, "source_log": f"{instance}/run{i // 40}",
                    "task_id": f"{instance}_{i}", "session_id": "campaign_20261003T120000", "instance": instance,
                    "t_dispatched_rel": t0, "t_completed_rel": t0 + k})
    return out


CB = {"iterations": 150, "depth": 4, "learning_rate": 0.2}
MLP = {"hidden": [16, 16], "epochs": 60, "lr": 0.01, "weight_decay": 0.0, "batch_size": 64}


def _mae(est, rows):
    return float(np.mean([abs(est.estimate(TaskSpec(r["task_id"], r["workload"], r["size"]), r["pool"], r["ctx"]) - r["kernel_s"])
                          for r in rows]))


# --- metrics -----------------------------------------------------------------------

def test_accuracy_metrics_known_values():
    m = accuracy_metrics([1, 2, 4], [1.5, 2, 3])
    assert m["mae_s"] == pytest.approx(0.5) and m["rmse_s"] == pytest.approx(math.sqrt(1.25 / 3))
    assert m["bias_s"] == pytest.approx(-0.5 / 3) and m["mape"] == pytest.approx(0.25) and m["median_ape"] == pytest.approx(0.25)
    assert m["relative_mae"] == pytest.approx(0.5 / (7 / 3))
    assert "small" in m["mape_note"] and "median_ape" in m["mape_note"] and "mape_above_floor" not in m
    f = accuracy_metrics([1, 2, 4], [1.5, 2, 3], mape_floor_s=2)       # only y >= 2: APE 0 and 0.25
    assert f["n_above_floor"] == 2 and f["mape_above_floor"] == pytest.approx(0.125) and f["mape"] == pytest.approx(0.25)
    with pytest.raises(ValueError):
        accuracy_metrics([0.0, 1.0], [1.0, 1.0])


def test_calibration_deciles_and_latency_distribution():
    y = np.arange(1.0, 101.0)
    bins = calibration_deciles(y, y * 2)
    assert len(bins) == 10 and all(b["n"] == 10 for b in bins)
    assert all(b["mean_predicted_s"] == pytest.approx(2 * b["mean_observed_s"]) for b in bins)
    assert len(calibration_deciles([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])) == 3
    lat = latency_distribution(lambda i: sum(range(100)), 50)
    assert lat["n_calls"] == 50 and 0 < lat["p50_us"] <= lat["p90_us"] <= lat["p99_us"] <= lat["max_us"]


def test_replay_online_uses_only_completions_before_the_decision():
    base = StaticProfileEstimator({("matmul", 64, "P"): 1.0})

    def row(i, d, c, k):
        return {"task_id": f"t{i}", "workload": "matmul", "size": 64, "pool": "P", "kernel_s": k, "ctx": None,
                "t_dispatched_rel": d, "t_completed_rel": c}
    rows = [row(0, 0.0, 1.0, 5.0), row(1, 2.0, 4.0, 7.0), row(2, 0.5, 3.0, 9.0)]
    p = replay_online(MovingHistoryEstimator(base, window=1), rows)
    # t0 and t2 are decided before anything completed; t1 (t=2) sees t0's 5.0 but not t2's (done at 3.0)
    assert list(p) == [1.0, 5.0, 1.0]


def test_measured_times_the_untraced_call_and_traces_a_second_call_only_on_request():
    seen = []
    res, m = measured(lambda: seen.append(tracemalloc.is_tracing()) or "r", memory=False)
    assert res == "r" and seen == [False] and m["tracemalloc_peak_bytes"] is None and m["seconds"] >= 0
    seen.clear()
    _, m = measured(lambda: seen.append(tracemalloc.is_tracing()) or bytearray(100_000))
    assert seen == [False, True] and m["tracemalloc_peak_bytes"] >= 100_000


def test_select_model_rule():
    models = [{"name": "ridge", "complexity": 1}, {"name": "catboost", "complexity": 2}, {"name": "mlp", "complexity": 3}]

    def pair(s, c, lo):
        return {"simple": s, "complex": c, "diff_mean": lo + 0.01, "diff_lo": lo, "diff_hi": lo + 0.02}
    pairs = [pair("ridge", "catboost", 0.01), pair("ridge", "mlp", 0.03), pair("catboost", "mlp", -0.02)]
    rec = select_model(models, pairs, margin=0.0)
    assert rec["selected"] == "catboost"                       # ridge is significantly worse; catboost is not worse than mlp
    assert select_model(models, pairs, margin=0.06)["selected"] == "ridge"   # CI upper bounds (0.03, 0.05) within the margin
    worse = [pair("ridge", "catboost", 0.01), pair("ridge", "mlp", 0.03), pair("catboost", "mlp", 0.02)]
    assert select_model(models, worse, 0.0)["selected"] == "mlp"             # nothing cheaper qualifies
    with pytest.raises(KeyError, match="no scheduling comparison"):
        select_model(models, pairs[:2], 0.0)
    # "not worse" needs the CI UPPER bound within the margin: a CI straddling the margin keeps the complex model
    def ci(s, c, lo, hi):
        return {"simple": s, "complex": c, "diff_mean": (lo + hi) / 2, "diff_lo": lo, "diff_hi": hi}
    two = models[:2]
    assert select_model(two, [ci("ridge", "catboost", -0.01, 0.01)], 0.0)["selected"] == "catboost"   # straddles 0
    assert select_model(two, [ci("ridge", "catboost", -0.03, -0.001)], 0.0)["selected"] == "ridge"    # clearly not worse
    assert select_model(two, [ci("ridge", "catboost", -0.01, 0.01)], 0.01)["selected"] == "ridge"     # hi == margin: within
    assert select_model(two, [ci("ridge", "catboost", 0.02, 0.04)], 0.0)["checks"][0]["against"][0]["not_worse"] is False


# --- predictors ---------------------------------------------------------------------

@pytest.mark.parametrize("cls,params", [(CatBoostEstimator, CB), (MlpEstimator, MLP)])
def test_models_learn_interference_and_beat_the_profile(profile, tmp_path, cls, params):
    base = StaticProfileEstimator.from_file(profile)
    train, test = _rows(600, "i1", 1) + _rows(600, "i2", 2), _rows(300, "i3", 3)
    m = cls.fit(train, base, params, seed=0)
    e1 = _mae(base, test)
    assert _mae(m, test) < 0.5 * e1                              # held-out instance, known law
    assert m.uses_context and m.estimate(TaskSpec("x", "matmul", 64), "P", None) > 0   # ctx=None allowed (imputed)
    # R occupancy is a feature (audit D7): same task, busier remote pool -> slower
    t = TaskSpec("x", "matmul", 64)
    lo = m.estimate(t, "E", EstimateContext.build(0, 3, ["matmul"] * 3, 1.0, {"R": 0}))
    hi = m.estimate(t, "E", EstimateContext.build(0, 3, ["matmul"] * 3, 1.0, {"R": 2}))
    assert hi > lo


@pytest.mark.parametrize("cls,params", [(CatBoostEstimator, CB), (MlpEstimator, MLP)])
def test_models_are_deterministic_and_roundtrip_with_profile_binding(profile, tmp_path, cls, params):
    base = StaticProfileEstimator.from_file(profile)
    train, test = _rows(200, "i1", 1), _rows(30, "i2", 2)
    a, b = cls.fit(train, base, params, seed=7), cls.fit(train, base, params, seed=7)
    pa, pb = a.estimate_many(test), b.estimate_many(test)
    assert np.allclose(pa, pb, rtol=0, atol=0)                   # same seed -> identical predictions
    a.save(tmp_path / "m.json")
    loaded = load_tabular(tmp_path / "m.json")
    assert loaded.base.source == str(profile) and loaded.name == a.name
    assert np.allclose(loaded.estimate_many(test), pa, rtol=1e-9)
    one = [a.estimate(TaskSpec("x", r["workload"], r["size"]), r["pool"], r["ctx"]) for r in test]
    assert np.allclose(one, pa, rtol=1e-9)                       # per-call == batch path
    # profile binding (same rules as E4): a profile with other measurements is refused
    other = tmp_path / "20261003T150000_profile.json"
    other.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": [
        {"workload": w, "size": s, "pool": p, "median_s": v * 1.3} for (w, s, p), v in BASE_S.items()]}))
    with pytest.raises(BaseProfileMismatchError, match="fitted against"):
        load_tabular(tmp_path / "m.json", base=StaticProfileEstimator.from_file(other))
    assert load_tabular(tmp_path / "m.json", base=StaticProfileEstimator.from_file(profile)).base.source == str(profile)
    d = json.loads((tmp_path / "m.json").read_text())
    d["base_profile"] = ""
    (tmp_path / "bad.json").write_text(json.dumps(d))
    with pytest.raises(ValueError, match="no usable base_profile"):
        load_tabular(tmp_path / "bad.json")
    # estimator ladder access: build_estimator, including the online recalibration wrapper
    est = build_estimator("CatBoost" if cls is CatBoostEstimator else "MLP", profile, model_path=tmp_path / "m.json")
    assert est.estimate(TaskSpec("x", "matmul", 64), "P", test[0]["ctx"]) > 0
    rc = build_estimator(("CatBoost" if cls is CatBoostEstimator else "MLP") + "+rc", profile, model_path=tmp_path / "m.json")
    assert rc.uses_context
    with pytest.raises(ValueError, match="needs model_path"):
        build_estimator("MLP", profile)


def test_unseen_pool_or_workload_is_an_error_and_pool_counts_are_kept():
    from caosched.estimators.tabular import encode
    base = StaticProfileEstimator(dict(BASE_S))
    rows = _rows(60, "i", 1)   # executing pools P/E; "R" occurs only as a co-runner pool (busy_other)
    m = CatBoostEstimator.fit(rows, base, CB, 0)
    assert m.spec["n_rows_by_pool"] == {p: sum(r["pool"] == p for r in rows) for p in ("E", "P")}
    assert "R" in m.spec["pools"]
    for wl, pool in (("matmul", "R"), ("zzz", "P")):
        with pytest.raises(ValueError, match="no training rows"):
            encode(m.spec, wl, 64, pool, 0.01, None)
    assert encode(m.spec, "matmul", 64, "P", 0.01, None).shape[0] == len(m.describe()["features"])


def test_catboost_params_may_not_override_the_fixed_reproducibility_settings():
    base = StaticProfileEstimator(dict(BASE_S))
    for bad in ("random_seed", "thread_count"):
        with pytest.raises(ValueError, match="must not set"):
            CatBoostEstimator.fit(_rows(20, "i", 1), base, {**CB, bad: 1}, 0)


def test_unprofiled_base_has_no_source_cannot_be_saved():
    base = StaticProfileEstimator(dict(BASE_S))
    m = CatBoostEstimator.fit(_rows(60, "i", 1), base, CB, 0)
    with pytest.raises(ValueError, match="no source file"):
        m.save("unused.json")


# --- splits -------------------------------------------------------------------------

def _split_rows():
    rows = []
    for inst, sess in (("a", "s1"), ("b", "s1"), ("c", "s2")):
        for run in range(4):
            for size in (64, 128):
                rows.append({"instance": inst, "session_id": sess, "source_log": f"{inst}/{run}", "size": size})
    return rows


def test_split_policies_hold_out_whole_groups():
    rows = _split_rows()
    loo = folds(rows, {"policy": "instance", "leave_one_out": True})
    assert [f[0] for f in loo] == ["instance:a", "instance:b", "instance:c"]
    for name, train, test in loo:
        held = name.split(":")[1]
        assert {r["instance"] for r in test} == {held} and held not in {r["instance"] for r in train}
    (_, tr, te), = folds(rows, {"policy": "instance", "test": ["a", "b"]})
    assert {r["instance"] for r in te} == {"a", "b"} and {r["instance"] for r in tr} == {"c"}
    (_, tr, te), = folds(rows, {"policy": "session", "test": "s2"})
    assert {r["session_id"] for r in te} == {"s2"} and "s2" not in {r["session_id"] for r in tr}
    # every run here has both sizes: the size cut straddles runs -> refused unless explicitly allowed
    # (this used to be accepted silently with the same run in train and test)
    with pytest.raises(ValueError, match="both train and test"):
        folds(rows, {"policy": "size", "test": [128]})
    (_, tr, te), = folds(rows, {"policy": "size", "test": [128], "allow_straddle": True})
    assert {r["size"] for r in te} == {128} and {r["size"] for r in tr} == {64}
    by_size = [dict(r, source_log=f"{r['source_log']}@{r['size']}") for r in rows]   # runs of one size only: no straddle
    (_, tr, te), = folds(by_size, {"policy": "size", "test": [128]})
    assert {r["size"] for r in te} == {128} and {r["size"] for r in tr} == {64}
    (_, tr, te), = folds(rows, {"policy": "time", "train_fraction": 0.5})
    assert not ({r["source_log"] for r in tr} & {r["source_log"] for r in te})
    # per session, in collection order: s1 = a/0..a/3, b/0..b/3 (first 4 train); s2 = c/0..c/3 (first 2 train)
    assert {r["source_log"] for r in te} == {"b/0", "b/1", "b/2", "b/3", "c/2", "c/3"}
    with pytest.raises(ValueError, match="random row splits"):
        folds(rows, {"policy": "random"})
    with pytest.raises(ValueError, match="empty"):
        folds(rows, {"policy": "instance", "test": ["zzz"]})


def test_time_split_orders_runs_by_collection_order_not_file_name():
    def runs(names_in_time_order, extra):  # file names sort OPPOSITE to collection order
        return [{"instance": "i", "session_id": "s", "source_log": n, "size": 64, **extra(k)}
                for k, n in enumerate(names_in_time_order) for _ in range(2)]
    names = ["z_first", "y_second", "x_third", "w_fourth"]
    for extra in (lambda k: {"order_index": str(k)},                       # csv strings, like tasks.csv
                  lambda k: {"order_index": "", "timestamp_epoch": 1.8e9 + 100 * k}):   # epoch fallback
        (_, tr, te), = folds(runs(names, extra=extra), {"policy": "time", "train_fraction": 0.5})
        assert {r["source_log"] for r in tr} == {"z_first", "y_second"} and {r["source_log"] for r in te} == {"x_third", "w_fourth"}
    # file name is only the last tie-break
    (_, tr, te), = folds(runs(names, extra=lambda k: {}), {"policy": "time", "train_fraction": 0.5})
    assert {r["source_log"] for r in tr} == {"w_fourth", "x_third"}


def test_split_refuses_rows_without_group_key_and_supports_occupancy():
    rows = _split_rows() + [{"instance": "", "session_id": None, "source_log": "orphan", "size": 64}]
    with pytest.raises(ValueError, match="empty 'instance'"):
        folds(rows, {"policy": "instance", "leave_one_out": True})
    with pytest.raises(ValueError, match="empty 'session_id'"):
        folds(rows, {"policy": "session", "test": "s1"})
    with pytest.raises(ValueError, match="empty 'session_id'"):
        folds(rows, {"policy": "time", "train_fraction": 0.5})
    occ = [{"source_log": f"r{i}", "busy_total": str(b), "size": 64} for i, b in enumerate([0, 2, 4, 5, 7])]  # csv strings
    (name, tr, te), = folds(occ, {"policy": "occupancy", "threshold": 4})
    assert name == "occupancy:>4" and [r["busy_total"] for r in tr] == ["0", "2", "4"] and [r["busy_total"] for r in te] == ["5", "7"]
    mixed = [dict(r, source_log="same") for r in occ]                     # one run on both sides
    with pytest.raises(ValueError, match="both train and test"):
        folds(mixed, {"policy": "occupancy", "threshold": 4})
    assert len(folds(mixed, {"policy": "occupancy", "threshold": 4, "allow_straddle": True})) == 1


def test_make_splits_adds_leave_instance_out_and_time_ordered():
    # session_runs arrive in COLLECTION order (build_dataset sorts by order_index/epoch); make_splits must not
    # re-sort by name (this used to pass ["l4", "l3", "l2", "l1"] and expect name order)
    sp = make_splits({"phase2_x", "campaign_1"}, {"matmul": {64, 128}}, {"campaign_1": ["c4", "c3", "c2", "c1"]},
                     instances={"i1": ["l1", "l2"], "i2": ["l3"]},
                     session_runs={"phase2_x": ["l4", "l3", "l2", "l1"]}, train_fraction=0.5)
    assert [f["held_out"] for f in sp["leave_instance_out"]["folds"]] == ["i1", "i2"]
    f1 = sp["leave_instance_out"]["folds"][0]
    assert f1["test_runs"] == ["l1", "l2"] and f1["train_runs"] == ["l3"]
    t = sp["time_ordered_within_session"]["sessions"]["phase2_x"]
    assert t["train_runs"] == ["l4", "l3"] and t["test_runs"] == ["l2", "l1"]
    # train_fraction is honoured by the campaign split too, in the given order, and splits.json says so
    c = sp["by_run_within_latest_campaign"]
    assert c["train_runs"] == ["c4", "c3"] and c["test_runs"] == ["c2", "c1"] and c["train_fraction"] == 0.5 and "50%" in c["rule"]
    assert sp["by_occupancy"]["split_spec"] == {"policy": "occupancy", "threshold": 4}
    assert "random" in sp["forbidden"]


# --- dataset loading and the evaluation driver -----------------------------------------

def test_load_rows_requires_decision_context_and_evaluate_scores_held_out_only(profile, tmp_path):
    base = StaticProfileEstimator.from_file(profile)
    rows = _rows(300, "i1", 1) + _rows(300, "i2", 2) + _rows(300, "i3", 3)
    cfg = {"seed": 0, "split": {"policy": "instance", "leave_one_out": True}, "e3_window": 4,
           "rc": {"alpha": 0.3, "min_obs": 1, "clamp": [0.5, 3.0]},
           "ridge": {"ridge_lambda": 1.0, "min_rows": 10, "feature_set": "occupancy+history"},
           "catboost": {"iterations": 30, "depth": 3, "learning_rate": 0.3}, "mlp": {**MLP, "epochs": 5},
           "latency": {"n_calls": 20}}
    out = tmp_path / "eval"
    metrics = evaluate(rows, base, cfg, out)
    assert metrics["folds"] == ["instance:i1", "instance:i2", "instance:i3"]
    assert set(metrics["models"]) == {"E1", "E3", "E1+rc", "Ridge", "CatBoost", "MLP"}
    for name, m in metrics["models"].items():
        assert m["overall"]["n"] == 900                          # every row is scored exactly once, by a model that did not train on it
        assert set(m["per_fold"]) == set(metrics["folds"]) and len(m["calibration_deciles"]) == 10
        assert m["inference_latency"]["p50_us"] > 0 and "by_workload" in m and "by_pool" in m
    for name in ("Ridge", "CatBoost", "MLP"):
        m = metrics["models"][name]
        assert m["model_size_bytes"] > 0 and m["train_seconds"] > 0 and m["n_train_rows"] == 600
        # per-fold training record + the saved file is labelled as the LAST fold's model
        assert set(m["train_per_fold"]) == set(metrics["folds"])
        assert all(v["n_train_rows"] == 600 and v["n_train_rows_by_pool"] and v["train_seconds"] > 0
                   for v in m["train_per_fold"].values())
        assert m["train_tracemalloc_peak_bytes"] is None             # measure_memory not requested: fit timed untraced, once
        assert m["saved_model"]["fitted_on_fold"] == "instance:i3" and "fold model" in m["saved_model"]["note"]
        assert json.loads((out / f"model_{name}.json").read_text())["meta"]["fitted_on_fold"] == "instance:i3"
    assert metrics["models"]["E1"]["overall"]["mape_note"] and metrics["models"]["E1"]["headline_relative_error"] == "median_ape"
    for p in ("predictions_E1.csv", "predictions_E1_rc.csv", "predictions_CatBoost.csv", "model_CatBoost.json", "metrics.json"):
        assert (out / p).exists()
    with (out / "predictions_MLP.csv").open(encoding="utf-8") as fh:
        got = list(csv.DictReader(fh))
    assert len(got) == 900 and {g["fold"] for g in got} == set(metrics["folds"])
    for g in got:                                                # fold i held out => instance i only in its own fold
        assert g["fold"] == "instance:" + g["instance"]


def test_load_rows_drops_non_decision_rows(tmp_path):
    root = tmp_path / "data" / "events" / "phase2_20261003T115816"
    root.mkdir(parents=True)
    ctx = {"busy_P": 1, "busy_E": 0, "corunning": {"matmul": 1}, "target_busy_frac": 1.0, "busy_other": {"R": 2}}
    ev = [{"seq": 0, "t": 0.0, "event": "run_started", "run_id": "r", "scheduler": "s", "scheduler_config": {},
           "metadata": {"experiment_id": "phase2_20261003T115816", "trace": "inst1"},
           "tasks": {t: {"workload": "matmul", "size": 64, "seed": i} for i, t in enumerate("ab")}},
          {"seq": 1, "t": 0.1, "event": "task_ready", "task_id": "a"},
          {"seq": 2, "t": 0.2, "event": "task_dispatched", "task_id": "a", "worker_id": "P0", "pool": "P",
           "decision": {"ctx_version": 2, "candidates": {"P0": {"ctx": ctx}}}},
          {"seq": 3, "t": 0.3, "event": "task_completed", "task_id": "a", "worker_id": "P0", "pool": "P",
           "t_started": 0.25, "t_completed": 0.5, "wall_time_seconds": 0.2},
          {"seq": 4, "t": 0.31, "event": "task_ready", "task_id": "b"},
          {"seq": 5, "t": 0.32, "event": "task_dispatched", "task_id": "b", "worker_id": "P0", "pool": "P"},
          {"seq": 6, "t": 0.7, "event": "task_completed", "task_id": "b", "worker_id": "P0", "pool": "P",
           "t_started": 0.6, "t_completed": 0.7, "wall_time_seconds": 0.1},
          {"seq": 7, "t": 0.8, "event": "run_finished", "status": "completed"}]
    (root / "r.jsonl").write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    (tmp_path / "data" / "profiles").mkdir()
    out = build_dataset(tmp_path / "data" / "events", tmp_path / "data" / "profiles", tmp_path / "data" / "datasets",
                        context_source="auto")  # explicit opt-in: the default is 'decision'
    m = json.loads((out / "manifest.json").read_text())
    assert m["rows_per_ctx_source"] == {"decision": 1, "start": 1} and m["context_source"] == "auto"
    default = json.loads((build_dataset(tmp_path / "data" / "events", tmp_path / "data" / "profiles",
                                        tmp_path / "data" / "datasets2") / "manifest.json").read_text())
    assert default["context_source"] == "decision" and default["rows_per_ctx_source"] == {"decision": 1}   # default drops start rows
    rows, info = load_rows(out, require_decision_context=True)
    assert [r["task_id"] for r in rows] == ["a"] and info == {"dropped": 1}
    assert rows[0]["ctx"].busy_by_pool == {"P": 1, "E": 0, "R": 2} and rows[0]["ctx"].busy_total == 3
    allrows, _ = load_rows(out, require_decision_context=False)
    assert len(allrows) == 2
    tasks = list(csv.DictReader((out / "tasks.csv").open(encoding="utf-8")))
    assert tasks[0]["busy_R"] == "2" and tasks[0]["busy_total"] == "3" and tasks[0]["instance"] == "inst1"


def test_evaluate_models_cli_end_to_end(profile, tmp_path, monkeypatch, capsys):
    """scripts/evaluate_models.py on a dataset built from logs: profile-predates-session guard, thresholds from JSON, selection record."""
    import importlib.util
    import pathlib
    root = tmp_path / "data" / "events" / "phase2_20261003T115816"
    root.mkdir(parents=True)
    r = random.Random(5)
    for inst in ("i1", "i2"):
        ev = [{"seq": 0, "t": 0.0, "event": "run_started", "run_id": inst, "scheduler": "s", "scheduler_config": {},
               "metadata": {"experiment_id": "phase2_20261003T115816", "trace": inst},
               "tasks": {f"t{i}": {"workload": "matmul", "size": 64, "seed": i} for i in range(40)}}]
        for i in range(40):
            pool, wid, be = ("P", "P0", r.randint(0, 5)) if i % 2 else ("E", "E0", r.randint(0, 5))
            k = BASE_S[("matmul", 64, pool)] * math.exp(0.2 * be)
            t0 = 1.0 + i
            ctx = {"busy_P": 0, "busy_E": be, "corunning": {"matmul": be} if be else {}, "target_busy_frac": 1.0}
            ev += [{"seq": 3 * i + 1, "t": t0, "event": "task_ready", "task_id": f"t{i}"},
                   {"seq": 3 * i + 2, "t": t0 + 0.001, "event": "task_dispatched", "task_id": f"t{i}", "worker_id": wid,
                    "pool": pool, "decision": {"ctx_version": 2, "candidates": {wid: {"ctx": ctx}}}},
                   {"seq": 3 * i + 3, "t": t0 + 0.5, "event": "task_completed", "task_id": f"t{i}", "worker_id": wid, "pool": pool,
                    "t_started": t0 + 0.002, "t_completed": t0 + 0.002 + k, "wall_time_seconds": k}]
        ev.append({"seq": 999, "t": 99.0, "event": "run_finished", "status": "completed"})
        (root / f"{inst}.jsonl").write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    (tmp_path / "data" / "profiles").mkdir()
    ds = build_dataset(tmp_path / "data" / "events", tmp_path / "data" / "profiles", tmp_path / "data" / "datasets")
    cfg = {"seed": 0, "split": {"policy": "instance", "leave_one_out": True}, "require_decision_context": True,
           "e3_window": 4, "rc": {"alpha": 0.3, "min_obs": 1, "clamp": [0.5, 3.0]},
           "ridge": {"ridge_lambda": 1.0, "min_rows": 10, "feature_set": "occupancy+history"},
           "catboost": {"iterations": 20, "depth": 2, "learning_rate": 0.3}, "latency": {"n_calls": 10},
           "selection": {"margin": 0.0}}
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    (tmp_path / "sched.json").write_text(json.dumps({
        "models": [{"name": "Ridge", "complexity": 1}, {"name": "CatBoost", "complexity": 2}],
        "pairs": [{"simple": "Ridge", "complex": "CatBoost", "diff_mean": 0.0, "diff_lo": -0.01, "diff_hi": 0.01}]}))
    spec = importlib.util.spec_from_file_location("evaluate_models", pathlib.Path(__file__).parents[1] / "scripts" / "evaluate_models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    argv = ["x", "--dataset", str(ds), "--profile", str(profile), "--config", str(tmp_path / "cfg.json"),
            "--out", str(tmp_path / "out"), "--scheduling", str(tmp_path / "sched.json")]
    monkeypatch.setattr("sys.argv", argv)
    mod.main()
    m = json.loads((tmp_path / "out" / "metrics.json").read_text())
    assert m["dataset"]["n_rows_used"] == 80 and m["models"]["CatBoost"]["overall"]["n"] == 80
    # CI [-0.01, 0.01] straddles margin 0: "Ridge not worse" cannot be established -> the more complex model is chosen
    # (this assertion used to expect Ridge under the wrong diff_lo <= margin rule)
    rec = json.loads((tmp_path / "out" / "selection_record.json").read_text())
    assert rec["selected"] == "CatBoost" and rec["rows_per_ctx_source"] == {"decision": 80}
    assert m["rows_per_ctx_source"] == {"decision": 80} and m["models"]["CatBoost"]["saved_model"]["fitted_on_fold"] == "instance:i2"
    # require_decision_context=false is refused for these configs unless explicitly allowed (then it is recorded)
    (tmp_path / "cfg_nd.json").write_text(json.dumps({**cfg, "require_decision_context": False}))
    nd = [*argv[:6], str(tmp_path / "cfg_nd.json"), *argv[7:]]
    monkeypatch.setattr("sys.argv", nd)
    with pytest.raises(SystemExit, match="allow_non_decision_context"):
        mod.main()
    (tmp_path / "cfg_nd.json").write_text(json.dumps({**cfg, "require_decision_context": False, "allow_non_decision_context": True}))
    mod.main()
    assert "WARNING" in json.loads((tmp_path / "out" / "metrics.json").read_text())
    monkeypatch.setattr("sys.argv", argv)
    # a profile newer than the earliest session is refused (calibration must predate the data)
    late = tmp_path / "20261231T000000_profile.json"
    late.write_text(profile.read_text())
    monkeypatch.setattr("sys.argv", argv[:4] + [str(late)] + argv[5:])
    with pytest.raises(SystemExit, match="newer than the earliest session"):
        mod.main()
