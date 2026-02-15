"""Device schemas."""

from datetime import datetime

from pydantic import BaseModel


class DeviceCreate(BaseModel):
    name: str
    type: str
    address: str | None = None
    sample_rate: int | None = None
    channels: list[dict] = []
    config: dict = {}


class DeviceUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    sample_rate: int | None = None
    channels: list[dict] | None = None
    config: dict | None = None


class DeviceRead(BaseModel):
    id: int
    name: str
    type: str
    address: str | None
    sample_rate: int | None
    channels: list[dict]
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
