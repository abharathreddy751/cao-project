"""Light checks of the Stage 5 figure code: real log axes, zero-based bars, labelled axes, evidence label, CI drawn."""
import pytest

plt = pytest.importorskip("matplotlib.pyplot")

from caosched.analysis.stats_paired import load_result, make_figures, write_tables  # noqa: E402


def _result():
    conds = {"B0_P_only": (268.0, 0.001, 0.015), "B4_greedy": (414.0, 0.0013, 0.02), "EFT_E1": (272.0, 0.02, 0.35), "EFT_CatBoost": (272.5, 1.5, 25.0)}
    summ = [{"condition": c, "instance": "i1", "scope": "per_instance", "n": 2, "mean_s": g} for c, (g, _, _) in conds.items()]
    summ += [{"condition": c, "instance": "all", "scope": "pooled_log_scale", "n": 4, "geo_mean_s": g, "ci_lo_s": g - 1, "ci_hi_s": g + 1,
              "queue_wait_total_s_mean": 450.0, "transfer_total_s_mean": "not measured", "sched_overhead_total_s_mean": o,
              "sched_overhead_per_decision_s_mean": d / 1e3} for c, (g, o, d) in conds.items()]
    effects = [{"variant": "primary", "metric": "makespan_s", "cond": c, "n_blocks": 4, "effect_pct": e, "ci_lo_pct": e - 0.5,
                "ci_hi_pct": e + 0.5, "ci_excludes_zero": True} for c, e in (("B4_greedy", 54.0), ("EFT_E1", 1.3), ("EFT_CatBoost", 1.4))]
    return {"meta": {"evidence_label": "real", "reference": "B0_P_only"}, "tables": {"summary": summ, "effects": effects}}


def test_figures_axes_and_labels(tmp_path, monkeypatch):
    figs = []
    monkeypatch.setattr(plt, "close", lambda f=None: figs.append(f))
    paths = make_figures(_result(), tmp_path)
    assert [p.name for p in paths] == ["fig_makespan_by_policy.png", "fig_overhead_breakdown.png", "fig_effect_vs_baseline.png"]
    assert all(p.stat().st_size > 0 for p in paths)
    mk, ov, ef = figs
    assert all("evidence: real" in f._suptitle.get_text() for f in figs)
    assert mk.axes[0].get_yscale() == "log" and mk.axes[1].get_yscale() == "linear"  # log panel + zoom of near-fastest policies
    assert ov.axes[0].get_xlim()[0] == 0 and ov.axes[1].get_xscale() == "log" and ov.axes[2].get_xscale() == "log"  # bars from 0
    assert len(ef.axes) == 2  # outlier (B4 +54%) gets a zoom panel
    assert all(ax.get_xlabel() or ax.get_ylabel() for f in figs for ax in f.axes)
    assert any(len(ax.lines) or ax.containers for ax in ef.axes)  # intervals are drawn


def test_load_result_roundtrip(tmp_path):
    r = _result()
    r["tables"]["crosscheck"], r["tables"]["runs"], r["tables"]["exclusions"] = [], [], []
    r["meta"].update(paths=[])
    write_tables(r, tmp_path)
    back = load_result(tmp_path)
    assert back["meta"]["reference"] == "B0_P_only"
    assert next(e for e in back["tables"]["effects"] if e["cond"] == "EFT_E1")["effect_pct"] == pytest.approx(1.3)
    assert make_figures(back, tmp_path / "f")
