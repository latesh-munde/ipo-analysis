from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"status": "ok"},
        "error": None,
        "meta": {},
    }


def test_home_page_is_served() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "IPO Analysis" in response.text


def test_unknown_api_route_returns_standard_error() -> None:
    response = client.get("/api/v1/unknown")

    assert response.status_code == 404
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "NOT_FOUND"
