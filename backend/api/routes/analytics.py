"""
NeuroVision AI — Analytics REST API
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CrowdAnalytics, Detection, Incident, SystemMetrics, get_db
from core.streaming.manager import stream_manager

router = APIRouter()


@router.get("/crowd/{camera_id}")
async def crowd_timeline(
    camera_id: str,
    hours: int = Query(default=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """Crowd density timeline for a camera."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = (
        select(CrowdAnalytics)
        .where(CrowdAnalytics.camera_id == camera_id)
        .where(CrowdAnalytics.timestamp >= cutoff)
        .order_by(CrowdAnalytics.timestamp)
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "person_count": r.person_count,
            "congestion_score": r.congestion_score,
        }
        for r in rows
    ]


@router.get("/detections/heatmap")
async def detection_heatmap(
    camera_id: Optional[str] = None,
    hours: int = Query(default=6, le=48),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated detection positions for spatial heatmap."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = select(
        Detection.bbox_x, Detection.bbox_y,
        func.count(Detection.id).label("hits")
    ).where(Detection.timestamp >= cutoff)
    if camera_id:
        q = q.where(Detection.camera_id == camera_id)
    q = q.group_by(Detection.bbox_x, Detection.bbox_y).limit(5000)
    result = await db.execute(q)
    return [{"x": r[0], "y": r[1], "count": r[2]} for r in result.all()]


@router.get("/system/metrics")
async def system_metrics_history(
    hours: int = Query(default=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = (
        select(SystemMetrics)
        .where(SystemMetrics.timestamp >= cutoff)
        .order_by(SystemMetrics.timestamp)
        .limit(1000)
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "cpu_percent": r.cpu_percent,
            "memory_percent": r.memory_percent,
            "gpu_percent": r.gpu_percent,
            "total_fps": r.total_fps,
            "active_cameras": r.active_cameras,
        }
        for r in rows
    ]


@router.get("/incidents/timeline")
async def incident_timeline(
    camera_id: Optional[str] = None,
    hours: int = Query(default=24, le=168),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = (
        select(Incident)
        .where(Incident.created_at >= cutoff)
        .order_by(desc(Incident.created_at))
        .limit(200)
    )
    if camera_id:
        q = q.where(Incident.camera_id == camera_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "camera_id": r.camera_id,
            "incident_type": r.incident_type.value,
            "severity": r.severity.value,
            "title": r.title,
            "confidence_score": r.confidence_score,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/live/summary")
async def live_summary():
    """Real-time summary across all active cameras."""
    statuses = stream_manager.get_stream_status()
    alert_engine = stream_manager.get_alert_engine()
    recent_alerts = alert_engine.get_recent_alerts(20) if alert_engine else []

    return {
        "active_cameras": len([s for s in statuses.values() if s["status"] == "running"]),
        "total_cameras": len(statuses),
        "camera_statuses": statuses,
        "recent_alerts": [a.to_dict() for a in recent_alerts],
        "total_recent_alerts": len(recent_alerts),
    }
