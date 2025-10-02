"""Replay protection middleware."""
from __future__ import annotations

import logging
import os
import time
from typing import Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


LOGGER = logging.getLogger("chat-backend.anti-replay")

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
FRESHNESS_WINDOW = int(os.getenv("FRESHNESS_WINDOW", "300"))
NONCES: Dict[str, float] = {}


class AntiReplayMiddleware(BaseHTTPMiddleware):
    """Rejects requests that reuse nonces or stale timestamps."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        sid_prefix = getattr(request.state, "sid", "")[:8]

        ts_header = request.headers.get("X-TS")
        nonce = request.headers.get("X-Nonce")

        if not ts_header or not nonce:
            LOGGER.info(
                "anti_replay.reject",
                extra={"reason": "missing_headers", "ip": client_host, "sid": sid_prefix},
            )
            return Response(status_code=401)

        try:
            ts_value = int(ts_header)
        except ValueError:
            LOGGER.info(
                "anti_replay.reject",
                extra={"reason": "invalid_ts", "ip": client_host, "sid": sid_prefix},
            )
            return Response(status_code=401)

        now = int(time.time())
        if abs(now - ts_value) > FRESHNESS_WINDOW:
            LOGGER.info(
                "anti_replay.reject",
                extra={"reason": "stale_ts", "ip": client_host, "sid": sid_prefix},
            )
            return Response(status_code=401)

        # purge expired nonces lazily
        expired = [key for key, expires in NONCES.items() if expires <= now]
        for key in expired:
            NONCES.pop(key, None)

        if nonce in NONCES:
            LOGGER.info(
                "anti_replay.reject",
                extra={"reason": "nonce_reuse", "ip": client_host, "sid": sid_prefix},
            )
            return Response(status_code=401)

        NONCES[nonce] = now + FRESHNESS_WINDOW
        return await call_next(request)


__all__ = ["AntiReplayMiddleware", "FRESHNESS_WINDOW", "NONCES"]
