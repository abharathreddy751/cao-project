"""Wire protocol between a remote proxy (local worker slot) and a remote node.

frame := uint32 big-endian header length | JSON header (utf-8) | payload bytes
The header's ``payload_len`` gives the payload size. Plain TCP + JSON keeps
the node portable to a physical ARM device (Python + numpy + Pillow only).
"""
from __future__ import annotations

import json
import socket
import struct

_LEN = struct.Struct(">I")


def send_frame(sock: socket.socket, header: dict, payload: bytes = b"") -> None:
    header = {**header, "payload_len": len(payload)}
    h = json.dumps(header).encode("utf-8")
    sock.sendall(_LEN.pack(len(h)) + h)
    if payload:
        sock.sendall(payload)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray(n)
    view = memoryview(buf)
    got = 0
    while got < n:
        k = sock.recv_into(view[got:], n - got)
        if k == 0:
            raise ConnectionError("peer closed the connection")
        got += k
    return bytes(buf)


def recv_frame(sock: socket.socket) -> tuple[dict, bytes]:
    (hlen,) = _LEN.unpack(_recv_exact(sock, _LEN.size))
    header = json.loads(_recv_exact(sock, hlen).decode("utf-8"))
    n = int(header.get("payload_len", 0))
    return header, (_recv_exact(sock, n) if n else b"")
