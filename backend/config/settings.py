"""
NeuroVision AI - Configuration Management
Centralized settings with environment variable support
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=5432, alias="DB_PORT")
    name: str = Field(default="neurovision", alias="DB_NAME")
    user: str = Field(default="neurovision", alias="DB_USER")
    password: str = Field(default="neurovision_secret", alias="DB_PASSWORD")
    pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    class Config:
        populate_by_name = True


class RedisSettings(BaseSettings):
    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    db: int = Field(default=0, alias="REDIS_DB")
    max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

    class Config:
        populate_by_name = True


class AISettings(BaseSettings):
    # Model paths
    models_dir: Path = Field(default=Path("/app/models"), alias="MODELS_DIR")
    yolo_model: str = Field(default="yolov8n.pt", alias="YOLO_MODEL")
    pose_model: str = Field(default="yolov8n-pose.pt", alias="POSE_MODEL")

    # Inference
    device: str = Field(default="cuda", alias="AI_DEVICE")
    half_precision: bool = Field(default=True, alias="AI_HALF_PRECISION")
    batch_size: int = Field(default=4, alias="AI_BATCH_SIZE")
    confidence_threshold: float = Field(default=0.45, alias="CONF_THRESHOLD")
    iou_threshold: float = Field(default=0.45, alias="IOU_THRESHOLD")

    # Detection classes
    detect_classes: List[int] = Field(default=[0, 24, 26, 28, 32, 39, 41, 67, 73])
    # 0=person, 24=backpack, 26=handbag, 28=suitcase, 32=sports_ball,
    # 39=bottle, 41=cup, 67=cell_phone, 73=laptop

    # Tracking
    track_max_age: int = Field(default=30, alias="TRACK_MAX_AGE")
    track_min_hits: int = Field(default=3, alias="TRACK_MIN_HITS")
    track_iou_threshold: float = Field(default=0.3, alias="TRACK_IOU_THRESHOLD")

    # Trajectory
    trajectory_history_frames: int = Field(default=30, alias="TRAJ_HISTORY")
    trajectory_predict_frames: int = Field(default=15, alias="TRAJ_PREDICT")

    # Anomaly
    anomaly_threshold: float = Field(default=0.75, alias="ANOMALY_THRESHOLD")

    # ONNX/TensorRT
    use_tensorrt: bool = Field(default=False, alias="USE_TENSORRT")
    use_onnx: bool = Field(default=False, alias="USE_ONNX")

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        import torch
        if v == "cuda" and not torch.cuda.is_available():
            return "cpu"
        return v

    class Config:
        populate_by_name = True


class StreamingSettings(BaseSettings):
    max_cameras: int = Field(default=16, alias="MAX_CAMERAS")
    frame_width: int = Field(default=1280, alias="FRAME_WIDTH")
    frame_height: int = Field(default=720, alias="FRAME_HEIGHT")
    target_fps: int = Field(default=25, alias="TARGET_FPS")
    jpeg_quality: int = Field(default=85, alias="JPEG_QUALITY")
    buffer_size: int = Field(default=10, alias="STREAM_BUFFER_SIZE")
    reconnect_delay: float = Field(default=2.0, alias="RECONNECT_DELAY")
    max_reconnect_attempts: int = Field(default=5, alias="MAX_RECONNECT")

    class Config:
        populate_by_name = True


class AlertSettings(BaseSettings):
    # Zone violation
    zone_alert_cooldown: int = Field(default=30, alias="ZONE_COOLDOWN")

    # Crowd
    crowd_density_threshold: float = Field(default=0.7, alias="CROWD_THRESHOLD")
    max_persons_threshold: int = Field(default=50, alias="MAX_PERSONS")

    # Loitering
    loiter_time_threshold: int = Field(default=60, alias="LOITER_TIME")

    # Abandoned object
    abandoned_time_threshold: int = Field(default=30, alias="ABANDONED_TIME")

    # Webhook
    webhook_url: Optional[str] = Field(default=None, alias="ALERT_WEBHOOK_URL")
    webhook_timeout: float = Field(default=5.0, alias="WEBHOOK_TIMEOUT")

    class Config:
        populate_by_name = True


class SecuritySettings(BaseSettings):
    secret_key: str = Field(default="change-me-in-production-please", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE")
    api_key: Optional[str] = Field(default=None, alias="API_KEY")

    class Config:
        populate_by_name = True


class Settings(BaseSettings):
    # App
    app_name: str = "NeuroVision AI"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="DEBUG")
    environment: str = Field(default="production", alias="ENVIRONMENT")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ORIGINS"
    )

    # Subconfigs
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    ai: AISettings = Field(default_factory=AISettings)
    streaming: StreamingSettings = Field(default_factory=StreamingSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    # Storage
    upload_dir: Path = Field(default=Path("/app/data/uploads"), alias="UPLOAD_DIR")
    recordings_dir: Path = Field(default=Path("/app/data/recordings"), alias="RECORDINGS_DIR")
    reports_dir: Path = Field(default=Path("/app/data/reports"), alias="REPORTS_DIR")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        for d in [self.upload_dir, self.recordings_dir, self.reports_dir, self.ai.models_dir]:
            d.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
