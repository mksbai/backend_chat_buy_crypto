import sys
from pathlib import Path

import secrets
import time

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import app, PLACEHOLDER_TEXT  # noqa: E402  pylint: disable=wrong-import-position


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_healthz():
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_chat_streams_placeholder_text():
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as client:
            seed_response = await client.get("/healthz")
            assert seed_response.status_code == 200

            csrf_cookie = client.cookies.get("csrftoken")
            assert csrf_cookie is not None

            headers = {
                "X-CSRF-Token": csrf_cookie,
                "X-TS": str(int(time.time())),
                "X-Nonce": secrets.token_hex(16),
            }

            response = await client.post(
                "/api/chat",
                json={"message": "hello"},
                headers=headers,
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/plain")
            assert response.headers["cache-control"] == "no-cache"
            chunks = []
            async for chunk in response.aiter_text():
                chunks.append(chunk)
    body = "".join(chunks)
    assert PLACEHOLDER_TEXT in body
