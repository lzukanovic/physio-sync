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
    # Unknown until derived (Tobii epoch) or until capture closes (coverage, n_samples).
    epoch_utc: float | None = None
    epoch_method: str | None = None
    epoch_uncertainty_s: float | None = None
    coverage: tuple[float, float] | None = None
    n_samples: int | None = None


class Manifest(BaseModel):
    schema_version: int = SCHEMA_VERSION
    uuid: str
    study_id: int
    participant_id: str
    """The participant code (e.g. ``P07``), not the SQLite row id, so the manifest is readable alone."""
    scenario_id: int
    take_index: int
    app_version: str
    created_utc: float
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
