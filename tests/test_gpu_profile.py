"""CPU/GPU profiling helpers (revival Phase 1). Ordinary tests need neither an NVIDIA GPU nor NVML; hardware tests skip with a reason."""
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

from caosched.apps.cuda_stages import cuda_available
from caosched.revival import gpuprofile as gp

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("revival_profile_cpu_gpu", ROOT / "scripts" / "revival_profile_cpu_gpu.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["revival_profile_cpu_gpu"] = mod
    spec.loader.exec_module(mod)
    return mod


def _row(case="img_edges", side=512, device="P", load="quiet", occ=0.01, valid=True, warm=False, phase=None):
    return {"phase": phase or load, "warmup": warm, "valid": valid, "case": case, "side": side, "device": device, "gpu_load": load,
            "occupation_s": occ, "kernel_s": occ / 2, "io_s": occ / 4, "ipc_in_s": occ / 8, "ipc_out_s": occ / 8, "worker_other_s": 0.0,
            "worker_span_s": occ * 0.75}


def test_arguments_and_configuration_are_validated():
    m = _script()
    a = m.parse_args(["run", "somewhere", "--blocks", "7", "--no-monitor", "--smoke"])
    assert a.cmd == "run" and a.blocks == 7 and a.no_monitor and a.smoke and a.max_minutes == 90.0
    assert m.parse_args(["summarize", "raw", "out", "--check", "x.csv"]).check == "x.csv"
    with pytest.raises(ValueError):
        gp.ProfileConfig(blocks=2).validate()
    with pytest.raises(ValueError):
        gp.ProfileConfig(interval_s=0.01).validate()
    gp.ProfileConfig().validate()
    cl = m.cells((256, 2048))
    assert not any(c[0] == "img_denoise_n60" and c[3] == 2048 for c in cl)            # 60 iterations at 2048 px are skipped
    assert all(c[4] == ("P", "E") for c in cl if c[1] == "img_source") and all("G" in c[4] for c in cl if c[1] in ("img_edges", "img_features"))
    from caosched.apps.cuda_stages import CUDA_STAGES
    assert {c[1] for c in cl if "G" in c[4]} == set(CUDA_STAGES)                      # exactly the stages that have a CUDA variant


def test_block_order_is_deterministic_and_varies():
    items = list(range(12))
    assert gp.block_order(items, 1, 3, "quiet") == gp.block_order(items, 1, 3, "quiet")
    assert gp.block_order(items, 1, 3, "quiet") != gp.block_order(items, 1, 4, "quiet") and sorted(gp.block_order(items, 1, 3, "x")) == items


def test_summary_excludes_warmup_and_invalid_and_recomputes_from_raw():
    rows = [_row(occ=0.010 + 0.001 * i) for i in range(10)] + [_row(occ=9.9, warm=True), _row(occ=7.7, valid=False)]
    s = gp.summarize(rows)
    assert len(s) == 1 and s[0]["n_valid"] == 10 and s[0]["n_failed"] == 1                 # the warm-up row is not counted at all
    assert s[0]["occupation_s_median"] == pytest.approx(statistics.median(0.010 + 0.001 * i for i in range(10)))
    assert s[0]["occupation_s_ci_lo"] <= s[0]["occupation_s_median"] <= s[0]["occupation_s_ci_hi"]
    assert gp.summarize(rows) == s                                                          # deterministic (bootstrap seed fixed)
    assert [r for r in gp.valid_rows(rows)] and all(r["valid"] and not r["warmup"] for r in gp.valid_rows(rows))


def test_best_device_flip_detection():
    rows = []
    for i in range(12):
        j = 0.0001 * (i % 3)
        rows += [_row(device="P", load="quiet", occ=0.020 + j), _row(device="G", load="quiet", occ=0.005 + j),
                 _row(device="P", load="contended", occ=0.020 + j), _row(device="G", load="contended", occ=0.050 + j)]
    (b,) = gp.best_device(gp.summarize(rows), rows)
    assert b["best_quiet"] == "G" and b["best_contended"] == "P" and b["flip"] and b["flip_firm"]


def test_telemetry_unavailable_is_null_with_a_reason_never_zero():
    assert gp.parse_smi_line("55, 0, 6144, [N/A], 53, 1492") == {"gpu_util_pct": 55.0, "mem_used_mib": 0.0, "mem_total_mib": 6144.0,
                                                                  "power_w": None, "temp_c": 53.0, "sm_clock_mhz": 1492.0}

    def missing(*a, **k):
        raise FileNotFoundError

    s = gp.smi_sample(run=missing)
    assert s["available"] is False and "not found" in s["reason"] and all(s[k] is None for k in gp.SMI_KEYS)
    bad = gp.smi_sample(run=lambda *a, **k: subprocess.CompletedProcess(a, 9, "", "driver error"))
    assert bad["available"] is False and "exit 9" in bad["reason"] and bad["gpu_util_pct"] is None


def test_monitor_samples_in_a_thread_writes_a_file_and_stops(tmp_path):
    n = []
    mon = gp.NvidiaSmiMonitor(0.05, tmp_path / "t.jsonl", sample_fn=lambda: (n.append(1), {"t": time.perf_counter(), "available": False, "reason": "none"})[1])
    with mon:
        time.sleep(0.4)
    assert len(mon.samples) >= 3 and mon.latest()["reason"] == "none" and not mon._thread.is_alive()
    assert len((tmp_path / "t.jsonl").read_text().splitlines()) == len(mon.samples)


def test_burner_cleanup_on_normal_exit_timeout_and_expiry():
    with gp.GpuBurner(target=gp._dummy_burner, max_s=30) as b:
        assert b.alive()
        b.resume()
        b.pause()
        proc = b._proc
    assert not proc.is_alive()                                                              # joined or terminated by __exit__
    b2 = gp.GpuBurner(target=gp._never_ready_burner, max_s=30, ready_timeout_s=1.0)
    with pytest.raises(TimeoutError):
        b2.start()
    assert not b2._proc.is_alive()                                                          # a burner that never gets ready is killed
    b3 = gp.GpuBurner(target=gp._dummy_burner, max_s=0.3).start()
    time.sleep(1.5)
    assert not b3.alive()                                                                   # the hard lifetime bound ends it by itself
    b3.close()


def test_dispatch_choices_reconstruction():
    ev = [{"event": "run_started", "tasks": {"a": {"eligible_pools": ["P", "E", "G"]}, "b": {"eligible_pools": ["P", "E"]}, "c": {"eligible_pools": ["P", "E", "G"]}}},
          {"event": "worker_ready", "worker_id": "P0", "pool": "P"}, {"event": "worker_ready", "worker_id": "E0", "pool": "E"},
          {"event": "worker_ready", "worker_id": "G0", "pool": "G"},
          {"event": "task_dispatched", "task_id": "a", "worker_id": "G0", "queue_wait_seconds": 0.0},   # P0, E0, G0 idle: choice incl. G and CPU
          {"event": "task_dispatched", "task_id": "b", "worker_id": "P0", "queue_wait_seconds": 0.01},   # P0, E0 idle (G0 busy, not eligible): 2 CPU
          {"event": "task_dispatched", "task_id": "c", "worker_id": "E0", "queue_wait_seconds": 0.0}]    # only E0 idle: forced
    n = gp.dispatch_choices(ev)
    assert n == {"dispatches": 3, "one": 1, "multi": 2, "g_and_cpu": 1, "waited": 1}


def test_lp_lower_bound_matches_a_hand_calculation():
    # two workers pools of 1; stage x costs 1 s on A and 2 s on B, 4 tasks: best split 8/3 tasks on A... T = 4*1*2/(1*2+1*1)... solve by hand below
    b = gp.lp_lower_bound({"x": 4}, {("x", "A"): 1.0, ("x", "B"): 2.0}, {"A": 1, "B": 1})
    # shares s on A: 4*s*1 = T and 4*(1-s)*2 = T  ->  s = 2/3, T = 8/3
    assert b["T_s"] == pytest.approx(8 / 3, rel=1e-6)
    assert gp.headroom(3.2, b["T_s"]) == pytest.approx((3.2 / (8 / 3) - 1) * 100)
    with pytest.raises(ValueError):
        gp.lp_lower_bound({"y": 1}, {("x", "A"): 1.0}, {"A": 1})                            # a stage nobody can run is an error, not a silent skip


def test_verification_detects_a_corrupt_cpu_output_and_an_out_of_tolerance_cuda_output(tmp_path):
    import numpy as np

    from caosched.apps.stages import STAGES

    m = _script()
    spike = importlib.util.spec_from_file_location("gpu_spike", ROOT / "scripts" / "gpu_spike.py")
    assert spike is not None and spike.loader is not None
    sp = importlib.util.module_from_spec(spike)
    spike.loader.exec_module(sp)
    cell = m.CellData("img_edges", {}, 32, tmp_path, sp)
    good = tmp_path / "good.bin"
    good.write_bytes(cell.ref_blob)
    assert cell.verify("P", good)["ok"] is True and cell.verify("G", good)["ok"] is True
    from caosched.apps.stages import decode_arrays
    ref_arr = decode_arrays([cell.ref_blob])[0]
    tampered = ref_arr.copy()
    tampered[5, 5] = 255 - int(tampered[5, 5])                                              # one pixel off by a lot
    bad = tmp_path / "bad.bin"
    bad.write_bytes(STAGES["img_edges"].encode(tampered))
    assert cell.verify("P", bad)["ok"] is False                                             # CPU: byte identity required
    off = ref_arr.astype(np.int16) + 5
    wide = tmp_path / "wide.bin"
    wide.write_bytes(STAGES["img_edges"].encode(np.clip(off, 0, 255).astype(np.uint8)))
    assert cell.verify("G", wide)["ok"] is False and cell.verify("G", wide)["mode"] == "tolerance"


def test_existing_output_paths_are_never_overwritten(tmp_path):
    m = _script()
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "raw_samples.jsonl").write_text(json.dumps(_row()) + "\n")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(FileExistsError):
        m.main(["summarize", str(raw), str(out)])
    with pytest.raises(FileExistsError):
        m.main(["run", str(out)])
    assert m.main(["summarize", str(raw), str(tmp_path / "new_out")]) == 0
    assert (tmp_path / "new_out" / "summary.csv").is_file()
    assert m.main(["summarize", str(raw), str(tmp_path / "ignored"), "--check", str(tmp_path / "new_out" / "summary.csv")]) == 0   # independent recomputation


@pytest.mark.skipif(not cuda_available(), reason="no CUDA device (torch.cuda.is_available() is False)")
def test_hardware_one_cell_cpu_and_cuda_are_verified_through_the_worker_pool(tmp_path):
    m = _script()
    spike = importlib.util.spec_from_file_location("gpu_spike", ROOT / "scripts" / "gpu_spike.py")
    assert spike is not None and spike.loader is not None
    sp = importlib.util.module_from_spec(spike)
    spike.loader.exec_module(sp)
    cell = m.CellData("img_edges", {}, 128, tmp_path, sp)
    pool, _ = m.make_pool()
    try:
        recs = {d: m.run_item(pool, None, cell, "img_edges", d, "quiet", 1, "quiet", i, False, tmp_path, {}) for i, d in enumerate(("P", "E", "G"))}
    finally:
        pool.shutdown()
    for d, r in recs.items():
        assert r["valid"] is True, (d, r["reason"], r["error"])
        assert r["occupation_s"] >= r["worker_span_s"] > 0 and r["ipc_in_s"] >= 0 and r["telemetry_reason"] == "monitor off"


def test_simulation_matches_hand_calculations_and_oracle_never_loses_to_greedy():
    cost = {("img_source", "P"): 1.0, ("img_source", "E"): 2.0, ("img_denoise", "P"): 1.0, ("img_denoise", "E"): 2.0, ("img_denoise", "G"): 0.5,
            ("img_edges", "P"): 1.0, ("img_edges", "E"): 2.0, ("img_edges", "G"): 0.5, ("img_features", "P"): 1.0, ("img_features", "E"): 2.0,
            ("img_features", "G"): 0.5}
    el = {"img_source": ("P", "E"), "img_denoise": ("G", "P", "E"), "img_edges": ("G", "P", "E"), "img_features": ("G", "P", "E")}
    one = gp.simulate_list_schedule(1, cost, el, {"P": 1}, "greedy")            # one chain, one P worker: 4 stages of 1 s
    assert one["makespan_s"] == pytest.approx(4.0) and one["dispatches"] == 4 and one["one"] == 4
    with_coord = gp.simulate_list_schedule(1, cost, el, {"P": 1}, "greedy", coord_s=0.1)
    assert with_coord["makespan_s"] == pytest.approx(4.4)                          # every dispatch is delayed by the serial coordinator
    both = gp.simulate_list_schedule(2, cost, el, {"P": 1, "E": 1, "G": 1}, "greedy")
    best = gp.simulate_list_schedule(2, cost, el, {"P": 1, "E": 1, "G": 1}, "oracle")
    assert best["makespan_s"] <= both["makespan_s"] + 1e-9 and both["g_and_cpu"] >= 1
    assert gp.fit_coord_s(4.4, hi=0.2, run=lambda c: gp.simulate_list_schedule(1, cost, el, {"P": 1}, "greedy", coord_s=c)["makespan_s"]) == pytest.approx(0.1, abs=1e-6)


def test_manifest_verification_detects_a_changed_and_a_missing_file(tmp_path):
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta")
    rows = ["relpath\tsize\tsha256"] + [f"{n}\t{(tmp_path / n).stat().st_size}\t{gp.sha256_file(tmp_path / n)}" for n in ("a.txt", "b.txt")]
    (tmp_path / "SHA256_MANIFEST.tsv").write_text("\n".join(rows) + "\n")
    assert gp.verify_manifest(tmp_path) == []
    (tmp_path / "a.txt").write_text("alpha!")
    (tmp_path / "b.txt").unlink()
    assert sorted(gp.verify_manifest(tmp_path)) == ["hash mismatch a.txt", "missing b.txt"]
