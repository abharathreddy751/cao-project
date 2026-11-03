"""Offline release bundle of the submission (source incl. dashboards v2/v3, tests, docs, final-study evidence, all deliverables). Reads only; writes one zip."""
import os
import zipfile
from pathlib import Path

ROOT = Path(r"D:\cao project")
OUT = ROOT / "SUBMISSION_FINAL" / "GITHUB_RELEASE_PACKAGE" / "cao_release_bundle_submission_20261103.zip"
OUT.parent.mkdir(exist_ok=True)
INCLUDE_DIRS = ["src", "scripts", "tests", "docs", "config", "manifests", "data/results/final_20261101", "data/results/overnight_20261027", "publications", "SUBMISSION_FINAL"]
ROOT_FILES = [p.name for p in ROOT.iterdir() if p.is_file() and (p.suffix in {".md", ".csv", ".toml", ".txt"} or p.name == ".gitignore")]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", "_wordtest", ".venv", ".git", "GITHUB_RELEASE_PACKAGE"}
SKIP_SUFFIX = {".pyc", ".zip"}
n = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for name in ROOT_FILES:
        z.write(ROOT / name, name)
        n += 1
    for d in INCLUDE_DIRS:
        for dp, dn, fn in os.walk(ROOT / d):
            dn[:] = [x for x in dn if x not in SKIP_PARTS]
            for f in fn:
                p = Path(dp) / f
                if p.suffix in SKIP_SUFFIX:
                    continue
                z.write(p, p.relative_to(ROOT).as_posix())
                n += 1
print("files", n, "zip MB", round(OUT.stat().st_size / 1e6, 1))
