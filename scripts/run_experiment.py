"""Run a pre-registered design as interleaved seeded blocks (Stage 4).

  python scripts/run_experiment.py --design designs/montage_main.json --out data/experiments \
         --adapter mypkg.mymodule:make_adapter [--session-id S]
  python scripts/run_experiment.py --design d.json --out <tmp> --adapter stub    # synthetic dry run, label 'plan'

``--adapter module:factory`` is imported and called with no arguments; it must return an object with
``run_one(condition, workdir, seed) -> RunRecord`` (and optionally ``verify``) -- see
``caosched.experiment.design`` for the contract. Exit code 2 if the session aborted (e.g. memory preflight). An exception that escapes the runner
leaves ``session.json`` with status 'crashed' (the analysis then excludes that session). Optional design field
``run_timeout_s``: each run is executed in a child process and killed on expiry (status 'timeout'); the adapter
must then be picklable (see ``caosched.experiment.runner.run_session``).
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

from caosched.experiment.runner import run_session


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--design", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--session-id")
    a = ap.parse_args(argv)
    if a.adapter == "stub":
        from caosched.experiment.stub import StubAdapter
        adapter = StubAdapter()
    else:
        mod, _, fn = a.adapter.partition(":")
        adapter = getattr(importlib.import_module(mod), fn)()
    s = run_session(a.design, a.out, adapter, session_id=a.session_id)
    print(json.dumps(s, indent=2))
    return 0 if s["status"] == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
