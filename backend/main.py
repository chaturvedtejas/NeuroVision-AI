"""
NeuroVision AI — FastAPI Application Entry Point
"""
from __future__ import annotations
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from config.settings import settings
from db.models import init_db
from core.streaming.manager import stream_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    settings.ensure_dirs()
    await init_db()
    logger.info("✅ Database ready")
    try:
        import redis.asyncio as aioredis
        app.state.redis = aioredis.from_url(settings.redis.url, encoding="utf-8", decode_responses=True)
        await app.state.redis.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        app.state.redis = None
    try:
        await stream_manager.initialize()
        logger.info("✅ AI pipeline ready")
    except Exception as e:
        logger.error(f"AI pipeline init failed: {e}")
    logger.info("🚀 NeuroVision AI is ready")
    yield
    if hasattr(app.state, 'redis') and app.state.redis:
        await app.state.redis.close()

def create_app() -> FastAPI:
    app = FastAPI(
        title="NeuroVision AI",
        description="Real-Time Predictive Surveillance & Behavior Understanding System",
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    from api.routes import cameras, incidents, alerts, analytics, system, zones
    from api.websockets import stream_ws, events_ws
    pfx = "/api/v1"
    app.include_router(cameras.router,   prefix=f"{pfx}/cameras",   tags=["Cameras"])
    app.include_router(zones.router,     prefix=f"{pfx}/zones",     tags=["Zones"])
    app.include_router(incidents.router, prefix=f"{pfx}/incidents", tags=["Incidents"])
    app.include_router(alerts.router,    prefix=f"{pfx}/alerts",    tags=["Alerts"])
    app.include_router(analytics.router, prefix=f"{pfx}/analytics", tags=["Analytics"])
    app.include_router(system.router,    prefix=f"{pfx}/system",    tags=["System"])
    app.include_router(stream_ws.router, prefix="/ws",              tags=["WebSocket"])
    app.include_router(events_ws.router, prefix="/ws",              tags=["WebSocket"])

    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "healthy", "timestamp": time.time(),
                "ai_ready": stream_manager.is_initialized, "active_cameras": stream_manager.active_camera_count}

    @app.get("/", include_in_schema=False)
    async def root():
        return {"name": settings.app_name, "version": settings.app_version}

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error: {exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug, workers=1, loop="uvloop")
