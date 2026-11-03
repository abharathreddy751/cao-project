"""CUDA stage variants: equivalence to the CPU reference (needs a GPU) and clean CPU-only import."""
import importlib
import sys

import numpy as np
import pytest

from caosched.apps import cuda_stages
from caosched.apps.stages import STAGES


def test_imports_and_degrades_without_torch(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # `import torch` -> ImportError, as on a CPU-only node
    mod = importlib.reload(cuda_stages)
    try:
        assert mod.cuda_available() is False
        assert set(mod.CUDA_STAGES) <= set(STAGES)    # swap-in names are real CPU stage names
    finally:
        monkeypatch.undo()
        importlib.reload(cuda_stages)


@pytest.mark.skipif(not cuda_stages.cuda_available(), reason="no CUDA device")
@pytest.mark.parametrize("stage,params", [("img_denoise", {"radius": 2.0, "iterations": 2}), ("img_denoise", {"radius": 0.7}),
                                          ("img_edges", {}), ("img_features", {})])
def test_cuda_stage_matches_cpu_reference(stage, params):
    scene = STAGES["img_source"].compute([], {"height": 64, "width": 96, "seed": 5})  # fixed small input
    x = [STAGES["img_edges"].compute([scene], {})] if stage == "img_features" else [scene]
    cpu, gpu = STAGES[stage].compute(x, params), cuda_stages.CUDA_STAGES[stage](x, params)
    assert gpu.shape == cpu.shape and gpu.dtype == cpu.dtype
    if stage == "img_features":
        np.testing.assert_allclose(gpu, cpu, rtol=1e-9, atol=0)   # tolerance stated in scripts/gpu_spike.py
    else:
        d = np.abs(gpu.astype(int) - cpu.astype(int))
        assert d.max() <= (0 if stage == "img_denoise" else 1)
        assert (d > 0).mean() <= (0.0 if stage == "img_denoise" else 1e-3)  # declared fraction-of-differing-pixels bound
