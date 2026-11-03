"""GpuAdapter on tiny pipelines (tile 64). CUDA-dependent tests skip without a GPU."""
import json

import pytest

from caosched.apps.cuda_stages import cuda_available
from caosched.core.event_log import read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.experiment.design import Condition
from caosched.experiment.gpu_adapter import GpuAdapter, gpu_stage_table_from_spike

ALL3 = {"img_denoise": True, "img_edges": True, "img_features": True}


def _row(stage, side, verdict, params="{}"):
    return {"stage": stage, "params": params, "side": side, "verdict": verdict}


def test_stage_table_from_spike(tmp_path):
    p = tmp_path / "gpu_spike.json"
    d1, d8 = '{"radius": 2.0, "iterations": 1}', '{"radius": 2.0, "iterations": 8}'
    p.write_text(json.dumps({"rows": [
        _row("img_denoise", 512, "DROPPED", d1), _row("img_denoise", 1024, "PASS", d1), _row("img_denoise", 512, "PASS", d8),
        _row("img_edges", 512, "PASS"), _row("img_edges", 256, "DROPPED"), _row("img_features", 512, "DROPPED")]}))
    assert gpu_stage_table_from_spike(p, 512) == {"img_denoise": False, "img_edges": True, "img_features": False}
    assert gpu_stage_table_from_spike(p, 512, denoise_iterations=8)["img_denoise"] is True
    assert gpu_stage_table_from_spike(p, 1024)["img_denoise"] is True
    assert gpu_stage_table_from_spike(p, 64) == {"img_denoise": False, "img_edges": False, "img_features": False}  # no row = not measured


@pytest.fixture
def adapter():
    a = GpuAdapter(runtime_config=RuntimeConfig(p_core_slots=(0,), e_core_slots=(1,)), timeout_s=120, run_timeout_s=300)
    yield a
    a.close()


def _cond(name="B4", policy="B4", **kw):
    return Condition(name, policy, None, {}, {"tile": 64, **kw}, instance=None)


def _run(adapter, cond, tmp_path, n):
    wd = tmp_path / "session" / "runs" / f"b0000_0{n}_{cond.name}"
    wd.mkdir(parents=True)
    return adapter.run_one(cond, wd, seed=1), wd


def test_only_table_stages_are_eligible_for_g(adapter):
    dag, _ = adapter.build_dag({"tile": 64, "n_images": 4}, {"img_edges"})
    for t in dag.tasks.values():
        assert ("G" in t.eligible_pools) == (t.workload == "img_edges"), t.task_id
    dag, _ = adapter.build_dag({"tile": 64, "n_images": 4}, ())
    assert all(t.eligible_pools == ("P", "E") for t in dag.tasks.values())
    with pytest.raises(ValueError, match="perfect square"):
        adapter.build_dag({"n_images": 2})


def test_cpu_run_is_verified_and_no_gpu_ignores_the_table(adapter, tmp_path):
    rec, wd = _run(adapter, _cond(n_images=4), tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True, rec.error
    assert rec.extra["n_tasks"] == 20 and rec.extra["cuda_tasks"] == [] and "G" not in rec.extra["tasks_per_pool"]
    assert sum(rec.extra["tasks_per_pool"].values()) == 20 and rec.extra["output_verdict"]["match"] in ("exact", "numeric")
    assert "not measured" in rec.extra["h2d_d2h_copy_time"] and set(rec.output_hashes) == {"package"}
    assert read_events(wd / rec.event_log)[-1]["status"] == "completed" and not (wd / "artifacts").exists()
    rec2, _ = _run(adapter, _cond("B4_nogpu", n_images=4, gpu_stage_table=ALL3, no_gpu=True), tmp_path, 1)
    assert rec2.status == "ok" and rec2.output_ok is True and rec2.extra["gpu_pool"] is False
    assert rec2.output_hashes == rec.output_hashes   # same application, same output


@pytest.mark.skipif(not cuda_available(), reason="no CUDA device")
def test_g_pool_run_is_within_tolerance_and_confined(adapter, tmp_path):
    rec, wd = _run(adapter, _cond("rnd", "random", n_images=16, gpu_stage_table={"img_edges": True}), tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True, (rec.error, rec.extra.get("output_verdict"))
    assert rec.extra["gpu_pool"] is True and rec.extra["cuda_tasks"]
    assert all(t.startswith("edges_") for t in rec.extra["cuda_tasks"])    # denoise / features never on G
    assert all(p == "G" for t, (p, _) in rec.extra["task_placement"].items() if t in rec.extra["cuda_tasks"])
    rec2, _ = _run(adapter, _cond("rnd3", "random", n_images=16, gpu_stage_table=ALL3), tmp_path, 1)
    assert rec2.status == "ok" and rec2.output_ok is True, (rec2.error, rec2.extra.get("output_verdict"))
    assert {"G"} >= {p for t, (p, _) in rec2.extra["task_placement"].items() if t in rec2.extra["cuda_tasks"]}
