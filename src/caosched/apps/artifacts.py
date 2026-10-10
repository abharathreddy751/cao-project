"""Artifact store: where stage tasks read inputs and write outputs.

One directory per run: ``<root>/<run_id>/<task_id>.bin``. Local workers read
and write it directly (shared filesystem); the remote proxy reads a task's
input artifacts, ships the real bytes to the node, and writes the node's
returned output bytes back -- so for application stages the link carries the
actual data, not a stand-in buffer.
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "artifacts"


def artifact_path(run_dir: Path, task_id: str) -> Path:
    return Path(run_dir) / f"{task_id}.bin"


def read_artifacts(paths) -> list[bytes]:
    return [Path(p).read_bytes() for p in paths]


def write_artifact(path, blob: bytes) -> None:
    p = Path(path)
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(p)  # atomic: dependents never see a partial artifact
