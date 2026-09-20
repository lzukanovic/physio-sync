"""Runtime configuration, read from the environment."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PORT = 8000
# Interim reference until the SCANeR adapter exists (docs/adapters.md → Reference stream).
DEFAULT_REFERENCE_STREAM = "tobii.gaze"


class ConfigError(Exception):
    """Configuration is missing or unusable. The message is shown to the operator as-is."""


@dataclass(frozen=True)
class Settings:
    data_root: Path
    port: int
    reference_stream: str

    @property
    def db_path(self) -> Path:
        return self.data_root / "physiosync.db"


def load(env: dict[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env

    raw_root = env.get("PHYSIOSYNC_DATA", "").strip()
    if not raw_root:
        raise ConfigError(
            "PHYSIOSYNC_DATA is not set. Point it at the directory where recordings "
            "and the database live (outside the install), e.g. PHYSIOSYNC_DATA=D:\\physiosync-data"
        )
    data_root = Path(raw_root).expanduser()
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        # Real write probe: os.access is unreliable on Windows.
        with tempfile.TemporaryFile(dir=data_root):
            pass
    except OSError as e:
        raise ConfigError(f"PHYSIOSYNC_DATA={data_root} is not a writable directory: {e}") from e

    raw_port = env.get("PHYSIOSYNC_PORT", "").strip() or str(DEFAULT_PORT)
    try:
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ConfigError(f"PHYSIOSYNC_PORT={raw_port!r} is not a valid port (1-65535)") from None

    reference = env.get("PHYSIOSYNC_REFERENCE_STREAM", "").strip() or DEFAULT_REFERENCE_STREAM
    return Settings(data_root=data_root.resolve(), port=port, reference_stream=reference)
