"""Device CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.session import get_db
from api.models.device import Device
from api.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate

router = APIRouter()


@router.get("/", response_model=list[DeviceRead])
async def list_devices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).order_by(Device.id))
    return result.scalars().all()


@router.post("/", response_model=DeviceRead, status_code=201)
async def create_device(body: DeviceCreate, db: AsyncSession = Depends(get_db)):
    device = Device(**body.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    return device


@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: int, body: DeviceUpdate, db: AsyncSession = Depends(get_db)
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    for key, val in body.model_dump(exclude_unset=True).items():
        setattr(device, key, val)
    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    await db.delete(device)
    await db.commit()
