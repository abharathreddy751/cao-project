"""Leakage-safe train/test splits over dataset rows (EVALUATION_PROTOCOL section 5).

Rows are ``tasks.csv`` dicts. The unit of a split is a workflow instance, a
size, a session or a whole run (``source_log``) -- never a random row. Policies
(``spec["policy"]``):

  instance   test = ``spec["test"]`` instances, or every instance in turn
             (``"leave_one_out": true``)
  session    test = ``spec["test"]`` sessions, or every session in turn
  size       test = rows whose ``size`` is in ``spec["test"]`` (extrapolation axis)
  occupancy  train = rows with ``busy_total <= spec["threshold"]``, test = the busier rows
             (extrapolation axis)
  time       within each session, runs ordered by collection order (``run_order_key``: the
             run_started ``order_index``, then the first task start epoch, the file name only as
             the last tie-break): the first ``spec["train_fraction"]`` of runs train, later
             runs test

``folds`` returns ``[(name, train_rows, test_rows)]`` and raises if a fold is
empty on either side, if a run lands in both (every policy; size/occupancy are
row-level axes, so a run with rows on both sides raises unless
``spec["allow_straddle"]`` is true -- then the run's session state and co-runner
context are shared by train and test, report that), or if a row has an empty
``instance`` / ``session_id`` where the policy groups by it (never defaulted to train).
"""
from __future__ import annotations


def _num(x):
    return None if x in (None, "") else float(x)


def run_order_key(rows: list[dict], name: str) -> tuple:
    """Collection-order key of one run: (order_index, first task start epoch, name); a missing
    value sorts last. ``rows`` are the run's task rows, ``name`` its ``source_log``."""
    def first(k):
        v = [n for n in (_num(r.get(k)) for r in rows) if n is not None]
        return min(v) if v else float("inf")
    return first("order_index"), first("timestamp_epoch"), name


def _check(name: str, train: list, test: list, by_run: bool) -> tuple[str, list, list]:
    if not train or not test:
        raise ValueError(f"split {name!r}: empty {'train' if not train else 'test'} side")
    if by_run and {r["source_log"] for r in train} & {r["source_log"] for r in test}:
        raise ValueError(f"split {name!r}: a run is in both train and test (size/occupancy: allow_straddle=true accepts it)")
    return name, train, test


def _require(rows: list[dict], key: str, policy: str) -> None:
    bad = sum(r.get(key) in (None, "") for r in rows)
    if bad:
        raise ValueError(f"split policy {policy!r}: {bad} rows have an empty {key!r}; fix the dataset "
                         f"(they would otherwise fall silently on the train side)")


def folds(rows: list[dict], spec: dict) -> list[tuple[str, list, list]]:
    policy = spec["policy"]
    by_run = not spec.get("allow_straddle", False)  # only the row-level axes (size, occupancy) may opt out
    if policy in ("instance", "session"):
        key = "instance" if policy == "instance" else "session_id"
        _require(rows, key, policy)
        groups = sorted({r[key] for r in rows})
        held = groups if spec.get("leave_one_out") else [spec["test"]] if isinstance(spec["test"], str) else None
        if held is None:
            test_sets = [("+".join(sorted(spec["test"])), set(spec["test"]))]
        else:
            test_sets = [(h, {h}) for h in held]
        return [_check(f"{policy}:{name}", [r for r in rows if r[key] not in t], [r for r in rows if r[key] in t], True)
                for name, t in test_sets]
    if policy == "size":
        t = {int(x) for x in spec["test"]}
        return [_check("size:" + "+".join(map(str, sorted(t))), [r for r in rows if int(r["size"]) not in t],
                       [r for r in rows if int(r["size"]) in t], by_run)]
    if policy == "occupancy":
        thr = float(spec["threshold"])
        return [_check(f"occupancy:>{thr:g}", [r for r in rows if float(r["busy_total"]) <= thr],
                       [r for r in rows if float(r["busy_total"]) > thr], by_run)]
    if policy == "time":
        _require(rows, "session_id", policy)
        frac = float(spec["train_fraction"])
        run_rows: dict[str, list] = {}
        for r in rows:
            run_rows.setdefault(r["source_log"], []).append(r)
        sessions: dict[str, list] = {}
        for log, rs in run_rows.items():
            sessions.setdefault(rs[0]["session_id"], []).append(log)
        train_runs = set()
        for logs in sessions.values():
            logs.sort(key=lambda l: run_order_key(run_rows[l], l))
            train_runs.update(logs[:int(len(logs) * frac)])
        return [_check("time", [r for r in rows if r["source_log"] in train_runs],
                       [r for r in rows if r["source_log"] not in train_runs], True)]
    raise ValueError(f"unknown split policy {policy!r} (random row splits are not allowed)")
