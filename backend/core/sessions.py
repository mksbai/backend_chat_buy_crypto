"""In-memory session management for FastAPI."""
from __future__ import annotations

import asyncio
import os
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

SESSION_COOKIE_NAME = "sid"
SESSION_TTL = int(os.getenv("SESSION_TTL", "1800"))
SESSION_GC_INTERVAL = 60


SessionData = Dict[str, Any]


SESSIONS: Dict[str, SessionData] = {}
_GC_TASK: Optional[asyncio.Task[None]] = None


def _generate_sid() -> str:
    return secrets.token_urlsafe(32)


def _is_expired(session: SessionData, now: Optional[float] = None) -> bool:
    now = now or time.time()
    return (now - session["last_seen"]) > SESSION_TTL


def _create_session() -> tuple[str, SessionData]:
    now = time.time()
    sid = _generate_sid()
    session: SessionData = {
        "created_at": now,
        "last_seen": now,
        "user_id": None,
    }
    SESSIONS[sid] = session
    return sid, session


def rotate_sid(old_sid: str) -> tuple[str, SessionData]:
    """Rotate an existing SID to mitigate session fixation."""

    existing = SESSIONS.pop(old_sid, None)
    new_sid, session = _create_session()
    if existing:
        session.update(existing)
        session["created_at"] = existing["created_at"]
        session["last_seen"] = time.time()
    return new_sid, session


async def _gc_loop() -> None:
    try:
        while True:
            await asyncio.sleep(SESSION_GC_INTERVAL)
            now = time.time()
            expired = [sid for sid, session in SESSIONS.items() if _is_expired(session, now)]
            for sid in expired:
                SESSIONS.pop(sid, None)
    except asyncio.CancelledError:  # pragma: no cover - shutdown
        pass


def register_session_events(app) -> None:
    """Register startup/shutdown events for session garbage collection."""

    @app.on_event("startup")
    async def _start_gc() -> None:  # pragma: no cover - event hook
        global _GC_TASK
        if _GC_TASK is None:
            _GC_TASK = asyncio.create_task(_gc_loop())

    @app.on_event("shutdown")
    async def _stop_gc() -> None:  # pragma: no cover - event hook
        global _GC_TASK
        if _GC_TASK:
            _GC_TASK.cancel()
            try:
                await _GC_TASK
            except asyncio.CancelledError:
                pass
            _GC_TASK = None


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware that manages sessions stored in memory."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.secure_cookie = os.getenv("APP_ENV") == "prod"

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        sid = request.cookies.get(SESSION_COOKIE_NAME)
        now = time.time()
        session: Optional[SessionData] = None

        if sid:
            session = SESSIONS.get(sid)
            if session and _is_expired(session, now):
                SESSIONS.pop(sid, None)
                session = None
        if session is None:
            sid, session = _create_session()
        else:
            session["last_seen"] = now

        request.state.sid = sid
        request.state.session = session

        response = await call_next(request)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            sid,
            httponly=True,
            secure=self.secure_cookie,
            samesite="lax",
            path="/",
            max_age=SESSION_TTL,
        )
        return response


__all__ = [
    "SESSION_TTL",
    "SESSION_COOKIE_NAME",
    "SessionMiddleware",
    "rotate_sid",
    "register_session_events",
    "SESSIONS",
]
