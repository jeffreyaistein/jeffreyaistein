"""
Jeffrey AIstein - Health Endpoint Tests
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health(client):
    """Test basic health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready(client):
    """Test readiness endpoint."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data
    assert "checks" in data


def test_health_live(client):
    """Test liveness endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"live": True}


def test_api_info(client):
    """Test API info endpoint."""
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Jeffrey AIstein"
    assert "version" in data


def test_token_metrics_placeholder(client):
    """Test token metrics placeholder."""
    response = client.get("/api/token/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "market_cap" in data
    assert "meter_max" in data


def test_agent_stats_placeholder(client):
    """Test agent stats placeholder."""
    response = client.get("/api/stats/agent")
    assert response.status_code == 200
    data = response.json()
    assert "messages_processed" in data
    assert "learning_score" in data
