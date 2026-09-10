"""
NeuroVision AI — Incidents REST API
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Alert, AlertStatus, Incident, IncidentSeverity, IncidentType, get_db

router = APIRouter()


class IncidentResponse(BaseModel):
    id: str
    camera_id: str
    incident_type: str
    severity: str
    status: str
    title: str
    description: Optional[str]
    ai_summary: Optional[str]
    confidence_score: float
    snapshot_path: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_safe(cls, obj: Incident) -> "IncidentResponse":
        return cls(
            id=obj.id,
            camera_id=obj.camera_id,
            incident_type=obj.incident_type.value,
            severity=obj.severity.value,
            status=obj.status.value,
            title=obj.title,
            description=obj.description,
            ai_summary=obj.ai_summary,
            confidence_score=obj.confidence_score,
            snapshot_path=obj.snapshot_path,
            created_at=obj.created_at.isoformat(),
        )


class IncidentCreate(BaseModel):
    camera_id: str
    incident_type: IncidentType
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    title: str
    description: Optional[str] = None
    confidence_score: float = 0.0
    detection_data: Optional[dict] = None
    track_ids: Optional[List[int]] = None


class IncidentAcknowledge(BaseModel):
    resolved_by: str
    resolution_notes: Optional[str] = None


@router.get("", response_model=List[dict])
async def list_incidents(
    camera_id: Optional[str] = None,
    incident_type: Optional[IncidentType] = None,
    severity: Optional[IncidentSeverity] = None,
    status: Optional[AlertStatus] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(Incident).order_by(desc(Incident.created_at))
    if camera_id:
        q = q.where(Incident.camera_id == camera_id)
    if incident_type:
        q = q.where(Incident.incident_type == incident_type)
    if severity:
        q = q.where(Incident.severity == severity)
    if status:
        q = q.where(Incident.status == status)
    q = q.limit(limit).offset(offset)

    result = await db.execute(q)
    incidents = result.scalars().all()
    return [IncidentResponse.from_orm_safe(i).__dict__ for i in incidents]


@router.post("", status_code=201)
async def create_incident(body: IncidentCreate, db: AsyncSession = Depends(get_db)):
    inc = Incident(
        id=str(uuid.uuid4()),
        camera_id=body.camera_id,
        incident_type=body.incident_type,
        severity=body.severity,
        title=body.title,
        description=body.description,
        confidence_score=body.confidence_score,
        detection_data=body.detection_data,
        track_ids=body.track_ids,
    )
    db.add(inc)
    await db.flush()
    await db.refresh(inc)
    return IncidentResponse.from_orm_safe(inc)


@router.get("/{incident_id}")
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    inc = await _get_or_404(incident_id, db)
    return IncidentResponse.from_orm_safe(inc)


@router.post("/{incident_id}/acknowledge")
async def acknowledge_incident(
    incident_id: str,
    body: IncidentAcknowledge,
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    inc = await _get_or_404(incident_id, db)
    inc.status = AlertStatus.RESOLVED
    inc.resolved_by = body.resolved_by
    inc.resolution_notes = body.resolution_notes
    inc.resolved_at = datetime.utcnow()
    await db.flush()
    return {"incident_id": incident_id, "status": "acknowledged"}


@router.delete("/{incident_id}", status_code=204)
async def delete_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    inc = await _get_or_404(incident_id, db)
    await db.delete(inc)


@router.get("/stats/summary")
async def incident_summary(
    camera_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    q = select(
        Incident.incident_type,
        Incident.severity,
        func.count(Incident.id).label("count"),
    ).group_by(Incident.incident_type, Incident.severity)
    if camera_id:
        q = q.where(Incident.camera_id == camera_id)
    result = await db.execute(q)
    rows = result.all()
    return [
        {"incident_type": r[0].value, "severity": r[1].value, "count": r[2]}
        for r in rows
    ]


async def _get_or_404(incident_id: str, db: AsyncSession) -> Incident:
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc
