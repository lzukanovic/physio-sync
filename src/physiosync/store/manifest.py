"""Take manifest (docs/data-model.md → Manifest). Written incrementally, finalised post-stop.

Streams are keyed by stream id (``bitalino.main``, ``tobii.gaze``), not by channel. Streams
of one device may share an epoch (Tobii gaze and IMU); each still records it.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class StreamInfo(BaseModel):
    channels: list[str] = Field(default_factory=list)
    nominal_hz: float | None = None
    source: str | None = None
    """Adapter id that produced the stream, e.g. ``replay:tobii``: replayed data never passes as live."""
    # Unknown until derived (Tobii epoch) or until capture closes (coverage, n_samples).
    epoch_utc: float | None = None
    epoch_method: str | None = None
    epoch_uncertainty_s: float | None = None
    coverage_local: tuple[float, float] | None = None
    """First and last value of the stream's own time column (``t``, ``device_ts``)."""
    coverage_utc: tuple[float, float] | None = None
    """``coverage_local`` in UTC: equal to it if that column is UTC, else needs ``epoch_utc``."""
    n_samples: int | None = None


class Manifest(BaseModel):
    """Authoritative record of a take; SQLite is a rebuildable index over these (ADR 0011)."""

    schema_version: int = SCHEMA_VERSION
    uuid: str
    # Null for takes recorded outside a study (ADR 0011).
    study_id: int | None = None
    participant_id: str | None = None
    """The participant code (e.g. ``P07``), not the SQLite row id, so the manifest is readable alone."""
    scenario_id: int | None = None
    take_index: int | None = None
    app_version: str
    created_utc: float
    started_utc: float | None = None
    stopped_utc: float | None = None
    """Set when capture closes; a manifest with it null is a take still recording, or crashed."""
    wall_monotonic_delta: tuple[float, float | None] | None = None
    """``time.time() - time.monotonic()`` at start and stop. Only the difference means anything:
    stop minus start is how far the wall clock was stepped or slewed during the take (ADR 0012)."""
    reference_stream: str
    streams: dict[str, StreamInfo] = Field(default_factory=dict)
    usable_window: tuple[float, float] | None = None
    warnings: list[str] = Field(default_factory=list)


def read_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_manifest(path: Path, manifest: Manifest) -> None:
    """Atomic: it is rewritten during capture and must never be left half-written."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)
