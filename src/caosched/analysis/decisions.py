"""Per-decision records and one-step hindsight regret, from event logs alone.

Task x becomes READY at t_r and is bound to worker c at coordinator time
t_b >= t_r. Definitions:

    free_w(t)  = latest *actual* completion time (worker-side clock) of the
                 tasks bound to w at time t (executing or locally queued, not
                 yet completed as seen by the coordinator); t if none
    exec_h(p)  = E5 replay-oracle kernel time of x on pool p: median of the
                 same task's kernel time on that pool in OTHER logged runs

Three separate quantities are reported, because no single one is fair to
every policy type:

  placement regret (PRIMARY, ``regret_s``) -- judged at the binding moment:
      F_b(w) = (max(t_b, free_w(t_b)) - t_b) + exec_h(pool(w))
      regret = F_b(c) - min_w F_b(w)          (>= 0; optimal iff 0)
    "Given that the policy bound x now, did it pick the worker that would
    have finished x first?"
  bind delay (``bind_delay_s`` = t_b - t_r) -- time x waited unbound in the
    global ready queue (late-binding policies wait there; early-binding
    policies bind immediately and wait in a worker's local queue instead,
    which placement regret already sees).
  ready-time regret (SECONDARY, ``regret_ready_s``) -- alternatives "bind x
    alone right when it became ready" vs what happened:
      F_c = (max(t_b, free_c(t_b)) - t_r) + exec_h(pool(c))
      regret_ready = F_c - min(F_c, min_w [(max(t_r, free_w(t_r)) - t_r) + exec_h(pool(w))])
    CAVEAT: it ignores contention among tasks that became ready together
    (with 60 tasks ready at t=0 and 9 workers, every policy -- the oracle
    included -- scores ~0% optimal), so it is NOT used to rank policies.

History of this definition (both found from real runs, not assumed): a
bind-time-only regret hid waiting (B0_P_only looked 100% optimal); a
ready-time-only regret charged unavoidable contention as regret. Hence the
split. Makespan remains the end-to-end measure that combines both.

End-to-end variant (project decision 2026-10-03, ablation): with
``oracle_e2e`` (an E5 table built on each task's worker span = prepare +
kernel instead of kernel only) the same placement regret is also reported as
``regret_e2e_s`` / ``optimal_e2e``, so kernel-only and end-to-end results are
directly comparable on the same decisions.

All are ONE-STEP (myopic) hindsight quantities: they do not simulate how
later decisions would have changed (not observable), and exec_h is a
replay-oracle stand-in for the unobservable counterfactual kernel time. It does not simulate how later decisions would have
changed (that counterfactual is not observable), and exec_h is a
replay-oracle stand-in for the unobservable counterfactual kernel time
(kernel-only, like every estimator in this project). Workers whose pool has
no oracle observation for x are left out of the candidate set (counted).

Works for every policy: EFT-family decisions also carry the predicted
wait / exec / finish of each candidate (``decision`` payload), from which
the prediction margin (second-best minus best predicted finish) is taken.
"""
from __future__ import annotations

from caosched.estimators.base import TaskSpec


def decision_rows(events: list[dict], oracle, oracle_e2e=None) -> list[dict]:
    """``oracle``: ReplayOracleEstimator on kernel time (exclude this run
    before calling); ``oracle_e2e`` (optional): the same on worker span."""
    start = next(e for e in events if e["event"] == "run_started")
    specs = start["tasks"]
    pools: dict[str, str] = {e["worker_id"]: e["pool"] for e in events if e["event"] == "worker_ready"}
    completed = {e["task_id"]: e for e in events if e["event"] == "task_completed"}
    ready = {e["task_id"]: e for e in events if e["event"] == "task_ready"}
    dispatched = [e for e in events if e["event"] == "task_dispatched"]
    if not pools:  # fall back to pools seen in dispatch events
        pools = {e["worker_id"]: e["pool"] for e in dispatched}

    def free_at(t: float, seq: int) -> dict[str, float]:
        free = {w: t for w in pools}
        for prev in dispatched:
            if prev["seq"] >= seq:
                break
            c = completed.get(prev["task_id"])
            if c is None or c["seq"] > seq:  # still bound to its worker at that moment
                end = c["t_completed"] if c is not None else float("inf")
                free[prev["worker_id"]] = max(free[prev["worker_id"]], end)
        return free

    rows = []
    for d in dispatched:
        t_b, x, chosen = d["t"], d["task_id"], d["worker_id"]
        r = ready.get(x)
        t_r, seq_r = (r["t"], r["seq"]) if r is not None else (t_b, d["seq"])
        spec = specs[x]
        task = TaskSpec(x, spec["workload"], int(spec["size"]), int(spec["seed"]))
        free_r, free_b = free_at(t_r, seq_r), free_at(t_b, d["seq"])
        exec_h: dict[str, float] = {}
        for p in set(pools.values()):
            try:
                exec_h[p] = oracle.estimate(task, p)
            except KeyError:
                pass
        F_r = {w: (max(t_r, free_r[w]) - t_r) + exec_h[pools[w]] for w in pools if pools[w] in exec_h}
        F = {w: (max(t_b, free_b[w]) - t_b) + exec_h[pools[w]] for w in pools if pools[w] in exec_h}
        row = {
            "run_id": start["run_id"], "policy": start["scheduler"], "task_id": x,
            "workload": task.workload, "size": task.size, "chosen_worker": chosen, "chosen_pool": d["pool"],
            "actual_kernel_s": completed[x]["wall_time_seconds"] if x in completed else None,
            "bind_delay_s": t_b - t_r, "n_candidates": len(F), "n_workers": len(pools),
        }
        dec = d.get("decision")
        if dec:
            cand = dec["candidates"]
            fin = sorted(v["finish"] for v in cand.values())
            ch = cand[chosen]
            row.update(pred_exec=ch["exec"], pred_wait=ch["wait"], pred_finish=ch["finish"],
                       pred_margin=(fin[1] - fin[0]) if len(fin) > 1 else None)
        if F and chosen in F:
            best = min(F, key=F.get)
            row.update(hind_best_worker=best, hind_best_pool=pools[best], hind_best_finish=F[best],
                       hind_chosen_finish=F[chosen], regret_s=F[chosen] - F[best],
                       regret_rel=(F[chosen] - F[best]) / F[best], optimal=F[chosen] <= F[best] + 1e-12)
            f_c = (max(t_b, free_b[chosen]) - t_r) + exec_h[pools[chosen]]
            row["regret_ready_s"] = f_c - min(f_c, min(F_r.values()))
        if oracle_e2e is not None:
            span_h: dict[str, float] = {}
            for p in set(pools.values()):
                try:
                    span_h[p] = oracle_e2e.estimate(task, p)
                except KeyError:
                    pass
            Fe = {w: (max(t_b, free_b[w]) - t_b) + span_h[pools[w]] for w in pools if pools[w] in span_h}
            if Fe and chosen in Fe:
                be = min(Fe, key=Fe.get)
                row.update(regret_e2e_s=Fe[chosen] - Fe[be], optimal_e2e=Fe[chosen] <= Fe[be] + 1e-12)
        rows.append(row)
    return rows
