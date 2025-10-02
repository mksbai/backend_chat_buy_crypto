"""FastAPI application providing chat streaming endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from json import JSONDecodeError
from typing import AsyncGenerator, Iterable
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from settings import settings

from core.anti_replay import AntiReplayMiddleware
from core.csrf import ensure_csrf_cookie_from_request, require_csrf
from core.rate_limit import RateLimitMiddleware
from core.sessions import SessionMiddleware, register_session_events

logger = logging.getLogger("chat-backend")
logging.basicConfig(level=settings.log_level.upper())

PLACEHOLDER_TEXT = (
    "This is a placeholder response from the backend. Your message was received and the "
    "streaming is working. Replace this with real AI output when ready."
)
CHUNK_SIZE = 24


def chunk_text(text: str, size: int) -> Iterable[str]:
    for index in range(0, len(text), size):
        yield text[index : index + size]


def message_too_large(message: str) -> bool:
    return len(message.encode("utf-8")) > settings.max_message_bytes


app = FastAPI()
register_session_events(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.add_middleware(SessionMiddleware)
app.add_middleware(AntiReplayMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def add_request_logging(request: Request, call_next):  # type: ignore[override]
    request_id = str(uuid4())
    request.state.request_id = request_id
    logger.info(
        "request.start",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else None,
            "request_id": request_id,
        },
    )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request.error", extra={"request_id": request_id})
        raise
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "request.end",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "request_id": request_id,
        },
    )
    return response


@app.middleware("http")
async def ensure_csrf_cookie_middleware(request: Request, call_next):  # type: ignore[override]
    response = await call_next(request)
    ensure_csrf_cookie_from_request(request, response)
    return response


async def stream_placeholder(delay: float) -> AsyncGenerator[str, None]:
    try:
        for chunk in chunk_text(PLACEHOLDER_TEXT, CHUNK_SIZE):
            yield chunk
            await asyncio.sleep(delay)
    finally:
        logger.debug("stream.closed")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/me")
async def me(request: Request):
    session = getattr(request.state, "session", {})
    if not isinstance(session, dict):
        session = {}

    user_id = session.get("user_id")
    return {"anonymous": user_id is None, "user_id": user_id}


@app.post("/api/chat", dependencies=[Depends(require_csrf)])
async def chat_endpoint(request: Request):
    try:
        payload = await request.body()
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("request.body_error")
        raise HTTPException(status_code=400, detail="Invalid request body") from exc

    if not payload:
        raise HTTPException(status_code=400, detail="Request body is required")

    try:
        data = json.loads(payload)
    except JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    message = data.get("message") if isinstance(data, dict) else None
    if message is None:
        raise HTTPException(status_code=400, detail="'message' field is required")
    if not isinstance(message, str):
        raise HTTPException(status_code=400, detail="'message' must be a string")
    if not message.strip():
        raise HTTPException(status_code=400, detail="'message' must not be empty")
    if message_too_large(message):
        raise HTTPException(status_code=400, detail="'message' exceeds size limit")

    delay_seconds = max(settings.delay_ms, 0) / 1000

    response = StreamingResponse(
        stream_placeholder(delay_seconds),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[override]
    detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    response = JSONResponse(status_code=exc.status_code, content=detail)
    if request_id := getattr(request.state, "request_id", None):
        response.headers.setdefault("X-Request-Id", request_id)
    return response
