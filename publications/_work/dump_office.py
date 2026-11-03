import openpyxl, sys
from pptx import Presentation
dl = r"C:\Users\Venkatesh\Downloads"
wb = openpyxl.load_workbook(dl + r"\AI_Heterogeneous_Computing_Literature_Survey.xlsx", data_only=True)
with open("survey_workbook.txt", "w", encoding="utf-8") as f:
    for ws in wb:
        f.write(f"\n##### SHEET {ws.title} {ws.max_row}x{ws.max_column}\n")
        for row in ws.iter_rows(values_only=True):
            if any(c is not None for c in row):
                f.write(" | ".join("" if c is None else str(c).replace("\n", " ") for c in row) + "\n")
for name in ["cao Review1.pptx", "CAO_Project_Status_Light_Modern_with_Architecture.pptx", "AI_Heterogeneous_Computing_Review1_Review1_Final.pptx"]:
    p = Presentation(dl + "\\" + name)
    with open("deck_" + name.replace(" ", "_") + ".txt", "w", encoding="utf-8") as f:
        for i, s in enumerate(p.slides, 1):
            f.write(f"\n--- slide {i}\n")
            for sh in s.shapes:
                if sh.has_text_frame:
                    f.write(sh.text_frame.text.replace("\n", " / ") + "\n")
                if getattr(sh, "has_table", False) and sh.has_table:
                    for r in sh.table.rows:
                        f.write(" | ".join(c.text.replace("\n", " ") for c in r.cells) + "\n")
print("ok")
