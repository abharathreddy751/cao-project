"""Dashboard v3 = dashboard v2 (unchanged) + a sixth tab that runs ONE live block of the final benchmark (all final policies, CPU and RTX 3050 GPU).

  GET  /api/live3                 state of the active live run, the options, and previous live runs
  POST /api/live3/start           {"policy": "PRED_RANK_GREEDY_E2E", "config": "cpu"|"gpu"|"ext"} -> starts one live run (same loopback, Origin and token rules)
Run: python -m caosched.dashboard_v3 --port 8769 --open
"""
from __future__ import annotations

import hmac
import json
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from caosched.dashboard import data, server as base
from caosched.dashboard_v2 import server as v2
from caosched.dashboard_v3 import live3

STATIC = Path(__file__).resolve().parent / "static"
FILES = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"),
         "/app.css": ("app.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
         "/final_charts.js": ("final_charts.js", "text/javascript; charset=utf-8"), "/live3.js": ("live3.js", "text/javascript; charset=utf-8")}


class LiveManager3:
    """At most one live run at a time, each in its own subprocess."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.sid: str | None = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, policy: str, config: str) -> dict:
        if policy not in live3.POLICIES or config not in live3.CONFIGS:
            raise ValueError(f"policy must be one of {list(live3.POLICIES)}, config one of {list(live3.CONFIGS)}")
        with self._lock:
            if self.running():
                raise RuntimeError(f"a live run is already in progress ({self.sid})")
            sid = live3.new_sid(policy, config)
            live3.write_status(sid, state="starting", policy=policy, config=config)
            log = open(live3.status_path(sid).with_suffix(".log"), "w", encoding="utf-8")
            self.proc = subprocess.Popen([sys.executable, "-m", "caosched.dashboard_v3.live3", "--policy", policy, "--config", config, "--sid", sid],
                                         stdout=log, stderr=subprocess.STDOUT, cwd=str(data.ROOT))
            self.sid = sid
            return {"session": sid, "pid": self.proc.pid}

    def state(self) -> dict:
        st = live3.read_status(self.sid) if self.sid else {}
        return {"session": self.sid, "process_running": self.running(), "exit_code": None if self.proc is None else self.proc.poll(), **st, **progress(self.sid, st)}


LIVE3 = LiveManager3()


def progress(sid: str | None, st: dict) -> dict:
    """Where the live run is, from its files: pool start-up, tasks completed so far (event log), verifying the output."""
    if not sid or st.get("state") not in ("starting", "running"):
        return {}
    runs = sorted((live3.DASH3 / "sessions" / sid / "runs").glob("*")) if (live3.DASH3 / "sessions" / sid / "runs").exists() else []
    if not runs:
        return {"phase": "starting the worker pool (CPU workers, CUDA worker)", "tasks_done": 0}
    logs = sorted(runs[0].glob("*.jsonl"))
    if not logs:
        return {"phase": "starting the run", "tasks_done": 0}
    try:
        text = logs[0].read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {"phase": "running", "tasks_done": None}
    done = text.count('"event": "task_completed"')
    total = None
    if '"event": "run_finished"' in text:
        return {"phase": "verifying the output (GPU tasks re-run on the CPU)", "tasks_done": done, "n_tasks": done}
    return {"phase": "running the tasks", "tasks_done": done, "n_tasks": 257}


def previous() -> list[dict]:
    out = []
    for p in sorted((live3.DASH3 / "status").glob("live3_*.json"), reverse=True)[:30]:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if s.get("state") == "done":
            out.append({"session": p.stem, "policy": s.get("policy"), "config": s.get("config"), "run_id": s.get("run_id"),
                        "makespan_s": s.get("end_to_end_makespan_s") or s.get("makespan_s"), "verified": s.get("output_verified")})
    return out


class Handler(v2.Handler):
    server_version = "CAODashboardV3/1.0"

    def do_GET(self):  # noqa: N802
        if self._host_ok():
            path = urlparse(self.path).path
            if path in FILES:
                name, ctype = FILES[path]
                return self._send((STATIC / name).read_bytes().replace(b"__CAO_TOKEN__", base.TOKEN.encode()), ctype)
            if path == "/api/live3":
                return self._json({"active": LIVE3.state(), "policies": list(live3.POLICIES), "configs": list(live3.CONFIGS), "previous": previous()})
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path == "/api/live3/start":
            origin = (self.headers.get("Origin") or "").removeprefix("http://")
            if not (self._host_ok() and origin in self._origins() and hmac.compare_digest(self.headers.get("X-CAO-Token", "").encode("utf-8", "replace"), base.TOKEN.encode())):
                return self._json({"error": "forbidden: bad Host/Origin or missing token"}, HTTPStatus.FORBIDDEN)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                return self._json(LIVE3.start(str(body.get("policy")), str(body.get("config"))))
            except (ValueError, TypeError) as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except RuntimeError as exc:
                return self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
        return super().do_POST()


def serve(port: int = 8769, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"CAO dashboard v3 on {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
