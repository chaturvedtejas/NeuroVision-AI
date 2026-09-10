"""
NeuroVision AI - Anomaly Detection
Autoencoder-based unsupervised anomaly scoring
plus statistical trajectory anomaly detection
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from loguru import logger

from app.tracking.tracker import TrackState
from config.settings import settings


@dataclass
class AnomalyResult:
    camera_id: str
    track_id: int
    anomaly_score: float   # 0-1 (higher = more anomalous)
    is_anomaly: bool
    anomaly_type: str
    details: Dict
    timestamp: float

    def to_dict(self) -> Dict:
        return {
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "anomaly_score": round(self.anomaly_score, 3),
            "is_anomaly": self.is_anomaly,
            "anomaly_type": self.anomaly_type,
            "details": self.details,
            "timestamp": self.timestamp,
        }


# ─── Trajectory Autoencoder ───────────────────────────────────────────────────

class TrajectoryAutoencoder(nn.Module):
    """
    Sequence autoencoder for trajectory anomaly detection.
    Reconstruction error indicates how "unusual" a trajectory is.
    """

    def __init__(self, seq_len: int = 20, latent_dim: int = 16):
        super().__init__()
        self.seq_len = seq_len
        input_dim = seq_len * 2  # Flattened x,y

        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Linear(64, latent_dim),
        )

        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(64, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, input_dim),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.encoder(x)
        x_hat = self.decoder(z)
        return x_hat, z

    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        x_hat, _ = self.forward(x)
        return torch.mean((x - x_hat) ** 2, dim=-1)


# ─── Statistical Anomaly Detector ────────────────────────────────────────────

class StatisticalAnomalyDetector:
    """
    Running statistics-based anomaly detection.
    Tracks per-camera baseline statistics and flags deviations.
    """

    def __init__(self, window: int = 500, n_sigma: float = 3.0):
        self.window = window
        self.n_sigma = n_sigma
        # Per-camera speed statistics
        self._speed_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self._direction_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self._count_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window))

    def update_baseline(self, camera_id: str, tracks: List[TrackState]) -> None:
        """Update per-camera statistical baselines."""
        speeds = []
        for track in tracks:
            if len(track.trajectory) >= 3:
                traj = track.trajectory
                dx = traj[-1][0] - traj[-2][0]
                dy = traj[-1][1] - traj[-2][1]
                speed = np.sqrt(dx**2 + dy**2)
                speeds.append(speed)

        if speeds:
            self._speed_buffers[camera_id].extend(speeds)
        self._count_buffers[camera_id].append(len(tracks))

    def score_track(
        self,
        camera_id: str,
        track: TrackState,
    ) -> float:
        """Score anomalousness of a track (0-1)."""
        if len(track.trajectory) < 3:
            return 0.0

        speed_buf = self._speed_buffers[camera_id]
        if len(speed_buf) < 30:
            return 0.0

        traj = track.trajectory
        dx = traj[-1][0] - traj[-2][0]
        dy = traj[-1][1] - traj[-2][1]
        speed = np.sqrt(dx**2 + dy**2)

        mean_speed = np.mean(speed_buf)
        std_speed = np.std(speed_buf) + 1e-8

        z_score = abs(speed - mean_speed) / std_speed
        anomaly_score = 1 - np.exp(-z_score / self.n_sigma)

        return float(np.clip(anomaly_score, 0, 1))

    def score_crowd(self, camera_id: str, current_count: int) -> float:
        """Score anomalousness of current crowd count."""
        count_buf = self._count_buffers[camera_id]
        if len(count_buf) < 30:
            return 0.0

        mean = np.mean(count_buf)
        std = np.std(count_buf) + 1e-8
        z = abs(current_count - mean) / std
        return float(np.clip(1 - np.exp(-z / 3.0), 0, 1))


# ─── Abandoned Object Detection ───────────────────────────────────────────────

class AbandonedObjectDetector:
    """
    Detects objects (bags, suitcases) left unattended
    by tracking their presence without an associated person nearby.
    """

    def __init__(self, time_threshold: int = 30):
        self.time_threshold = time_threshold
        # {camera_id: {track_id: (bbox_center, first_seen_time, last_person_nearby_time)}}
        self._object_records: Dict[str, Dict[int, Dict]] = defaultdict(dict)

    def update(
        self,
        camera_id: str,
        object_tracks: List[TrackState],
        person_tracks: List[TrackState],
        frame_timestamp: float,
    ) -> List[Dict]:
        """
        Update object tracking and return list of abandoned objects.
        object_tracks: non-person objects (bags, suitcases)
        person_tracks: all detected persons
        """
        abandoned = []
        cam_records = self._object_records[camera_id]

        # Build person position set
        person_centers = [t.bbox.center for t in person_tracks]

        for obj_track in object_tracks:
            if obj_track.class_name not in ("backpack", "handbag", "suitcase"):
                continue

            tid = obj_track.track_id
            obj_center = obj_track.bbox.center

            # Check if any person is nearby
            min_dist = 1.0
            if person_centers:
                dists = [
                    np.sqrt((obj_center[0] - pc[0])**2 + (obj_center[1] - pc[1])**2)
                    for pc in person_centers
                ]
                min_dist = min(dists)

            person_nearby = min_dist < 0.2  # Proximity threshold

            if tid not in cam_records:
                cam_records[tid] = {
                    "first_seen": frame_timestamp,
                    "last_person_nearby": frame_timestamp if person_nearby else None,
                    "class_name": obj_track.class_name,
                    "center": obj_center,
                }
            else:
                cam_records[tid]["center"] = obj_center
                if person_nearby:
                    cam_records[tid]["last_person_nearby"] = frame_timestamp

            record = cam_records[tid]
            last_person = record.get("last_person_nearby")

            # Object is abandoned if no person nearby for N seconds
            if last_person is None:
                alone_time = frame_timestamp - record["first_seen"]
            else:
                alone_time = frame_timestamp - last_person

            if alone_time > self.time_threshold:
                abandoned.append({
                    "track_id": tid,
                    "class_name": record["class_name"],
                    "center": obj_center,
                    "alone_time_sec": round(alone_time),
                    "confidence": min(0.95, 0.5 + alone_time / 120),
                })

        # Clean up tracks that are gone
        active_ids = {t.track_id for t in object_tracks}
        stale = [tid for tid in cam_records if tid not in active_ids]
        for tid in stale:
            del cam_records[tid]

        return abandoned


# ─── Zone Intrusion Detector ─────────────────────────────────────────────────

class ZoneIntrusionDetector:
    """
    Detects when tracked objects enter restricted zones.
    Zones are defined as normalized polygons.
    """

    @staticmethod
    def point_in_polygon(
        point: Tuple[float, float],
        polygon: List[Tuple[float, float]],
    ) -> bool:
        """Ray casting algorithm for point-in-polygon test."""
        x, y = point
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def check_intrusion(
        self,
        tracks: List[TrackState],
        zones: List[Dict],
    ) -> List[Dict]:
        """
        Check which tracks are in which restricted zones.
        zones: [{"id": str, "zone_type": str, "polygon": [[x,y],...], "alert_on_entry": bool}]
        """
        intrusions = []

        for track in tracks:
            cx, cy = track.bbox.center
            for zone in zones:
                if not zone.get("is_active", True):
                    continue
                if zone.get("zone_type") != "restricted":
                    continue
                if not zone.get("alert_on_entry", True):
                    continue

                polygon = [(p[0], p[1]) for p in zone["polygon"]]
                if len(polygon) < 3:
                    continue

                if self.point_in_polygon((cx, cy), polygon):
                    intrusions.append({
                        "track_id": track.track_id,
                        "zone_id": zone["id"],
                        "zone_name": zone.get("name", "Unknown"),
                        "position": (cx, cy),
                        "confidence": 0.95,
                    })

        return intrusions


# ─── Main Anomaly Service ─────────────────────────────────────────────────────

class AnomalyDetectionService:
    """
    Orchestrates all anomaly detection modules.
    """

    def __init__(self):
        self._stat_detector = StatisticalAnomalyDetector()
        self._abandoned_detector = AbandonedObjectDetector(
            time_threshold=settings.alerts.abandoned_time_threshold
        )
        self._zone_detector = ZoneIntrusionDetector()
        self._threshold = settings.ai.anomaly_threshold

    def analyze(
        self,
        camera_id: str,
        tracks: List[TrackState],
        zones: List[Dict],
        frame_timestamp: float,
    ) -> List[AnomalyResult]:
        """Run all anomaly detectors and return results."""
        results = []
        persons = [t for t in tracks if t.class_name == "person"]
        objects = [t for t in tracks if t.class_name != "person"]

        # Update baseline
        self._stat_detector.update_baseline(camera_id, persons)

        # Statistical anomalies per track
        for track in persons:
            score = self._stat_detector.score_track(camera_id, track)
            if score > self._threshold:
                results.append(AnomalyResult(
                    camera_id=camera_id,
                    track_id=track.track_id,
                    anomaly_score=score,
                    is_anomaly=True,
                    anomaly_type="statistical_motion",
                    details={"score": score},
                    timestamp=frame_timestamp,
                ))

        # Abandoned objects
        abandoned = self._abandoned_detector.update(
            camera_id, objects, persons, frame_timestamp
        )
        for ab in abandoned:
            results.append(AnomalyResult(
                camera_id=camera_id,
                track_id=ab["track_id"],
                anomaly_score=ab["confidence"],
                is_anomaly=True,
                anomaly_type="abandoned_object",
                details=ab,
                timestamp=frame_timestamp,
            ))

        # Zone intrusions
        if zones:
            intrusions = self._zone_detector.check_intrusion(persons, zones)
            for intr in intrusions:
                results.append(AnomalyResult(
                    camera_id=camera_id,
                    track_id=intr["track_id"],
                    anomaly_score=intr["confidence"],
                    is_anomaly=True,
                    anomaly_type="zone_intrusion",
                    details=intr,
                    timestamp=frame_timestamp,
                ))

        return results
