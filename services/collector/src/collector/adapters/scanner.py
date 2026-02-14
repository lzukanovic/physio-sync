"""SCANeR driving simulator adapter — placeholder.

The data access method for SCANeR is still under research.
This adapter implements the BaseAdapter interface with no-op methods
so the rest of the system can reference it without breaking.
"""

from __future__ import annotations

import asyncio
import logging

from collector.adapters.base import AdapterState, BaseAdapter

logger = logging.getLogger(__name__)


class ScannerAdapter(BaseAdapter):
    """Placeholder adapter for the SCANeR driving simulator."""

    def __init__(self, data_queue: asyncio.Queue, device_id: int = 0) -> None:
        super().__init__(data_queue)
        self.device_id = device_id
        self.status.device_name = "SCANeR (not implemented)"
        self.status.device_type = "scanner"

    async def connect(self) -> None:
        logger.warning("SCANeR adapter is a placeholder — connect is a no-op")
        self.status.state = AdapterState.CONNECTED

    async def disconnect(self) -> None:
        self.status.state = AdapterState.DISCONNECTED

    async def start_stream(self) -> None:
        logger.warning("SCANeR adapter is a placeholder — start_stream is a no-op")
        self.status.state = AdapterState.STREAMING

    async def stop_stream(self) -> None:
        self.status.state = AdapterState.CONNECTED
