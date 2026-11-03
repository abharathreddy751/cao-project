"""Generate one Montage workflow instance with the (Windows-patched) official generator and
download its raw inputs, recording URLs, sizes and SHA-256 [real].

  python scripts/montage_prepare.py --name d1.1_dss2b_c56.7_24.0 --center "56.7 24.0" --degrees 1.1 --band dss:DSS2B:blue

Writes data/montage/instances/<name>/{data/,inputs/,instance.json}; refuses to reuse a name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
MONTAGE = ROOT / "data" / "montage"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--center", required=True)
    ap.add_argument("--degrees", required=True)
    ap.add_argument("--band", action="append", required=True)
    a = ap.parse_args()
    inst = MONTAGE / "instances" / a.name
    inst.mkdir(parents=True)  # FileExistsError if the name was used: never overwrite
    env = {**os.environ, "PATH": str(MONTAGE / "bin_win64") + os.pathsep + os.environ["PATH"]}
    cmd = [sys.executable, str(MONTAGE / "montage-workflow-windows.py"), "--work-dir", str(inst),
           "--center", a.center, "--degrees", a.degrees]
    for b in a.band:
        cmd += ["--band", b]
    t0 = time.time()
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    (inst / "generator_stdout.txt").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
    if r.returncode:
        print(r.stdout, r.stderr)
        return 1
    gen_s = time.time() - t0
    yml = inst / "data" / "montage-workflow.yml"
    doc = yaml.safe_load(yml.read_text())
    (inst / "inputs").mkdir()
    files, t0 = [], time.time()
    for rep in doc["replicaCatalog"]["replicas"]:
        for pfn in rep["pfns"]:
            if pfn["site"] != "ipac":
                continue
            dst = inst / "inputs" / rep["lfn"]
            with requests.get(pfn["pfn"], stream=True, timeout=300) as resp:
                resp.raise_for_status()
                with open(dst, "wb") as f:
                    for chunk in resp.iter_content(1 << 20):
                        f.write(chunk)
            files.append({"lfn": rep["lfn"], "url": pfn["pfn"], "bytes": dst.stat().st_size, "sha256": sha256(dst)})
    jobs = doc["jobs"]
    meta = {"label": "real", "name": a.name, "center": a.center, "degrees": a.degrees, "bands": a.band,
            "generator": "data/montage/montage-workflow-windows.py (diff vs upstream in montage-workflow-windows.diff)",
            "generator_stdout": "generator_stdout.txt", "workflow_yml_sha256": sha256(yml),
            "generate_seconds": round(gen_s, 2), "download_seconds": round(time.time() - t0, 2),
            "n_jobs": len(jobs), "n_inputs": len(files), "input_bytes": sum(f["bytes"] for f in files),
            "inputs": files}
    (inst / "instance.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k != "inputs"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
