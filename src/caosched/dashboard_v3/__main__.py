"""``python -m caosched.dashboard_v3 [--port 8769] [--open] [--events-dir DIR ...]``"""
import argparse
from pathlib import Path

from caosched.dashboard import data
from caosched.dashboard_v3 import live3
from caosched.dashboard_v3.server import serve

ap = argparse.ArgumentParser(description="CAO dashboard v3 (local only)")
ap.add_argument("--port", type=int, default=8769)
ap.add_argument("--open", action="store_true")
ap.add_argument("--events-dir", action="append", default=[], metavar="DIR")
args = ap.parse_args()
(live3.DASH3 / "sessions").mkdir(parents=True, exist_ok=True)
data.EXTRA_ROOTS.append((live3.DASH3 / "sessions").resolve())  # live runs of tab 6 are read back through their run manifests
data.EXTRA_ROOTS.extend(Path(d).resolve() for d in args.events_dir)
serve(args.port, args.open)
