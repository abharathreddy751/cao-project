"""Copies the finished drafts into the one-folder submission layout. Never deletes or overwrites anything outside SUBMISSION_FINAL."""
import shutil
from pathlib import Path

ROOT = Path(r"D:\cao project")
SF = ROOT / "SUBMISSION_FINAL"
DR = SF / "_draft"
PUB = ROOT / "publications"

MAIN = ["01_Review1_Survey_IEEE", "02_Review2_BasePaper_Gaps_ProposedWork_IEEE", "03_Review3_Implementation_Results_IEEE", "05_Final_Project_Report",
        "06_Final_IEEE_Paper_Draft", "06b_Final_IEEE_Paper_Anonymous_for_Double_Blind_Review", "07_Publication_and_IPR_Plan", "08_IPR_Invention_Disclosure_Draft",
        "10_Demo_Video_Script_and_Shotlist"]
n = 0
for name in MAIN:
    for ext in (".docx", ".pdf"):
        shutil.copy2(DR / (name + ext), SF / (name + ext))
        n += 1
for ext in (".pptx", ".pdf"):
    shutil.copy2(DR / ("04_Project_Demo_Existing_vs_Proposed" + ext), SF / ("04_Project_Demo_Existing_vs_Proposed" + ext))
    shutil.copy2(PUB / ("09_Final_Static_vs_Dynamic_Demo" + ext), SF / ("09_Final_Static_vs_Dynamic_Demo" + ext))
    n += 2

# the exact files for VTOP (offline submission)
V = SF / "VTOP_UPLOAD"
V.mkdir(exist_ok=True)
MAP = [("DA1_Review1_Survey_and_Comparative_Analysis", "01_Review1_Survey_IEEE"),
       ("DA2_Review2_Base_Paper_Redo_and_Gaps", "02_Review2_BasePaper_Gaps_ProposedWork_IEEE"),
       ("DA3_Review3_Proposed_Work_Implementation", "03_Review3_Implementation_Results_IEEE"),
       ("Consolidated_Report_for_DA1_DA2_DA3", "05_Final_Project_Report"),
       ("Lab9_IPR_IDF_B_Draft", "08_IPR_Invention_Disclosure_Draft"),
       ("Lab10_IEEE_2column_Draft_14pages", "06_Final_IEEE_Paper_Draft")]
for new, old in MAP:
    for ext in (".docx", ".pdf"):
        shutil.copy2(DR / (old + ext), V / (new + ext))
        n += 1

# supporting evidence documents (copies; originals untouched)
S = SF / "supporting"
S.mkdir(exist_ok=True)
for f in ("CAO_FINAL_EXPERIMENT_REPORT.md", "RESULTS_TABLE_FINAL.csv", "RESEARCH_CLAIMS_AND_LIMITATIONS.md", "EVIDENCE_INDEX.md", "FACULTY_DEMO_CHECKLIST.md", "FACULTY_DEMO_SCRIPT.md", "PROJECT_MASTER_DOCUMENTATION.md"):
    shutil.copy2(ROOT / f, S / f)
    n += 1
FIG = SF / "figures"
FIG.mkdir(exist_ok=True)
for p in (SF / "_fig").glob("*.png"):
    shutil.copy2(p, FIG / p.name)
    n += 1
print("copied", n)
