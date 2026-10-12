"""Stage 4 adapter: run ONE real Montage instance under ONE condition (see ``design.py`` for the contract).

Per ``run_one``: Pegasus YAML of ``instances/<instance>/data`` -> extcmd DAG (executables from ``bin_dir``, which is
also prepended to every task's PATH because mDiffFit spawns mDiff/mFitplane by name) -> fresh ``<workdir>/work`` ->
raw inputs from ``instances/<instance>/inputs`` and ``.../data`` -> policy/estimator from the condition -> Coordinator
on one WorkerPool that is created lazily and reused for the whole session (rebuilt after a failed run) -> SHA-256 of
the final outputs, compared with the reference.

Condition fields: ``policy`` (B0_P_only, B0_E_only, B1/round_robin, B2..B7 names, ``random``, ``EFT_<estimator
spec>[_rank]`` e.g. EFT_E1, EFT_E4_rc_rank, ``HEFT_E1``, ``PEFT_E1``), ``estimator`` (E0/E1/E2/E3, ``+rc``,
``Ridge`` = E4, CatBoost, MLP; for ``EFT_*`` it is parsed from the policy name when None), ``instance``, ``kwargs``:
  profile          static profile JSON (E0-E3, B6/B7, HEFT/PEFT)
  model_path       learned model file (Ridge/E4, CatBoost, MLP)
  est_cfg          build_estimator cfg (E3 window, rc alpha/clamp ...)
  policy_cfg       ``policies:`` section for ``policy_factories`` (B2 mapping, B4 eligibility)
  reference_hashes JSON {lfn: sha256} (or a Stage-1 run.json: its ``final_outputs``)
  reference_dir    directory holding the reference output files (needed only for the tolerance comparison)
  fits_atol        absolute tolerance for FITS data when the bytes differ (None: bytes must be identical)
  eligible_pools   {transformation: [pool, ...]} restricts those tasks to the listed pools
  final_outputs    files to verify (default 1-mosaic.fits, 1-mosaic_area.fits, 1-mosaic.png)
  timeout_s / run_timeout_s   per-task / whole-run limits

``factory()`` is the zero-argument ``--adapter caosched.experiment.montage_adapter:factory`` entry point: it reads
the constructor settings from the JSON file named by the environment variable CAO_MONTAGE_ADAPTER_CONFIG, if set.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from caosched.core.coordinator import Coordinator, RunTimeoutError, TaskTimeoutError, pin_coordinator_to_reserved_core
from caosched.core.event_log import EventLogger
from caosched.core.extcmd import WORKDIR_MARKER, prepare_workdir
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.worker_pool import WorkerPool
from caosched.experiment.design import Condition, RunRecord
from caosched.experiment.manifest import sha256_file
from caosched.schedulers import ALL_POLICIES, eft_factories, plan_factories, policy_factories, rank_eft_factories
from caosched.schedulers.simple import RandomScheduler
from caosched.workflow.adapter import load_workflow, stage_raw_inputs

ROOT = Path(__file__).resolve().parents[3]
FINAL_OUTPUTS = ("1-mosaic.fits", "1-mosaic_area.fits", "1-mosaic.png")
_ALIASES = {"B1": "B1_round_robin", "round_robin": "B1_round_robin", "B2": "B2_static_mapping",
            "B3": "B3_shortest_queue", "B4": "B4_greedy_eligible", "B5": "B5_criticality"}
_PROFILE_SPECS = ("E0", "E1", "E2", "E3")


def estimator_spec(policy: str, estimator: str | None) -> str:
    """Spec for ``build_estimator`` ('E4+rc', 'CatBoost', ...). Inverse of ``eft_policy_name`` when ``estimator`` is None."""
    if estimator is None:
        estimator = policy.removeprefix("EFT_").removesuffix("_rank").replace("_rc", "+rc").replace("_e2e", "@e2e")
    return "E4" + estimator[len("Ridge"):] if estimator.startswith("Ridge") else estimator


def build_policy(cond: Condition, seed: int):
    """A fresh scheduling policy (and estimator) for one run."""
    kw, name = cond.kwargs, _ALIASES.get(cond.policy, cond.policy)
    profile = Path(kw["profile"]) if kw.get("profile") else None
    if name == "random":
        return RandomScheduler(kw.get("seed", seed))
    if name in ALL_POLICIES:
        return policy_factories(kw.get("policy_cfg") or {}, profile)[name]()
    if name.startswith("EFT_"):
        spec = estimator_spec(name, cond.estimator)
        if profile is None and spec.partition("@")[0].removesuffix("+rc") in _PROFILE_SPECS:
            raise ValueError(f"{cond.name}: {name} needs kwargs['profile']")
        make = rank_eft_factories if name.endswith("_rank") else eft_factories
        (policy,) = make([spec], profile, est_cfg=kw.get("est_cfg"),  # type: ignore[arg-type]  # profile is optional for model-bound E4/CatBoost; E0-E3 guarded above
                         model_path=Path(kw["model_path"]) if kw.get("model_path") else None).values()
        return policy()
    if name in ("HEFT_E1", "PEFT_E1"):
        if profile is None:
            raise ValueError(f"{cond.name}: {name} needs kwargs['profile']")
        return plan_factories(profile, kw.get("est_cfg"))[name]()
    raise ValueError(f"unknown policy {cond.policy!r}")


def _fits_close(a: Path, b: Path, atol: float) -> bool:
    from astropy.io import fits
    import numpy as np
    with fits.open(a, memmap=False) as fa, fits.open(b, memmap=False) as fb:
        if len(fa) != len(fb):
            return False
        for ha, hb in zip(fa, fb):
            if (ha.data is None) != (hb.data is None):
                return False
            if ha.data is not None and (ha.data.shape != hb.data.shape
                                        or not np.allclose(ha.data, hb.data, rtol=0.0, atol=atol, equal_nan=True)):
                return False
    return True


def compare_outputs(work: Path, names, reference: dict, reference_dir=None, fits_atol=None) -> tuple[bool, dict, dict]:
    """(passed, {name: sha256 or None}, {name: verdict}). Byte equality first; else, for FITS files with
    ``fits_atol`` and a ``reference_dir``, numpy allclose on the data. A PNG that differs is not compared
    (verdict 'not_compared') only when some FITS file passed by tolerance, since a render of near-equal
    data need not be byte-identical."""
    hashes = {n: sha256_file(work / n) if (work / n).is_file() else None for n in names}
    verdict = {}
    for n in names:
        if hashes[n] is None:
            verdict[n] = "missing"
        elif n not in reference:
            verdict[n] = "no_reference"
        elif hashes[n] == reference[n]:
            verdict[n] = "identical"
        elif (n.endswith(".fits") and fits_atol is not None and reference_dir is not None
              and (Path(reference_dir) / n).is_file() and _fits_close(work / n, Path(reference_dir) / n, fits_atol)):
            verdict[n] = "within_atol"
        else:
            verdict[n] = "differs"
    if "within_atol" in verdict.values():
        verdict = {n: "not_compared" if v == "differs" and n.endswith(".png") else v for n, v in verdict.items()}
    return all(v in ("identical", "within_atol", "not_compared") for v in verdict.values()), hashes, verdict


class MontageAdapter:
    def __init__(self, montage_root=None, bin_dir=None, executables: dict | None = None,
                 runtime_config: RuntimeConfig | None = None, timeout_s: float = 3600.0,
                 run_timeout_s: float | None = None, cleanup_work: bool = False):
        self.montage_root = Path(montage_root) if montage_root else ROOT / "data" / "montage"
        self.bin_dir = Path(bin_dir) if bin_dir else self.montage_root / "bin_win64"
        self.executables = dict(executables or {})
        self.runtime_config = runtime_config
        self.timeout_s, self.run_timeout_s = timeout_s, run_timeout_s
        self.cleanup_work = cleanup_work  # delete a VERIFIED run's work dir (~2 GB); hashes and the event log are kept
        self._pool: WorkerPool | None = None

    def __getstate__(self):  # picklable for the runner's isolated mode: the pool lives in the process that built it
        return {**self.__dict__, "_pool": None}

    # --- worker pool: one per session, rebuilt after a failed run ----------------

    def _config(self) -> RuntimeConfig:
        if self.runtime_config is None:
            self.runtime_config = RuntimeConfig.from_topology(max_p_slots=None)
        return self.runtime_config

    def _get_pool(self) -> WorkerPool:
        if self._pool is not None and (self._pool.dead_workers() or self._pool.idle_workers() != self._pool.worker_ids()):
            self.close()
        if self._pool is None:
            self._pool = WorkerPool.from_config(self._config(), warmup=False, strict_affinity=True)
        return self._pool

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown()

    # --- one run ---------------------------------------------------------------

    def _final(self, cond: Condition) -> tuple:
        return tuple(cond.kwargs.get("final_outputs") or FINAL_OUTPUTS)

    def _reference(self, cond: Condition) -> dict:
        ref = json.loads(Path(cond.kwargs["reference_hashes"]).read_text(encoding="utf-8"))
        return ref.get("final_outputs", ref)

    def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord:
        workdir = Path(workdir)
        if condition.instance is None:
            raise ValueError(f"{condition.name}: no workflow instance assigned (the planner fills it in per block)")
        inst = self.montage_root / "instances" / condition.instance
        env = {"PATH": str(self.bin_dir) + os.pathsep + os.environ.get("PATH", "")}
        exes = {p.stem: str(p) for p in self.bin_dir.glob("*.exe")} | self.executables
        wf = load_workflow(inst / "data" / "montage-workflow.yml", workdir / "work", bin_dir=self.bin_dir,
                           executables=exes, timeout_s=self.timeout_s, env=env)
        for t in wf.dag.tasks.values():  # e.g. {"mProject": ["P"]}: a per-transformation restriction, enforced by the coordinator
            if t.est_workload in (condition.kwargs.get("eligible_pools") or {}):
                t.eligible_pools = tuple(condition.kwargs["eligible_pools"][t.est_workload])
        prepare_workdir(wf.work_dir)
        stage_raw_inputs(wf, [inst / "inputs", inst / "data"])
        input_hashes = {lfn: sha256_file(wf.work_dir / lfn) for lfn in sorted(wf.raw_inputs)}
        policy = build_policy(condition, seed)
        run_id = workdir.name
        log_name = f"{run_id}.jsonl"
        meta = {"experiment_id": workdir.parent.parent.name, "workflow_instance": condition.instance,
                "condition": condition.name, "policy": condition.policy, "estimator": condition.estimator, "seed": seed}
        extra = {"n_tasks": len(wf.dag), "policy": policy.name}
        status, error, summary = "ok", None, None
        try:
            pool = self._get_pool()
            pin_coordinator_to_reserved_core(self._config())
            with EventLogger(run_id, output_dir=workdir) as log:
                summary = Coordinator(wf.dag, pool, policy, log, run_metadata=meta).run(run_timeout=self.run_timeout_s)
        except Exception as exc:  # noqa: BLE001 - a failed run is data; the runner flags and keeps it
            status = "timeout" if isinstance(exc, (TaskTimeoutError, RunTimeoutError)) else "failed"
            error = f"{type(exc).__name__}: {exc}"
            self.close()  # a killed / dead worker would poison the next run
        if summary is not None:
            extra.update(decision_time_total_s=summary.scheduling_time_seconds, makespan_seconds=summary.makespan_seconds,
                         n_completed=summary.n_completed, tasks_per_pool=summary.tasks_per_pool)
        rec = RunRecord(status=status, event_log=log_name if (workdir / log_name).is_file() else None, error=error,
                        input_hashes=input_hashes, extra=extra)
        if status == "ok":
            try:
                rec.output_ok, rec.output_hashes = self._verify(condition, workdir, rec)
            except Exception as exc:  # noqa: BLE001 - e.g. no reference_hashes: keep the run, unverified
                rec.output_ok, rec.error = False, f"verify raised {type(exc).__name__}: {exc}"
        return rec

    def _verify(self, condition: Condition, workdir: Path, record: RunRecord) -> tuple[bool, dict]:
        kw = condition.kwargs
        ok, hashes, verdict = compare_outputs(Path(workdir) / "work", self._final(condition), self._reference(condition),
                                              kw.get("reference_dir"), kw.get("fits_atol"))
        record.extra["output_verdict"] = verdict
        return ok, hashes

    def verify(self, condition: Condition, workdir: Path, record: RunRecord) -> tuple[bool, dict]:
        """The runner's final check (parent process, after ``run_one``). With ``cleanup_work`` a verified run's work dir
        is deleted here, the last use of the outputs, and only if ``prepare_workdir`` created it (marker file)."""
        ok, hashes = self._verify(condition, workdir, record)
        work = Path(workdir) / "work"
        if ok and self.cleanup_work and (work / WORKDIR_MARKER).is_file():
            shutil.rmtree(work)
            record.extra["work_dir_removed_after_verification"] = True
        return ok, hashes


def factory() -> MontageAdapter:
    path = os.environ.get("CAO_MONTAGE_ADAPTER_CONFIG")
    return MontageAdapter(**(json.loads(Path(path).read_text(encoding="utf-8")) if path else {}))
