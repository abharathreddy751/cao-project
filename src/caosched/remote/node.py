"""Remote execution node.

Runs tasks it receives over TCP exactly like a local worker (same workload
kernels, same thread pinning, kernel-only timing), and replies with a result
header plus a reply payload of the requested size. In Phase 5 it runs on this
machine (one E-core taken out of the E pool) behind the link shim; on a
physical device it would be started with ``python -m caosched.remote.node
--host 0.0.0.0 --port N`` and the shim configured to zero.

Security (AD-12): the node first sends {"op": "challenge", "nonce", "auth"}; with
a token configured (``--token`` / ``CAO_REMOTE_TOKEN``) the peer's hello must
carry ``auth`` = HMAC-SHA256(token, nonce) or the connection is dropped and the
node keeps listening. Binding a non-loopback host without a token (or with one shorter than
``MIN_TOKEN_BYTES``) is refused. The hello may carry the peer's own ``nonce``; the hello reply then
carries ``node_auth`` = HMAC-SHA256(token, that nonce) so the peer can authenticate the node too.
Frames above ``--max-payload`` bytes are rejected before allocation.

Robustness: a bad message (missing ``task_id``, absurd ``reply_len``, kernel error) gets an error reply
and the connection stays up. A frame that cannot be parsed or exceeds the cap leaves the byte stream
unrecoverable: the node sends an error frame, drops that connection and waits for the next peer.

Messages: {"op": "hello"} -> pid / affinity / warmup / capabilities report;
          {"op": "task", ...}  -> run a benchmark kernel (stand-in payload);
          {"op": "stage", ...} -> run an application stage on the REAL input
                                  bytes in the payload, reply with the output bytes;
          {"op": "bye"} -> exit (with ``--persistent``: wait for the next client instead).
"""
from __future__ import annotations

import argparse
import os
import secrets
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


def _accept_authenticated(srv, token, send_frame, recv_frame):
    """Accept until a peer passes the challenge handshake; return (conn, its hello header).
    A bad peer (wrong/missing digest, oversized or malformed frame, silence) is dropped."""
    from caosched.remote.protocol import digest_ok

    while True:
        conn, _ = srv.accept()
        try:
            conn.settimeout(10)
            nonce = secrets.token_hex(16)
            send_frame(conn, {"op": "challenge", "nonce": nonce, "auth": bool(token)})
            hello, _ = recv_frame(conn, max_payload=0)  # pre-auth frames carry no payload
            if hello.get("op") == "hello" and (not token or digest_ok(token, nonce, hello.get("auth"))):
                conn.settimeout(None)
                return conn, hello
            send_frame(conn, {"error": "authentication failed"})
        except (OSError, ValueError, TypeError):
            pass
        conn.close()


def serve(host: str, port: int, affinity: list[int] | None, ready_queue=None, token: str | None = None,
          max_payload: int | None = None, persistent: bool = False) -> None:
    import psutil

    from caosched.phase0.benchmarks.workloads import WORKLOADS
    from caosched.remote.protocol import MAX_PAYLOAD, MIN_TOKEN_BYTES, auth_digest, recv_frame, resolve_token, send_frame
    from caosched.util import clock

    token = resolve_token(token)
    max_payload = MAX_PAYLOAD if max_payload is None else max_payload
    if host not in ("127.0.0.1", "localhost", "::1"):
        if not token:
            raise ValueError(f"refusing to listen on {host} without a token (set --token or CAO_REMOTE_TOKEN)")
        if len(token.encode()) < MIN_TOKEN_BYTES:
            raise ValueError(f"refusing to listen on {host}: token shorter than {MIN_TOKEN_BYTES} bytes")

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
    def accept():
        c, hello = _accept_authenticated(srv, token, send_frame, recv_frame)
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return c, hello

    conn, first = accept()
    try:
        while True:
            try:
                header, _payload = (first, b"") if first else recv_frame(conn, max_payload=max_payload)
            except OSError:  # peer vanished (killed proxy, reset): a persistent node waits for the next client, else it ends
                if not persistent:
                    raise
                conn.close()
                conn, first = accept()
                continue
            except (ValueError, TypeError) as exc:  # oversized / malformed frame: stream unrecoverable, drop the peer
                try:
                    send_frame(conn, {"error": f"bad frame: {type(exc).__name__}: {exc}"})
                except OSError:
                    pass
                conn.close()
                conn, first = accept()
                continue
            first = None
            op = header.get("op")
            if op == "bye":
                if persistent:  # a new run / pool may reconnect (a node on another machine cannot be respawned by the coordinator)
                    conn.close()
                    conn, first = accept()
                    continue
                break
            if op == "hello":
                reply = {"pid": os.getpid(), "requested_affinity": affinity or [], "actual_affinity": actual,
                         "affinity_error": affinity_error, "warmup_seconds": warmup_s, "capabilities": capabilities()}
                if token and isinstance(header.get("nonce"), str):  # mutual auth: prove we know the secret too
                    reply["node_auth"] = auth_digest(token, header["nonce"])
                send_frame(conn, reply)
                continue
            try:  # one bad message gets an error reply, never ends the node
                task_id = header["task_id"]
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
                    send_frame(conn, {"task_id": task_id, "kernel_s": kernel, "codec_s": codec, "error": error,
                                      "t_started": t_started, "t_completed": t_completed}, out)
                    continue
                reply_len = int(header.get("reply_len", 0))
                if not 0 <= reply_len <= max_payload:
                    raise ValueError(f"reply_len {reply_len} outside 0..{max_payload}")
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
                send_frame(conn, {"task_id": task_id, "kernel_s": kernel, "error": error,
                                  "t_started": t_started, "t_completed": t_completed}, bytes(reply_len))
            except OSError:  # peer gone: nothing to reply to
                if not persistent:
                    raise
                conn.close()
                conn, first = accept()
            except Exception:  # noqa: BLE001
                now = clock.now()
                send_frame(conn, {"task_id": header.get("task_id"), "kernel_s": None, "error": traceback.format_exc(),
                                  "t_started": now, "t_completed": now})
    finally:
        conn.close()
        srv.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--affinity", type=int, nargs="*", default=None)
    ap.add_argument("--token", default=None, help="shared secret (default: $CAO_REMOTE_TOKEN)")
    ap.add_argument("--max-payload", type=int, default=None, help="max frame payload in bytes")
    ap.add_argument("--persistent", action="store_true",
                    help="keep serving: after a client says bye or disconnects, wait for the next one (use for a node on another machine; "
                         "default: one client, then exit)")
    args = ap.parse_args()
    serve(args.host, args.port, args.affinity, token=args.token, max_payload=args.max_payload, persistent=args.persistent)


if __name__ == "__main__":
    main()
