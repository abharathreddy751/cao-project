/* Dashboard v3, tab 6: run ONE live block of the final benchmark (final policies, CPU and RTX 3050 GPU) and show the result.
   Backend: GET /api/live3, POST /api/live3/start, GET /api/montage/run?id= (the run is read back through its run manifest).
   Uses helpers of app.js ($, esc, fmt, api, mgRun). */
(function () {
  const PNAME = { B4: "B4 (blind greedy)", B4_param_first: "B4 param-first (hand rule)", PRED_RANK_GREEDY: "PRED_RANK_GREEDY (dynamic)",
    PRED_RANK_GREEDY_E2E: "PRED_RANK_GREEDY_E2E (dynamic)", HEFT_param_model: "HEFT (static plan)", PEFT_param_model: "PEFT (static plan)",
    HEFT_E2E: "HEFT_E2E (static plan)", HEFT_ORACLE_REF: "HEFT oracle (static, reference only)" };
  const CNAME = { cpu: "CPU only (P + E cores)", gpu: "CPU + GPU, strict set", ext: "CPU + GPU, extended set" };
  const sel = $("#l3-pol"), cfg = $("#l3-cfg"), btn = $("#l3-start"), msg = $("#l3-msg");
  if (!sel) return;
  let timer = null, t0 = null, shown = null;
  fetch("/api/live3").then((r) => r.json()).then((j) => {
    sel.innerHTML = j.policies.map((p) => `<option value="${esc(p)}"${p === "PRED_RANK_GREEDY_E2E" ? " selected" : ""}>${esc(PNAME[p] || p)}</option>`).join("");
    cfg.innerHTML = j.configs.map((c) => `<option value="${esc(c)}"${c === "ext" ? " selected" : ""}>${esc(CNAME[c] || c)}</option>`).join("");
    fillPrev(j.previous);
    if (j.active && j.active.process_running) { t0 = Date.now(); poll(); }
  }).catch((e) => { msg.textContent = "live API unavailable: " + e.message; });

  function fillPrev(prev) {
    $("#l3-prev").innerHTML = `<option value="">previous live run…</option>` + (prev || []).map((p) =>
      `<option value="${esc(p.session)}">${esc(p.policy)} · ${esc(p.config)} · ${p.makespan_s != null ? Number(p.makespan_s).toFixed(2) + " s" : ""} · ${p.verified ? "output ok" : "unverified"}</option>`).join("");
    $("#l3-prev").dataset.runs = JSON.stringify(prev || []);
  }
  $("#l3-prev").addEventListener("change", async (e) => {
    const p = JSON.parse(e.target.dataset.runs || "[]").find((x) => x.session === e.target.value);
    if (p) await showRun(p.run_id, { state: "done", policy: p.policy, config: p.config, end_to_end_makespan_s: p.makespan_s, output_verified: p.verified });
  });

  btn.addEventListener("click", async () => {
    btn.disabled = true; msg.textContent = ""; shown = null; $("#l3-detail").hidden = true; $("#l3-tiles").innerHTML = "";
    try {
      await api("/api/live3/start", { method: "POST",
        headers: { "Content-Type": "application/json", "X-CAO-Token": document.querySelector('meta[name="cao-token"]').content },
        body: JSON.stringify({ policy: sel.value, config: cfg.value }) });
      t0 = Date.now(); poll();
    } catch (e) { msg.textContent = e.message; btn.disabled = false; }
  });

  /* while the run is going: phase, tasks completed (from the run's event log), live GPU load and free RAM (S.sys is refreshed every 2 s by app.js) */
  function runExtras(a, el) {
    const sys = (typeof S !== "undefined" && S.sys) || {}, g = sys.gpu || {};
    const done = a.tasks_done || 0, tot = a.n_tasks || 257, pctDone = Math.min(100, Math.round(100 * done / tot));
    const bar = (p, col) => `<div style="height:6px;background:var(--grid);border-radius:3px;margin-top:6px"><div style="height:6px;width:${p}%;background:${col};border-radius:3px"></div></div>`;
    const tile = (l, v, note, extra) => `<div class="tile"><div class="label">${esc(l)}</div><div class="value num" style="font-size:20px">${esc(v)}</div><div class="note">${esc(note || "")}</div>${extra || ""}</div>`;
    $("#l3-tiles").innerHTML = [
      tile("Phase", a.phase || a.state, `${el} s elapsed · ${PNAME[a.policy] || a.policy || ""} · ${CNAME[a.config] || ""}`),
      tile("Tasks completed", `${done} / ${tot}`, "from the run's event log", bar(pctDone, "var(--accent)")),
      tile("GPU load (live)", g.util_pct != null ? `${g.util_pct} %` : "n/a", g.mem_used_mib != null ? `${Math.round(g.mem_used_mib)} / ${g.memory_mib} MiB · ${g.temp_c != null ? g.temp_c : "n/a"} °C · ${g.power_w != null ? g.power_w : "n/a"} W` : "", bar(g.util_pct || 0, "var(--pool-E)")),
      tile("Free RAM (live)", sys.memory_available_gib != null ? `${Number(sys.memory_available_gib).toFixed(2)} GiB` : "n/a", `at start ${a.available_gib_at_start != null ? a.available_gib_at_start : "–"} GiB · ${a.mains_power === false ? "on battery" : "mains power"}`),
    ].join("");
  }
  function tiles(items) {
    $("#l3-tiles").innerHTML = items.map(([l, v, n]) => `<div class="tile"><div class="label">${esc(l)}</div><div class="value num" style="font-size:20px">${esc(v)}</div><div class="note">${esc(n || "")}</div></div>`).join("");
  }
  function poll() {
    if (timer) clearInterval(timer);
    const tick = async () => {
      let lv; try { lv = await api("/api/live3"); } catch (e) { msg.textContent = e.message; return; }
      const a = lv.active || {}, el = t0 ? Math.round((Date.now() - t0) / 1000) : 0;
      if (a.state === "starting" || a.state === "running") {
        tiles([["State", a.state, `${el} s elapsed`], ["Policy", PNAME[a.policy] || a.policy || "", CNAME[a.config] || ""],
               ["Free RAM at start", a.available_gib_at_start != null ? `${a.available_gib_at_start} GiB` : "–", a.mains_power === false ? "on battery" : "mains power"]]);
        msg.textContent = a.message || ""; runExtras(a, el);
      }
      if (!a.process_running && ["done", "failed", "refused"].includes(a.state)) {
        clearInterval(timer); timer = null; btn.disabled = false;
        if (a.state !== "done") { msg.textContent = a.message || `live run ended: ${a.state}`; tiles([["State", a.state, ""]]); return; }
        fillPrev(lv.previous);
        await showRun(a.run_id, a);
      } else if (!a.process_running && a.exit_code != null && a.state !== "done") {
        clearInterval(timer); timer = null; btn.disabled = false; msg.textContent = a.message || `process ended (exit ${a.exit_code}); see data/dashboard_runs_v3/status`;
      }
    };
    tick(); timer = setInterval(tick, 1500);
  }
  async function showRun(runId, a) {
    if (!runId || shown === runId) return; shown = runId;
    let d; try { d = await api(`/api/montage/run?id=${encodeURIComponent(runId)}`); } catch (e) { msg.textContent = "run view unavailable: " + e.message; return; }
    const f = d.view.finished || {}, pools = f.tasks_per_pool || {}, g = pools.G || 0, tot = Object.values(pools).reduce((x, y) => x + y, 0);
    const ver = d.verification || {};
    tiles([["Policy", PNAME[a.policy] || a.policy || "", CNAME[a.config] || ""],
           ["End-to-end makespan", a.end_to_end_makespan_s != null ? `${Number(a.end_to_end_makespan_s).toFixed(3)} s` : `${fmt(f.makespan_ms, 0)} ms`, "start of run to last completion (amendment F1)"],
           ["Tasks per pool", Object.entries(pools).map(([p, n]) => `${p} ${n}`).join(" · "), `of ${tot}; GPU tasks: ${g}`],
           ["Output check", ver.passed === true ? "hashes match reference" : ver.passed === false ? "FAILED" : "not verified", "GPU tasks re-run on CPU and compared"]]);
    const host = $("#l3-detail"); host.hidden = false; host.innerHTML = "";
    const tEnd = Math.max(1, f.makespan_ms || d.view.now_ms || 0);
    mgRun(host, d, tEnd, 9);
  }
})();
