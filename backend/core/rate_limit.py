"""In-memory per-IP rate limiting middleware."""
from __future__ import annotations

import logging
import os
import time
from typing import Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


LOGGER = logging.getLogger("chat-backend.rate-limit")

RATE_LIMIT_RPS = float(os.getenv("RATE_LIMIT_RPS", "10.0"))
RATE_LIMIT_BURST = RATE_LIMIT_RPS * 2
_RATE_LIMIT_STATE: Dict[str, Dict[str, float]] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple token-bucket rate limiter."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if RATE_LIMIT_RPS <= 0:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        record = _RATE_LIMIT_STATE.get(client_host)
        now = time.time()

        if record is None:
            record = {"tokens": RATE_LIMIT_BURST, "ts": now}
        else:
            elapsed = max(0.0, now - record["ts"])
            record["tokens"] = min(
                RATE_LIMIT_BURST,
                record.get("tokens", RATE_LIMIT_BURST) + elapsed * RATE_LIMIT_RPS,
            )
            record["ts"] = now

        if record["tokens"] < 1.0:
            LOGGER.info(
                "rate_limit.reject",
                extra={"ip": client_host, "sid": getattr(request.state, "sid", "")[:8]},
            )
            _RATE_LIMIT_STATE[client_host] = record
            return Response(status_code=429)

        record["tokens"] -= 1.0
        _RATE_LIMIT_STATE[client_host] = record
        return await call_next(request)


__all__ = ["RateLimitMiddleware", "RATE_LIMIT_RPS", "RATE_LIMIT_BURST"]
