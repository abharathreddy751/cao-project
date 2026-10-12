"""Re-derive reported tables from raw logs and re-check hashes; write a reproduction log.

  python scripts/reproduce_subset.py --analysis-dir analysis/montage_main --log reproduction_log.json \
         [--tables summary effects] [--rtol 1e-9]

Reads ``analysis.json`` (sessions, reference, seed) from the analysis dir, verifies every run's event-log
SHA-256 against its run manifest and the evidence-dir manifest (a missing SHA256_MANIFEST.tsv is a FAILED check), re-runs the analysis and compares
each reported CSV with the re-derived rows. Exit 0 only if everything matches.
"""
import argparse
import csv
import datetime
import json
import math
import sys
from pathlib import Path

from caosched.analysis.stats_paired import analyze
from caosched.experiment.manifest import NAME, verify_manifest


def _same(a: str, b, rtol: float) -> bool:
    b = "" if b is None else b
    try:
        return math.isclose(float(a), float(b), rel_tol=rtol, abs_tol=1e-12)
    except (TypeError, ValueError):
        return str(a) == str(b)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analysis-dir", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--tables", nargs="+", default=["summary", "effects"])
    ap.add_argument("--rtol", type=float, default=1e-9)
    a = ap.parse_args(argv)
    ad = Path(a.analysis_dir)
    meta = json.loads((ad / "analysis.json").read_text(encoding="utf-8"))
    log = {"when_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "analysis_dir": str(ad), "checks": []}
    for s in meta["paths"]:
        if (Path(s) / NAME).is_file():
            r = verify_manifest(s)
            log["checks"].append({"check": f"evidence manifest {s}", "ok": r["ok"], "detail": {k: r[k] for k in ("missing", "changed", "extra")}})
        else:  # no manifest = nothing proves the raw files are unchanged: a failed check, not a skipped one
            log["checks"].append({"check": f"evidence manifest {s}", "ok": False, "detail": f"{NAME} missing"})
    # also re-hashes every event log (log_ok)
    res = analyze(meta["paths"], meta["reference"], meta["seed"], allow_mixed_code=meta.get("allow_mixed_code", False))
    bad = [r["run_id"] for r in res["tables"]["runs"] if not r["log_ok"]]
    log["checks"].append({"check": "event-log hashes vs run manifests", "ok": not bad, "detail": bad})
    for t in a.tables:
        with (ad / f"{t}.csv").open(encoding="utf-8", newline="") as fh:
            rep = list(csv.DictReader(fh))
        new = res["tables"][t]
        diffs = []
        if len(rep) != len(new):
            diffs.append(f"row count {len(rep)} != {len(new)}")
        for i, (r, n) in enumerate(zip(rep, new)):
            diffs += [f"row {i} {k}: reported {v!r} vs derived {n.get(k)!r}" for k, v in r.items() if not _same(v, n.get(k), a.rtol)]
        log["checks"].append({"check": f"table {t} reproduced from raw logs", "ok": not diffs, "detail": diffs[:20]})
    log["ok"] = all(c["ok"] for c in log["checks"])
    Path(a.log).write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps({c["check"]: c["ok"] for c in log["checks"]}, indent=2))
    return 0 if log["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
