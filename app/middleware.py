"""
Middleware: request-id injection, security headers, CORS, structured logging,
and Redis-based rate limiting.

Rate limits (per IP):
  POST /api/v1/auth/send-otp   → 5 requests / 10 minutes
  POST /api/v1/auth/verify-otp → 10 requests / 10 minutes
  All other endpoints          → 100 requests / minute

Rate limiting uses Redis INCR + EXPIRE — never time.time() windows.
Key pattern: ratelimit:{ip}:{path_slug}:{window_bucket}

X-Request-ID: UUID4 injected into EVERY response including error responses.
Security headers added to every response.
"""

import logging
import math
import time
import uuid

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Rate limit config ─────────────────────────────────────────────────────────

RATE_LIMITS: list[tuple[str, str, int, int]] = [
    # (method, path_prefix, max_requests, window_seconds)
    ("POST", "/api/v1/auth/send-otp",   5,   600),   # 5 / 10 min
    ("POST", "/api/v1/auth/verify-otp", 10,  600),   # 10 / 10 min
]
DEFAULT_LIMIT = (100, 60)  # 100 / 1 min


def _get_limit(method: str, path: str) -> tuple[int, int]:
    for m, p, limit, window in RATE_LIMITS:
        if method.upper() == m and path.startswith(p):
            return limit, window
    return DEFAULT_LIMIT


def _path_slug(path: str) -> str:
    return path.strip("/").replace("/", "_").replace("-", "_")[:60]


def _window_bucket(window: int) -> int:
    """Current time bucket for this window size."""
    return math.floor(time.time() / window)


# ── Middleware classes ────────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis INCR + EXPIRE rate limiting per IP address.
    Injects X-Request-ID before returning — even on 429.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Always generate request ID first so ALL responses carry it
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Check rate limit
        try:
            from app.redis_client import get_redis
            redis: aioredis.Redis = get_redis()

            ip = request.client.host if request.client else "unknown"
            method = request.method
            path = request.url.path
            limit, window = _get_limit(method, path)

            bucket = _window_bucket(window)
            key = f"ratelimit:{ip}:{_path_slug(path)}:{bucket}"

            count = await redis.incr(key)
            if count == 1:
                # First request in this window — set TTL
                await redis.expire(key, window)

            if count > limit:
                retry_after = window - int(time.time() % window)
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many requests. Try again in {retry_after} seconds",
                        "retry_after": retry_after,
                    },
                )
                response.headers["X-Request-ID"] = request_id
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                return response

        except Exception as e:
            # Redis failure must not block requests — fail open
            logger.warning("Rate limit check failed (fail-open): %s", e)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Inject headers into every response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"

        logger.info(
            "%s %s → %d (%.1fms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id[:8],
        )
        return response


def register_middleware(app: FastAPI) -> None:
    """Register all middleware in correct order (outermost first)."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RateLimitMiddleware)
