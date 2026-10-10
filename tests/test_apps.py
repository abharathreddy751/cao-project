"""Application-level workflows: real data flow through the scheduler, local and
remote, verified against a single-process reference."""
import pytest

from caosched.apps import build_image_pipeline, run_reference, verify_output
from caosched.apps.artifacts import artifact_path
from caosched.core.coordinator import Coordinator
from caosched.core.event_log import EventLogger, read_events
from caosched.core.scheduler_base import FirstIdleScheduler, SchedulerContractError
from caosched.core.worker_pool import RemoteSlot, WorkerPool
from caosched.estimators import ReplayOracleEstimator, TaskSpec
from caosched.remote import LinkConfig
from caosched.schedulers.simple import GreedyEligibleScheduler, PoolOnlyScheduler

SMALL = dict(width=256, height=256, grid=2, seed=7)


def test_pipeline_shape_and_reference_is_deterministic():
    dag = build_image_pipeline(**SMALL)
    assert len(dag) == 4 * 4 + 4 and dag.critical_path_length() == 7
    assert dag.tasks["mosaic"].dependencies == tuple(f"edges_{i}" for i in range(4))
    a, b = run_reference(dag)["package"], run_reference(build_image_pipeline(**SMALL))["package"]
    assert verify_output(a, b)["match"] == "exact"
    other = run_reference(build_image_pipeline(**{**SMALL, "seed": 8}))["package"]
    assert verify_output(other, a)["match"] == "MISMATCH"


def _run(dag, pool, policy, tmp_path, name):
    with EventLogger(name, output_dir=tmp_path) as log:
        s = Coordinator(dag, pool, policy, log, artifact_dir=tmp_path / name).run(run_timeout=120)
    return s, read_events(log.path)


def test_local_pipeline_output_matches_reference(tmp_path):
    dag = build_image_pipeline(**SMALL)
    ref = run_reference(build_image_pipeline(**SMALL))["package"]
    with WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=False) as pool:
        s, ev = _run(dag, pool, FirstIdleScheduler(), tmp_path, "local")
    assert s.status == "completed" and s.n_completed == len(dag)
    final = artifact_path(tmp_path / "local", "package").read_bytes()
    assert verify_output(final, ref)["match"] == "exact"
    done = [e for e in ev if e["event"] == "task_completed"]
    assert all(e["output_bytes"] > 0 and e["io_s"] >= 0 and e["wall_time_seconds"] > 0 for e in done)
    assert ev[0]["tasks"]["tile_0"]["params"] == {"grid": 2, "index": 0} and ev[0]["artifact_dir"]


def test_remote_stages_move_real_data_and_output_matches(tmp_path):
    dag = build_image_pipeline(**SMALL, remote_stages={"img_denoise": ["R"], "img_edges": ["R"]})
    ref = run_reference(build_image_pipeline(**SMALL))["package"]
    link = LinkConfig("t", latency_s=0.001)
    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False,
                    remote_slots=[RemoteSlot(link, node_core=1)]) as pool:
        s, ev = _run(dag, pool, GreedyEligibleScheduler(priority=["R", "E"], name="remote_first"), tmp_path, "rem")
    final = artifact_path(tmp_path / "rem", "package").read_bytes()
    assert s.status == "completed" and verify_output(final, ref)["match"] == "exact"
    on_r = [e for e in ev if e["event"] == "task_completed" and e["pool"] == "R"]
    assert on_r and {e["task_id"].split("_")[0] for e in on_r} <= {"denoise", "edges"}
    for e in on_r:  # real bytes: input artifact (128x128x3 uint8 npy) + returned output
        assert e["payload_bytes"] > 128 * 128 * 3 and e["transfer_s"] >= 0.002 and e["output_bytes"] > 0
    assert all(e["pool"] != "R" for e in ev if e["event"] == "task_completed"
               and e["task_id"].split("_")[0] not in ("denoise", "edges"))
    caps = [e["capabilities"] for e in ev if e["event"] == "worker_ready" and e["pool"] == "R"][0]
    assert "img_edges" in caps["stages"] and caps["cuda"] in (True, False)


def test_ineligible_placement_is_a_contract_violation(tmp_path):
    dag = build_image_pipeline(**SMALL)  # no remote stages
    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False,
                    remote_slots=[RemoteSlot(LinkConfig("z"), node_core=1)]) as pool:
        with EventLogger("bad", output_dir=tmp_path) as log:
            with pytest.raises(SchedulerContractError, match="only eligible"):
                Coordinator(dag, pool, PoolOnlyScheduler("R"), log, artifact_dir=tmp_path / "bad").run(run_timeout=30)


def test_named_device_pool_and_foreign_clock(tmp_path):
    dag = build_image_pipeline(**SMALL, remote_stages={"img_edges": ["R_PI"]})
    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False,
                    remote_slots=[RemoteSlot(LinkConfig("z"), node_core=1, pool="R_PI", same_clock=False)]) as pool:
        assert pool.worker_ids("R_PI") == ["R_PI0"]
        pool.set_link("R_PI0", LinkConfig("z2"))
        s, ev = _run(dag, pool, GreedyEligibleScheduler(priority=["R_PI", "E"], name="pi_first"), tmp_path, "pi")
    assert s.status == "completed"
    pi = [e for e in ev if e["event"] == "task_completed" and e["pool"] == "R_PI"]
    assert pi and all(e["t_started"] <= e["t_completed"] for e in pi)


def test_oracle_incremental_add_equals_from_rows():
    rows = [{"run_id": r, "task_id": "t", "seed": 1, "workload": "matmul", "size": 8, "pool": "P", "kernel_s": v}
            for r, v in (("a", 1.0), ("b", 3.0), ("c", 2.0))]
    inc = ReplayOracleEstimator({})
    for r in rows:
        inc.add(r["run_id"], r["task_id"], r["seed"], r["workload"], r["size"], r["pool"], r["kernel_s"])
    full = ReplayOracleEstimator.from_rows(rows)
    t = TaskSpec("t", "matmul", 8, seed=1)
    for ex in (None, "a", "c"):
        inc.exclude_run(ex)
        full.exclude_run(ex)
        assert inc.estimate(t, "P") == full.estimate(t, "P")


def test_stage_payload_model_matches_real_artifacts():
    from caosched.remote.link import payload_bytes
    dag = build_image_pipeline(**SMALL)
    out = run_reference(dag)
    for i in range(4):
        t = dag.tasks[f"denoise_{i}"]
        assert payload_bytes(t.workload, t.size) == (len(out[f"tile_{i}"]), len(out[f"denoise_{i}"]))
        t = dag.tasks[f"edges_{i}"]
        assert payload_bytes(t.workload, t.size) == (len(out[f"denoise_{i}"]), len(out[f"edges_{i}"]))
        t = dag.tasks[f"features_{i}"]
        assert payload_bytes(t.workload, t.size) == (len(out[f"edges_{i}"]), len(out[f"features_{i}"]))
    with pytest.raises(KeyError):
        payload_bytes("img_mosaic", 1)


def test_transfer_aware_eft_runs_application_dag(tmp_path):
    from caosched.estimators import RecalibratedEstimator, StaticProfileEstimator
    from caosched.remote.link import TransferModel
    from caosched.schedulers.eft import EarliestFinishTimeScheduler
    dag = build_image_pipeline(**SMALL, remote_stages={"img_denoise": ["R"], "img_edges": ["R"]})
    ref = run_reference(build_image_pipeline(**SMALL))["package"]
    link = LinkConfig("t", latency_s=0.0005)
    table = {(t.workload, t.size, p): 0.001 for t in dag.tasks.values() for p in ("P", "E", "R")}
    pol = EarliestFinishTimeScheduler(RecalibratedEstimator(StaticProfileEstimator(table)), "EFT_t",
                                      transfer=TransferModel({"R": link}))
    with WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=False,
                    remote_slots=[RemoteSlot(link, node_core=1)]) as pool:
        s, ev = _run(dag, pool, pol, tmp_path, "eft")
    assert s.status == "completed"
    assert verify_output(artifact_path(tmp_path / "eft", "package").read_bytes(), ref)["match"] == "exact"
    assert all(e["pool"] in ("E", "R") for e in ev if e["event"] == "task_completed")


def test_denoise_iterations_knob():
    import io

    import numpy as np
    from PIL import Image, ImageFilter

    from caosched.apps.stages import run_stage
    tile = np.random.default_rng(3).integers(0, 255, (32, 32, 3), dtype=np.uint8)
    buf = io.BytesIO()
    np.save(buf, tile, allow_pickle=False)
    one, _, _ = run_stage("img_denoise", [buf.getvalue()], {"radius": 2.0})
    assert one == run_stage("img_denoise", [buf.getvalue()], {"radius": 2.0, "iterations": 1})[0]
    three = np.load(io.BytesIO(run_stage("img_denoise", [buf.getvalue()], {"radius": 2.0, "iterations": 3})[0]))
    img = Image.fromarray(tile)
    for _ in range(3):
        img = img.filter(ImageFilter.GaussianBlur(radius=2.0))
    assert np.array_equal(three, np.asarray(img))
    # same DAG structure at any intensity; k=1 is the original application output
    a = build_image_pipeline(**SMALL)
    b = build_image_pipeline(**SMALL, denoise_iterations=4)
    assert list(a.tasks) == list(b.tasks) and all(a.tasks[t].dependencies == b.tasks[t].dependencies for t in a.tasks)
    assert b.tasks["denoise_0"].params["iterations"] == 4
    ra, rb = run_reference(a)["package"], run_reference(b)["package"]
    assert ra != rb and rb == run_reference(build_image_pipeline(**SMALL, denoise_iterations=4))["package"]
