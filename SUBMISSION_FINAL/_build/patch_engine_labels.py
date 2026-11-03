"""Adds cross-reference labels to ieee_docx2.py: d.h1(..., label=), d.h2(..., label=), d.figure(..., label=), d.table(..., label=)
and the tokens @sec:key @fig:key @tab:key in text. Two passes: the numbers of the previous pass are used (stored in _labels_<script>.json)."""
p = "ieee_docx2.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:60]
    s = s.replace(old, new, 1)


rep("        self.refs_db, self.cite_order = REFS, []\n",
    "        self.refs_db, self.cite_order = REFS, []\n"
    "        import __main__, json, os\n"
    "        self._lab_path = Path(__file__).with_name('_labels_' + Path(getattr(__main__, '__file__', 'x')).stem + '.json')\n"
    "        self.labels = {}\n"
    "        try:\n"
    "            self.prev_labels = json.loads(self._lab_path.read_text(encoding='utf-8'))\n"
    "        except (OSError, ValueError):\n"
    "            self.prev_labels = {}\n")
rep("        return re.sub(r\"\\((\\[\\d+\\](?:, \\[\\d+\\])*)\\)\", lambda m: m.group(1), out)",
    "        out = re.sub(r\"\\((\\[\\d+\\](?:, \\[\\d+\\])*)\\)\", lambda m: m.group(1), out)\n"
    "        return re.sub(r\"@(fig|tab|sec):([a-z0-9_]+)\", lambda m: self.prev_labels.get(m.group(1) + ':' + m.group(2), '??'), out)")
rep("    def h1(self, text):\n        self.sec_no += 1\n",
    "    def h1(self, text, label=None):\n        self.sec_no += 1\n        if label:\n            self.labels['sec:' + label] = ROMAN[self.sec_no - 1]\n")
rep("    def h2(self, text):\n        self.sub_no += 1\n",
    "    def h2(self, text, label=None):\n        self.sub_no += 1\n        if label:\n            self.labels['sec:' + label] = f'{ROMAN[self.sec_no - 1]}-{chr(64 + self.sub_no)}'\n")
rep("    def figure(self, path, caption, width_in=3.4, span=False):\n",
    "    def figure(self, path, caption, width_in=3.4, span=False, label=None):\n")
rep("        self.fig_no += 1\n", "        self.fig_no += 1\n        if label:\n            self.labels['fig:' + label] = str(self.fig_no)\n")
rep("def table(self, caption, header, rows, widths_in, span=False, size=7.5, bold_first_col=False, keep=None):",
    "def table(self, caption, header, rows, widths_in, span=False, size=7.5, bold_first_col=False, keep=None, label=None):")
rep("        self.tab_no += 1\n", "        self.tab_no += 1\n        if label:\n            self.labels['tab:' + label] = ROMAN[self.tab_no - 1]\n")
rep("    def save(self, path):\n",
    "    def save(self, path):\n        import json\n        self._lab_path.write_text(json.dumps(self.labels), encoding='utf-8')\n")
rep("def export_pdf(docx_path, pdf_path):\n    \"\"\"Open in Word (COM), export PDF, return (pages, words).\"\"\"\n",
    "def export_pdf(docx_path, pdf_path):\n    \"\"\"Open in Word (COM), export PDF, return (pages, words).\"\"\"\n    import os\n    if os.environ.get('CAO_NOPDF'):\n        return 0, 0\n")
open(p, "w", encoding="utf-8").write(s)
print("engine patched")
