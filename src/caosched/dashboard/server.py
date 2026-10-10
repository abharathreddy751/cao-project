"""Local dashboard server (standard library only; binds to 127.0.0.1).

GET  /                         the single-page dashboard (static/)
GET  /api/system               live topology, per-LP CPU %, memory, live-run state
GET  /api/sessions             accepted sessions and their demo runs
GET  /api/run?session=&run=    one run reconstructed from its event log (replay or live)
GET  /api/artifact?session=&run=&which=source|mosaic   PNG of a real run artifact
GET  /api/comparison           B4 vs EFT_E1_rc from the verified Phase B summary
GET  /api/hardware             status table of docs/REMOTE_DEVICES.md
GET  /api/live                 live dashboard runs on disk + the active one
POST /api/live/start           {"policy": "B4"|"EFT", "k": 1|4|16|64} -> starts one live run
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from caosched.dashboard import data, live

STATIC = Path(__file__).resolve().parent / "static"
STATIC_FILES = {"/": ("index.html", "text/html; charset=utf-8"),
                "/index.html": ("index.html", "text/html; charset=utf-8"),
                "/app.css": ("app.css", "text/css; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8")}


class LiveManager:
    """At most one live run at a time, each in its own subprocess."""

    def __init__(self):
        self._lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.session: str | None = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, policy: str, k: int) -> dict:
        import psutil
        if policy not in live.POLICIES or k not in live.LEVELS:
            raise ValueError(f"policy must be one of {list(live.POLICIES)}, k one of {list(live.LEVELS)}")
        with self._lock:
            if self.running():
                raise RuntimeError(f"a live run is already in progress ({self.session})")
            avail = psutil.virtual_memory().available / 2**30
            if avail < live.MIN_START_GIB:
                raise RuntimeError(f"not enough free memory: {avail:.2f} GiB available, "
                                   f"{live.MIN_START_GIB} GiB required (runner preflight)")
            out = live.new_session_dir(policy, k)
            self.session = out.name
            log = open(out / "subprocess.log", "w", encoding="utf-8")
            self.proc = subprocess.Popen([sys.executable, "-m", "caosched.dashboard.live", "--policy", policy,
                                          "--k", str(k), "--out", str(out)], stdout=log, stderr=subprocess.STDOUT,
                                         cwd=str(data.ROOT))
            return {"session": out.name, "run": f"live_{policy}", "pid": self.proc.pid}

    def state(self) -> dict:
        st = live.read_status(live.DASH_RUNS / self.session) if self.session else {}
        return {"session": self.session, "process_running": self.running(),
                "exit_code": None if self.proc is None else self.proc.poll(), **st}


LIVE = LiveManager()


class Handler(BaseHTTPRequestHandler):
    server_version = "CAODashboard/1.0"

    def log_message(self, fmt, *args):  # quiet console; errors are still returned to the browser
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(json.dumps(obj, default=str).encode("utf-8"), "application/json", code)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in STATIC_FILES:
                name, ctype = STATIC_FILES[u.path]
                return self._send((STATIC / name).read_bytes(), ctype)
            if u.path == "/api/system":
                return self._json({**data.system_snapshot(), "live": LIVE.state()})
            if u.path == "/api/sessions":
                return self._json(data.accepted_sessions())
            if u.path == "/api/run":
                return self._json(data.run_view(data.session_log(q.get("session", ""), q.get("run", ""))))
            if u.path == "/api/artifact":
                png = data.artifact_png(data.session_log(q.get("session", ""), q.get("run", "")), q.get("which", ""))
                return self._send(png, "image/png")
            if u.path == "/api/comparison":
                return self._json(data.comparison())
            if u.path == "/api/hardware":
                return self._json(data.hardware_status())
            if u.path == "/api/live":
                return self._json({"active": LIVE.state(), "runs": data.live_runs()})
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except data.NotFound as exc:
            return self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI, never silently swallowed
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path != "/api/live/start":
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            return self._json(LIVE.start(str(body.get("policy")), int(body.get("k"))))
        except (ValueError, TypeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.CONFLICT)


def serve(port: int = 8765, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"CAO dashboard on {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
