"use strict";
/* CAO dashboard front end. All values come from the server's read-only API,
   which reads event logs, artifacts and verified result files. Nothing here
   invents a measurement: missing values render as "–". */

const NS = "http://www.w3.org/2000/svg";
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (x, d = 1) => (x == null || Number.isNaN(+x) ? "–" : (+x).toFixed(d));
const sgn = (x, d = 1) => (x == null ? "–" : (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(d));
const B4 = "B4_greedy_eligible_R", EFT = "EFT_E1_rc_R";
const POL = {
  [B4]: { short: "B4", label: "B4 greedy (P→E→R)", color: "var(--pol-B4)", shape: "circle" },
  [EFT]: { short: "EFT", label: "EFT_E1_rc (transfer-aware)", color: "var(--pol-EFT)", shape: "diamond" },
};
const POOL = { P: "P-core pool", E: "E-core pool", R: "Remote R0 (simulated)" };
const SHORT = { img_source: "src", img_tile: "tile", img_denoise: "dn", img_edges: "edg", img_features: "feat",
  img_mosaic: "mosaic", img_aggregate: "aggr", img_package: "package" };
const COL = { img_source: 0, img_tile: 1, img_denoise: 2, img_edges: 3, img_features: 4, img_mosaic: 5, img_aggregate: 5, img_package: 6 };

const S = { sessions: [], cmp: null, hw: null, sys: null, view: null, key: null, t: 0, tEnd: 1, playing: false,
  sel: null, mode: "replay", livePoll: null, liveStatus: null, nodeCore: null };

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status} ${r.statusText}`);
  return j;
}
function svg(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}
function txt(parent, x, y, s, attrs = {}) { const t = svg("text", { x, y, ...attrs }, parent); t.textContent = s; return t; }
const tint = (pool, pct) => `color-mix(in srgb, var(--pool-${pool}) ${pct}%, var(--surface))`;
const sessionDate = (s) => { const m = /(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/.exec(s || ""); return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}` : ""; };

/* ---------------- tooltip ---------------- */
const tip = $("#tip");
function showTip(ev, html) {
  tip.innerHTML = html; tip.style.display = "block";
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + w > innerWidth - 8) x = ev.clientX - w - 14;
  if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
const hideTip = () => { tip.style.display = "none"; };
const row = (k, v) => `<div class="r"><span>${esc(k)}</span><span>${v}</span></div>`;

/* ---------------- tabs & theme ---------------- */
function showTab(name) {
  const b = document.querySelector(`nav.tabs button[data-tab="${name}"]`);
  if (!b) return;
  document.querySelectorAll("nav.tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
  document.querySelectorAll("section.screen").forEach((s) => s.classList.toggle("active", s.id === `screen-${name}`));
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  if (name === "workflow") drawWorkflow();
  if (name === "montage") mgInit();
}
document.querySelectorAll("nav.tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
addEventListener("hashchange", () => showTab(location.hash.slice(1)));
if (location.hash) showTab(location.hash.slice(1));
$("#theme-btn").addEventListener("click", () => {
  const dark = getComputedStyle(document.documentElement).colorScheme === "dark";
  document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
  try { localStorage.setItem("cao-theme", dark ? "light" : "dark"); } catch (e) { /* storage optional */ }
  drawWorkflow(); drawComparison(); drawHardware();
});
try { const t = localStorage.getItem("cao-theme"); if (t) document.documentElement.setAttribute("data-theme", t); } catch (e) { /* optional */ }

function setModeBadge() {
  const b = $("#mode-badge");
  const live = S.mode === "live";
  b.className = `badge ${live ? "live" : "replay"}`;
  b.lastElementChild.textContent = live ? "LIVE EXECUTION" : "HISTORICAL REPLAY";
}

/* ================= 1. SYSTEM OVERVIEW ================= */
function lpRoles(sys) {
  const roles = {};
  const topo = sys.topology;
  if (!topo) return roles;
  topo.p_core_slots.forEach((lp, i) => { roles[lp] = { cls: "P", text: `P-core worker P${i}` }; });
  let e = 0;
  topo.e_core_slots.forEach((lp) => {
    if (lp === S.nodeCore) roles[lp] = { cls: "R", text: "Remote node R0 (simulated) + link shim" };
    else roles[lp] = { cls: "E", text: `E-core worker E${e++}` };
  });
  if (topo.coordinator_core != null) roles[topo.coordinator_core] = { cls: "", text: "Coordinator + remote proxy" };
  return roles;
}

function drawOverview() {
  const sys = S.sys; if (!sys) return;
  const topo = sys.topology;
  const roles = lpRoles(sys);
  const eWorkers = topo ? topo.e_core_slots.filter((x) => x !== S.nodeCore) : [];
  const runs = S.sessions.flatMap((s) => s.runs);
  const tiles = [
    ["Logical processors", sys.logical_processors, `${sys.physical_cores} physical cores (live)`],
    ["P-core workers", topo ? topo.p_core_slots.length : "–", topo ? `LP ${topo.p_core_slots.join(", ")}` : sys.topology_error],
    ["E-core workers", topo ? eWorkers.length : "–", topo ? `LP ${eWorkers.join(", ")}` : ""],
    ["Coordinator", topo ? `LP ${topo.coordinator_core}` : "–", "reserved E-core"],
    ["Remote worker", S.nodeCore != null ? `LP ${S.nodeCore}` : "–", "simulated (local node + shim)"],
    ["Free memory", `${fmt(sys.memory_available_gib, 2)} GiB`, `of ${fmt(sys.memory_total_gib, 1)} GiB (live)`],
  ];
  $("#ov-tiles").innerHTML = tiles.map(([l, v, n]) =>
    `<div class="tile"><div class="label">${esc(l)}</div><div class="value num">${esc(v)}</div><div class="note">${esc(n)}</div></div>`).join("");
  $("#ov-lps").innerHTML = sys.cpu_percent.map((p, i) => {
    const r = roles[i] || { cls: "", text: "not assigned (left free by the runtime)" };
    return `<div class="lp ${r.cls}"><div class="h"><span>LP ${i}</span><span class="num">${fmt(p, 0)}%</span></div>
      <div class="role">${esc(r.text)}</div><div class="bar"><div style="width:${Math.min(100, p)}%"></div></div></div>`;
  }).join("");
  const lv = sys.live || {};
  const exact = runs.filter((r) => r.output_match === "exact").length;
  const liveTxt = lv.process_running ? `running — ${esc(lv.state || "starting")} (${esc(lv.session)})`
    : lv.session ? `${esc(lv.state || "finished")} — ${esc(lv.session)}${lv.makespan_ms ? `, makespan ${fmt(lv.makespan_ms)} ms` : ""}${lv.verification ? `, output ${esc(lv.verification.match)}` : ""}`
      : "idle (no live run started in this server session)";
  $("#ov-status").innerHTML = `
    <dt>Live execution</dt><dd>${liveTxt}</dd>
    <dt>Scheduling policies</dt><dd>B4 greedy (first idle worker, P→E→R) and EFT_E1_rc (earliest predicted finish incl. link transfer; static stage profile with online recalibration)</dd>
    <dt>Application</dt><dd>Tiled image analysis: 68 tasks in 8 stages, real data passed as artifacts</dd>
    <dt>Verified record</dt><dd>${S.sessions.length} accepted sessions, ${runs.length} demo runs; final output exact vs reference in ${exact}/${runs.length} (runs.csv)</dd>
    <dt>Workload levels</dt><dd>${S.sessions.map((s) => `k=${s.k}`).join(", ")} (denoise blur applied k times)</dd>`;
}

async function drawRemote(view, origin) {
  const w = (view.workers || []).find((x) => x.pool === "R");
  const c = (w && w.capabilities) || {};
  const link = view.link || {};
  $("#ov-remote").innerHTML = w ? `
    <dt>Worker</dt><dd>${esc(w.id)} on LP ${esc(w.lp)} (affinity ${w.affinity_ok ? "verified" : "NOT verified"})</dd>
    <dt>Node reports</dt><dd>${esc(c.platform)} &middot; ${esc(c.machine)} &middot; Python ${esc(c.python)}</dd>
    <dt>CUDA</dt><dd>${c.cuda ? "available" : "not available"} (reported by the node)</dd>
    <dt>Stages offered</dt><dd>${(c.stages || []).length} application stages</dd>
    <dt>Link shim</dt><dd>${esc(link.name || "–")}: ${fmt((link.latency_s || 0) * 1e3, 1)} ms latency, ${fmt((link.bandwidth_Bps || 0) / 1e6, 0)} MB/s</dd>
    <dt>Source</dt><dd class="mono">${esc(origin)}</dd>` : `<dt>Status</dt><dd>no run loaded yet</dd>`;
}

/* ================= 2. APPLICATION WORKFLOW ================= */
function fillReplaySelectors() {
  const ks = $("#rp-k");
  ks.innerHTML = S.sessions.map((s) => `<option value="${s.k}">k = ${s.k} (${esc(s.session)})</option>`).join("");
  ks.value = "16";
  fillRuns();
}
function fillRuns() {
  const s = S.sessions.find((x) => String(x.k) === $("#rp-k").value);
  $("#rp-run").innerHTML = s.runs.slice().sort((a, b) => a.repeat - b.repeat || a.order_index - b.order_index).map((r) =>
    `<option value="${esc(r.run)}">r${String(r.repeat).padStart(2, "0")} · ${POL[r.policy].short} · ${fmt(r.makespan_ms, 0)} ms · ${r.tasks_R} remote · ${esc(r.output_match)}</option>`).join("");
  const firstEft = s.runs.find((r) => r.policy === EFT && r.tasks_R > 0) || s.runs[0];
  $("#rp-run").value = firstEft.run;
}
$("#rp-k").addEventListener("change", () => { fillRuns(); loadReplay(); });
$("#rp-run").addEventListener("change", loadReplay);

async function loadReplay() {
  stopLivePoll();
  S.mode = "replay"; setModeBadge();
  const s = S.sessions.find((x) => String(x.k) === $("#rp-k").value);
  const run = $("#rp-run").value;
  try {
    const v = await api(`/api/run?session=${encodeURIComponent(s.session)}&run=${encodeURIComponent(run)}`);
    S.view = v; S.key = { session: s.session, run, live: false, k: s.k }; S.sel = null;
    S.tEnd = endTime(v); S.t = S.tEnd;
    drawWorkflow();
  } catch (e) { $("#wf-banner").textContent = `Could not load run: ${e.message}`; }
}
function endTime(v) {
  let m = 0;
  for (const t of v.tasks || []) m = Math.max(m, t.t_done_event ?? t.t_completed ?? t.t_dispatched ?? t.t_ready ?? 0);
  return Math.max(m, v.now_ms || 0, 1);
}

function stateAt(task, t) {
  if (S.mode === "live" && !(S.view && S.view.finished)) return task.state; // live: what the log says right now
  const done = task.t_done_event ?? task.t_completed;
  if (done != null && done <= t) return "completed";
  if (task.t_dispatched != null && task.t_dispatched <= t) return "running";
  if (task.t_ready != null && task.t_ready <= t) return "ready";
  return "pending";
}

function nodeStyle(task, st) {
  const pool = task.pool;
  if (st === "completed") return { fill: tint(pool, 32), stroke: `var(--pool-${pool})`, sw: 1.25, text: "var(--ink)" };
  if (st === "running" || st === "dispatched") return { fill: "var(--surface)", stroke: `var(--pool-${pool})`, sw: 2.5, text: "var(--ink)" };
  if (st === "ready") return { fill: "var(--surface)", stroke: "var(--ink-2)", sw: 1.5, text: "var(--ink-2)" };
  if (st === "failed") return { fill: "var(--surface)", stroke: "var(--critical)", sw: 2.5, text: "var(--ink)" };
  return { fill: "var(--surface)", stroke: "var(--grid)", sw: 1, text: "var(--muted)" };
}

function drawWorkflow() {
  const v = S.view;
  drawBanner();
  if (!v || !v.started) {
    $("#dag").innerHTML = `<p class="empty">${S.mode === "live" ? "Waiting for the run to start (worker processes are being launched)…" : "No run loaded."}</p>`;
    $("#gantt").innerHTML = ""; $("#wf-summary").innerHTML = ""; $("#wf-out").innerHTML = ""; $("#wf-verify").innerHTML = "";
    return;
  }
  drawDag(v); drawGantt(v); drawSummary(v); drawOutput(v); drawTask(v);
  const slider = $("#t-slider");
  const live = S.mode === "live" && !v.finished;
  slider.disabled = live; $("#play").disabled = live;
  slider.value = String(Math.round((S.t / S.tEnd) * 1000));
  $("#t-label").textContent = `t = ${fmt(S.t, 1)} / ${fmt(S.tEnd, 1)} ms`;
}

function drawBanner() {
  const b = $("#wf-banner");
  if (S.mode === "live") {
    const st = S.liveStatus || {};
    b.innerHTML = `<span class="badge live"><span class="dot"></span>LIVE</span>
      <span>New execution on this laptop now: state <strong>${esc(st.state || "starting")}</strong>, policy ${esc(st.policy || "")}, k=${esc(st.k ?? "")}.
      Uses the real <code>WorkerPool</code>, <code>Coordinator</code> and scheduler. Output goes to <code>data/dashboard_runs/${esc(S.key && S.key.session)}</code>, kept apart from the experiment record.
      ${st.estimator_profile ? `EFT's stage profile: <code>${esc(st.estimator_profile)}</code> (from the accepted session for this k).` : ""}
      ${st.message ? `<br><strong>${esc(st.message)}</strong>` : ""}</span>`;
  } else if (S.key) {
    b.innerHTML = `<span class="badge replay"><span class="dot"></span>HISTORICAL REPLAY</span>
      <span>Accepted, verified session <code>${esc(S.key.session)}</code> (k=${S.key.k}, recorded ${sessionDate(S.key.session)}), run <code>${esc(S.key.run)}</code>.
      Read unchanged from <code>data/events/${esc(S.key.session)}/${esc(S.key.run)}.jsonl</code>; the slider replays the logged event times.</span>`;
  }
}

function dagLayout(tasks) {
  const W = 66, H = 17, colW = 118, rowH = 22, top = 14, left = 8;
  const pos = {};
  const mid = top + 7.5 * rowH;
  for (const t of tasks) {
    const c = COL[t.stage], i = t.id.includes("_") ? +t.id.split("_")[1] : -1;
    let y;
    if (t.stage === "img_source" || t.stage === "img_package") y = mid;
    else if (t.stage === "img_mosaic") y = top + 3.5 * rowH;
    else if (t.stage === "img_aggregate") y = top + 11.5 * rowH;
    else y = top + i * rowH;
    pos[t.id] = { x: left + c * colW, y, W, H };
  }
  return { pos, width: left + 6 * colW + W + 10, height: top + 16 * rowH + 4 };
}

function drawDag(v) {
  const { pos, width, height } = dagLayout(v.tasks);
  const root = svg("svg", { viewBox: `0 0 ${width} ${height + 18}`, role: "img",
    "aria-label": "DAG of the image-analysis application with each task's execution state" });
  const showCrit = v.critical_path.length && S.t >= S.tEnd - 1e-6;
  const critEdges = new Set();
  if (showCrit) for (let i = 1; i < v.critical_path.length; i++) critEdges.add(`${v.critical_path[i - 1]}>${v.critical_path[i]}`);
  const heads = ["source", "tile", "denoise", "edges", "features", "mosaic / aggregate", "package"];
  heads.forEach((h, c) => txt(root, 8 + c * 118 + 33, height + 13, h, { "text-anchor": "middle", class: "axis-label" }));
  const eg = svg("g", {}, root);
  for (const t of v.tasks) for (const d of t.deps) {
    const a = pos[d], b = pos[t.id];
    const x1 = a.x + a.W, y1 = a.y + a.H / 2, x2 = b.x, y2 = b.y + b.H / 2, mx = (x1 + x2) / 2;
    svg("path", { d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, class: `dag-edge${critEdges.has(`${d}>${t.id}`) ? " crit" : ""}` }, eg);
  }
  for (const c of critEdges) { /* draw critical edges on top */
    const [d, id] = c.split(">"); const a = pos[d], b = pos[id];
    const x1 = a.x + a.W, y1 = a.y + a.H / 2, x2 = b.x, y2 = b.y + b.H / 2, mx = (x1 + x2) / 2;
    svg("path", { d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, class: "dag-edge crit" }, root);
  }
  for (const t of v.tasks) {
    const p = pos[t.id], st = stateAt(t, S.t), sty = nodeStyle(t, st);
    const g = svg("g", { class: `dag-node${S.sel === t.id ? " sel" : ""}`, tabindex: 0, role: "button",
      "aria-label": `${t.id}: ${st}${t.pool ? ` on ${t.pool}` : ""}` }, root);
    svg("rect", { x: p.x, y: p.y, width: p.W, height: p.H, rx: 4, style: `fill:${sty.fill};stroke:${sty.stroke};stroke-width:${sty.sw}px` }, g);
    const idx = t.id.includes("_") ? t.id.split("_")[1] : "";
    const label = `${SHORT[t.stage]}${idx}${t.pool && st !== "pending" && st !== "ready" ? ` · ${t.pool}` : ""}`;
    txt(g, p.x + p.W / 2, p.y + p.H / 2 + 3.5, label, { "text-anchor": "middle", style: `fill:${sty.text}` });
    g.addEventListener("mousemove", (ev) => showTip(ev, taskTip(t, st)));
    g.addEventListener("mouseleave", hideTip);
    g.addEventListener("click", () => { S.sel = t.id; drawWorkflow(); });
    g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); S.sel = t.id; drawWorkflow(); } });
  }
  const host = $("#dag"); host.innerHTML = ""; host.appendChild(root);
  const pools = [...new Set(v.workers.map((w) => w.pool))];
  $("#dag-legend").innerHTML = pools.map((p) => `<span><i style="background:${tint(p, 32)};box-shadow:inset 0 0 0 1.5px var(--pool-${p})"></i>completed on ${POOL[p]}</span>`).join("")
    + `<span><i style="box-shadow:inset 0 0 0 2.5px var(--ink-2)"></i>running (pool-coloured outline)</span>`
    + `<span><i style="box-shadow:inset 0 0 0 1.5px var(--ink-2)"></i>ready</span><span><i style="box-shadow:inset 0 0 0 1px var(--axis)"></i>pending</span>`
    + (v.critical_path.length ? `<span><i class="line"></i>observed critical path (shown after completion)</span>` : "");
}

function taskTip(t, st) {
  return `<b>${esc(t.id)}</b> · ${esc(t.stage)}<br>` + row("state", esc(st))
    + (t.worker ? row("worker", `${esc(t.worker)} (${esc(POOL[t.pool])})`) : "")
    + (t.kernel_ms != null ? row("kernel", `${fmt(t.kernel_ms, 2)} ms`) : "")
    + (t.io_ms != null ? row("artifact I/O", `${fmt(t.io_ms, 2)} ms`) : "")
    + (t.transfer_ms != null ? row("link transfer", `${fmt(t.transfer_ms, 2)} ms`) : "")
    + (t.t_started != null ? row("start → end", `${fmt(t.t_started, 1)} → ${fmt(t.t_completed, 1)} ms`) : "");
}

function niceStep(span, target) {
  const raw = span / target, p = 10 ** Math.floor(Math.log10(raw)), f = raw / p;
  return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
}

function drawGantt(v) {
  const workers = v.workers.slice();
  const L = 92, R = 12, T = 8, rowH = 24, W = 960;
  const H = T + workers.length * rowH + 28;
  const x = (ms) => L + (ms / S.tEnd) * (W - L - R);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Per-worker timeline of task executions" });
  const step = niceStep(S.tEnd, 8);
  for (let s = 0; s <= S.tEnd + 1e-9; s += step) {
    svg("line", { x1: x(s), x2: x(s), y1: T, y2: T + workers.length * rowH, class: "grid-line" }, root);
    txt(root, x(s), T + workers.length * rowH + 14, `${Math.round(s)}`, { "text-anchor": "middle", class: "axis-label" });
  }
  txt(root, W - R, H - 2, "ms since run start", { "text-anchor": "end", class: "axis-label" });
  workers.forEach((w, i) => {
    const y = T + i * rowH;
    txt(root, 8, y + rowH / 2 + 4, `${w.id} [LP${w.lp}]`, { style: "fill:var(--ink-2);font-weight:600" });
    for (const t of v.tasks.filter((tt) => tt.worker === w.id)) {
      const s0 = t.t_started, e0 = t.t_completed;
      const live = S.mode === "live" && !v.finished;
      if (w.pool === "R" && t.t_submitted != null) {
        const a = t.t_submitted, b = t.t_done_event ?? e0 ?? (live ? v.now_ms : null);
        if (b != null && a < S.t) svg("rect", { x: x(a), y: y + 4, width: Math.max(1, x(Math.min(b, S.t)) - x(a)), height: rowH - 8, rx: 3,
          style: `fill:${tint("R", 25)}` }, root);
      }
      if (s0 == null) {
        if (live && t.state === "running" && t.t_submitted != null && w.pool !== "R")
          svg("rect", { x: x(t.t_submitted), y: y + 4, width: Math.max(2, x(v.now_ms) - x(t.t_submitted)), height: rowH - 8, rx: 3,
            style: `fill:none;stroke:var(--pool-${w.pool});stroke-width:2px` }, root);
        continue;
      }
      if (s0 >= S.t) continue;
      const bw = Math.max(1.5, x(Math.min(e0, S.t)) - x(s0));
      const r = svg("rect", { x: x(s0), y: y + (w.pool === "R" ? 7 : 4), width: bw, height: rowH - (w.pool === "R" ? 14 : 8), rx: 3,
        style: `fill:var(--pool-${w.pool});${S.sel === t.id ? "stroke:var(--ink);stroke-width:2px" : ""}`, tabindex: -1 }, root);
      if (bw > 34 && w.pool !== "R") txt(root, x(s0) + 4, y + rowH / 2 + 3.5, SHORT[t.stage], { style: "fill:#fff;font-size:9.5px;font-weight:650;pointer-events:none" });
      r.addEventListener("mousemove", (ev) => showTip(ev, taskTip(t, stateAt(t, S.t))));
      r.addEventListener("mouseleave", hideTip);
      r.addEventListener("click", () => { S.sel = t.id; drawWorkflow(); });
    }
  });
  if (S.t < S.tEnd || (S.mode === "live" && !v.finished))
    svg("line", { x1: x(Math.min(S.t, S.tEnd)), x2: x(Math.min(S.t, S.tEnd)), y1: T - 4, y2: T + workers.length * rowH, style: "stroke:var(--ink);stroke-width:1.5px" }, root);
  const host = $("#gantt"); host.innerHTML = ""; host.appendChild(root);
}

function drawSummary(v) {
  const f = v.finished;
  const tasks = v.tasks;
  const dec = tasks.map((t) => t.decision_us).filter((x) => x != null);
  const meanDec = dec.length ? dec.reduce((a, b) => a + b, 0) / dec.length : null;
  const counts = { P: 0, E: 0, R: 0 }; tasks.forEach((t) => { if (t.pool) counts[t.pool] = (counts[t.pool] || 0) + 1; });
  const done = tasks.filter((t) => t.state === "completed").length;
  const chips = Object.entries(counts).map(([p, n]) => `<span class="chip"><i style="background:var(--pool-${p})"></i>${p} ${n}</span>`).join(" ");
  const cp = v.critical_path.map((id) => SHORT[(tasks.find((t) => t.id === id) || {}).stage] || id).join(" → ");
  $("#wf-summary").innerHTML = `
    <dt>Scheduler</dt><dd>${esc((POL[v.scheduler] || {}).label || v.scheduler)}${v.estimator ? `<br><span class="mono">${esc(v.estimator)}</span>` : ""}</dd>
    <dt>Workload level</dt><dd>k = ${esc(v.metadata.denoise_iterations)} (${esc(v.metadata.width)}×${esc(v.metadata.height)}, grid ${esc(v.metadata.grid)})</dd>
    <dt>Status</dt><dd>${f ? esc(f.status) : `in progress — ${done}/${v.n_tasks} tasks completed`}</dd>
    <dt>Makespan</dt><dd class="num">${f ? `${fmt(f.makespan_ms, 1)} ms` : "–"}</dd>
    <dt>Placement</dt><dd>${chips}</dd>
    <dt>Sum of kernels</dt><dd class="num">${f ? `${fmt(f.total_kernel_ms, 1)} ms` : "–"}</dd>
    <dt>Scheduling time</dt><dd class="num">${f ? `${fmt(f.scheduling_ms, 2)} ms per run` : "–"} · ${fmt(meanDec, 1)} µs per decision</dd>
    <dt>Critical path</dt><dd>${cp ? esc(cp) : "after completion"}</dd>
    <dt>Free RAM at start</dt><dd class="num">${fmt(v.memory_available_gib, 2)} GiB</dd>
    <dt>Software</dt><dd class="mono">${esc((v.software || {}).version || "unrecorded")}</dd>`;
}

function drawOutput(v) {
  const q = `session=${encodeURIComponent(S.key.session)}&run=${encodeURIComponent(S.key.run)}`;
  const done = !!v.finished;
  const stamp = S.key.live ? `&v=${Date.now()}` : "";
  $("#wf-out").innerHTML = `
    <figure><img alt="Input scene (source artifact)" src="/api/artifact?${q}&which=source${stamp}" onerror="this.replaceWith(Object.assign(document.createElement('p'),{className:'empty',textContent:'input not written yet'}))"><figcaption>Input scene · <code>source.bin</code></figcaption></figure>
    <figure>${done ? `<img alt="Output edge mosaic (final package artifact)" src="/api/artifact?${q}&which=mosaic${stamp}">` : `<p class="empty">Final package not written yet.</p>`}<figcaption>Output edge mosaic · <code>package.bin</code> (contrast stretched for display)</figcaption></figure>`;
  let html = "";
  if (S.mode === "live") {
    const ver = (S.liveStatus || {}).verification;
    if (ver) {
      const acc = S.sessions.find((s) => s.k === (S.liveStatus || {}).k);
      const accSha = acc && acc.runs[0].output_sha256;
      html = `<span class="status ${ver.match === "exact" ? "good" : ver.match === "numeric" ? "warn" : "crit"}"><span class="ic">${ver.match === "exact" ? "✓" : "!"}</span>Output ${esc(ver.match)} vs single-process reference</span>
        <div class="sub mono" style="margin-top:4px">sha256 ${esc(ver.sha256.slice(0, 16))}…</div>
        ${accSha ? `<div class="sub">${accSha === ver.sha256 ? "Identical" : "Not identical"} to the verified output of accepted session k=${acc.k}.</div>` : ""}`;
    } else html = `<p class="empty">Verification runs after the last task completes.</p>`;
  } else {
    const s = S.sessions.find((x) => x.session === S.key.session);
    const r = s && s.runs.find((x) => x.run === S.key.run);
    if (r) html = `<span class="status ${r.output_match === "exact" ? "good" : "crit"}"><span class="ic">${r.output_match === "exact" ? "✓" : "!"}</span>Output ${esc(r.output_match)} vs reference (recorded in runs.csv)</span>
      <div class="sub mono" style="margin-top:4px">sha256 ${esc(r.output_sha256.slice(0, 16))}…</div>`;
  }
  $("#wf-verify").innerHTML = html;
}

function drawTask(v) {
  const t = v.tasks.find((x) => x.id === S.sel);
  const host = $("#wf-task");
  if (!t) { host.className = "empty"; host.textContent = "Click a task in the DAG or timeline."; return; }
  host.className = "";
  const w = v.workers.find((x) => x.id === t.worker);
  let html = `<dl class="kv">
    <dt>Task</dt><dd><strong>${esc(t.id)}</strong> · ${esc(t.stage)}</dd>
    <dt>Eligible pools</dt><dd>${esc((t.eligible || []).join(", "))}</dd>
    <dt>Assigned</dt><dd>${t.worker ? `${esc(t.worker)} · ${esc(POOL[t.pool])}${w ? ` · LP ${esc(w.lp)}` : ""}` : "not yet"}</dd>
    <dt>Ready / dispatched</dt><dd class="num">${fmt(t.t_ready, 1)} / ${fmt(t.t_dispatched, 1)} ms</dd>
    <dt>Started / completed</dt><dd class="num">${fmt(t.t_started, 1)} / ${fmt(t.t_completed, 1)} ms</dd>
    <dt>Kernel</dt><dd class="num">${fmt(t.kernel_ms, 2)} ms</dd>
    <dt>Artifact I/O</dt><dd class="num">${fmt(t.io_ms, 2)} ms</dd>
    <dt>Link transfer</dt><dd class="num">${t.transfer_ms != null ? `${fmt(t.transfer_ms, 2)} ms (${fmt((t.payload_bytes || 0) / 1024, 0)} KiB moved)` : "– (local)"}</dd>
    <dt>Decision latency</dt><dd class="num">${fmt(t.decision_us, 1)} µs</dd></dl>`;
  if (t.candidates) {
    html += `<h3>EFT's predictions at decision time</h3><div class="table-wrap"><table class="data"><thead><tr><th>worker</th><th class="n">wait</th><th class="n">transfer</th><th class="n">exec</th><th class="n">finish</th></tr></thead><tbody>`
      + t.candidates.map((c) => `<tr${c.worker === t.worker ? ' style="font-weight:700"' : ""}><td>${esc(c.worker)}${c.worker === t.worker ? " ✓" : ""}</td><td class="n">${fmt(c.wait_ms, 1)}</td><td class="n">${fmt(c.transfer_ms, 1)}</td><td class="n">${fmt(c.exec_ms, 1)}</td><td class="n">${fmt(c.finish_ms, 1)}</td></tr>`).join("")
      + `</tbody></table></div><p class="sub" style="margin-top:6px">ms, predicted. EFT picks the earliest predicted finish; the remote candidate pays the modelled link transfer.</p>`;
  } else if (v.scheduler === B4 && t.worker) {
    html += `<p class="sub" style="margin-top:8px">B4 makes no prediction: it binds the task to an idle worker in priority order P → E → R.</p>`;
  }
  host.innerHTML = html;
}

/* replay scrubber */
$("#t-slider").addEventListener("input", (e) => { S.t = (+e.target.value / 1000) * S.tEnd; S.playing = false; $("#play").textContent = "Play"; drawWorkflow(); });
$("#play").addEventListener("click", () => {
  if (S.playing) { S.playing = false; $("#play").textContent = "Play"; return; }
  S.playing = true; $("#play").textContent = "Pause";
  if (S.t >= S.tEnd - 1e-6) S.t = 0;
  const dur = 9000, t0 = performance.now(), start = S.t;
  const tick = (now) => {
    if (!S.playing) return;
    S.t = Math.min(S.tEnd, start + ((now - t0) / dur) * S.tEnd);
    drawWorkflow();
    if (S.t < S.tEnd) requestAnimationFrame(tick); else { S.playing = false; $("#play").textContent = "Play"; }
  };
  requestAnimationFrame(tick);
});

/* source toggle & live runs */
function setSource(live) {
  $("#src-replay").setAttribute("aria-pressed", String(!live));
  $("#src-live").setAttribute("aria-pressed", String(live));
  $("#replay-controls").hidden = live; $("#live-controls").hidden = !live;
  if (!live) loadReplay(); else fillPrevLive();
}
async function fillPrevLive() {
  try {
    const lv = await api("/api/live");
    S.liveRuns = lv.runs;
    $("#lv-prev").innerHTML = `<option value="">previous live run…</option>` + lv.runs.filter((r) => r.state === "done").map((r) =>
      `<option value="${esc(r.session)}">${esc(sessionDate(r.session))} · ${esc((POL[r.policy] || {}).short || r.policy)} · k=${esc(r.k)} · ${fmt(r.makespan_ms, 0)} ms · ${esc((r.verification || {}).match || "")}</option>`).join("");
  } catch (e) { $("#lv-msg").textContent = e.message; }
}
async function openLive(session) {
  const info = (S.liveRuns || []).find((r) => r.session === session) || (await api("/api/live")).runs.find((r) => r.session === session);
  if (!info) { $("#lv-msg").textContent = `no live run ${session}`; return; }
  stopLivePoll();
  S.mode = "live"; setModeBadge();
  S.liveStatus = info; S.key = { session, run: info.run, live: true, k: info.k }; S.sel = null;
  try {
    S.view = await api(`/api/run?session=${encodeURIComponent(session)}&run=${encodeURIComponent(info.run)}`);
    S.tEnd = endTime(S.view); S.t = S.tEnd;
  } catch (e) { S.view = null; $("#lv-msg").textContent = e.message; }
  drawWorkflow();
}
$("#lv-prev").addEventListener("change", (e) => { if (e.target.value) openLive(e.target.value); });
$("#src-replay").addEventListener("click", () => setSource(false));
$("#src-live").addEventListener("click", () => setSource(true));

$("#lv-start").addEventListener("click", async () => {
  const btn = $("#lv-start"); btn.disabled = true; $("#lv-msg").textContent = "";
  try {
    const r = await api("/api/live/start", { method: "POST",
      headers: { "Content-Type": "application/json", "X-CAO-Token": document.querySelector('meta[name="cao-token"]').content },
      body: JSON.stringify({ policy: $("#lv-pol").value, k: +$("#lv-k").value }) });
    S.mode = "live"; setModeBadge();
    S.key = { session: r.session, run: r.run, live: true, k: +$("#lv-k").value };
    S.view = null; S.sel = null; S.liveStatus = { state: "starting" };
    drawWorkflow(); startLivePoll();
  } catch (e) { $("#lv-msg").textContent = e.message; btn.disabled = false; }
});
function stopLivePoll() { if (S.livePoll) clearInterval(S.livePoll); S.livePoll = null; }
function startLivePoll() {
  stopLivePoll();
  const poll = async () => {
    try {
      const lv = await api("/api/live");
      S.liveStatus = lv.active;
      try {
        const v = await api(`/api/run?session=${encodeURIComponent(S.key.session)}&run=${encodeURIComponent(S.key.run)}`);
        S.view = v; S.tEnd = endTime(v); S.t = S.tEnd;
      } catch (e) { /* log not created yet: workers still starting */ }
      const st = lv.active.state;
      const finished = !lv.active.process_running && ["done", "failed", "refused"].includes(st);
      if (finished || (!lv.active.process_running && lv.active.exit_code != null)) {
        stopLivePoll(); $("#lv-start").disabled = false;
        if (st !== "done") $("#lv-msg").textContent = lv.active.message || `live run ended: ${st} (exit ${lv.active.exit_code})`;
      }
      drawWorkflow();
    } catch (e) { $("#lv-msg").textContent = e.message; }
  };
  poll(); S.livePoll = setInterval(poll, 400);
}

/* ================= 3. SCHEDULING COMPARISON ================= */
function chartFrame(W, H, m) { return { W, H, m, iw: W - m.l - m.r, ih: H - m.t - m.b }; }
function axisY(root, f, y, ticks, label, fmtT = (v) => v) {
  for (const v of ticks) {
    const yy = y(v);
    svg("line", { x1: f.m.l, x2: f.W - f.m.r, y1: yy, y2: yy, class: "grid-line" }, root);
    txt(root, f.m.l - 6, yy + 3.5, fmtT(v), { "text-anchor": "end", class: "axis-label" });
  }
  if (label) txt(root, f.m.l, f.m.t - 8, label, { class: "axis-label" });
}
function xCats(root, f, levels, xc) {
  svg("line", { x1: f.m.l, x2: f.W - f.m.r, y1: f.H - f.m.b, y2: f.H - f.m.b, class: "axis-line" }, root);
  levels.forEach((L) => txt(root, xc(L.k), f.H - f.m.b + 16, `k = ${L.k}`, { "text-anchor": "middle", style: "fill:var(--ink-2);font-weight:600" }));
}
function marker(root, shape, cx, cy, color, r = 5) {
  if (shape === "diamond") return svg("path", { d: `M${cx},${cy - r - 1} L${cx + r + 1},${cy} L${cx},${cy + r + 1} L${cx - r - 1},${cy} Z`, style: `fill:${color};stroke:var(--surface);stroke-width:2px` }, root);
  return svg("circle", { cx, cy, r, style: `fill:${color};stroke:var(--surface);stroke-width:2px` }, root);
}
function hit(root, x, y, w, h, html) {
  const r = svg("rect", { x, y, width: w, height: h, style: "fill:transparent" }, root);
  r.addEventListener("mousemove", (ev) => showTip(ev, html)); r.addEventListener("mouseleave", hideTip);
}
const legendHtml = (items) => `<div class="legend" style="margin:0 0 6px">${items.map(([c, l, shape]) => `<span><i style="background:${c};${shape === "diamond" ? "transform:rotate(45deg) scale(.8)" : "border-radius:50%"}"></i>${esc(l)}</span>`).join("")}</div>`;

function chartMakespan(levels) {
  const f = chartFrame(560, 260, { l: 52, r: 54, t: 24, b: 30 });
  const root = svg("svg", { viewBox: `0 0 ${f.W} ${f.H}`, role: "img", "aria-label": "Makespan by workload level for B4 and EFT with 95% confidence intervals" });
  const max = Math.max(...levels.flatMap((L) => [B4, EFT].map((p) => L.policy[p].makespan_ms.ci[1]))) * 1.08;
  const y = (v) => f.m.t + f.ih * (1 - v / max);
  axisY(root, f, y, [0, 250, 500, 750, 1000, 1250].filter((v) => v <= max), "ms");
  const band = f.iw / levels.length, xc = (k) => f.m.l + band * (levels.findIndex((L) => L.k === k) + 0.5);
  xCats(root, f, levels, xc);
  [B4, EFT].forEach((p, j) => {
    const off = j ? 10 : -10;
    levels.forEach((L, i) => {
      const d = L.policy[p].makespan_ms, cx = xc(L.k) + off;
      svg("line", { x1: cx, x2: cx, y1: y(d.ci[0]), y2: y(d.ci[1]), style: `stroke:${POL[p].color};stroke-width:2px` }, root);
      marker(root, POL[p].shape, cx, y(d.mean), POL[p].color);
      hit(root, cx - 9, y(d.ci[1]) - 6, 18, y(d.ci[0]) - y(d.ci[1]) + 12,
        `<b>${POL[p].label}</b> · k=${L.k}` + row("mean", `${fmt(d.mean)} ms`) + row("95% CI", `${fmt(d.ci[0])} – ${fmt(d.ci[1])}`) + row("n runs", d.n));
      if (i === levels.length - 1) txt(root, j ? cx + 10 : cx - 10, y(d.mean) + 4, POL[p].short,
        { "text-anchor": j ? "start" : "end", style: "fill:var(--ink);font-weight:650" });
    });
  });
  $("#ch-makespan").innerHTML = legendHtml([[POL[B4].color, POL[B4].label, "circle"], [POL[EFT].color, POL[EFT].label, "diamond"]]);
  $("#ch-makespan").appendChild(root);
}

function chartDots(host, levels, get, opts) {
  const f = chartFrame(560, 230, { l: 52, r: 18, t: 24, b: 30 });
  const root = svg("svg", { viewBox: `0 0 ${f.W} ${f.H}`, role: "img", "aria-label": opts.aria });
  const vals = levels.map(get).filter(Boolean);
  const lo = Math.min(0, ...vals.map((d) => d.ci[0])), hi = Math.max(0, ...vals.map((d) => d.ci[1]));
  const pad = (hi - lo) * 0.12, a = lo - pad * (lo < 0 ? 1 : 0), b = hi + pad;
  const y = (v) => f.m.t + f.ih * (1 - (v - a) / (b - a));
  const step = niceStep(b - a, 5), ticks = [];
  for (let v = Math.ceil(a / step) * step; v <= b; v += step) ticks.push(+v.toFixed(6));
  axisY(root, f, y, ticks, opts.unit, (v) => `${v}`);
  svg("line", { x1: f.m.l, x2: f.W - f.m.r, y1: y(0), y2: y(0), style: "stroke:var(--ink-2);stroke-width:1.25px" }, root);
  const band = f.iw / levels.length, xc = (k) => f.m.l + band * (levels.findIndex((L) => L.k === k) + 0.5);
  xCats(root, f, levels, xc);
  levels.forEach((L) => {
    const d = get(L); if (!d) return;
    const cx = xc(L.k);
    svg("line", { x1: cx, x2: cx, y1: y(d.ci[0]), y2: y(d.ci[1]), style: "stroke:var(--accent);stroke-width:2px" }, root);
    marker(root, "circle", cx, y(d.mean), "var(--accent)");
    txt(root, cx + 10, y(d.mean) + 4, `${sgn(d.mean)}${opts.suffix}`, { style: "fill:var(--ink);font-weight:600" });
    hit(root, cx - 10, y(d.ci[1]) - 6, 20, y(d.ci[0]) - y(d.ci[1]) + 12,
      `<b>k=${L.k}</b>` + row("mean", `${sgn(d.mean, 2)}${opts.suffix}`) + row("95% CI", `${sgn(d.ci[0], 2)} … ${sgn(d.ci[1], 2)}`) + row("n", d.n) + (opts.extra ? opts.extra(L) : ""));
  });
  host.innerHTML = ""; host.appendChild(root);
}

function chartRatio(levels) {
  const f = chartFrame(560, 240, { l: 52, r: 18, t: 24, b: 30 });
  const root = svg("svg", { viewBox: `0 0 ${f.W} ${f.H}`, role: "img", "aria-label": "Ratio of denoise compute time on an E-core to link transfer time, log scale" });
  const lg = (v) => Math.log2(v), a = -2, b = 7;
  const y = (v) => f.m.t + f.ih * (1 - (lg(v) - a) / (b - a));
  axisY(root, f, y, [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128], "compute ÷ transfer (log scale)", (v) => `${v}×`);
  const band = f.iw / levels.length, xc = (k) => f.m.l + band * (levels.findIndex((L) => L.k === k) + 0.5);
  xCats(root, f, levels, xc);
  svg("line", { x1: f.m.l, x2: f.W - f.m.r, y1: y(1), y2: y(1), style: "stroke:var(--ink);stroke-width:1.5px" }, root);
  txt(root, f.m.l + 4, y(1) - 6, "compute = transfer", { "text-anchor": "start", style: "fill:var(--ink);font-weight:600" });
  txt(root, f.W - f.m.r - 4, y(1) + 16, "below: transfer dominates", { "text-anchor": "end", class: "axis-label" });
  levels.forEach((L) => {
    const s = L.stages.img_denoise, r = s.kernel_over_transfer; if (!r) return;
    const cx = xc(L.k), w = Math.min(46, band * 0.42), y0 = y(1), y1 = y(r);
    svg("rect", { x: cx - w / 2, y: Math.min(y0, y1), width: w, height: Math.max(1, Math.abs(y1 - y0)), rx: 4, style: "fill:var(--accent)" }, root);
    txt(root, cx, r >= 1 ? y1 - 6 : y1 + 14, `${fmt(r, r < 10 ? 2 : 1)}×`, { "text-anchor": "middle", style: "fill:var(--ink);font-weight:650" });
    hit(root, cx - w / 2, Math.min(y0, y1) - 4, w, Math.abs(y1 - y0) + 8, `<b>k=${L.k} · denoise</b>`
      + row("E-core kernel", `${fmt(s.kernel_ms.E, 2)} ms`) + row("link transfer", `${fmt(s.transfer_ms && s.transfer_ms.mean, 2)} ms`)
      + row("ratio", `${fmt(r, 2)}×`) + row("transfer n runs", s.transfer_ms ? s.transfer_ms.n : "–"));
  });
  $("#ch-ratio").innerHTML = ""; $("#ch-ratio").appendChild(root);
}

function chartPlace(levels) {
  const f = chartFrame(560, 230, { l: 52, r: 18, t: 24, b: 30 });
  const root = svg("svg", { viewBox: `0 0 ${f.W} ${f.H}`, role: "img", "aria-label": "Remote placements per run by policy and workload level" });
  const max = Math.max(...levels.flatMap((L) => [B4, EFT].map((p) => L.policy[p].tasks_per_run.R))) * 1.25;
  const y = (v) => f.m.t + f.ih * (1 - v / max);
  axisY(root, f, y, [0, 1, 2, 3, 4, 5].filter((v) => v <= max), "remote tasks per run");
  const band = f.iw / levels.length, xc = (k) => f.m.l + band * (levels.findIndex((L) => L.k === k) + 0.5);
  xCats(root, f, levels, xc);
  const bw = Math.min(30, band * 0.28);
  levels.forEach((L) => [B4, EFT].forEach((p, j) => {
    const v = L.policy[p].tasks_per_run.R, x0 = xc(L.k) + (j ? 1 : -bw - 1);
    svg("rect", { x: x0, y: y(v), width: bw, height: Math.max(1, y(0) - y(v)), rx: 4, style: `fill:${POL[p].color}` }, root);
    hit(root, x0, y(v) - 4, bw, y(0) - y(v) + 4, `<b>${POL[p].label}</b> · k=${L.k}` + row("remote per run", fmt(v, 1))
      + row("remote total (10 runs)", L.policy[p].remote_total) + row("P / E per run", `${fmt(L.policy[p].tasks_per_run.P, 1)} / ${fmt(L.policy[p].tasks_per_run.E, 1)}`));
  }));
  $("#ch-place").innerHTML = legendHtml([[POL[B4].color, POL[B4].label, "circle"], [POL[EFT].color, POL[EFT].label, "circle"]]);
  $("#ch-place").appendChild(root);
}

function drawComparison() {
  const c = S.cmp; if (!c) return;
  const L = c.levels;
  $("#cmp-source").innerHTML = `Accepted, verified sessions only (${L.map((x) => `k=${x.k}: <code>${esc(x.session)}</code>`).join(", ")}). Read from <code>${esc(c.source)}</code>. No value on this screen comes from a new run.`;
  const pcts = L.map((x) => x.pct), allAbove = pcts.every((p) => p.ci[0] > 0);
  const ratios = L.map((x) => [x.k, x.stages.img_denoise.kernel_over_transfer]);
  const dom = ratios.filter(([, r]) => r < 1).map(([k, r]) => `k=${k} (${fmt(r, 2)}×)`);
  const rem = L.map((x) => x.stages.img_denoise.remote_minus_E_ms).filter(Boolean);
  $("#cmp-take").innerHTML = [
    ["EFT_E1_rc vs B4 makespan", `${sgn(Math.min(...pcts.map((p) => p.mean)))}% to ${sgn(Math.max(...pcts.map((p) => p.mean)))}%`,
      `EFT slower at all ${L.length} levels${allAbove ? "; every 95% CI lies above 0, but the lower bounds are close to 0" : ""}. No speed-up is claimed.`],
    ["Transfer vs compute (denoise)", dom.length ? `transfer dominates at ${dom.join(", ")}` : "compute dominates at every level",
      `Ratio grows from ${fmt(ratios[0][1], 2)}× (k=${ratios[0][0]}) to ${fmt(ratios[ratios.length - 1][1], 1)}× (k=${ratios[ratios.length - 1][0]}). Bytes moved do not depend on k.`],
    ["Remote path vs local E-core, per task", `${sgn(Math.min(...rem.map((d) => d.mean)))} to ${sgn(Math.max(...rem.map((d) => d.mean)))} ms`,
      "The remote path was slower per task at every level, because the simulated remote worker is an E-core of this same CPU."],
  ].map(([l, v, n]) => `<div class="tile"><div class="label">${esc(l)}</div><div class="value" style="font-size:19px">${esc(v)}</div><div class="note" style="color:var(--ink-2);font-size:12px">${esc(n)}</div></div>`).join("");
  chartMakespan(L);
  chartDots($("#ch-pct"), L, (x) => ({ mean: x.pct.mean, ci: x.pct.ci, n: 10 }), {
    unit: "% (EFT vs B4)", suffix: "%", aria: "Paired makespan change of EFT versus B4 with 95% CI",
    extra: (x) => row("bootstrap CI", `${sgn(x.pct.boot_ci[0], 1)} … ${sgn(x.pct.boot_ci[1], 1)}%`) + row("pairs EFT slower", `${x.pairs_eft_slower}/10`) });
  chartRatio(L);
  chartDots($("#ch-remote"), L, (x) => x.stages.img_denoise.remote_minus_E_ms, { unit: "ms per task", suffix: " ms",
    aria: "Remote path minus local E-core time per denoise task with 95% CI" });
  chartPlace(L);
  const r0 = ratios[0], rN = ratios[ratios.length - 1];
  $("#cmp-explain").innerHTML = `
    <p class="callout">At k=${r0[0]} a denoise task computes in ${fmt(L[0].stages.img_denoise.kernel_ms.E, 2)} ms on an E-core but needs ${fmt(L[0].stages.img_denoise.transfer_ms && L[0].stages.img_denoise.transfer_ms.mean, 2)} ms on the link, so <strong>transfer dominates</strong>. At k=${rN[0]} compute (${fmt(L[L.length - 1].stages.img_denoise.kernel_ms.E, 1)} ms) dwarfs transfer (${fmt(L[L.length - 1].stages.img_denoise.transfer_ms && L[L.length - 1].stages.img_denoise.transfer_ms.mean, 2)} ms).</p>
    <ul class="tight">
      <li>EFT_E1_rc uses the remote worker only when its own model predicts an earlier finish: ${L.map((x) => `${fmt(x.policy[EFT].tasks_per_run.R, 1)}`).join(" → ")} remote tasks per run across k, versus ${L.map((x) => `${fmt(x.policy[B4].tasks_per_run.R, 1)}`).join(" → ")} for greedy B4.</li>
      <li>Even when compute dominates, offloading cannot win per task here: the remote node is the same E-core silicon, so it adds a worker but not faster compute. A real break-even needs a remote device that computes faster than the link costs.</li>
      <li>No local-only condition was run, so the application-level benefit of offloading is <strong>not established</strong>.</li>
      <li>Limitations: each level is a separate session (time, temperature and free RAM differed), so compare policies within a level only. B4 ran first in 8 of 10 pairs at every level (fixed order seed). The remote path is simulated, not physical hardware.</li>
    </ul>`;
  $("#cmp-methods").textContent = `Methods: ${c.methods.unit}; per-policy CI: ${c.methods.per_policy_ci}; paired CI: ${c.methods.paired_ci}; across levels: ${c.methods.cross_k}.`;
  const ci = (d, digits = 1) => d ? `${fmt(d.mean, digits)} [${fmt(d.ci[0], digits)}, ${fmt(d.ci[1], digits)}]` : "–";
  $("#cmp-table").innerHTML = `<table class="data"><thead><tr><th>k</th><th class="n">B4 makespan ms</th><th class="n">EFT makespan ms</th><th class="n">EFT−B4 ms (paired t)</th><th class="n">EFT vs B4 %</th><th class="n">bootstrap %</th><th class="n">remote tasks B4 / EFT</th><th class="n">denoise kernel P / E / R ms</th><th class="n">denoise transfer ms</th><th class="n">decision µs B4 / EFT</th><th class="n">runs verified</th></tr></thead><tbody>`
    + L.map((x) => { const s = x.stages.img_denoise; return `<tr><td>${x.k}</td><td class="n">${ci(x.policy[B4].makespan_ms)}</td><td class="n">${ci(x.policy[EFT].makespan_ms)}</td><td class="n">${ci(x.diff_ms)}</td><td class="n">${sgn(x.pct.mean)} [${sgn(x.pct.ci[0])}, ${sgn(x.pct.ci[1])}]</td><td class="n">[${sgn(x.pct.boot_ci[0])}, ${sgn(x.pct.boot_ci[1])}]</td><td class="n">${x.policy[B4].remote_total} / ${x.policy[EFT].remote_total}</td><td class="n">${fmt(s.kernel_ms.P, 2)} / ${fmt(s.kernel_ms.E, 2)} / ${fmt(s.kernel_ms.R, 2)}</td><td class="n">${ci(s.transfer_ms, 2)}</td><td class="n">${fmt(x.policy[B4].decision_us.mean)} / ${fmt(x.policy[EFT].decision_us.mean)}</td><td class="n">${x.verification.final_output_exact_vs_reference}/20</td></tr>`; }).join("")
    + `</tbody></table>`;
}

/* ================= 4. HARDWARE EXPANSION ================= */
function cellStatus(s) {
  const t = String(s || "").replace(/\*/g, "").trim().toLowerCase();
  if (t.startsWith("yes")) return ["good", "✓"];
  if (t === "no" || t.startsWith("not ") || t.startsWith("no ") || t.includes("not verified")) return ["crit", "✕"];
  return ["warn", "◐"];
}
function drawHardware() {
  const hw = S.hw, sys = S.sys; if (!hw) return;
  const topo = (sys && sys.topology) || null;
  const eW = topo ? topo.e_core_slots.filter((x) => x !== S.nodeCore) : [];
  const W = 980, H = 400, root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": "Intended architecture: laptop with coordinator, P and E worker pools and a simulated remote node; Raspberry Pi and NVIDIA T4 not yet connected" });
  const box = (x, y, w, h, cls, title, lines, mark) => {
    svg("rect", { x, y, width: w, height: h, rx: 10, class: `box ${cls}` }, root);
    txt(root, x + 14, y + 22, title, { class: "title" });
    lines.forEach((l, i) => txt(root, x + 14, y + 40 + i * 15, l, { class: "t2" }));
    if (mark) {
      const [cls2, sym] = mark;
      const col = cls2 === "good" ? "var(--good)" : cls2 === "warn" ? "var(--warning)" : "var(--muted)";
      svg("circle", { cx: x + w - 18, cy: y + 17, r: 9, style: `fill:${col}` }, root);
      txt(root, x + w - 18, y + 21, sym, { "text-anchor": "middle", style: `fill:${cls2 === "warn" ? "#0b0b0b" : "#fff"};font-weight:800;font-size:11px` });
    }
  };
  svg("rect", { x: 10, y: 10, width: 560, height: 380, rx: 14, class: "box real", style: "fill:transparent" }, root);
  txt(root, 28, 36, "Laptop · Intel Core i5-1235U (earlier machine, historical data)", { class: "title" });
  txt(root, 28, 54, "runtime, schedulers and application: implemented, executed and verified here", { class: "t2" });
  box(30, 72, 250, 84, "", "Coordinator + remote proxy", [`LP ${topo ? topo.coordinator_core : "?"} (reserved core)`, "B4 greedy · EFT_E1_rc scheduler", "event log, artifact store"], ["good", "✓"]);
  box(300, 72, 250, 84, "", "P-core pool", [`${topo ? topo.p_core_slots.length : "?"} workers · LP ${topo ? topo.p_core_slots.join(", ") : "?"}`, "local stage execution"], ["good", "✓"]);
  box(300, 172, 250, 84, "", "E-core pool", [`${eW.length} workers · LP ${eW.join(", ")}`, "local stage execution"], ["good", "✓"]);
  box(30, 172, 250, 84, "", "lan_1g link shim (software)", ["injected latency + bandwidth", "real bytes over a local socket"], ["warn", "◐"]);
  box(30, 280, 250, 92, "", "Remote node R0 (simulated)", [`node process on LP ${S.nodeCore ?? "?"} (an E-core)`, "real remote code path,", "same silicon as the E pool"], ["warn", "◐"]);
  svg("path", { d: "M155,156 L155,172", class: "wire" }, root);
  svg("path", { d: "M155,256 L155,280", class: "wire" }, root);
  box(680, 40, 280, 130, "ghost", "Raspberry Pi · pool R_PI", ["ARM CPU over a real network", "node + connect-to-host: implemented", "NOT run on a Pi · NOT validated", "no metrics (not connected)"], ["none", "○"]);
  box(680, 220, 280, 140, "ghost", "NVIDIA T4 · pool R_T4", ["CUDA img_edges variant: implemented", "NOT executed (no GPU here)", "NOT validated", "no GPU metrics (not connected)"], ["none", "○"]);
  svg("path", { d: "M570,150 C620,150 630,105 680,105", class: "wire ghost" }, root);
  svg("path", { d: "M570,230 C620,230 630,290 680,290", class: "wire ghost" }, root);
  txt(root, 625, 195, "real network", { "text-anchor": "middle", class: "t2" });
  txt(root, 625, 210, "(not executed)", { "text-anchor": "middle", class: "t2" });
  $("#arch").innerHTML = ""; $("#arch").appendChild(root);
  $("#arch-legend").innerHTML = `<span class="status good"><span class="ic">✓</span>executed &amp; verified on this laptop</span>
    <span class="status warn"><span class="ic">◐</span>software shim / simulated</span>
    <span class="status none"><span class="ic">○</span>implemented in code, not tested on hardware</span>`;
  $("#hw-src").innerHTML = `Parsed live from <code>${esc(hw.source)}</code> (${esc(hw.heading || "")}).`;
  $("#hw-table").innerHTML = `<table class="data"><thead><tr><th>item</th><th>implemented</th><th>executed</th><th>verified</th></tr></thead><tbody>`
    + hw.rows.map((r) => `<tr><td>${esc(r.item.replace(/`/g, ""))}<div class="sub" style="margin:2px 0 0">${esc((r.notes || "").replace(/\*/g, ""))}</div></td>`
      + ["implemented", "executed", "verified"].map((k) => { const [c, s] = cellStatus(r[k]); return `<td><span class="status ${c}"><span class="ic">${s}</span>${esc(String(r[k]).replace(/\*/g, ""))}</span></td>`; }).join("") + `</tr>`).join("")
    + `</tbody></table>`;
  drawWhy();
}
function drawWhy() {
  const c = S.cmp; if (!c) return;
  const rows = c.levels.map((L) => {
    const s = L.stages.img_denoise, t = s.transfer_ms && s.transfer_ms.mean;
    const need = s.kernel_ms.E + s.io_ms.E - t - s.io_ms.R; // remote kernel budget for per-task break-even
    return `<tr><td>${L.k}</td><td class="n">${fmt(s.kernel_ms.E, 2)}</td><td class="n">${fmt(s.kernel_ms.R, 2)}</td><td class="n">${fmt(t, 2)}</td><td class="n">${need > 0 ? `≤ ${fmt(need, 1)}` : "impossible"}</td></tr>`;
  }).join("");
  $("#hw-why").innerHTML = `
    <p>The present remote worker is an E-core of this laptop, so its measured compute matches the local E-cores. It can show that the remote code path works, but not whether offloading pays off. Denoise stage, per task, mean of the accepted sessions:</p>
    <div class="table-wrap"><table class="data"><thead><tr><th>k</th><th class="n">local E-core ms</th><th class="n">simulated remote ms</th><th class="n">link ms</th><th class="n">break-even remote kernel ms</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="sub" style="margin-top:8px">Break-even = local E-core (kernel + I/O) − (transfer + remote I/O), from the accepted sessions' measured means. This is an <strong>estimate</strong>: it assumes a device keeps this machine's I/O and shim link costs, which real hardware will not. Measuring them is exactly what the devices are for.</p>
    <ul class="tight">
      <li><strong>Raspberry Pi</strong> (slower ARM CPU, real network): tests whether EFT_E1_rc correctly <em>avoids</em> a slow device, and gives real link costs instead of the shim.</li>
      <li><strong>NVIDIA T4</strong> (CUDA stage): the only planned device that could compute faster than an E-core. It tests whether offloading pays for its transfer at the heavier workload levels.</li>
      <li>Neither result exists yet. No hardware numbers are shown or implied.</li>
    </ul>`;
}

/* ================= 5. MONTAGE & GPU WORKLOADS (read-only) ================= */
/* Only function declarations here (no top-level const): showTab() may call mgInit() before this point is reached. */
function mgCol(p) { return ["P", "E", "R"].includes(p) ? `var(--pool-${p})` : "var(--accent)"; }
async function mgInit() {
  if (S.mg) return;
  S.mg = { runs: [], data: {} };
  try {
    S.mg.runs = await api("/api/montage/runs");
    $("#mg-kind").addEventListener("change", mgFill);
    $("#mg-a").addEventListener("change", mgDraw);
    $("#mg-b").addEventListener("change", mgDraw);
    mgFill();
  } catch (e) { $("#mg-msg").textContent = e.message; }
}
function mgFill() {
  const gpu = $("#mg-kind").value === "gpu";
  const rs = S.mg.runs.filter((r) => (r.kind === "montage") !== gpu && r.has_log)
    .sort((a, b) => String(a.instance).localeCompare(String(b.instance)) || String(a.id).localeCompare(String(b.id)));
  const opt = (r) => `<option value="${esc(r.id)}">${esc(r.instance || "")} · ${esc(r.condition)} · ${fmt(r.makespan_ms, 0)} ms · ${r.output_ok ? "output ok" : "output NOT verified"}${r.warmup ? " · warm-up" : ""}</option>`;
  $("#mg-a").innerHTML = rs.map(opt).join("");
  $("#mg-b").innerHTML = `<option value="">none</option>` + rs.map(opt).join("");
  $("#mg-msg").textContent = rs.length ? "" : "No runs with an event log found for this workload.";
  $("#mg-gpu").hidden = !gpu;
  if (gpu) mgGpu();
  mgDraw();
}
async function mgGet(id) {
  if (!S.mg.data[id]) S.mg.data[id] = await api(`/api/montage/run?id=${encodeURIComponent(id)}`);
  return S.mg.data[id];
}
async function mgDraw() {
  const ids = [$("#mg-a").value, $("#mg-b").value].filter(Boolean);
  const host = $("#mg-runs");
  if (!ids.length) { host.innerHTML = ""; return; }
  try {
    const ds = await Promise.all(ids.map(mgGet));
    const tEnd = Math.max(1, ...ds.map((d) => d.view.finished ? d.view.finished.makespan_ms : d.view.now_ms || 0));
    host.innerHTML = ds.map((d, i) => `<div class="card" id="mg-card-${i}"></div>`).join("");
    if (ds.length > 1 && ds[0].run.instance !== ds[1].run.instance)
      $("#mg-msg").textContent = "Warning: the two runs are of different instances; makespans are not comparable.";
    else $("#mg-msg").textContent = "";
    ds.forEach((d, i) => mgRun($(`#mg-card-${i}`), d, tEnd, i));
  } catch (e) { $("#mg-msg").textContent = e.message; }
}
function mgRun(host, d, tEnd, i) {
  const v = d.view, r = d.run, f = v.finished || {}, ver = d.verification || {};
  if (!v.started) { host.innerHTML = `<p class="empty">Event log has no run_started event.</p>`; return; }
  const chips = Object.entries(f.tasks_per_pool || {}).map(([p, n]) => `<span class="chip"><i style="background:${mgCol(p)}"></i>${esc(p)} ${n}</span>`).join(" ");
  const verd = ver.verdict ? Object.entries(ver.verdict).map(([k, x]) => `${esc(k)}: ${esc(x)}`).join("<br>") : "";
  const ok = ver.passed === true;
  host.innerHTML = `<h2>${esc(r.condition)} <span class="sub">${esc(r.instance || "")}</span></h2>
    <dl class="kv">
      <dt>Policy</dt><dd>${esc(v.scheduler)}${v.estimator ? ` · <span class="mono">${esc(v.estimator)}</span>` : ""}</dd>
      <dt>Evidence label</dt><dd>${esc(r.evidence_label)}${r.warmup ? " (warm-up block)" : ""}</dd>
      <dt>Status</dt><dd>${esc(f.status || "in progress")}${d.error ? ` — ${esc(d.error)}` : ""}</dd>
      <dt>Makespan</dt><dd class="num">${f.makespan_ms != null ? `${fmt(f.makespan_ms, 1)} ms` : "–"}</dd>
      <dt>Placement</dt><dd>${chips || "–"} of ${esc(v.n_tasks)} tasks</dd>
      <dt>Sum of task times</dt><dd class="num">${fmt(f.total_kernel_ms, 1)} ms · scheduling ${fmt(f.scheduling_ms, 2)} ms</dd>
      <dt>Output check</dt><dd><span class="status ${ok ? "good" : "crit"}"><span class="ic">${ok ? "✓" : "!"}</span>${ver.passed == null ? "not verified" : ok ? "hashes match reference" : "hash check FAILED"}</span>
        ${verd ? `<div class="sub mono">${verd}</div>` : ""}<div class="sub">event log SHA-256 ${ver.log_sha256_ok ? "matches the manifest" : "does NOT match the manifest"}</div></dd></dl>
    <h3>DAG by ${v.extcmd ? "transformation" : "stage"}</h3><div class="svg-wrap" id="mg-dag-${i}"></div>
    <h3>Timeline per worker</h3><div class="svg-wrap" id="mg-tl-${i}"></div>
    <h3>Per ${v.extcmd ? "transformation" : "stage"}</h3><div class="table-wrap">${mgStageTable(d)}</div>
    <h3>Tasks</h3><div class="table-wrap">${mgTaskTable(v)}</div>`;
  mgDag($(`#mg-dag-${i}`, host), d);
  mgTimeline($(`#mg-tl-${i}`, host), v, tEnd);
}
function mgStageTable(d) {
  return `<table class="data"><thead><tr><th>${d.view.extcmd ? "transformation" : "stage"}</th><th class="n">tasks</th><th>pools</th><th class="n">Σ task ms</th><th class="n">mean queue wait ms</th></tr></thead><tbody>`
    + d.stages.map((s) => `<tr><td>${esc(s.stage)}</td><td class="n">${s.n}</td><td>${Object.entries(s.pools).map(([p, n]) => `${esc(p)} ${n}`).join(", ")}</td><td class="n">${fmt(s.kernel_ms, 1)}</td><td class="n">${fmt(s.queue_wait_ms / s.n, 1)}</td></tr>`).join("") + `</tbody></table>`;
}
function mgTaskTable(v) {
  const wk = Object.fromEntries(v.workers.map((w) => [w.id, w]));
  const cap = 300;
  return `<table class="data"><thead><tr><th>task</th><th>${v.extcmd ? "transformation" : "stage"}</th><th>eligible</th><th>pool / worker</th><th>device</th><th class="n">ready</th><th class="n">queue wait</th><th class="n">start</th><th class="n">end</th><th class="n">run ms</th></tr></thead><tbody>`
    + v.tasks.slice(0, cap).map((t) => { const c = (wk[t.worker] || {}).capabilities || {};
      return `<tr><td>${esc(t.id)}</td><td>${esc(t.stage)}</td><td>${esc((t.eligible || ["any"]).join(","))}</td><td>${esc(t.pool || "–")} / ${esc(t.worker || "–")}</td><td>${esc(c.cuda ? (c.cuda_device || "cuda") : t.pool ? "cpu" : "–")}</td><td class="n">${fmt(t.t_ready, 1)}</td><td class="n">${fmt(t.queue_wait_ms, 1)}</td><td class="n">${fmt(t.t_started, 1)}</td><td class="n">${fmt(t.t_completed, 1)}</td><td class="n">${fmt(t.kernel_ms, 1)}</td></tr>`; }).join("")
    + `</tbody></table>` + (v.tasks.length > cap ? `<p class="sub">First ${cap} of ${v.tasks.length} tasks shown.</p>` : "");
}
function mgDag(host, d) {
  const cw = 150, bw = 128, bh = 36, gap = 10, top = 6;
  const levels = [...new Set(d.stages.map((s) => s.level))].sort((a, b) => a - b);
  const rows = Math.max(...levels.map((l) => d.stages.filter((s) => s.level === l).length));
  const root = svg("svg", { viewBox: `0 0 ${levels.length * cw + 8} ${top * 2 + rows * (bh + gap)}`, role: "img",
    "aria-label": "DAG aggregated by transformation: one box per transformation, edge labels count task dependencies" });
  const pos = {};
  levels.forEach((l, c) => d.stages.filter((s) => s.level === l).forEach((s, i) => { pos[s.stage] = { x: 4 + c * cw, y: top + i * (bh + gap) }; }));
  for (const e of d.edges) {
    const a = pos[e.from], b = pos[e.to]; if (!a || !b || e.from === e.to) continue;
    const x1 = a.x + bw, y1 = a.y + bh / 2, x2 = b.x, y2 = b.y + bh / 2, mx = (x1 + x2) / 2;
    svg("path", { d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, class: "dag-edge" }, root);
    txt(root, mx, (y1 + y2) / 2 - 2, `×${e.n}`, { "text-anchor": "middle", class: "axis-label" });
  }
  for (const s of d.stages) {
    const p = pos[s.stage], main = Object.entries(s.pools).sort((a, b) => b[1] - a[1])[0];
    const g = svg("g", { class: "dag-node" }, root);
    svg("rect", { x: p.x, y: p.y, width: bw, height: bh, rx: 4, style: `fill:var(--surface);stroke:${mgCol(main && main[0])};stroke-width:2px` }, g);
    txt(g, p.x + 6, p.y + 15, s.stage, { style: "fill:var(--ink);font-weight:650" });
    txt(g, p.x + 6, p.y + 29, `${s.n} task${s.n > 1 ? "s" : ""} · Σ ${fmt(s.kernel_ms, 0)} ms`, { class: "axis-label" });
  }
  host.innerHTML = ""; host.appendChild(root);
}
function mgTimeline(host, v, tEnd) {
  const L = 92, R = 12, T = 8, rowH = 22, W = 960, H = T + v.workers.length * rowH + 26;
  const x = (ms) => L + (ms / tEnd) * (W - L - R);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Per-worker timeline of task executions" });
  const step = niceStep(tEnd, 8);
  for (let s = 0; s <= tEnd + 1e-9; s += step) {
    svg("line", { x1: x(s), x2: x(s), y1: T, y2: T + v.workers.length * rowH, class: "grid-line" }, root);
    txt(root, x(s), H - 12, `${Math.round(s)}`, { "text-anchor": "middle", class: "axis-label" });
  }
  txt(root, W - R, H - 1, "ms since run start (same axis for compared runs)", { "text-anchor": "end", class: "axis-label" });
  v.workers.forEach((w, i) => {
    const y = T + i * rowH;
    txt(root, 8, y + rowH / 2 + 4, `${w.id} [${w.pool}]`, { style: "fill:var(--ink-2);font-weight:600" });
    for (const t of v.tasks.filter((tt) => tt.worker === w.id && tt.t_started != null)) {
      const bw = Math.max(1.5, x(t.t_completed) - x(t.t_started));
      const r = svg("rect", { x: x(t.t_started), y: y + 3, width: bw, height: rowH - 6, rx: 2, style: `fill:${mgCol(w.pool)}` }, root);
      if (bw > 40) txt(root, x(t.t_started) + 3, y + rowH / 2 + 3.5, t.stage, { style: "fill:#fff;font-size:9.5px;font-weight:650;pointer-events:none" });
      r.addEventListener("mousemove", (ev) => showTip(ev, `<b>${esc(t.id)}</b> · ${esc(t.stage)}` + row("worker", esc(w.id)) + row("queue wait", `${fmt(t.queue_wait_ms, 1)} ms`)
        + row("start → end", `${fmt(t.t_started, 1)} → ${fmt(t.t_completed, 1)} ms`)));
      r.addEventListener("mouseleave", hideTip);
    }
  });
  host.innerHTML = ""; host.appendChild(root);
}
async function mgGpu() {
  const h = $("#mg-gpu");
  try {
    const g = await api("/api/gpu"), e = g.env || {};
    h.innerHTML = `<h2>CPU vs CUDA, per stage <span class="sub">(median of ${esc((g.rows[0] || {}).reps)} reps)</span></h2>
      <p class="sub">Source <code>${esc(g.source)}</code> · ${esc(e.gpu)} · torch ${esc(e.torch)} / CUDA ${esc(e.torch_cuda)} · driver ${esc(e.driver)} · ${esc(e.date)}. Verdict is the spike's own (speed-up and numerical equivalence within the stage tolerance).</p>
      <div class="table-wrap"><table class="data"><thead><tr><th>stage</th><th>params</th><th class="n">side</th><th class="n">CPU ms</th><th class="n">CUDA ms</th><th class="n">speed-up</th><th>equivalent</th><th class="n">max abs diff</th><th>verdict</th></tr></thead><tbody>`
      + g.rows.map((r) => `<tr><td>${esc(r.stage)}</td><td class="mono">${esc(r.params)}</td><td class="n">${esc(r.side)}</td><td class="n">${fmt(r.cpu_ms, 3)}</td><td class="n">${fmt(r.gpu_ms, 3)}</td><td class="n">${fmt(r.speedup, 2)}×</td><td><span class="status ${r.equivalent ? "good" : "crit"}"><span class="ic">${r.equivalent ? "✓" : "✕"}</span>${r.equivalent ? "yes" : "NO"}</span></td><td class="n">${esc(r.max_abs)}</td><td>${esc(r.verdict)}</td></tr>`).join("")
      + `</tbody></table></div>`;
  } catch (err) { h.innerHTML = `<p class="empty">${esc(err.message)}</p>`; }
}

/* ================= boot ================= */
async function refreshSystem() {
  try { S.sys = await api("/api/system"); drawOverview(); } catch (e) { $("#ov-status").innerHTML = `<dt>Error</dt><dd>${esc(e.message)}</dd>`; }
}
async function boot() {
  $("#foot").innerHTML = "Read-only views of: event logs (<code>data/events</code>), run artifacts (<code>data/artifacts</code>), the Phase B result summary and <code>docs/REMOTE_DEVICES.md</code>. Live runs write only to <code>data/dashboard_runs</code>.";
  try {
    [S.sessions, S.cmp, S.hw] = await Promise.all([api("/api/sessions"), api("/api/comparison"), api("/api/hardware")]);
    S.nodeCore = S.sessions.length ? S.sessions[0].node_core : null;
  } catch (e) { document.querySelector("main").insertAdjacentHTML("afterbegin", `<div class="banner"><strong>Error loading data:</strong> ${esc(e.message)}</div>`); }
  await refreshSystem();
  setInterval(refreshSystem, 2000);
  fillReplaySelectors();
  await loadReplay();
  const guard = (name, fn) => { try { fn(); } catch (e) { console.error(name, e); const h = document.querySelector(`#screen-${name}`); if (h) h.insertAdjacentHTML("afterbegin", `<div class="banner"><strong>Render error:</strong> ${esc(e.message)}</div>`); } };
  if (S.view) guard("overview", () => drawRemote(S.view, `worker_ready event of ${S.key.session}/${S.key.run}`));
  guard("compare", drawComparison);
  guard("hardware", drawHardware);
  const m = /^#live=([A-Za-z0-9_.-]+)$/.exec(location.hash);
  if (m) { showTab("workflow"); setSource(true); await openLive(m[1]); }
}
boot();
