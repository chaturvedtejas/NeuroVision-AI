"""
NeuroVision AI - Pose Estimation
Human skeleton detection using YOLO-Pose with keypoint extraction
and joint angle computation for action analysis
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from config.settings import settings


# COCO 17 keypoints
KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# Skeleton connections for drawing
SKELETON_CONNECTIONS = [
    (0, 1), (0, 2), (1, 3), (2, 4),            # Face
    (5, 6),                                       # Shoulders
    (5, 7), (7, 9),                               # Left arm
    (6, 8), (8, 10),                              # Right arm
    (5, 11), (6, 12),                             # Torso
    (11, 12),                                     # Hips
    (11, 13), (13, 15),                           # Left leg
    (12, 14), (14, 16),                           # Right leg
]

# Color per connection (gradient from head to feet)
SKELETON_COLORS = [
    (255, 200, 0),   # Face - yellow
    (255, 200, 0),
    (255, 200, 0),
    (255, 200, 0),
    (0, 255, 200),   # Shoulders - cyan
    (0, 200, 255),   # Arms
    (0, 200, 255),
    (0, 200, 255),
    (0, 200, 255),
    (100, 255, 100), # Torso - green
    (100, 255, 100),
    (100, 255, 100),
    (255, 100, 200), # Legs - pink
    (255, 100, 200),
    (255, 100, 200),
    (255, 100, 200),
]


@dataclass
class Keypoint:
    x: float  # normalized 0-1
    y: float  # normalized 0-1
    confidence: float
    name: str

    @property
    def is_valid(self) -> bool:
        return self.confidence > 0.35

    @property
    def pixel_coords(self) -> Optional[Tuple[int, int]]:
        return None  # Set when frame dimensions are known


@dataclass
class Pose:
    track_id: Optional[int]
    keypoints: List[Keypoint]  # 17 keypoints in COCO order
    bbox: Optional[Tuple[float, float, float, float]] = None  # x1,y1,x2,y2

    def get_keypoint(self, name: str) -> Optional[Keypoint]:
        idx = KEYPOINT_NAMES.index(name) if name in KEYPOINT_NAMES else -1
        if idx < 0 or idx >= len(self.keypoints):
            return None
        kp = self.keypoints[idx]
        return kp if kp.is_valid else None

    def get_angle(self, p1_name: str, vertex_name: str, p2_name: str) -> Optional[float]:
        """Compute joint angle in degrees."""
        p1 = self.get_keypoint(p1_name)
        vertex = self.get_keypoint(vertex_name)
        p2 = self.get_keypoint(p2_name)

        if not all([p1, vertex, p2]):
            return None

        v1 = np.array([p1.x - vertex.x, p1.y - vertex.y])
        v2 = np.array([p2.x - vertex.x, p2.y - vertex.y])

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return None

        cos_angle = np.dot(v1, v2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        return float(np.degrees(np.arccos(cos_angle)))

    @property
    def body_aspect_ratio(self) -> Optional[float]:
        """Height/width ratio of body bounding box."""
        if self.bbox is None:
            return None
        x1, y1, x2, y2 = self.bbox
        w = x2 - x1
        h = y2 - y1
        return h / w if w > 0 else None

    @property
    def is_upright(self) -> bool:
        """Heuristic: person is standing/upright."""
        ratio = self.body_aspect_ratio
        return ratio is not None and ratio > 1.5

    @property
    def is_fallen(self) -> bool:
        """Heuristic: person appears horizontal (fallen)."""
        ratio = self.body_aspect_ratio
        return ratio is not None and ratio < 0.6

    @property
    def torso_inclination(self) -> Optional[float]:
        """Angle of spine (shoulder-midpoint to hip-midpoint) from vertical."""
        ls = self.get_keypoint("left_shoulder")
        rs = self.get_keypoint("right_shoulder")
        lh = self.get_keypoint("left_hip")
        rh = self.get_keypoint("right_hip")

        if not all([ls, rs, lh, rh]):
            return None

        sx = (ls.x + rs.x) / 2
        sy = (ls.y + rs.y) / 2
        hx = (lh.x + rh.x) / 2
        hy = (lh.y + rh.y) / 2

        dx = sx - hx
        dy = sy - hy
        # Angle from vertical (downward = 0)
        angle = math.degrees(math.atan2(abs(dx), abs(dy)))
        return angle

    def to_dict(self) -> Dict:
        return {
            "track_id": self.track_id,
            "keypoints": [
                {"name": kp.name, "x": kp.x, "y": kp.y, "confidence": kp.confidence}
                for kp in self.keypoints
            ],
            "bbox": list(self.bbox) if self.bbox else None,
            "is_upright": self.is_upright,
            "is_fallen": self.is_fallen,
            "torso_inclination": self.torso_inclination,
        }


class PoseEstimator:
    """
    Pose estimation using YOLO-Pose model.
    Extracts 17 COCO keypoints per person with confidence scores.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None,
        confidence: float = 0.35,
    ):
        self.device = device or settings.ai.device
        self.confidence = confidence
        self._model = None
        self._model_path = model_path or str(settings.ai.models_dir / settings.ai.pose_model)

    def load(self) -> None:
        """Load pose estimation model."""
        try:
            from ultralytics import YOLO
            logger.info(f"Loading pose model from {self._model_path}")
            self._model = YOLO(self._model_path)
            logger.info("✅ Pose model loaded")
        except Exception as e:
            logger.error(f"Failed to load pose model: {e}")
            raise

    def estimate(
        self,
        frame: np.ndarray,
        tracked_bboxes: Optional[List] = None,
    ) -> List[Pose]:
        """
        Estimate poses in frame.
        If tracked_bboxes provided, associates poses with track IDs.
        """
        if self._model is None:
            return []

        h, w = frame.shape[:2]
        results = self._model(
            frame,
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )

        poses = []
        for result in results:
            if result.keypoints is None:
                continue

            kps_data = result.keypoints.data.cpu().numpy()  # [N, 17, 3]
            boxes = result.boxes.xyxy.cpu().numpy() if result.boxes else None

            for pi in range(len(kps_data)):
                kp_array = kps_data[pi]  # [17, 3] = (x, y, conf)
                bbox = None

                if boxes is not None and pi < len(boxes):
                    x1, y1, x2, y2 = boxes[pi]
                    bbox = (float(x1)/w, float(y1)/h, float(x2)/w, float(y2)/h)

                keypoints = []
                for ki, name in enumerate(KEYPOINT_NAMES):
                    kx, ky, kconf = kp_array[ki]
                    keypoints.append(Keypoint(
                        x=float(kx) / w,
                        y=float(ky) / h,
                        confidence=float(kconf),
                        name=name,
                    ))

                # Match with tracked bbox if available
                track_id = None
                if tracked_bboxes and bbox:
                    track_id = self._match_to_track(bbox, tracked_bboxes)

                poses.append(Pose(
                    track_id=track_id,
                    keypoints=keypoints,
                    bbox=bbox,
                ))

        return poses

    def _match_to_track(
        self,
        pose_bbox: Tuple,
        tracked_bboxes: List,
    ) -> Optional[int]:
        """Match pose to nearest tracked bbox by IoU."""
        best_iou = 0.3  # Minimum threshold
        best_id = None

        px1, py1, px2, py2 = pose_bbox
        for tbox in tracked_bboxes:
            if tbox.track_id is None:
                continue
            ix1 = max(px1, tbox.x1)
            iy1 = max(py1, tbox.y1)
            ix2 = min(px2, tbox.x2)
            iy2 = min(py2, tbox.y2)

            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2 - ix1) * (iy2 - iy1)
                area1 = (px2 - px1) * (py2 - py1)
                area2 = (tbox.x2 - tbox.x1) * (tbox.y2 - tbox.y1)
                iou = inter / (area1 + area2 - inter + 1e-6)
                if iou > best_iou:
                    best_iou = iou
                    best_id = tbox.track_id

        return best_id

    def draw_poses(self, frame: np.ndarray, poses: List[Pose]) -> np.ndarray:
        """Draw skeleton overlays on frame."""
        out = frame.copy()
        h, w = frame.shape[:2]

        for pose in poses:
            kps = pose.keypoints

            # Draw connections
            for ci, (ki, kj) in enumerate(SKELETON_CONNECTIONS):
                if ki >= len(kps) or kj >= len(kps):
                    continue
                kp1 = kps[ki]
                kp2 = kps[kj]

                if not kp1.is_valid or not kp2.is_valid:
                    continue

                p1 = (int(kp1.x * w), int(kp1.y * h))
                p2 = (int(kp2.x * w), int(kp2.y * h))
                color = SKELETON_COLORS[ci % len(SKELETON_COLORS)]

                cv2.line(out, p1, p2, color, 2, cv2.LINE_AA)

            # Draw keypoints
            for kp in kps:
                if not kp.is_valid:
                    continue
                px, py = int(kp.x * w), int(kp.y * h)
                cv2.circle(out, (px, py), 4, (255, 255, 255), -1)
                cv2.circle(out, (px, py), 4, (0, 150, 255), 1)

            # Indicate fallen state
            if pose.is_fallen and pose.bbox:
                x1 = int(pose.bbox[0] * w)
                y1 = int(pose.bbox[1] * h)
                cv2.putText(out, "FALLEN!", (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return out
