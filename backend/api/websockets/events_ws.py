"""
NeuroVision AI — WebSocket: Global Event Bus
Broadcasts alerts, incidents, and system metrics to all dashboard clients
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


class EventBroadcaster:
    """Global event broadcaster for dashboard-level events."""

    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._broadcast_task = None
        self._metrics_task = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        logger.info(f"Dashboard WS connected | total={len(self._clients)}")

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def emit(self, event_type: str, data: dict) -> None:
        payload = {"type": event_type, "timestamp": time.time(), **data}
        try:
            self._event_queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass

    async def broadcast_loop(self) -> None:
        while True:
            try:
                payload = await asyncio.wait_for(self._event_queue.get(), timeout=2.0)
                message = json.dumps(payload)
                dead: Set[WebSocket] = set()
                for ws in self._clients.copy():
                    try:
                        await ws.send_text(message)
                    except Exception:
                        dead.add(ws)
                for ws in dead:
                    self._clients.discard(ws)
            except asyncio.TimeoutError:
                if self._clients:
                    hb = json.dumps({"type": "heartbeat", "timestamp": time.time()})
                    dead = set()
                    for ws in self._clients.copy():
                        try:
                            await ws.send_text(hb)
                        except Exception:
                            dead.add(ws)
                    for ws in dead:
                        self._clients.discard(ws)
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")
                await asyncio.sleep(0.5)

    async def system_metrics_loop(self) -> None:
        import psutil
        while True:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()

                gpu_util, gpu_mem = None, None
                try:
                    import GPUtil
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu_util = gpus[0].load * 100
                        gpu_mem = gpus[0].memoryUtil * 100
                except Exception:
                    pass

                from core.streaming.manager import stream_manager
                statuses = stream_manager.get_stream_status()
                active = sum(1 for s in statuses.values() if s["status"] == "running")
                avg_fps = (
                    sum(s["fps"] for s in statuses.values()) / len(statuses)
                    if statuses else 0.0
                )

                await self.emit("system_metrics", {
                    "cpu_percent": round(cpu, 1),
                    "memory_percent": round(mem.percent, 1),
                    "memory_used_gb": round(mem.used / 1e9, 2),
                    "memory_total_gb": round(mem.total / 1e9, 2),
                    "gpu_percent": round(gpu_util, 1) if gpu_util is not None else None,
                    "gpu_memory_percent": round(gpu_mem, 1) if gpu_mem is not None else None,
                    "active_cameras": active,
                    "total_cameras": len(statuses),
                    "avg_fps": round(avg_fps, 1),
                    "ws_clients": self.client_count,
                })
            except Exception as e:
                logger.debug(f"Metrics broadcast error: {e}")

            await asyncio.sleep(2.0)

    def ensure_background_tasks(self):
        loop = asyncio.get_event_loop()
        running = {t.get_name() for t in asyncio.all_tasks(loop)}
        if "nv_broadcast_loop" not in running:
            asyncio.create_task(self.broadcast_loop(), name="nv_broadcast_loop")
        if "nv_metrics_loop" not in running:
            asyncio.create_task(self.system_metrics_loop(), name="nv_metrics_loop")

    @property
    def client_count(self) -> int:
        return len(self._clients)


event_broadcaster = EventBroadcaster()


@router.websocket("/events")
async def events_endpoint(websocket: WebSocket):
    """
    WebSocket: global dashboard events.
    Receives: { type: "alert"|"system_metrics"|"heartbeat"|"incident" }
    """
    await event_broadcaster.connect(websocket)
    event_broadcaster.ensure_background_tasks()

    await websocket.send_json({
        "type": "connected",
        "message": "NeuroVision AI event stream connected",
        "timestamp": time.time(),
    })

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
            except asyncio.TimeoutError:
                pass
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        event_broadcaster.disconnect(websocket)
