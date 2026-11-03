p = "ieee_docx2.py"
s = open(p, encoding="utf-8").read()
# 'nextlabel': d.nextlabel = "key" before d.h1/h2/figure/table gives that element a label
for sig in ("    def h1(self, text, label=None):\n", "    def h2(self, text, label=None):\n"):
    assert sig in s
    s = s.replace(sig, sig + "        label = label or getattr(self, 'nextlabel', None)\n        self.nextlabel = None\n", 1)
sig = "    def figure(self, path, caption, width_in=3.4, span=False, label=None):\n"
assert sig in s
s = s.replace(sig, sig + "        label = label or getattr(self, 'nextlabel', None)\n        self.nextlabel = None\n", 1)
i = s.index("def table(self, caption, header, rows, widths_in")
j = s.index("\n", i)
s = s[:j + 1] + "        label = label or getattr(self, 'nextlabel', None)\n        self.nextlabel = None\n" + s[j + 1:]
open(p, "w", encoding="utf-8").write(s)
print("ok")
