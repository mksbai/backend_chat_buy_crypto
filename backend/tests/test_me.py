import sys
from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import app  # noqa: E402  pylint: disable=wrong-import-position


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_me_endpoint_returns_session_information():
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"anonymous": True, "user_id": None}
