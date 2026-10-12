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


# --- AD-12 hardening: frame caps and shared-secret handshake -------------------------------------------------

def test_recv_frame_rejects_oversized_before_allocating():
    from caosched.remote.protocol import FrameTooLarge
    a, b = socket.socketpair()
    try:
        a.sendall((2**31).to_bytes(4, "big"))  # header length over the cap
        with pytest.raises(FrameTooLarge):
            recv_frame(b)
    finally:
        a.close(); b.close()
    a, b = socket.socketpair()
    try:
        h = json.dumps({"op": "x", "payload_len": 2**40}).encode()
        a.sendall(len(h).to_bytes(4, "big") + h)  # claims 1 TiB, sends none: must fail fast, not allocate or block
        with pytest.raises(FrameTooLarge):
            recv_frame(b)
    finally:
        a.close(); b.close()
    for cap, ok in ((4, False), (5, True)):  # configurable cap, boundary inclusive
        a, b = socket.socketpair()
        try:
            send_frame(a, {"op": "y"}, b"12345")
            if ok:
                assert recv_frame(b, max_payload=cap)[1] == b"12345"
            else:
                with pytest.raises(FrameTooLarge):
                    recv_frame(b, max_payload=cap)
        finally:
            a.close(); b.close()


def _start_node(token=None, max_payload=None):
    import queue
    import threading

    from caosched.remote.node import serve
    q, errs = queue.Queue(), []

    def run():
        try:
            serve("127.0.0.1", 0, None, q, token=token, max_payload=max_payload)
        except Exception as exc:  # noqa: BLE001 - asserted by the tests
            errs.append(exc)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    return q.get(timeout=60), th, errs


def _connect(port, token=None, digest=None):
    """Open a connection and answer the challenge; returns (sock, challenge, reply-to-hello)."""
    from caosched.remote.protocol import auth_digest
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    ch, _ = recv_frame(s)
    d = digest if digest is not None else (auth_digest(token, ch["nonce"]) if token else None)
    send_frame(s, {"op": "hello", "auth": d})
    return s, ch


def test_node_handshake_valid_wrong_missing_and_oversized(monkeypatch):
    monkeypatch.delenv("CAO_REMOTE_TOKEN", raising=False)
    port, th, errs = _start_node(token="s3cret", max_payload=1000)
    for kw in (dict(token="wrong"), dict(), dict(digest="0" * 64),
               dict(digest="é" * 64), dict(digest="\udcff" * 64)):  # wrong, missing, forged, non-ASCII digests
        s, ch = _connect(port, **kw)
        assert ch["auth"] is True
        reply, _ = recv_frame(s)
        assert "error" in reply and "pid" not in reply
        s.close()
    s = socket.create_connection(("127.0.0.1", port), timeout=10)  # oversized pre-auth header length
    recv_frame(s)
    s.sendall((2**31).to_bytes(4, "big"))
    with pytest.raises((ConnectionError, OSError)):
        recv_frame(s)
    s.close()
    assert th.is_alive() and not errs                       # bad peers never stop the node
    s, _ = _connect(port, token="s3cret")                   # valid path
    reply, _ = recv_frame(s)
    assert "pid" in reply and "capabilities" in reply
    h = json.dumps({"op": "task", "payload_len": 5000}).encode()
    s.sendall(len(h).to_bytes(4, "big") + h)                # post-auth oversized payload: rejected before any read
    err, _ = recv_frame(s)
    assert "bad frame" in err["error"] and "FrameTooLarge" in err["error"]
    with pytest.raises((ConnectionError, OSError)):         # that peer is dropped (stream is unrecoverable) ...
        recv_frame(s)
    s.close()
    assert th.is_alive() and not errs                       # ... but the node survives and keeps serving
    s, _ = _connect(port, token="s3cret")
    assert "pid" in recv_frame(s)[0]
    send_frame(s, {"op": "bye"})
    th.join(timeout=10)
    s.close()
    assert not th.is_alive() and not errs


def test_node_survives_bad_messages_and_caps_reply_len(monkeypatch):
    monkeypatch.delenv("CAO_REMOTE_TOKEN", raising=False)
    port, th, errs = _start_node(max_payload=1000)
    s, _ = _connect(port)
    assert "pid" in recv_frame(s)[0]
    send_frame(s, {"op": "task", "workload": "matmul", "size": 16, "seed": 0})  # no task_id
    r, _ = recv_frame(s)
    assert r["task_id"] is None and "task_id" in r["error"] and r["kernel_s"] is None
    send_frame(s, {"op": "task", "task_id": "a", "workload": "matmul", "size": 16, "seed": 0, "reply_len": 10**9})
    r, _ = recv_frame(s)
    assert r["task_id"] == "a" and "reply_len" in r["error"]
    send_frame(s, {"op": "task", "task_id": "b", "workload": "matmul", "size": 16, "seed": 0, "reply_len": "x"})
    assert recv_frame(s)[0]["error"]
    send_frame(s, {"op": "task", "task_id": "c", "workload": "matmul", "size": 16, "seed": 0, "reply_len": 10})
    r, payload = recv_frame(s)                              # same connection still works
    assert r["task_id"] == "c" and r["error"] is None and len(payload) == 10
    send_frame(s, {"op": "bye"})
    th.join(timeout=10)
    s.close()
    assert not th.is_alive() and not errs


def test_proxy_authenticates_the_node_and_token_length_for_public_bind(monkeypatch):
    import queue
    import threading

    from caosched.remote.node import serve
    from caosched.remote.protocol import MIN_TOKEN_BYTES
    from caosched.remote.proxy import proxy_loop
    monkeypatch.delenv("CAO_REMOTE_TOKEN", raising=False)
    with pytest.raises(ValueError, match="shorter"):
        serve("0.0.0.0", 0, None, token="x" * (MIN_TOKEN_BYTES - 1))
    # a node that knows the token: handshake completes in both directions
    port, th, errs = _start_node(token="s3cret")
    inq, outq = queue.Queue(), queue.Queue()
    inq.put(None)
    proxy_loop("R0", "127.0.0.1", port, LinkConfig("z"), [], inq, outq, token="s3cret")
    th.join(timeout=10)
    assert outq.get_nowait()[0] == "ready" and not errs
    # an impostor that accepts any digest but cannot answer the proxy's nonce is rejected by the proxy
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def impostor():
        c, _ = srv.accept()
        send_frame(c, {"op": "challenge", "nonce": "n", "auth": True})
        recv_frame(c)
        send_frame(c, {"pid": 1, "requested_affinity": [], "actual_affinity": [], "affinity_error": None,
                       "warmup_seconds": 0.0, "capabilities": {}})
        c.close()
    t2 = threading.Thread(target=impostor, daemon=True)
    t2.start()
    with pytest.raises(PermissionError, match="node_auth"):
        proxy_loop("R0", "127.0.0.1", srv.getsockname()[1], LinkConfig("z"), [], queue.Queue(), queue.Queue(), token="s3cret")
    t2.join(timeout=10)
    srv.close()


def test_node_valid_token_roundtrip_and_no_token_dev_default(monkeypatch):
    monkeypatch.delenv("CAO_REMOTE_TOKEN", raising=False)
    for token in ("tok", None):  # None: loopback dev default, no auth required, same wire protocol
        port, th, errs = _start_node(token=token)
        s, ch = _connect(port, token=token)
        assert ch["auth"] is bool(token)
        reply, _ = recv_frame(s)
        assert reply["pid"] > 0
        send_frame(s, {"op": "bye"})
        th.join(timeout=10)
        s.close()
        assert not th.is_alive() and not errs


def test_node_refuses_public_bind_without_token(monkeypatch):
    from caosched.remote.node import serve
    monkeypatch.delenv("CAO_REMOTE_TOKEN", raising=False)
    with pytest.raises(ValueError):
        serve("0.0.0.0", 0, None)
