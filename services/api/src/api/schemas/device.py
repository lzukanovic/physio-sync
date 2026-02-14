"""Device schemas."""

from datetime import datetime

from pydantic import BaseModel


class DeviceCreate(BaseModel):
    name: str
    type: str
    address: str | None = None
    config: dict = {}


class DeviceUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    config: dict | None = None


class DeviceRead(BaseModel):
    id: int
    name: str
    type: str
    address: str | None
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
