"""Wire protocol between a remote proxy (local worker slot) and a remote node.

frame := uint32 big-endian header length | JSON header (utf-8) | payload bytes
The header's ``payload_len`` gives the payload size. Plain TCP + JSON keeps
the node portable to a physical ARM device (Python + numpy + Pillow only).

Hardening (AD-12): frame sizes are capped before any buffer is allocated, and
a node started with a shared secret (``CAO_REMOTE_TOKEN`` or ``--token``) sends
a random challenge on accept; the first frame must carry
HMAC-SHA256(token, nonce), compared in constant time. The authentication is
mutual: the hello also carries the peer's own ``nonce`` and the node's hello
reply carries ``node_auth`` = HMAC-SHA256(token, that nonce), which the proxy
verifies, so a node that does not know the secret is rejected too. The secret
never crosses the wire. Limit: no encryption of the payload (use loopback or a
trusted LAN); a non-loopback bind requires a token of >= MIN_TOKEN_BYTES.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import struct

_LEN = struct.Struct(">I")
MAX_HEADER = 1 << 20      # JSON header cap, bytes
MAX_PAYLOAD = 256 << 20   # payload cap, bytes (image artifacts are a few MB)
TOKEN_ENV = "CAO_REMOTE_TOKEN"
MIN_TOKEN_BYTES = 32      # shortest secret accepted when listening beyond loopback


class FrameTooLarge(ValueError):
    pass


def resolve_token(token: str | None = None) -> str | None:
    return token or os.environ.get(TOKEN_ENV) or None


def auth_digest(token: str, nonce: str) -> str:
    return hmac.new(token.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def digest_ok(token: str, nonce: str, digest) -> bool:
    # bytes, not str: compare_digest raises TypeError on a non-ASCII str
    return isinstance(digest, str) and hmac.compare_digest(auth_digest(token, nonce).encode(), digest.encode("utf-8", "replace"))


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


def recv_frame(sock: socket.socket, max_header: int = MAX_HEADER, max_payload: int = MAX_PAYLOAD) -> tuple[dict, bytes]:
    (hlen,) = _LEN.unpack(_recv_exact(sock, _LEN.size))
    if hlen > max_header:
        raise FrameTooLarge(f"header length {hlen} exceeds cap {max_header}")
    header = json.loads(_recv_exact(sock, hlen).decode("utf-8"))
    if not isinstance(header, dict):
        raise ValueError("frame header is not an object")
    n = int(header.get("payload_len", 0))
    if not 0 <= n <= max_payload:
        raise FrameTooLarge(f"payload length {n} outside 0..{max_payload}")
    return header, (_recv_exact(sock, n) if n else b"")
