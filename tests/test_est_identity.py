"""Estimator identity of extcmd tasks (Task.est_workload / est_size / est_bytes): two transformations must not look
identical to E0/E1/E3/CatBoost/MLP, and the offline dataset rows must carry the same identity the estimators saw online."""
import random
import sys

import numpy as np
import pytest

from caosched.core.coordinator import Coordinator
from caosched.core.dag import DAG
from caosched.core.event_log import EventLogger, read_events
from caosched.core.extcmd import make_extcmd_task
from caosched.core.task import Task
from caosched.core.worker_pool import WorkerPool
from caosched.dataset.events import rows_from_events
from caosched.estimators import (CatBoostEstimator, ConstantProfileEstimator, EstimateContext, ExecutionTimeEstimator,
                                 MlpEstimator, MovingHistoryEstimator, StaticProfileEstimator)
from caosched.estimators.base import TaskSpec
from caosched.estimators.tabular import encode
from caosched.schedulers.eft import EarliestFinishTimeScheduler

COPY = "import sys; open(sys.argv[-1],'w').write(''.join(open(f).read() for f in sys.argv[1:-1]) + 'x')"
TABLE = {("mProject", 1, "P"): 2.0, ("mProject", 1, "E"): 3.0, ("mDiffFit", 1, "P"): 0.5, ("mDiffFit", 1, "E"): 0.8}


def _task(tmp_path, tid, name, nbytes=None, deps=(), src=None):
    """Reads ``src`` (an upstream output) or, by default, a raw ``<tid>.in`` of ``nbytes``; writes ``<tid>.out``."""
    if src is None:
        src = f"{tid}.in"
        (tmp_path / src).write_bytes(b"x" * nbytes)
    return make_extcmd_task(tid, [sys.executable, "-c", COPY, src, f"{tid}.out"], tmp_path, [src], [f"{tid}.out"],
                            deps, name=name)


def test_properties_extcmd_and_plain(tmp_path):
    t = _task(tmp_path, "a", "mProject", 1000)
    assert (t.est_workload, t.est_size, t.est_bytes) == ("mProject", 1, 1000)
    t.input_bytes = 0
    assert t.est_bytes == 1                                   # log(est_bytes) must be defined
    m = Task("m", "matmul", 64)
    assert (m.est_workload, m.est_size, m.est_bytes) == ("matmul", 64, 64)
    s = TaskSpec("s", "matmul", 64)
    assert (s.est_workload, s.est_size, s.est_bytes) == ("matmul", 64, 64)


def test_e0_e1_e3_tell_transformations_apart(tmp_path):
    a, b = _task(tmp_path, "a", "mProject", 10), _task(tmp_path, "b", "mDiffFit", 10)
    e1 = StaticProfileEstimator(TABLE)
    assert (e1.estimate(a, "P"), e1.estimate(b, "P")) == (2.0, 0.5)
    e0 = ConstantProfileEstimator({("mProject", "P"): 2.0, ("mDiffFit", "P"): 0.5})
    assert (e0.estimate(a, "P"), e0.estimate(b, "P")) == (2.0, 0.5)
    e3 = MovingHistoryEstimator(e1, window=2)
    e3.observe(a, "P", 9.0)
    assert (e3.estimate(a, "P"), e3.estimate(b, "P")) == (9.0, 0.5) and e3.n_observations(b, "P") == 0


def _rows(n, seed):
    r = random.Random(seed)
    out = []
    for i in range(n):
        wl, pool = r.choice(["mProject", "mDiffFit"]), r.choice(["P", "E"])
        nb = r.choice([1_000, 50_000, 2_000_000])
        ctx = EstimateContext.build(r.randint(0, 2), r.randint(0, 3), [r.choice(["mProject", "mDiffFit"])], 1.0)
        k = TABLE[(wl, 1, pool)] * (1 + nb / 4e6) * (1 + 0.1 * ctx.busy_E)
        out.append({"workload": wl, "size": 1, "bytes": nb, "pool": pool, "kernel_s": k, "ctx": ctx})
    return out


@pytest.mark.parametrize("cls,params", [(CatBoostEstimator, {"iterations": 10, "depth": 3, "learning_rate": 0.3}),
                                        (MlpEstimator, {"hidden": [8], "epochs": 3, "lr": 0.01, "weight_decay": 0.0, "batch_size": 32})])
def test_learned_models_see_transformation_and_bytes(tmp_path, cls, params):
    base = StaticProfileEstimator(TABLE)
    m = cls.fit(_rows(80, 1), base, params, seed=0)
    a, b = _task(tmp_path, "a", "mProject", 50_000), _task(tmp_path, "b", "mDiffFit", 50_000)
    c = _task(tmp_path, "c", "mProject", 2_000_000)
    ctx = EstimateContext.build(1, 1, ["mProject"], 1.0)
    enc = lambda t: encode(m.spec, t.est_workload, t.est_bytes, "P", base.lookup(t.est_workload, t.est_size, "P"), ctx)
    assert not np.array_equal(enc(a), enc(b)) and not np.array_equal(enc(a), enc(c))   # transformation, bytes, base time
    assert m.estimate(a, "P", ctx) != m.estimate(b, "P", ctx)
    # online (Task) == offline (row) input
    row = {"workload": "mProject", "size": 1, "bytes": 2_000_000, "pool": "P", "ctx": ctx}
    assert m.estimate(c, "P", ctx) == pytest.approx(m.estimate_many([row])[0])


class _Spy(ExecutionTimeEstimator):
    name = "spy"

    def __init__(self):
        self.seen = {}

    def estimate(self, task, pool, ctx=None):
        return TABLE[(task.est_workload, task.est_size, pool)]

    def observe(self, task, pool, kernel_seconds, ctx=None):
        self.seen[task.task_id] = (task.est_workload, task.est_size, task.est_bytes)


def test_parity_extcmd_run_rows_equal_online_identity(tmp_path):
    a = _task(tmp_path, "a", "mProject", 700)
    # b and c consume their producers' outputs: their input size is known only when they become ready
    b = _task(tmp_path, "b", "mDiffFit", deps=("a",), src="a.out")
    c = _task(tmp_path, "c", "mProject", deps=("b",), src="b.out")
    spy = _Spy()
    with WorkerPool(p_core_slots=[0], e_core_slots=[1], warmup=False) as pool, EventLogger("par", output_dir=tmp_path) as log:
        s = Coordinator(DAG({"a": a, "b": b, "c": c}), pool, EarliestFinishTimeScheduler(spy, "spy"), log).run(run_timeout=120)
    assert s.status == "completed"
    rows = {r["task_id"]: r for r in rows_from_events(read_events(tmp_path / "par.jsonl"), "decision")}
    assert set(rows) == {"a", "b", "c"}
    for tid, r in rows.items():
        assert (r["workload"], r["size"], r["bytes"]) == spy.seen[tid] and r["is_extcmd"]
    assert rows["a"]["bytes"] == 700 and rows["b"]["bytes"] == 701 and rows["c"]["bytes"] == 702   # each stage appends 'x'
    assert rows["b"]["input_bytes"] == 701 and rows["b"]["output_bytes"] == 702
