"""Collector entry point — orchestrates adapters and the WS transport."""

from __future__ import annotations

import asyncio
import logging
import signal

from collector.config import settings
from collector.transport.ws_client import stream_to_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    data_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)
    stop_event = asyncio.Event()

    # Graceful shutdown on SIGINT / SIGTERM
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # Start the WS transport (sends queued data to the API)
    transport_task = asyncio.create_task(
        stream_to_api(data_queue, settings.collector_api_ws_url, stop_event=stop_event)
    )

    # --- Adapter startup (to be wired up when devices are configured) ---
    # For now just log readiness; individual adapters will be started via
    # API commands or config in a future iteration.
    logger.info("Collector ready — waiting for adapter commands")
    logger.info("  API WebSocket: %s", settings.collector_api_ws_url)
    if settings.bitalino_address:
        logger.info("  BITalino configured: %s", settings.bitalino_address)
    if settings.tobii_address:
        logger.info("  Tobii configured: %s", settings.tobii_address)

    # Block until stop
    await stop_event.wait()
    logger.info("Shutting down …")
    transport_task.cancel()
    try:
        await transport_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
