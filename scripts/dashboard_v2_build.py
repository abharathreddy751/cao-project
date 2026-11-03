"""Builds the static files of src/caosched/dashboard_v2 from the unchanged originals in src/caosched/dashboard/static (new files only)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "caosched" / "dashboard" / "static"
D = ROOT / "src" / "caosched" / "dashboard_v2" / "static"
D.mkdir(parents=True, exist_ok=True)
for f in ("app.css", "app.js", "index.html"):
    (D / f).write_bytes((SRC / f).read_bytes())

h = (D / "index.html").read_text(encoding="utf-8")
a = h.index('      <div class="card">\n        <h2>NVIDIA T4')
END = "      </div>" + chr(10)
b = h.index(END, h.index("No GPU utilisation")) + len(END)   # end of the whole old T4 card
new = '''      <div class="card">
        <h2>Local NVIDIA GPU &middot; CUDA worker G <span class="badge sim" style="margin-left:6px"><span class="dot"></span>USED IN THE FINAL BENCHMARK</span></h2>
        <p class="sub">The laptop's own GPU. In the final benchmark it runs as one CUDA worker <code>G</code> (configurations cpu / gpu / ext). The live demo on screen 2 runs P, E and the simulated remote worker only; GPU results are on screen 3 (stored measurements) and screen 5.</p>
        <dl class="kv" id="ov-gpu"><dt>Status</dt><dd>loading...</dd></dl>
      </div>
      <div class="card">
        <h2>Remote NVIDIA T4 <span class="badge off" style="margin-left:6px"><span class="dot"></span>NOT CONNECTED</span></h2>
        <p class="sub">Planned remote pool <code>R_T4</code> (an external device) with the CUDA <code>img_edges</code> variant: <strong>never attached or executed</strong>. This is not the local GPU above.</p>
        <p class="empty">No remote GPU metrics: nothing is attached.</p>
      </div>
'''
h = h[:a] + new + h[b:]
card = '''    <div class="card" id="final-card" style="margin-bottom:16px"><h2>Final benchmark: static vs dynamic scheduling (CPU and GPU) <span class="badge sim" style="margin-left:6px"><span class="dot"></span>REAL &middot; STORED</span></h2>
      <p class="sub" id="final-src">loading...</p><div class="table-wrap" id="final-conf"></div><div class="table-wrap" id="final-prim" style="margin-top:12px"></div></div>
'''
charts = '''    <div class="banner"><span class="badge sim"><span class="dot"></span>REAL &middot; FINAL BENCHMARK</span>
      <span>Stored results of the final static-vs-dynamic study (RTX 3050 CUDA worker G + P/E cores). The older B4-vs-EFT comparison is kept below, collapsed.</span></div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card chart-card"><h2>End-to-end makespan by policy (primary workload)</h2><p class="sub">Lower is better; bars = geometric mean over 24 blocks, whiskers = 95% CI. Static plans: HEFT, PEFT, HEFT_E2E, HEFT_oracle (reference only).</p><div id="fc-make"></div></div>
      <div class="card chart-card"><h2>Confirmatory contrasts C1&ndash;C10</h2><p class="sub">Effect on makespan, % (left of 0 = first policy faster), 95% CI; shaded band = the &plusmn;2% equivalence margin.</p><div id="fc-forest"></div></div>
      <div class="card chart-card"><h2>PRED_RANK_GREEDY vs static HEFT, all six workloads</h2><p class="sub">Paired effect %, 95% CI (negative = dynamic faster). Only the primary workload is confirmatory; the others are exploratory.</p><div id="fc-wl-static"></div></div>
      <div class="card chart-card"><h2>PRED_RANK_GREEDY vs blind B4, all six workloads</h2><p class="sub">Paired effect %, 95% CI (negative = PRED faster). The gain disappears when task cost does not vary (uniform, light workloads).</p><div id="fc-wl-b4"></div></div>
      <div class="card chart-card"><h2>Where the tasks ran (primary workload, extended GPU set)</h2><p class="sub">Tasks on CPU (P+E) vs the RTX 3050; the number is the GPU busy fraction.</p><div id="fc-place"></div></div>
    </div>
'''
a_h = h.index('    <div class="banner"><span class="badge replay"><span class="dot"></span>HISTORICAL</span>')
b_h = h.index("  </section>", a_h)
h = h[:a_h] + charts + card + '    <details style="margin-top:16px"><summary><strong>Historical comparison: B4 vs EFT_E1_rc (earlier machine, Phase B sweep)</strong></summary>\n' + h[a_h:b_h] + '    </details>\n' + h[b_h:]
h = h.replace('<script src="/app.js"></script>', '<script src="/app.js"></script>\n<script src="/final_charts.js"></script>', 1)
h = h.replace("<title>", "<title>v2 - ", 1)
h = re.sub(r'\s*<p class="sub">Read-only: runs are found through.*?</p>', '', h, count=1, flags=re.S)  # tab 5 note removed on request
(D / "index.html").write_text(h, encoding="utf-8")

j = (D / "app.js").read_text(encoding="utf-8")
anchor = '    ["Remote worker", S.nodeCore != null'
i = j.index(anchor)
e = j.index("\n", i)
tile = ('\n    ["Local GPU (CUDA worker G)", (sys.gpu && sys.gpu.available) ? sys.gpu.name : "not detected", '
        '(sys.gpu && sys.gpu.available) ? `${Math.round(sys.gpu.memory_mib / 1024)} GiB, used in the final benchmark; live demo = P/E/R only` : ((sys.gpu && sys.gpu.error) || "")],')
j = j[:e] + tile + j[e:]
gpu_dl = ('  if ($("#ov-gpu")) $("#ov-gpu").innerHTML = (sys.gpu && sys.gpu.available) ? '
          '`<dt>Device</dt><dd>${esc(sys.gpu.name)}</dd><dt>Memory</dt><dd>${esc(sys.gpu.memory_mib)} MiB</dd><dt>Driver</dt><dd>${esc(sys.gpu.driver)} (nvidia-smi)</dd>'
          '<dt>Role</dt><dd>CUDA worker G in the final benchmark; not part of the live demo pool</dd>` : '
          '`<dt>Status</dt><dd>not detected (${esc((sys.gpu && sys.gpu.error) || "no data")})</dd>`;\n')
j = j.replace("  const lv = sys.live || {};", gpu_dl + "  const lv = sys.live || {};", 1)
j = j.replace('"NOT executed (no GPU here)", "NOT validated", "no GPU metrics (not connected)"',
              '"NOT executed (remote T4 not attached)", "NOT validated", "no remote GPU metrics (not connected)"', 1)
fin = '''
async function drawFinal() {
  let f; try { f = await api("/api/final"); } catch (e) { $("#final-src").textContent = "final results unavailable: " + e.message; return; }
  $("#final-src").innerHTML = `Primary workload, end-to-end makespan, 24 blocks. Source: ${esc(f.source)}. Negative effect = faster.`;
  const n = (x, d = 2) => Number(x).toFixed(d), sg = (x) => (Number(x) > 0 ? "+" : "") + n(x, 1);
  $("#final-conf").innerHTML = `<table class="data"><thead><tr><th>id</th><th>contrast</th><th class="n">effect % [95% CI]</th><th class="n">Holm p</th><th>result</th></tr></thead><tbody>`
    + f.confirmatory.map((r) => `<tr><td>${esc(r.id)}</td><td>${esc(r.cond)} vs ${esc(r.ref)}</td><td class="n">${sg(r.effect_pct)} [${sg(r.ci_lo_pct)}, ${sg(r.ci_hi_pct)}]</td><td class="n">${n(r.p_holm, 3)}</td><td>${esc(r.classification)}</td></tr>`).join("") + `</tbody></table>`;
  $("#final-prim").innerHTML = `<table class="data"><thead><tr><th>config</th><th>policy</th><th>kind</th><th class="n">makespan s [95% CI]</th><th class="n">tasks CPU/GPU</th><th class="n">GPU busy</th></tr></thead><tbody>`
    + f.primary.map((r) => `<tr><td>${esc(r.config)}</td><td>${esc(r.policy)}</td><td>${esc(r.kind)}</td><td class="n">${n(r.e2e_geo_mean_s, 3)} [${n(r.e2e_ci_lo_s, 3)}, ${n(r.e2e_ci_hi_s, 3)}]</td><td class="n">${n(r.tasks_cpu, 0)}/${n(r.tasks_gpu, 0)}</td><td class="n">${n(r.gpu_busy_frac, 2)}</td></tr>`).join("") + `</tbody></table>`;
}
'''
j = j.replace("async function boot() {", fin + "async function boot() {", 1)
j = j.replace('  guard("compare", drawComparison);', '  guard("compare", drawComparison);\n  drawFinal();', 1)
(D / "app.js").write_text(j, encoding="utf-8")
print("built", D)
import runpy
runpy.run_path(str(ROOT / "scripts" / "dashboard_v2_patch.py"))
runpy.run_path(str(ROOT / "scripts" / "dashboard_v2_patch2.py"))
runpy.run_path(str(ROOT / "scripts" / "dashboard_v2_patch3.py"))
