"""Emulated-remote-pool adapter: ONE tiled image-pipeline instance on pools P, E and an emulated remote pool 'R'.

Evidence label of every run: **emulation**. 'R' is a real node process (``caosched.remote.node``) on one logical
processor of THIS machine, reached through a real loopback TCP connection, with a configured delay added in front of
every message by the link shim (``caosched.remote.link``: latency + per-message + bytes / bandwidth). The adapter stamps
``RunRecord.extra['evidence_label'] = 'emulation'`` and the link parameters on every run. Not emulated / not measured:
real network behaviour (loss, queues, congestion), a foreign clock, authentication beyond the token handshake, jitter
(the shim has none: a nonzero ``jitter_ms`` is rejected rather than silently ignored).

Plug-in contract: ``caosched.experiment.design`` (as ``gpu_adapter``, whose class is the base here: pool close, picklability,
reference cache and output verification are inherited, not copied). Pools are the same for EVERY condition of a session: P,
E without the node's core, and R on that core; a 'no remote' condition simply makes R ineligible, so remote and control
conditions differ only in whether tasks may use R (the idle node core is not given back to E).

Condition kwargs: ``tile`` (default 256), ``n_images`` (perfect square, default 16), ``seed``, ``denoise_iterations``,
``remote`` (bool: the stages in ``remote_stages`` may run on R; default False), ``remote_stages`` (default denoise, edges,
features: the stages whose input/output sizes are known to ``stage_payload_bytes``), ``link`` ({name, latency_ms (one-way,
per message), bandwidth_mbps (None = unshaped), per_message_ms, jitter_ms (must be 0)}), ``profile`` (E1 profile with P, E and R
rows AND ``link_calibration``: written by ``scripts/calibrate_link.py``), ``est_cfg`` / ``model_path`` / ``policy_cfg`` (as
montage), ``keep_artifacts``. Policies: B0_P_only, B4_greedy_eligible (remote: priority P, E, R), EFT_* (remote: with
``FileTransferModel`` = configured link both ways + the measured socket cost from the profile), random, ...
Constructor: ``max_p_slots`` (default 2: scarce fast cores, the only regime where an extra worker can matter), ``node_core``
(default: the last E slot). ``factory()`` reads constructor settings from the JSON file named by CAO_REMOTE_ADAPTER_CONFIG.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import shutil
from pathlib import Path

from caosched.core.coordinator import Coordinator, RunTimeoutError, TaskTimeoutError, pin_coordinator_to_reserved_core
from caosched.core.event_log import EventLogger
from caosched.core.runtime_config import RuntimeConfig
from caosched.core.worker_pool import RemoteSlot, WorkerPool
from caosched.apps.image_pipeline import build_image_pipeline, run_reference
from caosched.experiment.design import Condition, RunRecord
from caosched.experiment.gpu_adapter import GpuAdapter
from caosched.experiment.montage_adapter import build_policy, estimator_spec
from caosched.remote.link import LinkConfig
from caosched.schedulers import eft_factories, rank_eft_factories
from caosched.schedulers.rank_eft import FileTransferModel
from caosched.schedulers.simple import GreedyEligibleScheduler

REMOTE_POOL = "R"
DEFAULT_REMOTE_STAGES = ("img_denoise", "img_edges", "img_features")
EVIDENCE_LABEL = "emulation"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def link_from_kwargs(link: dict | None) -> LinkConfig:
    """``{name, latency_ms, bandwidth_mbps, per_message_ms, jitter_ms}`` -> shim ``LinkConfig`` (bytes/s = Mbit/s * 1e6 / 8)."""
    link = link or {}
    if link.get("jitter_ms"):
        raise ValueError("jitter_ms != 0 is not supported: the link shim has no jitter (do not claim it)")
    bw = link.get("bandwidth_mbps")
    return LinkConfig(link.get("name", "none"), latency_s=link.get("latency_ms", 0.0) / 1e3,
                      bandwidth_Bps=None if bw is None else bw * 1e6 / 8, per_message_s=link.get("per_message_ms", 0.0) / 1e3)


class RemoteAdapter(GpuAdapter):
    evidence_label_override = EVIDENCE_LABEL  # the runner stamps session.json / run manifests with this

    def __init__(self, runtime_config: RuntimeConfig | None = None, timeout_s: float = 600.0,
                 run_timeout_s: float | None = None, max_p_slots: int | None = 2, node_core: int | None = None,
                 remote_host: str | None = None, remote_port: int | None = None):
        super().__init__(runtime_config, timeout_s, run_timeout_s)
        self.max_p_slots, self.node_core = max_p_slots, node_core
        if (remote_host is None) != (remote_port is None):
            raise ValueError("remote_host and remote_port must be given together")
        # External node (e.g. a Raspberry Pi): already running, reached over the real network. No local core is given to it.
        self.remote_host, self.remote_port = remote_host, remote_port
        # a loopback address is a local rehearsal, never 'real'; the runner reads this instance attribute
        self.evidence_label_override = "real" if remote_host and remote_host not in LOOPBACK_HOSTS else EVIDENCE_LABEL

    def _layout(self) -> tuple[RuntimeConfig, int | None]:
        """(local pools P and E-without-the-node-core, node core); with an external node all E cores stay local and node is None."""
        if self.runtime_config is None:
            self.runtime_config = RuntimeConfig.from_topology(max_p_slots=self.max_p_slots)
        base = self.runtime_config
        if self.remote_host is not None:
            return base, None
        node = self.node_core if self.node_core is not None else base.e_core_slots[-1]
        if node not in base.e_core_slots:
            raise ValueError(f"node_core {node} must be one of the E slots {base.e_core_slots}")
        return RuntimeConfig(base.p_core_slots, tuple(c for c in base.e_core_slots if c != node), base.coordinator_core), node

    def _get_pool(self, link: LinkConfig) -> WorkerPool:  # type: ignore[override]
        if self._pool is not None and (self._pool.dead_workers() or self._pool.idle_workers() != self._pool.worker_ids()):
            self.close()
        if self._pool is None:
            cfg, node = self._layout()
            if self.remote_host is not None:  # connect to the running node; its clock is foreign (proxy-side timestamps)
                slot = RemoteSlot(link, proxy_core=cfg.coordinator_core, host=self.remote_host, port=self.remote_port,
                                  pool=REMOTE_POOL, same_clock=False)
            else:
                slot = RemoteSlot(link, node_core=node, proxy_core=cfg.coordinator_core)
            self._pool = WorkerPool(list(cfg.p_core_slots), list(cfg.e_core_slots), warmup=False, strict_affinity=True,
                                    remote_slots=[slot])
        else:
            self._pool.set_link(f"{REMOTE_POOL}0", link)  # applied by the proxy before its next task
        return self._pool

    def build_dag(self, kw: dict, stages=()):  # type: ignore[override]
        tile, n = int(kw.get("tile", 256)), int(kw.get("n_images", 16))
        grid = math.isqrt(n)
        if grid * grid != n:
            raise ValueError(f"n_images must be a perfect square, got {n}")
        key = (tile, grid, int(kw.get("seed", 0)), int(kw.get("denoise_iterations", 1)))
        return build_image_pipeline(tile * grid, tile * grid, grid, key[2], denoise_iterations=key[3],
                                    remote_stages={s: [REMOTE_POOL] for s in stages}), key

    def _policy(self, cond: Condition, link: LinkConfig, seed: int):
        kw, remote = cond.kwargs, bool(cond.kwargs.get("remote"))
        plain = dataclasses.replace(cond, kwargs={k: v for k, v in kw.items() if k != "seed"})  # app seed != random-policy seed
        if not remote:
            return build_policy(plain, seed), None
        if cond.policy in ("B4", "B4_greedy_eligible"):
            return GreedyEligibleScheduler(priority=["P", "E", REMOTE_POOL], name="B4_greedy_eligible_R"), None
        if not cond.policy.startswith("EFT_"):
            raise ValueError(f"{cond.name}: remote supports B4 and EFT_* policies, got {cond.policy!r}")
        profile = Path(kw["profile"])
        cal = json.loads(profile.read_text(encoding="utf-8")).get("link_calibration")
        if not cal:
            raise ValueError(f"{profile} has no link_calibration: run scripts/calibrate_link.py")
        tm = FileTransferModel({REMOTE_POOL: link}, socket_a_s=cal["socket_a_s"],
                               socket_b_s_per_byte=cal["socket_b_s_per_byte"], calibration_source=str(profile))
        make = rank_eft_factories if cond.policy.endswith("_rank") else eft_factories
        (factory_,) = make([estimator_spec(cond.policy, cond.estimator)], profile, est_cfg=kw.get("est_cfg"),
                           model_path=Path(kw["model_path"]) if kw.get("model_path") else None, transfer=tm).values()
        return factory_(), tm.describe()

    def run_one(self, condition: Condition, workdir: Path, seed: int) -> RunRecord:
        workdir, kw = Path(workdir), condition.kwargs
        remote = bool(kw.get("remote"))
        stages = tuple(kw.get("remote_stages") or DEFAULT_REMOTE_STAGES) if remote else ()
        link = link_from_kwargs(kw.get("link"))
        if remote and self.evidence_label_override == "real" and link.shim_delay(10**9) != 0.0:
            raise ValueError("a delay shim on top of a real network would count the link twice: use link {'name': 'real'} "
                             "(no latency/bandwidth) for a non-loopback node")
        dag, key = self.build_dag(kw, stages)
        if key not in self._ref:
            self._ref[key] = run_reference(dag)
        ref, art = self._ref[key], workdir / "artifacts"
        policy, transfer_model = self._policy(condition, link, seed)
        run_id, log_name = workdir.name, f"{workdir.name}.jsonl"
        meta = {"experiment_id": workdir.parent.parent.name, "workflow_instance": condition.instance,
                "condition": condition.name, "policy": condition.policy, "estimator": condition.estimator, "seed": seed,
                "link": link.to_dict() if remote else None}
        cfg, node = self._layout()
        extra = {"evidence_label": self.evidence_label_override, "n_tasks": len(dag), "policy": policy.name, "tile": key[0],
                 "grid": key[1], "n_images": key[1] ** 2, "denoise_iterations": key[3], "remote": remote,
                 "remote_stages": list(stages), "link": link.to_dict(), "link_kwargs": kw.get("link"),
                 "link_active": remote, "node_core": node, "max_p_slots": self.max_p_slots,
                 "pools": {"P": list(cfg.p_core_slots), "E": list(cfg.e_core_slots), REMOTE_POOL: [] if node is None else [node]},
                 "transfer_model": transfer_model, "cuda_tasks": []}
        if self.remote_host is not None:
            extra.update(remote_host=self.remote_host, remote_port=self.remote_port,
                         emulation_note=("external node, link = the real network (shim zero), foreign clock" if self.evidence_label_override == "real"
                                         else "external node on a LOOPBACK address: a local rehearsal, not a network measurement"))
        else:
            extra["emulation_note"] = ("node = real process on a core of this machine behind a loopback socket with a delay shim; "
                                       "no real network, same clock, token handshake only")
        status, error, summary = "ok", None, None
        try:
            pool = self._get_pool(link)
            pin_coordinator_to_reserved_core(cfg)
            with EventLogger(run_id, output_dir=workdir) as log:
                summary = Coordinator(dag, pool, policy, log, run_metadata=meta, artifact_dir=art).run(run_timeout=self.run_timeout_s)
        except Exception as exc:  # noqa: BLE001 - a failed run is data; the runner flags and keeps it
            status = "timeout" if isinstance(exc, (TaskTimeoutError, RunTimeoutError)) else "failed"
            error = f"{type(exc).__name__}: {exc}"
            self.close()
        if summary is not None:
            extra.update(decision_time_total_s=summary.scheduling_time_seconds, makespan_seconds=summary.makespan_seconds,
                         n_completed=summary.n_completed, tasks_per_pool=summary.tasks_per_pool,
                         task_placement={t.task_id: [t.assigned_pool, t.assigned_worker] for t in dag.tasks.values()},
                         remote_tasks=sorted(t.task_id for t in dag.tasks.values() if t.assigned_pool == REMOTE_POOL))
        rec = RunRecord(status=status, event_log=log_name if (workdir / log_name).is_file() else None, error=error,
                        input_hashes={"source": hashlib.sha256(ref["source"]).hexdigest()}, extra=extra)
        if status == "ok":
            try:
                rec.output_ok, rec.output_hashes = self._verify(dag, art, ref, extra)  # all-CPU rule: exact, else numeric
            except Exception as exc:  # noqa: BLE001 - keep the run, unverified
                rec.output_ok, rec.error = False, f"verify raised {type(exc).__name__}: {exc}"
        if not kw.get("keep_artifacts"):
            shutil.rmtree(art, ignore_errors=True)
        return rec


def factory() -> RemoteAdapter:
    path = os.environ.get("CAO_REMOTE_ADAPTER_CONFIG")
    return RemoteAdapter(**(json.loads(Path(path).read_text(encoding="utf-8")) if path else {}))
