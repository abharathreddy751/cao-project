"""Stage 1 reference: run a generated Montage workflow SEQUENTIALLY (one task at a time) in a fresh work
directory, recording per-task wall time, exit status, output sizes, SHA-256 and the final mosaic [real].

Independent of the coordinator and the workflow adapter: it reads the Pegasus YAML directly and runs the jobs in
file order after checking every input exists (so file order is a valid topological order or the run aborts).

  python scripts/montage_sequential.py --instance d1.1_dss2b_c56.7_24.0 --out data/results/stage1_20261011/seq_run1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

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
    ap.add_argument("--instance", required=True)
    ap.add_argument("--out", required=True, help="fresh directory (must not exist)")
    ap.add_argument("--timeout-s", type=float, default=3600)
    ap.add_argument("--pin-lp", type=int, default=None, help="pin this process (children inherit) to one logical processor, e.g. a P core; recorded in run.json")
    ap.add_argument("--seed-work", help="DEBUG ONLY: copy this work dir first and skip tasks whose outputs already exist (run is labelled debug, not evidence)")
    a = ap.parse_args()
    inst = MONTAGE / "instances" / a.instance
    out = Path(a.out)
    if a.pin_lp is not None:
        import psutil
        psutil.Process().cpu_affinity([a.pin_lp])
    work = out / "work"
    work.mkdir(parents=True)  # never reuse
    doc = yaml.safe_load((inst / "data" / "montage-workflow.yml").read_text())
    for f in (inst / "inputs").iterdir():
        shutil.copy2(f, work / f.name)
    for rep in doc["replicaCatalog"]["replicas"]:
        if any(p["site"] == "local" for p in rep["pfns"]):
            shutil.copy2(inst / "data" / rep["lfn"], work / rep["lfn"])
    # mDiffFit spawns mDiff/mFitplane by name: the executables must be on PATH (Pegasus does the same)
    env = {**os.environ, "PATH": str(MONTAGE / "bin_win64") + os.pathsep + os.environ["PATH"]}
    seeded = bool(a.seed_work)
    if seeded:
        shutil.copytree(a.seed_work, work, dirs_exist_ok=True)
    raw = {p.name for p in work.iterdir()}
    produced, tasks = set(), []
    t_run = time.perf_counter()
    status = "ok"
    for j in doc["jobs"]:
        ins = [u["lfn"] for u in j["uses"] if u["type"] == "input"]
        outs = [u["lfn"] for u in j["uses"] if u["type"] == "output"]
        missing = [f for f in ins if f not in raw and f not in produced]
        if missing:
            raise SystemExit(f"{j['id']} {j['name']}: inputs {missing} not available: file order is not topological")
        if seeded and outs and all((work / o).exists() for o in outs):
            produced.update(outs)
            continue
        argv = [str(MONTAGE / "bin_win64" / (j["name"] + ".exe")), *j["arguments"]]
        t0 = time.perf_counter()
        try:
            r = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True, timeout=a.timeout_s)
            rc, so = r.returncode, (r.stdout + r.stderr).strip()[-400:]
        except subprocess.TimeoutExpired:
            rc, so = -1, "timeout"
        dt = time.perf_counter() - t0
        # exit status + declared outputs decide: the Pegasus-grid mDiffFit prints stat="ERROR" (images don't overlap)
        # and exits 0 on purpose
        ok = rc == 0 and all((work / o).exists() for o in outs)
        produced.update(outs)
        tasks.append({"id": j["id"], "name": j["name"], "argv": [Path(argv[0]).name, *j["arguments"]], "inputs": ins,
                      "outputs": [{"lfn": o, "bytes": (work / o).stat().st_size if (work / o).exists() else None} for o in outs],
                      "wall_s": dt, "exit": rc, "ok": ok, "tail": so})
        if not ok:
            status = f"failed:{j['id']}"
            break
    total = time.perf_counter() - t_run
    final = [u["lfn"] for j in doc["jobs"] for u in j["uses"] if u["type"] == "output" and u.get("stageOut")]
    hashes = {f: sha256(work / f) for f in final if (work / f).exists()}
    res = {"label": "debug" if seeded else "real", "seeded_from": a.seed_work, "pinned_lp": a.pin_lp, "instance": a.instance, "status": status, "total_wall_s": total, "n_tasks": len(tasks),
           "final_outputs": hashes, "tasks": tasks}
    (out / "run.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "tasks"}, indent=1))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
