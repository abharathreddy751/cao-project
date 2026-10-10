"""Read-only quality audit of one dataset build. Streams tasks.csv / candidates.csv.
Usage: audit_dataset.py <dataset dir>. Writes nothing."""
import collections, csv, json, math, re, sys
from pathlib import Path

sys.path.insert(0, r"D:\cao project\src")
from caosched.dataset.build import CAND_FIELDS, TASK_FIELDS  # noqa: E402

D = Path(sys.argv[1])
man = json.loads((D / "manifest.json").read_text(encoding="utf-8"))
spl = json.loads((D / "splits.json").read_text(encoding="utf-8"))
STAMP = re.compile(r"(\d{8}T\d{6})")
fails, notes = [], []


def check(ok, msg):
    print(("OK   " if ok else "FAIL ") + msg)
    if not ok:
        fails.append(msg)


def f(x):
    return None if x in ("", None) else float(x)


# ---------------- tasks.csv (rows of one source_log are contiguous) ----------------
nulls = collections.Counter()
per_src = collections.Counter()
per_kind = collections.Counter()
bad = collections.Counter()
keys, row_ids = set(), []
task_cand = {}            # (source_log, task_id) -> (worker_id, n_candidates, predicted_finish_s)
sess_rows = collections.Counter()
wss_by_session = collections.defaultdict(set)   # session -> {(workload,size,seed)}
rows_by_session_wss = collections.defaultdict(collections.Counter)
size_rows = collections.Counter()
busy_shift = collections.Counter()  # rows where co-runner count at dispatch != at start
tbf_after_dispatch = collections.Counter()
binding_rows = collections.Counter()
shift_hist = collections.Counter()
gap = collections.defaultdict(list)
srcs = {x["source_log"]: x for x in man["sources"]}
sessions = set(man["sessions"])


def flush(group):
    """Per-run checks that need the run's other tasks: decision-time vs start-time context."""
    for r in group:
        td, ts = r["_td"], r["_ts"]
        if td is None:
            continue
        binding_rows[r["policy_binding"]] += 1
        others = [o for o in group if o["worker_id"] != r["worker_id"]]
        at_dispatch = sum(1 for o in others if o["_ts"] <= td < o["_tc"])
        at_start = sum(1 for o in others if o["_ts"] <= ts < o["_tc"])
        if at_dispatch != at_start:
            busy_shift[r["policy_binding"]] += 1
        shift_hist[(r["policy_binding"], at_start - at_dispatch)] += 1
        gap[r["policy_binding"]].append(ts - td)
        # own-worker task finishing between decision and start -> target_busy_frac saw post-decision info
        if r["target_busy_frac"] != "" and any(o["worker_id"] == r["worker_id"] and td < o["_tc"] <= ts for o in group
                                               if o is not r):
            tbf_after_dispatch[r["policy_binding"]] += 1


with (D / "tasks.csv").open(encoding="utf-8", newline="") as fh:
    rd = csv.DictReader(fh)
    check(rd.fieldnames == TASK_FIELDS, f"tasks.csv header == TASK_FIELDS ({len(TASK_FIELDS)} columns)")
    cur, group, n = None, [], 0
    for r in rd:
        n += 1
        for c in TASK_FIELDS:
            if r[c] == "":
                nulls[c] += 1
        for c in ("kernel_s", "t_started_rel", "t_completed_rel", "worker_span_s"):
            v = f(r[c])
            if v is None or not math.isfinite(v):
                bad[f"{c} missing/non-finite"] += 1
        k = (r["source_log"], r["task_id"])
        if k in keys:
            bad["duplicate (source_log, task_id)"] += 1
        keys.add(k)
        row_ids.append(int(r["row_id"]))
        per_src[r["source_log"]] += 1
        per_kind[r["source_kind"]] += 1
        sess_rows[r["session_id"]] += 1
        if r["source_log"] not in srcs:
            bad["row from a source not in manifest"] += 1
        if r["session_id"] not in sessions:
            bad["session not in manifest"] += 1
        if not r["session_id"].startswith(r["source_kind"] + "_"):
            bad["source_kind inconsistent with session"] += 1
        if float(r["kernel_s"]) <= 0:
            bad["kernel_s <= 0"] += 1
        ts, tc = float(r["t_started_rel"]), float(r["t_completed_rel"])
        if ts > tc:
            bad["t_started > t_completed"] += 1
        td = f(r["t_dispatched_rel"])
        tr = f(r["t_ready_rel"])
        if tr is not None and td is not None and tr > td + 1e-9:
            bad["t_ready > t_dispatched"] += 1
        if td is not None and td > ts + 1e-9:
            bad["t_dispatched > t_started"] += 1
        if r["pool"] not in ("P", "E", "R"):
            bad["pool not in P/E/R"] += 1
        if (r["pool"] == "R") != (r["transfer_s"] != ""):
            bad["transfer_s present iff pool R violated"] += 1
        if float(r["setup_s"]) < -1e-6:
            bad["setup_s < 0 (span < kernel)"] += 1
        for c in ("busy_P", "busy_E", "busy_R", "busy_total"):
            if int(r[c]) < 0:
                bad[f"{c} < 0"] += 1
        if int(r["busy_total"]) != int(r["busy_P"]) + int(r["busy_E"]) + int(r["busy_R"]):
            bad["busy_total != P+E+R"] += 1
        if r["target_busy_frac"] != "" and not (0 <= float(r["target_busy_frac"]) <= 1):
            bad["target_busy_frac outside [0,1]"] += 1
        if r["calibration_profile"]:
            if STAMP.search(r["calibration_profile"]).group(1) > STAMP.search(r["session_id"]).group(1):
                bad["calibration profile measured AFTER the session (future info)"] += 1
        if r["n_candidates"] != "":
            task_cand[k] = (r["worker_id"], int(r["n_candidates"]), f(r["predicted_finish_s"]))
        wss = (r["workload"], r["size"], r["seed"])
        wss_by_session[r["session_id"]].add(wss)
        rows_by_session_wss[r["session_id"]][wss] += 1
        size_rows[(r["workload"], int(r["size"]))] += 1
        rr = {"worker_id": r["worker_id"], "policy_binding": r["policy_binding"], "target_busy_frac": r["target_busy_frac"],
              "_td": td, "_ts": ts, "_tc": tc}
        if r["source_log"] != cur:
            flush(group)
            cur, group = r["source_log"], []
        group.append(rr)
    flush(group)

print("\n== tasks.csv")
check(n == man["n_task_rows"], f"task rows {n} == manifest {man['n_task_rows']}")
check(sorted(row_ids) == list(range(n)) and row_ids == sorted(row_ids), "row_id unique, contiguous 0..n-1, in file order")
check(all(per_src[s] == x["rows"] for s, x in srcs.items()) and set(per_src) == set(srcs),
      f"per-source row counts match manifest for all {len(srcs)} sources")
check(dict(per_kind) == man["rows_per_source_kind"], f"rows per kind match manifest {dict(per_kind)}")
check(set(sess_rows) == sessions, f"sessions in rows == manifest sessions ({len(sessions)})")
check(not bad, "no invalid values / duplicates / provenance mismatches" + ("" if not bad else f": {dict(bad)}"))
print("   null counts (non-zero):", {c: v for c, v in nulls.items() if v})

# ---------------- candidates.csv ----------------
print("\n== candidates.csv")
dec_rows = collections.Counter()
dec_chosen = collections.defaultdict(list)
orphans = cbad = 0
decs_per_task = collections.defaultdict(set)
with (D / "candidates.csv").open(encoding="utf-8", newline="") as fh:
    rd = csv.DictReader(fh)
    check(rd.fieldnames == CAND_FIELDS, f"candidates.csv header == CAND_FIELDS ({len(CAND_FIELDS)} columns)")
    nc = 0
    for r in rd:
        nc += 1
        k = (r["source_log"], r["task_id"])
        if k not in keys:
            orphans += 1
        d = (r["source_log"], r["task_id"], r["decision_seq"])
        dec_rows[d] += 1
        decs_per_task[k].add(r["decision_seq"])
        if r["chosen"] == "True":
            dec_chosen[d].append((r["candidate_worker"], f(r["pred_finish_s"])))
        for c in ("pred_wait_s", "pred_exec_s", "pred_finish_s"):
            v = f(r[c])
            if v is None or not math.isfinite(v) or v < 0:
                cbad += 1
check(nc == man["n_candidate_rows"], f"candidate rows {nc} == manifest {man['n_candidate_rows']}")
check(orphans == 0, f"every candidate links to a task row (orphans: {orphans})")
check(cbad == 0, f"pred_wait/exec/finish present, finite, >= 0 (bad: {cbad})")
check(all(len(v) == 1 for v in decs_per_task.values()), "one decision per task")
multi = sum(1 for d in dec_rows if len(dec_chosen.get(d, [])) != 1)
check(multi == 0, f"exactly one chosen candidate per decision (violations: {multi}; decisions {len(dec_rows)})")
mism = cnt_mism = fin_mism = 0
for (src, tid, seq), cnt in dec_rows.items():
    t = task_cand.get((src, tid))
    if t is None:
        mism += 1
        continue
    wid, ncand, pf = t
    cw, cf = dec_chosen[(src, tid, seq)][0]
    cnt_mism += cnt != ncand
    fin_mism += (cw != wid) or (pf is not None and abs(cf - pf) > 1e-12)
check(mism == 0, f"every decision belongs to a task with n_candidates set (missing: {mism})")
check(len(task_cand) == len(dec_rows), f"tasks with n_candidates ({len(task_cand)}) == decisions ({len(dec_rows)})")
check(cnt_mism == 0, f"candidate count == task n_candidates (mismatches: {cnt_mism})")
check(fin_mism == 0, f"chosen candidate == executing worker and its pred_finish == task predicted_finish_s (mismatches: {fin_mism})")

# ---------------- splits ----------------
print("\n== splits.json")
bs = spl["by_session"]
tr_s, te_s = set(bs["train_sessions"]), set(bs["test_sessions"])
check(not (tr_s & te_s) and (tr_s | te_s) == sessions, f"by_session: disjoint and covers all sessions (train {sorted(tr_s)})")
br = spl["by_run_within_latest_campaign"]
check(not (set(br["train_runs"]) & set(br["test_runs"])) and all(x.split("/")[1] == br["session"] for x in br["train_runs"] + br["test_runs"]),
      f"by_run: disjoint runs, all in {br['session']} ({len(br['train_runs'])}/{len(br['test_runs'])})")
same = [w for w in spl["by_size"]["train"] if spl["by_size"]["train"][w] == spl["by_size"]["test"][w]]
check(not same, f"by_size: train size != test size for every workload (same: {same})")
tr_rows = sum(sess_rows[s] for s in tr_s)
te_rows = sum(sess_rows[s] for s in te_s)
tr_w = set().union(*(wss_by_session[s] for s in tr_s)) if tr_s else set()
te_rows_seen = sum(c for s in te_s for w, c in rows_by_session_wss[s].items() if w in tr_w)
print(f"   by_session rows: train {tr_rows}, test {te_rows}")
print(f"   test rows whose exact (workload, size, seed) input also occurs in train sessions: {te_rows_seen}/{te_rows} "
      f"({100 * te_rows_seen / max(te_rows, 1):.1f}%)")
tr_wl = {w for w, _, _ in tr_w}
te_wl = {w for s in te_s for w, _, _ in wss_by_session[s]}
print(f"   workloads train {sorted(tr_wl)}; test-only workloads {sorted(te_wl - tr_wl)}")
print(f"   sizes per workload: { {w: sorted(s for (ww, s) in size_rows if ww == w) for w in sorted({w for w, _ in size_rows})} }")

print("\n== decision-time availability of context features (rows with a dispatch time)")
for b in sorted(binding_rows):
    print(f"   binding={b}: rows {binding_rows[b]}; co-runner count differs between dispatch and start: {busy_shift[b]} "
          f"({100 * busy_shift[b] / binding_rows[b]:.1f}%); target_busy_frac includes an own task finished after dispatch: "
          f"{tbf_after_dispatch[b]}")
for b in sorted(binding_rows):
    h = {d: c for (bb, d), c in sorted(shift_hist.items()) if bb == b}
    g = sorted(gap[b])
    print(f"   binding={b}: (co-runners at start - at dispatch) histogram {h}; dispatch->start gap median "
          f"{g[len(g) // 2] * 1e3:.3f} ms, p90 {g[int(len(g) * 0.9)] * 1e3:.3f} ms")
print("\nRESULT:", "ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
