"""Sensor data model (TimescaleDB hypertable)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class SensorData(Base):
    __tablename__ = "sensor_data"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id"), primary_key=True
    )
    recording_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recordings.id"), primary_key=True
    )
    channel: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    sequence: Mapped[int | None] = mapped_column(BigInteger)
