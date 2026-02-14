"""WebSocket client that forwards queued samples to the API service."""

from __future__ import annotations

import asyncio
import json
import logging

import websockets

logger = logging.getLogger(__name__)

# How many samples to batch before sending (reduces WS overhead)
BATCH_SIZE = 50
# Max seconds to wait before flushing an incomplete batch
FLUSH_INTERVAL = 0.1


async def stream_to_api(
    data_queue: asyncio.Queue,
    ws_url: str,
    *,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Read samples from *data_queue* and send them to the API over WebSocket.

    Reconnects automatically on connection loss.
    """
    stop = stop_event or asyncio.Event()

    while not stop.is_set():
        try:
            async with websockets.connect(ws_url) as ws:
                logger.info("Connected to API WebSocket: %s", ws_url)
                batch: list[dict] = []

                while not stop.is_set():
                    try:
                        sample = await asyncio.wait_for(
                            data_queue.get(), timeout=FLUSH_INTERVAL
                        )
                        batch.append(sample)

                        if len(batch) >= BATCH_SIZE:
                            await ws.send(json.dumps(batch))
                            batch = []
                    except asyncio.TimeoutError:
                        # Flush partial batch
                        if batch:
                            await ws.send(json.dumps(batch))
                            batch = []

        except (
            websockets.ConnectionClosed,
            ConnectionRefusedError,
            OSError,
        ) as exc:
            logger.warning("WebSocket disconnected (%s), reconnecting in 2s …", exc)
            await asyncio.sleep(2)
