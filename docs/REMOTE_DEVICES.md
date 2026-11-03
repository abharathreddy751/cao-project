# Remote devices: Raspberry Pi and NVIDIA T4 (preparation)

The scheduler is unchanged: a physical device is attached as one more remote
pool through the existing proxy/node interface (`RemoteSlot`), exactly like
the Phase 5/6 local node. Nothing below has been run on real Pi or T4
hardware.

## Status (as of 2026-10-03)

| item | IMPLEMENTED | EXECUTED | VERIFIED | notes |
|---|---|---|---|---|
| Node server portable to another host (`python -m caosched.remote.node --host 0.0.0.0 --port N`) | yes | locally only (node on LP11 of the i5-1235U) | locally (tests, Phase 5/6B) | NOT VERIFIED on a Pi / Linux / ARM |
| Named remote pools (`RemoteSlot(pool="R_PI")`, `"R_T4"`) | yes | yes (test with a local node as `R_PI`) | yes (tests) | |
| Connect to an already-running node (`RemoteSlot(host=..., port=..., node_core=None)`) | yes | no (all tests spawn the node locally) | NOT VERIFIED | |
| Proxy-side timestamps for a node with a foreign clock (`same_clock=False`) | yes | yes (local node forced to `same_clock=False`) | ordering only (tests) | NOT VERIFIED against a real clock offset |
| Capability report in the handshake (platform, machine, numpy/Pillow versions, CUDA via PyTorch, stage list) | yes | yes (local node: CPU, `cuda: False`) | yes for the CPU case | CUDA detection NOT VERIFIED (no GPU, PyTorch not installed here) |
| Application stages on the remote node with real data (payload = actual artifacts) | yes | yes (local node) | yes: output bit-identical to the reference (tests) | NOT VERIFIED on ARM (numeric-tolerance verification is implemented for that case) |
| GPU stage variant `img_edges` with `params["device"]="cuda"` (PyTorch conv2d Sobel) | yes | **no** | **NOT VERIFIED** | needs a CUDA machine (T4); output equivalence to the CPU Sobel is untested |
| Real network instead of the shim (shim configured to zero) | yes (`LinkConfig("real")`) | no | NOT VERIFIED | |

## Raspberry Pi (planned procedure)

1. On the Pi: Python 3.11+, `pip install numpy pillow psutil`, copy or install
   the `caosched` package (`pip install -e .`).
2. Start the node: `python -m caosched.remote.node --host 0.0.0.0 --port 5555`
   (optionally `--affinity` to pin it to one core).
3. Coordinator side: `RemoteSlot(LinkConfig("real"), host="<pi ip>", port=5555,
   pool="R_PI", same_clock=False)`; mark Pi-eligible stages with
   `remote_stages={"img_denoise": ["R_PI"], ...}`.
4. Before using it in experiments: profile the R_PI pool
   (`run_app_demo.py`-style pinned runs), calibrate the real link (shim zero),
   and verify application outputs with `verify_output` (ARM float rounding
   may give a `numeric` rather than `exact` match).

## NVIDIA T4 (planned procedure)

Same as the Pi, plus PyTorch with CUDA on the T4 host; the node then reports
`cuda: True` and the device name. GPU stages are selected per pool via
`build_image_pipeline(..., device_params={"img_edges": {"device": "cuda"}},
remote_stages={"img_edges": ["R_T4"]})`. Note: `device_params` currently
applies to every task of that stage type, so a stage marked `cuda` must only
be eligible for CUDA pools; per-pool parameter selection is an open item.
