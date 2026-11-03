"""Fourth pass of the dashboard v2 build: the GPU card in tab 1 shows LIVE utilisation (with a bar), memory in use, temperature, power and clock,
refreshed with the other live numbers every 2 s. New files only."""
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "src" / "caosched" / "dashboard_v2" / "static"


def rep(s: str, old: str, new: str) -> str:
    if old not in s:
        raise SystemExit("patch3 target not found: " + old[:70])
    return s.replace(old, new, 1)


j = (D / "app.js").read_text(encoding="utf-8")
old = "<dt>Memory</dt><dd>${esc(sys.gpu.memory_mib)} MiB</dd>"
new = ('<dt>GPU load (live)</dt><dd>${sys.gpu.util_pct != null ? esc(sys.gpu.util_pct) + " %" : "n/a"}'
       '<div style="height:6px;background:var(--grid);border-radius:3px;margin-top:4px"><div style="height:6px;width:${Math.min(100, sys.gpu.util_pct || 0)}%;background:var(--accent);border-radius:3px"></div></div></dd>'
       '<dt>Memory in use (live)</dt><dd>${sys.gpu.mem_used_mib != null ? esc(Math.round(sys.gpu.mem_used_mib)) + " / " : ""}${esc(sys.gpu.memory_mib)} MiB'
       '<div style="height:6px;background:var(--grid);border-radius:3px;margin-top:4px"><div style="height:6px;width:${Math.min(100, 100 * (sys.gpu.mem_used_mib || 0) / (sys.gpu.memory_mib || 1))}%;background:var(--pool-E);border-radius:3px"></div></div></dd>'
       '<dt>Temperature &middot; power &middot; clock</dt><dd>${sys.gpu.temp_c != null ? esc(sys.gpu.temp_c) + " &deg;C" : "n/a"} &middot; ${sys.gpu.power_w != null ? esc(sys.gpu.power_w) + " W" : "n/a"} &middot; ${sys.gpu.sm_clock_mhz != null ? esc(sys.gpu.sm_clock_mhz) + " MHz" : "n/a"}</dd>')
j = rep(j, old, new)
(D / "app.js").write_text(j, encoding="utf-8")
print("tab 1: live GPU load, memory, temperature, power")
