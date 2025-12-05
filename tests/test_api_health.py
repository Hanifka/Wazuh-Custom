from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Health check should work without auth."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]
    assert "database_connected" in data
    assert isinstance(data["database_connected"], bool)
    assert "timestamp" in data
    # Verify timestamp is valid ISO format
    datetime.fromisoformat(data["timestamp"])


def test_health_check_db_connected(client: TestClient):
    """Health check should report database connected."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # With the test client and in-memory DB, should be connected
    assert data["database_connected"] is True
    assert data["status"] == "healthy"


@pytest.fixture
def auth():
    """Default test authentication tuple."""
    return ("testuser", "testpass")


def test_settings_response_structure(client: TestClient, auth):
    """Settings endpoint should return proper structure."""
    response = client.get("/api/v1/settings", auth=auth)
    assert response.status_code == 200
    data = response.json()

    assert "sigma_multiplier" in data
    assert isinstance(data["sigma_multiplier"], float)
    assert data["sigma_multiplier"] > 0

    assert "baseline_window_days" in data
    assert isinstance(data["baseline_window_days"], int)
    assert data["baseline_window_days"] > 0

    assert "last_analyzer_run_at" in data
    # Can be None initially
    if data["last_analyzer_run_at"] is not None:
        datetime.fromisoformat(data["last_analyzer_run_at"])


def test_settings_default_values(client: TestClient, auth):
    """Settings should return default values."""
    response = client.get("/api/v1/settings", auth=auth)
    assert response.status_code == 200
    data = response.json()

    # Default values from env.py
    assert data["sigma_multiplier"] == 3.0
    assert data["baseline_window_days"] == 30
    assert data["last_analyzer_run_at"] is None


def test_settings_with_risk_history(client: TestClient, sample_risk_history, auth):
    """Settings should return last analyzer run time when history exists."""
    response = client.get("/api/v1/settings", auth=auth)
    assert response.status_code == 200
    data = response.json()

    # Should have a last_analyzer_run_at timestamp
    assert data["last_analyzer_run_at"] is not None
    datetime.fromisoformat(data["last_analyzer_run_at"])
