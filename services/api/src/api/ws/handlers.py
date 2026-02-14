"""WebSocket endpoints for collector intake and frontend push.

- ``/ws/collector``: receives batched samples from the collector service.
- ``/ws/live``: pushes real-time data to connected frontend clients.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import insert

from api.db.session import async_session
from api.models.sensor_data import SensorData

logger = logging.getLogger(__name__)
router = APIRouter()

# Connected frontend clients
_live_clients: set[WebSocket] = set()


@router.websocket("/ws/collector")
async def collector_intake(ws: WebSocket):
    """Receive batched sensor samples from the collector and write to DB."""
    await ws.accept()
    logger.info("Collector connected")

    try:
        while True:
            raw = await ws.receive_text()
            samples = json.loads(raw)

            if not samples:
                continue

            # Convert to DB rows
            rows = []
            for s in samples:
                rows.append(
                    {
                        "time": datetime.fromtimestamp(
                            s["timestamp_us"] / 1_000_000, tz=timezone.utc
                        ),
                        "device_id": s["device_id"],
                        "recording_id": s.get("recording_id", 1),
                        "channel": s["channel"],
                        "value": s["value"],
                        "sequence": s.get("sequence"),
                    }
                )

            # Bulk insert
            async with async_session() as session:
                await session.execute(insert(SensorData), rows)
                await session.commit()

            # Forward to live clients
            for client in list(_live_clients):
                try:
                    await client.send_text(raw)
                except Exception:
                    _live_clients.discard(client)

    except WebSocketDisconnect:
        logger.info("Collector disconnected")


@router.websocket("/ws/live")
async def live_stream(ws: WebSocket):
    """Push real-time data to a frontend client."""
    await ws.accept()
    _live_clients.add(ws)
    logger.info("Live client connected (%d total)", len(_live_clients))
    try:
        while True:
            # Keep connection alive; client only listens
            await ws.receive_text()
    except WebSocketDisconnect:
        _live_clients.discard(ws)
        logger.info("Live client disconnected (%d total)", len(_live_clients))
