"""Session manager: one take at a time. Owns adapter lifecycles, the take directory and manifest.

The manifest is the authoritative record of a take (docs/decisions/0011-manifest-authoritative.md);
it is written at create, after adapters start, and on stop.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from pathlib import Path

from physiosync import __version__
from physiosync.adapters import ADAPTERS
from physiosync.adapters.base import SampleBatch, SourceAdapter, StopInfo, StreamSpec
from physiosync.capture.live import LiveFeed
from physiosync.capture.writer import Writer
from physiosync.store.manifest import Manifest, StreamInfo, write_manifest

log = logging.getLogger(__name__)


class SessionError(Exception):
    """The operation cannot proceed. The message is shown to the operator as-is."""


class SessionManager:
    def __init__(
        self,
        data_root: Path,
        reference_stream: str,
        adapters=ADAPTERS,
        live: LiveFeed | None = None,
    ) -> None:
        self.takes_dir = Path(data_root) / "takes"
        self._reference = reference_stream
        self._factories = adapters
        self.live = live or LiveFeed()
        self._lock = asyncio.Lock()
        self._clear()

    def _clear(self) -> None:
        self.take_dir: Path | None = None
        self.manifest: Manifest | None = None
        self.writer: Writer | None = None
        self._specs: dict[str, StreamSpec] = {}
        self._adapters: list[SourceAdapter] = []

    @property
    def recording(self) -> bool:
        return self.writer is not None

    async def start(self, configs: dict[str, dict]) -> Path:
        """Start a take with one adapter per ``configs`` key (adapter id -> its configure dict)."""
        async with self._lock:
            if self.recording:
                raise SessionError("a take is already recording")
            unknown = set(configs) - set(self._factories)
            if not configs or unknown:
                raise SessionError(f"unknown or no adapters: {sorted(unknown)}")
            adapters = [self._factories[aid]() for aid in configs]
            warnings: list[str] = []
            for a, cfg in zip(adapters, configs.values()):
                status = await a.probe()
                if not status.connected:
                    raise SessionError(f"{a.id}: {status.detail or 'not connected'}")
                warnings.extend(status.warnings)
                await a.configure(cfg)

            take_id = str(uuid.uuid4())
            self.take_dir = self.takes_dir / take_id
            (self.take_dir / "raw").mkdir(parents=True)
            try:
                self.manifest = Manifest(
                    uuid=take_id,
                    app_version=__version__,
                    created_utc=time.time(),
                    reference_stream=self._reference,
                    streams={
                        s.id: StreamInfo(
                            source=a.id, channels=list(s.channels), nominal_hz=s.nominal_hz
                        )
                        for a in adapters
                        for s in a.streams
                    },
                    warnings=warnings,
                )
                self._write()
                specs = [s for a in adapters for s in a.streams]
                self._specs = {s.id: s for s in specs}
                self.writer = Writer(self.take_dir / "raw", specs)
                self.live.reset(specs)
                writer, live = self.writer, self.live

                def sink(batch: SampleBatch) -> None:
                    # Fan-out, not a chain: the live feed never sits on the path to disk
                    # (ADR 0013). Both calls only enqueue; neither raises.
                    writer.put(batch)
                    live.put(batch)

                wall, mono = time.time(), time.monotonic()
                self.manifest.started_utc = wall
                self.live.t_start = wall
                self.manifest.wall_monotonic_delta = (wall - mono, None)
                for a in adapters:
                    epochs = await a.start(sink)
                    self._adapters.append(a)
                    for sid, epoch in epochs.epochs.items():
                        self.manifest.streams[sid].epoch_utc = epoch
                        self.manifest.streams[sid].epoch_method = epochs.methods.get(sid)
                self._write()
            except BaseException:
                await self._discard()
                raise
            return self.take_dir

    async def stop(self) -> Manifest:
        """End the take and finalise the manifest. Safe at any point: the sink only enqueues."""
        async with self._lock:
            if not self.recording:
                raise SessionError("no take is recording")
            wall, mono = time.time(), time.monotonic()
            infos = await self._teardown()
            m, w = self.manifest, self.writer
            m.stopped_utc = wall
            m.wall_monotonic_delta = (m.wall_monotonic_delta[0], wall - mono)
            for sid, info in m.streams.items():
                info.n_samples = w.n_samples[sid]
                if sid in w.first:
                    local = (w.first[sid], w.last[sid])
                    info.coverage_local = local
                    if self._specs[sid].time_is_utc:
                        info.coverage_utc = local
                    elif info.epoch_utc is not None:
                        info.coverage_utc = (info.epoch_utc + local[0], info.epoch_utc + local[1])
            for i in infos:
                for sid, n in i.n_samples.items():
                    if n != w.n_samples.get(sid):
                        log.error(
                            "%s: adapter emitted %d, writer wrote %s", sid, n, w.n_samples.get(sid)
                        )
                        m.warnings.append(f"capture.count_mismatch:{sid}")
            if w.error is not None:
                m.warnings.append("capture.writer_failed")
            if w.late_batches:
                m.warnings.append("capture.batches_after_stop")
            self._write()
            self._clear()
            return m

    async def cancel(self) -> None:
        """End the take and delete its directory. Nothing is left behind."""
        async with self._lock:
            if not self.recording:
                raise SessionError("no take is recording")
            await self._discard()

    async def _teardown(self) -> list[StopInfo]:
        """Stop every started adapter (one failing never leaves another running), then the writer."""
        results = await asyncio.gather(*(a.stop() for a in self._adapters), return_exceptions=True)
        infos = []
        for a, r in zip(self._adapters, results):
            if isinstance(r, BaseException):
                log.error("%s: stop failed", a.id, exc_info=r)
                self.manifest.warnings.append(f"capture.stop_failed:{a.id}")
            else:
                infos.append(r)
        self.live.end()
        if self.writer is not None:
            await asyncio.to_thread(self.writer.close)
        return infos

    async def _discard(self) -> None:
        try:
            await self._teardown()
        finally:
            shutil.rmtree(self.take_dir, ignore_errors=True)
            self._clear()

    def _write(self) -> None:
        write_manifest(self.take_dir / "manifest.json", self.manifest)
