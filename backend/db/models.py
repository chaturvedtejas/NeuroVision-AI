"""
NeuroVision AI - Database Models
Complete SQLAlchemy async ORM models
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column

from config.settings import settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class CameraStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    PAUSED = "paused"
    RECORDING = "recording"


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(str, enum.Enum):
    FIGHTING = "fighting"
    RUNNING = "running"
    FALLING = "falling"
    LOITERING = "loitering"
    SUSPICIOUS = "suspicious_movement"
    ABANDONED_OBJECT = "abandoned_object"
    INTRUSION = "intrusion"
    CROWD_CONGESTION = "crowd_congestion"
    ANOMALY = "anomaly"
    OBJECT_DETECTION = "object_detection"


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class ZoneType(str, enum.Enum):
    RESTRICTED = "restricted"
    MONITORING = "monitoring"
    SAFE = "safe"
    ENTRANCE = "entrance"
    EXIT = "exit"


# ─── Models ───────────────────────────────────────────────────────────────────

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    stream_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[CameraStatus] = mapped_column(Enum(CameraStatus), default=CameraStatus.OFFLINE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Capabilities
    has_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_width: Mapped[int] = mapped_column(Integer, default=1280)
    resolution_height: Mapped[int] = mapped_column(Integer, default=720)
    fps: Mapped[float] = mapped_column(Float, default=25.0)

    # PTZ
    is_ptz: Mapped[bool] = mapped_column(Boolean, default=False)
    ptz_config: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)

    # Analytics settings
    detection_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pose_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    metadata_: Mapped[Optional[Dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    zones: Mapped[List["Zone"]] = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    incidents: Mapped[List["Incident"]] = relationship("Incident", back_populates="camera")
    detections: Mapped[List["Detection"]] = relationship("Detection", back_populates="camera")

    __table_args__ = (
        Index("ix_cameras_status", "status"),
        Index("ix_cameras_is_active", "is_active"),
    )


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("cameras.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[ZoneType] = mapped_column(Enum(ZoneType), default=ZoneType.MONITORING)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Polygon coordinates [[x1,y1],[x2,y2],...]  (normalized 0-1)
    polygon: Mapped[List] = mapped_column(JSONB, nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#FF0000")

    # Alert settings
    alert_on_entry: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_exit: Mapped[bool] = mapped_column(Boolean, default=False)
    max_persons: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    alert_schedule: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="zones")

    __table_args__ = (
        UniqueConstraint("camera_id", "name", name="uq_zone_camera_name"),
    )


class TrackedObject(Base):
    __tablename__ = "tracked_objects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("cameras.id"))
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    object_class: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Trajectory as list of {frame, x, y, w, h, timestamp}
    trajectory: Mapped[List] = mapped_column(JSONB, default=list)
    predicted_trajectory: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)

    # Re-ID
    reid_feature: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)
    appearance_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    total_frames: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        Index("ix_tracked_objects_camera_track", "camera_id", "track_id"),
        Index("ix_tracked_objects_class", "object_class"),
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("cameras.id"))
    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Bounding box (normalized)
    bbox_x: Mapped[float] = mapped_column(Float)
    bbox_y: Mapped[float] = mapped_column(Float)
    bbox_w: Mapped[float] = mapped_column(Float)
    bbox_h: Mapped[float] = mapped_column(Float)

    object_class: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float)

    # Pose keypoints
    pose_keypoints: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)

    # Action predictions
    action_predictions: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)

    # Zone info
    zone_ids: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="detections")

    __table_args__ = (
        Index("ix_detections_camera_timestamp", "camera_id", "timestamp"),
        Index("ix_detections_track_id", "track_id"),
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("cameras.id"))
    incident_type: Mapped[IncidentType] = mapped_column(Enum(IncidentType))
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity), default=IncidentSeverity.MEDIUM)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.ACTIVE)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Evidence
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    clip_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    frame_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Context data
    detection_data: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    track_ids: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)
    zone_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)

    # Scores
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="incidents")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="incident")

    __table_args__ = (
        Index("ix_incidents_camera_type", "camera_id", "incident_type"),
        Index("ix_incidents_created_at", "created_at"),
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_severity", "severity"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("incidents.id"))
    camera_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("cameras.id"))

    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity))
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.ACTIVE)

    # Delivery
    delivered_via: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    incident: Mapped["Incident"] = relationship("Incident", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_incident", "incident_id"),
        Index("ix_alerts_created_at", "created_at"),
        Index("ix_alerts_status", "status"),
    )


class CrowdAnalytics(Base):
    __tablename__ = "crowd_analytics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("cameras.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    frame_number: Mapped[int] = mapped_column(Integer)

    person_count: Mapped[int] = mapped_column(Integer, default=0)
    density_map: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)  # Compressed grid
    flow_vectors: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)
    heatmap_data: Mapped[Optional[List]] = mapped_column(JSONB, nullable=True)

    avg_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    congestion_score: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        Index("ix_crowd_analytics_camera_timestamp", "camera_id", "timestamp"),
    )


class SystemMetrics(Base):
    __tablename__ = "system_metrics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cpu_percent: Mapped[float] = mapped_column(Float)
    memory_percent: Mapped[float] = mapped_column(Float)
    gpu_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gpu_memory_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    active_cameras: Mapped[int] = mapped_column(Integer, default=0)
    total_fps: Mapped[float] = mapped_column(Float, default=0.0)
    total_detections: Mapped[int] = mapped_column(Integer, default=0)
    active_tracks: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_system_metrics_timestamp", "timestamp"),
    )


# ─── Database Engine & Session ────────────────────────────────────────────────

engine = create_async_engine(
    settings.db.async_url,
    pool_size=settings.db.pool_size,
    max_overflow=settings.db.max_overflow,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db():
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
