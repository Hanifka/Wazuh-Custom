from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_check_no_auth(client: TestClient):
    """Health check endpoint should not require authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "database_connected" in data
    assert "timestamp" in data


def test_entities_requires_auth(client: TestClient):
    """Entities endpoint should require authentication."""
    response = client.get("/api/v1/entities")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_entities_with_wrong_password(client: TestClient):
    """Should reject wrong password."""
    response = client.get("/api/v1/entities", auth=("testuser", "wrongpass"))
    assert response.status_code == 401


def test_entities_with_wrong_username(client: TestClient):
    """Should reject wrong username."""
    response = client.get("/api/v1/entities", auth=("wronguser", "testpass"))
    assert response.status_code == 401


def test_entities_with_correct_auth(client: TestClient, sample_entities):
    """Should accept correct credentials."""
    response = client.get("/api/v1/entities", auth=("testuser", "testpass"))
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total_count" in data
    assert "page" in data
    assert "page_size" in data


def test_history_requires_auth(client: TestClient, sample_entities):
    """History endpoint should require authentication."""
    entity_id = sample_entities["user1"].id
    response = client.get(f"/api/v1/entities/{entity_id}/history")
    assert response.status_code == 401


def test_events_requires_auth(client: TestClient, sample_entities):
    """Events endpoint should require authentication."""
    entity_id = sample_entities["user1"].id
    response = client.get(f"/api/v1/entities/{entity_id}/events")
    assert response.status_code == 401


def test_settings_requires_auth(client: TestClient):
    """Settings endpoint should require authentication."""
    response = client.get("/api/v1/settings")
    assert response.status_code == 401


def test_settings_with_correct_auth(client: TestClient):
    """Settings endpoint should work with correct auth."""
    response = client.get("/api/v1/settings", auth=("testuser", "testpass"))
    assert response.status_code == 200
    data = response.json()
    assert "sigma_multiplier" in data
    assert "baseline_window_days" in data
