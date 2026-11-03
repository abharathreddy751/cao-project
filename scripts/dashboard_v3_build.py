"""Builds src/caosched/dashboard_v3/static from the v2 static files (unchanged) plus the live tab (tab 6). New files only."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "src" / "caosched" / "dashboard_v2" / "static"
V3 = ROOT / "src" / "caosched" / "dashboard_v3" / "static"
V3.mkdir(parents=True, exist_ok=True)
for f in V2.iterdir():
    if f.is_file():
        shutil.copyfile(f, V3 / f.name)
shutil.copyfile(ROOT / "src" / "caosched" / "dashboard_v3" / "static_src" / "live3.js", V3 / "live3.js")


def rep(s, old, new):
    if old not in s:
        raise SystemExit("patch target not found: " + old[:70])
    return s.replace(old, new, 1)


h = (V3 / "index.html").read_text(encoding="utf-8")
h = rep(h, "<title>v2 - ", "<title>v3 - ")
h = rep(h, "Dashboard v2. ", "Dashboard v3 (v2 plus tab 6: live runs of the final benchmark with the RTX 3050). ")
h = rep(h, '<button role="tab" aria-selected="false" data-tab="montage">5 &middot; Montage &amp; GPU</button>',
        '<button role="tab" aria-selected="false" data-tab="montage">5 &middot; Montage &amp; GPU</button>\n    <button role="tab" aria-selected="false" data-tab="live3">6 &middot; Live: final benchmark</button>')
section = '''
  <!-- 6. LIVE RUN OF THE FINAL BENCHMARK -->
  <section class="screen" id="screen-live3" role="tabpanel">
    <div class="banner"><span class="badge live"><span class="dot"></span>LIVE</span>
      <span>Runs <strong>one block</strong> of the final benchmark on this laptop now: the real <code>WorkerPool</code> + <code>Coordinator</code> with P cores, E cores and (if chosen) the RTX 3050 CUDA worker G, the final workload (16 heavy chains of 64, 512 px) and the policy you pick. A demonstration run, not an experiment record: one repeat, no warm-up, so its makespan is not comparable with the confirmatory numbers on tab 3.</span></div>
    <div class="card">
      <div class="controls">
        <label>Policy <select id="l3-pol"></select></label>
        <label>Resources <select id="l3-cfg"></select></label>
        <button class="btn primary" id="l3-start" type="button">Run live (final benchmark)</button>
        <label>or reopen <select id="l3-prev"><option value="">previous live run&hellip;</option></select></label>
        <span id="l3-msg" class="sub" style="margin:0"></span>
      </div>
      <p class="sub">Takes about one to two minutes: worker start-up (and CUDA start-up for the GPU options), one run, then output verification (GPU tasks are re-run on the CPU and compared). Needs 2.4 GB of free RAM; close other programs first. Dynamic = decides while running; static = a fixed plan made before the run.</p>
    </div>
    <div class="grid g3" id="l3-tiles" style="margin-top:16px"></div>
    <div class="card" id="l3-detail" style="margin-top:16px" hidden></div>
  </section>
'''
h = rep(h, "</main>", section + "</main>")
h = rep(h, '<script src="/final_charts.js"></script>', '<script src="/final_charts.js"></script>\n<script src="/live3.js"></script>')
h = rep(h, "The live demo on screen 2 runs P, E and the simulated remote worker only; GPU results are on screen 3 (stored measurements) and screen 5.",
        "Live runs of the final benchmark on screen 6 use it; the older live demo on screen 2 runs P, E and the simulated remote worker only. GPU results are on screen 3 (stored measurements) and screen 5.")
(V3 / "index.html").write_text(h, encoding="utf-8")
j = (V3 / "app.js").read_text(encoding="utf-8")
j = rep(j, "CUDA worker G in the final benchmark; not part of the live demo pool", "CUDA worker G: used in the final benchmark and by the live runs on tab 6")
j = rep(j, "used in the final benchmark; live demo = P/E/R only", "used in the final benchmark and by tab 6 live runs")
j = rep(j, '"executed in the final benchmark", "not in the live demo pool"', '"executed in the final benchmark", "also used by the live runs on tab 6"')
j = rep(j, "Live demo (this dashboard): B4 greedy and EFT_E1_rc. Final benchmark (tab 3, stored):", "Live: screen 2 runs B4 greedy or EFT_E1_rc; screen 6 runs the final policies (static and dynamic, CPU or CPU + GPU). Final benchmark results (tab 3, stored):")
(V3 / "app.js").write_text(j, encoding="utf-8")
print("built", V3)
