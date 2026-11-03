"""scripts/final_oracle_rows.py on a synthetic calibration session: class medians become CachedOracle rows for every task and pool."""
import importlib.util
import json
from pathlib import Path

import pytest

from caosched.study2.policies import CachedOracle

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("final_oracle_rows", ROOT / "scripts" / "final_oracle_rows.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _log(path, tasks, completed):
    rows = [{"seq": 0, "event": "run_started", "tasks": tasks}] + [
        {"seq": i + 1, "event": "task_completed", "task_id": t, "pool": p, "wall_time_seconds": v} for i, (t, p, v) in enumerate(completed)]
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_class_medians_skip_warmup_and_group_by_iterations(tmp_path):
    spec = {"denoise_0": {"workload": "img_denoise", "size": 4096, "params": {"radius": 2.0, "iterations": 2}},
            "denoise_1": {"workload": "img_denoise", "size": 4096, "params": {"radius": 2.0, "iterations": 120}}}
    s = tmp_path / "sess"
    _log(s / "runs" / "b0000_00_x" / "a.jsonl", spec, [("denoise_0", "P", 99.0)])                 # warm-up: ignored
    _log(s / "runs" / "b0001_00_x" / "a.jsonl", spec, [("denoise_0", "P", 0.010), ("denoise_1", "P", 0.600)])
    _log(s / "runs" / "b0002_00_x" / "a.jsonl", spec, [("denoise_0", "P", 0.030), ("denoise_1", "P", 0.800), ("denoise_1", "G", 0.5)])
    med = mod.class_medians([s])
    assert med[("img_denoise", 4096, 2, "P")] == pytest.approx(0.020)
    assert med[("img_denoise", 4096, 120, "P")] == pytest.approx(0.700)
    assert med[("img_denoise", 4096, 120, "G")] == pytest.approx(0.5)
    assert ("img_denoise", 4096, 2, "G") not in med


def test_rows_feed_cached_oracle(tmp_path):
    rows = [{"run_id": "class_median", "task_id": "denoise_0", "seed": 2, "workload": "img_denoise", "size": 4096, "pool": "P", "kernel_s": 0.02}]
    est = CachedOracle.from_rows(rows)

    class T:
        task_id, seed, est_workload, est_size = "denoise_0", 2, "img_denoise", 4096

    assert est.estimate(T, "P") == pytest.approx(0.02)
    with pytest.raises(KeyError):
        est.estimate(T, "G")                    # no guessing for a pool without an observation
