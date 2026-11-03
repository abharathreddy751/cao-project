"""``python -m caosched.dashboard [--port 8765] [--open] [--events-dir DIR ...]``"""
import argparse
from pathlib import Path

from caosched.dashboard import data
from caosched.dashboard.server import serve

ap = argparse.ArgumentParser(description="CAO demonstration dashboard (local only)")
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--open", action="store_true", help="open the dashboard in the default browser")
ap.add_argument("--events-dir", action="append", default=[], metavar="DIR",
                help="extra experiment output dir (holds <session>/runs/<run>/run_manifest.json); repeatable")
args = ap.parse_args()
data.EXTRA_ROOTS.extend(Path(d).resolve() for d in args.events_dir)
serve(args.port, args.open)
