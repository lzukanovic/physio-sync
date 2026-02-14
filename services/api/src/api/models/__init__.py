"""SQLAlchemy models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from api.models.device import Device  # noqa: E402, F401
from api.models.recording import Recording, RecordingDevice  # noqa: E402, F401
from api.models.sensor_data import SensorData  # noqa: E402, F401
