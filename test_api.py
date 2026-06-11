import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_key_123")

    with TestClient(app) as test_client:
        yield test_client


def test_get_order_uses_cache_aside(client: TestClient):
    response_first = client.get("/orders/ORD-123")
    assert response_first.status_code == 200

    payload_first = response_first.json()
    assert payload_first["order_id"] == "ORD-123"
    assert payload_first["cached"] is False

    response_second = client.get("/orders/ORD-123")
    assert response_second.status_code == 200

    payload_second = response_second.json()
    assert payload_second["order_id"] == "ORD-123"
    assert payload_second["cached"] is True


def test_health_endpoint_returns_manager_status(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert "status" in payload
    assert "healthy" in payload
    assert "checks" in payload
    assert "database" in payload["checks"]
    assert "cache" in payload["checks"]
    assert "http" in payload["checks"]
