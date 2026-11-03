"""Revival: offline, leakage-safe comparison of runtime-model variants (the poorly predicted lightest class of the two-factor study).

Fit on the coverage sessions only (``--train``), choose on one held-out set (``--select``), report on another held-out set that took no
part in the choice (``--report``). One row per completed task of every run outside warm-up block 0 (target ``wall_time_seconds``).

Variants (per (workload, pool) group, features chosen from the data exactly as ``study2/param_model.py``):
  linear        the current model (ridge least squares on inputs and their products)
  floor         linear, never below 0.5 x the smallest training time of the group
  log_power     log(time) ~ a + sum b_i log(x_i)          (power law; inputs with value 0 dropped)
  log_linear    log(time) ~ a + sum b_i x_i                (exponential in standardised inputs and products)
  linear_class  linear x a class-aware multiplicative correction: median(actual / predicted) per log2-millisecond bucket of the
                predicted time, learned on the TRAINING rows only (the offline counterpart of the online correction in ``revival.state``)

Metrics per group and variant: mean absolute error (ms), median absolute percentage error, and the same for the stage ``img_denoise``
split by class (image side, iterations).

  python scripts/revival_model_eval.py <out.json> --train <sess>... --select <sess>... --report <sess>...
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

from caosched.study2.param_model import column, feature_names, fit_group

ROOT = Path(__file__).resolve().parents[1]


def _points(sessions):
    spec = importlib.util.spec_from_file_location("study2_train_param_model", ROOT / "scripts" / "study2_train_param_model.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.points(sessions)


def _lin(g, p):
    return float(np.dot(g["coef"], [1.0] + [column(p, f) for f in g["features"]]))


def fit_variants(rows):
    ps, y = [p for p, _ in rows], np.array([v for _, v in rows], float)
    g = fit_group(ps, list(y))
    out = {"linear": lambda p: max(1e-6, _lin(g, p))}
    floor = 0.5 * float(y.min())
    out["floor"] = lambda p: max(floor, _lin(g, p))
    names = feature_names(ps)
    base = [n for n in names if "*" not in n]
    if base:
        X = np.array([[math.log(max(column(p, n), 1.0)) for n in base] for p in ps])
        Z = np.hstack([np.ones((len(y), 1)), X])
        c, *_ = np.linalg.lstsq(Z, np.log(y), rcond=None)
        out["log_power"] = lambda p: float(math.exp(c[0] + sum(ci * math.log(max(column(p, n), 1.0)) for ci, n in zip(c[1:], base))))
    F = np.array([[column(p, n) for n in names] for p in ps]).reshape(len(ps), len(names))
    if names:
        mu, sd = F.mean(axis=0), F.std(axis=0)
        sd[sd == 0] = 1.0
        Z = np.hstack([np.ones((len(y), 1)), (F - mu) / sd])
        c2, *_ = np.linalg.lstsq(Z, np.log(y), rcond=None)
        out["log_linear"] = lambda p: float(math.exp(c2[0] + sum(ci * (column(p, n) - m) / s for ci, n, m, s in zip(c2[1:], names, mu, sd))))
    pred = np.array([max(1e-6, _lin(g, p)) for p in ps])
    buckets: dict[int, list[float]] = {}
    for a, b in zip(y, pred):
        buckets.setdefault(int(math.floor(math.log2(max(b, 1e-6) * 1000))), []).append(a / b)
    corr = {k: float(np.median(v)) for k, v in buckets.items()}

    def linear_class(p):
        v = max(1e-6, _lin(g, p))
        return v * corr.get(int(math.floor(math.log2(v * 1000))), 1.0)

    out["linear_class"] = linear_class
    return out


def evaluate(models, held):
    res: dict = {}
    for grp, rows in sorted(held.items()):
        if grp not in models:
            continue
        for name, f in models[grp].items():
            pr = np.array([f(p) for p, _ in rows])
            y = np.array([v for _, v in rows])
            res.setdefault(grp, {})[name] = {"n": len(y), "mae_ms": float(np.mean(np.abs(pr - y)) * 1e3),
                                             "median_ape": float(np.median(np.abs(pr - y) / y))}
    return res


def by_class(models, held, grp="img_denoise|P"):
    res: dict = {}
    rows = held.get(grp, [])
    for key in sorted({(int(p["size"]), int(p.get("iterations", 0))) for p, _ in rows}):
        sub = [(p, v) for p, v in rows if (int(p["size"]), int(p.get("iterations", 0))) == key]
        y = np.array([v for _, v in sub])
        res[f"side^2={key[0]} N={key[1]}"] = {"n": len(sub), "mean_actual_ms": float(y.mean() * 1e3),
                                              **{name: float(np.mean([f(p) for p, _ in sub]) * 1e3) for name, f in models[grp].items()}}
    return res


def main(out, train, select, report):
    if Path(out).exists():
        sys.exit(f"{out} exists: refusing to overwrite")
    tr = _points(train)
    models = {g: fit_variants(rows) for g, rows in tr.items()}
    result = {"train": train, "select": select, "report": report,
              "select_metrics": evaluate(models, _points(select)), "report_metrics": evaluate(models, _points(report)),
              "select_denoise_P_by_class_ms": by_class(models, _points(select)), "report_denoise_P_by_class_ms": by_class(models, _points(report)),
              "report_denoise_E_by_class_ms": by_class(models, _points(report), "img_denoise|E")}
    with Path(out).open("x", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    for part in ("select_metrics", "report_metrics"):
        print(part)
        for g, d in result[part].items():
            print(" ", g, {k: (round(v["mae_ms"], 2), round(v["median_ape"], 2)) for k, v in d.items()})
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]

    def part(flag):
        rest = a[a.index(flag) + 1:]
        end = next((i for i, x in enumerate(rest) if x.startswith("--")), len(rest))
        return rest[:end]

    sys.exit(main(a[0], part("--train"), part("--select"), part("--report")))
