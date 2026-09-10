"""
NeuroVision AI - Multi-Object Tracking
ByteTrack-inspired tracker with Kalman filter + Hungarian algorithm
Supports persistent track IDs and cross-frame re-identification
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger
from scipy.optimize import linear_sum_assignment

from app.detection.detector import BoundingBox, DetectionFrame
from config.settings import settings


# ─── Kalman Filter ────────────────────────────────────────────────────────────

class KalmanBoxTracker:
    """
    Kalman filter for bounding box state estimation.
    State: [x, y, s, r, dx, dy, ds] where x,y=center, s=scale, r=aspect ratio
    """

    count = 0

    def __init__(self, bbox: BoundingBox):
        from filterpy.kalman import KalmanFilter

        self.kf = KalmanFilter(dim_x=7, dim_z=4)

        # State transition matrix
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1],
        ], dtype=np.float32)

        # Measurement matrix
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0],
        ], dtype=np.float32)

        # Covariances
        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01

        # Initialize state from bbox
        cx, cy, w, h = bbox.xywh
        s = w * h
        r = w / float(h) if h > 0 else 1.0
        self.kf.x[:4] = np.array([[cx], [cy], [s], [r]], dtype=np.float32)

        KalmanBoxTracker.count += 1
        self.id = KalmanBoxTracker.count
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
        self.time_since_update = 0
        self.history: List[np.ndarray] = []
        self.class_name = bbox.class_name
        self.class_id = bbox.class_id
        self.confidence = bbox.confidence
        self.trajectory: List[Tuple[float, float]] = [(cx, cy)]

    def update(self, bbox: BoundingBox) -> None:
        """Update with new detection."""
        cx, cy, w, h = bbox.xywh
        s = w * h
        r = w / float(h) if h > 0 else 1.0
        self.kf.update(np.array([[cx], [cy], [s], [r]], dtype=np.float32))
        self.confidence = bbox.confidence
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.trajectory.append((cx, cy))
        if len(self.trajectory) > 100:
            self.trajectory.pop(0)

    def predict(self) -> np.ndarray:
        """Predict next state."""
        if self.kf.x[6] + self.kf.x[2] <= 0:
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        self.history.append(self._get_state())
        return self.history[-1]

    def _get_state(self) -> np.ndarray:
        """Convert internal state to [x1, y1, x2, y2]."""
        cx, cy, s, r = float(self.kf.x[0]), float(self.kf.x[1]), float(self.kf.x[2]), float(self.kf.x[3])
        if s < 0:
            s = 0
        w = np.sqrt(max(s * abs(r), 0))
        h = s / w if w > 0 else 0
        return np.array([cx - w/2, cy - h/2, cx + w/2, cy + h/2])

    def get_bbox(self) -> Optional[BoundingBox]:
        """Get current state as BoundingBox."""
        state = self._get_state()
        if state is None:
            return None
        return BoundingBox(
            x1=float(np.clip(state[0], 0, 1)),
            y1=float(np.clip(state[1], 0, 1)),
            x2=float(np.clip(state[2], 0, 1)),
            y2=float(np.clip(state[3], 0, 1)),
            confidence=self.confidence,
            class_id=self.class_id,
            class_name=self.class_name,
            track_id=self.id,
        )


# ─── IOU Utilities ────────────────────────────────────────────────────────────

def iou_batch(bb_test: np.ndarray, bb_gt: np.ndarray) -> np.ndarray:
    """Compute IoU matrix between two sets of boxes [N,4] and [M,4]."""
    bb_gt = np.expand_dims(bb_gt, 0)
    bb_test = np.expand_dims(bb_test, 1)

    xx1 = np.maximum(bb_test[..., 0], bb_gt[..., 0])
    yy1 = np.maximum(bb_test[..., 1], bb_gt[..., 1])
    xx2 = np.minimum(bb_test[..., 2], bb_gt[..., 2])
    yy2 = np.minimum(bb_test[..., 3], bb_gt[..., 3])

    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    inter = w * h

    area_test = (bb_test[..., 2] - bb_test[..., 0]) * (bb_test[..., 3] - bb_test[..., 1])
    area_gt = (bb_gt[..., 2] - bb_gt[..., 0]) * (bb_gt[..., 3] - bb_gt[..., 1])
    union = area_test + area_gt - inter

    return inter / np.maximum(union, 1e-6)


def associate_detections(
    detections: np.ndarray,
    trackers: np.ndarray,
    iou_threshold: float = 0.3,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hungarian algorithm-based detection-tracker association."""
    if trackers.shape[0] == 0:
        return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty(0, dtype=int)

    iou_matrix = iou_batch(detections, trackers)

    if min(iou_matrix.shape) > 0:
        matched_indices = linear_sum_assignment(-iou_matrix)
        matched_indices = np.stack(matched_indices, axis=1)
    else:
        matched_indices = np.empty((0, 2), dtype=int)

    unmatched_dets = []
    for d in range(len(detections)):
        if d not in matched_indices[:, 0]:
            unmatched_dets.append(d)

    unmatched_trks = []
    for t in range(len(trackers)):
        if t not in matched_indices[:, 1]:
            unmatched_trks.append(t)

    matches = []
    for m in matched_indices:
        if iou_matrix[m[0], m[1]] < iou_threshold:
            unmatched_dets.append(m[0])
            unmatched_trks.append(m[1])
        else:
            matches.append(m.reshape(1, 2))

    if len(matches) == 0:
        matches = np.empty((0, 2), dtype=int)
    else:
        matches = np.concatenate(matches, axis=0)

    return matches, np.array(unmatched_dets), np.array(unmatched_trks)


# ─── SORT Tracker ─────────────────────────────────────────────────────────────

class SORTTracker:
    """
    Simple Online and Realtime Tracking (SORT) with Kalman filter.
    Extended for multi-class tracking.
    """

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3,
    ):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers: List[KalmanBoxTracker] = []
        self.frame_count = 0
        KalmanBoxTracker.count = 0  # Reset global counter

    def update(self, detections: List[BoundingBox]) -> List[BoundingBox]:
        """
        Update tracker with new detections.
        Returns tracked boxes with persistent IDs.
        """
        self.frame_count += 1

        # Get predicted positions from existing trackers
        trks = np.zeros((len(self.trackers), 4))
        to_del = []
        for t, trk in enumerate(self.trackers):
            pos = trk.predict()
            trks[t] = pos
            if np.any(np.isnan(pos)):
                to_del.append(t)

        for t in reversed(to_del):
            self.trackers.pop(t)
        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))

        if len(detections) > 0:
            dets_arr = np.array([[d.x1, d.y1, d.x2, d.y2] for d in detections])
        else:
            dets_arr = np.empty((0, 4))

        matched, unmatched_dets, unmatched_trks = associate_detections(
            dets_arr, trks, self.iou_threshold
        )

        # Update matched trackers
        for m in matched:
            self.trackers[m[1]].update(detections[m[0]])

        # Create new trackers for unmatched detections
        for i in unmatched_dets:
            self.trackers.append(KalmanBoxTracker(detections[i]))

        # Return active tracks
        results = []
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            i -= 1
            bbox = trk.get_bbox()
            if bbox is None:
                continue

            if (trk.time_since_update < 1) and (
                trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits
            ):
                results.append(bbox)

            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)

        return results

    def get_trajectories(self) -> Dict[int, List[Tuple[float, float]]]:
        """Get current trajectories for all active tracks."""
        return {
            trk.id: trk.trajectory
            for trk in self.trackers
            if trk.time_since_update < 1
        }

    def reset(self) -> None:
        self.trackers = []
        self.frame_count = 0
        KalmanBoxTracker.count = 0


# ─── Multi-Camera Tracking Manager ────────────────────────────────────────────

@dataclass
class TrackState:
    track_id: int
    camera_id: str
    class_name: str
    bbox: BoundingBox
    trajectory: List[Tuple[float, float]]
    age: int
    hits: int
    last_seen: float
    reid_features: Optional[np.ndarray] = None
    zones: List[str] = field(default_factory=list)


class MultiCameraTracker:
    """
    Manages trackers for multiple camera streams simultaneously.
    Supports cross-camera re-identification.
    """

    def __init__(self):
        self._trackers: Dict[str, SORTTracker] = {}
        self._track_states: Dict[str, Dict[int, TrackState]] = defaultdict(dict)
        self._global_track_map: Dict[Tuple[str, int], int] = {}  # (camera, local_id) -> global_id
        self._global_counter = 0

    def get_tracker(self, camera_id: str) -> SORTTracker:
        """Get or create tracker for a camera."""
        if camera_id not in self._trackers:
            self._trackers[camera_id] = SORTTracker(
                max_age=settings.ai.track_max_age,
                min_hits=settings.ai.track_min_hits,
                iou_threshold=settings.ai.track_iou_threshold,
            )
            logger.info(f"Created tracker for camera {camera_id}")
        return self._trackers[camera_id]

    def update(
        self,
        camera_id: str,
        detection_frame: DetectionFrame,
    ) -> List[BoundingBox]:
        """Update tracking for a camera frame."""
        tracker = self.get_tracker(camera_id)
        persons = [d for d in detection_frame.detections if d.class_name == "person"]
        all_objects = detection_frame.detections

        tracked = tracker.update(persons)
        trajectories = tracker.get_trajectories()

        # Update track states
        for bbox in tracked:
            if bbox.track_id is None:
                continue
            key = (camera_id, bbox.track_id)
            traj = trajectories.get(bbox.track_id, [bbox.center])

            self._track_states[camera_id][bbox.track_id] = TrackState(
                track_id=bbox.track_id,
                camera_id=camera_id,
                class_name=bbox.class_name,
                bbox=bbox,
                trajectory=traj,
                age=next(
                    (t.age for t in tracker.trackers if t.id == bbox.track_id), 0
                ),
                hits=next(
                    (t.hits for t in tracker.trackers if t.id == bbox.track_id), 1
                ),
                last_seen=time.time(),
            )

        # Add non-person detections back (untracked)
        non_persons = [d for d in all_objects if d.class_name != "person"]
        return tracked + non_persons

    def get_active_tracks(self, camera_id: str) -> List[TrackState]:
        """Get currently active tracks for a camera."""
        now = time.time()
        cutoff = now - 2.0  # 2 second cutoff
        states = self._track_states.get(camera_id, {})
        return [
            state for state in states.values()
            if state.last_seen > cutoff
        ]

    def get_all_active_tracks(self) -> Dict[str, List[TrackState]]:
        """Get active tracks across all cameras."""
        return {
            cam_id: self.get_active_tracks(cam_id)
            for cam_id in self._trackers
        }

    def remove_camera(self, camera_id: str) -> None:
        """Clean up tracker for a removed camera."""
        self._trackers.pop(camera_id, None)
        self._track_states.pop(camera_id, None)

    def get_stats(self) -> Dict:
        return {
            "active_cameras": len(self._trackers),
            "total_active_tracks": sum(
                len(self.get_active_tracks(cam)) for cam in self._trackers
            ),
            "tracks_per_camera": {
                cam: len(self.get_active_tracks(cam)) for cam in self._trackers
            },
        }
