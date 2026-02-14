"""Recording management endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.session import get_db
from api.models.recording import Recording, RecordingDevice
from api.schemas.recording import RecordingCreate, RecordingRead

router = APIRouter()


@router.get("/", response_model=list[RecordingRead])
async def list_recordings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Recording).order_by(Recording.id.desc()))
    return result.scalars().all()


@router.post("/", response_model=RecordingRead, status_code=201)
async def create_recording(body: RecordingCreate, db: AsyncSession = Depends(get_db)):
    recording = Recording(
        name=body.name,
        metadata_=body.metadata,
    )
    db.add(recording)
    await db.flush()

    for dev_id in body.device_ids:
        db.add(RecordingDevice(recording_id=recording.id, device_id=dev_id))

    await db.commit()
    await db.refresh(recording)
    return recording


@router.get("/{recording_id}", response_model=RecordingRead)
async def get_recording(recording_id: int, db: AsyncSession = Depends(get_db)):
    recording = await db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(404, "Recording not found")
    return recording


@router.post("/{recording_id}/start", response_model=RecordingRead)
async def start_recording(recording_id: int, db: AsyncSession = Depends(get_db)):
    recording = await db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(404, "Recording not found")
    recording.status = "running"
    recording.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(recording)
    return recording


@router.post("/{recording_id}/stop", response_model=RecordingRead)
async def stop_recording(recording_id: int, db: AsyncSession = Depends(get_db)):
    recording = await db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(404, "Recording not found")
    recording.status = "stopped"
    recording.stopped_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(recording)
    return recording
