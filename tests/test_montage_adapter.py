"""MontageAdapter on a hand-built 3-job instance whose commands are `python -c` scripts (no Montage)."""
import dataclasses
import hashlib
import json
import pickle
import sys

import pytest
import yaml

from caosched.core.event_log import read_events
from caosched.core.runtime_config import RuntimeConfig
from caosched.experiment.design import Condition
from caosched.experiment.montage_adapter import MontageAdapter, build_policy, compare_outputs, factory

COPY = "import sys; open(sys.argv[-1],'w').write(''.join(open(f).read() for f in sys.argv[1:-1]) + 'x')"
OUT = hashlib.sha256(b"RxRxxx").hexdigest()   # a = R+x, b = a+x, out = a+b+x


def _job(jid, name, ins, out):
    return {"type": "job", "name": name, "id": jid, "arguments": ["-c", COPY, *ins, out],
            "uses": [{"lfn": f, "type": "input"} for f in ins] + [{"lfn": out, "type": "output"}]}


@pytest.fixture
def root(tmp_path):
    inst = tmp_path / "montage" / "instances" / "tiny"
    (inst / "data").mkdir(parents=True)
    (inst / "inputs").mkdir()
    (inst / "inputs" / "raw.txt").write_text("R")
    doc = {"pegasus": "5.0.4", "name": "tiny",
           "replicaCatalog": {"replicas": [{"lfn": "raw.txt", "pfns": [{"site": "ipac", "pfn": "http://example.invalid/raw.txt"}]}]},
           "jobs": [_job("J1", "tA", ["raw.txt"], "a.txt"), _job("J2", "tB", ["a.txt"], "b.txt"),
                    _job("J3", "tA", ["a.txt", "b.txt"], "out.txt")],
           "jobDependencies": [{"id": "J1", "children": ["J2", "J3"]}, {"id": "J2", "children": ["J3"]}]}
    (inst / "data" / "montage-workflow.yml").write_text(yaml.safe_dump(doc))
    return tmp_path / "montage"


@pytest.fixture
def adapter(root):
    a = MontageAdapter(root, executables={"tA": sys.executable, "tB": sys.executable},
                       runtime_config=RuntimeConfig(p_core_slots=(0,), e_core_slots=(1,)), timeout_s=60, run_timeout_s=120)
    yield a
    a.close()


def _cond(tmp_path, name="B4", ref=OUT, **kw):
    refp = tmp_path / f"ref_{name}.json"
    refp.write_text(json.dumps({"out.txt": ref}))
    return Condition(name, name, None, {}, {"reference_hashes": str(refp), "final_outputs": ["out.txt"], **kw}, instance="tiny")


def _run(adapter, cond, tmp_path, n):
    wd = tmp_path / "session" / "runs" / f"b0000_0{n}_{cond.name}"
    wd.mkdir(parents=True)
    return adapter.run_one(cond, wd, seed=1), wd


def test_b4_run_verifies_and_reuses_the_pool(adapter, tmp_path):
    rec, wd = _run(adapter, _cond(tmp_path), tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True and rec.output_hashes == {"out.txt": OUT}
    assert rec.extra["n_tasks"] == 3 and rec.extra["policy"] == "B4_greedy_eligible" and rec.extra["decision_time_total_s"] >= 0
    assert rec.input_hashes == {"raw.txt": hashlib.sha256(b"R").hexdigest()}
    ev = read_events(wd / rec.event_log)
    assert ev[0]["metadata"]["experiment_id"] == "session" and ev[-1]["status"] == "completed"
    pool = adapter._pool
    rec2, _ = _run(adapter, _cond(tmp_path, ref="0" * 64), tmp_path, 1)   # wrong reference hash: ran fine, output not verified
    assert rec2.status == "ok" and rec2.output_ok is False and adapter._pool is pool
    assert adapter.verify(_cond(tmp_path), wd, rec)[0] is True


def test_restricted_eligibility_is_enforced(adapter, tmp_path):
    rec, wd = _run(adapter, _cond(tmp_path, eligible_pools={"tB": ["E"]}), tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True
    pools = {e["task_id"]: e["pool"] for e in read_events(wd / rec.event_log) if e["event"] == "task_dispatched"}
    assert pools["J2"] == "E" and pools["J1"] == "P"      # B4 prefers P; J2 is only eligible for E


def test_failed_run_is_kept_and_the_pool_rebuilt(adapter, root, tmp_path):
    bad = MontageAdapter(root, executables={"tA": sys.executable, "tB": str(tmp_path / "nope.exe")},
                         runtime_config=adapter.runtime_config, timeout_s=60)
    rec, wd = _run(bad, _cond(tmp_path), tmp_path, 0)
    assert rec.status == "failed" and "J2" in rec.error and rec.output_ok is None
    assert bad._pool is None and (wd / rec.event_log).is_file()
    bad.close()


def test_compare_outputs_bytes_then_tolerance(tmp_path):
    from astropy.io import fits
    import numpy as np
    ref, run = tmp_path / "ref", tmp_path / "run"
    ref.mkdir(), run.mkdir()
    for d, v in ((ref, 1.0), (run, 1.0 + 1e-6)):
        fits.PrimaryHDU(np.full((4, 4), v, dtype=">f8")).writeto(d / "m.fits")
        (d / "m.png").write_bytes(b"png-" + (b"a" if d is ref else b"b"))
    refh = {n: hashlib.sha256((ref / n).read_bytes()).hexdigest() for n in ("m.fits", "m.png")}
    assert compare_outputs(run, ("m.fits", "m.png"), refh)[0] is False                                  # bytes differ, no tolerance
    ok, _, verdict = compare_outputs(run, ("m.fits", "m.png"), refh, ref, fits_atol=1e-3)
    assert ok and verdict == {"m.fits": "within_atol", "m.png": "not_compared"}
    assert compare_outputs(run, ("m.fits",), refh, ref, fits_atol=1e-9)[0] is False                     # outside tolerance
    assert compare_outputs(ref, ("m.fits", "m.png"), refh)[2] == {"m.fits": "identical", "m.png": "identical"}
    assert compare_outputs(run, ("gone.fits",), refh)[2] == {"gone.fits": "missing"}


def test_build_policy_names_and_factory(root, tmp_path, monkeypatch):
    prof = tmp_path / "20261011T000000_profile.json"
    prof.write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": [
        {"workload": "tA", "size": 1, "pool": p, "median_s": 1.0} for p in "PE"]}))

    def pol(policy, est=None, **kw):
        return build_policy(Condition("c", policy, est, {}, {"profile": str(prof), **kw}), 7).name
    assert pol("random") == "random_s7" and pol("B1") == "B1_round_robin" and pol("B5_criticality") == "B5_criticality"
    assert pol("EFT_E1") == "EFT_E1" and pol("EFT_E3_rank") == "EFT_E3_rank" and pol("EFT_x", "E1+rc") == "EFT_E1_rc"
    assert pol("HEFT_E1") == "HEFT_E1" and pol("PEFT_E1") == "PEFT_E1"
    with pytest.raises(ValueError, match="profile"):
        build_policy(Condition("c", "EFT_E1"), 0)
    with pytest.raises(ValueError, match="unknown policy"):
        pol("nonsense")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"montage_root": str(root), "timeout_s": 5}))
    monkeypatch.setenv("CAO_MONTAGE_ADAPTER_CONFIG", str(cfg))
    f = factory()
    assert f.montage_root == root and f.timeout_s == 5 and pickle.loads(pickle.dumps(f))._pool is None


def test_run_one_without_an_assigned_instance_is_a_clear_error(adapter, tmp_path):
    cond = dataclasses.replace(_cond(tmp_path), instance=None)
    with pytest.raises(ValueError, match="no workflow instance"):
        adapter.run_one(cond, tmp_path, seed=1)


def test_cleanup_work_only_after_verified_runs(root, tmp_path):
    a = MontageAdapter(root, executables={"tA": sys.executable, "tB": sys.executable}, cleanup_work=True,
                       runtime_config=RuntimeConfig(p_core_slots=(0,), e_core_slots=(1,)), timeout_s=60, run_timeout_s=120)
    try:
        rec, wd = _run(a, _cond(tmp_path), tmp_path, 0)
        assert rec.output_ok is True and (wd / "work" / "out.txt").is_file()      # run_one alone never deletes
        assert a.verify(_cond(tmp_path), wd, rec)[0] is True                      # the runner's final check does
        assert not (wd / "work").exists() and rec.extra["work_dir_removed_after_verification"]
        assert (wd / rec.event_log).is_file()
        rec2, wd2 = _run(a, _cond(tmp_path, ref="0" * 64), tmp_path, 1)      # unverified output: the work dir is kept
        assert a.verify(_cond(tmp_path, ref="0" * 64), wd2, rec2)[0] is False and (wd2 / "work" / "out.txt").is_file()
    finally:
        a.close()


def test_random_occupancy_logs_decision_context_and_respects_eligibility(adapter, tmp_path):
    from caosched.dataset.events import rows_from_events
    cond = _cond(tmp_path, "RandomOccupancy", eligible_pools={"tB": ["E"]}, seed=5, allowed_pools=["P", "E"])
    rec, wd = _run(adapter, cond, tmp_path, 0)
    assert rec.status == "ok" and rec.output_ok is True and rec.extra["policy"] == "campaign_random_occupancy"
    ev = read_events(wd / rec.event_log)
    disp = {e["task_id"]: e for e in ev if e["event"] == "task_dispatched"}
    assert len(disp) == 3 and disp["J2"]["pool"] == "E"                       # J2 is only eligible for E
    for e in disp.values():                                                   # the chosen worker's context is logged
        assert e["decision"]["ctx_version"] == 2 and "ctx" in e["decision"]["candidates"][e["worker_id"]]
    assert [r["ctx_source"] for r in rows_from_events(ev, "decision")] == ["decision"] * 3
    assert ev[0]["scheduler_config"]["allowed_pools"] == ["P", "E"] and ev[0]["scheduler_config"]["seed"] == 5
    # the dataset builder accepts the log (session layout) and keeps its 3 rows with the logged context
    from caosched.dataset.build import build_dataset
    src = wd / rec.event_log
    dst = tmp_path / "ev" / "20261012T101305" / "runs" / "r0" / "r0.jsonl"
    dst.parent.mkdir(parents=True)
    dst.write_text(src.read_text().replace('"experiment_id": "session"', '"experiment_id": "20261012T101305"'))
    (dst.parent / "run_manifest.json").write_text(json.dumps({"status": rec.status, "verification": {"passed": rec.output_ok}}))
    (tmp_path / "profiles").mkdir()
    out = build_dataset(tmp_path / "ev", tmp_path / "profiles", tmp_path / "ds")
    man = json.loads((out / "manifest.json").read_text())
    assert man["n_task_rows"] == 3 and man["rows_per_ctx_source"] == {"decision": 3} and man["n_candidate_rows"] == 0
    only_e, _ = _run(adapter, _cond(tmp_path, "RandomOccupancy", allowed_pools=["E"]), tmp_path, 1)
    assert only_e.status == "ok" and only_e.extra["tasks_per_pool"].get("P", 0) == 0


def test_random_occupancy_policy_kwargs():
    p = build_policy(Condition("c", "RandomOccupancy", None, {}, {"seed": 3, "allowed_pools": ["E"], "min_idle_s": 0.5,
                                                                    "concurrency": [1, 2]}), 99)
    d = p.describe()
    assert (d["seed"], d["allowed_pools"], d["min_idle_s"], d["concurrency"]) == (3, ["E"], 0.5, (1, 2))
    assert build_policy(Condition("c", "RandomOccupancy"), 99).seed == 99          # default: the run seed


def test_max_p_slots_limits_the_p_pool(root):
    full = MontageAdapter(root)._config()
    if len(full.p_core_slots) < 3:
        pytest.skip("host has fewer than 3 physical P cores")
    assert len(MontageAdapter(root, max_p_slots=2)._config().p_core_slots) == 2
    assert MontageAdapter(root, max_p_slots=2)._config().e_core_slots == full.e_core_slots


def test_reference_by_instance_overrides_the_default(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text('{"out.txt": "aa"}')
    b.write_text('{"out.txt": "bb"}')
    cond = Condition("c", "B4", None, {}, {"reference_hashes": str(a), "reference_by_instance": {"i2": {"reference_hashes": str(b)}}},
                     instance="i2")
    assert MontageAdapter()._reference(cond) == {"out.txt": "bb"}
    assert MontageAdapter()._reference(dataclasses.replace(cond, instance="i1")) == {"out.txt": "aa"}
