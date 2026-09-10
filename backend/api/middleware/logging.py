"""Request logging middleware."""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - t0) * 1000
        if not request.url.path.startswith("/ws"):
            logger.debug(f"{request.method} {request.url.path} → {response.status_code} ({ms:.1f}ms)")
        return response
