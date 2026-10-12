"""Phase 6A dataset builder: provenance, exclusions, schema, splits, validation.
Uses small synthetic event logs written under tmp_path as *test fixtures*."""
import csv
import json

import pytest

from caosched.dataset.build import TASK_FIELDS, build_dataset, classify, validate_dataset


def _write_run(path, run_id, exp, completed=True, policy="B4", decision=False, order_index=1):
    ev = [{"seq": 0, "t": 100.0, "event": "run_started", "run_id": run_id, "scheduler": policy,
           "scheduler_config": {"binds_only_idle": not decision}, "epoch_anchor": 1.79e9, "perf_anchor": 100.0,
           "metadata": {"experiment_id": exp, "trace": "tr", "repeat": 0, "order_index": order_index},
           "tasks": {"a": {"workload": "matmul", "size": 256, "seed": 1},
                     "b": {"workload": "compression", "size": 1048576, "seed": 2}}},
          {"seq": 1, "t": 100.0, "event": "worker_ready", "worker_id": "P0", "pool": "P", "actual_affinity": [0]},
          {"seq": 2, "t": 100.0, "event": "worker_ready", "worker_id": "E0", "pool": "E", "actual_affinity": [5]}]
    seq = 3
    for tid, wid, pool, t0, t1, k in (("a", "P0", "P", 100.10, 100.20, 0.05), ("b", "E0", "E", 100.12, 100.30, 0.1)):
        ev.append({"seq": seq, "t": t0 - 0.02, "event": "task_ready", "task_id": tid}); seq += 1
        d = {"seq": seq, "t": t0 - 0.01, "event": "task_dispatched", "task_id": tid, "worker_id": wid, "pool": pool}
        if decision:
            d["decision"] = {"model": "kernel", "chosen": wid,
                             "candidates": {"P0": {"wait": 0, "transfer": 0, "exec": 0.04, "finish": 0.04},
                                            "E0": {"wait": 0, "transfer": 0, "exec": 0.09, "finish": 0.09}}}
        ev.append(d); seq += 1
        ev.append({"seq": seq, "t": t0 - 0.005, "event": "task_submitted", "task_id": tid, "worker_id": wid}); seq += 1
        ev.append({"seq": seq, "t": t1 + 0.001, "event": "task_completed", "task_id": tid, "worker_id": wid,
                   "pool": pool, "t_started": t0, "t_completed": t1, "wall_time_seconds": k,
                   "response_time_seconds": t1 - t0 + 0.02}); seq += 1
    ev.append({"seq": seq, "t": 100.4, "event": "run_finished", "status": "completed" if completed else "failed"})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in ev) + "\n", encoding="utf-8")


@pytest.fixture
def tree(tmp_path):
    ev = tmp_path / "data" / "events"
    _write_run(ev / "phase2_20261003T115816" / "r1.jsonl", "r1", "phase2_20261003T115816")
    _write_run(ev / "phase4_20261003T145958" / "r1.jsonl", "r1", "phase4_20261003T145958", decision=True, policy="EFT")
    _write_run(ev / "campaign_20261003T144004" / "run_000.jsonl", "run_000", "campaign_20261003T144004")
    _write_run(ev / "campaign_20261003T144004" / "run_001.jsonl", "run_001", "campaign_20261003T144004", completed=False)
    _write_run(ev / "phase5_20261003T153046" / "x" / "r.jsonl", "r", "phase5_20261003T153046")  # smoke
    (ev / "phase1_chain.jsonl").write_text("{}\n")
    prof = tmp_path / "data" / "profiles"
    prof.mkdir(parents=True)
    (prof / "20261003T115606_profile.json").write_text(json.dumps({"metric": "kernel_wall_time_seconds", "entries": [
        {"workload": "matmul", "size": 256, "pool": "P", "median_s": 0.0008}]}))
    return tmp_path


def test_classify_exclusions(tree):
    root = tree / "data" / "events"
    assert classify(root / "phase1_chain.jsonl", root)[0] is None
    assert "smoke" in classify(root / "phase5_20261003T153046" / "x" / "r.jsonl", root)[1]
    assert classify(root / "phase4_20261003T145958" / "r1.jsonl", root) == ("phase4", None)


def test_build_schema_provenance_and_validation(tree):
    out = build_dataset(tree / "data" / "events", tree / "data" / "profiles", tree / "data" / "datasets", context_source="start")  # fixture logs have no logged decision ctx
    rows = list(csv.DictReader((out / "tasks.csv").open(encoding="utf-8")))
    assert list(rows[0].keys()) == TASK_FIELDS
    assert len(rows) == 6  # 3 completed runs x 2 tasks (failed run, smoke, phase1 excluded)
    m = json.loads((out / "manifest.json").read_text())
    reasons = " ".join(e["reason"] for e in m["excluded"])
    assert "smoke" in reasons and "Phase 1" in reasons and "not completed" in reasons
    assert all(len(s["sha256"]) == 64 for s in m["sources"])
    a = next(r for r in rows if r["source_kind"] == "phase2" and r["task_id"] == "a")
    assert float(a["kernel_s"]) == 0.05 and float(a["setup_s"]) == pytest.approx(0.05)
    assert float(a["queue_wait_s"]) == pytest.approx(0.01) and a["logical_processor"] == "0"
    assert float(a["calibration_kernel_s"]) == 0.0008 and a["calibration_profile"].startswith("20261003T115606")
    assert int(a["input_bytes"]) == 2 * 256 * 256 * 8
    assert a["software_version"].startswith("unrecorded") and a["memory_available_bytes"] == ""
    b4 = next(r for r in rows if r["source_kind"] == "phase4" and r["task_id"] == "b")
    assert float(b4["predicted_exec_s"]) == 0.09 and float(b4["pred_margin_s"]) == pytest.approx(0.05)
    cands = list(csv.DictReader((out / "candidates.csv").open(encoding="utf-8")))
    assert len(cands) == 4 and sum(c["chosen"] == "True" for c in cands) == 2
    splits = json.loads((out / "splits.json").read_text())
    assert splits["by_session"]["train_sessions"] == ["campaign_20261003T144004"]
    assert "phase2_20261003T115816" in splits["by_session"]["test_sessions"]
    assert validate_dataset(out)["rows"] == 6


def test_validation_detects_modified_raw_log(tree):
    out = build_dataset(tree / "data" / "events", tree / "data" / "profiles", tree / "data" / "datasets", context_source="start")  # fixture logs have no logged decision ctx
    p = tree / "data" / "events" / "phase2_20261003T115816" / "r1.jsonl"
    p.write_text(p.read_text() + "\n")
    with pytest.raises(ValueError, match="raw log changed"):
        validate_dataset(out)


def test_default_context_source_is_decision_and_time_splits_follow_collection_order(tree):
    root = tree / "data" / "events"
    # the fixture logs carry no decision context: the default drops every row instead of reconstructing from the start
    out = build_dataset(root, tree / "data" / "profiles", tree / "data" / "datasets0")
    assert json.loads((out / "manifest.json").read_text())["n_task_rows"] == 0
    # two completed campaign runs whose names sort OPPOSITE to collection order (order_index)
    camp = root / "campaign_20261003T150000"
    _write_run(camp / "a_late.jsonl", "a_late", camp.name, order_index=9)
    _write_run(camp / "b_early.jsonl", "b_early", camp.name, order_index=2)
    out = build_dataset(root, tree / "data" / "profiles", tree / "data" / "datasets", context_source="start", train_fraction=0.5)
    sp = json.loads((out / "splits.json").read_text())
    t = sp["time_ordered_within_session"]["sessions"][camp.name]
    assert t["train_runs"] == [f"events/{camp.name}/b_early.jsonl"] and t["test_runs"] == [f"events/{camp.name}/a_late.jsonl"]
    c = sp["by_run_within_latest_campaign"]
    assert c["train_runs"] == t["train_runs"] and c["train_fraction"] == 0.5


def test_stamp_of_names_the_offending_file():
    from caosched.dataset.build import _stamp_of
    assert _stamp_of("x_20261003T115741_profile.json") == "20261003T115741"
    with pytest.raises(ValueError, match="no YYYYMMDDTHHMMSS stamp"):
        _stamp_of("campaign_nostamp")
