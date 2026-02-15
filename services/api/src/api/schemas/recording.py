"""Recording schemas."""

from datetime import datetime

from pydantic import BaseModel


class RecordingCreate(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = []
    metadata: dict = {}


class RecordingRead(BaseModel):
    id: int
    name: str
    description: str | None
    tags: list[str]
    status: str
    started_at: datetime | None
    stopped_at: datetime | None
    device_configs: list[dict]
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
