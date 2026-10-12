"""Local demonstration dashboard (standard library HTTP server + static page).

Launch: ``python -m caosched.dashboard [--port 8765] [--open]``. See docs/DASHBOARD.md.

Montage / GPU demonstration (read-only, from existing event logs + run manifests; tab 5)::

    python -m caosched.dashboard --events-dir data/experiments --open

``--events-dir`` (repeatable) adds an experiment output dir whose ``<session>/runs/<run>/run_manifest.json`` files are
listed next to ``data/experiments`` and ``data/results``. The GPU table reads the newest
``data/results/*/gpu/**/gpu_spike.json``. Nothing is run from this tab.
"""
