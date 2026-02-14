"""Sensor data schemas."""

from datetime import datetime

from pydantic import BaseModel


class SensorSample(BaseModel):
    timestamp_us: int
    device_id: int
    channel: str
    value: float
    sequence: int | None = None


class SensorDataRead(BaseModel):
    time: datetime
    device_id: int
    recording_id: int
    channel: str
    value: float
    sequence: int | None

    model_config = {"from_attributes": True}
