p = "build_review2.py"
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)


def label_before(call_start, key):
    global s
    i = s.index(call_start)
    k = s.rfind("\n", 0, i) + 1
    s = s[:k] + f'd.nextlabel = "{key}"\n' + s[k:]


label_before('d.figure(FIG + r"\\fig_architecture.png"', "arch")
label_before('d.figure(FIG + r"\\fig_dose_heavy.png"', "dose")
label_before('d.figure(FIG + r"\\fig_per_order.png"', "perorder")
label_before('d.table("Confirmatory contrasts fixed in the protocol', "conf")
rep("The proposal extends the redone runtime (Fig. 4):", "The proposal extends the redone runtime (@fig:arch):")
rep("is largest when few chains are heavy (Fig. 3).", "is largest when few chains are heavy (@fig:dose).")
open(p, "w", encoding="utf-8").write(s)
print("r2b ok")
