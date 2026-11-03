"""Revival workload: a mixed DAG of image chains with a two-level fan-in (dynamic-contention study).

    source_i -> denoise_i -> edges_i -> features_i          (chain i, its own (image side, denoise iterations))
    gagg_g  <- features_i for the chains of group g          (img_aggregate, a partial result per group)
    aggregate <- gagg_0 .. gagg_{G-1}                        (img_aggregate, the final result)

The stages are the existing ones (``apps/stages.py``); the chains are those of ``study2.workload.build_classes``; what is new is the
group level (a depth-6 DAG with a barrier per group instead of one flat fan-in), so that the order in which groups finish matters.
Chain i belongs to group ``i % n_groups`` after a fixed shuffle (``order_seed``).
"""
from __future__ import annotations

import random

from caosched.core.dag import DAG
from caosched.core.task import Task
from caosched.study2.workload import GPU_POOL, LOCAL_POOLS


def build_dyn(classes, n_groups: int = 6, seed: int = 0, radius: float = 2.0, gpu_stages=(), gpu_pool: str = GPU_POOL,
              order_seed: int = 0) -> DAG:
    chains = [(int(side), int(n)) for count, side, n in classes for _ in range(int(count))]
    if not chains or n_groups < 1 or n_groups > len(chains) or min(c[0] for c in chains) < 8 or min(c[1] for c in chains) < 1:
        raise ValueError(f"need chains with side >= 8, iterations >= 1 and 1 <= n_groups <= chains, equal groups (got {len(chains)} chains, {n_groups} groups)")
    if len(chains) % n_groups:  # img_aggregate emits 2 x 35 + (number of inputs) values: unequal groups cannot be fanned in again
        raise ValueError(f"{len(chains)} chains cannot be split into {n_groups} equal groups")
    random.Random(order_seed).shuffle(chains)
    gpu_stages = set(gpu_stages)

    def task(tid, stage, size, params, deps=(), tseed=0):
        pools = LOCAL_POOLS + ((gpu_pool,) if stage in gpu_stages else ())
        return Task(task_id=tid, workload=stage, size=size, seed=tseed, dependencies=tuple(deps), params=params, eligible_pools=pools)

    tasks = []
    members: dict[int, list[str]] = {g: [] for g in range(n_groups)}
    for i, (side, n) in enumerate(chains):
        px = side * side
        # Task.seed = the chain's class (side, iterations): the replay oracle keys a task by (id, seed, stage, size, pool) and the same
        # task id carries a different cost in a different chain order (no stage reads Task.seed; same device as study2.workload.build_iters)
        cs = side * 10000 + n
        tasks += [task(f"source_{i}", "img_source", px, {"width": side, "height": side, "seed": seed + i}, tseed=cs),
                  task(f"denoise_{i}", "img_denoise", px, {"radius": radius, "iterations": n}, [f"source_{i}"], tseed=cs),
                  task(f"edges_{i}", "img_edges", px, {}, [f"denoise_{i}"], tseed=cs),
                  task(f"features_{i}", "img_features", px, {}, [f"edges_{i}"], tseed=cs)]
        members[i % n_groups].append(f"features_{i}")
    for g, deps in members.items():
        tasks.append(task(f"gagg_{g}", "img_aggregate", len(deps), {}, deps))
    tasks.append(task("aggregate", "img_aggregate", n_groups, {}, [f"gagg_{g}" for g in range(n_groups)]))
    return DAG({t.task_id: t for t in tasks})
