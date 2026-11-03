"""Dashboard v2 extras (read-only): local GPU status via nvidia-smi and the final static-vs-dynamic results from the stored CSV files."""
from __future__ import annotations

import csv
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_GPU: dict | None = None


def gpu_info() -> dict:
    global _GPU
    if _GPU is None:
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout.strip().splitlines()[0]
            name, mem, drv = [x.strip() for x in out.split(",")]
            _GPU = {"available": True, "name": name, "memory_mib": int(mem), "driver": drv}
        except Exception as exc:  # noqa: BLE001 - shown on the page
            _GPU = {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    return _GPU


def final_results() -> dict:
    ev = ROOT / "data" / "results" / "final_20261101" / "eval" / "analysis_h16_l120"
    with (ev / "confirmatory.csv").open(newline="", encoding="utf-8") as fh:
        conf = list(csv.DictReader(fh))
    with (ROOT / "RESULTS_TABLE_FINAL.csv").open(newline="", encoding="utf-8") as fh:
        prim = [r for r in csv.DictReader(fh) if r["workload"] == "h16_l120" and r["kind"] != "confirmatory"]
    keep = ("config", "policy", "kind", "e2e_geo_mean_s", "e2e_ci_lo_s", "e2e_ci_hi_s", "tasks_cpu", "tasks_gpu", "gpu_busy_frac")
    with (ROOT / "RESULTS_TABLE_FINAL.csv").open(newline="", encoding="utf-8") as fh:
        allrows = [r for r in csv.DictReader(fh) if r["kind"] != "confirmatory"]
    akeep = keep + ("workload", "vs_static_effect_pct", "vs_static_ci_lo_pct", "vs_static_ci_hi_pct", "vs_B4_effect_pct", "vs_B4_ci_lo_pct", "vs_B4_ci_hi_pct", "vs_static_classification", "vs_B4_classification")
    return {"source": "RESULTS_TABLE_FINAL.csv and analysis_h16_l120/confirmatory.csv (stored, real measurements, primary workload)",
            "all": [{k: r[k] for k in akeep} for r in allrows],
            "confirmatory": [{k: r[k] for k in ("id", "cond", "ref", "n_blocks", "effect_pct", "ci_lo_pct", "ci_hi_pct", "p_holm", "classification")} for r in conf],
            "primary": [{k: r[k] for k in keep} for r in prim]}


def cpu_percent_now() -> list[float]:
    """Per-LP CPU %, measured over a short blocking window. psutil's interval=None keeps its baseline per thread, and the HTTP server
    handles every request in a new thread, so the original dashboard's call returned 0 for every LP after the first request."""
    import psutil
    return psutil.cpu_percent(interval=0.25, percpu=True)


def gpu_final() -> dict:
    """The GPU speed-up records the final benchmark used (512 px rows of the original and the extended record), not the newest file by mtime."""
    import json
    recs = [("original record", ROOT / "data/results/stage1_20261011/gpu/gpu_spike.json"),
            ("extended record", ROOT / "data/results/final_20261101/gpu_spike_iters/spike_20261101T144333/gpu_spike.json")]
    rows, env = [], None
    for tag, p in recs:
        d = json.loads(p.read_text(encoding="utf-8"))
        env = d.get("env") if tag.startswith("extended") else env
        for r in d["rows"]:
            if r.get("side") != 512:
                continue
            rows.append({"record": tag, "stage": r["stage"], "params": r.get("params"), "side": r["side"], "reps": r.get("reps"),
                         "cpu_ms": r["cpu_median_s"] * 1e3, "gpu_ms": r["gpu_median_s"] * 1e3, "speedup": r.get("speedup"),
                         "equivalent": r.get("equivalent"), "max_abs": r.get("max_abs"), "verdict": r.get("verdict")})
    return {"source": "data/results/stage1_20261011/gpu/gpu_spike.json + data/results/final_20261101/gpu_spike_iters/.../gpu_spike.json (512 px rows: the records the final benchmark used)",
            "env": env, "rows": rows}


def hardware() -> dict:
    """docs/REMOTE_DEVICES.md status table, with the local-GPU row brought up to date (the document itself is not edited)."""
    from caosched.dashboard import data
    h = data.hardware_status()
    for r in h["rows"]:
        if "img_edges" in r.get("item", "") and "cuda" in r.get("item", ""):
            r["item"] = r["item"] + " [local RTX 3050; the remote T4 variant is a separate, still unexecuted case]"
            r["executed"] = "yes: local CUDA worker G, final benchmark (GPU tasks in every _gpu / _ext condition)"
            r["verified"] = "yes: output equivalent and 7.7x faster than CPU at 512 px (GPU spike, tab 5); benchmark outputs verified"
    h["note"] = "Local-GPU row updated by dashboard v2; the remote Pi and T4 rows are unchanged."
    return h
