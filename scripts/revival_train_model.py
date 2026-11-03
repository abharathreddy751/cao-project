"""Revival: train the runtime model with the functional form chosen PER (workload, pool) group on a held-out selection set.

For each group the additive form (``fit_group``) and the power-law form (``fit_group_log_power``) are fitted on the TRAINING sessions;
the form with the lower mean absolute error on the SELECTION sessions is kept (ties: additive). A model that never saw the selection
sessions is therefore compared on them honestly; a third set (the report set of ``revival_model_eval.py``) takes no part in the choice.
Also writes the "blind" baseline profile used by the resource-state-only ablation: size is its only input (task parameters such as the
number of denoise iterations are stripped), additive form, fitted on the same training sessions.

  python scripts/revival_train_model.py <model.json> <blind.json> --train <sess>... --select <sess>...
Files are created exclusively.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from caosched.study2.param_model import fit_group, fit_group_log_power, predict_group

ROOT = Path(__file__).resolve().parents[1]


def _points(sessions):
    spec = importlib.util.spec_from_file_location("study2_train_param_model", ROOT / "scripts" / "study2_train_param_model.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.points(sessions)


def main(model_out: str, blind_out: str, train: list[str], select: list[str]) -> int:
    for o in (model_out, blind_out):
        if Path(o).exists():
            sys.exit(f"{o} exists: refusing to overwrite")
    tr, se = _points(train), _points(select)
    groups: dict[str, dict] = {}
    report: dict[str, dict] = {}
    blind: dict[str, dict] = {}
    for k, rows in sorted(tr.items()):
        ps, y = [p for p, _ in rows], [v for _, v in rows]
        cands = {"additive": fit_group(ps, y), "log_power": fit_group_log_power(ps, y)}
        blind[k] = fit_group([{"size": p["size"]} for p in ps], y)
        if k not in se:
            groups[k], report[k] = cands["additive"], {"chosen": "additive", "reason": "group absent from the selection sessions"}
            continue
        err = {name: float(np.mean([abs(predict_group(g, p) - v) for p, v in se[k]])) for name, g in cands.items()}
        chosen = "log_power" if err["log_power"] < err["additive"] else "additive"
        groups[k] = cands[chosen]
        report[k] = {"chosen": chosen, "select_mae_ms": {n: e * 1e3 for n, e in err.items()}, "n_train": len(rows), "n_select": len(se[k])}
    meta = {"train_sessions": [str(s) for s in train], "select_sessions": [str(s) for s in select]}
    with Path(model_out).open("x", encoding="utf-8") as fh:
        json.dump({"groups": groups, "form_selection": report, **meta, "rule": "per-group form chosen on held-out selection sessions"}, fh, indent=1)
    with Path(blind_out).open("x", encoding="utf-8") as fh:
        json.dump({"groups": blind, **meta, "rule": "baseline profile: size is the only input (task parameters stripped), additive"}, fh, indent=1)
    for k, r in report.items():
        print(f"{k:22s} {r['chosen']:9s}", {n: round(e, 2) for n, e in r.get("select_mae_ms", {}).items()})
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    t0, s0 = a.index("--train"), a.index("--select")
    sys.exit(main(a[0], a[1], a[t0 + 1:s0] if t0 < s0 else a[t0 + 1:], a[s0 + 1:t0] if s0 < t0 else a[s0 + 1:]))
