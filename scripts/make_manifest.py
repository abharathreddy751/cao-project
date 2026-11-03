"""SHA-256 manifest of an evidence directory, and verification.

  python scripts/make_manifest.py DIR [--out FILE] [--force]   # writes DIR/SHA256_MANIFEST.tsv; refuses to overwrite it without --force
  python scripts/make_manifest.py DIR --verify [--manifest FILE]   # exit 1 on any changed/missing/extra file
"""
import argparse
import json
import sys

from caosched.experiment.manifest import build_manifest, sha256_file, verify_manifest

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--verify", action="store_true")
ap.add_argument("--out")
ap.add_argument("--manifest")
ap.add_argument("--force", action="store_true", help="overwrite an existing manifest (default: refuse)")
a = ap.parse_args()
if a.verify:
    r = verify_manifest(a.dir, a.manifest)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
try:
    p = build_manifest(a.dir, a.out, force=a.force)
except FileExistsError as exc:
    sys.exit(f"refusing to overwrite {exc.filename} (use --force)")
print(f"{p}  sha256={sha256_file(p)}")
