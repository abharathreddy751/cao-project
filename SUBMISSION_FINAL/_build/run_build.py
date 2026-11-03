"""Two-pass build of one document: pass 1 collects figure/table/section numbers (no PDF), pass 2 resolves @fig:/@tab:/@sec: and exports the PDF through Word.
usage: run_build.py build_review3.py [...]"""
import os
import subprocess
import sys

PY = r"D:\cao project\.venv\Scripts\python.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
for script in sys.argv[1:]:
    env = dict(os.environ, CAO_NOPDF="1")
    r1 = subprocess.run([PY, "-W", "ignore", script], cwd=HERE, env=env, capture_output=True, text=True)
    if r1.returncode:
        print(script, "pass 1 failed:\n", r1.stderr[-1500:])
        continue
    env.pop("CAO_NOPDF")
    r2 = subprocess.run([PY, "-W", "ignore", script], cwd=HERE, env=env, capture_output=True, text=True)
    print(script, (r2.stdout.strip().splitlines() or [""])[-1], r2.stderr[-800:] if r2.returncode else "")
