"""Recording schemas."""

from datetime import datetime

from pydantic import BaseModel


class RecordingCreate(BaseModel):
    name: str
    device_ids: list[int] = []
    metadata: dict = {}


class RecordingRead(BaseModel):
    id: int
    name: str
    status: str
    started_at: datetime | None
    stopped_at: datetime | None
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
