"""Replay adapter: plays a recorded live-capture fixture back as if it were the hardware.

One instance per device (``replay:bitalino``, ``replay:tobii``), emitting the same stream ids
and columns the live adapters write. Rules in docs/adapters.md → Replay adapter; the rebasing
choices in docs/decisions/0009-replay-per-device-rebasing.md.
"""

from __future__ import annotations

import asyncio
import csv
import math
import time
from contextlib import suppress
from pathlib import Path

from physiosync.adapters.base import (
    DeviceStatus,
    SampleBatch,
    SampleSink,
    StopInfo,
    StreamEpochs,
    StreamSpec,
)

# Repo checkout layout (src/physiosync/adapters/ -> repo root). Pass ``dir`` for anything else.
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "live-capture"
BITALINO_HZ = 100.0

# device -> stream id -> fixture file
FILES = {
    "bitalino": {"bitalino.main": "bitalino.csv"},
    "tobii": {"tobii.gaze": "tobii_gaze.csv", "tobii.imu": "tobii_imu.csv"},
}
# (pacing column, absolute host-clock column) per device, in emitted names.
CLOCKS = {"bitalino": ("arrival_ts", "arrival_ts"), "tobii": ("device_ts", "local_ts")}
TIMING = {"t", "arrival_ts", "nseq", "device_ts", "local_ts"}
RENAME = {
    "Sequence": "nseq",
    "Timestamp": "arrival_ts",
    "DeviceTS": "device_ts",
    "LocalTS": "local_ts",
}


def _column(name: str) -> str:
    if name in RENAME:
        return RENAME[name]
    if " (RAW)" in name:  # "A1 (RAW) Port1" -> "A1"
        return name.split()[0]
    return name.lower()  # "Gaze2D_X" -> "gaze2d_x"


def _value(v: str) -> int | float | None:
    if v == "":
        return None
    try:
        return int(v)
    except ValueError:
        return float(v)


def _read_csv(path: Path) -> dict[str, list]:
    """Prototype-app CSV: ``#`` metadata lines, a blank line, header, rows. Columnar result."""
    with open(path, newline="") as f:
        reader = csv.reader(line for line in f if line.strip() and not line.startswith("#"))
        names = [_column(h) for h in next(reader)]
        cols: list[list] = [[] for _ in names]
        for row in reader:
            for col, v in zip(cols, row):
                col.append(_value(v))
    return dict(zip(names, cols))


class _Stream:
    def __init__(self, stream_id: str, cols: dict[str, list], pace_col: str) -> None:
        self.cols = cols
        self.pace = cols[pace_col]
        bitalino = stream_id == "bitalino.main"
        self.spec = StreamSpec(
            id=stream_id,
            columns=("t", *cols) if bitalino else tuple(cols),
            channels=tuple(c for c in cols if c not in TIMING),
            nominal_hz=BITALINO_HZ if bitalino else 100.0,
            time_column="t" if bitalino else "device_ts",
            time_is_utc=bitalino,
        )
        self.first = 0  # first index emitted (after seek)
        self.pos = 0  # next index to emit


class ReplayAdapter:
    def __init__(self, device: str, directory: Path | str = DEFAULT_DIR) -> None:
        if device not in FILES:
            raise ValueError(f"no replay for device {device!r}; known: {sorted(FILES)}")
        self.id = f"replay:{device}"
        self._device = device
        self._speed = 1.0
        self._seek = 0.0
        self._task: asyncio.Task | None = None
        self._load(Path(directory))

    def _load(self, directory: Path) -> None:
        pace_col, abs_col = CLOCKS[self._device]
        self._dir = directory
        self._streams = [
            _Stream(sid, _read_csv(directory / name), pace_col)
            for sid, name in FILES[self._device].items()
        ]
        self.streams = [s.spec for s in self._streams]
        # One origin per device so streams sharing a device clock keep their relative offset.
        self._origin = min(s.pace[0] for s in self._streams)
        # Absolute column minus pacing column, minimised: 0 for BITalino, the Tobii host-vs-device
        # offset. Subtracting it maps pacing time `origin + seek` to wall-clock `t_start`.
        self._base = min(
            a - p for s in self._streams for a, p in zip(s.cols[abs_col], s.pace) if a is not None
        )

    async def probe(self) -> DeviceStatus:
        return DeviceStatus(connected=True, detail=f"replaying {self._dir}")

    async def configure(self, cfg: dict) -> None:
        """Keys: ``dir`` (fixture directory), ``speed`` (> 0, 1.0 = realtime), ``seek`` (s)."""
        speed = float(cfg.get("speed", self._speed))
        if not (speed > 0 and math.isfinite(speed)):
            raise ValueError(f"speed must be positive and finite, got {speed}")
        self._speed = speed
        self._seek = float(cfg.get("seek", self._seek))
        if "dir" in cfg:
            self._load(Path(cfg["dir"]))

    async def start(self, sink: SampleSink) -> StreamEpochs:
        self._t_start = time.time()
        self._shift = self._t_start - self._origin - self._seek - self._base
        cutoff = self._origin + self._seek
        for s in self._streams:
            s.pos = 0
            while s.pos < len(s.pace) and s.pace[s.pos] < cutoff:
                s.pos += 1
            s.first = s.pos
        self._task = asyncio.create_task(self._run(sink))
        if self._device == "bitalino":
            return StreamEpochs({"bitalino.main": self._t_start}, {"bitalino.main": "host:t_start"})
        return StreamEpochs({s.spec.id: None for s in self._streams})

    async def _run(self, sink: SampleSink) -> None:
        mono0 = time.monotonic()
        while True:
            # "Now" on the recording's own clock.
            now = self._origin + self._seek + (time.monotonic() - mono0) * self._speed
            next_due = math.inf
            for s in self._streams:
                # Everything due goes out as one batch, so batch sizes follow the host timer
                # resolution (~1 ms macOS, ~15 ms Windows); arrival timing follows the recording.
                # Linear, not bisect: an out-of-order timestamp is emitted immediately, not skipped.
                end = s.pos
                while end < len(s.pace) and s.pace[end] <= now:
                    end += 1
                if end > s.pos:
                    sink(self._batch(s, s.pos, end))
                    s.pos = end
                if s.pos < len(s.pace):
                    next_due = min(next_due, s.pace[s.pos])
            if next_due == math.inf:
                return  # end of recording; idle until stopped
            await asyncio.sleep(max(0.0, (next_due - now) / self._speed))

    def _batch(self, s: _Stream, i: int, j: int) -> SampleBatch:
        abs_col = CLOCKS[self._device][1]
        cols = {name: col[i:j] for name, col in s.cols.items()}
        cols[abs_col] = [None if v is None else v + self._shift for v in cols[abs_col]]
        if s.spec.id == "bitalino.main":
            nseq0 = s.cols["nseq"][s.first]
            cols = {"t": [self._t_start + (n - nseq0) / BITALINO_HZ for n in cols["nseq"]], **cols}
        return SampleBatch(stream_id=s.spec.id, columns=cols)

    async def stop(self) -> StopInfo:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        return StopInfo(
            stopped_utc=time.time(),
            n_samples={s.spec.id: s.pos - s.first for s in self._streams},
        )
