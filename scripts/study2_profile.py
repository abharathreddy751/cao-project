"""Study 2: solo kernel-time profile (E1 input) of the study 2 batch workload on pools P, E and G.

Re-uses ``scripts/profile_gpu_workload.py`` unchanged (measurement code, output format, exclusive-create rules); only the DAG
it profiles is replaced by ``study2.workload.build_batch``. One representative task per stage type: sizes are pixels per
image (``--tile`` squared), ``img_aggregate`` size = k.

  python scripts/study2_profile.py --out data/profiles/study2_t512 --tile 512 --k 64 --denoise-iterations 8 [--reps 5]
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    k = 64
    if "--k" in argv:
        i = argv.index("--k")
        k = int(argv[i + 1])
        del argv[i:i + 2]
    spec = importlib.util.spec_from_file_location("profile_gpu_workload", ROOT / "scripts" / "profile_gpu_workload.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from caosched.study2.workload import build_batch

    def builder(width, height, grid, seed, denoise_iterations=1, **_kw):  # grid is 1: one image per chain, side = width
        return build_batch(k, width // grid, seed, 2.0, denoise_iterations)

    mod.build_image_pipeline = builder
    return mod.main([*argv, "--n-images", "1"])


if __name__ == "__main__":
    sys.exit(main())
