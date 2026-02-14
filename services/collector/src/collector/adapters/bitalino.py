"""BITalino adapter — Bluetooth-based physiological signal acquisition.

Adapts the PLUX SDK callback model to the async BaseAdapter interface.
The PLUX SDK runs a blocking acquisition loop in a background thread;
data is forwarded to the async queue via ``loop.call_soon_threadsafe``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import sys
import threading
import time
from typing import Any

from collector.adapters.base import AdapterState, BaseAdapter
from collector.sync.clock import system_timestamp_us

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PLUX binary loader (adapted from bitalino-mvp/utils/plux_loader.py)
# ---------------------------------------------------------------------------

def _get_plux_binary_dir() -> str:
    """Return the subdirectory name for the current platform's PLUX binary."""
    system = platform.system()
    py_ver = "".join(platform.python_version_tuple()[:2])

    if system == "Darwin":
        arch = "M1" if platform.machine() == "arm64" else "Intel"
        return f"{arch}_{py_ver}"
    elif system == "Linux":
        machine = platform.machine()
        if machine == "x86_64":
            return "Linux64"
        elif machine == "aarch64":
            return f"LinuxARM64_{py_ver}" if py_ver in ("38", "39") else "LinuxARM64_38"
        elif "arm" in machine:
            return "LinuxARM32_311" if py_ver == "311" else "LinuxARM32"
    elif system == "Windows":
        bits = platform.architecture()[0][:2]
        return f"Win{bits}_{py_ver}"

    raise OSError(f"Unsupported platform: {system} {platform.machine()}")


def _load_plux(base_path: str | None = None):
    """Import the ``plux`` module after adding the correct binary path."""
    if base_path is None:
        # Default: services/collector/PLUX-API-Python3
        base_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            os.pardir, os.pardir, os.pardir, os.pardir,
            "PLUX-API-Python3",
        )
        base_path = os.path.normpath(base_path)

    binary_dir = _get_plux_binary_dir()
    full_path = os.path.join(base_path, binary_dir)

    if full_path not in sys.path:
        sys.path.insert(0, full_path)

    import plux  # noqa: E402
    logger.info("Loaded PLUX library from %s", full_path)
    return plux


# ---------------------------------------------------------------------------
# BITalino device wrapper (runs in a thread)
# ---------------------------------------------------------------------------

class _BITalinoDevice:
    """Thin wrapper around ``plux.SignalsDev`` created inside the worker thread.

    We cannot subclass plux.SignalsDev at import time because the ``plux``
    module may not yet be on sys.path.  Instead we build the subclass lazily.
    """

    def __init__(
        self,
        plux_mod: Any,
        address: str,
        frequency: int,
        channel_code: int,
        on_sample: Any,
    ) -> None:
        # Dynamically create the subclass so we can override onRawFrame
        outer_on_sample = on_sample
        outer_running = threading.Event()
        outer_running.set()

        class _Dev(plux_mod.SignalsDev):
            def __init__(inner_self, addr: str):
                plux_mod.SignalsDev.__init__(inner_self, addr)
                inner_self.running = outer_running

            def onRawFrame(inner_self, nSeq: int, data: list) -> bool:
                if inner_self.running.is_set():
                    outer_on_sample(nSeq, data)
                return not inner_self.running.is_set()

        self._dev = _Dev(address)
        self._running = outer_running
        self.frequency = frequency
        self.channel_code = channel_code

    def start(self) -> None:
        self._running.set()
        battery = self._dev.getBattery()
        logger.info("BITalino battery: %d%%", battery)
        self._dev.start(self.frequency, self.channel_code, 16)
        self._dev.loop()  # blocks until onRawFrame returns True

    def stop(self) -> None:
        self._running.clear()

    def close(self) -> None:
        try:
            self._dev.stop()
        except Exception:
            pass
        try:
            self._dev.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Async adapter
# ---------------------------------------------------------------------------

class BITalinoAdapter(BaseAdapter):
    """Adapter for BITalino devices via Bluetooth (PLUX SDK)."""

    def __init__(
        self,
        data_queue: asyncio.Queue,
        address: str,
        frequency: int = 100,
        channel_code: int = 0x01,
        device_id: int = 0,
    ) -> None:
        super().__init__(data_queue)
        self.address = address
        self.frequency = frequency
        self.channel_code = channel_code
        self.device_id = device_id

        self.status.device_name = f"BITalino ({address})"
        self.status.device_type = "bitalino"

        self._device: _BITalinoDevice | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # -- BaseAdapter ---------------------------------------------------------

    async def connect(self) -> None:
        self.status.state = AdapterState.CONNECTING
        logger.info("Loading PLUX library …")
        self._plux = _load_plux()
        self.status.state = AdapterState.CONNECTED
        logger.info("BITalino adapter ready (address=%s)", self.address)

    async def disconnect(self) -> None:
        await self.stop_stream()
        self.status.state = AdapterState.DISCONNECTED

    async def start_stream(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.warning("Stream already running")
            return

        self._loop = asyncio.get_running_loop()
        self.status.state = AdapterState.STREAMING
        self.status.samples_received = 0

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    async def stop_stream(self) -> None:
        if self._device:
            self._device.stop()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        if self._device:
            self._device.close()
            self._device = None
        if self.status.state == AdapterState.STREAMING:
            self.status.state = AdapterState.CONNECTED

    # -- internals -----------------------------------------------------------

    def _on_sample(self, nSeq: int, data: list) -> None:
        """Called from the PLUX thread for every raw frame."""
        ts = system_timestamp_us()
        value = data[0] if data else 0
        sample = {
            "timestamp_us": ts,
            "device_id": self.device_id,
            "channel": "ecg",
            "value": value,
            "sequence": nSeq,
        }
        self.status.samples_received += 1
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self.data_queue.put_nowait, sample)

    def _worker(self) -> None:
        """Background thread: connect, acquire, clean up."""
        try:
            self._device = _BITalinoDevice(
                self._plux,
                self.address,
                self.frequency,
                self.channel_code,
                self._on_sample,
            )
            self._device.start()
        except Exception as exc:
            logger.exception("BITalino worker error")
            self.status.state = AdapterState.ERROR
            self.status.error = str(exc)
