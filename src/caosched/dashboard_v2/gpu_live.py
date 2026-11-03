"""Live GPU numbers for the dashboard card (read-only): utilisation, memory in use, temperature, power draw, clock, from nvidia-smi.

nvidia-smi can take several seconds while the GPU is busy (a CUDA run is exactly when the card matters), and a short timeout made the card fall
back to n/a. A background thread therefore samples it continuously (timeout 20 s) and the request handler only returns the latest sample.
"""
from __future__ import annotations

import subprocess
import threading
import time

QUERY = "utilization.gpu,memory.used,temperature.gpu,power.draw,clocks.sm"
_LATEST: dict = {}
_LOCK = threading.Lock()
_STARTED = False


def _num(x: str):
    x = x.strip()
    return None if x in ("", "N/A", "[N/A]", "[Not Supported]") else float(x)


def _sample() -> dict:
    line = subprocess.run(["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
                          capture_output=True, text=True, timeout=20).stdout.strip().splitlines()[0]
    u, m, t, p, c = line.split(",")
    return {"util_pct": _num(u), "mem_used_mib": _num(m), "temp_c": _num(t), "power_w": _num(p), "sm_clock_mhz": _num(c)}


def _loop() -> None:
    while True:
        try:
            s = _sample()
            s["sampled_at"] = time.time()
            with _LOCK:
                _LATEST.clear()
                _LATEST.update(s)
        except Exception:  # noqa: BLE001 - keep the last good sample, try again
            pass
        time.sleep(0.5)


def gpu_live() -> dict:
    """Latest sample (the first call starts the sampler and waits briefly for the first value). Empty dict if nvidia-smi never answered."""
    global _STARTED
    if not _STARTED:
        _STARTED = True
        threading.Thread(target=_loop, daemon=True, name="gpu-sampler").start()
        for _ in range(40):
            with _LOCK:
                if _LATEST:
                    break
            time.sleep(0.1)
    with _LOCK:
        out = dict(_LATEST)
    if out:
        out["age_s"] = round(time.time() - out.pop("sampled_at"), 1)
    return out
