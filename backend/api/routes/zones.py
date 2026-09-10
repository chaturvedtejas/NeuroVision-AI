"""NeuroVision AI — Zones Route"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Zone, ZoneType, get_db

router = APIRouter()

class ZoneCreate(BaseModel):
    camera_id: str
    name: str
    zone_type: ZoneType = ZoneType.RESTRICTED
    polygon: List[List[float]]
    color: str = "#FF0000"
    alert_on_entry: bool = True
    alert_on_exit: bool = False
    max_persons: Optional[int] = None

@router.get("/{camera_id}")
async def list_zones(camera_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Zone).where(Zone.camera_id == camera_id))
    zones = result.scalars().all()
    return [
        {
            "id": z.id, "camera_id": z.camera_id, "name": z.name,
            "zone_type": z.zone_type.value, "polygon": z.polygon,
            "color": z.color, "is_active": z.is_active,
            "alert_on_entry": z.alert_on_entry,
        }
        for z in zones
    ]

@router.post("", status_code=201)
async def create_zone(body: ZoneCreate, db: AsyncSession = Depends(get_db)):
    zone = Zone(
        id=str(uuid.uuid4()),
        camera_id=body.camera_id,
        name=body.name,
        zone_type=body.zone_type,
        polygon=body.polygon,
        color=body.color,
        alert_on_entry=body.alert_on_entry,
        alert_on_exit=body.alert_on_exit,
        max_persons=body.max_persons,
    )
    db.add(zone)
    await db.flush()
    await db.refresh(zone)
    return {"id": zone.id, "name": zone.name, "zone_type": zone.zone_type.value}

@router.delete("/{zone_id}", status_code=204)
async def delete_zone(zone_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    await db.delete(zone)
