"""Fills in the faculty guide named by the user (3 Nov 2026). Institution and e-mail stay placeholders: the user has not given them."""
import io

B = r"D:\cao project\SUBMISSION_FINAL\_build"
G = "Dr. Yokesh Babu S, Associate Professor Grade 1"


def sub(fname, old, new, count=1):
    p = B + "\\" + fname
    s = io.open(p, encoding="utf-8").read()
    assert s.count(old) >= 1, (fname, old[:60])
    s = s.replace(old, new) if count == 0 else s.replace(old, new, count)
    io.open(p, "w", encoding="utf-8", newline="").write(s)


OLD_AFF = "[Institution, department, guide and e-mail to be filled by the authors]"
NEW_AFF = "Guide: " + G + ". [Institution, department and e-mail to be filled by the authors]"
for f in ("build_review1.py", "build_review2.py", "build_review3.py", "build_paper_final.py"):
    sub(f, OLD_AFF, NEW_AFF)

sub("build_report_final.py", 'r.center("Guide: [name and designation to be filled by the authors]", 11, after=2)',
    'r.center("Guide: ' + G + '", 11, after=2)')
sub("build_plan.py", "[guide to be confirmed]",
    "guide Dr. Yokesh Babu S, Associate Professor Grade 1 (whether the guide is a co-inventor depends on his contribution to the inventive concept and is for the IPR cell to decide)")
sub("build_plan.py", '["Institution, department", "[to be filled]"],',
    '["Guide / supervisor", "Dr. Yokesh Babu S, Associate Professor Grade 1"],\n         ["Institution, department", "[to be filled]"],')
print("ok")
