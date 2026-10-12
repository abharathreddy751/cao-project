"""Pegasus workflow YAML -> internal DAG of external-command tasks (AD-1).

Reads the file written by ``Pegasus.api.Workflow.write()`` (schema 5.x) with
no manual edits:

  jobs[]            -> one extcmd task each (task id = job id); argv =
                       executable + ``arguments`` (File arguments are already
                       lfn strings); ``uses`` -> declared inputs / outputs by
                       lfn; ``stdout`` -> redirected to that lfn
  edges             -> union of ``jobDependencies`` and file producer ->
                       consumer relations; the two are compared and any
                       disagreement is reported, never silently dropped
  raw inputs        -> input lfns no job produces, looked up in the
                       ``replicaCatalog`` (inline or a separate file)

All jobs run in one flat work directory (lfn == file name there), like a
shared-filesystem Pegasus run. Jobs are not clustered: ``clusters.size``
profiles are ignored and every job is one task. Jobs of type other than
"job" (sub-workflows) and ``stderr``/``stdin`` redirection are rejected.
Executables are ``executables[name]``, else ``bin_dir/name``, else ``name``
on PATH; the transformation catalog's pfns (container paths) are not used.
"""
from __future__ import annotations

import collections
import dataclasses
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import yaml

from caosched.core.dag import DAG
from caosched.core.extcmd import declared_input_bytes, make_extcmd_task


@dataclasses.dataclass
class LoadedWorkflow:
    dag: DAG
    work_dir: Path
    raw_inputs: dict          # lfn -> pfn from the replica catalog (None if absent from it)
    final_outputs: list       # lfns written by a job and consumed by none
    report: dict              # counts, edge agreement, unresolved inputs


def _safe(lfn: str) -> str:
    """lfns become paths inside the work directory: no absolute paths, no '..'."""
    win = PureWindowsPath(lfn)  # also catches drive-relative ("C:x") and root-relative ("\\x") names
    if PurePosixPath(lfn).is_absolute() or win.is_absolute() or win.drive or win.root \
            or ".." in PurePosixPath(lfn.replace("\\", "/")).parts:
        raise ValueError(f"Unsafe logical file name {lfn!r}")
    return lfn


def _replicas(doc: dict, catalog_path) -> dict:
    rc = yaml.safe_load(Path(catalog_path).read_text(encoding="utf-8")) if catalog_path else doc.get("replicaCatalog")
    out: dict[str, str] = {}
    for r in (rc or {}).get("replicas", []):
        pfns = r.get("pfns") or ([{"pfn": r["pfn"]}] if "pfn" in r else [])
        if pfns:
            out.setdefault(r["lfn"], pfns[0]["pfn"])
    return out


def load_workflow(path, work_dir, *, bin_dir=None, executables: dict | None = None, replica_catalog=None,
                  timeout_s: float = 600.0, env: dict | None = None) -> LoadedWorkflow:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    jobs = doc.get("jobs") or []
    if not jobs:
        raise ValueError(f"{path}: workflow has no jobs")
    ids = [j["id"] for j in jobs]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: duplicate job ids")
    work_dir = Path(work_dir).resolve()

    io: dict[str, tuple[list, list]] = {}
    producer: dict[str, str] = {}
    for j in jobs:
        if j.get("type", "job") != "job":
            raise NotImplementedError(f"Job {j['id']}: type {j['type']!r} (sub-workflow) is not supported")
        if j.get("stderr") or j.get("stdin"):
            raise NotImplementedError(f"Job {j['id']}: stdin/stderr redirection is not supported")
        ins: list[str] = []
        outs: list[str] = []
        for u in j.get("uses", []):
            if u["type"] not in ("input", "output"):  # e.g. "checkpoint": dropping it would hide a real dependency
                raise ValueError(f"Job {j['id']}: unsupported `uses` type {u['type']!r} for {u['lfn']!r} "
                                 f"(only input/output)")
            (ins if u["type"] == "input" else outs).append(_safe(u["lfn"]))
        if j.get("stdout") and j["stdout"] not in outs:
            outs.append(_safe(j["stdout"]))
        io[j["id"]] = (ins, outs)
        for lfn in outs:
            if producer.setdefault(lfn, j["id"]) != j["id"]:
                raise ValueError(f"File {lfn!r} is produced by both {producer[lfn]} and {j['id']}")

    from_files = {(producer[lfn], jid) for jid, (ins, _) in io.items() for lfn in ins
                  if lfn in producer and producer[lfn] != jid}
    from_yaml = {(d["id"], c) for d in doc.get("jobDependencies") or [] for c in d.get("children", [])}
    unknown = sorted({x for e in from_yaml for x in e if x not in io})
    if unknown:
        raise ValueError(f"jobDependencies name unknown job ids: {unknown}")
    parents: dict[str, list] = collections.defaultdict(list)
    pos = {jid: i for i, jid in enumerate(ids)}
    for p, c in sorted(from_files | from_yaml, key=lambda e: (pos[e[0]], pos[e[1]])):
        parents[c].append(p)

    def executable(name: str) -> str:
        return (executables or {}).get(name) or (str(Path(bin_dir) / name) if bin_dir else name)

    tasks = {}
    for j in jobs:
        ins, outs = io[j["id"]]
        tasks[j["id"]] = make_extcmd_task(
            j["id"], [executable(j["name"]), *[str(a) for a in j.get("arguments", [])]], work_dir, ins, outs,
            parents[j["id"]], timeout_s=timeout_s, env=env, stdout=j.get("stdout"), name=j["name"])
    dag = DAG(tasks)

    rc = _replicas(doc, replica_catalog)
    raw = {lfn: rc.get(lfn) for lfn in dict.fromkeys(l for ins, _ in io.values() for l in ins) if lfn not in producer}
    consumed = {l for ins, _ in io.values() for l in ins}
    report = {
        "n_jobs": len(jobs), "n_edges": len(from_files | from_yaml),
        "n_edges_jobDependencies": len(from_yaml), "n_edges_from_files": len(from_files),
        "edges_only_in_jobDependencies": sorted(from_yaml - from_files),
        "edges_only_in_files": sorted(from_files - from_yaml),
        "n_raw_inputs": len(raw), "unresolved_inputs": sorted(l for l, pfn in raw.items() if pfn is None),
        "transformations": dict(collections.Counter(j["name"] for j in jobs)),
    }
    return LoadedWorkflow(dag, work_dir, raw, [l for l in producer if l not in consumed], report)


def _local_source(lfn: str, pfn: str | None, search_dirs) -> Path | None:
    if pfn and pfn.startswith("file:"):
        p = Path(url2pathname(unquote(urlparse(pfn).path)))
        if p.is_file():
            return p
    return next((d / lfn for d in map(Path, search_dirs) if (d / lfn).is_file()), None)


def stage_raw_inputs(wf: LoadedWorkflow, search_dirs=()) -> None:
    """Copy every raw input into the work directory: from its ``file://`` pfn if
    that exists, else from the first of ``search_dirs`` holding a file of that
    name. Nothing is downloaded: an http(s) pfn must have been fetched into a
    search dir already. Then refreshes the tasks' known input sizes."""
    wf.work_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    for lfn, pfn in wf.raw_inputs.items():
        dst = wf.work_dir / lfn
        if dst.exists():
            continue
        src = _local_source(lfn, pfn, search_dirs)
        if src is None:
            missing.append(lfn)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    if missing:
        raise FileNotFoundError(f"Cannot stage {len(missing)} raw input(s) (no local file:// replica, not in "
                                f"{list(map(str, search_dirs))}): {missing[:10]}")
    for t in wf.dag.tasks.values():
        assert t.params is not None  # every adapter task is an extcmd task
        t.input_bytes = declared_input_bytes(t.params)
