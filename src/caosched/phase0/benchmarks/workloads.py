"""CPU-bound benchmark workloads for Phase 0.

Each workload is split into ``prepare(size, seed) -> inputs`` and
``run(inputs) -> None``. Only ``run`` is timed by the harness -- separating
input generation from the timed region keeps the measured "execution time"
attributable to the actual compute kernel (BLAS matmul, Pillow's C-level blur,
zlib's C-level compression), not to Python-level synthetic-input generation.

``size`` means something different per workload (documented on each function):
matrix dimension for matmul, image side length for image_filter, payload byte
count for compression. The benchmark CSV always records ``workload`` alongside
``size`` so this is never ambiguous downstream.

Callers running these in a subprocess MUST call
``caosched.util.threadpin.pin_single_thread()`` before numpy is imported in
that process (see ``caosched.phase0.benchmarks.worker``), otherwise BLAS may
spawn its own thread pool and contaminate P-vs-E / load-level comparisons.
"""
from __future__ import annotations

import dataclasses
import random
import zlib
from typing import Any, Callable


@dataclasses.dataclass(frozen=True)
class Workload:
    name: str
    prepare: Callable[[int, int], Any]
    run: Callable[[Any], None]


def _prepare_matmul(size: int, seed: int) -> Any:
    """``size`` = matrix dimension N; prepares two NxN float64 matrices."""
    import numpy as np

    rng = np.random.default_rng(seed)
    a = rng.standard_normal((size, size))
    b = rng.standard_normal((size, size))
    return (a, b)


def _run_matmul(inputs: Any) -> None:
    a, b = inputs
    result = a @ b
    _ = float(result[0, 0])


def _prepare_image_filter(size: int, seed: int) -> Any:
    """``size`` = image side length in pixels; prepares a synthetic size x size RGB image."""
    from PIL import Image

    rng = random.Random(seed)
    pixel_bytes = rng.randbytes(size * size * 3)
    return Image.frombytes("RGB", (size, size), pixel_bytes)


def _run_image_filter(img: Any) -> None:
    from PIL import ImageFilter

    blurred = img.filter(ImageFilter.GaussianBlur(radius=3))
    _ = blurred.getpixel((0, 0))


def _prepare_compression(size: int, seed: int) -> Any:
    """``size`` = payload length in bytes. Uses a repeated random chunk (not
    pure random bytes) so the payload is realistically compressible -- pure
    random data is zlib's adversarial worst case and not representative.
    """
    rng = random.Random(seed)
    chunk = rng.randbytes(4096)
    repeats = size // len(chunk) + 1
    return (chunk * repeats)[:size]


def _run_compression(payload: Any) -> None:
    compressed = zlib.compress(payload, level=6)
    _ = len(compressed)


WORKLOADS: dict[str, Workload] = {
    "matmul": Workload("matmul", _prepare_matmul, _run_matmul),
    "image_filter": Workload("image_filter", _prepare_image_filter, _run_image_filter),
    "compression": Workload("compression", _prepare_compression, _run_compression),
}
