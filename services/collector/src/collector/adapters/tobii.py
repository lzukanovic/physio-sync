"""Tobii Pro Glasses 3 adapter.

The Tobii Pro SDK (``tobii_research``) is licensed for non-commercial research
use and is NOT bundled with this project.  Install it separately::

    pip install tobii-research

If the SDK is not installed the adapter will raise ``ImportError`` on connect.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from collector.adapters.base import AdapterState, BaseAdapter
from collector.sync.clock import system_timestamp_us

logger = logging.getLogger(__name__)

# Try to import at module level so we can report availability early,
# but don't crash if it's missing — the adapter just won't work.
try:
    import tobii_research as tr  # type: ignore[import-untyped]

    TOBII_AVAILABLE = True
except ImportError:
    tr = None  # type: ignore[assignment]
    TOBII_AVAILABLE = False


class TobiiAdapter(BaseAdapter):
    """Adapter for Tobii Pro Glasses 3 (network, 100 Hz gaze data)."""

    def __init__(
        self,
        data_queue: asyncio.Queue,
        address: str,
        device_id: int = 0,
    ) -> None:
        super().__init__(data_queue)
        self.address = address
        self.device_id = device_id

        self.status.device_name = f"Tobii Pro Glasses 3 ({address})"
        self.status.device_type = "tobii"

        self._eyetracker: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self) -> None:
        if not TOBII_AVAILABLE:
            raise ImportError(
                "tobii_research is not installed. "
                "Install it with: pip install tobii-research"
            )

        self.status.state = AdapterState.CONNECTING
        # Find the eye tracker at the given address
        self._eyetracker = tr.EyeTracker(self.address)
        logger.info(
            "Connected to Tobii: %s (serial: %s)",
            self._eyetracker.model,
            self._eyetracker.serial_number,
        )
        self.status.state = AdapterState.CONNECTED

    async def disconnect(self) -> None:
        await self.stop_stream()
        self._eyetracker = None
        self.status.state = AdapterState.DISCONNECTED

    async def start_stream(self) -> None:
        if self._eyetracker is None:
            raise RuntimeError("Not connected — call connect() first")

        self._loop = asyncio.get_running_loop()
        self.status.state = AdapterState.STREAMING
        self.status.samples_received = 0
        self._eyetracker.subscribe_to(
            tr.EYETRACKER_GAZE_DATA, self._on_gaze_data
        )
        logger.info("Tobii gaze stream started")

    async def stop_stream(self) -> None:
        if self._eyetracker is not None:
            try:
                self._eyetracker.unsubscribe_from(
                    tr.EYETRACKER_GAZE_DATA, self._on_gaze_data
                )
            except Exception:
                pass
        if self.status.state == AdapterState.STREAMING:
            self.status.state = AdapterState.CONNECTED

    # -- callback (called from Tobii SDK thread) ----------------------------

    def _on_gaze_data(self, gaze_data: dict[str, Any]) -> None:
        """Push gaze sample onto the async queue."""
        # The SDK provides system_time_stamp in microseconds
        ts = gaze_data.get("system_time_stamp", system_timestamp_us())

        left = gaze_data.get("left_gaze_point_on_display_area", (None, None))
        right = gaze_data.get("right_gaze_point_on_display_area", (None, None))
        left_pupil = gaze_data.get("left_pupil_diameter", None)
        right_pupil = gaze_data.get("right_pupil_diameter", None)

        samples = [
            {"channel": "gaze_left_x", "value": left[0]},
            {"channel": "gaze_left_y", "value": left[1]},
            {"channel": "gaze_right_x", "value": right[0]},
            {"channel": "gaze_right_y", "value": right[1]},
            {"channel": "pupil_left", "value": left_pupil},
            {"channel": "pupil_right", "value": right_pupil},
        ]

        self.status.samples_received += 1

        if self._loop is None:
            return

        for s in samples:
            if s["value"] is None:
                continue
            msg = {
                "timestamp_us": ts,
                "device_id": self.device_id,
                "channel": s["channel"],
                "value": float(s["value"]),
            }
            self._loop.call_soon_threadsafe(self.data_queue.put_nowait, msg)
