import io

B = r"D:\cao project\SUBMISSION_FINAL\_build"
G = "Guide: Dr. Yokesh Babu S, Associate Professor Grade 1"


def sub(fname, old, new):
    p = B + "\\" + fname
    s = io.open(p, encoding="utf-8").read()
    assert old in s, (fname, old[:50])
    io.open(p, "w", encoding="utf-8", newline="").write(s.replace(old, new, 1))


sub("build_demo_deck_final.py", '"Computer Architecture and Organization",\n                            "Measured on one laptop (RTX 3050',
    '"Computer Architecture and Organization | ' + G + '",\n                            "Measured on one laptop (RTX 3050')
sub("build_video_script.py", "(26MAI0058) | Version of 3 November 2026", "(26MAI0058) | " + G + " | Version of 3 November 2026")
print("ok")
