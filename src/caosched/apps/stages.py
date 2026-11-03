"""Application stage registry (application-level workflows).

A stage is ``decode(list[bytes]) -> objects``, ``compute(objects, params) ->
object``, ``encode(object) -> bytes``. Only ``compute`` is timed as the
task's kernel (consistent with the project's kernel-only execution-time
definition); reading/decoding inputs and encoding/writing the output are
timed separately as I/O. Stages are pure functions of their inputs and
params, so the same stage gives the same result locally, on the remote node,
or in the single-process reference implementation.

Image-analysis stages (numpy + Pillow only, portable to an ARM device):
  img_source     deterministic synthetic scene (the application's input data)
  img_tile       crop one tile of a g x g grid
  img_denoise    Gaussian blur (Pillow), applied ``iterations`` times (default 1)
  img_edges      Sobel gradient magnitude (numpy, float32) -> uint8
  img_features   32-bin edge histogram + mean, std, edge density
  img_mosaic     stitch edge tiles back into a full edge map
  img_aggregate  global descriptor from all tile features
  img_package    zlib-compressed bundle of mosaic + descriptor (final output)

Optional device variant: ``img_edges`` with ``params["device"] == "cuda"``
uses PyTorch on a CUDA device (remote nodes, e.g. the T4 worker; see
docs/REMOTE_DEVICES.md for its verification status). Local workers never see
that flag: cpu workers run the code here, "cuda" pools run ``cuda_stages()``.
"""
from __future__ import annotations

import dataclasses
import io
import time
import zlib
from typing import Any, Callable

import numpy as np


@dataclasses.dataclass(frozen=True)
class Stage:
    name: str
    decode: Callable[[list[bytes]], list[Any]]
    compute: Callable[[list[Any], dict], Any]
    encode: Callable[[Any], bytes]


def encode_array(a: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, a, allow_pickle=False)
    return buf.getvalue()


def decode_arrays(blobs: list[bytes]) -> list[np.ndarray]:
    return [np.load(io.BytesIO(b), allow_pickle=False) for b in blobs]


def _source(_inputs, p) -> np.ndarray:
    h, w = int(p["height"]), int(p["width"])
    rng = np.random.default_rng(int(p["seed"]))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.empty((h, w, 3), dtype=np.float32)
    for ch in range(3):
        fx, fy = rng.uniform(2, 9, 2)
        img[..., ch] = 96 + 64 * np.sin(2 * np.pi * fx * xx / w) * np.cos(2 * np.pi * fy * yy / h)
    for _ in range(24):  # rectangles and discs give real edges to find
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        r = int(rng.integers(h // 32 + 1, h // 6 + 2))
        color = rng.uniform(0, 255, 3).astype(np.float32)
        if rng.random() < 0.5:
            img[max(0, cy - r):cy + r, max(0, cx - r):cx + r] = color
        else:
            m = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
            img[m] = color
    img += rng.normal(0, 8, img.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def _tile(inputs, p) -> np.ndarray:
    (img,) = inputs
    g, i = int(p["grid"]), int(p["index"])
    r, c = divmod(i, g)
    th, tw = img.shape[0] // g, img.shape[1] // g
    return np.ascontiguousarray(img[r * th:(r + 1) * th, c * tw:(c + 1) * tw])


def _denoise(inputs, p) -> np.ndarray:
    from PIL import Image, ImageFilter

    (t,) = inputs
    img = Image.fromarray(t)
    blur = ImageFilter.GaussianBlur(radius=float(p.get("radius", 2.0)))
    for _ in range(int(p.get("iterations", 1))):  # repeated smoothing: compute x k, bytes unchanged
        img = img.filter(blur)
    return np.asarray(img)


def _sobel_numpy(gray: np.ndarray) -> np.ndarray:
    g = gray
    gx = (g[:-2, 2:] + 2 * g[1:-1, 2:] + g[2:, 2:]) - (g[:-2, :-2] + 2 * g[1:-1, :-2] + g[2:, :-2])
    gy = (g[2:, :-2] + 2 * g[2:, 1:-1] + g[2:, 2:]) - (g[:-2, :-2] + 2 * g[:-2, 1:-1] + g[:-2, 2:])
    mag = np.zeros_like(g)
    mag[1:-1, 1:-1] = np.sqrt(gx * gx + gy * gy)
    return np.clip(mag / 4.0, 0, 255).astype(np.uint8)


def _sobel_cuda(gray: np.ndarray) -> np.ndarray:
    import torch  # optional dependency; only on a CUDA node (e.g. the T4 worker)

    if not torch.cuda.is_available():
        raise RuntimeError("img_edges with device=cuda requested but no CUDA device is available")
    t = torch.from_numpy(np.ascontiguousarray(gray)).to("cuda")[None, None]
    kx = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32, device="cuda")[None, None]
    ky = torch.tensor([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=torch.float32, device="cuda")[None, None]
    gx = torch.nn.functional.conv2d(t, kx)
    gy = torch.nn.functional.conv2d(t, ky)
    mag = torch.zeros_like(t)
    mag[..., 1:-1, 1:-1] = torch.sqrt(gx * gx + gy * gy)
    return torch.clamp(mag / 4.0, 0, 255).to(torch.uint8)[0, 0].cpu().numpy()


def _edges(inputs, p) -> np.ndarray:
    (t,) = inputs
    gray = t.astype(np.float32).mean(axis=2)
    return _sobel_cuda(gray) if p.get("device") == "cuda" else _sobel_numpy(gray)


def _features(inputs, _p) -> np.ndarray:
    (e,) = inputs
    hist = np.bincount((e >> 3).ravel(), minlength=32).astype(np.float64)
    hist /= hist.sum()
    return np.concatenate([hist, [e.mean(), e.std(), (e > 64).mean()]])


def _mosaic(inputs, p) -> np.ndarray:
    g = int(p["grid"])
    rows = [np.concatenate(inputs[r * g:(r + 1) * g], axis=1) for r in range(g)]
    return np.concatenate(rows, axis=0)


def _aggregate(inputs, _p) -> np.ndarray:
    f = np.stack(inputs)
    return np.concatenate([f.mean(axis=0), f.max(axis=0), f[:, -1]])


def _package(inputs, p) -> bytes:
    mosaic, desc = inputs
    head = np.array(mosaic.shape + desc.shape, dtype=np.int64).tobytes()
    return zlib.compress(head + mosaic.tobytes() + desc.astype(np.float64).tobytes(), int(p.get("level", 6)))


STAGES: dict[str, Stage] = {
    "img_source": Stage("img_source", lambda b: [], _source, encode_array),
    "img_tile": Stage("img_tile", decode_arrays, _tile, encode_array),
    "img_denoise": Stage("img_denoise", decode_arrays, _denoise, encode_array),
    "img_edges": Stage("img_edges", decode_arrays, _edges, encode_array),
    "img_features": Stage("img_features", decode_arrays, _features, encode_array),
    "img_mosaic": Stage("img_mosaic", decode_arrays, _mosaic, encode_array),
    "img_aggregate": Stage("img_aggregate", decode_arrays, _aggregate, encode_array),
    "img_package": Stage("img_package", decode_arrays, _package, lambda b: b),
}


NPY_HEADER = 128  # np.save header for these 1-3 dim uint8 / float64 arrays
_N_FEATURES = 35  # 32-bin histogram + mean, std, edge density


def stage_payload_bytes(stage: str, pixels: int) -> tuple[int, int]:
    """(input bytes, output bytes) of one stage task, from its ``size`` (pixels).
    Defined only where ``size`` determines both; fan-in stages (tile, mosaic,
    aggregate, package) raise KeyError rather than guess -- they are not
    remote-eligible in the shipped pipelines."""
    rgb, gray = pixels * 3 + NPY_HEADER, pixels + NPY_HEADER
    sizes = {"img_source": (0, rgb), "img_denoise": (rgb, rgb), "img_edges": (rgb, gray),
             "img_features": (gray, _N_FEATURES * 8 + NPY_HEADER)}
    if stage not in sizes:
        raise KeyError(f"No payload model for stage {stage!r} (input size not determined by task size)")
    return sizes[stage]


def cuda_stages() -> dict[str, Callable]:
    """CUDA variants: ``{stage name: fn(decoded inputs, params) -> output object}``,
    same signature as ``Stage.compute`` but the function does its own host/device
    copies and synchronisation, so its timing includes them. Written in
    ``caosched.apps.cuda_stages``; empty if that module or torch is missing."""
    try:
        from caosched.apps.cuda_stages import CUDA_STAGES
    except ImportError:
        return {}
    return CUDA_STAGES


def run_stage(name: str, input_blobs: list[bytes], params: dict, compute: Callable | None = None) -> tuple[bytes, float, float]:
    """Execute one stage on raw input bytes. Returns (output bytes, compute
    seconds, codec seconds). Compute is the kernel; codec = decode + encode.
    ``compute`` replaces the stage's CPU kernel (a CUDA variant on a cuda worker)."""
    st = STAGES[name]
    t0 = time.perf_counter()
    objs = st.decode(input_blobs)
    t1 = time.perf_counter()
    out = (compute or st.compute)(objs, params)
    t2 = time.perf_counter()
    blob = st.encode(out)
    t3 = time.perf_counter()
    return blob, t2 - t1, (t1 - t0) + (t3 - t2)
