"""Revival Phase 1: CPU/GPU profiling and opportunity audit (docs/revival/PROTOCOL_gpu_cpu_profile.md). Profiling only: no scheduler is changed.

  python scripts/revival_profile_cpu_gpu.py run       <out_dir> [--blocks 20] [--seed N] [--no-monitor] [--max-minutes 90] [--smoke]
  python scripts/revival_profile_cpu_gpu.py overhead  <out_dir> [--blocks 8]            (monitoring on/off, same mini-profile)
  python scripts/revival_profile_cpu_gpu.py dag       <out_dir> [--blocks 10]           (small DAG-runtime reference, quiet and contended GPU)
  python scripts/revival_profile_cpu_gpu.py summarize <raw_dir> <summary_dir> [--check <existing summary.csv>]
  python scripts/revival_profile_cpu_gpu.py opportunity <profile_raw_dir> <dag_dir> <out_dir> [--stored <session_dir> ...]

``out_dir`` / ``summary_dir`` / ``out_dir`` are created exclusively (an existing path is refused, nothing is overwritten). Raw samples are JSON lines
(schema gpuprofile/1) in ``raw_samples.jsonl``; every table is derived from them by ``summarize`` / ``opportunity``.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from caosched.revival import gpuprofile as gp  # noqa: E402
from caosched.util import clock  # noqa: E402
from caosched.util.threadpin import pin_single_thread  # noqa: E402

DENOISE_N = (2, 8, 60)
SIDES = (256, 512, 1024, 2048)
P_SLOT, E_SLOT, BURNER_CORE = 2, 14, 19
DEVICE_WORKER = {"P": "P0", "E": "E0", "G": "G0"}


def cells(sides=SIDES):
    """(case, stage, params, side, devices). 60 denoise iterations are skipped at 2048 px (about 4 s per P sample)."""
    out = []
    for s in sides:
        for n in DENOISE_N:
            if s == 2048 and n == 60:
                continue
            out.append((f"img_denoise_n{n}", "img_denoise", {"radius": 2.0, "iterations": n}, s, ("P", "E", "G")))
        out.append(("img_edges", "img_edges", {}, s, ("P", "E", "G")))
        out.append(("img_features", "img_features", {}, s, ("P", "E", "G")))
        out.append(("img_source", "img_source", {"width": s, "height": s, "seed": 0}, s, ("P", "E")))
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("out")
    r.add_argument("--blocks", type=int, default=20)
    r.add_argument("--seed", type=int, default=20262601)
    r.add_argument("--no-monitor", action="store_true")
    r.add_argument("--max-minutes", type=float, default=90.0)
    r.add_argument("--smoke", action="store_true", help="3 blocks, sides 256 and 512 only (a quick check of the machinery)")
    o = sub.add_parser("overhead")
    o.add_argument("out")
    o.add_argument("--blocks", type=int, default=8)
    d = sub.add_parser("dag")
    d.add_argument("out")
    d.add_argument("--blocks", type=int, default=10)
    d.add_argument("--seed", type=int, default=20262602)
    d.add_argument("--tile", type=int, default=512, help="image side of every chain (the representative uniform batch: 512)")
    d.add_argument("--k", type=int, default=64, help="number of chains")
    s = sub.add_parser("summarize")
    s.add_argument("raw")
    s.add_argument("out")
    s.add_argument("--check", default=None)
    v = sub.add_parser("verify", help="re-hash every file of the given directories against their SHA256_MANIFEST.tsv")
    v.add_argument("dirs", nargs="+")
    t = sub.add_parser("_transfer", help="internal: H2D/D2H/total micro-profile in a child process")
    t.add_argument("out")
    t.add_argument("work")
    t.add_argument("sides")
    p = sub.add_parser("opportunity")
    p.add_argument("raw")
    p.add_argument("out")
    p.add_argument("--dag", default=None, help="directory of DAG-runtime reference runs, if they were run")
    p.add_argument("--stored", nargs="*", default=[], help="stored real-run session directories (read only) for the choice counts")
    p.add_argument("--validate", default=None, help="stored analysis directory whose quiet makespans validate the simulation")
    return ap.parse_args(argv)


# --- environment / preflight -------------------------------------------------------------------------------------------------

def env_record(cfg: dict) -> dict:
    import psutil

    smi = gp.smi_sample()
    try:
        import torch

        t = {"torch": torch.__version__, "torch_cuda": torch.version.cuda, "cuda_available": bool(torch.cuda.is_available()),
             "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    except Exception as exc:  # noqa: BLE001
        t = {"torch": None, "cuda_available": False, "error": f"{type(exc).__name__}: {exc}"}
    drv = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], capture_output=True, text=True)
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, cwd=ROOT).stdout.strip()  # noqa: E731
    try:
        import pynvml  # noqa: F401

        nvml = True
    except Exception:  # noqa: BLE001
        nvml = False
    b = psutil.sensors_battery()
    return {"schema": gp.SCHEMA, "date": datetime.datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(),
            "platform": platform.platform(), "cpus_physical": psutil.cpu_count(False), "cpus_logical": psutil.cpu_count(True),
            "ram_total_gb": psutil.virtual_memory().total / 2**30, "ram_free_gb": psutil.virtual_memory().available / 2**30,
            "power_plugged": None if b is None else bool(b.power_plugged), "battery_percent": None if b is None else b.percent,
            "disk_free_gb": {d: psutil.disk_usage(d).free / 2**30 for d in ("D:\\", "C:\\") if Path(d).exists()},
            "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"), "git_commit": git("rev-parse", "HEAD"),
            "git_status_tracked": git("status", "--short", "--untracked-files=no"), "git_remotes": git("remote", "-v"),
            "git_tags": git("tag"), "driver": drv.stdout.strip() or None, **t, "nvml_available": nvml,
            "telemetry": {"source": "nvidia-smi", "first_sample": smi, "nvml": "unavailable (pynvml not installed; not installed by this profile)"},
            "thread_env_pinned": True, "config": cfg, "script_sha256": gp.sha256_file(Path(__file__)),
            "helper_sha256": gp.sha256_file(ROOT / "src" / "caosched" / "revival" / "gpuprofile.py")}


def preflight(cfg: gp.ProfileConfig, wait_cpu: bool = True) -> dict:
    import psutil

    from caosched.experiment.runner import on_mains_power

    if not on_mains_power():
        raise SystemExit("stopping: not on mains power (timings would not be comparable)")
    free = psutil.virtual_memory().available / 2**30
    if free < cfg.min_free_gb:
        raise SystemExit(f"stopping: free RAM {free:.2f} GB < {cfg.min_free_gb}")
    cpu = psutil.cpu_percent(interval=1.0)
    waited = 0.0
    while wait_cpu and cpu > cfg.max_cpu_pct and waited < 30:
        time.sleep(2)
        waited += 2
        cpu = psutil.cpu_percent(interval=1.0)
    smi = gp.smi_sample()
    t = smi.get("temp_c")
    cool = 0.0
    while t is not None and t > cfg.max_temp_c:
        if cool >= 60:
            raise SystemExit(f"stopping: GPU temperature {t} C stays above {cfg.max_temp_c} C")
        time.sleep(5)
        cool += 5
        t = gp.smi_sample().get("temp_c")
    return {"free_ram_gb": free, "cpu_pct": cpu, "cpu_wait_s": waited, "power_plugged": True, "gpu_temp_c": t}


# --- cell data ---------------------------------------------------------------------------------------------------------------

class CellData:
    """Inputs (artifact files shared by all devices), the sequential CPU reference output, and the identity hashes of one cell."""

    def __init__(self, stage: str, params: dict, side: int, workdir: Path, spike):
        import numpy as np

        from caosched.apps.artifacts import write_artifact
        from caosched.apps.stages import decode_arrays, run_stage

        self.stage, self.params, self.side, self.spike = stage, params, side, spike
        src_blob, _, _ = run_stage("img_source", [], {"width": side, "height": side, "seed": 0})
        if stage == "img_source":
            in_blobs: list[bytes] = []
        elif stage == "img_denoise":
            in_blobs = [src_blob]
        else:
            den, _, _ = run_stage("img_denoise", [src_blob], {"radius": 2.0, "iterations": 2})
            in_blobs = [den] if stage == "img_edges" else [run_stage("img_edges", [den], {})[0]]
        self.in_blobs = in_blobs
        self.in_refs = []
        for i, b in enumerate(in_blobs):
            p = workdir / f"in_{stage}_{side}_{i}.bin"
            write_artifact(p, b)
            self.in_refs.append(str(p))
        self.ref_blob, _, _ = run_stage(stage, in_blobs, params)
        self.input_sha = hashlib.sha256(b"".join(hashlib.sha256(b).digest() for b in in_blobs)).hexdigest()
        self.ref_sha = hashlib.sha256(self.ref_blob).hexdigest()
        self._decode = decode_arrays
        self._np = np

    def verify(self, device: str, out_path: Path) -> dict:
        """CPU: byte-identical to the sequential reference. CUDA: the recorded tolerances of ``gpu_spike.compare``."""
        blob = Path(out_path).read_bytes()
        sha = hashlib.sha256(blob).hexdigest()
        if device != "G":
            return {"ok": blob == self.ref_blob, "mode": "byte_identical", "output_sha": sha}
        a, b = self._decode([self.ref_blob])[0], self._decode([blob])[0]
        c = self.spike.compare(self.stage, self._np.asarray(a), self._np.asarray(b))
        return {"ok": bool(c["equivalent"]), "mode": "tolerance", "output_sha": sha, **{k: v for k, v in c.items() if k != "equivalent"}}


# --- pool ---------------------------------------------------------------------------------------------------------------------

def make_pool():
    from caosched.core.runtime_config import PoolSpec
    from caosched.core.worker_pool import WorkerPool

    t0 = clock.now()
    pool = WorkerPool(p_core_slots=(P_SLOT,), e_core_slots=(E_SLOT,), pools={"G": PoolSpec((0,), "cuda")}, warmup=False, strict_affinity=True)
    return pool, clock.now() - t0


def submit_one(pool, device: str, cell: CellData, out_path: Path, tag: str):
    from caosched.core.task import TaskMessage

    wid = DEVICE_WORKER[device]
    msg = TaskMessage(tag, cell.stage, cell.side * cell.side, 0, params=dict(cell.params), input_refs=tuple(cell.in_refs), output_ref=str(out_path))
    t_sub = clock.now()
    pool.submit(wid, msg)
    return wid, t_sub


def timings(res, t_sub: float, t_recv: float) -> dict:
    span = res.t_completed - res.t_started
    kernel, io_s = res.wall_time_seconds, res.io_s
    other = None if kernel is None or io_s is None else span - kernel - io_s
    return {"t_submit": t_sub, "t_started": res.t_started, "t_completed": res.t_completed, "t_recv": t_recv, "kernel_s": kernel, "io_s": io_s,
            "ipc_in_s": res.t_started - t_sub, "worker_span_s": span, "worker_other_s": other, "ipc_out_s": t_recv - res.t_completed,
            "occupation_s": t_recv - t_sub, "out_bytes": res.output_bytes}


def telem(mon) -> dict:
    s = mon.latest() if mon is not None else None
    if s is None:
        return {"gpu_util_pct": None, "gpu_mem_used_mib": None, "gpu_temp_c": None, "gpu_power_w": None, "gpu_sm_clock_mhz": None,
                "telemetry_age_s": None, "telemetry_reason": "monitor off" if mon is None else "no sample yet"}
    return {"gpu_util_pct": s["gpu_util_pct"], "gpu_mem_used_mib": s["mem_used_mib"], "gpu_temp_c": s["temp_c"], "gpu_power_w": s["power_w"],
            "gpu_sm_clock_mhz": s["sm_clock_mhz"], "telemetry_age_s": clock.now() - s["t"], "telemetry_reason": s.get("reason")}


# --- run ---------------------------------------------------------------------------------------------------------------------

def host_side_profile(cell_list, datas, tmp: Path, reps=20) -> list[dict]:
    """Per (stage, side): read, decode, encode, write of the artifact path, measured in this process (identical for every device)."""
    from caosched.apps.artifacts import read_artifacts, write_artifact
    from caosched.apps.stages import STAGES

    rows = []
    for (case, stage, params, side, _devs) in cell_list:
        d = datas[(case, side)]
        st = STAGES[stage]
        out = st.decode(list(d.in_blobs))
        res = st.compute(out, params)
        blob = st.encode(res)
        t: dict[str, list[float]] = {"read": [], "decode": [], "encode": [], "write": []}
        for _ in range(reps):
            if d.in_refs:
                t0 = time.perf_counter()
                read_artifacts(d.in_refs)
                t["read"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            st.decode(list(d.in_blobs))
            t["decode"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            st.encode(res)
            t["encode"].append(time.perf_counter() - t0)
            p = tmp / f"hs_{case}_{side}.bin"
            t0 = time.perf_counter()
            write_artifact(p, blob)
            t["write"].append(time.perf_counter() - t0)
            p.unlink()
        rows.append({"case": case, "side": side, "reps": reps, "in_bytes": sum(len(b) for b in d.in_blobs), "out_bytes": len(blob),
                     **{f"{k}_median_s": (statistics.median(v) if v else None) for k, v in t.items()}})
    return rows


def transfer_profile(cell_list, datas, reps=20) -> list[dict]:
    """H2D, D2H and total of each CUDA stage in this process (CUDA events replaced by synchronise-bracketed perf_counter); kernel = total - H2D - D2H (derived)."""
    import numpy as np
    import torch

    from caosched.apps.cuda_stages import CUDA_STAGES
    from caosched.apps.stages import STAGES

    rows = []
    for (case, stage, params, side, devs) in cell_list:
        if "G" not in devs:
            continue
        d = datas[(case, side)]
        x = STAGES[stage].decode(list(d.in_blobs))
        fn = CUDA_STAGES[stage]
        for _ in range(3):
            fn(x, params)
        h2d, d2h, tot = [], [], []
        for _ in range(reps):
            a = np.ascontiguousarray(x[0])
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            g = torch.from_numpy(a).cuda()
            torch.cuda.synchronize()
            h2d.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            g.cpu()
            torch.cuda.synchronize()
            d2h.append(time.perf_counter() - t0)
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            out = fn(x, params)
            torch.cuda.synchronize()
            tot.append(time.perf_counter() - t0)
        rows.append({"case": case, "side": side, "reps": reps, "h2d_bytes": int(np.ascontiguousarray(x[0]).nbytes), "out_bytes": int(np.asarray(out).nbytes),
                     "h2d_median_s": statistics.median(h2d), "d2h_input_sized_median_s": statistics.median(d2h), "total_median_s": statistics.median(tot),
                     "kernel_derived_s": max(0.0, statistics.median(tot) - statistics.median(h2d) - statistics.median(d2h))})
        torch.cuda.empty_cache()
    return rows


def run_item(pool, mon, cell: CellData, case: str, device: str, load: str, block: int, phase: str, seq: int, warm: bool, work: Path, meta: dict) -> dict:
    tag = f"{case}_{cell.side}_{device}_{block}_{phase}_{seq}"
    out = work / f"{tag}.bin"
    rec = {"schema": gp.SCHEMA, "block": block, "phase": phase, "seq": seq, "warmup": warm or block == 0, "case": case, "stage": cell.stage,
           "params": json.dumps(cell.params, sort_keys=True), "side": cell.side, "pixels": cell.side * cell.side, "device": device,
           "worker_id": DEVICE_WORKER[device], "gpu_load": load, "input_sha": cell.input_sha, **meta, **telem(mon)}
    try:
        wid, t_sub = submit_one(pool, device, cell, out, tag)
        res = pool.poll_result(timeout=180)
        t_recv = clock.now()
        if res is None or res.worker_id != wid or res.task_id != tag:
            raise RuntimeError(f"unexpected result {res!r}")
        rec.update(timings(res, t_sub, t_recv))
        if res.error:
            rec.update(valid=False, reason="worker error", error=res.error[-400:], verify=None)
        else:
            v = cell.verify(device, out)
            rec.update(valid=bool(v["ok"]), reason=None if v["ok"] else "verification failed", error=None, verify=v, output_sha=v["output_sha"])
    except Exception as exc:  # noqa: BLE001 - a failed sample is data: kept with its reason
        rec.update(valid=False, reason="exception", error=f"{type(exc).__name__}: {exc}", verify=None)
    finally:
        out.unlink(missing_ok=True)
    return rec


def run_pair(pool, mon, cell: CellData, case: str, cpu_dev: str, block: int, seq: int, work: Path, meta: dict) -> list[dict]:
    """Same task submitted at the same instant to a CPU worker and the CUDA worker (quiet GPU); both results are kept."""
    pair_id = f"{case}_{cell.side}_{cpu_dev}G_{block}_{seq}"
    outs = {d: work / f"{pair_id}_{d}.bin" for d in (cpu_dev, "G")}
    subs = {}
    t0 = clock.now()
    for d in (cpu_dev, "G"):
        subs[d] = submit_one(pool, d, cell, outs[d], f"{pair_id}_{d}")
    recs, got = [], {}
    try:
        for _ in range(2):
            res = pool.poll_result(timeout=180)
            got[res.worker_id] = (res, clock.now())
        t_all = max(t for _, t in got.values())
        for d in (cpu_dev, "G"):
            wid, t_sub = subs[d]
            res, t_recv = got[wid]
            r = {"schema": gp.SCHEMA, "block": block, "phase": "pair", "seq": seq, "warmup": block == 0, "case": case, "stage": cell.stage,
                 "params": json.dumps(cell.params, sort_keys=True), "side": cell.side, "pixels": cell.side * cell.side, "device": d,
                 "partner": cpu_dev if d == "G" else "G", "pair_id": pair_id, "pair_wall_s": t_all - t0, "worker_id": wid, "gpu_load": "pair_quiet",
                 "input_sha": cell.input_sha, **meta, **telem(mon), **timings(res, t_sub, t_recv)}
            if res.error:
                r.update(valid=False, reason="worker error", error=res.error[-400:], verify=None)
            else:
                v = cell.verify(d, outs[d])
                r.update(valid=bool(v["ok"]), reason=None if v["ok"] else "verification failed", error=None, verify=v)
            recs.append(r)
    except Exception as exc:  # noqa: BLE001
        recs.append({"schema": gp.SCHEMA, "block": block, "phase": "pair", "pair_id": pair_id, "valid": False, "reason": "exception",
                     "error": f"{type(exc).__name__}: {exc}", "warmup": block == 0})
    finally:
        for p in outs.values():
            p.unlink(missing_ok=True)
    return recs


def write_manifest(out: Path) -> None:
    rows = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "SHA256_MANIFEST.tsv":
            rows.append((p.relative_to(out).as_posix(), p.stat().st_size, gp.sha256_file(p)))
    with (out / "SHA256_MANIFEST.tsv").open("x", encoding="utf-8") as fh:
        fh.write("relpath\tsize\tsha256\n")
        for r in rows:
            fh.write("\t".join(map(str, r)) + "\n")


def cmd_run(a) -> int:
    pin_single_thread()
    from caosched.apps.cuda_stages import cuda_available
    from caosched.core.coordinator import pin_coordinator_to_reserved_core
    from caosched.experiment.gpu_adapter import _spike

    sides = (256, 512) if a.smoke else SIDES
    cfg = gp.ProfileConfig(blocks=3 if a.smoke else a.blocks, seed=a.seed, sides=sides, monitor=not a.no_monitor, max_minutes=a.max_minutes)
    cfg.validate()
    out = Path(a.out)
    if out.exists():
        raise FileExistsError(f"{out} exists: refusing to overwrite")
    if not cuda_available():
        raise SystemExit("CUDA unavailable: this profile needs the GPU (CPU-only machines: no GPU evidence can be produced)")
    out.mkdir(parents=True, exist_ok=False)
    work = out / "work"
    work.mkdir()
    env = env_record(dataclass_dict(cfg))
    (out / "env.json").write_text(json.dumps(env, indent=1, default=str), encoding="utf-8")
    pf = preflight(cfg)
    pin_coordinator_to_reserved_core()
    spike = _spike()
    cl = cells(sides)
    datas = {(c, s): CellData(st, p, s, work, spike) for (c, st, p, s, _d) in cl}
    (out / "host_side.json").write_text(json.dumps(host_side_profile(cl, datas, work), indent=1), encoding="utf-8")
    # the transfer micro-profile needs a CUDA context in THIS process; it runs in a short-lived child so the sweep does not carry that memory (amendment A4)
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "_transfer", str(out / "transfer.json"), str(work), ",".join(map(str, sides))], check=True)
    t_start = clock.now()
    raw = (out / "raw_samples.jsonl").open("x", encoding="utf-8")
    mon = gp.NvidiaSmiMonitor(cfg.interval_s, out / "telemetry.jsonl").start() if cfg.monitor else None
    stop_reason = None
    pool, pool_s = make_pool()
    (out / "pool_startup.json").write_text(json.dumps({"pool_creation_s": pool_s, "workers": {w: {"affinity": list(pool.workers[w].affinity)} for w in pool.workers}}), encoding="utf-8")
    seq = 0
    try:
        with gp.GpuBurner(cpu=BURNER_CORE, max_s=cfg.max_minutes * 60 + 600) as burner:
            for block in range(cfg.blocks):
                if (clock.now() - t_start) / 60 > cfg.max_minutes:
                    stop_reason = f"wall-clock budget of {cfg.max_minutes} min exceeded before block {block}"
                    break
                try:
                    meta = {**preflight(cfg), "run_block": block}
                except SystemExit as stop:  # a stopping rule of the protocol: keep what was measured, record why
                    stop_reason = f"preflight before block {block}: {stop}"
                    break
                fails = total = 0
                phases = ["quiet", "contended"] if block % 2 == 0 else ["contended", "quiet"]
                for phase in phases + ["pair"]:
                    if phase == "contended":
                        burner.resume()
                        time.sleep(1.0)
                    else:
                        burner.pause()
                        time.sleep(0.3)
                    if phase == "pair":
                        items = [(c, s, d) for (c, st, p, s, devs) in cl if "G" in devs and (s != 2048 or block % 2 == 0) for d in ("P", "E")]
                        for (c, s, d) in gp.block_order(items, cfg.seed, block, phase):
                            seq += 1
                            for r in run_pair(pool, mon, datas[(c, s)], c, d, block, seq, work, meta):
                                raw.write(json.dumps(r, default=str) + "\n")
                                total += 1
                                fails += 0 if r.get("valid") else 1
                        raw.flush()
                        continue
                    items = [(c, s, d) for (c, st, p, s, devs) in cl if (s != 2048 or block % 2 == 0) for d in devs]
                    for k, (c, s, d) in enumerate(gp.block_order(items, cfg.seed, block, phase)):
                        seq += 1
                        r = run_item(pool, mon, datas[(c, s)], c, d, phase, block, phase, seq, False, work, {**meta, "order_in_phase": k})
                        raw.write(json.dumps(r, default=str) + "\n")
                        total += 1
                        fails += 0 if r.get("valid") else 1
                    raw.flush()
                burner.pause()
                if pool.dead_workers():
                    stop_reason = f"worker died in block {block}: {pool.dead_workers()}"
                    break
                if total and fails / total > 0.10:
                    stop_reason = f"more than 10% failed samples in block {block} ({fails}/{total})"
                    break
                if not burner.alive():
                    stop_reason = f"GPU burner died in block {block}"
                    break
    finally:
        raw.close()
        if mon is not None:
            mon.stop()
        pool.shutdown()
    for p in work.glob("*"):
        p.unlink()
    work.rmdir()
    (out / "run_end.json").write_text(json.dumps({"stop_reason": stop_reason, "blocks_requested": cfg.blocks, "samples": seq, "elapsed_s": clock.now() - t_start,
                                                  "preflight_first": pf}, indent=1), encoding="utf-8")
    write_manifest(out)
    print("wrote", out, "stop_reason:", stop_reason)
    return 0 if stop_reason is None else 3


def dataclass_dict(cfg) -> dict:
    import dataclasses

    return dataclasses.asdict(cfg)


# --- monitoring overhead ------------------------------------------------------------------------------------------------------

def cmd_transfer(a) -> int:
    pin_single_thread()
    from caosched.experiment.gpu_adapter import _spike

    sides = tuple(int(x) for x in a.sides.split(","))
    work = Path(a.work) / "transfer_child"
    work.mkdir()
    spike = _spike()
    cl = cells(sides)
    datas = {(c, s): CellData(st, p, s, work, spike) for (c, st, p, s, _d) in cl if "G" in _d}
    Path(a.out).write_text(json.dumps(transfer_profile([c for c in cl if "G" in c[4]], datas), indent=1), encoding="utf-8")
    for f in work.glob("*"):
        f.unlink()
    work.rmdir()
    return 0


def cmd_overhead(a) -> int:
    """The same mini-profile with the monitor on and off, alternating by block; the difference is the cost of monitoring."""
    pin_single_thread()
    from caosched.core.coordinator import pin_coordinator_to_reserved_core
    from caosched.experiment.gpu_adapter import _spike

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    work = out / "work"
    work.mkdir()
    spike = _spike()
    sel = [c for c in cells((256, 512)) if c[0] in ("img_denoise_n8", "img_edges", "img_features")]
    datas = {(c, s): CellData(st, p, s, work, spike) for (c, st, p, s, _d) in sel}
    pin_coordinator_to_reserved_core()
    preflight(gp.ProfileConfig())
    pool, _ = make_pool()
    rows: list[dict] = []
    calls: list[float] = []
    seq = 0
    try:
        for block in range(a.blocks):
            for state in gp.block_order(["on", "off"], 7, block, "o"):
                mon = gp.NvidiaSmiMonitor(0.5).start() if state == "on" else None
                time.sleep(0.6 if mon else 0.1)
                try:
                    for rep in range(3):
                        for (c, st, p, s, devs) in sel:
                            for d in gp.block_order(list(devs), 7, block * 10 + rep, c):
                                seq += 1
                                rows.append(run_item(pool, mon, datas[(c, s)], c, d, "quiet", block, "quiet", seq, block == 0, work, {"monitor": state}))
                finally:
                    if mon is not None:
                        mon.stop()
                        calls += [x["call_s"] for x in mon.samples]
    finally:
        pool.shutdown()
    with (out / "raw_samples.jsonl").open("x", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    res = []
    for key in sorted({(r["case"], r["side"], r["device"]) for r in rows}):
        g = {m: [r["occupation_s"] for r in rows if (r["case"], r["side"], r["device"]) == key and r["monitor"] == m and r["valid"] and not r["warmup"]]
             for m in ("on", "off")}
        if len(g["on"]) > 1 and len(g["off"]) > 1:
            on, off = statistics.median(g["on"]), statistics.median(g["off"])
            res.append({"case": key[0], "side": key[1], "device": key[2], "n_on": len(g["on"]), "n_off": len(g["off"]), "median_on_s": on,
                        "median_off_s": off, "overhead_pct": (on / off - 1) * 100})
    pooled = statistics.median(r["overhead_pct"] for r in res) if res else None
    (out / "monitor_overhead.json").write_text(json.dumps({"rows": res, "nvidia_smi_call_s_median": statistics.median(calls) if calls else None,
                                                           "pooled_overhead_pct_median_of_cells": pooled}, indent=1), encoding="utf-8")
    for p in work.glob("*"):
        p.unlink()
    work.rmdir()
    write_manifest(out)
    print(json.dumps({"pooled_overhead_pct": pooled}))
    return 0


# --- DAG-runtime reference ----------------------------------------------------------------------------------------------------

def cmd_dag(a) -> int:
    pin_single_thread()
    from caosched.apps.cuda_stages import cuda_available
    from caosched.experiment.design import Condition
    from caosched.study2.adapter import Study2Adapter

    if not cuda_available():
        raise SystemExit("CUDA unavailable")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    cfg = gp.ProfileConfig(blocks=a.blocks, seed=a.seed)
    base = {"k": a.k, "tile": a.tile, "seed": 0, "denoise_iterations": 8,
            "profile": str(next((ROOT / "data" / "results" / "study2_20261024" / "profile_t512").glob("*_profile.json")))}
    b4g = {"policy_cfg": {"B4_greedy_eligible": {"priority": ["G", "P", "E"]}}}
    all3 = {"img_denoise": True, "img_edges": True, "img_features": True}
    ef = {"img_denoise": False, "img_edges": True, "img_features": True}
    conds = {"B4_gpu_all": Condition("B4_gpu_all", "B4", None, {}, {**base, **b4g, "gpu_stage_table": all3}, instance=None),
             "B4_gpu_ef": Condition("B4_gpu_ef", "B4", None, {}, {**base, **b4g, "gpu_stage_table": ef}, instance=None),
             "B4_cpu": Condition("B4_cpu", "B4", None, {}, {**base, "gpu_stage_table": all3, "no_gpu": True}, instance=None)}
    (out / "env.json").write_text(json.dumps(env_record(dataclass_dict(cfg)), indent=1, default=str), encoding="utf-8")
    ad = Study2Adapter(timeout_s=120, run_timeout_s=120)
    rows = []
    mon = gp.NvidiaSmiMonitor(0.5, out / "telemetry.jsonl").start()
    try:
        with gp.GpuBurner(cpu=BURNER_CORE, max_s=3600) as burner:
            for block in range(cfg.blocks):
                meta = preflight(cfg)
                for load in (["quiet", "contended"] if block % 2 == 0 else ["contended", "quiet"]):
                    burner.resume() if load == "contended" else burner.pause()
                    time.sleep(1.0 if load == "contended" else 0.3)
                    for i, name in enumerate(gp.block_order(list(conds), cfg.seed, block, load)):
                        wd = out / "runs" / f"b{block:02d}_{load}_{i}_{name}" / "run"
                        wd.mkdir(parents=True)
                        t0 = clock.now()
                        rec = ad.run_one(conds[name], wd, seed=1)
                        rows.append({"schema": gp.SCHEMA, "block": block, "warmup": block == 0, "gpu_load": load, "condition": name, "status": rec.status,
                                     "output_ok": rec.output_ok, "error": rec.error, "makespan_s": rec.extra.get("makespan_seconds"),
                                     "scheduling_s": rec.extra.get("decision_time_total_s"), "tasks_per_pool": rec.extra.get("tasks_per_pool"),
                                     "event_log": str((wd / rec.event_log).relative_to(out)) if rec.event_log else None, "run_s": clock.now() - t0, **meta,
                                     **telem(mon)})
                burner.pause()
    finally:
        mon.stop()
        ad.close()
    with (out / "dag_runs.jsonl").open("x", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    write_manifest(out)
    print("wrote", out)
    return 0


# --- summaries ---------------------------------------------------------------------------------------------------------------

def load_rows(raw: Path) -> list[dict]:
    return [json.loads(line) for line in (Path(raw) / "raw_samples.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def overlap_table(rows: list[dict]) -> list[dict]:
    """Pair phase: both tasks submitted together. efficiency = max(solo occupation of the two) / pair wall time (1.0 = the two overlap perfectly;
    sum(solo)/pair wall - 1 is the gain over running them one after the other)."""
    solo: dict[tuple, list[float]] = {}
    for r in gp.valid_rows(rows):
        if r["gpu_load"] == "quiet":
            solo.setdefault((r["case"], r["side"], r["device"]), []).append(r["occupation_s"])
    by: dict[tuple, dict] = {}
    for r in rows:
        if r.get("phase") == "pair" and r.get("valid") and not r.get("warmup"):
            by.setdefault(r["pair_id"], {})[r["device"]] = r
    agg: dict[tuple, list] = {}
    for pid, d in by.items():
        if "G" not in d or len(d) != 2:
            continue
        cpu = next(k for k in d if k != "G")
        r0 = d["G"]
        agg.setdefault((r0["case"], r0["side"], cpu), []).append(r0["pair_wall_s"])
    out = []
    for (case, side, cpu), walls in sorted(agg.items()):
        sc, sg = solo.get((case, side, cpu)), solo.get((case, side, "G"))
        if not sc or not sg or len(walls) < 2:
            continue
        mc, mg, mw = statistics.median(sc), statistics.median(sg), statistics.median(walls)
        out.append({"case": case, "side": side, "cpu_device": cpu, "n_pairs": len(walls), "solo_cpu_s": mc, "solo_gpu_s": mg, "pair_wall_s": mw,
                    "efficiency_max_over_pair": max(mc, mg) / mw, "gain_over_serial_pct": ((mc + mg) / mw - 1) * 100})
    return out


def breakdown_table(summary: list[dict]) -> list[dict]:
    out = []
    for s in summary:
        occ = s.get("occupation_s_median")
        if not occ:
            continue
        row = {"case": s["case"], "side": s["side"], "device": s["device"], "gpu_load": s["gpu_load"], "occupation_s": occ}
        for m, label in (("kernel_s", "kernel_incl_transfers"), ("io_s", "io_codec"), ("ipc_in_s", "ipc_in"), ("ipc_out_s", "ipc_out"), ("worker_other_s", "worker_other")):
            v = s.get(f"{m}_median")
            row[f"{label}_s"] = v
            row[f"{label}_pct"] = None if v is None else 100 * v / occ
        out.append(row)
    return out


def telemetry_summary(raw: Path, rows: list[dict]) -> dict:
    by: dict[str, list[float]] = {}
    for r in rows:
        if r.get("gpu_util_pct") is not None and r.get("phase") in ("quiet", "contended"):
            by.setdefault(r["gpu_load"], []).append(r["gpu_util_pct"])
    tel = [json.loads(line) for line in (raw / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()] if (raw / "telemetry.jsonl").exists() else []
    return {"util_pct_at_samples": {k: {"n": len(v), "median": statistics.median(v), "mean": statistics.fmean(v)} for k, v in by.items()},
            "telemetry_samples": len(tel), "telemetry_unavailable": sum(1 for t in tel if not t.get("available")),
            "per_call_s_median": statistics.median(t["call_s"] for t in tel) if tel else None,
            "max_temp_c": max((t["temp_c"] for t in tel if t.get("temp_c") is not None), default=None),
            "max_power_w": max((t["power_w"] for t in tel if t.get("power_w") is not None), default=None)}


def cmd_summarize(a) -> int:
    raw, out = Path(a.raw), Path(a.out)
    rows = load_rows(raw)
    if a.check:
        out_dir = Path(a.check).parent
        s = gp.summarize(rows)
        keys = list(dict.fromkeys(k for r in s for k in r))
        import io

        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=keys, lineterminator="\r\n")
        w.writeheader()
        w.writerows(s)
        same = buf.getvalue() == Path(a.check).read_bytes().decode("utf-8")
        print("summary.csv recomputed from raw samples is", "IDENTICAL" if same else "DIFFERENT", "to", a.check, "(dir", out_dir, ")")
        return 0 if same else 1
    out.mkdir(parents=True, exist_ok=False)
    summary = gp.summarize(rows)
    write_csv(out / "summary.csv", summary)
    write_csv(out / "breakdown.csv", breakdown_table(summary))
    flips = gp.best_device(summary, rows)
    write_csv(out / "best_device.csv", flips)
    write_csv(out / "overlap.csv", overlap_table(rows))
    n = {"samples": len(rows), "warmup": sum(1 for r in rows if r.get("warmup")), "valid_measured": len(gp.valid_rows(rows)),
         "failed_measured": sum(1 for r in rows if r.get("phase") in ("quiet", "contended") and not r.get("warmup") and not r.get("valid")),
         "pair_valid": sum(1 for r in rows if r.get("phase") == "pair" and r.get("valid") and not r.get("warmup")),
         "pair_failed": sum(1 for r in rows if r.get("phase") == "pair" and not r.get("valid") and not r.get("warmup")),
         "blocks": sorted({r["block"] for r in rows if "block" in r})[-1:] , "telemetry": telemetry_summary(raw, rows)}
    (out / "counts.json").write_text(json.dumps(n, indent=1), encoding="utf-8")
    print(json.dumps(n))
    return 0


def _geo_mid(summary_csv: Path, condition: str) -> float:
    for r in csv.DictReader(Path(summary_csv).open(encoding="utf-8")):
        if r["scope"] == "pooled_log_scale" and r["condition"] == condition:
            return (float(r["ci_lo_s"]) * float(r["ci_hi_s"])) ** 0.5
    raise KeyError(condition)


def cmd_opportunity(a) -> int:
    """Per workload: best device per cell and flips, class work shares, measured choice counts from stored real runs, a list-scheduling SIMULATION
    (validated on stored quiet makespans, then run with quiet and contended costs), the LP bound and the headroom estimates. Everything is labelled."""
    from caosched.core.event_log import read_events

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    raw = Path(a.raw)
    rows = load_rows(raw)
    summary = gp.summarize(rows)
    flips = gp.best_device(summary, rows)
    med = {(s["case"], s["side"], s["device"], s["gpu_load"]): s.get("occupation_s_median") for s in summary}
    res: dict = {"label": "measured profile medians; choice counts reconstructed from stored real runs; simulation and LP are ESTIMATES, not measurements",
                 "profile_raw": str(raw), "dag_reference_runs": ("present" if a.dag and Path(a.dag).exists() else "not run (RAM stopping rule; see report)")}
    stored: dict[str, dict[str, int]] = {}
    for s in a.stored:
        for d in sorted(Path(s).glob("runs/*")):
            if d.name.startswith("b0000_"):
                continue
            logs = list(d.glob("*.jsonl"))
            if logs:
                cond = d.name.split("_", 2)[2]
                for k, v in gp.dispatch_choices(read_events(logs[0])).items():
                    stored.setdefault(cond, {}).setdefault(k, 0)
                    stored[cond][k] += v
    res["stored_real_run_choices"] = stored
    measured_q = {c: _geo_mid(Path(a.validate) / "summary.csv", c) for c in ("B4_gpu", "B0_P_only")} if a.validate else {}
    res["measured_quiet_makespan_s_stored"] = measured_q
    wl_out: dict = {}
    coord = 0.0
    for side, k in ((512, 64), (1024, 24)):
        stages = {"img_source": "img_source", "img_denoise": "img_denoise_n8", "img_edges": "img_edges", "img_features": "img_features"}
        cost = {load: {(st, dev): float(med[(case, side, dev, load)]) for st, case in stages.items() for dev in ("P", "E", "G")
                       if med.get((case, side, dev, load)) and not (dev == "G" and st == "img_source")} for load in ("quiet", "contended")}
        pools = {"P": 6, "E": 7, "G": 1}
        el = {"all3": {"img_source": ("P", "E"), "img_denoise": ("G", "P", "E"), "img_edges": ("G", "P", "E"), "img_features": ("G", "P", "E")},
              "ef": {"img_source": ("P", "E"), "img_denoise": ("P", "E"), "img_edges": ("G", "P", "E"), "img_features": ("G", "P", "E")},
              "cpu": {st: ("P", "E") for st in stages}, "ponly": {st: ("P",) for st in stages}}
        w: dict = {"image_side": side, "chains": k}

        def sim(load, name, policy, cs):
            return gp.simulate_list_schedule(k, dict(cost[load]), el[name], pools if name != "ponly" else {"P": 6}, policy, cs)

        if side == 512 and measured_q:
            coord = gp.fit_coord_s(measured_q["B4_gpu"], lambda cs: sim("quiet", "all3", "greedy", cs)["makespan_s"])
            w["validation_quiet"] = {"coord_s_fitted_on_B4_gpu": coord,
                                     "B4_gpu": {"measured_s": measured_q["B4_gpu"], "simulated_s": sim("quiet", "all3", "greedy", coord)["makespan_s"]},
                                     "B0_P_only_NOT_used_for_fit": {"measured_s": measured_q["B0_P_only"], "simulated_s": sim("quiet", "ponly", "greedy", coord)["makespan_s"]}}
            res["coord_s"] = coord
        sims = {}
        for load in ("quiet", "contended"):
            sims[load] = {"B4_gpu_all": sim(load, "all3", "greedy", coord), "B4_gpu_ef": sim(load, "ef", "greedy", coord), "B4_cpu": sim(load, "cpu", "greedy", coord),
                          "ORACLE_greedy": sim(load, "all3", "oracle", coord)}
        w["simulation"] = sims
        lp = {}
        for load in ("quiet", "contended"):
            for gpu_allowed, label in ((True, "with_gpu"), (False, "cpu_only")):
                cc = {kk: v for kk, v in cost[load].items() if gpu_allowed or kk[1] != "G"}
                cap = {kk: v for kk, v in pools.items() if gpu_allowed or kk != "G"}
                lp[f"{load}|{label}"] = gp.lp_lower_bound({st: k for st in stages}, cc, cap)
        w["lp"] = lp
        pcost = {kk: v for kk, v in cost["quiet"].items() if kk[1] == "P"}
        r_lp = gp.lp_lower_bound({st: k for st in stages}, pcost, {"P": 6})["T_s"]
        w["structural_overhead_ratio_r"] = (measured_q["B0_P_only"] / r_lp) if (measured_q and side == 512) else None
        work = {}
        for st, case in stages.items():
            vals = [v for d in ("P", "E", "G") if (v := med.get((case, side, d, "quiet")))]
            work[st] = k * min(vals) if vals else None
        tot = sum(v for v in work.values() if v)
        w["class_work_share_pct"] = {st: (100 * v / tot if v else None) for st, v in work.items()}
        w["flips_at_this_side"] = [f for f in flips if f["side"] == side and f["flip"]]
        share = w["class_work_share_pct"]
        w["g1_flip_classes_with_share_ge_20pct"] = [f["case"] for f in w["flips_at_this_side"]
                                                     if f["flip_firm"] and (share.get({"img_denoise_n8": "img_denoise"}.get(f["case"], f["case"])) or 0) >= 20]
        hr = {}
        for load in ("quiet", "contended"):
            simple = {n_: sims[load][n_]["makespan_s"] for n_ in ("B4_gpu_all", "B4_gpu_ef", "B4_cpu")}
            best = min(simple, key=simple.__getitem__)
            ratio = w["structural_overhead_ratio_r"]
            hr[load] = {"best_simple_sim": best, "best_simple_sim_s": simple[best], "oracle_greedy_sim_s": sims[load]["ORACLE_greedy"]["makespan_s"],
                        "headroom_sim_pct": (simple[best] / sims[load]["ORACLE_greedy"]["makespan_s"] - 1) * 100,
                        "lp_with_gpu_s": lp[f"{load}|with_gpu"]["T_s"],
                        "headroom_lp_raw_pct": gp.headroom(simple[best], lp[f"{load}|with_gpu"]["T_s"]),
                        "headroom_lp_overhead_corrected_pct": gp.headroom(simple[best], lp[f"{load}|with_gpu"]["T_s"], ratio) if ratio else None}
        w["headroom"] = hr
        wl_out[f"side{side}_k{k}"] = w
    res["workloads"] = wl_out
    res["flips_all"] = flips
    (out / "opportunity.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    write_csv(out / "flips.csv", flips)
    print(json.dumps({k_: {"headroom": v["headroom"], "g1": v["g1_flip_classes_with_share_ge_20pct"], "validation": v.get("validation_quiet")} for k_, v in wl_out.items()},
                     indent=1, default=str)[:4000])
    return 0


def cmd_verify(a) -> int:
    bad = 0
    for d in a.dirs:
        problems = gp.verify_manifest(Path(d))
        print(("OK   " if not problems else "FAIL ") + d, problems[:3])
        bad += bool(problems)
    return 1 if bad else 0


def main(argv=None) -> int:
    a = parse_args(argv)
    return {"verify": cmd_verify, "run": cmd_run, "_transfer": cmd_transfer, "overhead": cmd_overhead, "dag": cmd_dag, "summarize": cmd_summarize, "opportunity": cmd_opportunity}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
