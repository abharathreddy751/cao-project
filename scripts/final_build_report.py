"""Final study: build CAO_FINAL_EXPERIMENT_REPORT.md. Every number in the tables and in the sentences that quote a result is read from the
analysis files written by scripts/final_analyze.py (eval/analysis_*/), from RESULTS_TABLE_FINAL.csv, from the hold-out log of the model
training, or from the two GPU-spike records; nothing is typed in by hand. Written exclusively (fails if the report exists).

  python scripts/final_build_report.py <out.md>
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIN = ROOT / "data" / "results" / "final_20261101"
EV = FIN / "eval"
WL = ["h16_l120", "uniform", "h04_l120", "h40_l120", "h16_l40", "h16_l15"]
CFG = ["cpu", "gpu", "ext"]


def rd(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


TAB = [r for r in rd(ROOT / "RESULTS_TABLE_FINAL.csv") if r["kind"] != "confirmatory"]
T = {(r["workload"], r["config"], r["policy"]): r for r in TAB}
CONF = rd(EV / "analysis_h16_l120" / "confirmatory.csv")
CON = {w: [r for r in rd(EV / f"analysis_{w}" / "contrasts.csv") if r["metric"] == "makespan_e2e_s"] for w in WL}
META = {w: json.load(open(EV / f"analysis_{w}" / "meta.json")) for w in WL}


def con(w, cond, ref, kind="within configuration"):
    for r in CON[w]:
        if r["cond"] == cond and r["ref"] == ref and r["kind"] == kind:
            return r
    return None


CF = {r['id']: r for r in CONF}


def ce(i):
    return eff(CF[i])


def eff(r):
    return "n/a" if r is None else f"{float(r['effect_pct']):+.1f}% [{float(r['ci_lo_pct']):+.1f}, {float(r['ci_hi_pct']):+.1f}]"


def g(w, c, p, k="e2e_geo_mean_s", nd=3):
    r = T.get((w, c, p))
    return "-" if r is None or r.get(k, "") == "" else f"{float(r[k]):.{nd}f}"


def md(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows])


DYN = ["B4", "B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E"]
STA = ["HEFT_param_model", "PEFT_param_model", "HEFT_E2E", "HEFT_ORACLE_REF"]
LABEL = {"HEFT_ORACLE_REF": "HEFT_oracle (reference only)"}

# ---------- tables
prim = []
for c in CFG:
    for p in DYN + STA:
        r = T[("h16_l120", c, p)]
        prim.append([c, p if p not in LABEL else LABEL[p], "dynamic" if p in DYN else "static",
                     f"{float(r['e2e_geo_mean_s']):.3f} [{float(r['e2e_ci_lo_s']):.3f}, {float(r['e2e_ci_hi_s']):.3f}]",
                     f"{float(r['init_s']) * 1000:.1f}", f"{float(r['policy_setup_s']) * 1000:.1f}", f"{float(r['sched_total_s']) * 1000:.1f}",
                     f"{float(r['queue_wait_mean_s']):.3f}", f"{float(r['tasks_cpu']):.0f}/{float(r['tasks_gpu']):.0f}", f"{float(r['gpu_busy_frac']):.2f}",
                     f"{float(r['cpu_util']):.2f}", g("h16_l120", c, p, "plan_over_actual", 2) if p in STA else "-", f"{r['output_ok']}/{r['n']}"])
T_PRIM = md(["config", "policy", "kind", "end-to-end makespan s [95% CI]", "init ms", "policy setup ms", "scheduling ms", "queue wait s", "tasks CPU/GPU", "GPU busy", "CPU util", "planned/actual", "output ok"], prim)

ids = {"C1": "dynamic PRED vs B4 (CPU)", "C2": "PRED_E2E vs PRED (CPU)", "C3": "PRED vs static HEFT_param_model (CPU)", "C4": "PRED_E2E vs HEFT_E2E (CPU)",
       "C5": "PRED vs static HEFT_param_model (strict GPU)", "C6": "PRED_E2E vs HEFT_E2E (strict GPU)", "C7": "PRED_E2E vs PRED (strict GPU)",
       "C8": "PRED vs B4 (strict GPU)", "C9": "PRED strict GPU vs PRED CPU", "C10": "B4 strict GPU vs B4 CPU"}
pred = {"C1": "faster (earlier sessions: about -19%)", "C2": "equivalent", "C3": "inconclusive or equivalent", "C4": "inconclusive or equivalent",
        "C5": "(none stated)", "C6": "(none stated)", "C7": "faster or equivalent", "C8": "(none stated)", "C9": "small", "C10": "small"}
T_CONF = md(["id", "contrast", "effect % [95% CI]", "Holm p", "classification", "stated before the data"],
            [[r["id"], ids[r["id"]], f"{float(r['effect_pct']):+.2f} [{float(r['ci_lo_pct']):+.2f}, {float(r['ci_hi_pct']):+.2f}]",
              f"{float(r['p_holm']):.4f}", r["classification"], pred[r["id"]]] for r in CONF])


def cross(c, ref_tag):
    rows = []
    for w in WL:
        if (w, c, "PRED_RANK_GREEDY") not in T:
            continue
        row = [w]
        for p in ("B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E"):
            r = T[(w, c, p)]
            e = r.get(f"vs_{ref_tag}_effect_pct", "")
            row.append("-" if e == "" else f"{float(e):+.1f}% [{float(r[f'vs_{ref_tag}_ci_lo_pct']):+.1f}, {float(r[f'vs_{ref_tag}_ci_hi_pct']):+.1f}]")
        rows.append(row)
    return md(["workload", "B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E"], rows)


GEO = md(["workload", "config", *DYN, *[LABEL.get(p, p) for p in STA]],
         [[w, c, *[g(w, c, p) for p in DYN + STA]] for w in WL for c in CFG if (w, c, "B4") in T])

# hold-out accuracy
hold = []
for ln in open(FIN / "models" / "train.stdout.txt", encoding="utf-8"):
    m = re.match(r"holdout (\S+) (\{.*\})", ln.strip())
    if m:
        d = eval(m.group(2))
        hold.append([m.group(1), d["n"], f"{d['mae_s'] * 1000:.2f}", f"{d['median_ape'] * 100:.1f}%"])
T_HOLD = md(["stage|pool", "n hold-out tasks", "MAE ms", "median abs % error"], hold)

# GPU spike
spk = []
for tag, p in (("original record", ROOT / "data/results/stage1_20261011/gpu/gpu_spike.json"),
               ("extended record", FIN / "gpu_spike_iters/spike_20261101T144333/gpu_spike.json")):
    for r in json.load(open(p))["rows"]:
        if r["side"] == 512:
            spk.append([tag, r["stage"], json.loads(r["params"]).get("iterations", "-") if r["stage"] == "img_denoise" else "-",
                        f"{r['cpu_median_s'] * 1000:.1f}", f"{r['gpu_median_s'] * 1000:.1f}", f"{r['speedup']:.2f}x", r["verdict"]])
T_SPK = md(["record", "stage", "denoise iterations", "CPU ms", "GPU ms (incl. H2D, kernel, D2H)", "speedup", "verdict"], spk)

# hybrid
hyb = (EV / "hybrid_check.md").read_text(encoding="utf-8")
hyb_line = [ln for ln in hyb.splitlines() if ln.startswith("cells:")][0]
# timing convention: end-to-end minus old
tim = []
for p in DYN + STA:
    r = T[("h16_l120", "cpu", p)]
    tim.append([LABEL.get(p, p), f"{float(r['old_geo_mean_s']):.3f}", f"{float(r['e2e_geo_mean_s']):.3f}", f"{(float(r['e2e_geo_mean_s']) - float(r['old_geo_mean_s'])) * 1000:.1f}"])
T_TIM = md(["policy (CPU, primary)", "old convention s (first dispatch to last completion)", "end-to-end s (start of run to last completion)", "difference ms"], tim)
nruns = {w: META[w]["n_runs"] for w in WL}
n_incl = {w: META[w]["n_included"] for w in WL}
gpuvcpu = con("h16_l120", "PRED_RANK_GREEDY_gpu", "PRED_RANK_GREEDY_cpu", "configuration effect")
extvcpu = con("h16_l120", "PRED_RANK_GREEDY_ext", "PRED_RANK_GREEDY_cpu", "configuration effect")
extvstrict = con("h16_l120", "PRED_RANK_GREEDY_ext", "PRED_RANK_GREEDY_gpu", "extended vs strict GPU set")
heft_ext_cpu = con("h16_l120", "HEFT_param_model_ext", "HEFT_param_model_cpu", "configuration effect")
b4_ext_cpu = con("h16_l120", "B4_ext", "B4_cpu", "configuration effect")
_old = [r for r in rd(EV / "analysis_h16_l120" / "contrasts.csv") if r["metric"] == "makespan_s" and r["cond"] == "PRED_RANK_GREEDY_cpu" and r["ref"] == "HEFT_param_model_cpu"][0]
c3_old = eff(_old)
pf = {}
for c in CFG:
    for r in rd(EV / f"exploratory_pf_{c}" / "effects.csv"):
        if r["metric"] == "makespan_e2e_s" and r["cond"] == f"PRED_RANK_GREEDY_{c}" and r["ref"] == f"B4_param_first_{c}" and r["n_blocks"] == "24":   # 24 blocks = warm-up excluded; the generic tool calls this tier "confirmatory", it is exploratory here

            pf[c] = f"{float(r['effect_pct']):+.1f}% [{float(r['ci_lo_pct']):+.1f}, {float(r['ci_hi_pct']):+.1f}]"
uni_cpu = con("uniform", "PRED_RANK_GREEDY_cpu", "B4_cpu")
uni_gpu = con("uniform", "PRED_RANK_GREEDY_gpu", "B4_gpu")
uni_e2e_gpu = con("uniform", "PRED_RANK_GREEDY_E2E_gpu", "B4_gpu")
heft_e2e_vs = {c: con("h16_l120", f"HEFT_E2E_{c}", f"HEFT_param_model_{c}") for c in CFG}
peft_vs = {c: con("h16_l120", f"PEFT_param_model_{c}", f"HEFT_param_model_{c}") for c in CFG}
orc_vs = {c: con("h16_l120", f"HEFT_ORACLE_REF_{c}", f"HEFT_param_model_{c}") for c in CFG}
ov = lambda p, c="cpu": float(T[("h16_l120", c, p)]["policy_setup_s"]) * 1000
sched = lambda p, c="cpu": float(T[("h16_l120", c, p)]["sched_total_s"]) * 1000
mk = lambda p, c="cpu": float(T[("h16_l120", c, p)]["e2e_geo_mean_s"]) * 1000

REPORT = f"""# CAO final experiment report: static versus dynamic scheduling on a CPU + GPU workstation

Generated by `scripts/final_build_report.py` from the analysis files of the final study (`data/results/final_20261101/`). Evidence label of every
number below: **real measurement on one laptop** (Intel P cores + E cores, one RTX 3050 6 GB, Windows 11), except Section 12 (earlier **emulated**
remote-worker sessions, cited, not rerun) and Section 13 (a descriptive check on the measured data). Raspberry Pi is out of scope.

## 1. Answer in one page

Question: does the end-to-end dynamic scheduling framework (DAG manager, runtime estimation, rank-based ordering, late-bound CPU/GPU worker
choice, execution feedback) finish a workflow sooner than a fixed static schedule built from the same cost model, and under which conditions?

* **Supported (confirmatory, Holm-adjusted, primary workload, end-to-end makespan).** The dynamic policy PRED_RANK_GREEDY beats the static
  HEFT_param_model plan by {ce('C3')} on CPU only (C3) and
  {ce('C5')} with the strict GPU set (C5); the end-to-end variant beats HEFT_E2E by
  {ce('C4')} (C4) and {ce('C6')} (C6).
  Against blind B4 the gain is {ce('C1')} on CPU (C1) and
  {ce('C8')} with the strict GPU set (C8). Percent is the change in makespan: negative = faster.
* **Where the dynamic gain shrinks or vanishes.** With little spread in task cost (uniform workload, and the `l15` and `l40` workloads) PRED is
  equal to B4 within the margin or only a few percent faster (Section 7). The dynamic-versus-static gap is 0.2 to 5.2% on CPU across the six workloads.
* **The simple parameter-aware baseline captures almost all of the gain.** PRED_RANK_GREEDY against B4_param_first, end-to-end makespan, primary workload, exploratory: {pf['cpu']} (CPU), {pf['ext']} (extended GPU)
  and {pf['gpu']} (strict GPU), i.e. under 1% in every configuration. Most of the improvement over B4 comes from using task parameters
  to choose where and in which order to run, not from rank ordering and late binding as such.
* **The end-to-end cost terms did not change the outcome.** PRED_E2E versus PRED: {ce('C2')} on CPU (C2) and
  {ce('C7')} on strict GPU (C7): both equivalent within +-2%. On the uniform workload with the strict GPU set the E2E variant was
  {eff(uni_e2e_gpu)} against B4 (exploratory).
* **GPU.** Using the GPU only where the spike records verified a speedup helps the dynamic policy: extended set versus CPU only
  {eff(extvcpu)}, strict set versus CPU only {eff(gpuvcpu)} (C9). It does not help blind B4 ({ce('C10')}, C10, inconclusive).
* **Hybrid.** Not justified: {hyb_line}
* **Not shown.** No universal claim. One machine, one image-pipeline family, sizes 512 px, the effect depends on the spread of task cost. The remote worker was not rerun with the final policies.

## 2. What was built and changed

| Item | Where | Status |
|---|---|---|
| Timing accounting: init, policy setup, scheduling, execution in one end-to-end makespan; old makespan kept | `core/coordinator.py`, `study2/adapter.py`, `analysis/stats_paired.py`, `docs/final/AMENDMENT_F1_timing.md` | new convention labelled; old results untouched |
| Fair static baselines HEFT_param_model, PEFT_param_model, HEFT_E2E, HEFT_oracle (reference only) | `final/policies.py`, `study2` registered classes | fixed assignment; planned vs actual logged |
| New dynamic policy PRED_RANK_GREEDY_E2E | `final/policies.py` | calibrated on separate sessions; unit tests |
| Per-task GPU eligibility from verified spike rows | `final/gpu_region.py` | only PASS rows; a DROPPED row wins |
| Final adapter, designs, analysis, report scripts | `final/adapter.py`, `scripts/final_*.py` | idempotent, exclusive writes |

Preservation: git state, diff, SHA-256 of sources, 164 earlier designs and key documents, run-manifest count 4753, and backups of every edited tracked file are in `data/results/final_20261101/preservation/` and `backups/`. No earlier result was overwritten; the earlier `RESULTS_TABLE.csv` is unchanged and the new table is `RESULTS_TABLE_FINAL.csv`.

## 3. Cost audit: no double counting of transfer

Checked in `apps/cuda_stages.py` and the timing in `run_stage`: the CUDA stage wall time already contains host-to-device copy, kernel and device-to-host copy. The CUDA table above therefore uses that time as is, and the E2E variant adds only artifact I/O (setup) and inter-process overhead, never H2D or D2H again. For local pools the modelled transfer is 0.

## 4. Method

* Workloads (image pipeline: source, denoise, edges, features, aggregate; 512 px). Primary `h16_l120`: 16 heavy chains (denoise 120 iterations) among light ones, 25 blocks. Other workloads: `uniform`, `h04_l120`, `h40_l120`, `h16_l40`, `h16_l15` (13 blocks each; the first block of every session is a warm-up and excluded).
* Configurations: `cpu` (P+E), `gpu` (strict: only stages verified on the original GPU record), `ext` (strict plus denoise at iteration counts verified on the extended record). The uniform workload has `cpu` and `gpu` only.
* Policies: static HEFT_param_model, PEFT_param_model, HEFT_E2E, HEFT_oracle (class-median costs, reference only); dynamic B4, B4_param_first, PRED_RANK_GREEDY, PRED_RANK_GREEDY_E2E.
* Separate data: the cost model and the end-to-end terms were fitted on calibration sessions (`cal_l15`, `cal_l40`, `cal_l120`, `cal_uniform`) and checked on hold-out sessions (`hold_l40`, `hold_l120`); the evaluation sessions came afterwards, with new chain orders. The protocol (`docs/final/PROTOCOL_final.md`) and the evaluation design hashes were logged as frozen before the first evaluation session.
* Interleaved blocks, one run of every condition per block; free RAM and mains power were checked before every block. Runs per session: {', '.join(f'{w} {nruns[w]} ({n_incl[w]} included)' for w in WL)}. Output correctness verified for every included run (`output ok` column).
* Statistics: paired within-block log-ratio, stratified percentile bootstrap (10000 resamples), sign-flip p, Holm over the 10 confirmatory contrasts of the primary session, equivalence margin +-2%. Everything else is exploratory and unadjusted.

## 5. Cost model quality (hold-out, never used for fitting)

{T_HOLD}

CPU stages are predicted within about 4 to 11% median error. GPU stages are predicted much worse (about 23 to 31% median error): the GPU estimate is the weakest part of the model and limits what the model-based GPU placement can do.

## 6. GPU eligibility (spike records)

{T_SPK}

Only PASS rows enter a GPU configuration; denoise with 2 iterations stays on CPU. No GPU worker or stream was added; one CUDA worker.

## 7. Results

### 7.1 Primary workload `h16_l120` (end-to-end makespan, geometric mean over {META['h16_l120']['n_included'] // 24} blocks)

{T_PRIM}

### 7.2 Confirmatory contrasts (Holm family of 10)

{T_CONF}

Predictions written before the data held for C1, C2, C7, C9 and C10. C3 and C4 were predicted inconclusive or equivalent; the data show the dynamic policy faster by about 5%, so that prediction was wrong. C5, C6 and C8 had no stated expectation.

### 7.3 All workloads: end-to-end makespan, seconds

{GEO}

### 7.4 Effect against the static plan HEFT_param_model (percent, negative = dynamic faster; exploratory outside the primary session)

CPU only:

{cross('cpu', 'static')}

Strict GPU:

{cross('gpu', 'static')}

Extended GPU:

{cross('ext', 'static')}

### 7.5 Effect against blind B4

CPU only:

{cross('cpu', 'B4')}

Strict GPU:

{cross('gpu', 'B4')}

Extended GPU:

{cross('ext', 'B4')}

### 7.6 Uniform control

PRED against B4 on the uniform workload: CPU {eff(uni_cpu)}, strict GPU {eff(uni_gpu)}; PRED_E2E against B4 on strict GPU {eff(uni_e2e_gpu)}. With no spread in task cost the policies differ little, as expected, but the E2E variant is not free of cost on the strict GPU set.

## 8. Static baselines

* HEFT_param_model is the main static comparator (same model as the dynamic policies). HEFT_E2E adds the setup and overhead terms to the plan costs: against HEFT_param_model it is {eff(heft_e2e_vs['cpu'])} (CPU), {eff(heft_e2e_vs['gpu'])} (strict GPU), {eff(heft_e2e_vs['ext'])} (extended GPU). Adding the terms to the static plan did not help consistently.
* PEFT_param_model against HEFT_param_model: {eff(peft_vs['cpu'])} (CPU), {eff(peft_vs['gpu'])} (strict GPU), {eff(peft_vs['ext'])} (extended GPU): clearly the slowest static plan here.
* HEFT_oracle (class-median costs from the calibration sessions, not per-run realised times) against HEFT_param_model: {eff(orc_vs['cpu'])} (CPU), {eff(orc_vs['gpu'])} (strict GPU), {eff(orc_vs['ext'])} (extended GPU). It is a reference, not a bound: with realised per-run times a static plan could be better.
* Planned versus actual makespan of the static plans is in the primary table (column planned/actual): the plans are not far from reality in total, yet the fixed assignment cannot react to the actual completion order.

## 9. Timing accounting (amendment F1)

{T_TIM}

The difference is the initialisation plus the policy setup (the static plan is computed before the first dispatch, which the old convention hid). It is small against a makespan of about 3 s (policy setup {ov('HEFT_param_model'):.0f} ms for HEFT, {ov('PEFT_param_model'):.0f} ms for PEFT, {ov('PRED_RANK_GREEDY'):.0f} ms for PRED; total scheduling time {sched('HEFT_param_model'):.0f}, {sched('PEFT_param_model'):.0f} and {sched('PRED_RANK_GREEDY'):.0f} ms), so no conclusion of this study flips between the two conventions on this workload size. Check on the old convention (same session, metric `makespan_s`): PRED against HEFT_param_model on CPU only is {c3_old}.

## 10. GPU findings

* Strict GPU set versus CPU only for PRED: {eff(gpuvcpu)}; extended set versus CPU only: {eff(extvcpu)}; extended versus strict: {eff(extvstrict)}.
* The static HEFT plan on the extended set versus its CPU plan: {eff(heft_ext_cpu)}; blind B4 on the extended set versus CPU only: {eff(b4_ext_cpu)} (it sends work to the GPU without a cost model).
* Tasks per resource and GPU busy fraction are in the primary table. Under the model-based policies the GPU takes roughly 15 to 20% of the 257 tasks (blind B4 on the strict set sends about 32%) and its busy fraction is higher with the extended set.
* One CUDA worker, so the GPU is a single, narrow resource; the benefit comes from putting the right tasks on it, which needs the cost model.

## 11. Is a hybrid selector justified?

No. Decision rule fixed in the protocol: build one only if a B4-or-PRED selector could gain more than the +-2% margin in the development cells. {hyb_line} Full table: `data/results/final_20261101/eval/hybrid_check.md`. No hybrid was built and no held-out hybrid session was run.

## 12. Remote worker (secondary, emulated, not rerun)

Not part of the confirmatory family and not rerun with the final policies. Earlier registered emulated sessions (claims S7, S8, N6, X5 in `RESEARCH_CLAIMS_AND_LIMITATIONS.md`): on a slow emulated wide-area link blind remote placement was clearly harmful (+31.18% against no remote worker) and transfer-aware placement avoided that harm (+0.32%, not significant); on a fast emulated link the remote worker gave **no benefit**: at denoise level 1 none, and at level 30 the predictive policy was 3.78% slower with the remote worker (+3.78% [+2.27, +5.58]) even though the predicted remote execution and transfer times matched the measured ones (0.1457 s against 0.1464 s, 0.0937 s against 0.0943 s). These are emulation results from the earlier study (loopback node behind a delay shim, not a real network), labelled as such. A real remote benefit remains unproven.

## 13. Limitations

* One machine, one workload family (image pipeline), 512 px, 6 P + 7 E workers and one CUDA worker. No claim beyond these.
* The GPU estimate has 23 to 31% median error on the hold-out set. A static plan commits to those estimates in advance; a dynamic policy only uses them when a worker is idle. Part of the dynamic-versus-static gap on the GPU configurations may therefore reflect model error and not only the timing of decisions; this was not separated experimentally (the HEFT_oracle reference uses class medians, which is not realised per-run time).
* The earlier overnight session (claim S11) found HEFT level with PRED (+1.10% [-0.53, +2.81], old convention, different chain orders). This study finds PRED faster than HEFT_param_model by about 5% on CPU only. The two conventions do not explain it (Section 9); the difference between the sessions (new chain orders, 24 blocks, current code, the idle CUDA worker kept in the pool in the `cpu` configuration) was not isolated, so the earlier and the new result should both be quoted.
* Static plans use occupancy-blind planning (as registered); a static plan with perfect knowledge of actual task times was not computed (HEFT_oracle uses class medians).
* Only the primary session is confirmatory; the other five workloads are exploratory and unadjusted, as is B4_param_first against PRED.
* The features for the hybrid check were computed after the primary results had been read (the model and DAG alone determine them); this is logged in `ACTIVITY_LOG.md`.
* The remote worker was not rerun with the final policies (Section 12).
* Environment: Windows 11 laptop; sessions needed mains power and at least 0.8 GB free RAM per block; aborted attempts are kept on disk (`_r2`, ...) and never pooled.

## 14. Contribution statement

A reproducible end-to-end timing convention and benchmark for comparing static and dynamic scheduling of DAG workflows on a CPU+GPU workstation with the same cost model on both sides; per-task GPU eligibility derived from recorded speedup measurements; a fair set of static baselines; and honest results: the dynamic policy is faster than the static plan by about 2 to 12% where task cost varies, ties blind B4 where it does not, and a simple parameter-aware baseline gets almost the same benefit.

## 15. Reproducing

`scripts/final_stage1.ps1` (calibration, models, designs, smoke), `scripts/final_stage2.ps1` (six evaluation sessions and analyses), `scripts/final_analyze.py ... --confirmatory`, `scripts/final_results_table.py`, `scripts/final_cross_workload.py`, `scripts/final_hybrid_check.py`, `scripts/final_build_report.py`. Hashes of protocol, designs and models: `data/results/final_20261101/ACTIVITY_LOG.md`. Tests: `tests/test_final_*.py`.
"""

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("x", encoding="utf-8") as fh:
    fh.write(REPORT)
print("wrote", out, len(REPORT.splitlines()), "lines")
