"""
NeuroVision AI — WebSocket: Live Camera Stream
Pushes annotated frames + analytics to connected clients in real time
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from core.streaming.manager import FrameResult, stream_manager

router = APIRouter()


class StreamConnectionManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, camera_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(camera_id, set()).add(ws)
        logger.info(f"Stream WS connected camera={camera_id} total={len(self._connections[camera_id])}")

    def disconnect(self, camera_id: str, ws: WebSocket) -> None:
        if camera_id in self._connections:
            self._connections[camera_id].discard(ws)
            if not self._connections[camera_id]:
                del self._connections[camera_id]

    async def broadcast(self, camera_id: str, data: dict) -> None:
        connections = self._connections.get(camera_id, set()).copy()
        if not connections:
            return
        message = json.dumps(data)
        dead: Set[WebSocket] = set()
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[camera_id].discard(ws)

    def has_viewers(self, camera_id: str) -> bool:
        return bool(self._connections.get(camera_id))


ws_manager = StreamConnectionManager()


async def _frame_result_handler(result: FrameResult) -> None:
    """Registered with StreamManager to push frames to WebSocket clients."""
    if not ws_manager.has_viewers(result.camera_id):
        return

    payload = {
        "type": "frame",
        "camera_id": result.camera_id,
        "frame_number": result.frame_number,
        "timestamp": result.timestamp,
        "fps": round(result.fps, 1),
        "inference_ms": round(result.inference_ms, 1),
        "person_count": result.person_count,
        "total_detections": result.total_detections,
        "active_tracks": result.active_tracks,
        "frame": result.encoded_frame,
        "detections": result.detections,
        "tracks": result.tracks,
        "actions": result.actions,
        "trajectories": result.trajectories,
        "anomalies": result.anomalies,
        "crowd": result.crowd_metrics,
        "alerts": result.alerts,
    }
    await ws_manager.broadcast(result.camera_id, payload)


# Register handler once at import time
stream_manager.add_result_callback(_frame_result_handler)


@router.websocket("/stream/{camera_id}")
async def stream_endpoint(camera_id: str, websocket: WebSocket):
    """
    WebSocket: live annotated video + analytics for a single camera.
    Client sends: { action: "pause"|"resume"|"ping" }
    Server sends: { type: "frame", frame (base64), detections, tracks, actions, ... }
    """
    await ws_manager.connect(camera_id, websocket)

    await websocket.send_json({
        "type": "connected",
        "camera_id": camera_id,
        "timestamp": time.time(),
    })

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=0.05)
                action = data.get("action")
                if action == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
            except asyncio.TimeoutError:
                pass
            except Exception:
                break
    except WebSocketDisconnect:
        logger.info(f"Stream WS disconnected: camera {camera_id}")
    finally:
        ws_manager.disconnect(camera_id, websocket)
