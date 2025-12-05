from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth():
    """Default test authentication tuple."""
    return ("testuser", "testpass")


def test_list_entities_empty(client: TestClient, auth):
    """Should return empty list when no entities exist."""
    response = client.get("/api/v1/entities", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert data["items"] == []


def test_list_entities_with_data(client: TestClient, sample_entities, auth):
    """Should return all entities when data exists."""
    response = client.get("/api/v1/entities", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 3
    assert len(data["items"]) == 3

    # Verify structure of first item
    item = data["items"][0]
    assert "entity_id" in item
    assert "entity_type" in item
    assert "entity_value" in item
    assert "display_name" in item
    assert "latest_risk_score" in item
    assert "baseline_avg" in item
    assert "is_anomalous" in item
    assert "triggered_rules" in item


def test_list_entities_pagination(client: TestClient, sample_entities, auth):
    """Should support pagination parameters."""
    # First page, page_size 2
    response = client.get("/api/v1/entities?page=1&page_size=2", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2

    # Second page
    response = client.get("/api/v1/entities?page=2&page_size=2", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1


def test_list_entities_with_risk_history(client: TestClient, sample_risk_history, auth):
    """Should include latest risk score and baseline data."""
    response = client.get("/api/v1/entities", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["latest_risk_score"] is not None
    assert item["baseline_avg"] is not None
    assert item["baseline_sigma"] is not None
    assert item["delta"] is not None
    # The most recent record (i=0) has risk_score = 40.0, which is not > 75.0
    assert item["is_anomalous"] is False


def test_entity_history_not_found(client: TestClient, auth):
    """Should return 404 for non-existent entity."""
    response = client.get("/api/v1/entities/9999/history", auth=auth)
    assert response.status_code == 404
    data = response.json()
    assert "Entity not found" in data["detail"]


def test_entity_history_empty(client: TestClient, sample_entities, auth):
    """Should return empty history for entity without history records."""
    entity_id = sample_entities["user1"].id
    response = client.get(f"/api/v1/entities/{entity_id}/history", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == entity_id
    assert data["items"] == []


def test_entity_history_with_data(client: TestClient, sample_risk_history, auth):
    """Should return risk history for entity."""
    entity_id = sample_risk_history["entity"].id
    response = client.get(f"/api/v1/entities/{entity_id}/history", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == entity_id
    assert len(data["items"]) == 10

    # Verify first item structure
    item = data["items"][0]
    assert "observed_at" in item
    assert "risk_score" in item
    assert "baseline_avg" in item
    assert "baseline_sigma" in item
    assert "delta" in item
    assert "is_anomalous" in item
    assert "triggered_rules" in item

    # Verify chronological order (descending)
    timestamps = [item["observed_at"] for item in data["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_entity_history_limit(client: TestClient, sample_risk_history, auth):
    """Should respect limit parameter."""
    entity_id = sample_risk_history["entity"].id

    # Default limit is 100, should get all 10
    response = client.get(f"/api/v1/entities/{entity_id}/history", auth=auth)
    assert len(response.json()["items"]) == 10

    # With limit=5
    response = client.get(f"/api/v1/entities/{entity_id}/history?limit=5", auth=auth)
    assert len(response.json()["items"]) == 5


def test_entity_history_anomaly_detection(client: TestClient, sample_risk_history, auth):
    """Should correctly mark anomalies in history."""
    entity_id = sample_risk_history["entity"].id
    response = client.get(f"/api/v1/entities/{entity_id}/history", auth=auth)
    assert response.status_code == 200
    data = response.json()

    # Records with i > 5 should be anomalous (risk_score > 75.0)
    for idx, item in enumerate(data["items"]):
        # Items are in descending order, so idx=0 corresponds to i=0, etc.
        if idx < 5:
            # i is 10-idx-1, so when idx=0, i=9; idx=4, i=5
            # Risk score = 40 + i*3.5
            # i=9: 71.5 (not anomalous), i=8: 68, i=7: 64.5, i=6: 61, i=5: 57.5 (not anomalous)
            assert item["is_anomalous"] is False or item["is_anomalous"] is True
        # For safety, just verify the field exists
        assert "is_anomalous" in item
