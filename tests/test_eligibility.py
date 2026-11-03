"""Uniform eligibility (AD-5), capability model (AD-4) and device choice at
dispatch (AD-6): every policy places only on eligible workers and fails before
the run (not by deadlock) when a task can never be placed; pool names are
arbitrary labels."""
import dataclasses

import pytest

from caosched.apps import build_image_pipeline, run_reference, verify_output
from caosched.apps.artifacts import artifact_path
from caosched.core.coordinator import Coordinator
from caosched.core.dag import DAG
from caosched.core.eligibility import EligibilityError, resolve_eligibility
from caosched.core.event_log import EventLogger, read_events
from caosched.core.runtime_config import PoolSpec, RuntimeConfig
from caosched.core.scheduler_base import FirstIdleScheduler, NoEligibleWorkerError
from caosched.core.runtime_state import RuntimeState
from caosched.core.task import Task
from caosched.core.worker_pool import RemoteSlot, WorkerPool, WorkerPoolError
from caosched.estimators.base import ExecutionTimeEstimator
from caosched.schedulers.eft import EarliestFinishTimeScheduler
from caosched.schedulers.simple import (CriticalityScheduler, GreedyEligibleScheduler, PoolOnlyScheduler,
                                        RandomScheduler, RoundRobinScheduler, ShortestQueueScheduler,
                                        StaticMappingScheduler)


class _Flat(ExecutionTimeEstimator):
    name = "flat"

    def estimate(self, task, pool, ctx=None):
        return 0.01


# name -> (factory, pools the policy is confined to, None = all)
POLICIES = {
    "B0_X1": (lambda: PoolOnlyScheduler("X1"), {"X1"}),
    "B0_X2": (lambda: PoolOnlyScheduler("X2"), {"X2"}),
    "B1": (RoundRobinScheduler, None),
    "B2": (lambda: StaticMappingScheduler({"matmul": "X1"}), {"X1"}),
    "B3": (ShortestQueueScheduler, None),
    "B4": (GreedyEligibleScheduler, None),
    "B5": (CriticalityScheduler, None),
    "random": (lambda: RandomScheduler(3), None),
    "first_idle": (FirstIdleScheduler, None),
    "EFT": (lambda: EarliestFinishTimeScheduler(_Flat(), "eft_flat"), None),
}


def _dag(restricted_to_x2: bool) -> DAG:
    def t(tid, deps=(), pools=None):
        return Task(tid, "matmul", 16, dependencies=deps, eligible_pools=pools)

    tasks = [t("a", pools=("X1",)), t("b", pools=("X2",) if restricted_to_x2 else ("X1", "X2")), t("c"),
             t("d", ("a", "b")), t("e", ("c",), ("X1",)), t("f", ("c",), ("X2",) if restricted_to_x2 else None),
             t("g", ("e", "f"))]
    return DAG({x.task_id: x for x in tasks})


@pytest.fixture(scope="module")
def pool():
    with WorkerPool(pools={"X1": PoolSpec((0,)), "X2": PoolSpec((1,))}, warmup=False) as p:
        yield p


@pytest.mark.parametrize("restricted_to_x2", [True, False])
@pytest.mark.parametrize("name", POLICIES)
def test_every_policy_places_only_on_eligible_workers_or_fails_before_running(pool, tmp_path, name, restricted_to_x2):
    make, confined = POLICIES[name]
    dag = _dag(restricted_to_x2)
    doomed = confined is not None and any(
        not (set(t.eligible_pools or ("X1", "X2")) & confined) for t in dag.tasks.values())
    with EventLogger("r", output_dir=tmp_path) as log:
        c = Coordinator(dag, pool, make(), log)
        if doomed:
            with pytest.raises(NoEligibleWorkerError, match="no eligible worker"):
                c.run(run_timeout=30)
        else:
            assert c.run(run_timeout=60).status == "completed"
    ev = read_events(log.path)
    if doomed:
        assert not any(e["event"] == "task_dispatched" for e in ev)
        assert ev[-1]["task_status"] == {tid: "not_run" for tid in dag.tasks}
    else:
        for t in dag.tasks.values():
            assert t.assigned_pool in (t.eligible_pools or ("X1", "X2")), (name, t.task_id, t.assigned_pool)
            if confined is not None:  # a pool-confined policy never leaves its pools, whatever the task allows
                assert t.assigned_pool in confined, (name, t.task_id, t.assigned_pool)


def test_runtime_config_declares_arbitrary_pools_and_stays_backward_compatible():
    cfg = RuntimeConfig(pools={"X1": PoolSpec((0, 2)), "X2": PoolSpec((4,), task_types=("matmul",))},
                        coordinator_core=1)
    assert list(cfg.pools) == ["X1", "X2"] and cfg.p_core_slots == () and cfg.to_dict()["pools"]["X2"]["task_types"] == ["matmul"]
    legacy = RuntimeConfig((0, 2), (4, 5), 1)
    assert list(legacy.pools) == ["P", "E"] and legacy.pools["E"].slots == (4, 5)
    mixed = RuntimeConfig((0,), (), pools={"G": PoolSpec((0,), "cuda")})  # cuda slots are device indices
    assert list(mixed.pools) == ["P", "G"]
    assert dataclasses.replace(legacy, coordinator_core=3).pools == legacy.pools
    with pytest.raises(ValueError, match="more than one"):
        RuntimeConfig(pools={"X1": PoolSpec((0,)), "X2": PoolSpec((0,))})
    with pytest.raises(ValueError, match="Coordinator core"):
        RuntimeConfig(pools={"X1": PoolSpec((0,))}, coordinator_core=0)
    with pytest.raises(ValueError, match="kind"):
        PoolSpec((0,), "tpu")


def test_from_topology_names_detected_classes_p_and_e():
    cfg = RuntimeConfig.from_topology()
    if not (cfg.p_core_slots and cfg.e_core_slots):
        pytest.skip("this host has no distinct P and E core classes")
    assert set(cfg.pools) == {"P", "E"} and cfg.pools["P"].slots == cfg.p_core_slots
    assert cfg.coordinator_core is not None and cfg.pools["E"].kind == "cpu"


def test_build_time_errors_name_the_task():
    specs = {"P": PoolSpec((0,)), "Q": PoolSpec((1,), task_types=("compression",), memory_limit_bytes=100)}
    dag = DAG({"a": Task("a", "matmul", 16), "b": Task("b", "compression", 16, memory_bytes=50)})
    resolve_eligibility(dag, specs)
    assert dag.tasks["a"].eligible_pools == ("P",) and dag.tasks["b"].eligible_pools is None  # capable of both
    with pytest.raises(EligibilityError, match="'x'"):
        resolve_eligibility(DAG({"x": Task("x", "compression", 16, memory_bytes=500)}), {"Q": specs["Q"]})
    with pytest.raises(EligibilityError, match="cannot run it"):
        resolve_eligibility(DAG({"x": Task("x", "matmul", 16, eligible_pools=("P", "Q"))}), specs)
    with pytest.raises(EligibilityError, match="no eligible worker"):
        resolve_eligibility(DAG({"x": Task("x", "matmul", 16, eligible_pools=("Z",))}), specs)


def test_resolve_eligibility_changes_nothing_when_it_fails():
    specs = {"P": PoolSpec((0,)), "Q": PoolSpec((1,), task_types=("compression",))}
    dag = DAG({"a": Task("a", "matmul", 16), "z": Task("z", "matmul", 16, eligible_pools=("Zed",))})
    with pytest.raises(EligibilityError, match="'z'"):
        resolve_eligibility(dag, specs)
    assert dag.tasks["a"].eligible_pools is None  # 'a' would have been narrowed to ("P",); not left half-done


def test_coordinator_narrows_eligibility_for_the_run_only_so_one_dag_can_meet_other_pools(tmp_path):
    dag = DAG({"a": Task("a", "matmul", 16)})
    with WorkerPool(pools={"P": PoolSpec((0,)), "Q": PoolSpec((1,), task_types=("compression",))}, warmup=False) as p, \
            EventLogger("r", output_dir=tmp_path) as log:
        assert Coordinator(dag, p, FirstIdleScheduler(), log).run(run_timeout=60).status == "completed"
    started = next(e for e in read_events(log.path) if e["event"] == "run_started")
    assert started["tasks"]["a"]["eligible_pools"] == ["P"] and dag.tasks["a"].assigned_pool == "P"
    assert dag.tasks["a"].eligible_pools is None  # declared value restored: a later pool set is judged afresh


def test_criticality_picks_pools_named_p_and_e_not_dict_order():
    dag = DAG({"a": Task("a", "matmul", 16)})
    s = CriticalityScheduler()
    s.on_run_start(dag, RuntimeState(dag, {"X0": "X", "E0": "E", "P0": "P"}))
    assert (s.fast, s.slow) == ("P", "E")
    s.on_run_start(dag, RuntimeState(dag, {"X0": "X", "Y0": "Y"}))  # no P/E: worker order
    assert (s.fast, s.slow) == ("X", "Y")


def test_remote_slot_cannot_reuse_the_name_of_a_cpu_pool():
    with pytest.raises(ValueError, match="collides"):
        WorkerPool(pools={"R": PoolSpec((0,))}, remote_slots=[RemoteSlot(link=None, port=1, pool="R")], warmup=False)


def test_coordinator_raises_eligibility_error_before_logging_anything(pool, tmp_path):
    dag = DAG({"x": Task("x", "matmul", 16, eligible_pools=("Z",))})
    with EventLogger("r", output_dir=tmp_path) as log:
        with pytest.raises(EligibilityError):
            Coordinator(dag, pool, FirstIdleScheduler(), log).run()
    assert read_events(log.path) == []


def test_cuda_only_variants_are_never_eligible_for_a_pool_without_cuda(monkeypatch):
    import caosched.apps.stages as stages

    monkeypatch.setattr(stages, "cuda_stages", lambda: {"gpu_only": object(), "img_edges": object()})
    mixed = {"P": PoolSpec((0,)), "G": PoolSpec((0,), "cuda")}
    dag = DAG({"g": Task("g", "gpu_only", 1), "e": Task("e", "img_edges", 1, params={}),
               "m": Task("m", "matmul", 1), "x": Task("x", "extcmd", 1, params={})})
    resolve_eligibility(dag, mixed)
    assert [dag.tasks[t].eligible_pools for t in "gemx"] == [("G",), None, ("P",), ("P",)]
    with pytest.raises(EligibilityError, match="cannot run it"):
        resolve_eligibility(DAG({"g": Task("g", "gpu_only", 1, eligible_pools=("P", "G"))}), mixed)
    with pytest.raises(EligibilityError, match="no eligible worker"):  # no cuda pool at all
        resolve_eligibility(DAG({"g": Task("g", "gpu_only", 1)}), {"P": PoolSpec((0,))})
    monkeypatch.setattr(stages, "cuda_stages", lambda: {})  # CPU stage without a CUDA variant
    with pytest.raises(EligibilityError, match="cannot run it"):
        resolve_eligibility(DAG({"e": Task("e", "img_edges", 1, params={}, eligible_pools=("P", "G"))}), mixed)


def test_cuda_pool_refuses_cleanly_when_cuda_is_unavailable(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")  # inherited by the spawned worker: no device visible
    with pytest.raises(WorkerPoolError, match="CUDA"):
        WorkerPool(pools={"G": PoolSpec((0,), "cuda")}, warmup=False, startup_timeout=120)


def test_cuda_flag_baked_into_tasks_no_longer_breaks_cpu_pools(tmp_path):
    """Audit D1: device is chosen by the worker's pool kind, so a CUDA-flagged
    stage on a CPU pool runs the CPU variant instead of raising."""
    small = dict(width=128, height=128, grid=2, seed=7)
    dag = build_image_pipeline(**small, device_params={"img_edges": {"device": "cuda"}})
    ref = run_reference(build_image_pipeline(**small))["package"]
    with WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=False) as p, EventLogger("d", output_dir=tmp_path) as log:
        s = Coordinator(dag, p, GreedyEligibleScheduler(), log, artifact_dir=tmp_path / "d").run(run_timeout=120)
    assert s.status == "completed"
    assert verify_output(artifact_path(tmp_path / "d", "package").read_bytes(), ref)["match"] == "exact"


def test_real_cuda_worker_runs_cuda_variants_selected_by_pool(tmp_path):
    from caosched.apps.cuda_stages import cuda_available

    if not cuda_available():
        pytest.skip("no CUDA device")
    small = dict(width=128, height=128, grid=2, seed=7)
    gpu_stages = {s: ["G"] for s in ("img_denoise", "img_edges", "img_features")}
    dag = build_image_pipeline(**small, remote_stages=gpu_stages)  # "G" is just an extra eligible pool name
    ref = run_reference(build_image_pipeline(**small))["package"]
    with WorkerPool(pools={"E": PoolSpec((0,)), "G": PoolSpec((0,), "cuda")}, warmup=False, startup_timeout=180) as p, \
            EventLogger("g", output_dir=tmp_path) as log:
        assert [i.capabilities["cuda"] for i in p.ready_infos() if i.capabilities] == [True]
        s = Coordinator(dag, p, GreedyEligibleScheduler(priority=["G", "E"]), log, artifact_dir=tmp_path / "g").run(
            run_timeout=180)
    assert s.status == "completed" and s.tasks_per_pool.get("G", 0) > 0
    assert {dag.tasks[t].workload for t in dag.tasks if dag.tasks[t].assigned_pool == "G"} <= set(gpu_stages)
    # "numeric" is verify_output's stated tolerance: mosaic within 1 grey level, descriptors allclose(rtol=1e-5, atol=1e-6)
    assert verify_output(artifact_path(tmp_path / "g", "package").read_bytes(), ref)["match"] in ("exact", "numeric")
