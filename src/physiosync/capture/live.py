"""Display path: decimated, batched, lossy live feed for /ws/live.

A second consumer of the session's sink, beside the writer and never in series with it
(docs/decisions/0013-live-feed.md). ``put`` runs on the adapter's call stack, so it only
appends to a per-stream buffer bounded by the stream's own clock and drops the oldest batches.
A 10 Hz task drains the buffers, decimates each stream to <= 20 Hz and hands one frame to every
connected client, each with its own bounded frame queue. Batches are never mutated here: the
writer serialises the same objects.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque

from physiosync.adapters.base import SampleBatch, StreamSpec

log = logging.getLogger(__name__)

TICK_S = 0.1
"""Drain and broadcast period."""
MAX_HZ = 20.0
"""Per-stream display rate ceiling."""
WINDOW_S = 2.0
"""Buffer bound per stream, in the stream's own time: ~200 samples at 100 Hz whatever the replay speed."""
CLIENT_FRAMES = round(WINDOW_S / TICK_S)
"""Per-client queue: frames are one per tick, so this is also WINDOW_S of time."""


class Client:
    """One WebSocket subscriber. Drop-oldest; a reconnecting client starts empty (no backlog)."""

    def __init__(self) -> None:
        self.frames: deque[dict] = deque(maxlen=CLIENT_FRAMES)
        self.skipped = 0
        self._ready = asyncio.Event()

    def offer(self, frame: dict) -> None:
        if len(self.frames) == self.frames.maxlen:
            self.skipped += 1
        self.frames.append(frame)
        self._ready.set()

    async def next(self) -> dict:
        while not self.frames:
            self._ready.clear()
            await self._ready.wait()
        return self.frames.popleft()


class LiveFeed:
    def __init__(self) -> None:
        self._lock = threading.Lock()  # put() may run on a vendor SDK thread (ADR 0006)
        self._specs: dict[str, StreamSpec] = {}
        self._buf: dict[str, deque[SampleBatch]] = {}
        self._last_kept: dict[str, float] = {}
        self.dropped: dict[str, int] = {}
        """Samples shed from the input buffers since the take started. Display path only."""
        self.recording = False
        self.clients: set[Client] = set()
        self._warned = False

    def reset(self, streams: list[StreamSpec]) -> None:
        """A take is starting: new streams, empty buffers, drop counts back to zero."""
        with self._lock:
            self._specs = {s.id: s for s in streams}
            self._buf = {s.id: deque() for s in streams}
            self.dropped = {s.id: 0 for s in streams}
            self._last_kept = {}
            self.recording = True

    def end(self) -> None:
        self.recording = False

    def put(self, batch: SampleBatch) -> None:
        """Second ``SampleSink`` consumer: O(evictions), never blocks on I/O, never raises."""
        try:
            sid = batch.stream_id
            spec = self._specs.get(sid)
            if spec is None:
                return  # late batch from a previous take
            tc = spec.time_column
            if not batch.columns[tc]:
                return
            newest = batch.columns[tc][-1]
            with self._lock:
                buf = self._buf[sid]
                buf.append(batch)
                while newest - buf[0].columns[tc][-1] > WINDOW_S:
                    self.dropped[sid] += len(buf.popleft().columns[tc])
        except Exception:
            if not self._warned:
                self._warned = True
                log.exception("live feed: put failed; display path only, capture unaffected")

    def subscribe(self) -> Client:
        c = Client()
        self.clients.add(c)
        return c

    def unsubscribe(self, c: Client) -> None:
        self.clients.discard(c)

    def tick(self) -> dict:
        """Drain, decimate, broadcast one frame. Event-loop thread only."""
        with self._lock:
            bufs = self._buf
            self._buf = {sid: deque() for sid in bufs}
            dropped = dict(self.dropped)
            specs = self._specs
        frame = {
            "t_utc": time.time(),
            "recording": self.recording,
            "dropped": dropped,
            "streams": {sid: self._decimate(specs[sid], b) for sid, b in bufs.items()},
        }
        for c in self.clients:
            c.offer(frame)
        return frame

    async def run(self) -> None:
        while True:
            await asyncio.sleep(TICK_S)
            self.tick()

    def _decimate(self, spec: StreamSpec, batches: deque[SampleBatch]) -> dict[str, list]:
        """Keep a sample once its own clock is >= 1/MAX_HZ past the last kept one."""
        out: dict[str, list] = {c: [] for c in spec.columns}
        last = self._last_kept.get(spec.id, float("-inf"))
        for b in batches:
            for i, t in enumerate(b.columns[spec.time_column]):
                if t - last >= 1 / MAX_HZ:
                    last = t
                    for c in spec.columns:
                        out[c].append(b.columns[c][i])
        self._last_kept[spec.id] = last
        return out
