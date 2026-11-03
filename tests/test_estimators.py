"""Phase 3 estimator ladder: E0, E2, E4, E5 (E1/E3 are covered in
test_schedulers.py) and the decision-time EstimateContext."""
import csv
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

from caosched.core.dag import build_independent_dag
from caosched.core.runtime_state import RuntimeState
from caosched.estimators import (
    AnalyticSizeEstimator, BaseProfileMismatchError, ConstantProfileEstimator, EstimateContext,
    InterferenceRidgeEstimator, ReplayOracleEstimator, StaticProfileEstimator, TaskSpec, build_estimator,
)
from caosched.estimators.learned import FEATURE_SETS, FEATURES, feature_vector
from caosched.estimators.profile_data import load_profile_rows


@pytest.fixture
def profile(tmp_path):
    """Synthetic solo profile obeying t = a * size^3 exactly (matmul)."""
    raw = tmp_path / "x_raw.csv"
    a = {"P": 1e-9, "E": 2.5e-9}
    with raw.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["round", "is_warmup", "workload", "size", "seed", "worker_id", "pool",
                    "logical_processor", "kernel_s", "worker_span_s"])
        for rnd in range(4):
            for size in (100, 200):
                for pool in "PE":
                    w.writerow([rnd, rnd == 0, "matmul", size, 0, pool + "0", pool, 0,
                                a[pool] * size ** 3 * (100.0 if rnd == 0 else 1.0), 0])
    entries = [{"workload": "matmul", "size": s, "pool": p, "median_s": a[p] * s ** 3} for s in (100, 200) for p in "PE"]
    prof = tmp_path / "x_profile.json"
    prof.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "source_csv": raw.name, "entries": entries}))
    return prof


def test_profile_rows_exclude_warmups(profile):
    rows = load_profile_rows(profile)
    assert len(rows) == 3 * 2 * 2 and all(not r["is_warmup"] for r in rows)
    assert len(load_profile_rows(profile, include_warmup=True)) == 16


def test_e0_is_size_blind(profile):
    e0 = ConstantProfileEstimator.from_profile(profile)
    small, big = TaskSpec("a", "matmul", 100), TaskSpec("b", "matmul", 200)
    assert e0.estimate(small, "P") == e0.estimate(big, "P")
    assert e0.estimate(small, "P") < e0.estimate(small, "E")
    with pytest.raises(KeyError):
        e0.estimate(TaskSpec("c", "compression", 1), "P")


def test_e2_recovers_exact_power_law_and_extrapolates(profile):
    e2 = AnalyticSizeEstimator.from_profile(profile, exponents={"matmul": 3.0})
    assert e2.estimate(TaskSpec("t", "matmul", 400), "E") == pytest.approx(2.5e-9 * 400 ** 3, rel=1e-9)
    fitted = AnalyticSizeEstimator.from_profile(profile, fit_exponent=True)
    assert fitted.exponents["matmul"] == pytest.approx(3.0, abs=1e-9)


def test_e2_fit_exponent_needs_two_sizes():
    rows = [{"workload": "matmul", "size": 64, "pool": "P", "kernel_s": 0.01}]
    with pytest.raises(ValueError):
        AnalyticSizeEstimator.fit(rows, fit_exponent=True)


def test_context_from_state_excludes_candidate_and_counts_types():
    dag = build_independent_dag(4)
    dag.tasks["t1"].workload = "compression"
    s = RuntimeState(dag, {"P0": "P", "P1": "P", "E0": "E", "E1": "E"})
    s.mark_submitted("P0", "t0", 0.0)
    s.mark_submitted("E0", "t1", 0.0)
    s.mark_submitted("E1", "t2", 0.0)
    ctx = EstimateContext.from_state(s, exclude_worker="E1")
    assert (ctx.busy_P, ctx.busy_E) == (1, 1)
    assert ctx.corun == {"compression": 1, "matmul": 1}
    assert EstimateContext.from_state(s, None).busy_total == 3


def _synthetic_rows(n=400, seed=0):
    """kernel = E1 * exp(0.05*busy_E + 0.10*corun_matmul) + small noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        be, mm = int(rng.integers(0, 7)), int(rng.integers(0, 3))
        ctx = EstimateContext.build(0, be, ["matmul"] * mm + ["compression"] * max(0, be - mm))
        k = 2.5e-9 * 200 ** 3 * math.exp(0.05 * be + 0.10 * mm + rng.normal(0, 0.01))
        rows.append({"workload": "matmul", "size": 200, "pool": "E", "kernel_s": k, "ctx": ctx})
    return rows


def test_e4_learns_known_interference_slopes(profile, tmp_path):
    base = StaticProfileEstimator.from_file(profile)
    e4 = InterferenceRidgeEstimator.fit(_synthetic_rows(), base, ridge_lambda=1e-6, min_rows=30)
    w = dict(zip(FEATURES, e4.weights[("matmul", "E")]))
    assert w["intercept"] == pytest.approx(0.0, abs=0.01)
    # busy_E and corun_* are collinear in this construction; the *prediction* is what must be right:
    t = TaskSpec("t", "matmul", 200)
    ctx = EstimateContext.build(0, 4, ["matmul", "matmul", "compression", "compression"])
    truth = 2.5e-9 * 200 ** 3 * math.exp(0.05 * 4 + 0.10 * 2)
    assert e4.estimate(t, "E", ctx) == pytest.approx(truth, rel=0.03)
    assert e4.estimate(t, "E", EstimateContext()) == pytest.approx(2.5e-9 * 200 ** 3, rel=0.03)
    # P group had no rows -> falls back to E1 exactly
    assert e4.estimate(t, "P", ctx) == base.lookup("matmul", 200, "P")
    path = tmp_path / "models" / "e4_test.json"
    e4.save(path)
    again = InterferenceRidgeEstimator.load(path, base)
    assert again.estimate(t, "E", ctx) == pytest.approx(e4.estimate(t, "E", ctx))


def test_e4_small_group_falls_back_and_is_reported(profile):
    base = StaticProfileEstimator.from_file(profile)
    e4 = InterferenceRidgeEstimator.fit(_synthetic_rows(n=10), base, min_rows=30)
    assert e4.meta["groups"]["matmul|E"]["fallback_to_E1"] is True
    assert not np.any(e4.weights[("matmul", "E")])


def test_e4_correction_is_clamped(profile):
    base = StaticProfileEstimator.from_file(profile)
    e4 = InterferenceRidgeEstimator(base, {("matmul", "E"): np.array([50.0, 0, 0, 0, 0, 0])},
                                    features=FEATURE_SETS["occupancy"])
    t = TaskSpec("t", "matmul", 200)
    assert e4.estimate(t, "E") == pytest.approx(base.lookup("matmul", 200, "E") * 10.0)


def test_feature_vector_layout():
    ctx = EstimateContext.build(1, 2, ["matmul", "image_filter", "matmul"], target_busy_frac=0.25)
    assert list(feature_vector(ctx)) == [1, 1, 2, 0, 1, 2, 0.25]  # compression, image_filter, matmul, frac
    assert list(feature_vector(ctx, FEATURE_SETS["occupancy"])) == [1, 1, 2, 0, 1, 2]
    unknown = EstimateContext.build(0, 0, [])
    assert feature_vector(unknown, impute={"target_busy_frac": 0.7})[-1] == 0.7


def test_e5_leave_run_out_and_strictness():
    rows = [{"run_id": r, "task_id": "t0", "seed": 7, "workload": "matmul", "size": 64, "pool": "P", "kernel_s": v}
            for r, v in (("r1", 1.0), ("r2", 2.0), ("r3", 9.0))]
    e5 = ReplayOracleEstimator.from_rows(rows)
    t = TaskSpec("t0", "matmul", 64, seed=7)
    assert e5.estimate(t, "P") == 2.0
    e5.exclude_run("r3")
    assert e5.estimate(t, "P") == 1.5
    with pytest.raises(KeyError):
        e5.estimate(t, "E")
    with pytest.raises(KeyError):
        e5.estimate(TaskSpec("t0", "matmul", 64, seed=8), "P")  # different input seed = different task


def test_registry_builds_online_rungs_and_refuses_e5(profile):
    for n in ("E0", "E1", "E2", "E3"):
        assert build_estimator(n, profile).estimate(TaskSpec("t", "matmul", 100), "P") > 0
    with pytest.raises(ValueError):
        build_estimator("E5", profile)


def test_busy_fraction_and_candidate_context():
    dag = build_independent_dag(3)
    s = RuntimeState(dag, {"P0": "P", "E0": "E"})
    s.record_activity("P0", 9.0, 9.25)       # busy 0.25 s inside the window [9.0, 9.5]
    assert s.busy_fraction("P0", now=9.5, window=0.5) == pytest.approx(0.5)
    assert s.busy_fraction("P0", now=20.0, window=0.5) == 0.0
    s.mark_submitted("E0", "t0", 0.0)
    ctx = EstimateContext.from_state(s, "E0")  # candidate busy -> task would start on a warm core
    assert ctx.target_busy_frac == 1.0
    assert EstimateContext.from_state(s, None).target_busy_frac is None


def test_e4_learns_recent_activity_effect(profile):
    rng = np.random.default_rng(1)
    rows = []
    for _ in range(300):
        frac = float(rng.uniform(0, 1))
        k = 1e-9 * 200 ** 3 * math.exp(0.4 * (1 - frac) + rng.normal(0, 0.01))  # idle core -> slower
        rows.append({"workload": "matmul", "size": 200, "pool": "P", "kernel_s": k,
                     "ctx": EstimateContext.build(0, 0, [], target_busy_frac=frac)})
    base = StaticProfileEstimator.from_file(profile)
    full = InterferenceRidgeEstimator.fit(rows, base, ridge_lambda=1e-6)
    occ = InterferenceRidgeEstimator.fit(rows, base, ridge_lambda=1e-6, features=FEATURE_SETS["occupancy"])
    t = TaskSpec("t", "matmul", 200)
    cold = EstimateContext.build(0, 0, [], target_busy_frac=0.0)
    warm = EstimateContext.build(0, 0, [], target_busy_frac=1.0)
    assert full.estimate(t, "P", cold) == pytest.approx(1e-9 * 200 ** 3 * math.exp(0.4), rel=0.03)
    assert full.estimate(t, "P", warm) == pytest.approx(1e-9 * 200 ** 3, rel=0.03)
    assert occ.estimate(t, "P", cold) == pytest.approx(occ.estimate(t, "P", warm))  # ablation cannot see it


# --- E4 base-profile binding (audit finding D2) ------------------------------

TASK = TaskSpec("t", "matmul", 200)
CTX = EstimateContext.build(0, 4, ["matmul", "matmul", "compression", "compression"])
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def e4_model(profile, tmp_path):
    """E4 fitted against the synthetic profile (E group learned, P group falls back to E1), saved."""
    e4 = InterferenceRidgeEstimator.fit(_synthetic_rows(), StaticProfileEstimator.from_file(profile),
                                        ridge_lambda=1e-6, min_rows=30)
    path = tmp_path / "models" / "e4_bound.json"
    e4.save(path)
    return e4, path


def _variant_profile(profile, dest, p_scale):
    """Copy of ``profile`` with every P median scaled (a different session's measurements)."""
    d = json.loads(profile.read_text())
    for e in d["entries"]:
        if e["pool"] == "P":
            e["median_s"] *= p_scale
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(d))
    return dest


def _rewrite_model(path, dest, **changes):
    d = json.loads(path.read_text())
    for k, v in changes.items():
        if v is KeyError:
            del d[k]
        else:
            d[k] = v
    dest.write_text(json.dumps(d))
    return dest


def test_e4_load_defaults_to_recorded_profile(profile, e4_model):
    e4, path = e4_model
    loaded = InterferenceRidgeEstimator.load(path)
    assert loaded.base.source == str(profile)
    assert loaded.base.table == e4.base.table
    assert loaded.meta["base_profile_recorded"] == str(profile)
    for pool in "PE":
        assert loaded.estimate(TASK, pool, CTX) == e4.estimate(TASK, pool, CTX)


def test_e4_load_accepts_matching_explicit_profile(profile, e4_model, tmp_path):
    e4, path = e4_model
    copy = tmp_path / "elsewhere" / "copy_profile.json"   # same measurements at another path
    copy.parent.mkdir()
    shutil.copyfile(profile, copy)
    for base_path in (profile, copy):
        loaded = InterferenceRidgeEstimator.load(path, StaticProfileEstimator.from_file(base_path))
        assert loaded.estimate(TASK, "E", CTX) == e4.estimate(TASK, "E", CTX)


def test_e4_load_rejects_mismatched_explicit_profile(profile, e4_model, tmp_path):
    _, path = e4_model
    other = _variant_profile(profile, tmp_path / "other" / "y_profile.json", 1.1)
    with pytest.raises(BaseProfileMismatchError, match="fitted against"):
        InterferenceRidgeEstimator.load(path, StaticProfileEstimator.from_file(other))


def test_registry_e4_ignores_session_profile_and_keeps_predictions(profile, e4_model, tmp_path):
    """Regression for D2: the build_estimator path used by the Phase 4/5/6B runners."""
    e4, path = e4_model
    session = _variant_profile(profile, tmp_path / "session" / "z_profile.json", 1.1)
    assert StaticProfileEstimator.from_file(session).table != e4.base.table  # the test is meaningful
    for spec in ("E4", "E4f", "E4+rc", "E4f+rc"):
        est = build_estimator(spec, session, model_path=path)
        e4_part = est.base if spec.endswith("+rc") else est
        assert e4_part.base.source == str(profile)
        for pool in "PE":  # +rc is neutral before any observation; E4f equals E4 to ~1e-12
            assert est.estimate(TASK, pool, CTX) == pytest.approx(e4.estimate(TASK, pool, CTX), rel=1e-12)
    assert build_estimator("E1", session).source == str(session)  # E0-E3 still use the session profile


@pytest.mark.parametrize("bad", [KeyError, None, "", "   ", 42])
def test_e4_load_refuses_missing_or_invalid_base_profile(profile, e4_model, tmp_path, bad):
    _, path = e4_model
    p = _rewrite_model(path, tmp_path / "models" / "e4_nometa.json", base_profile=bad)
    for base in (None, StaticProfileEstimator.from_file(profile)):
        with pytest.raises(ValueError, match="no usable base_profile"):
            InterferenceRidgeEstimator.load(p, base)


def test_e4_load_when_recorded_profile_was_moved(profile, e4_model, tmp_path):
    e4, path = e4_model
    for recorded in (str(tmp_path / "gone" / profile.name), "D:\\moved away\\data\\profiles\\" + profile.name):
        p = _rewrite_model(path, tmp_path / "models" / "e4_moved.json", base_profile=recorded)
        with pytest.raises(FileNotFoundError, match="not found"):
            InterferenceRidgeEstimator.load(p)
        same_file = InterferenceRidgeEstimator.load(p, StaticProfileEstimator.from_file(profile))
        assert same_file.estimate(TASK, "E", CTX) == e4.estimate(TASK, "E", CTX)
        other = _variant_profile(profile, tmp_path / "o" / "other_profile.json", 1.0)  # same values, other file
        with pytest.raises(BaseProfileMismatchError, match="not the same profile file"):
            InterferenceRidgeEstimator.load(p, StaticProfileEstimator.from_file(other))


def test_e4_save_refuses_base_without_source(tmp_path):
    e4 = InterferenceRidgeEstimator(StaticProfileEstimator({("matmul", 200, "E"): 0.02}), {})
    with pytest.raises(ValueError, match="no source file"):
        e4.save(tmp_path / "m.json")
    assert not (tmp_path / "m.json").exists()


def test_saved_phase_models_bind_to_their_training_profile():
    """The shipped Phase 3 model (read only): recorded profile by default, Phase 5/6B profile refused."""
    model = REPO / "data" / "models" / "e4_20261003T144301_occupancy_history.json"
    trained_on = REPO / "data" / "profiles" / "20261003T115606_profile.json"
    session = REPO / "data" / "profiles" / "20261003T152700_profile.json"
    if not (model.is_file() and trained_on.is_file() and session.is_file()):
        pytest.skip("project evidence files not present")
    loaded = InterferenceRidgeEstimator.load(model)
    assert Path(loaded.base.source).name == trained_on.name
    assert loaded.base.table == StaticProfileEstimator.from_file(trained_on).table
    with pytest.raises(BaseProfileMismatchError):
        InterferenceRidgeEstimator.load(model, StaticProfileEstimator.from_file(session))
    assert Path(build_estimator("E4f+rc", session, model_path=model).base.base.source).name == trained_on.name
