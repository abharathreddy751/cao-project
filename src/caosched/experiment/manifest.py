"""SHA-256 manifest of an evidence directory (same TSV format as manifests/stage0_*/data_sha256.tsv:
columns relpath, size, mtime_ns, sha256; '/' separators) and verification.

``verify`` compares size + sha256 (mtime is informational) and reports changed,
missing and extra files.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

NAME = "SHA256_MANIFEST.tsv"
HEADER = "relpath\tsize\tmtime_ns\tsha256"


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path, skip: str):
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = Path(dp) / fn
            rel = p.relative_to(root).as_posix()
            if rel != skip:
                yield rel, p


def build_manifest(root, out=None, force: bool = False) -> Path:
    """Write the manifest (default <root>/SHA256_MANIFEST.tsv, excluded from itself); returns its path.
    Refuses (FileExistsError) to overwrite an existing manifest unless ``force``: it is evidence."""
    root = Path(root)
    out = Path(out) if out else root / NAME
    skip = out.relative_to(root).as_posix() if out.is_relative_to(root) else ""
    lines = [HEADER]
    for rel, p in sorted(_files(root, skip)):
        st = p.stat()
        lines.append(f"{rel}\t{st.st_size}\t{st.st_mtime_ns}\t{sha256_file(p)}")
    with open(out, "w" if force else "x", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return out


def verify_manifest(root, manifest=None) -> dict:
    root = Path(root)
    manifest = Path(manifest) if manifest else root / NAME
    skip = manifest.relative_to(root).as_posix() if manifest.is_relative_to(root) else ""
    rows = [ln.split("\t") for ln in manifest.read_text(encoding="utf-8").splitlines()[1:] if ln]
    expected = {r[0]: (int(r[1]), r[3]) for r in rows}
    missing, changed = [], []
    for rel, (size, digest) in expected.items():
        p = root / rel
        if not p.is_file():
            missing.append(rel)
        elif p.stat().st_size != size or sha256_file(p) != digest:
            changed.append(rel)
    extra = sorted(rel for rel, _ in _files(root, skip) if rel not in expected)
    return {"ok": not (missing or changed or extra), "n_checked": len(expected), "missing": missing,
            "changed": changed, "extra": extra, "manifest_sha256": sha256_file(manifest)}
