"""The adapter contract. Types and docstrings only; see docs/adapters.md.

Rules for every adapter: never resample, interpolate, filter or reorder; never talk to
another device; emit batches; report health, do not decide; stopping is safe at any time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class StreamSpec:
    """One stream an adapter produces, e.g. ``bitalino.main`` or ``tobii.gaze``."""

    id: str
    """``<adapter>.<stream>``. Also the manifest key and the Parquet file stem."""
    columns: tuple[str, ...]
    """Every column a batch carries, timestamp columns included (e.g. ``t``, ``arrival_ts``)."""
    channels: tuple[str, ...] = ()
    """Signal columns among ``columns`` (e.g. ``A1``..``A6``); the rest is timing/diagnostics."""
    nominal_hz: float | None = None
    """Nominal rate; ``None`` if irregular (SCANeR)."""


@dataclass(frozen=True, slots=True)
class SampleBatch:
    """One device callback or WebSocket message, columnar and unmodified.

    ``columns`` maps each column name of the stream's ``StreamSpec`` to equal-length values.
    ``None`` marks a value the device did not provide (e.g. Tobii IMU with a missing sensor).
    """

    stream_id: str
    columns: dict[str, Sequence[float | int | None]]


class SampleSink(Protocol):
    """Where an adapter hands batches. Synchronous, non-blocking, thread-safe.

    Non-blocking because the storage path must never be back-pressured. Thread-safe because
    vendor SDK callbacks (PLUX) arrive on a foreign thread and must be able to call it directly.
    Implementations must not raise into the adapter; overflow is the sink's problem.
    """

    def __call__(self, batch: SampleBatch) -> None: ...


@dataclass(frozen=True, slots=True)
class DeviceStatus:
    """Result of ``probe``: is the device reachable, and anything the operator should see."""

    connected: bool
    detail: str = ""
    warnings: tuple[str, ...] = ()
    """Machine-readable tags, e.g. ``tobii.ntp_not_synchronized``. Copied into the manifest."""
    info: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StreamEpochs:
    """Absolute epoch (UTC seconds) per stream id, returned by ``start``.

    ``None`` means the epoch must be derived post-hoc from the captured data (Tobii).
    """

    epochs: dict[str, float | None]
    methods: dict[str, str] = field(default_factory=dict)
    """Epoch provenance per stream, e.g. ``host:t_start``. Copied into the manifest."""


@dataclass(frozen=True, slots=True)
class Anomaly:
    """Something the adapter observed and did NOT correct, for the quality report."""

    stream_id: str
    kind: str
    """E.g. ``nseq_gap``, ``reconnect``."""
    detail: str = ""
    magnitude: float | None = None
    t_utc: float | None = None


@dataclass(frozen=True, slots=True)
class StopInfo:
    stopped_utc: float
    n_samples: dict[str, int]
    anomalies: tuple[Anomaly, ...] = ()


class SourceAdapter(Protocol):
    id: str
    """``bitalino``, ``tobii``, ``scaner``, ``replay:tobii``."""
    streams: list[StreamSpec]

    async def probe(self) -> DeviceStatus:
        """Check reachability and read health info. Must not start capture."""
        ...

    async def configure(self, cfg: dict) -> None:
        """Apply operator configuration (channels, rate, address). Before ``start`` only."""
        ...

    async def start(self, sink: SampleSink) -> StreamEpochs:
        """Begin emitting batches to ``sink`` and return the stream epochs."""
        ...

    async def stop(self) -> StopInfo:
        """End capture. Safe at any time: mid-batch, while disconnected, or if never started."""
        ...
