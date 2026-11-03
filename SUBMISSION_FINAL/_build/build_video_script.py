"""10: demo video script and shot list (the recording itself must be made by the authors)."""
import sys
sys.path.insert(0, r"D:\cao project\SUBMISSION_FINAL\_build")
from report_docx1 import Report
from ieee_docx2 import export_pdf

OUT = r"D:\cao project\SUBMISSION_FINAL\_draft"
r = Report(11)
r.center("", 12, after=14)
r.center("Project Demo Video: Script and Shot List", 22, bold=True, after=6)
r.center("Static versus dynamic task scheduling on a hybrid CPU/GPU machine", 12, italic=True, after=4)
r.center("Lakshay S (26MAI0064), Arkkadu Bharath Reddy (26MAI0058) | Guide: Dr. Yokesh Babu S, Associate Professor Grade 1 | Version of 3 November 2026", 10, after=12)
r.para("**Why this document exists.** The course asks for a video recording of the project demo (YouTube or Google Drive link). A video cannot be produced by the assistant; this script lets the authors record it in one take of about 8 minutes. "
       "Nothing here was recorded or uploaded, and no link exists yet.")
r.chapter("Before recording", new_page=False)
r.numbered([
    "Close other programs; free RAM must be at least 2.4 GB if the live run on screen 6 is shown (Docker Desktop and WSL use a lot: run `docker desktop stop` and `wsl --shutdown` first). Plug in the charger.",
    "Open a PowerShell window in `D:\\cao project`. Start the dashboard: `.\\.venv\\Scripts\\python.exe -m caosched.dashboard_v3 --port 8770 --events-dir data\\results\\final_20261101\\eval\\sessions --open` (use another port if 8770 is busy).",
    "Open `SUBMISSION_FINAL\\04_Project_Demo_Existing_vs_Proposed.pdf` or the .pptx in a second window.",
    "Record the screen with Windows Game Bar (Win+G, Record) or OBS Studio at 1080p with microphone. Rehearse once; a live run takes 1 to 2 minutes, so start it early or cut the waiting in editing.",
    "Do not show the repository on a public site or any private data; the video itself must not be uploaded publicly before the IPR decision (use *unlisted* on YouTube or a Drive link restricted to the course).",
])
r.chapter("Shot list and narration (about 8 minutes)")
r.table("Timed script",
        ["Time", "Screen", "Say"],
        [["0:00", "slide 1 (title)", "We compare static scheduling, where a plan is made before the run, with dynamic scheduling, where decisions are made while running, on one laptop with P cores, E cores and an RTX 3050 GPU. Everything shown is measured on this machine; the remote worker is emulated and the Raspberry Pi is not tested."],
         ["0:30", "slide 2, 3", "A workflow is a graph of tasks. The base idea B4 gives each ready task to the first idle worker it can run on. It keeps workers busy but is blind to task cost."],
         ["1:15", "slide 4, 5", "Our proposal: order ready tasks by predicted upward rank and give a task only to an idle worker with the least predicted time. HEFT and PEFT are the static plans, built from the same cost model. The GPU is used only for stages where we measured a speed-up."],
         ["2:15", "slide 6 (architecture)", "One cost model and one GPU table feed both families. The coordinator, event log and workers are shared, so the comparison is fair. The end-to-end time counts planning and start-up."],
         ["3:00", "slide 7, 8", "On the main workload, the dynamic dispatcher is 17.8% faster than blind dispatch on the CPU and 21.2% with the GPU, and 5.2% and 12.2% faster than the static HEFT plan. Ten contrasts were fixed before the data and Holm-corrected."],
         ["4:00", "slide 9, 10", "The gain depends on how much task cost varies: about 40% with four heavy chains, small with many heavy chains, none when all tasks cost the same. The GPU helps the dispatcher by 2.6% to 7.5% but not blind B4. The GPU cost model has 23% to 31% error."],
         ["5:00", "slide 11", "What it does not show: a hand rule that knows the cost parameter is within 1%; a hybrid selector would gain at most 1.1%; the remote worker gave no benefit in emulation; an earlier session found HEFT level."],
         ["5:45", "browser: dashboard screen 1", "The dashboard shows the RTX 3050 as connected with live load, memory, temperature and power. The Raspberry Pi card says not connected, because it was never attached."],
         ["6:15", "dashboard screen 3", "Screen 3 shows the final results; hover a bar to see the numbers."],
         ["6:45", "dashboard screen 6", "Screen 6 runs one live block of the final benchmark. I pick PRED_RANK_GREEDY_E2E with the extended GPU set and press Run live. Phase and task count update; at the end the tasks per pool and the output check appear. This single run is a demonstration, not an experiment result."],
         ["7:45", "slide 14, 15", "Tests: 520 of 521 pass (the one failure is a test that refuses to start when free RAM is below its own gate). Next steps: a better GPU model, a second workload, the Raspberry Pi, and the IPR decision before publishing."]],
        [0.6, 1.5, 4.2], size=9)
r.chapter("After recording")
r.numbered([
    "Check audio and that no password, token or personal file is visible. The dashboard header shows a token only inside the page source, not on screen.",
    "Upload as *unlisted* (YouTube) or share a restricted Drive link; paste the link into the submission form. Do not make it public before the IPR decision.",
    "Keep the raw recording; store it outside the repository (large files).",
])
o = OUT + r"\10_Demo_Video_Script_and_Shotlist"
r.save(o + ".docx")
print("10", export_pdf(o + ".docx", o + ".pdf"))
