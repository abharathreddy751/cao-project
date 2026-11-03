"""Remote offloading (Phase 5): link shim, wire protocol, node, proxy."""
from caosched.remote.link import LinkConfig, TransferModel, payload_bytes, precise_wait

__all__ = ["LinkConfig", "TransferModel", "payload_bytes", "precise_wait"]
