"""Pegasus workflow YAML -> internal DAG. The YAML here is hand-built to the
schema Pegasus.api ``Workflow.write()`` produces (jobs / uses / jobDependencies /
replicaCatalog / transformationCatalog). A real generated file is loaded too,
when one exists under data/results."""
import sys
from pathlib import Path

import pytest
import yaml

from caosched.core.coordinator import Coordinator
from caosched.core.event_log import EventLogger
from caosched.core.extcmd import prepare_workdir
from caosched.core.scheduler_base import FirstIdleScheduler
from caosched.core.worker_pool import WorkerPool
from caosched.schedulers.simple import (CriticalityScheduler, GreedyEligibleScheduler, RandomScheduler,
                                        RoundRobinScheduler, ShortestQueueScheduler)
from caosched.workflow.adapter import load_workflow, stage_raw_inputs

COPY = "import sys; open(sys.argv[-1],'w').write(''.join(open(f).read() for f in sys.argv[1:-1]) + 'x')"


def _job(jid, ins, outs, name="py", **extra):
    return {"type": "job", "name": name, "id": jid, "arguments": ["-c", COPY, *ins, outs[0]],
            "uses": [{"lfn": f, "type": "input"} for f in ins]
            + [{"lfn": f, "type": "output", "stageOut": False, "registerReplica": False} for f in outs], **extra}


def _diamond(raw_pfn):
    return {
        "x-pegasus": {"apiLang": "python", "createdBy": "test", "createdOn": "2026-10-11T00:00:00Z"},
        "pegasus": "5.0.4", "name": "diamond",
        "replicaCatalog": {"replicas": [{"lfn": "raw.txt", "pfns": [{"site": "local", "pfn": raw_pfn}]}]},
        "transformationCatalog": {"transformations": [
            {"name": "py", "sites": [{"name": "local", "pfn": "/usr/bin/python3", "type": "installed"}]}]},
        "jobs": [_job("ID0000001", ["raw.txt"], ["a.txt"]), _job("ID0000002", ["a.txt"], ["b.txt"]),
                 _job("ID0000003", ["a.txt"], ["c.txt"]), _job("ID0000004", ["b.txt", "c.txt"], ["d.txt"])],
        "jobDependencies": [{"id": "ID0000001", "children": ["ID0000002", "ID0000003"]},
                            {"id": "ID0000002", "children": ["ID0000004"]},
                            {"id": "ID0000003", "children": ["ID0000004"]}],
    }


def _write(tmp_path, doc, name="wf.yml"):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return p


@pytest.fixture
def raw(tmp_path):
    f = tmp_path / "src" / "raw.txt"
    f.parent.mkdir()
    f.write_text("R")
    return f


def _load(tmp_path, doc, **kw):
    return load_workflow(_write(tmp_path, doc), tmp_path / "work", executables={"py": sys.executable}, **kw)


def test_round_trip_counts_commands_files_and_edges(tmp_path, raw):
    wf = _load(tmp_path, _diamond(raw.as_uri()))
    r = wf.report
    assert (r["n_jobs"], r["n_edges"]) == (4, 4) == (len(wf.dag), sum(len(t.dependencies) for t in wf.dag.tasks.values()))
    assert r["edges_only_in_jobDependencies"] == [] and r["edges_only_in_files"] == [] and r["unresolved_inputs"] == []
    t = wf.dag.tasks["ID0000004"]
    assert t.dependencies == ("ID0000002", "ID0000003") and t.workload == "extcmd"
    assert t.params["argv"] == [sys.executable, "-c", COPY, "b.txt", "c.txt", "d.txt"]
    assert t.params["inputs"] == ["b.txt", "c.txt"] and t.params["outputs"] == ["d.txt"]
    assert t.params["transformation"] == "py" and t.params["cwd"] == str(wf.work_dir)
    assert wf.raw_inputs == {"raw.txt": raw.as_uri()} and wf.final_outputs == ["d.txt"]


def test_edge_disagreement_is_reported_and_union_is_used(tmp_path, raw):
    doc = _diamond(raw.as_uri())
    doc["jobDependencies"].pop(0)                                   # file edges missing from the YAML
    doc["jobDependencies"].append({"id": "ID0000002", "children": ["ID0000003"]})  # YAML-only (control) edge
    r = _load(tmp_path, doc).report
    assert r["edges_only_in_files"] == [("ID0000001", "ID0000002"), ("ID0000001", "ID0000003")]
    assert r["edges_only_in_jobDependencies"] == [("ID0000002", "ID0000003")] and r["n_edges"] == 5


@pytest.mark.parametrize("policy", [FirstIdleScheduler, RoundRobinScheduler, ShortestQueueScheduler,
                                    GreedyEligibleScheduler, CriticalityScheduler, RandomScheduler])
def test_adapted_workflow_runs_under_every_policy_with_identical_output(tmp_path, raw, policy):
    doc = _diamond(raw.as_uri())
    wf = _load(tmp_path, doc, bin_dir=None)
    prepare_workdir(wf.work_dir)
    stage_raw_inputs(wf)
    assert wf.dag.tasks["ID0000001"].input_bytes == 1
    with WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=False) as pool, EventLogger("w", output_dir=tmp_path) as log:
        s = Coordinator(wf.dag, pool, policy(), log).run(run_timeout=120)
    assert s.status == "completed" and set(s.task_status.values()) == {"done"}
    assert (wf.work_dir / "d.txt").read_text() == "RxxRxxx"  # b + c + "x", each of b, c = a + "x"


def test_stdout_redirect_job_and_undeclared_raw_input_report(tmp_path, raw):
    doc = _diamond(raw.as_uri())
    doc["replicaCatalog"]["replicas"] = []
    doc["jobs"][0]["stdout"] = "log.txt"
    doc["jobs"][0]["uses"].append({"lfn": "log.txt", "type": "output"})
    wf = _load(tmp_path, doc)
    assert wf.dag.tasks["ID0000001"].params["stdout"] == "log.txt"
    assert wf.report["unresolved_inputs"] == ["raw.txt"]
    with pytest.raises(FileNotFoundError, match="raw.txt"):
        stage_raw_inputs(wf)
    stage_raw_inputs(wf, search_dirs=[raw.parent])  # found by name in a search dir
    assert (wf.work_dir / "raw.txt").read_text() == "R"


def test_unsupported_or_malformed_workflows_fail_loudly(tmp_path, raw):
    sub = _diamond(raw.as_uri())
    sub["jobs"][1]["type"] = "pegasusWorkflow"
    with pytest.raises(NotImplementedError, match="sub-workflow"):
        _load(tmp_path, sub)
    twice = _diamond(raw.as_uri())
    twice["jobs"][2]["uses"][1]["lfn"] = "b.txt"
    with pytest.raises(ValueError, match="produced by both"):
        _load(tmp_path, twice)
    unsafe = _diamond(raw.as_uri())
    unsafe["jobs"][0]["uses"][0]["lfn"] = "../evil.txt"
    with pytest.raises(ValueError, match="Unsafe"):
        _load(tmp_path, unsafe)
    for evil in ("C:evil.txt", "\\evil.txt", "/evil.txt", "a/../../evil.txt"):  # drive-/root-relative, absolute, traversal
        bad_name = _diamond(raw.as_uri())
        bad_name["jobs"][0]["uses"][0]["lfn"] = evil
        with pytest.raises(ValueError, match="Unsafe"):
            _load(tmp_path, bad_name)
    odd = _diamond(raw.as_uri())
    odd["jobs"][1]["uses"].append({"lfn": "ckpt.dat", "type": "checkpoint"})
    with pytest.raises(ValueError, match="ID0000002.*checkpoint"):
        _load(tmp_path, odd)
    ghost = _diamond(raw.as_uri())
    ghost["jobDependencies"].append({"id": "ID0000001", "children": ["ID9999999"]})
    with pytest.raises(ValueError, match="unknown job ids"):
        _load(tmp_path, ghost)


def _montage_like(n_images=3):
    """The job/file structure montage-workflow.py add_band() creates for one band."""
    jobs, fits = [], []
    for i in range(n_images):
        jobs.append({"type": "job", "name": "mProject", "id": f"P{i}", "arguments": ["-X", f"in{i}.fits", f"p{i}.fits", "region-oversized.hdr"],
                     "uses": [{"lfn": "region-oversized.hdr", "type": "input"}, {"lfn": f"in{i}.fits", "type": "input"},
                              {"lfn": f"p{i}.fits", "type": "output"}, {"lfn": f"p{i}_area.fits", "type": "output"}]})
    diffs = [(i, i + 1) for i in range(n_images - 1)]
    for a, b in diffs:
        jobs.append({"type": "job", "name": "mDiffFit", "id": f"D{a}{b}",
                     "arguments": ["-d", "-s", f"fit.{a}.{b}.txt", f"p{a}.fits", f"p{b}.fits", f"diff.{a}.{b}.fits", "region-oversized.hdr"],
                     "uses": [{"lfn": f, "type": "input"} for f in (f"p{a}.fits", f"p{a}_area.fits", f"p{b}.fits", f"p{b}_area.fits", "region-oversized.hdr")]
                     + [{"lfn": f"fit.{a}.{b}.txt", "type": "output"}]})
    jobs.append({"type": "job", "name": "mConcatFit", "id": "CF", "arguments": ["stat.tbl", "fits.tbl", "."],
                 "uses": [{"lfn": "stat.tbl", "type": "input"}, {"lfn": "fits.tbl", "type": "output"}]
                 + [{"lfn": f"fit.{a}.{b}.txt", "type": "input"} for a, b in diffs]})
    jobs.append({"type": "job", "name": "mBgModel", "id": "BG", "arguments": ["-i", "100000", "images.tbl", "fits.tbl", "corr.tbl"],
                 "uses": [{"lfn": "images.tbl", "type": "input"}, {"lfn": "fits.tbl", "type": "input"}, {"lfn": "corr.tbl", "type": "output"}]})
    for i in range(n_images):
        jobs.append({"type": "job", "name": "mBackground", "id": f"B{i}", "arguments": ["-t", f"p{i}.fits", f"c{i}.fits", "projected.tbl", "corr.tbl"],
                     "uses": [{"lfn": f, "type": "input"} for f in (f"p{i}.fits", f"p{i}_area.fits", "projected.tbl", "corr.tbl")]
                     + [{"lfn": f"c{i}.fits", "type": "output"}, {"lfn": f"c{i}_area.fits", "type": "output"}]})
    jobs.append({"type": "job", "name": "mAdd", "id": "ADD", "arguments": ["-e", "corrected.tbl", "region.hdr", "mosaic.fits"],
                 "uses": [{"lfn": "corrected.tbl", "type": "input"}, {"lfn": "region.hdr", "type": "input"},
                          {"lfn": "mosaic.fits", "type": "output"}, {"lfn": "mosaic_area.fits", "type": "output"}]
                 + [{"lfn": f"c{i}{s}.fits", "type": "input"} for i in range(n_images) for s in ("", "_area")]})
    jobs.append({"type": "job", "name": "mViewer", "id": "V", "arguments": ["-ct", "1", "-gray", "mosaic.fits", "-png", "mosaic.png"],
                 "uses": [{"lfn": "mosaic.fits", "type": "input"}, {"lfn": "mosaic.png", "type": "output"}]})
    producers = {u["lfn"]: j["id"] for j in jobs for u in j["uses"] if u["type"] == "output"}
    edges = {}
    for j in jobs:
        for u in j["uses"]:
            if u["type"] == "input" and u["lfn"] in producers:
                edges.setdefault(producers[u["lfn"]], set()).add(j["id"])
    return {"pegasus": "5.0.4", "name": "montage", "jobs": jobs,
            "jobDependencies": [{"id": p, "children": sorted(c)} for p, c in edges.items()],
            "replicaCatalog": {"replicas": [{"lfn": f, "pfns": [{"site": "local", "pfn": f"file:///data/{f}"}]}
                                            for f in ("region-oversized.hdr", "region.hdr", "stat.tbl", "images.tbl", "projected.tbl", "corrected.tbl")]
                               + [{"lfn": f"in{i}.fits", "pfns": [{"site": "ipac", "pfn": f"http://example.invalid/in{i}.fits"}]} for i in range(n_images)]}}


def test_montage_shaped_workflow_counts_and_kinds(tmp_path):
    doc = _montage_like(3)
    n_edges = sum(len(d["children"]) for d in doc["jobDependencies"])
    wf = load_workflow(_write(tmp_path, doc), tmp_path / "w", bin_dir=tmp_path / "bin")
    assert (len(wf.dag), wf.report["n_edges"]) == (len(doc["jobs"]), n_edges)
    assert wf.report["edges_only_in_files"] == wf.report["edges_only_in_jobDependencies"] == []
    assert wf.report["transformations"] == {"mProject": 3, "mDiffFit": 2, "mConcatFit": 1, "mBgModel": 1,
                                             "mBackground": 3, "mAdd": 1, "mViewer": 1}
    assert wf.dag.tasks["P0"].params["argv"][0] == str(tmp_path / "bin" / "mProject")
    assert wf.final_outputs == ["mosaic_area.fits", "mosaic.png"] and wf.report["unresolved_inputs"] == []
    assert wf.dag.critical_path_length() == 7  # mProject, mDiffFit, mConcatFit, mBgModel, mBackground, mAdd, mViewer
    assert wf.dag.tasks["V"].dependencies == ("ADD",)


REAL = sorted(Path(__file__).resolve().parents[1].glob("data/results/stage1_*/workflow/*.y*ml"))


@pytest.mark.skipif(not REAL, reason="no real generated workflow under data/results/stage1_*/workflow yet")
def test_real_generated_workflow_loads_without_edits(tmp_path):
    doc = yaml.safe_load(REAL[0].read_text(encoding="utf-8"))
    wf = load_workflow(REAL[0], tmp_path / "w")
    assert len(wf.dag) == len(doc["jobs"])
    assert wf.report["n_edges"] == sum(len(d["children"]) for d in doc.get("jobDependencies", []))
    assert wf.report["edges_only_in_files"] == [] and wf.report["edges_only_in_jobDependencies"] == []
