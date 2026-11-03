"""Second pass of the dashboard v2 build: brings text and widgets that described the earlier study up to the final study (new files only;
the originals in src/caosched/dashboard are untouched). Run by scripts/dashboard_v2_build.py. Every replacement must match exactly or the build stops."""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "src" / "caosched" / "dashboard_v2" / "static"


def rep(s: str, old: str, new: str) -> str:
    if old not in s:
        raise SystemExit("patch target not found: " + old[:70])
    return s.replace(old, new, 1)


h = (D / "index.html").read_text(encoding="utf-8")
h = rep(h, "Base framework demonstration. Tabs 1-4 replay historical data from an earlier laptop (Intel Core i5-1235U, 2 P-cores + 8 E-cores); tab 5 shows the Stage 4 Montage and GPU runs recorded on an Intel Core i5-13500HX with an RTX 3050. Every number on these screens is read from event logs, artifacts or verified result files.",
        "Dashboard v2. Tab 3 (top) and the GPU table in tab 5 show the FINAL benchmark (static vs dynamic scheduling, P/E cores + RTX 3050 CUDA worker, Intel Core i5-13500HX). Tab 2 replays accepted runs from an earlier laptop (i5-1235U) and its Run Live button uses the earlier demo setup (B4 or EFT_E1_rc, P/E cores + a simulated remote worker). Every number on these screens is read from event logs, artifacts or verified result files.")
h = rep(h, '<div id="wf-banner" class="banner" style="margin:14px 0 0"></div>',
        '<p class="sub" style="margin:10px 0 0"><strong>Scope of this screen:</strong> replay of accepted runs from the earlier image-pipeline demo, and Run Live with B4 or EFT_E1_rc on P/E cores plus a simulated remote worker (no GPU worker, no PRED/HEFT here). The final benchmark with the RTX 3050 is on tab 3 and tab 5.</p>\n      <div id="wf-banner" class="banner" style="margin:14px 0 0"></div>')
h = rep(h, '<option value="gpu">GPU workload</option>', '<option value="gpu">GPU / study runs (incl. final benchmark sessions)</option>')
h = rep(h, '<label>Run <select id="mg-a"></select></label>',
        '<label>Filter <input id="mg-filter" placeholder="e.g. PRED_RANK_GREEDY_E2E_ext" size="30"></label>\n        <label>Run <select id="mg-a"></select></label>')
(D / "index.html").write_text(h, encoding="utf-8")

# tab 1: the Raspberry Pi stays as "NOT CONNECTED"; the remote T4 card is removed; the local GPU reads CONNECTED (live nvidia-smi check)
h = (D / "index.html").read_text(encoding="utf-8")
NL = chr(10)
a = h.index('      <div class="card">' + NL + '        <h2>Remote NVIDIA T4')
END = "      </div>" + NL
b = h.index(END, a) + len(END)
h = h[:a] + h[b:]
h = rep(h, '<span class="badge sim" style="margin-left:6px"><span class="dot"></span>USED IN THE FINAL BENCHMARK</span>',
        '<span id="ov-gpu-badge" class="badge live" style="margin-left:6px"><span class="dot"></span>CONNECTED</span>')
h = rep(h, "No Raspberry Pi or NVIDIA T4 is connected.", "No Raspberry Pi is connected. The laptop's own RTX 3050 is connected as a local CUDA worker (used in the final benchmark; the live demo on screen 2 uses P, E and the simulated remote worker).")
(D / "index.html").write_text(h, encoding="utf-8")

j = (D / "app.js").read_text(encoding="utf-8")
j, n = re.subn(r"<dt>Scheduling policies</dt><dd>.*?</dd>",
               "<dt>Scheduling policies</dt><dd>Live demo (this dashboard): B4 greedy and EFT_E1_rc. Final benchmark (tab 3, stored): dynamic B4, B4_param_first, PRED_RANK_GREEDY, PRED_RANK_GREEDY_E2E versus static HEFT, PEFT, HEFT_E2E and HEFT_oracle (reference), in CPU-only and RTX 3050 GPU configurations</dd>",
               j, count=1, flags=re.S)
if n != 1:
    raise SystemExit("scheduling policies row not found")
j = rep(j, "Laptop · Intel Core i5-1235U (earlier machine, historical data)", "Laptop · Intel Core i5-13500HX + RTX 3050 (this machine)")
j = rep(j, '"B4 greedy · EFT_E1_rc scheduler"', '"B4, EFT, PRED, HEFT/PEFT policies"')
i = j.index('box(300, 172, 250, 84, "", "E-core pool"')   # the call in drawHardware (the string also occurs earlier, in a comment)
e = j.index("\n", i)
j = j[:e] + '\n  box(300, 280, 250, 92, "", "Local GPU · CUDA worker G", ["NVIDIA RTX 3050 6 GB (PyTorch CUDA)", "executed in the final benchmark", "not in the live demo pool"], ["good", "✓"]);' + j[e:]
j = rep(j, 'if ($("#ov-gpu")) $("#ov-gpu").innerHTML =', 'if ($("#ov-gpu-badge")) { const ok = !!(sys.gpu && sys.gpu.available); $("#ov-gpu-badge").className = "badge " + (ok ? "live" : "off"); $("#ov-gpu-badge").innerHTML = `<span class="dot"></span>${ok ? "CONNECTED" : "NOT DETECTED"}`; }\n  if ($("#ov-gpu")) $("#ov-gpu").innerHTML =')
j = rep(j, "Denoise stage, per task, mean of the accepted sessions:", "Denoise stage, per task, mean of the accepted sessions (earlier machine, historical):")
j = rep(j, "<strong>NVIDIA T4</strong> (CUDA stage): the only planned device that could compute faster than an E-core.",
        "<strong>Remote NVIDIA T4</strong> (CUDA stage): the only planned remote device that could compute faster than an E-core (the laptop's own RTX 3050 has already been measured, see tab 5).")
j = rep(j, "<li>Neither result exists yet. No hardware numbers are shown or implied.</li>",
        "<li>Neither the Raspberry Pi nor the remote T4 result exists yet; no remote-hardware numbers are shown or implied. The local RTX 3050 is a separate case: executed in the final benchmark (tab 3, tab 5).</li>")
j = rep(j, '$("#mg-kind").addEventListener("change", mgFill);',
        '$("#mg-kind").addEventListener("change", mgFill);\n    $("#mg-kind").value = "gpu";\n    $("#mg-filter").addEventListener("input", mgFill);')
j = rep(j, 'const rs = S.mg.runs.filter((r) => (r.kind === "montage") !== gpu && r.has_log)',
        'const q = ($("#mg-filter") ? $("#mg-filter").value.trim().toLowerCase() : "");\n  const rs = S.mg.runs.filter((r) => (r.kind === "montage") !== gpu && r.has_log && (!q || `${r.condition} ${r.instance} ${r.session}`.toLowerCase().includes(q)))')
j = rep(j, "<tr><th>stage</th><th>params</th>", "<tr><th>record</th><th>stage</th><th>params</th>")
j = rep(j, "<tr><td>${esc(r.stage)}</td><td class=\"mono\">${esc(r.params)}</td>", "<tr><td>${esc(r.record || \"\")}</td><td>${esc(r.stage)}</td><td class=\"mono\">${esc(r.params)}</td>")
j = rep(j, '<p class="sub">Source <code>', '<p class="sub">512 px rows of the two records the final benchmark used (an earlier spike on 128 and 256 px images found the GPU slower, so those sizes are not used). Source <code>')
(D / "app.js").write_text(j, encoding="utf-8")
print("patched final-study text and widgets")
