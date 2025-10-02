from fastapi.testclient import TestClient

from app import app
from core.csrf import CSRFTOKEN_COOKIE_NAME


client = TestClient(app)


def test_csrf_seed_sets_cookie_and_allows_frontend_origin():
    response = client.get("/csrf", headers={"origin": "https://www.mksmart.info"})

    assert response.status_code == 200
    payload = response.json()
    token = payload.get("csrf")
    assert token
    assert response.cookies.get(CSRFTOKEN_COOKIE_NAME) == token
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://www.mksmart.info"
    )
    assert response.headers.get("access-control-allow-credentials") == "true"
