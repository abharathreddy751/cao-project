"""PyTorch-CUDA variants of image-pipeline stages (Stage 1 GPU spike, AD-6).

``CUDA_STAGES[name](inputs, params) -> np.ndarray`` has the semantics of the CPU
``Stage.compute`` in ``apps/stages.py`` (decoded numpy arrays in, numpy array out),
so the runtime can swap implementations by worker pool kind. Host-device copies
(H2D of the inputs, D2H of the result) are INSIDE each function: the caller
sees the true cost. Results are float32-on-GPU vs the CPU reference, so they are
equivalent within a stated tolerance (see scripts/gpu_spike.py), not bit-exact.

Imports cleanly without torch; ``cuda_available()`` is False then. A stage is
used as GPU evidence only if scripts/gpu_spike.py shows equivalence AND a
measured speed-up including the copies; otherwise it is dropped, not forced.
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np


def cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - torch absent or broken DLLs: CPU-only node
        return False


def _box_radius(sigma: float, passes: int = 3) -> float:
    """Pillow's ``_gaussian_blur_radius``: GaussianBlur is ``passes`` extended box blurs."""
    s2 = sigma * sigma
    big_l = math.sqrt(12.0 * s2 / passes + 1.0)
    l = math.floor((big_l - 1.0) / 2.0)
    a = (2 * l + 1) * (l * (l + 1) - 3.0 * s2 / passes) / (6 * (s2 / passes - (l + 1) * (l + 1)))
    return l + a


def _box_pass(x, radius: float, dim: int):
    """One Pillow extended box blur along ``dim`` in exact 24-bit fixed point (int64 cumsum, edge-replicated)."""
    import torch

    r = int(radius)
    ww = int(np.float32(1 << 24) / np.float32(radius * 2 + 1))
    fw = ((1 << 24) - (2 * r + 1) * ww) // 2
    n = x.shape[dim]
    idx = torch.arange(-r - 1, n + r + 1, device=x.device).clamp_(0, n - 1)
    pad = x.index_select(dim, idx)
    cs = pad.cumsum(dim)
    acc = cs.narrow(dim, 2 * r + 1, n) - cs.narrow(dim, 0, n)
    far = pad.narrow(dim, 0, n) + pad.narrow(dim, 2 * r + 2, n)
    return (acc * ww + far * fw + (1 << 23)) >> 24


def _denoise(inputs, p) -> np.ndarray:
    """Pillow GaussianBlur re-implemented as the same 3+3 extended box passes in integer
    arithmetic, so the result is expected to be bit-exact (verified by the spike, not assumed)."""
    import torch

    (t,) = inputs
    radius = _box_radius(float(p.get("radius", 2.0)))
    x = torch.from_numpy(np.ascontiguousarray(t)).cuda().permute(2, 0, 1).to(torch.int64)
    for _ in range(int(p.get("iterations", 1))):
        for dim in (2, 2, 2, 1, 1, 1):  # all horizontal passes, then all vertical (Pillow's order)
            x = _box_pass(x, radius, dim)
    return np.ascontiguousarray(x.to(torch.uint8).permute(1, 2, 0).cpu().numpy())


def _edges(inputs, _p) -> np.ndarray:
    """Gray mean + Sobel magnitude with the CPU stage's exact float32 formulas (slice arithmetic,
    not conv2d: cuDNN may use TF32 and would perturb the non-integer gray values)."""
    import torch

    (t,) = inputs
    s = torch.from_numpy(np.ascontiguousarray(t)).cuda().float().sum(dim=2)
    g = s / torch.full_like(s, 3.0)  # tensor divisor: `s / 3.0` is lowered to s * (1/3) on CUDA, which rounds differently
    gx = (g[:-2, 2:] + 2 * g[1:-1, 2:] + g[2:, 2:]) - (g[:-2, :-2] + 2 * g[1:-1, :-2] + g[2:, :-2])
    gy = (g[2:, :-2] + 2 * g[2:, 1:-1] + g[2:, 2:]) - (g[:-2, :-2] + 2 * g[:-2, 1:-1] + g[:-2, 2:])
    mag = torch.zeros_like(g)
    mag[1:-1, 1:-1] = torch.sqrt(gx * gx + gy * gy)
    return torch.clamp(mag / 4.0, 0, 255).to(torch.uint8).cpu().numpy()


def _features(inputs, _p) -> np.ndarray:
    """32-bin edge histogram + mean, std, edge density (float64, as the CPU stage)."""
    import torch

    (e,) = inputs
    x = torch.from_numpy(np.ascontiguousarray(e)).cuda()
    hist = torch.bincount((x >> 3).flatten().long(), minlength=32).double()
    hist /= hist.sum()
    xd = x.double()
    tail = torch.stack([xd.mean(), xd.std(unbiased=False), (x > 64).double().mean()])
    return torch.cat([hist, tail]).cpu().numpy()


CUDA_STAGES: dict[str, Callable[[list, dict], np.ndarray]] = {
    "img_denoise": _denoise,
    "img_edges": _edges,
    "img_features": _features,
}
