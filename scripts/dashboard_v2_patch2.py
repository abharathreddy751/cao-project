"""Third pass of the dashboard v2 build (run after dashboard_v2_patch.py): tab 4 drops the remote NVIDIA T4 box ("not connected") and its wire,
keeps the Raspberry Pi box as "not connected", and describes the laptop's own RTX 3050 as connected. New files only."""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "src" / "caosched" / "dashboard_v2" / "static"


def rep(s: str, old: str, new: str) -> str:
    if old not in s:
        raise SystemExit("patch2 target not found: " + old[:70])
    return s.replace(old, new, 1)


def drop_line(s: str, prefix: str) -> str:
    i = s.index(prefix)
    return s[:i] + s[s.index("\n", i) + 1:]


j = (D / "app.js").read_text(encoding="utf-8")
j = drop_line(j, 'box(680, 220, 280, 140, "ghost", "NVIDIA T4')
j = drop_line(j, 'svg("path", { d: "M570,230 C620,230 630,290 680,290"')
j = rep(j, "Raspberry Pi and NVIDIA T4 not yet connected", "Raspberry Pi not yet connected; the laptop's RTX 3050 is a connected local CUDA worker")
j, n1 = re.subn(r"<li><strong>Remote NVIDIA T4</strong>.*?</li>",
                "<li><strong>Local RTX 3050</strong> (CUDA worker G): connected and used in the final benchmark; its measured speed-ups are on tab 5. A remote GPU is not part of this project.</li>", j, count=1, flags=re.S)
j, n2 = re.subn(r"<li>Neither the Raspberry Pi nor the remote T4 result exists yet.*?</li>",
                "<li>The Raspberry Pi result does not exist yet; no remote-hardware numbers are shown or implied. The local RTX 3050 is a separate case: connected and executed in the final benchmark (tab 3, tab 5).</li>", j, count=1, flags=re.S)
if n1 != 1 or n2 != 1:
    raise SystemExit(f"tab 4 bullets not found ({n1}, {n2})")
(D / "app.js").write_text(j, encoding="utf-8")

h = (D / "index.html").read_text(encoding="utf-8")
h, n3 = re.subn(r'<p class="lede">The target system adds a Raspberry Pi.*?</p>',
                '<p class="lede">The target system adds a Raspberry Pi (slow ARM CPU over a real network) as an additional remote pool, through the existing proxy/node interface and without changing the scheduler. The laptop\'s own RTX 3050 is already connected as a local CUDA worker. This screen separates what runs today from what is only implemented in code.</p>',
                h, count=1, flags=re.S)
if n3 != 1:
    raise SystemExit("tab 4 lede not found")
(D / "index.html").write_text(h, encoding="utf-8")
print("tab 4: T4 box removed, Pi kept as not connected, local GPU described as connected")
