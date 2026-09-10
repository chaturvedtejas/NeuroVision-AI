"""NeuroVision AI — Alerts Route"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Alert, get_db
from typing import Optional

router = APIRouter()

@router.get("")
async def list_alerts(
    camera_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    if camera_id:
        q = q.where(Alert.camera_id == camera_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "incident_id": r.incident_id,
            "camera_id": r.camera_id,
            "alert_type": r.alert_type,
            "message": r.message,
            "severity": r.severity.value,
            "status": r.status.value,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    from datetime import datetime
    from sqlalchemy import select
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    from db.models import AlertStatus
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.utcnow()
    await db.flush()
    return {"alert_id": alert_id, "status": "acknowledged"}
