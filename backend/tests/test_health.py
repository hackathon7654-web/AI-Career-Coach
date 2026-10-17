from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_health_endpoint_success(client):
    """Verify that GET /api/health returns HTTP 200 and matches the documented schema."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["application"] == "ProofPath AI API"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"

    # Verify timestamp is valid ISO format
    assert "timestamp" in data
    ts = datetime.fromisoformat(data["timestamp"])
    assert ts is not None

    # Verify status honesty: database and LLM are reported as not_configured
    assert data["database"] == "not_configured"
    assert data["llm"] == "not_configured"


def test_app_starts_without_external_credentials(client):
    """Verify that the application boots without any Supabase, GitHub, or LLM credentials."""
    assert settings.SUPABASE_URL is None or settings.SUPABASE_URL == ""
    assert settings.GITHUB_TOKEN is None or settings.GITHUB_TOKEN == ""
    assert settings.LLM_API_KEY is None or settings.LLM_API_KEY == ""

    # Ensure endpoints function without external dependencies
    response = client.get("/api/health")
    assert response.status_code == 200


def test_openapi_docs_accessible(client):
    """Verify that /docs and /openapi.json are accessible in development."""
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    schema = openapi_response.json()
    assert schema["info"]["title"] == "ProofPath AI API"


def test_cors_allowed_origin(client):
    """Verify that requests from the allowed frontend origin receive proper CORS headers."""
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_disallowed_origin(client):
    """Verify that requests from an unauthorized origin are not granted CORS access."""
    response = client.get(
        "/api/health",
        headers={"Origin": "http://unauthorized-domain.com"},
    )
    assert response.status_code == 200
    # Disallowed origin should NOT be echoed back
    assert response.headers.get("access-control-allow-origin") is None
