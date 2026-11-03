"""Dashboard v2: the original dashboard (unchanged) plus /api/final, a local-GPU entry in /api/system and an updated static page.
Run: python -m caosched.dashboard_v2 --port 8766 --open"""
from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from caosched.dashboard import data, server as base
from caosched.dashboard_v2 import extra
from caosched.dashboard_v2.gpu_live import gpu_live

STATIC = Path(__file__).resolve().parent / "static"


class Handler(base.Handler):
    server_version = "CAODashboardV2/1.0"

    def do_GET(self):  # noqa: N802
        if self._host_ok():
            path = urlparse(self.path).path
            if path == "/final_charts.js":
                return self._send((STATIC / "final_charts.js").read_bytes(), "text/javascript; charset=utf-8")
            if path in base.STATIC_FILES:
                name, ctype = base.STATIC_FILES[path]
                return self._send((STATIC / name).read_bytes().replace(b"__CAO_TOKEN__", base.TOKEN.encode()), ctype)
            if path == "/api/system":
                return self._json({**data.system_snapshot(), "cpu_percent": extra.cpu_percent_now(), "gpu": {**extra.gpu_info(), **gpu_live()}, "live": base.LIVE.state()})
            if path == "/api/gpu":
                return self._json(extra.gpu_final())
            if path == "/api/hardware":
                return self._json(extra.hardware())
            if path == "/api/final":
                try:
                    return self._json(extra.final_results())
                except Exception as exc:  # noqa: BLE001
                    return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return super().do_GET()


def serve(port: int = 8766, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"CAO dashboard v2 on {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
