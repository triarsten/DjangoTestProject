import pytest


@pytest.mark.django_db
def test_health_ok(client, db):
    response = client.get("/health/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"]["status"] == "ok"


@pytest.mark.django_db
def test_health_response_time_present(client, db):
    response = client.get("/health/")

    data = response.json()
    assert "response_time_ms" in data["checks"]["database"]
    assert data["checks"]["database"]["response_time_ms"] >= 0


def test_health_content_type(client):
    response = client.get("/health/")

    assert "application/json" in response.headers["Content-Type"]
