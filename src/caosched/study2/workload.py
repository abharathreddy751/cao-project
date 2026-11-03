"""Study 2 workload: a batch of ``k`` independent image-analysis chains built from the existing stage functions.

    source_i -> denoise_i -> edges_i -> features_i      (i = 0 .. k-1)       aggregate <- features_0 .. features_{k-1}

Why this shape (docs/research_redesign/EVALUATION_PROTOCOL_study2.md): the stage 5 workloads have one serial stage that
dominates the makespan (Montage ``mProject``; the pipeline's ``img_source`` on a 4096 px scene), so no placement rule has
room to win. Here every chain is independent and small, so the makespan is set by how well the P cores, E cores and the
single CUDA worker are shared. Stage speeds are REAL and come from the measured profile (``scripts/study2_profile.py``);
nothing is assumed: ``img_edges`` and ``img_features`` are several times faster on the GPU, ``img_denoise`` is about as fast
on a P core as on the GPU, and the sources have no CUDA variant.

``gpu_stages``: stage types that may also run on pool ``gpu_pool`` (the caller passes only stages whose CUDA variant passed
the recorded spike at this tile size); every other task is eligible for P and E only (uniform eligibility, AD-5).
"""
from __future__ import annotations

import random

from caosched.core.dag import DAG
from caosched.core.task import Task

LOCAL_POOLS = ("P", "E")
GPU_POOL = "G"


def build_batch(k: int = 64, side: int = 512, seed: int = 0, radius: float = 2.0, iterations: int = 8,
                gpu_stages=(), gpu_pool: str = GPU_POOL) -> DAG:
    if k < 1 or side < 8 or iterations < 1:
        raise ValueError(f"need k >= 1, side >= 8, iterations >= 1 (got {k}, {side}, {iterations})")
    px, gpu_stages = side * side, set(gpu_stages)

    def task(tid, stage, size, params, deps=()):
        pools = LOCAL_POOLS + ((gpu_pool,) if stage in gpu_stages else ())
        return Task(task_id=tid, workload=stage, size=size, seed=seed, dependencies=tuple(deps), params=params,
                    eligible_pools=pools)

    tasks = []
    for i in range(k):
        tasks += [task(f"source_{i}", "img_source", px, {"width": side, "height": side, "seed": seed + i}),
                  task(f"denoise_{i}", "img_denoise", px, {"radius": radius, "iterations": int(iterations)}, [f"source_{i}"]),
                  task(f"edges_{i}", "img_edges", px, {}, [f"denoise_{i}"]),
                  task(f"features_{i}", "img_features", px, {}, [f"edges_{i}"])]
    tasks.append(task("aggregate", "img_aggregate", k, {}, [f"features_{i}" for i in range(k)]))
    return DAG({t.task_id: t for t in tasks})


def build_mixed(small, big, seed: int = 0, radius: float = 2.0, iterations: int = 8, gpu_stages=(),
                gpu_pool: str = GPU_POOL, order_seed: int = 0) -> DAG:
    """Heavy-tailed batch (protocol section 17): ``small`` = [count, side], ``big`` = [count, side] independent chains of the same
    four stages as ``build_batch``, at two image sizes (a 1024 px chain is 16 times the pixels of a 256 px chain). The order of
    the chains (the order in which a FIFO rule sees them) is a fixed shuffle of ``order_seed``; ``aggregate`` size = chain count."""
    sides = [int(small[1])] * int(small[0]) + [int(big[1])] * int(big[0])
    if not sides or min(sides) < 8 or iterations < 1:
        raise ValueError(f"need chains with side >= 8 and iterations >= 1 (got {sides[:3]}..., {iterations})")
    random.Random(order_seed).shuffle(sides)
    gpu_stages = set(gpu_stages)

    def task(tid, stage, size, params, deps=()):
        pools = LOCAL_POOLS + ((gpu_pool,) if stage in gpu_stages else ())
        return Task(task_id=tid, workload=stage, size=size, seed=seed, dependencies=tuple(deps), params=params,
                    eligible_pools=pools)

    tasks = []
    for i, side in enumerate(sides):
        px = side * side
        tasks += [task(f"source_{i}", "img_source", px, {"width": side, "height": side, "seed": seed + i}),
                  task(f"denoise_{i}", "img_denoise", px, {"radius": radius, "iterations": int(iterations)}, [f"source_{i}"]),
                  task(f"edges_{i}", "img_edges", px, {}, [f"denoise_{i}"]),
                  task(f"features_{i}", "img_features", px, {}, [f"edges_{i}"])]
    tasks.append(task("aggregate", "img_aggregate", len(sides), {}, [f"features_{i}" for i in range(len(sides))]))
    return DAG({t.task_id: t for t in tasks})


def build_iters(small, big, side: int = 512, seed: int = 0, radius: float = 2.0, gpu_stages=(), gpu_pool: str = GPU_POOL,
                order_seed: int = 0) -> DAG:
    """Hidden-cost batch (protocol section 18): ``small`` = [count, iterations], ``big`` = [count, iterations] independent chains of
    the same four stages at ONE image size; only the number of denoise iterations differs (runtime of ``img_denoise`` is linear in
    it, but the task ``size`` in pixels is the same for every chain, so a table keyed by size cannot see the cost). Chain order is a
    fixed shuffle of ``order_seed``; ``aggregate`` size = chain count."""
    its = [int(small[1])] * int(small[0]) + [int(big[1])] * int(big[0])
    if not its or side < 8 or min(its) < 1:
        raise ValueError(f"need chains with iterations >= 1 and side >= 8 (got {its[:3]}..., {side})")
    random.Random(order_seed).shuffle(its)
    gpu_stages, px = set(gpu_stages), side * side

    def task(tid, stage, size, params, deps=(), tseed=0):
        pools = LOCAL_POOLS + ((gpu_pool,) if stage in gpu_stages else ())
        return Task(task_id=tid, workload=stage, size=size, seed=tseed, dependencies=tuple(deps), params=params,
                    eligible_pools=pools)

    tasks = []
    for i, n in enumerate(its):
        # Task.seed = the chain's iterations: the replay oracle keys a task by (id, seed, stage, size, pool), and the same task id
        # carries a different cost in a different chain order, so the key must separate them (no stage reads Task.seed).
        tasks += [task(f"source_{i}", "img_source", px, {"width": side, "height": side, "seed": seed + i}, tseed=n),
                  task(f"denoise_{i}", "img_denoise", px, {"radius": radius, "iterations": n}, [f"source_{i}"], tseed=n),
                  task(f"edges_{i}", "img_edges", px, {}, [f"denoise_{i}"], tseed=n),
                  task(f"features_{i}", "img_features", px, {}, [f"edges_{i}"], tseed=n)]
    tasks.append(task("aggregate", "img_aggregate", len(its), {}, [f"features_{i}" for i in range(len(its))]))
    return DAG({t.task_id: t for t in tasks})


def build_classes(classes, seed: int = 0, radius: float = 2.0, gpu_stages=(), gpu_pool: str = GPU_POOL, order_seed: int = 0) -> DAG:
    """Two-factor hidden-cost batch (protocol section 30): ``classes`` = [[count, side, iterations], ...] independent chains of the same four
    stages. A chain's cost depends on BOTH its image side (source, edges, features, denoise per iteration all scale with pixels) and its
    denoise ``iterations``, roughly as pixels x iterations for the denoise stage. A rule that sorts by one factor alone (size, or
    repeats) misorders the classes where the other factor dominates; ``aggregate`` size = chain count; chain order = fixed shuffle."""
    chains = [(int(side), int(n)) for count, side, n in classes for _ in range(int(count))]
    if not chains or min(c[0] for c in chains) < 8 or min(c[1] for c in chains) < 1:
        raise ValueError(f"need chains with side >= 8 and iterations >= 1 (got {chains[:3]}...)")
    random.Random(order_seed).shuffle(chains)
    gpu_stages = set(gpu_stages)

    def task(tid, stage, size, params, deps=()):
        pools = LOCAL_POOLS + ((gpu_pool,) if stage in gpu_stages else ())
        return Task(task_id=tid, workload=stage, size=size, seed=0, dependencies=tuple(deps), params=params, eligible_pools=pools)

    tasks = []
    for i, (side, n) in enumerate(chains):
        px = side * side
        tasks += [task(f"source_{i}", "img_source", px, {"width": side, "height": side, "seed": seed + i}),
                  task(f"denoise_{i}", "img_denoise", px, {"radius": radius, "iterations": n}, [f"source_{i}"]),
                  task(f"edges_{i}", "img_edges", px, {}, [f"denoise_{i}"]),
                  task(f"features_{i}", "img_features", px, {}, [f"edges_{i}"])]
    tasks.append(task("aggregate", "img_aggregate", len(chains), {}, [f"features_{i}" for i in range(len(chains))]))
    return DAG({t.task_id: t for t in tasks})
