"""Revival adapter: the Study 2 adapter plus (a) the mixed-DAG workload ``dyn``, (b) a controlled contention schedule that starts with the
run, (c) the revival policies. ``Study2Adapter`` is subclassed, not edited (apart from its one-line ``_build_policy`` seam).

Condition kwargs (on top of the Study 2 ones):
  ``dyn``            {"classes": [[count, side, iterations], ...], "groups": 6, "seed": 0}
  ``instances_spec`` {instance: {"order_seed": int, "contention": {"seed": int, "n_hot": 3, "burners": 2, "t0": 0.2, "phase_s": 1.0,
                      "n_phases": 2} | null}}  (an instance = a chain order AND a contention schedule; held-out ones are new seeds)
  ``binding``        rsa_combined | rsa_task_only | rsa_state_only | oracle_state | any Study 2 binding
  ``param_model`` / ``blind_model`` / ``oracle_rows`` / ``e2e_terms`` / ``calibration`` file paths (see ``build_revival_policy``).
The SAME contention schedule is started at ``on_run_start`` of EVERY policy of the instance, B4 and static rules included.
"""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

from caosched.experiment.design import Condition, RunRecord
from caosched.revival.contention import ContentionRunner, ContentionSchedule
from caosched.revival.oracle import ScheduleOracleRankGreedy
from caosched.revival.policy import ResourceStateAwareRankGreedy, decision_summary
from caosched.revival.state import StateProvider, default_cpu_fn, default_ram_fn, nvml_gpu_fn
from caosched.revival.workload import build_dyn
from caosched.study2.adapter import Study2Adapter, build_study2_policy
from caosched.study2.workload import GPU_POOL

REVIVAL_BINDINGS = ("rsa_combined", "rsa_task_only", "rsa_state_only", "oracle_state")


def load_calibration(path: str | Path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))["slowdown"]["img_denoise_256_x60"]
    return {int(k): float(v) for k, v in d.items()}


def build_revival_policy(cond: Condition, seed: int, core_of: dict[str, int] | None = None, schedule: ContentionSchedule | None = None):
    kw = cond.kwargs
    b = kw.get("binding")
    if b not in REVIVAL_BINDINGS:
        return build_study2_policy(cond, seed)
    from caosched.estimators.e2e import EndToEndTerms
    from caosched.study2.param_model import ParamModelEstimator
    from caosched.study2.policies import CachedOracle

    terms = EndToEndTerms.load(Path(kw["e2e_terms"])) if kw.get("e2e_terms") else None
    table = load_calibration(kw["calibration"]) if kw.get("calibration") else {0: 1.0, 1: 2.0, 2: 3.0}
    if b == "oracle_state":
        oest = CachedOracle.from_rows(json.loads(Path(kw["oracle_rows"]).read_text(encoding="utf-8")))
        return ScheduleOracleRankGreedy(oest, "ORACLE_STATE", schedule=schedule, core_of=core_of or {}, slowdown=table, e2e=terms,
                                        diagnostics=bool(kw.get("diagnostics", False)))
    live = b in ("rsa_combined", "rsa_state_only")
    est = ParamModelEstimator.load(Path(kw["blind_model" if b == "rsa_state_only" else "param_model"]))
    provider = StateProvider(core_of=core_of, cpu_fn=default_cpu_fn() if core_of else None, ram_fn=default_ram_fn(), gpu_fn=nvml_gpu_fn(),
                             use_residual=live, use_foreign=live, foreign_k=table.get(1, 2.0) - 1.0)
    name = {"rsa_combined": "RSA_COMBINED", "rsa_task_only": "RSA_TASK_ONLY", "rsa_state_only": "RSA_STATE_ONLY"}[b]
    return ResourceStateAwareRankGreedy(est, name, provider=provider, live_state=live, e2e=terms,
                                        decision_budget_s=float(kw.get("decision_budget_s", 0.002)),
                                        diagnostics=bool(kw.get("diagnostics", False)))


class ReviveAdapter(Study2Adapter):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._runner: ContentionRunner | None = None
        self._schedule: ContentionSchedule | None = None
        self._t0: float | None = None
        self._policy = None

    # --- workload ------------------------------------------------------------------------------------------------------

    def build_dag(self, kw: dict, gpu_stages=()):
        if kw.get("dyn"):
            d = kw["dyn"]
            key: tuple = ("dyn", tuple(map(tuple, d["classes"])), int(d.get("groups", 6)), int(d.get("seed", 0)), int(kw.get("order_seed", 0)))
            return build_dyn(d["classes"], key[2], key[3], 2.0, gpu_stages, GPU_POOL, key[4]), key
        return super().build_dag(kw, gpu_stages)

    # --- contention ----------------------------------------------------------------------------------------------------

    def _core_of(self) -> dict[str, int]:
        pools = self._config(False).pools or {}
        return {f"{name}{i}": core for name, spec in pools.items() if spec.kind == "cpu" for i, core in enumerate(spec.slots)}

    def _start_contention(self) -> float | None:
        if self._schedule is None or self._runner is None:
            return None
        self._t0 = self._runner.start(self._schedule)
        return self._t0

    def _build_policy(self, condition: Condition, kw: dict, seed: int):
        policy = build_revival_policy(dataclasses.replace(condition, kwargs={k: v for k, v in kw.items() if k != "seed"}), seed,
                                      self._core_of(), self._schedule)
        self._policy, original = policy, policy.on_run_start

        def on_run_start(dag, state, _orig=original):
            t0 = self._start_contention()  # identical for every policy: the schedule's time 0 is the start of the run
            if isinstance(policy, ScheduleOracleRankGreedy):
                policy.t0 = t0
            _orig(dag, state)

        policy.on_run_start = on_run_start  # type: ignore[method-assign]
        return policy

    def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord:
        kw = dict(condition.kwargs)
        spec = (kw.get("instances_spec") or {}).get(condition.instance)
        self._schedule, self._t0 = None, None
        if spec is not None:
            kw["order_seed"] = int(spec["order_seed"])
            c = spec.get("contention")
            if c:
                cores = list(self._config(False).pools["P"].slots)
                self._schedule = ContentionSchedule.phases(f"c{c['seed']}", cores, int(c["seed"]), int(c.get("n_hot", 3)),
                                                           int(c.get("burners", 2)), float(c.get("t0", 0.2)), float(c.get("phase_s", 1.0)),
                                                           int(c.get("n_phases", 2)))
                if self._runner is None:
                    self._runner = ContentionRunner(cores, max_burners_per_core=max(2, int(c.get("burners", 2))))
        try:
            rec = super().run_one(dataclasses.replace(condition, kwargs=kw), workdir, seed)
        finally:
            if self._runner is not None:
                self._runner.stop()
        rec.extra["contention"] = self._schedule.to_dict() if self._schedule else None
        rec.extra["contention_t0"] = self._t0
        if isinstance(self._policy, ResourceStateAwareRankGreedy):
            rec.extra["revival"] = decision_summary(self._policy)
        return rec

    def close(self) -> None:
        if self._runner is not None:
            self._runner.close()
            self._runner = None
        super().close()


def factory() -> ReviveAdapter:
    path = os.environ.get("CAO_REVIVAL_ADAPTER_CONFIG")
    return ReviveAdapter(**(json.loads(Path(path).read_text(encoding="utf-8")) if path else {}))
