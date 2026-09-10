"""
NeuroVision AI - Action Recognition
Rule-based + ML action classification using pose, trajectory,
and motion features for surveillance-critical behaviors
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from app.pose.estimator import Pose
from app.tracking.tracker import TrackState
from config.settings import settings


class ActionType(str, Enum):
    WALKING = "walking"
    RUNNING = "running"
    STANDING = "standing"
    SITTING = "sitting"
    FALLING = "falling"
    FALLEN = "fallen"
    FIGHTING = "fighting"
    LOITERING = "loitering"
    SUSPICIOUS = "suspicious_movement"
    CROUCHING = "crouching"
    JUMPING = "jumping"
    WAVING = "waving"
    UNKNOWN = "unknown"


@dataclass
class ActionPrediction:
    track_id: int
    action: ActionType
    confidence: float
    timestamp: float = field(default_factory=time.time)
    supporting_evidence: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "track_id": self.track_id,
            "action": self.action.value,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "evidence": self.supporting_evidence,
        }


class TrackFeatureBuffer:
    """Rolling feature buffer per track for temporal action analysis."""

    def __init__(self, window: int = 30):
        self.window = window
        self.velocities: deque = deque(maxlen=window)
        self.positions: deque = deque(maxlen=window)
        self.poses: deque = deque(maxlen=window)
        self.bbox_sizes: deque = deque(maxlen=window)
        self.timestamps: deque = deque(maxlen=window)
        self.first_seen: float = time.time()
        self.last_position: Optional[Tuple[float, float]] = None
        self.total_distance: float = 0.0

    def update(self, track: TrackState, pose: Optional[Pose] = None) -> None:
        pos = track.bbox.center
        now = time.time()
        self.timestamps.append(now)
        self.positions.append(pos)

        # Velocity
        if self.last_position is not None and len(self.timestamps) > 1:
            dt = now - (self.timestamps[-2] if len(self.timestamps) > 1 else now)
            if dt > 0:
                dx = pos[0] - self.last_position[0]
                dy = pos[1] - self.last_position[1]
                vx, vy = dx / dt, dy / dt
                speed = np.sqrt(vx**2 + vy**2)
                self.velocities.append(speed)
                self.total_distance += np.sqrt(dx**2 + dy**2)
        else:
            self.velocities.append(0.0)

        self.last_position = pos
        self.poses.append(pose)
        w = track.bbox.x2 - track.bbox.x1
        h = track.bbox.y2 - track.bbox.y1
        self.bbox_sizes.append((w, h))

    @property
    def avg_speed(self) -> float:
        return float(np.mean(self.velocities)) if self.velocities else 0.0

    @property
    def max_speed(self) -> float:
        return float(np.max(self.velocities)) if self.velocities else 0.0

    @property
    def time_in_scene(self) -> float:
        return time.time() - self.first_seen

    @property
    def displacement(self) -> float:
        """Net displacement from first to last position."""
        if len(self.positions) < 2:
            return 0.0
        p0 = self.positions[0]
        p1 = self.positions[-1]
        return float(np.sqrt((p1[0]-p0[0])**2 + (p1[1]-p0[1])**2))

    @property
    def is_stationary(self) -> bool:
        return self.avg_speed < 0.005 and self.displacement < 0.05

    @property
    def speed_variance(self) -> float:
        return float(np.var(self.velocities)) if len(self.velocities) > 3 else 0.0

    @property
    def recent_pose(self) -> Optional[Pose]:
        for p in reversed(self.poses):
            if p is not None:
                return p
        return None


class RuleBasedActionClassifier:
    """
    Multi-cue action classification using:
    - Velocity profiles
    - Pose geometry
    - Temporal patterns
    - Bounding box changes
    """

    # Speed thresholds (normalized coords per second)
    SPEED_WALKING_MIN = 0.01
    SPEED_WALKING_MAX = 0.06
    SPEED_RUNNING_MIN = 0.06

    # Loitering
    LOITER_TIME_SEC = 60
    LOITER_MAX_DISPLACEMENT = 0.15

    # Fight detection: rapid velocity changes between two nearby persons
    FIGHT_PROXIMITY_THRESHOLD = 0.15
    FIGHT_SPEED_THRESHOLD = 0.08
    FIGHT_SPEED_VARIANCE_THRESHOLD = 0.003

    def classify(
        self,
        track: TrackState,
        buffer: TrackFeatureBuffer,
        nearby_tracks: List[TrackState],
        nearby_buffers: Dict[int, TrackFeatureBuffer],
    ) -> ActionPrediction:
        """Classify action for a single track."""

        pose = buffer.recent_pose
        speed = buffer.avg_speed
        max_spd = buffer.max_speed

        # ── Fall detection (highest priority) ──────────────────────────────
        if pose and pose.is_fallen:
            return ActionPrediction(
                track_id=track.track_id,
                action=ActionType.FALLEN,
                confidence=0.92,
                supporting_evidence={"bbox_ratio": pose.body_aspect_ratio, "pose_based": True},
            )

        # Check for falling (transition to fallen)
        if len(buffer.bbox_sizes) >= 3:
            recent_ratios = [h / max(w, 0.001) for w, h in list(buffer.bbox_sizes)[-5:]]
            if len(recent_ratios) >= 2:
                ratio_delta = recent_ratios[-1] - recent_ratios[0]
                if ratio_delta < -0.5 and max_spd > 0.03:  # Rapid height reduction
                    return ActionPrediction(
                        track_id=track.track_id,
                        action=ActionType.FALLING,
                        confidence=0.78,
                        supporting_evidence={"ratio_delta": ratio_delta},
                    )

        # ── Fighting detection ──────────────────────────────────────────────
        fight_evidence = self._check_fighting(
            track, buffer, nearby_tracks, nearby_buffers
        )
        if fight_evidence is not None:
            return fight_evidence

        # ── Speed-based classification ─────────────────────────────────────
        if max_spd > self.SPEED_RUNNING_MIN:
            confidence = min(0.95, 0.6 + (max_spd - self.SPEED_RUNNING_MIN) * 5)
            return ActionPrediction(
                track_id=track.track_id,
                action=ActionType.RUNNING,
                confidence=confidence,
                supporting_evidence={"max_speed": max_spd, "avg_speed": speed},
            )

        # ── Loitering detection ─────────────────────────────────────────────
        if (
            buffer.time_in_scene > self.LOITER_TIME_SEC
            and buffer.displacement < self.LOITER_MAX_DISPLACEMENT
        ):
            confidence = min(0.9, 0.5 + (buffer.time_in_scene - self.LOITER_TIME_SEC) / 300)
            return ActionPrediction(
                track_id=track.track_id,
                action=ActionType.LOITERING,
                confidence=confidence,
                supporting_evidence={
                    "time_in_scene_sec": round(buffer.time_in_scene),
                    "displacement": round(buffer.displacement, 3),
                },
            )

        # ── Stationary ──────────────────────────────────────────────────────
        if buffer.is_stationary:
            # Check pose for sitting vs standing
            action = ActionType.STANDING
            conf = 0.7

            if pose:
                if not pose.is_upright:
                    action = ActionType.SITTING
                    conf = 0.65
                else:
                    action = ActionType.STANDING
                    conf = 0.8

            return ActionPrediction(
                track_id=track.track_id,
                action=action,
                confidence=conf,
            )

        # ── Walking ─────────────────────────────────────────────────────────
        if self.SPEED_WALKING_MIN <= speed <= self.SPEED_WALKING_MAX:
            return ActionPrediction(
                track_id=track.track_id,
                action=ActionType.WALKING,
                confidence=0.75,
                supporting_evidence={"avg_speed": speed},
            )

        # ── Suspicious movement (erratic) ──────────────────────────────────
        if buffer.speed_variance > self.FIGHT_SPEED_VARIANCE_THRESHOLD and speed > 0.02:
            return ActionPrediction(
                track_id=track.track_id,
                action=ActionType.SUSPICIOUS,
                confidence=0.6,
                supporting_evidence={"speed_variance": buffer.speed_variance},
            )

        return ActionPrediction(
            track_id=track.track_id,
            action=ActionType.UNKNOWN,
            confidence=0.3,
        )

    def _check_fighting(
        self,
        track: TrackState,
        buffer: TrackFeatureBuffer,
        nearby_tracks: List[TrackState],
        nearby_buffers: Dict[int, TrackFeatureBuffer],
    ) -> Optional[ActionPrediction]:
        """Detect fighting based on proximity and erratic high-speed movement."""
        cx, cy = track.bbox.center

        for other in nearby_tracks:
            if other.track_id == track.track_id:
                continue
            ocx, ocy = other.bbox.center
            dist = np.sqrt((cx - ocx)**2 + (cy - ocy)**2)

            if dist > self.FIGHT_PROXIMITY_THRESHOLD:
                continue

            other_buf = nearby_buffers.get(other.track_id)
            if other_buf is None:
                continue

            # Both persons have high speed variance + high speed
            if (
                buffer.speed_variance > self.FIGHT_SPEED_VARIANCE_THRESHOLD
                and other_buf.speed_variance > self.FIGHT_SPEED_VARIANCE_THRESHOLD
                and buffer.max_speed > self.FIGHT_SPEED_THRESHOLD
                and other_buf.max_speed > self.FIGHT_SPEED_THRESHOLD
            ):
                confidence = min(0.88, 0.6 + (buffer.speed_variance + other_buf.speed_variance) * 30)
                return ActionPrediction(
                    track_id=track.track_id,
                    action=ActionType.FIGHTING,
                    confidence=confidence,
                    supporting_evidence={
                        "proximity": round(dist, 3),
                        "speed_variance": round(buffer.speed_variance, 4),
                        "other_track": other.track_id,
                    },
                )
        return None


class ActionRecognitionService:
    """
    Service managing action recognition for all active tracks.
    Maintains temporal buffers and aggregates predictions.
    """

    def __init__(self):
        self._buffers: Dict[str, Dict[int, TrackFeatureBuffer]] = defaultdict(dict)
        self._classifier = RuleBasedActionClassifier()
        self._action_history: Dict[str, Dict[int, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=10)))

    def update(
        self,
        camera_id: str,
        tracks: List[TrackState],
        poses: List[Pose],
    ) -> List[ActionPrediction]:
        """Process current tracks and return action predictions."""
        # Build pose lookup by track_id
        pose_map = {p.track_id: p for p in poses if p.track_id is not None}
        cam_buffers = self._buffers[camera_id]

        # Update feature buffers
        for track in tracks:
            if track.track_id not in cam_buffers:
                cam_buffers[track.track_id] = TrackFeatureBuffer()
            cam_buffers[track.track_id].update(track, pose_map.get(track.track_id))

        # Classify actions
        predictions = []
        for track in tracks:
            buf = cam_buffers.get(track.track_id)
            if buf is None or len(buf.positions) < 2:
                continue

            pred = self._classifier.classify(
                track=track,
                buffer=buf,
                nearby_tracks=tracks,
                nearby_buffers={t.track_id: cam_buffers.get(t.track_id) for t in tracks},
            )

            # Temporal smoothing via voting
            self._action_history[camera_id][track.track_id].append(pred.action)
            smoothed = self._smooth_action(self._action_history[camera_id][track.track_id])
            pred.action = smoothed

            predictions.append(pred)

        # Clean up stale buffers
        active_ids = {t.track_id for t in tracks}
        stale = [tid for tid in cam_buffers if tid not in active_ids]
        for tid in stale:
            cam_buffers.pop(tid, None)

        return predictions

    def _smooth_action(self, history: deque) -> ActionType:
        """Majority vote over recent action history."""
        if not history:
            return ActionType.UNKNOWN
        counts: Dict[ActionType, int] = {}
        for a in history:
            counts[a] = counts.get(a, 0) + 1
        return max(counts, key=counts.get)

    def get_loiterers(self, camera_id: str) -> List[int]:
        """Get track IDs currently loitering."""
        return [
            tid for tid, buf in self._buffers[camera_id].items()
            if buf.time_in_scene > settings.alerts.loiter_time_threshold
            and buf.displacement < 0.15
        ]

    def cleanup_camera(self, camera_id: str) -> None:
        self._buffers.pop(camera_id, None)
        self._action_history.pop(camera_id, None)
