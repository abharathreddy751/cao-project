"""Stage 4 experiment tooling: pre-registered design, interleaved seeded blocks,
per-run manifests, memory preflight, evidence-directory manifests.

``design``   -- design file, deterministic block plan, RunRecord / Adapter protocol.
``stub``     -- synthetic adapter for tests and dry runs (label forced to 'plan').
``runner``   -- session runner (preflight, environment manifest, run dirs, manifests).
``manifest`` -- SHA-256 manifest of an evidence directory (+ verify).
"""
