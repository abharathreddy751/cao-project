"""Stage 1 gate check from the raw sequential runs [real]: repeatability of the mosaic, WCS sanity, DAG
extraction versus the generator's own dependencies, per-task times. Writes <evidence>/stage1_gate.json.

  python scripts/stage1_report.py --evidence data/results/stage1_20261011 --instance d1.1_dss2b_c56.7_24.0 rep1 rep2 rep3
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[1]


def mosaic_compare(paths: list[Path]) -> dict:
    """Max abs difference and NaN-pattern equality of the mosaic data between runs (reference = first)."""
    ref = fits.getdata(paths[0]).astype("float64")
    out = []
    for p in paths[1:]:
        a = fits.getdata(p).astype("float64")
        same_nan = bool(np.array_equal(np.isnan(ref), np.isnan(a)))
        d = np.abs(ref - a)
        out.append({"file": str(p), "shape_equal": ref.shape == a.shape, "nan_pattern_equal": same_nan,
                    "max_abs_diff": float(np.nanmax(d)) if same_nan else None,
                    "max_rel_to_range": float(np.nanmax(d) / (np.nanmax(ref) - np.nanmin(ref))) if same_nan else None})
    return {"reference": str(paths[0]), "comparisons": out}


def wcs_sanity(mosaic: Path, region_hdr: Path) -> dict:
    want = {}
    for line in region_hdr.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            want[k.strip()] = v.strip().strip("'")
    with fits.open(mosaic) as h:
        hd = h[0].header
        data = h[0].data
    checks = {}
    for k in ("NAXIS1", "NAXIS2"):
        checks[k] = {"expected": int(want[k]), "got": int(hd[k]), "ok": int(want[k]) == int(hd[k])}
    for k in ("CRVAL1", "CRVAL2", "CDELT1", "CDELT2", "CRPIX1", "CRPIX2"):
        w, g = float(want[k]), float(hd[k])
        checks[k] = {"expected": w, "got": g, "ok": abs(w - g) <= 1e-6 * max(1.0, abs(w))}
    for k in ("CTYPE1", "CTYPE2"):
        checks[k] = {"expected": want[k], "got": str(hd[k]).strip(), "ok": want[k] == str(hd[k]).strip()}
    finite = np.isfinite(data)
    return {"header_checks": checks, "all_header_ok": all(c["ok"] for c in checks.values()),
            "finite_fraction": float(finite.mean()), "data_min": float(np.nanmin(data)), "data_max": float(np.nanmax(data)),
            "data_mean": float(np.nanmean(data))}


def dag_vs_generator(inst: Path) -> dict:
    """Edges implied by the generator's jobDependencies versus producer->consumer file relations."""
    doc = yaml.safe_load((inst / "data" / "montage-workflow.yml").read_text())
    prod = {}
    for j in doc["jobs"]:
        for u in j["uses"]:
            if u["type"] == "output":
                prod[u["lfn"]] = j["id"]
    file_edges = {(prod[u["lfn"]], j["id"]) for j in doc["jobs"] for u in j["uses"] if u["type"] == "input" and u["lfn"] in prod}
    dep_edges = {(d["id"], c) for d in doc.get("jobDependencies", []) for c in d["children"]}
    return {"n_jobs": len(doc["jobs"]), "edges_jobDependencies": len(dep_edges), "edges_from_files": len(file_edges),
            "only_in_jobDependencies": sorted(dep_edges - file_edges), "only_in_files": sorted(file_edges - dep_edges)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--instance", required=True)
    ap.add_argument("reps", nargs="+")
    a = ap.parse_args()
    ev = Path(a.evidence)
    inst = ROOT / "data" / "montage" / "instances" / a.instance
    runs = {r: json.loads((ev / r / "run.json").read_text()) for r in a.reps}
    gate = {"label": "real", "instance": a.instance, "reps": {}}
    for r, d in runs.items():
        gate["reps"][r] = {"status": d["status"], "n_tasks": d["n_tasks"], "total_wall_s": d["total_wall_s"],
                           "all_tasks_timed": all(t["wall_s"] is not None for t in d["tasks"]),
                           "final_outputs": d["final_outputs"]}
    hashes = [tuple(sorted(d["final_outputs"].items())) for d in runs.values()]
    gate["completed_3_of_3"] = len(runs) >= 3 and all(d["status"] == "ok" for d in runs.values())
    gate["output_hashes_identical"] = len(set(hashes)) == 1
    mos = [ev / r / "work" / "1-mosaic.fits" for r in a.reps]
    gate["mosaic_comparison"] = mosaic_compare(mos) if all(m.exists() for m in mos) else "missing"
    gate["wcs"] = wcs_sanity(mos[0], inst / "data" / "region.hdr") if mos[0].exists() else "missing"
    gate["dag"] = dag_vs_generator(inst)
    per = defaultdict(list)
    for d in runs.values():
        for t in d["tasks"]:
            per[t["name"]].append(t["wall_s"])
    gate["per_transformation_wall_s"] = {k: {"n": len(v), "min": min(v), "median": float(np.median(v)), "max": max(v)} for k, v in per.items()}
    (ev / "stage1_gate.json").open("x").write(json.dumps(gate, indent=1))
    print(json.dumps({k: v for k, v in gate.items() if k != "reps"}, indent=1, default=str)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
