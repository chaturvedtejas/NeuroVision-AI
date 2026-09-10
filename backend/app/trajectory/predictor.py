"""
NeuroVision AI - Trajectory Prediction
LSTM-based movement prediction for anticipatory surveillance.
Predicts future N positions from historical trajectory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from loguru import logger

from config.settings import settings


@dataclass
class TrajectoryPrediction:
    track_id: int
    camera_id: str
    historical: List[Tuple[float, float]]  # Past positions
    predicted: List[Tuple[float, float]]   # Predicted future positions
    confidence: float
    predicted_zone: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "track_id": self.track_id,
            "camera_id": self.camera_id,
            "historical": [{"x": x, "y": y} for x, y in self.historical],
            "predicted": [{"x": x, "y": y} for x, y in self.predicted],
            "confidence": round(self.confidence, 3),
        }


# ─── LSTM Model ────────────────────────────────────────────────────────────────

class TrajectoryLSTM(nn.Module):
    """
    Sequence-to-sequence LSTM for trajectory prediction.
    Input: (batch, seq_len, 2) - normalized x,y positions
    Output: (batch, pred_len, 2) - predicted positions
    """

    def __init__(
        self,
        input_size: int = 2,
        hidden_size: int = 128,
        num_layers: int = 2,
        pred_len: int = 15,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.pred_len = pred_len

        # Encoder
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Velocity embedding
        self.velocity_embed = nn.Linear(2, 32)

        # Decoder
        self.decoder = nn.LSTM(
            input_size=input_size + 32,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Output projection
        self.fc_out = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 2),
        )

        # Attention
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=4,
            batch_first=True,
            dropout=0.1,
        )

    def forward(
        self,
        x: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, 2) - input trajectory
        Returns:
            (batch, pred_len, 2) - predicted positions
        """
        batch_size = x.shape[0]

        # Compute velocities
        velocities = torch.diff(x, dim=1)  # (batch, seq-1, 2)
        if velocities.shape[1] > 0:
            last_vel = velocities[:, -1:, :]  # (batch, 1, 2)
        else:
            last_vel = torch.zeros(batch_size, 1, 2, device=x.device)

        # Encode sequence
        enc_out, (h_n, c_n) = self.encoder(x)

        # Self-attention over encoded sequence
        attn_out, _ = self.attention(enc_out, enc_out, enc_out)

        # Decode autoregressively
        preds = []
        last_pos = x[:, -1:, :]  # (batch, 1, 2)
        vel_feat = self.velocity_embed(last_vel)  # (batch, 1, 32)

        h, c = h_n, c_n
        for _ in range(self.pred_len):
            dec_in = torch.cat([last_pos, vel_feat], dim=-1)  # (batch, 1, 34)
            dec_out, (h, c) = self.decoder(dec_in, (h, c))
            pos_delta = self.fc_out(dec_out)  # (batch, 1, 2)
            next_pos = last_pos + pos_delta
            preds.append(next_pos)

            # Update velocity
            vel_feat = self.velocity_embed(pos_delta)
            last_pos = next_pos

        return torch.cat(preds, dim=1)  # (batch, pred_len, 2)


# ─── Prediction Service ────────────────────────────────────────────────────────

class TrajectoryPredictor:
    """
    Manages trajectory prediction with optional learned model
    or physics-based fallback.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        history_frames: int = 30,
        predict_frames: int = 15,
    ):
        self.history_frames = history_frames
        self.predict_frames = predict_frames
        self.device = settings.ai.device
        self._model: Optional[TrajectoryLSTM] = None
        self._model_path = model_path
        self._use_learned = False

    def load(self) -> None:
        """Try to load learned model, fall back to physics."""
        if self._model_path:
            try:
                model = TrajectoryLSTM(pred_len=self.predict_frames)
                state = torch.load(self._model_path, map_location=self.device)
                model.load_state_dict(state)
                model.eval()
                model.to(self.device)
                self._model = model
                self._use_learned = True
                logger.info(f"✅ Trajectory LSTM loaded from {self._model_path}")
            except Exception as e:
                logger.warning(f"Could not load trajectory model: {e}. Using physics fallback.")
        else:
            logger.info("No trajectory model path specified. Using physics-based prediction.")

    def predict(
        self,
        track_id: int,
        camera_id: str,
        trajectory: List[Tuple[float, float]],
    ) -> Optional[TrajectoryPrediction]:
        """Predict future positions from trajectory history."""
        if len(trajectory) < 4:
            return None

        # Use last N positions
        hist = trajectory[-self.history_frames:]

        if self._use_learned and self._model is not None:
            predicted = self._predict_lstm(hist)
            confidence = 0.82
        else:
            predicted = self._predict_physics(hist)
            confidence = 0.65

        return TrajectoryPrediction(
            track_id=track_id,
            camera_id=camera_id,
            historical=hist,
            predicted=predicted,
            confidence=confidence,
        )

    def _predict_lstm(
        self,
        trajectory: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        """LSTM-based prediction."""
        arr = np.array(trajectory, dtype=np.float32)

        # Normalize around last position
        mean = arr.mean(axis=0)
        std = arr.std(axis=0) + 1e-6
        normalized = (arr - mean) / std

        x = torch.from_numpy(normalized).unsqueeze(0).to(self.device)

        with torch.no_grad():
            pred = self._model(x)  # (1, pred_len, 2)

        pred_np = pred.squeeze(0).cpu().numpy()
        # Denormalize
        pred_denorm = pred_np * std + mean

        # Clamp to valid range
        pred_denorm = np.clip(pred_denorm, 0.0, 1.0)

        return [(float(p[0]), float(p[1])) for p in pred_denorm]

    def _predict_physics(
        self,
        trajectory: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        """
        Physics-based prediction using Kalman smoother and constant velocity model.
        Falls back to linear extrapolation with velocity decay.
        """
        arr = np.array(trajectory)
        n = len(arr)

        if n < 2:
            return [trajectory[-1]] * self.predict_frames

        # Estimate velocity using exponential moving average
        alpha = 0.3
        vx, vy = 0.0, 0.0
        for i in range(1, n):
            dvx = arr[i][0] - arr[i-1][0]
            dvy = arr[i][1] - arr[i-1][1]
            vx = alpha * dvx + (1 - alpha) * vx
            vy = alpha * dvy + (1 - alpha) * vy

        # Acceleration (second-order)
        ax, ay = 0.0, 0.0
        if n >= 3:
            # Average acceleration
            accs_x = []
            accs_y = []
            for i in range(2, min(n, 6)):
                dvx1 = arr[i-1][0] - arr[i-2][0]
                dvx2 = arr[i][0] - arr[i-1][0]
                accs_x.append(dvx2 - dvx1)
                dvy1 = arr[i-1][1] - arr[i-2][1]
                dvy2 = arr[i][1] - arr[i-1][1]
                accs_y.append(dvy2 - dvy1)
            if accs_x:
                ax = np.mean(accs_x) * 0.1  # Dampen acceleration
                ay = np.mean(accs_y) * 0.1

        predictions = []
        last = arr[-1].copy()
        decay = 0.98  # Velocity decay factor

        for i in range(self.predict_frames):
            vx = vx * decay + ax
            vy = vy * decay + ay
            next_x = last[0] + vx
            next_y = last[1] + vy
            next_x = float(np.clip(next_x, 0.0, 1.0))
            next_y = float(np.clip(next_y, 0.0, 1.0))
            predictions.append((next_x, next_y))
            last = np.array([next_x, next_y])

        return predictions

    def predict_batch(
        self,
        tracks: List[Tuple[int, str, List[Tuple[float, float]]]],
    ) -> List[TrajectoryPrediction]:
        """Predict trajectories for multiple tracks."""
        results = []
        for track_id, camera_id, trajectory in tracks:
            pred = self.predict(track_id, camera_id, trajectory)
            if pred is not None:
                results.append(pred)
        return results
