"""Double-submit CSRF protection utilities."""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import Response


LOGGER = logging.getLogger("chat-backend.csrf")

CSRFTOKEN_COOKIE_NAME = "csrftoken"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _cookie_secure() -> bool:
    return os.getenv("APP_ENV") == "prod"


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def ensure_csrf_cookie(response: Response, token: Optional[str] = None) -> str:
    """Ensure the csrftoken cookie is present on the response."""

    value = token or generate_csrf_token()
    response.set_cookie(
        CSRFTOKEN_COOKIE_NAME,
        value,
        httponly=False,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    return value


async def require_csrf(request: Request) -> None:
    """Dependency enforcing the double-submit cookie pattern."""

    if request.method not in MUTATING_METHODS:
        return

    cookie = request.cookies.get(CSRFTOKEN_COOKIE_NAME)
    header = request.headers.get("X-CSRF-Token")

    if not cookie or not header:
        LOGGER.info(
            "csrf.reject",
            extra={
                "reason": "missing",
                "ip": request.client.host if request.client else "unknown",
                "sid": getattr(request.state, "sid", "")[:8],
            },
        )
        raise HTTPException(status_code=403, detail="CSRF token missing")

    if not secrets.compare_digest(cookie, header):
        LOGGER.info(
            "csrf.reject",
            extra={
                "reason": "mismatch",
                "ip": request.client.host if request.client else "unknown",
                "sid": getattr(request.state, "sid", "")[:8],
            },
        )
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


def ensure_csrf_cookie_from_request(request: Request, response: Response) -> None:
    if CSRFTOKEN_COOKIE_NAME not in request.cookies:
        ensure_csrf_cookie(response)


__all__ = [
    "CSRFTOKEN_COOKIE_NAME",
    "ensure_csrf_cookie",
    "ensure_csrf_cookie_from_request",
    "generate_csrf_token",
    "require_csrf",
]
