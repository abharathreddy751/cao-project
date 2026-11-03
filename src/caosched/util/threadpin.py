"""Pin numerical libraries to a single thread before numpy is imported.

Must be called at the very top of any process entry point, before ``import
numpy`` or anything that transitively imports it -- otherwise the BLAS library
has already read these environment variables at its own init time and this has
no effect. This exists because the benchmark harness needs single-threaded,
affinity-pinned execution to attribute measured time to a specific core; a BLAS
library that silently spawns its own thread pool would contaminate every P-vs-E
and load-level comparison the harness makes.
"""
from __future__ import annotations

import os

_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


def pin_single_thread() -> None:
    for var in _THREAD_ENV_VARS:
        os.environ[var] = "1"
