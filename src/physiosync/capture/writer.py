"""Storage path: every sample, unmodified, appended to one gzipped JSONL file per stream.

One JSON object per sample per line, keys in ``StreamSpec.columns`` order. A single thread does
all disk work, fed by an unbounded queue, so ``put`` (the ``SampleSink``) never blocks and never
drops. Rationale in docs/decisions/0010-capture-storage-path.md.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import queue
import threading
import time
from pathlib import Path

from physiosync.adapters.base import SampleBatch, StreamSpec

log = logging.getLogger(__name__)

FLUSH_S = 1.0
"""Max seconds between flush+fsync, so a crash costs at most this much (task brief: <= 2 s)."""
_STOP = object()


def raw_path(raw_dir: Path, stream_id: str) -> Path:
    return Path(raw_dir) / f"{stream_id}.jsonl.gz"


class Writer:
    def __init__(self, raw_dir: Path, streams: list[StreamSpec]) -> None:
        self._specs = {s.id: s for s in streams}
        # "x": the OS refuses to reopen a capture file, so a closed one is never rewritten.
        # Open for the take's lifetime, closed by the writer thread.
        self._files = {s.id: gzip.open(raw_path(raw_dir, s.id), "xb") for s in streams}  # noqa: SIM115
        # ponytail: unbounded on purpose; the storage path may neither block nor drop. Memory
        # grows only if the disk stalls; the disk-space guard is Phase 6.
        self._q: queue.SimpleQueue = queue.SimpleQueue()
        self._closed = False
        self.n_samples = {s.id: 0 for s in streams}
        self.first: dict[str, float] = {}
        self.last: dict[str, float] = {}
        """First and last value of each stream's ``time_column``."""
        self.error: BaseException | None = None
        self.late_batches = 0
        self._thread = threading.Thread(target=self._run, name="writer", daemon=True)
        self._thread.start()

    def put(self, batch: SampleBatch) -> None:
        """The ``SampleSink``: thread-safe, never blocks, never raises."""
        if self._closed:
            self.late_batches += 1
            if self.late_batches == 1:
                log.warning(
                    "batch for %s after writer closed; adapter outlived stop()", batch.stream_id
                )
            return
        self._q.put(batch)

    def close(self) -> None:
        """Drain everything queued, finish the gzip trailers, join. Blocking; run off the loop."""
        if not self._closed:
            self._closed = True
            self._q.put(_STOP)
        self._thread.join()

    def _run(self) -> None:
        try:
            last_flush = time.monotonic()
            while True:
                try:
                    item = self._q.get(timeout=FLUSH_S)
                except queue.Empty:
                    item = None
                if item is _STOP:
                    break
                if item is not None:
                    self._write(item)
                if time.monotonic() - last_flush >= FLUSH_S:
                    self._flush()
                    last_flush = time.monotonic()
            self._flush()
        except BaseException as e:  # surfaced by the session manager at stop
            log.exception("writer failed")
            self.error = e
        finally:
            for f in self._files.values():
                try:
                    f.close()
                except OSError:
                    log.exception("closing %s", f.name)

    def _write(self, batch: SampleBatch) -> None:
        sid = batch.stream_id
        names = self._specs[sid].columns
        rows = zip(*(batch.columns[c] for c in names))
        lines = "".join(json.dumps(dict(zip(names, r)), separators=(",", ":")) + "\n" for r in rows)
        self._files[sid].write(lines.encode())
        n = len(batch.columns[names[0]])
        if n:
            self.n_samples[sid] += n
            tc = self._specs[sid].time_column
            if tc is not None:
                self.first.setdefault(sid, batch.columns[tc][0])
                self.last[sid] = batch.columns[tc][-1]

    def _flush(self) -> None:
        for f in self._files.values():
            f.flush()  # gzip sync flush: everything so far is decodable without the trailer
            os.fsync(f.fileno())
