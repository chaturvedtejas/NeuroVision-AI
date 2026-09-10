"""
NeuroVision AI - Camera Stream Manager
Thread-safe multi-camera streaming with full AI pipeline integration
"""
from __future__ import annotations

import asyncio
import base64
import io
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger
from PIL import Image

from app.action.recognizer import ActionRecognitionService
from app.alerts.engine import SmartAlertEngine
from app.anomaly.detector import AnomalyDetectionService
from app.crowd.analytics import CrowdAnalyticsService
from app.detection.detector import DetectionFrame, ObjectDetectionService
from app.pose.estimator import PoseEstimator
from app.tracking.tracker import MultiCameraTracker
from app.trajectory.predictor import TrajectoryPredictor
from config.settings import settings


class StreamStatus(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class FrameResult:
    """Complete per-frame analysis result."""
    camera_id: str
    frame_number: int
    timestamp: float
    fps: float
    inference_ms: float
    person_count: int
    total_detections: int
    active_tracks: int
    detections: List[Dict] = field(default_factory=list)
    tracks: List[Dict] = field(default_factory=list)
    poses: List[Dict] = field(default_factory=list)
    actions: List[Dict] = field(default_factory=list)
    trajectories: List[Dict] = field(default_factory=list)
    anomalies: List[Dict] = field(default_factory=list)
    crowd_metrics: Optional[Dict] = None
    alerts: List[Dict] = field(default_factory=list)
    encoded_frame: Optional[str] = None  # Base64 JPEG


@dataclass
class CameraConfig:
    camera_id: str
    name: str
    stream_url: str
    is_rtsp: bool = False
    detection_enabled: bool = True
    tracking_enabled: bool = True
    pose_enabled: bool = True
    recording_enabled: bool = False
    zones: List[Dict] = field(default_factory=list)


class CameraStream:
    """
    Single camera stream with dedicated capture thread.
    Decouples capture from processing for maximum throughput.
    """

    def __init__(self, config: CameraConfig):
        self.config = config
        self.status = StreamStatus.IDLE
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=settings.streaming.buffer_size)
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._current_fps = 0.0
        self.error_message: Optional[str] = None
        self._reconnect_count = 0

    def start(self) -> None:
        """Start camera capture thread."""
        self._stop_event.clear()
        self.status = StreamStatus.CONNECTING
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name=f"capture-{self.config.camera_id}",
        )
        self._capture_thread.start()
        logger.info(f"Stream started for camera {self.config.camera_id}")

    def stop(self) -> None:
        """Stop camera capture."""
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=5.0)
        if self._cap:
            self._cap.release()
        self.status = StreamStatus.STOPPED
        logger.info(f"Stream stopped for camera {self.config.camera_id}")

    def _capture_loop(self) -> None:
        """Main capture loop running in dedicated thread."""
        retry_count = 0

        while not self._stop_event.is_set():
            try:
                url = self.config.stream_url
                # Handle webcam index
                if url.isdigit():
                    url = int(url)

                self._cap = cv2.VideoCapture(url)

                if not self._cap.isOpened():
                    raise RuntimeError(f"Cannot open stream: {self.config.stream_url}")

                # Configure for performance
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.streaming.frame_width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.streaming.frame_height)
                self._cap.set(cv2.CAP_PROP_FPS, settings.streaming.target_fps)
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

                self.status = StreamStatus.RUNNING
                retry_count = 0
                logger.info(f"Camera {self.config.camera_id} connected successfully")

                while not self._stop_event.is_set():
                    ret, frame = self._cap.read()
                    if not ret:
                        logger.warning(f"Frame read failed for camera {self.config.camera_id}")
                        break

                    self._frame_count += 1

                    # FPS calculation
                    now = time.time()
                    elapsed = now - self._last_fps_time
                    if elapsed >= 1.0:
                        self._current_fps = self._frame_count / elapsed
                        self._frame_count = 0
                        self._last_fps_time = now

                    # Drop old frames if queue is full (prefer freshness)
                    if self._frame_queue.full():
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass

                    self._frame_queue.put_nowait((frame, time.time()))

            except Exception as e:
                self.error_message = str(e)
                self.status = StreamStatus.ERROR
                logger.error(f"Camera {self.config.camera_id} error: {e}")

                retry_count += 1
                if retry_count > settings.streaming.max_reconnect_attempts:
                    logger.error(f"Max reconnect attempts reached for {self.config.camera_id}")
                    break

                if self._cap:
                    self._cap.release()
                    self._cap = None

                time.sleep(settings.streaming.reconnect_delay * retry_count)
                self.status = StreamStatus.CONNECTING
                logger.info(f"Reconnecting camera {self.config.camera_id} (attempt {retry_count})")

    def get_frame(self, timeout: float = 0.1) -> Optional[Tuple[np.ndarray, float]]:
        """Get latest frame from queue."""
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def fps(self) -> float:
        return self._current_fps

    def is_running(self) -> bool:
        return self.status == StreamStatus.RUNNING


class StreamPipeline:
    """
    Full AI processing pipeline for a camera stream.
    Processes frames through: detect → track → pose → action → anomaly → alert
    """

    def __init__(
        self,
        detection_service: ObjectDetectionService,
        tracker: MultiCameraTracker,
        pose_estimator: PoseEstimator,
        action_service: ActionRecognitionService,
        trajectory_predictor: TrajectoryPredictor,
        crowd_service: CrowdAnalyticsService,
        anomaly_service: AnomalyDetectionService,
        alert_engine: SmartAlertEngine,
    ):
        self._detect = detection_service
        self._tracker = tracker
        self._pose = pose_estimator
        self._action = action_service
        self._trajectory = trajectory_predictor
        self._crowd = crowd_service
        self._anomaly = anomaly_service
        self._alerts = alert_engine

    async def process(
        self,
        frame: np.ndarray,
        camera_config: CameraConfig,
        frame_number: int,
        encode_frame: bool = True,
    ) -> FrameResult:
        """Process a single frame through the full pipeline."""
        t0 = time.perf_counter()
        camera_id = camera_config.camera_id
        timestamp = time.time()

        # 1. Object Detection
        detection_frame = await self._detect.process_frame(frame, camera_id, frame_number)

        # 2. Multi-Object Tracking
        tracked_boxes = []
        if camera_config.tracking_enabled:
            tracked_boxes = self._tracker.update(camera_id, detection_frame)
            # Assign track IDs back to detection result
            detection_frame.detections = tracked_boxes

        active_tracks = self._tracker.get_active_tracks(camera_id)

        # 3. Pose Estimation (every 3rd frame for performance)
        poses = []
        if camera_config.pose_enabled and frame_number % 3 == 0:
            poses = self._pose.estimate(frame, tracked_boxes)

        # 4. Action Recognition
        actions = []
        if active_tracks:
            actions = self._action.update(camera_id, active_tracks, poses)

        # 5. Trajectory Prediction
        trajectory_preds = []
        if active_tracks:
            traj_inputs = [
                (t.track_id, camera_id, t.trajectory)
                for t in active_tracks
                if len(t.trajectory) >= 4
            ]
            if traj_inputs:
                trajectory_preds = self._trajectory.predict_batch(traj_inputs)

        # 6. Crowd Analytics
        crowd_metrics = self._crowd.analyze(camera_id, active_tracks, timestamp)

        # 7. Anomaly Detection
        anomalies = self._anomaly.analyze(
            camera_id, active_tracks, camera_config.zones, timestamp
        )

        # 8. Alert Generation
        alerts = []
        action_alerts = await self._alerts.process_actions(
            camera_id, camera_config.name, actions
        )
        alerts.extend(action_alerts)

        anomaly_alerts = await self._alerts.process_anomalies(
            camera_id, camera_config.name, anomalies
        )
        alerts.extend(anomaly_alerts)

        crowd_alert = await self._alerts.process_crowd(
            camera_id, camera_config.name,
            crowd_metrics.person_count, crowd_metrics.congestion_score,
        )
        if crowd_alert:
            alerts.append(crowd_alert)

        # 9. Visualize and encode frame
        encoded = None
        if encode_frame:
            viz_frame = self._visualize(frame, detection_frame, poses, trajectory_preds)
            encoded = self._encode_frame(viz_frame)

        total_ms = (time.perf_counter() - t0) * 1000

        return FrameResult(
            camera_id=camera_id,
            frame_number=frame_number,
            timestamp=timestamp,
            fps=detection_frame.fps,
            inference_ms=total_ms,
            person_count=crowd_metrics.person_count,
            total_detections=len(detection_frame.detections),
            active_tracks=len(active_tracks),
            detections=[d.to_dict() for d in detection_frame.detections],
            tracks=[
                {
                    "track_id": t.track_id,
                    "class_name": t.class_name,
                    "bbox": t.bbox.to_dict(),
                    "trajectory": [{"x": p[0], "y": p[1]} for p in t.trajectory[-20:]],
                    "age": t.age,
                }
                for t in active_tracks
            ],
            poses=[p.to_dict() for p in poses],
            actions=[a.to_dict() for a in actions],
            trajectories=[tp.to_dict() for tp in trajectory_preds],
            anomalies=[a.to_dict() for a in anomalies],
            crowd_metrics=crowd_metrics.to_dict(),
            alerts=[a.to_dict() for a in alerts],
            encoded_frame=encoded,
        )

    def _visualize(
        self,
        frame: np.ndarray,
        detection_frame: DetectionFrame,
        poses,
        trajectories,
    ) -> np.ndarray:
        """Draw all annotations on frame."""
        out = frame.copy()
        h, w = out.shape[:2]

        # Draw detections
        out = self._detect.draw_detections(out, detection_frame)

        # Draw poses
        out = self._pose.draw_poses(out, poses)

        # Draw predicted trajectories
        for traj_pred in trajectories:
            # Historical (green)
            pts_hist = [(int(p[0]*w), int(p[1]*h)) for p in traj_pred.historical[-10:]]
            for i in range(1, len(pts_hist)):
                alpha = i / len(pts_hist)
                color = (0, int(255 * alpha), 0)
                cv2.line(out, pts_hist[i-1], pts_hist[i], color, 1)

            # Predicted (orange dashed)
            pts_pred = [(int(p[0]*w), int(p[1]*h)) for p in traj_pred.predicted]
            for i in range(1, len(pts_pred)):
                if i % 2 == 0:  # Dashed effect
                    cv2.line(out, pts_pred[i-1], pts_pred[i], (0, 165, 255), 1, cv2.LINE_AA)

            if pts_pred:
                cv2.circle(out, pts_pred[-1], 4, (0, 100, 255), -1)

        return out

    def _encode_frame(self, frame: np.ndarray) -> str:
        """Encode frame to base64 JPEG for WebSocket streaming."""
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, settings.streaming.jpeg_quality]
        _, buffer = cv2.imencode(".jpg", frame, encode_params)
        return base64.b64encode(buffer.tobytes()).decode("utf-8")


# ─── Stream Manager ───────────────────────────────────────────────────────────

class StreamManager:
    """
    Manages all camera streams and their processing pipelines.
    Singleton service used across the application.
    """

    def __init__(self):
        self._streams: Dict[str, CameraStream] = {}
        self._pipeline: Optional[StreamPipeline] = None
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        self._result_callbacks: List[Callable] = []
        self._is_initialized = False

    async def initialize(self) -> None:
        """Initialize all AI services."""
        logger.info("Initializing AI pipeline...")

        detect_svc = ObjectDetectionService()
        await detect_svc.initialize()

        pose = PoseEstimator()
        pose.load()

        trajectory = TrajectoryPredictor()
        trajectory.load()

        self._pipeline = StreamPipeline(
            detection_service=detect_svc,
            tracker=MultiCameraTracker(),
            pose_estimator=pose,
            action_service=ActionRecognitionService(),
            trajectory_predictor=trajectory,
            crowd_service=CrowdAnalyticsService(),
            anomaly_service=AnomalyDetectionService(),
            alert_engine=SmartAlertEngine(),
        )

        self._is_initialized = True
        logger.info("✅ AI pipeline initialized")

    def add_result_callback(self, callback: Callable) -> None:
        self._result_callbacks.append(callback)

    async def add_camera(self, config: CameraConfig) -> None:
        """Add and start a new camera stream."""
        if config.camera_id in self._streams:
            await self.remove_camera(config.camera_id)

        stream = CameraStream(config)
        self._streams[config.camera_id] = stream
        stream.start()

        # Start processing task
        task = asyncio.create_task(
            self._process_stream(config, stream),
            name=f"process-{config.camera_id}",
        )
        self._processing_tasks[config.camera_id] = task
        logger.info(f"Camera {config.camera_id} added and processing started")

    async def remove_camera(self, camera_id: str) -> None:
        """Stop and remove a camera stream."""
        if camera_id in self._processing_tasks:
            self._processing_tasks[camera_id].cancel()
            try:
                await self._processing_tasks[camera_id]
            except asyncio.CancelledError:
                pass
            del self._processing_tasks[camera_id]

        if camera_id in self._streams:
            self._streams[camera_id].stop()
            del self._streams[camera_id]

        logger.info(f"Camera {camera_id} removed")

    async def _process_stream(
        self,
        config: CameraConfig,
        stream: CameraStream,
    ) -> None:
        """Main async processing loop for a camera stream."""
        frame_number = 0
        target_interval = 1.0 / settings.streaming.target_fps

        while True:
            loop_start = time.perf_counter()

            frame_data = stream.get_frame(timeout=0.1)
            if frame_data is None:
                if not stream.is_running():
                    await asyncio.sleep(0.5)
                continue

            frame, frame_timestamp = frame_data
            frame_number += 1

            try:
                result = await self._pipeline.process(
                    frame, config, frame_number, encode_frame=True
                )

                # Dispatch to all registered callbacks
                for callback in self._result_callbacks:
                    try:
                        await callback(result)
                    except Exception as e:
                        logger.debug(f"Result callback error: {e}")

            except Exception as e:
                logger.error(f"Pipeline error for camera {config.camera_id}: {e}")

            # Rate limiting
            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0, target_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    def get_stream_status(self) -> Dict[str, Dict]:
        return {
            cam_id: {
                "status": stream.status.value,
                "fps": round(stream.fps, 1),
                "error": stream.error_message,
            }
            for cam_id, stream in self._streams.items()
        }

    def get_alert_engine(self) -> Optional[SmartAlertEngine]:
        if self._pipeline:
            return self._pipeline._alerts
        return None

    @property
    def active_camera_count(self) -> int:
        return sum(1 for s in self._streams.values() if s.is_running())

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized


# Global singleton
stream_manager = StreamManager()
