"""Sensor data query endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.session import get_db
from api.models.sensor_data import SensorData
from api.schemas.sensor_data import SensorDataRead

router = APIRouter()


@router.get("/{recording_id}", response_model=list[SensorDataRead])
async def get_recording_data(
    recording_id: int,
    device_id: int | None = None,
    channel: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=10000, le=100000),
    db: AsyncSession = Depends(get_db),
):
    q = select(SensorData).where(SensorData.recording_id == recording_id)
    if device_id is not None:
        q = q.where(SensorData.device_id == device_id)
    if channel is not None:
        q = q.where(SensorData.channel == channel)
    if start is not None:
        q = q.where(SensorData.time >= start)
    if end is not None:
        q = q.where(SensorData.time <= end)
    q = q.order_by(SensorData.time).limit(limit)

    result = await db.execute(q)
    return result.scalars().all()
