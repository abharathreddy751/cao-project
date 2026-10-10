"""Remote proxy: the local worker-slot process for one remote node.

To the coordinator it is indistinguishable from a local worker (same input /
output queues, same ``WorkerReady`` handshake, same ``TaskResult``), so no
scheduler or coordinator code knows a task went over a link -- except via the
extra transfer fields on the result. For each task it:

  1. waits the link shim's upstream delay, then sends the request header and
     an input-sized payload over TCP;
  2. receives the node's result header and reply payload;
  3. waits the shim's downstream delay.

Measured (``clock.now``, QPC) and returned: total transfer time = round trip
minus the node-side span (node t_completed - t_started, a duration, so it is
valid even when the node's clock differs from ours), upstream time, and the
payload bytes. ``t_started`` / ``t_completed`` on the result are the node's
values; they share our timebase only because the Phase 5 node runs on this
machine (documented limitation for a physical device).
"""
from __future__ import annotations

import socket

from caosched.core.task import TaskResult
from caosched.remote.link import LinkConfig, payload_bytes, precise_wait
from caosched.remote.protocol import recv_frame, send_frame
from caosched.util import clock


def proxy_loop(worker_id: str, host: str, port: int, link: LinkConfig, affinity: list[int],
               input_queue, output_queue, connect_timeout: float = 60.0, same_clock: bool = True) -> None:
    """``same_clock`` False (a physical device): the node's timestamps are not
    in our timebase, so t_started / t_completed are reconstructed on the proxy
    side: t_completed = reply received, t_started = t_completed - node span
    (error bounded by the one-way return latency); the node's own durations
    (kernel, span) are used unchanged."""
    import psutil

    from caosched.core.worker_pool import WorkerReady

    if affinity:
        try:
            psutil.Process().cpu_affinity(affinity)
        except Exception:  # noqa: BLE001 - proxy pinning is best-effort; node pinning is verified
            pass
    sock = socket.create_connection((host, port), timeout=connect_timeout)
    sock.settimeout(None)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    send_frame(sock, {"op": "hello"})
    hello, _ = recv_frame(sock)
    output_queue.put(("ready", WorkerReady(
        worker_id, hello["pid"], tuple(hello["requested_affinity"]), tuple(hello["actual_affinity"]),
        hello["affinity_error"], hello["warmup_seconds"], None, hello.get("capabilities"))))
    try:
        while True:
            msg = input_queue.get()
            if msg is None:
                send_frame(sock, {"op": "bye"})
                break
            if isinstance(msg, LinkConfig):  # control message: switch link conditions between runs
                link = msg
                continue
            is_stage = msg.params is not None
            read_t = write_t = 0.0
            if is_stage:  # application stage: ship the REAL input artifacts
                from caosched.apps.artifacts import read_artifacts
                t_r = clock.now()
                blobs = read_artifacts(msg.input_refs)
                read_t = clock.now() - t_r
                up_b = sum(len(b) for b in blobs)
            t0 = clock.now()
            if is_stage:
                precise_wait(link.shim_delay(up_b))
                send_frame(sock, {"op": "stage", "task_id": msg.task_id, "stage": msg.workload,
                                  "params": msg.params, "input_lens": [len(b) for b in blobs]}, b"".join(blobs))
            else:  # benchmark kernel: stand-in payload of the modelled size
                up_b, down_b = payload_bytes(msg.workload, msg.size)
                precise_wait(link.shim_delay(up_b))
                send_frame(sock, {"op": "task", "task_id": msg.task_id, "workload": msg.workload,
                                  "size": msg.size, "seed": msg.seed, "reply_len": down_b}, bytes(up_b))
            t_sent = clock.now()
            reply, payload = recv_frame(sock)
            t_recv = clock.now()
            down_b = len(payload)
            precise_wait(link.shim_delay(down_b))
            if is_stage and reply["error"] is None:
                from caosched.apps.artifacts import write_artifact
                t_w = clock.now()
                write_artifact(msg.output_ref, payload)
                write_t = clock.now() - t_w
            t_end = clock.now()
            node_span = reply["t_completed"] - reply["t_started"]
            if same_clock:
                t_st, t_co = reply["t_started"], reply["t_completed"]
            else:
                t_co = t_recv
                t_st = t_recv - node_span
            io_s = (read_t + (reply.get("codec_s") or 0.0) + write_t) if is_stage else None
            output_queue.put(("result", TaskResult(
                msg.task_id, worker_id, reply["kernel_s"], reply["error"], t_st, t_co,
                transfer_s=(t_end - t0) - node_span - write_t, transfer_up_s=t_sent - t0,
                payload_bytes=up_b + down_b, output_bytes=down_b if is_stage else None, io_s=io_s)))
    finally:
        sock.close()
