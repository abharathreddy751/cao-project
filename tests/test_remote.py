"""Phase 5: link shim, payload model, transfer model, wire protocol, and a real
node + proxy behind the shim inside the worker pool / coordinator."""
import importlib.util
import json
import socket
from pathlib import Path

import pytest

from caosched.core.coordinator import Coordinator
from caosched.core.dag import build_independent_dag
from caosched.core.event_log import EventLogger, read_events
from caosched.core.task import TaskMessage
from caosched.core.worker_pool import RemoteSlot, WorkerPool
from caosched.estimators import TaskSpec
from caosched.remote import LinkConfig, TransferModel, payload_bytes, precise_wait
from caosched.remote.protocol import recv_frame, send_frame
from caosched.schedulers.simple import GreedyEligibleScheduler


def test_payload_sizes_follow_workload_data():
    assert payload_bytes("matmul", 256) == (2 * 256 * 256 * 8, 256 * 256 * 8)
    assert payload_bytes("image_filter", 512) == (512 * 512 * 3, 512 * 512 * 3)
    up, down = payload_bytes("compression", 1 << 20)
    assert up == 1 << 20 and 0 < down < up  # real zlib output of the (compressible) input
    with pytest.raises(KeyError):
        payload_bytes("sorting", 10)


def test_link_config_delay_and_validation():
    link = LinkConfig("l", latency_s=0.002, bandwidth_Bps=1e6, per_message_s=0.0005)
    assert link.shim_delay(1000) == pytest.approx(0.002 + 0.0005 + 0.001)
    assert LinkConfig("z").shim_delay(10**9) == 0.0
    for bad in (dict(latency_s=-1), dict(bandwidth_Bps=0), dict(per_message_s=-0.1)):
        with pytest.raises(ValueError):
            LinkConfig("x", **bad)
    assert LinkConfig.from_dict(link.to_dict()) == link


def test_precise_wait_is_not_short_and_close():
    for target in (0.0003, 0.002, 0.008):
        got = precise_wait(target)
        assert target <= got < target + 0.002


def test_transfer_model_local_zero_remote_shim_plus_socket(tmp_path):
    link = LinkConfig("l", latency_s=0.001, bandwidth_Bps=1e7)
    t = TaskSpec("t", "image_filter", 512)
    up, down = payload_bytes("image_filter", 512)
    tm = TransferModel({"R": link}, socket_a_s=0.0002, socket_b_s_per_byte=1e-9)
    assert tm.estimate(t, "P") == 0.0
    assert tm.estimate(t, "R") == pytest.approx(link.shim_delay(up) + link.shim_delay(down) + 0.0002 + 1e-9 * (up + down))
    prof = tmp_path / "p_profile.json"
    prof.write_text(json.dumps({"link_calibration": None}))
    with pytest.raises(ValueError):
        TransferModel.with_profile_calibration({"R": link}, prof)
    prof.write_text(json.dumps({"link_calibration": {"socket_a_s": 0.001, "socket_b_s_per_byte": 2e-9}}))
    assert TransferModel.with_profile_calibration({"R": link}, prof).socket_b_s_per_byte == 2e-9


def test_protocol_roundtrip_large_payload():
    a, b = socket.socketpair()
    try:
        import threading

        payload = bytes(range(256)) * 20000  # 5 MB, forces many partial recv calls
        th = threading.Thread(target=send_frame, args=(a, {"op": "task", "x": 1}, payload))
        th.start()
        header, got = recv_frame(b)
        th.join()
        assert header["op"] == "task" and header["payload_len"] == len(payload) and got == payload
    finally:
        a.close()
        b.close()


def test_link_calibration_fit_recovers_line():
    path = Path(__file__).resolve().parents[1] / "scripts" / "profile_static.py"
    spec = importlib.util.spec_from_file_location("profile_static", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = [{"is_warmup": False, "payload_bytes": n, "transfer_s": 0.0005 + 2e-9 * n} for n in (1e5, 1e6, 4e6)]
    rows.append({"is_warmup": True, "payload_bytes": 1e6, "transfer_s": 9.0})  # warmups ignored
    rows.append({"is_warmup": False, "payload_bytes": None, "transfer_s": None})  # local rows ignored
    cal = mod.fit_link_calibration(rows)
    assert cal["socket_a_s"] == pytest.approx(0.0005) and cal["socket_b_s_per_byte"] == pytest.approx(2e-9)


@pytest.fixture(scope="module")
def remote_pool():
    link = LinkConfig("test", latency_s=0.004, bandwidth_Bps=50e6)
    pool = WorkerPool(p_core_slots=[], e_core_slots=[0], warmup=True,
                      remote_slots=[RemoteSlot(link, node_core=1)])
    yield pool, link
    pool.shutdown()


def test_remote_slot_handshake_and_task_through_the_shim(remote_pool):
    pool, link = remote_pool
    info = {i.worker_id: i for i in pool.ready_infos()}
    assert pool.worker_ids("R") == ["R0"] and info["R0"].actual_affinity == (1,) and info["R0"].affinity_ok
    assert info["R0"].pid != info["E0"].pid
    pool.submit("R0", TaskMessage("x", "compression", 1 << 20, 3))
    r = pool.poll_result(timeout=60)
    up, down = payload_bytes("compression", 1 << 20)
    assert r.error is None and r.wall_time_seconds > 0 and r.payload_bytes == up + down
    assert r.transfer_s >= link.shim_delay(up) + link.shim_delay(down)       # never shorter than the shim
    assert link.shim_delay(up) <= r.transfer_up_s < r.transfer_s
    assert r.t_started <= r.t_completed


def test_coordinator_logs_transfer_for_remote_tasks_only(remote_pool, tmp_path):
    pool, _ = remote_pool
    dag = build_independent_dag(6, workload="matmul", size=64)
    pol = GreedyEligibleScheduler(priority=["R", "E"], name="B4_test_R_first")
    with EventLogger("remote", output_dir=tmp_path) as log:
        assert Coordinator(dag, pool, pol, log).run(run_timeout=60).status == "completed"
    done = [e for e in read_events(log.path) if e["event"] == "task_completed"]
    assert {e["pool"] for e in done} == {"R", "E"}
    for e in done:
        assert ("transfer_s" in e) == (e["pool"] == "R")
    assert all(t.transfer_s is not None for t in dag.tasks.values() if t.assigned_pool == "R")
