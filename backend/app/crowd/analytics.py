"""
NeuroVision AI - Crowd Analytics
Real-time crowd density estimation, heatmaps, and flow analysis
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from app.tracking.tracker import TrackState


@dataclass
class CrowdMetrics:
    camera_id: str
    timestamp: float
    person_count: int
    density_score: float       # 0-1
    congestion_score: float    # 0-1
    avg_velocity: float
    flow_direction: Optional[Tuple[float, float]]  # (vx, vy) dominant flow
    hotspots: List[Tuple[float, float, float]]      # [(x, y, intensity)]
    heatmap: Optional[np.ndarray] = None            # H x W density map

    def to_dict(self) -> Dict:
        return {
            "camera_id": self.camera_id,
            "timestamp": self.timestamp,
            "person_count": self.person_count,
            "density_score": round(self.density_score, 3),
            "congestion_score": round(self.congestion_score, 3),
            "avg_velocity": round(self.avg_velocity, 4),
            "flow_direction": list(self.flow_direction) if self.flow_direction else None,
            "hotspots": [
                {"x": round(x, 3), "y": round(y, 3), "intensity": round(i, 3)}
                for x, y, i in self.hotspots
            ],
        }


class DensityEstimator:
    """
    Gaussian kernel-based crowd density estimation.
    Creates density maps from person bounding box centroids.
    """

    def __init__(self, grid_size: Tuple[int, int] = (64, 64), kernel_sigma: float = 3.0):
        self.grid_h, self.grid_w = grid_size
        self.sigma = kernel_sigma
        self._kernel = self._make_gaussian_kernel(int(kernel_sigma * 4) | 1)

    def _make_gaussian_kernel(self, size: int) -> np.ndarray:
        """Create normalized 2D Gaussian kernel."""
        half = size // 2
        x = np.arange(-half, half + 1)
        y = np.arange(-half, half + 1)
        xx, yy = np.meshgrid(x, y)
        kernel = np.exp(-(xx**2 + yy**2) / (2 * self.sigma**2))
        return (kernel / kernel.sum()).astype(np.float32)

    def compute_density(self, positions: List[Tuple[float, float]]) -> np.ndarray:
        """
        Compute density map from normalized positions.
        Returns (H, W) density array normalized to [0, 1].
        """
        density = np.zeros((self.grid_h, self.grid_w), dtype=np.float32)

        for x, y in positions:
            gx = int(np.clip(x * self.grid_w, 0, self.grid_w - 1))
            gy = int(np.clip(y * self.grid_h, 0, self.grid_h - 1))

            kh, kw = self._kernel.shape
            half_h, half_w = kh // 2, kw // 2

            y1 = max(0, gy - half_h)
            y2 = min(self.grid_h, gy + half_h + 1)
            x1 = max(0, gx - half_w)
            x2 = min(self.grid_w, gx + half_w + 1)

            ky1 = half_h - (gy - y1)
            ky2 = ky1 + (y2 - y1)
            kx1 = half_w - (gx - x1)
            kx2 = kx1 + (x2 - x1)

            density[y1:y2, x1:x2] += self._kernel[ky1:ky2, kx1:kx2]

        if density.max() > 0:
            density /= density.max()

        return density

    def density_to_heatmap(
        self,
        density: np.ndarray,
        output_size: Tuple[int, int] = (256, 256),
        colormap: int = cv2.COLORMAP_JET,
    ) -> np.ndarray:
        """Convert density map to colored heatmap image."""
        resized = cv2.resize(density, output_size, interpolation=cv2.INTER_LINEAR)
        normalized = (resized * 255).astype(np.uint8)
        colored = cv2.applyColorMap(normalized, colormap)
        return colored

    def find_hotspots(
        self,
        density: np.ndarray,
        n_spots: int = 5,
        min_intensity: float = 0.3,
    ) -> List[Tuple[float, float, float]]:
        """Find high-density hotspot locations."""
        spots = []
        d = density.copy()

        for _ in range(n_spots):
            idx = np.unravel_index(d.argmax(), d.shape)
            val = d[idx]
            if val < min_intensity:
                break

            # Normalized coordinates
            ny = idx[0] / self.grid_h
            nx = idx[1] / self.grid_w
            spots.append((float(nx), float(ny), float(val)))

            # Suppress neighborhood
            gy, gx = idx
            half = max(2, int(self.sigma))
            y1 = max(0, gy - half)
            y2 = min(self.grid_h, gy + half + 1)
            x1 = max(0, gx - half)
            x2 = min(self.grid_w, gx + half + 1)
            d[y1:y2, x1:x2] = 0

        return spots


class FlowAnalyzer:
    """
    Optical flow analysis for crowd movement direction and speed.
    Uses Lucas-Kanade sparse optical flow on person bounding box regions.
    """

    def __init__(self, history_frames: int = 10):
        self.history_frames = history_frames
        self._position_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=history_frames))

    def update(self, tracks: List[TrackState]) -> None:
        for track in tracks:
            self._position_history[track.track_id].append(track.bbox.center)

    def compute_flow(
        self,
        tracks: List[TrackState],
    ) -> Tuple[Optional[Tuple[float, float]], float]:
        """
        Compute dominant flow direction and average velocity.
        Returns: (flow_vector, avg_speed)
        """
        velocities = []

        for track in tracks:
            hist = self._position_history.get(track.track_id)
            if hist is None or len(hist) < 3:
                continue

            positions = list(hist)
            # Average velocity over last few frames
            n = min(5, len(positions) - 1)
            if n < 1:
                continue

            recent = positions[-n-1:]
            vx = (recent[-1][0] - recent[0][0]) / n
            vy = (recent[-1][1] - recent[0][1]) / n
            velocities.append((vx, vy))

        if not velocities:
            return None, 0.0

        vel_arr = np.array(velocities)
        avg_vx = float(np.mean(vel_arr[:, 0]))
        avg_vy = float(np.mean(vel_arr[:, 1]))
        avg_speed = float(np.mean(np.linalg.norm(vel_arr, axis=1)))

        # Normalize flow vector
        mag = np.sqrt(avg_vx**2 + avg_vy**2)
        if mag > 1e-6:
            flow = (avg_vx / mag, avg_vy / mag)
        else:
            flow = (0.0, 0.0)

        return flow, avg_speed

    def cleanup_stale(self, active_ids: set) -> None:
        stale = [tid for tid in self._position_history if tid not in active_ids]
        for tid in stale:
            del self._position_history[tid]


class CrowdAnalyticsService:
    """
    Orchestrates crowd density, flow, and congestion analysis
    across multiple camera streams.
    """

    MAX_CAPACITY = 50  # Person count considered 100% congestion

    def __init__(self):
        self._density_estimator = DensityEstimator(grid_size=(64, 64))
        self._flow_analyzers: Dict[str, FlowAnalyzer] = {}
        self._cumulative_heatmaps: Dict[str, np.ndarray] = {}
        self._heatmap_decay = 0.995  # Per-frame decay

    def get_flow_analyzer(self, camera_id: str) -> FlowAnalyzer:
        if camera_id not in self._flow_analyzers:
            self._flow_analyzers[camera_id] = FlowAnalyzer()
        return self._flow_analyzers[camera_id]

    def analyze(
        self,
        camera_id: str,
        tracks: List[TrackState],
        timestamp: float,
    ) -> CrowdMetrics:
        """Analyze crowd metrics for current frame."""
        import time

        persons = [t for t in tracks if t.class_name == "person"]
        positions = [t.bbox.center for t in persons]

        # Density
        density = self._density_estimator.compute_density(positions)
        density_score = float(density.mean()) if len(positions) > 0 else 0.0

        # Update cumulative heatmap
        if camera_id not in self._cumulative_heatmaps:
            self._cumulative_heatmaps[camera_id] = np.zeros_like(density)
        self._cumulative_heatmaps[camera_id] *= self._heatmap_decay
        self._cumulative_heatmaps[camera_id] += density

        # Hotspots
        hotspots = self._density_estimator.find_hotspots(density)

        # Flow
        flow_analyzer = self.get_flow_analyzer(camera_id)
        flow_analyzer.update(persons)
        flow_vector, avg_velocity = flow_analyzer.compute_flow(persons)
        flow_analyzer.cleanup_stale({t.track_id for t in persons})

        # Congestion
        count = len(persons)
        congestion = min(1.0, count / self.MAX_CAPACITY)

        # Amplify if density is high
        if density_score > 0.5:
            congestion = min(1.0, congestion * 1.5)

        return CrowdMetrics(
            camera_id=camera_id,
            timestamp=timestamp,
            person_count=count,
            density_score=density_score,
            congestion_score=congestion,
            avg_velocity=avg_velocity,
            flow_direction=flow_vector,
            hotspots=hotspots,
            heatmap=density,
        )

    def get_cumulative_heatmap_image(
        self,
        camera_id: str,
        size: Tuple[int, int] = (512, 512),
    ) -> Optional[np.ndarray]:
        """Get accumulated heatmap as colored image for visualization."""
        hm = self._cumulative_heatmaps.get(camera_id)
        if hm is None:
            return None
        if hm.max() > 0:
            normalized = hm / hm.max()
        else:
            normalized = hm
        return self._density_estimator.density_to_heatmap(normalized, output_size=size)

    def reset_heatmap(self, camera_id: str) -> None:
        self._cumulative_heatmaps.pop(camera_id, None)
