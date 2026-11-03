/* Dashboard v2, tab 3: interactive charts of the final static-vs-dynamic benchmark. Data: GET /api/final (stored RESULTS_TABLE_FINAL.csv and
   confirmatory.csv). Uses the helpers of app.js (svg, txt, esc, row, showTip, hideTip). Hover any bar, dot or row for its numbers. Nothing here
   runs an experiment. */
(async function () {
  let f;
  try { f = await (await fetch("/api/final")).json(); } catch (e) { return; }
  if (!f || !f.all) return;
  const CFG = ["cpu", "gpu", "ext"];
  const COL = { cpu: "var(--pool-P)", gpu: "var(--pool-E)", ext: "var(--accent)" };
  const NAME = { cpu: "CPU only (P+E)", gpu: "strict GPU set", ext: "extended GPU set" };
  const WL = ["h16_l120", "uniform", "h04_l120", "h40_l120", "h16_l40", "h16_l15"];
  const WLD = { h16_l120: "16 heavy chains (primary)", uniform: "uniform (no spread)", h04_l120: "4 heavy chains", h40_l120: "40 heavy chains",
    h16_l40: "16 chains, 40 iterations", h16_l15: "16 chains, 15 iterations" };
  const POL = ["B4", "B4_param_first", "PRED_RANK_GREEDY", "PRED_RANK_GREEDY_E2E", "HEFT_param_model", "PEFT_param_model", "HEFT_E2E", "HEFT_ORACLE_REF"];
  const SHORT = { B4: "B4", B4_param_first: "B4 param-first", PRED_RANK_GREEDY: "PRED", PRED_RANK_GREEDY_E2E: "PRED_E2E", HEFT_param_model: "HEFT",
    PEFT_param_model: "PEFT", HEFT_E2E: "HEFT_E2E", HEFT_ORACLE_REF: "HEFT oracle*" };
  const sh = (s) => s.replace("PRED_RANK_GREEDY_E2E", "PRED_E2E").replace("PRED_RANK_GREEDY", "PRED").replace("_param_model", "").replace("HEFT_ORACLE_REF", "HEFT_oracle");
  const N = (x) => Number(x);
  const pct = (e, lo, hi) => `${N(e) > 0 ? "+" : ""}${N(e).toFixed(1)}% [${N(lo) > 0 ? "+" : ""}${N(lo).toFixed(1)}, ${N(hi) > 0 ? "+" : ""}${N(hi).toFixed(1)}]`;
  const get = (w, c, p) => f.all.find((r) => r.workload === w && r.config === c && r.policy === p);
  const frame = (id, W, H) => { const h = document.getElementById(id); if (!h) return null; h.innerHTML = ""; const r = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }); h.appendChild(r); return r; };
  const legend = (root, items, x, y) => items.forEach(([c, t], i) => { svg("rect", { x: x + i * 135, y, width: 10, height: 10, rx: 2, style: `fill:${c}` }, root); txt(root, x + i * 135 + 14, y + 9, t, { class: "axis-label" }); });
  const hline = (root, x1, x2, y, st) => svg("line", { x1, x2, y1: y, y2: y, style: st }, root);
  /* tooltip + hover highlight on any SVG element */
  const tip = (el, html) => {
    el.style.cursor = "pointer";
    el.addEventListener("mousemove", (ev) => showTip(ev, html));
    el.addEventListener("mouseenter", () => { el.dataset.o = el.style.opacity || ""; el.style.stroke = "var(--ink)"; el.style.strokeWidth = "1.5px"; });
    el.addEventListener("mouseleave", () => { el.style.stroke = ""; el.style.strokeWidth = ""; hideTip(); });
  };
  const hint = (id, text) => { const h = document.getElementById(id); if (h && h.parentElement && !h.parentElement.querySelector(".fc-hint")) h.insertAdjacentHTML("beforebegin", `<p class="sub fc-hint" style="margin:0 0 6px;font-style:italic">${text}</p>`); };
  ["fc-make", "fc-forest", "fc-wl-static", "fc-wl-b4", "fc-place"].forEach((id) => hint(id, "Hover a bar, dot or row for its numbers."));

  /* A. makespan bars, primary workload */
  (function () {
    const W = 660, H = 330, L = 48, R = 10, T = 30, B = 62, iw = W - L - R, ih = H - T - B, y0 = 2.5, y1 = 4.4;
    const root = frame("fc-make", W, H); if (!root) return;
    const y = (v) => T + ih - ((v - y0) / (y1 - y0)) * ih;
    for (let v = 2.5; v <= 4.4; v += 0.5) { hline(root, L, W - R, y(v), "stroke:var(--grid)"); txt(root, L - 6, y(v) + 4, v.toFixed(1), { "text-anchor": "end", class: "axis-label" }); }
    txt(root, 4, 12, "seconds (axis starts at 2.5 s)", { class: "axis-label" });
    const gw = iw / POL.length, bw = gw / 4;
    POL.forEach((p, i) => {
      CFG.forEach((c, j) => {
        const r = get("h16_l120", c, p); if (!r) return;
        const x = L + i * gw + bw * 0.5 + j * bw, v = N(r.e2e_geo_mean_s);
        const bar = svg("rect", { x, y: y(v), width: bw - 2, height: T + ih - y(v), style: `fill:${COL[c]};opacity:${i < 4 ? 1 : 0.6}` }, root);
        svg("line", { x1: x + (bw - 2) / 2, x2: x + (bw - 2) / 2, y1: y(N(r.e2e_ci_lo_s)), y2: y(N(r.e2e_ci_hi_s)), style: "stroke:var(--ink);stroke-width:1.2;pointer-events:none" }, root);
        tip(bar, `<b>${esc(SHORT[p])}</b> · ${esc(NAME[c])}` + row("type", i < 4 ? "dynamic policy" : "static plan") + row("end-to-end makespan", `${N(r.e2e_geo_mean_s).toFixed(3)} s`)
          + row("95% CI", `${N(r.e2e_ci_lo_s).toFixed(3)} to ${N(r.e2e_ci_hi_s).toFixed(3)} s`) + row("tasks CPU / GPU", `${N(r.tasks_cpu).toFixed(0)} / ${N(r.tasks_gpu).toFixed(0)}`)
          + row("GPU busy fraction", N(r.gpu_busy_frac).toFixed(2)) + (p === "HEFT_ORACLE_REF" ? row("note", "reference only (oracle costs)") : ""));
      });
      txt(root, L + i * gw + gw / 2, H - 38, SHORT[p], { "text-anchor": "middle", class: "axis-label" });
      txt(root, L + i * gw + gw / 2, H - 26, i < 4 ? "dynamic" : "static", { "text-anchor": "middle", class: "axis-label", style: "opacity:.7" });
    });
    legend(root, CFG.map((c) => [COL[c], NAME[c]]), L, H - 14);
  })();

  /* B. forest plot of C1-C10 */
  (function () {
    const rows = f.confirmatory, W = 660, rowH = 28, L = 250, R = 14, T = 8, H = T + rows.length * rowH + 40, xmin = -26, xmax = 6;
    const root = frame("fc-forest", W, H); if (!root) return;
    const x = (v) => L + ((v - xmin) / (xmax - xmin)) * (W - L - R);
    svg("rect", { x: x(-2), y: T, width: x(2) - x(-2), height: rows.length * rowH, style: "fill:var(--accent);opacity:.12;pointer-events:none" }, root);
    for (let v = -25; v <= 5; v += 5) { svg("line", { x1: x(v), x2: x(v), y1: T, y2: T + rows.length * rowH, style: "stroke:var(--grid);pointer-events:none" }, root); txt(root, x(v), H - 22, String(v), { "text-anchor": "middle", class: "axis-label" }); }
    svg("line", { x1: x(0), x2: x(0), y1: T, y2: T + rows.length * rowH, style: "stroke:var(--ink);stroke-width:1.5;pointer-events:none" }, root);
    txt(root, x(0), H - 8, "effect on makespan, % (negative = first policy faster)", { "text-anchor": "middle", class: "axis-label" });
    rows.forEach((r, i) => {
      const cy = T + i * rowH + rowH / 2, e = N(r.effect_pct), lo = N(r.ci_lo_pct), hi = N(r.ci_hi_pct);
      const col = /equivalent/.test(r.classification) ? "var(--accent)" : (hi < 0 && N(r.p_holm) < 0.05) ? "var(--good)" : "var(--muted)";
      const band = svg("rect", { x: 0, y: T + i * rowH, width: W, height: rowH, style: "fill:transparent" }, root);
      txt(root, 6, cy + 4, `${r.id}  ${sh(r.cond)} vs ${sh(r.ref)}`, { class: "axis-label", style: "fill:var(--ink-2);pointer-events:none" });
      svg("line", { x1: x(lo), x2: x(hi), y1: cy, y2: cy, style: `stroke:${col};stroke-width:2.5;pointer-events:none` }, root);
      svg("circle", { cx: x(e), cy, r: 4.5, style: `fill:${col};pointer-events:none` }, root);
      txt(root, W - R, cy - 7, `${e > 0 ? "+" : ""}${e.toFixed(1)}% · p ${N(r.p_holm).toFixed(3)}`, { "text-anchor": "end", class: "axis-label", style: "font-size:9.5px;pointer-events:none" });
      tip(band, `<b>${esc(r.id)}</b>: ${esc(r.cond)}<br>vs ${esc(r.ref)}` + row("effect on makespan", pct(r.effect_pct, r.ci_lo_pct, r.ci_hi_pct))
        + row("Holm-adjusted p", N(r.p_holm).toFixed(4)) + row("result", esc(r.classification)) + row("blocks", esc(r.n_blocks || "24")));
    });
  })();

  /* C, D. PRED vs HEFT / B4 across workloads */
  function wlChart(id, tag, refName) {
    const W = 660, H = 300, L = 46, R = 10, T = 28, B = 56, iw = W - L - R, ih = H - T - B;
    const root = frame(id, W, H); if (!root) return;
    const pts = [];
    WL.forEach((w, i) => CFG.forEach((c, j) => {
      const r = get(w, c, "PRED_RANK_GREEDY"); if (!r || r[`vs_${tag}_effect_pct`] === "") return;
      pts.push({ i, j, w, e: N(r[`vs_${tag}_effect_pct`]), lo: N(r[`vs_${tag}_ci_lo_pct`]), hi: N(r[`vs_${tag}_ci_hi_pct`]), c, cls: r[`vs_${tag}_classification`], mk: N(r.e2e_geo_mean_s) });
    }));
    const lo = Math.min(0, ...pts.map((p) => p.lo)) - 1, hi = Math.max(2, ...pts.map((p) => p.hi)) + 1;
    const y = (v) => T + ih - ((v - lo) / (hi - lo)) * ih;
    const step = (hi - lo) > 30 ? 10 : 5;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) { hline(root, L, W - R, y(v), "stroke:var(--grid)"); txt(root, L - 6, y(v) + 4, `${v}%`, { "text-anchor": "end", class: "axis-label" }); }
    hline(root, L, W - R, y(0), "stroke:var(--ink);stroke-width:1.5");
    const gw = iw / WL.length;
    WL.forEach((w, i) => txt(root, L + i * gw + gw / 2, H - 34, w, { "text-anchor": "middle", class: "axis-label" }));
    pts.forEach((p) => {
      const cx = L + p.i * gw + gw / 2 + (p.j - 1) * 16;
      svg("line", { x1: cx, x2: cx, y1: y(p.lo), y2: y(p.hi), style: `stroke:${COL[p.c]};stroke-width:2.5;pointer-events:none` }, root);
      svg("circle", { cx, cy: y(p.e), r: 4, style: `fill:${COL[p.c]};pointer-events:none` }, root);
      const hit = svg("circle", { cx, cy: y((p.lo + p.hi) / 2), r: 11, style: "fill:transparent" }, root);
      tip(hit, `<b>PRED</b> vs ${esc(refName)}<br>${esc(WLD[p.w])} · ${esc(NAME[p.c])}` + row("effect on makespan", pct(p.e, p.lo, p.hi)) + row("PRED makespan", `${p.mk.toFixed(3)} s`)
        + row("result", esc(p.cls || "exploratory")) + row("status", p.w === "h16_l120" ? "primary workload" : "exploratory, unadjusted"));
    });
    txt(root, 4, 12, "effect on makespan, % (negative = PRED faster)", { class: "axis-label" });
    legend(root, CFG.map((c) => [COL[c], NAME[c]]), L, H - 14);
  }
  wlChart("fc-wl-static", "static", "static HEFT");
  wlChart("fc-wl-b4", "B4", "blind B4");

  /* E. where tasks ran */
  (function () {
    const W = 660, rowH = 28, L = 120, R = 70, T = 10, H = T + POL.length * rowH + 34, tot = 257;
    const root = frame("fc-place", W, H); if (!root) return;
    const x = (v) => L + (v / tot) * (W - L - R);
    POL.forEach((p, i) => {
      const r = get("h16_l120", "ext", p); if (!r) return;
      const cy = T + i * rowH, c = N(r.tasks_cpu), g = N(r.tasks_gpu);
      txt(root, 6, cy + 17, SHORT[p], { class: "axis-label", style: "fill:var(--ink-2)" });
      const b1 = svg("rect", { x: x(0), y: cy + 5, width: x(c) - x(0), height: 16, style: "fill:var(--pool-P)" }, root);
      const b2 = svg("rect", { x: x(c), y: cy + 5, width: Math.max(1, x(c + g) - x(c)), height: 16, style: "fill:var(--accent)" }, root);
      txt(root, x(c + g) + 6, cy + 17, `${Math.round(c)}/${Math.round(g)} · busy ${N(r.gpu_busy_frac).toFixed(2)}`, { class: "axis-label", style: "pointer-events:none" });
      const html = `<b>${esc(SHORT[p])}</b> · ${esc(NAME.ext)} · mean per run` + row("tasks on CPU (P+E)", c.toFixed(1)) + row("tasks on RTX 3050", g.toFixed(1))
        + row("GPU share of tasks", `${((g / (c + g)) * 100).toFixed(0)}%`) + row("GPU busy fraction", N(r.gpu_busy_frac).toFixed(2)) + row("makespan", `${N(r.e2e_geo_mean_s).toFixed(3)} s`);
      tip(b1, html); tip(b2, html);
    });
    legend(root, [["var(--pool-P)", "CPU tasks (P+E)"], ["var(--accent)", "GPU tasks (RTX 3050)"]], L, H - 14);
  })();
})();
