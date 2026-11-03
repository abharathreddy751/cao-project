"""``python -m caosched.dashboard_v2 [--port 8766] [--open] [--events-dir DIR ...]``"""
import argparse
from pathlib import Path

from caosched.dashboard import data
from caosched.dashboard_v2.server import serve

ap = argparse.ArgumentParser(description="CAO dashboard v2 (local only)")
ap.add_argument("--port", type=int, default=8766)
ap.add_argument("--open", action="store_true")
ap.add_argument("--events-dir", action="append", default=[], metavar="DIR")
args = ap.parse_args()
data.EXTRA_ROOTS.extend(Path(d).resolve() for d in args.events_dir)
serve(args.port, args.open)
