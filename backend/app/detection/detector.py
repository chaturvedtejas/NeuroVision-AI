"""
NeuroVision AI - Detection Pipeline
High-performance real-time object detection using YOLO models
with GPU acceleration and batch processing
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from loguru import logger

from config.settings import settings


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str
    track_id: Optional[int] = None

    @property
    def xyxy(self) -> Tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2, self.y2

    @property
    def xywh(self) -> Tuple[float, float, float, float]:
        cx = (self.x1 + self.x2) / 2
        cy = (self.y1 + self.y2) / 2
        w = self.x2 - self.x1
        h = self.y2 - self.y1
        return cx, cy, w, h

    @property
    def tlwh(self) -> Tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2 - self.x1, self.y2 - self.y1

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2

    @property
    def area(self) -> float:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)

    def to_dict(self) -> Dict:
        return {
            "x1": round(self.x1, 4),
            "y1": round(self.y1, 4),
            "x2": round(self.x2, 4),
            "y2": round(self.y2, 4),
            "confidence": round(self.confidence, 4),
            "class_id": self.class_id,
            "class_name": self.class_name,
            "track_id": self.track_id,
            "center": [round(c, 4) for c in self.center],
        }


@dataclass
class DetectionFrame:
    camera_id: str
    frame_number: int
    timestamp: float
    frame: np.ndarray
    detections: List[BoundingBox] = field(default_factory=list)
    inference_time_ms: float = 0.0
    fps: float = 0.0

    @property
    def person_count(self) -> int:
        return sum(1 for d in self.detections if d.class_name == "person")

    @property
    def has_detections(self) -> bool:
        return len(self.detections) > 0


# COCO class names (subset we care about)
COCO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
    39: "bottle",
    41: "cup",
    67: "cell phone",
    73: "laptop",
}

# Priority classes for surveillance
SURVEILLANCE_CLASSES = {0, 24, 26, 28, 2, 3, 5, 7}  # persons, bags, vehicles


class YOLODetector:
    """
    High-performance YOLO detector with:
    - GPU acceleration
    - Half precision inference
    - Configurable confidence/IOU thresholds
    - Multi-class filtering
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None,
        confidence: Optional[float] = None,
        iou: Optional[float] = None,
        classes: Optional[List[int]] = None,
        half: Optional[bool] = None,
    ):
        self.device = device or settings.ai.device
        self.confidence = confidence or settings.ai.confidence_threshold
        self.iou = iou or settings.ai.iou_threshold
        self.classes = classes or list(SURVEILLANCE_CLASSES)
        self.half = half if half is not None else settings.ai.half_precision
        self._model = None
        self._model_path = model_path or str(settings.ai.models_dir / settings.ai.yolo_model)
        self._frame_count = 0
        self._total_inference_time = 0.0

    def load(self) -> None:
        """Load the YOLO model."""
        try:
            from ultralytics import YOLO

            logger.info(f"Loading YOLO model from {self._model_path} on {self.device}")
            self._model = YOLO(self._model_path)

            # Warm up
            if self.device == "cuda" and torch.cuda.is_available():
                dummy = torch.zeros(1, 3, 640, 640).to(self.device)
                if self.half:
                    dummy = dummy.half()
                logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
                logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

            logger.info(f"✅ YOLO model loaded | device={self.device} | half={self.half}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise

    def detect(
        self,
        frame: np.ndarray,
        camera_id: str = "unknown",
        frame_number: int = 0,
    ) -> DetectionFrame:
        """
        Run inference on a single frame.
        Returns DetectionFrame with all detections.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        t0 = time.perf_counter()
        h, w = frame.shape[:2]

        results = self._model(
            frame,
            conf=self.confidence,
            iou=self.iou,
            classes=self.classes,
            device=self.device,
            half=self.half,
            verbose=False,
            stream=False,
        )

        inference_ms = (time.perf_counter() - t0) * 1000
        self._total_inference_time += inference_ms
        self._frame_count += 1

        detections: List[BoundingBox] = []

        for result in results:
            if result.boxes is None:
                continue

            boxes = result.boxes.xyxy.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()
            cls_ids = result.boxes.cls.cpu().numpy().astype(int)

            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes[i]
                conf = float(confs[i])
                cls_id = int(cls_ids[i])
                cls_name = COCO_CLASSES.get(cls_id, f"class_{cls_id}")

                detections.append(BoundingBox(
                    x1=float(x1) / w,
                    y1=float(y1) / h,
                    x2=float(x2) / w,
                    y2=float(y2) / h,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=cls_name,
                ))

        avg_fps = 1000.0 / (self._total_inference_time / self._frame_count) if self._frame_count > 0 else 0.0

        return DetectionFrame(
            camera_id=camera_id,
            frame_number=frame_number,
            timestamp=time.time(),
            frame=frame,
            detections=detections,
            inference_time_ms=inference_ms,
            fps=avg_fps,
        )

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[BoundingBox]]:
        """Batch inference for multiple frames."""
        if not frames:
            return []

        t0 = time.perf_counter()
        results = self._model(
            frames,
            conf=self.confidence,
            iou=self.iou,
            classes=self.classes,
            device=self.device,
            half=self.half,
            verbose=False,
            stream=False,
        )
        inference_ms = (time.perf_counter() - t0) * 1000
        logger.debug(f"Batch inference: {len(frames)} frames in {inference_ms:.1f}ms")

        all_detections = []
        for fi, result in enumerate(results):
            h, w = frames[fi].shape[:2]
            frame_dets = []

            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                cls_ids = result.boxes.cls.cpu().numpy().astype(int)

                for i in range(len(boxes)):
                    x1, y1, x2, y2 = boxes[i]
                    frame_dets.append(BoundingBox(
                        x1=float(x1) / w,
                        y1=float(y1) / h,
                        x2=float(x2) / w,
                        y2=float(y2) / h,
                        confidence=float(confs[i]),
                        class_id=int(cls_ids[i]),
                        class_name=COCO_CLASSES.get(int(cls_ids[i]), f"class_{int(cls_ids[i])}"),
                    ))
            all_detections.append(frame_dets)

        return all_detections

    @property
    def avg_inference_ms(self) -> float:
        if self._frame_count == 0:
            return 0.0
        return self._total_inference_time / self._frame_count

    def reset_stats(self) -> None:
        self._frame_count = 0
        self._total_inference_time = 0.0


class ObjectDetectionService:
    """
    High-level detection service managing detector lifecycle
    with multiple camera support.
    """

    def __init__(self):
        self._detector: Optional[YOLODetector] = None
        self._pose_detector: Optional["PoseDetector"] = None  # Lazy import
        self.is_ready = False

    async def initialize(self) -> None:
        """Initialize detection models."""
        logger.info("Initializing object detection service...")
        self._detector = YOLODetector()
        self._detector.load()
        self.is_ready = True
        logger.info("✅ Detection service ready")

    async def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_number: int = 0,
    ) -> DetectionFrame:
        """Process a single frame through detection pipeline."""
        if not self.is_ready:
            raise RuntimeError("Detection service not initialized")
        return self._detector.detect(frame, camera_id, frame_number)

    def draw_detections(
        self,
        frame: np.ndarray,
        detection_frame: DetectionFrame,
        draw_labels: bool = True,
        draw_conf: bool = True,
    ) -> np.ndarray:
        """Draw detection boxes on frame (BGR format)."""
        h, w = frame.shape[:2]
        out = frame.copy()

        CLASS_COLORS = {
            "person": (0, 255, 136),      # Neon green
            "car": (0, 200, 255),          # Cyan
            "truck": (0, 150, 255),
            "bus": (0, 100, 255),
            "backpack": (255, 200, 0),     # Yellow
            "handbag": (255, 150, 0),
            "suitcase": (255, 100, 0),
        }
        DEFAULT_COLOR = (0, 165, 255)  # Orange

        for det in detection_frame.detections:
            x1 = int(det.x1 * w)
            y1 = int(det.y1 * h)
            x2 = int(det.x2 * w)
            y2 = int(det.y2 * h)

            color = CLASS_COLORS.get(det.class_name, DEFAULT_COLOR)

            # Draw box with glow effect
            cv2.rectangle(out, (x1-1, y1-1), (x2+1, y2+1), (color[0]//3, color[1]//3, color[2]//3), 2)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

            if draw_labels:
                label = det.class_name
                if det.track_id is not None:
                    label = f"#{det.track_id} {label}"
                if draw_conf:
                    label += f" {det.confidence:.2f}"

                (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(out, (x1, y1 - th - baseline - 4), (x1 + tw + 2, y1), color, -1)
                cv2.putText(out, label, (x1 + 1, y1 - baseline - 2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        # Stats overlay
        fps_text = f"FPS: {detection_frame.fps:.1f} | Detections: {len(detection_frame.detections)}"
        cv2.putText(out, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                   (0, 255, 136), 2, cv2.LINE_AA)

        return out
