"""Abstract base class that every sensor adapter must implement."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AdapterState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    ERROR = "error"


@dataclass
class AdapterStatus:
    state: AdapterState = AdapterState.DISCONNECTED
    device_name: str = ""
    device_type: str = ""
    samples_received: int = 0
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "samples_received": self.samples_received,
            "error": self.error,
            **self.extra,
        }


class BaseAdapter(ABC):
    """Interface that all sensor adapters must implement.

    Data produced by the adapter is placed onto *data_queue* as dicts
    with at least the keys: ``timestamp_us``, ``device_id``, ``channel``,
    ``value``.
    """

    def __init__(self, data_queue: asyncio.Queue) -> None:
        self.data_queue = data_queue
        self.status = AdapterStatus()

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the device."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Cleanly disconnect from the device."""

    @abstractmethod
    async def start_stream(self) -> None:
        """Begin streaming data into *data_queue*."""

    @abstractmethod
    async def stop_stream(self) -> None:
        """Stop streaming data."""

    def get_status(self) -> dict[str, Any]:
        """Return current adapter status as a dict."""
        return self.status.to_dict()
