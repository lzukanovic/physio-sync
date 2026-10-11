"""Run one capture end to end from the command line and print what landed on disk.

python -m physiosync.devcheck replay --seconds 30 [--speed 1]
"""

from __future__ import annotations

import argparse
import asyncio
import gzip

from physiosync import config
from physiosync.capture.session import SessionManager
from physiosync.capture.writer import raw_path

DEVICES = {"replay": ("replay:bitalino", "replay:tobii")}


async def run(device: str, seconds: float, speed: float) -> None:
    settings = config.load()
    manager = SessionManager(settings.data_root, settings.reference_stream)
    take = await manager.start({aid: {"speed": speed} for aid in DEVICES[device]})
    await asyncio.sleep(seconds)
    manifest = await manager.stop()
    print(take)
    for sid, info in manifest.streams.items():
        with gzip.open(raw_path(take / "raw", sid), "rt") as f:
            lines = sum(1 for _ in f)
        print(f"  {sid:<15} lines={lines:<7} manifest n_samples={info.n_samples}")
    for w in manifest.warnings:
        print(f"  warning: {w}")


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m physiosync.devcheck")
    p.add_argument("device", choices=sorted(DEVICES))
    p.add_argument("--seconds", type=float, default=10.0)
    p.add_argument("--speed", type=float, default=1.0)
    a = p.parse_args()
    try:
        asyncio.run(run(a.device, a.seconds, a.speed))
    except config.ConfigError as e:
        raise SystemExit(f"physiosync: configuration error: {e}") from None


if __name__ == "__main__":
    main()
