"""``python -m caosched.dashboard [--port 8765] [--open]``"""
import argparse

from caosched.dashboard.server import serve

ap = argparse.ArgumentParser(description="CAO demonstration dashboard (local only)")
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--open", action="store_true", help="open the dashboard in the default browser")
args = ap.parse_args()
serve(args.port, args.open)
