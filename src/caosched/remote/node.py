"""Remote execution node.

Runs tasks it receives over TCP exactly like a local worker (same workload
kernels, same thread pinning, kernel-only timing), and replies with a result
header plus a reply payload of the requested size. In Phase 5 it runs on this
machine (one E-core taken out of the E pool) behind the link shim; on a
physical device it would be started with ``python -m caosched.remote.node
--host 0.0.0.0 --port N`` and the shim configured to zero.

Messages: {"op": "hello"} -> pid / affinity / warmup / capabilities report;
          {"op": "task", ...}  -> run a benchmark kernel (stand-in payload);
          {"op": "stage", ...} -> run an application stage on the REAL input
                                  bytes in the payload, reply with the output bytes;
          {"op": "bye"} -> exit.
"""
from __future__ import annotations

import argparse
import os
import socket
import time
import traceback

from caosched.util.threadpin import pin_single_thread

pin_single_thread()

_WARMUP_SIZES = {"matmul": 16, "image_filter": 16, "compression": 1024}


def capabilities() -> dict:
    """What this node can run (reported in the hello reply, logged by the
    coordinator). CUDA is reported only if PyTorch is importable and sees a
    device -- never assumed."""
    import platform

    import numpy

    cap = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
           "numpy": numpy.__version__, "cuda": False, "cuda_device": None}
    try:
        import PIL
        cap["pillow"] = PIL.__version__
    except Exception:  # noqa: BLE001
        cap["pillow"] = None
    try:
        import torch
        if torch.cuda.is_available():
            cap["cuda"] = True
            cap["cuda_device"] = torch.cuda.get_device_name(0)
    except Exception:  # noqa: BLE001 - torch absent: CPU-only node
        pass
    try:
        from caosched.apps.stages import STAGES
        cap["stages"] = sorted(STAGES)
    except Exception:  # noqa: BLE001
        cap["stages"] = []
    return cap


def serve(host: str, port: int, affinity: list[int] | None, ready_queue=None) -> None:
    import psutil

    from caosched.phase0.benchmarks.workloads import WORKLOADS
    from caosched.remote.protocol import recv_frame, send_frame
    from caosched.util import clock

    proc = psutil.Process()
    affinity_error = None
    if affinity:
        try:
            proc.cpu_affinity(affinity)
        except Exception as exc:  # noqa: BLE001 - reported in the hello reply
            affinity_error = f"{type(exc).__name__}: {exc}"
    actual = list(proc.cpu_affinity())
    t0 = time.perf_counter()
    for name, wl in WORKLOADS.items():
        wl.run(wl.prepare(_WARMUP_SIZES.get(name, 16), 0))
    warmup_s = time.perf_counter() - t0

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    if ready_queue is not None:
        ready_queue.put(srv.getsockname()[1])  # tell the launcher which port we got
    conn, _ = srv.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        while True:
            header, _payload = recv_frame(conn)
            op = header.get("op")
            if op == "bye":
                break
            if op == "hello":
                send_frame(conn, {"pid": os.getpid(), "requested_affinity": affinity or [],
                                  "actual_affinity": actual, "affinity_error": affinity_error,
                                  "warmup_seconds": warmup_s, "capabilities": capabilities()})
                continue
            if op == "stage":
                from caosched.apps.stages import run_stage
                t_started = clock.now()
                out, kernel, codec, error = b"", None, None, None
                try:
                    blobs, off = [], 0
                    for n in header["input_lens"]:
                        blobs.append(_payload[off:off + n])
                        off += n
                    out, kernel, codec = run_stage(header["stage"], blobs, header["params"])
                except Exception:  # noqa: BLE001
                    error = traceback.format_exc()
                    out = b""
                t_completed = clock.now()
                send_frame(conn, {"task_id": header["task_id"], "kernel_s": kernel, "codec_s": codec, "error": error,
                                  "t_started": t_started, "t_completed": t_completed}, out)
                continue
            t_started = clock.now()
            kernel = error = None
            try:
                wl = WORKLOADS[header["workload"]]
                inputs = wl.prepare(int(header["size"]), int(header["seed"]))
                s = time.perf_counter()
                wl.run(inputs)
                kernel = time.perf_counter() - s
            except Exception:  # noqa: BLE001 - report, never crash the node
                error = traceback.format_exc()
            t_completed = clock.now()
            send_frame(conn, {"task_id": header["task_id"], "kernel_s": kernel, "error": error,
                              "t_started": t_started, "t_completed": t_completed},
                       bytes(int(header.get("reply_len", 0))))
    finally:
        conn.close()
        srv.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--affinity", type=int, nargs="*", default=None)
    args = ap.parse_args()
    serve(args.host, args.port, args.affinity)


if __name__ == "__main__":
    main()
