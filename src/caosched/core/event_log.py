"""Append-only JSONL event logger.

Per the project's "log raw data first, generate summaries afterward" rule,
every state transition the coordinator makes is written here immediately
(flushed per line) rather than buffered and summarized in memory -- if the
process crashes mid-run, the log up to that point is still intact and usable.

Every record carries:
  ``seq``        -- strictly increasing per log; total order of events.
  ``t``          -- ``caosched.util.clock.now()`` (QPC, 100 ns resolution), the
                    same timebase as every ``t_*`` field including the
                    worker-side ``t_started``/``t_completed``. Use this for
                    all interval arithmetic.
  ``timestamp``  -- ``time.time()`` epoch seconds, for human orientation only:
                    on CPython 3.11/Windows it has ~1-16 ms resolution (see
                    clock.py). ``run_started`` carries an (epoch, perf) anchor.
  ``event``      -- event type (see ARCHITECTURE.md "Event log schema").

An existing log is never overwritten unless ``overwrite=True`` -- raw run
records must not be silently clobbered by a re-run with the same run id.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from caosched.util import clock

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data" / "events"


class EventLogger:
    def __init__(self, run_id: str, output_dir: Path | None = None, *, overwrite: bool = False):
        output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.path = output_dir / f"{run_id}.jsonl"
        self._fh = self.path.open("w" if overwrite else "x", encoding="utf-8")
        self._seq = 0

    def log(self, event_type: str, **fields) -> dict:
        if self._fh.closed:
            raise RuntimeError(f"EventLogger for {self.run_id!r} is closed")
        record = {"seq": self._seq, "t": clock.now(), "timestamp": time.time(), "event": event_type, **fields}
        self._fh.write(json.dumps(record, default=str) + "\n")
        self._fh.flush()
        self._seq += 1
        return record

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "EventLogger":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def read_events(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
