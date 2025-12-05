from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth():
    """Default test authentication tuple."""
    return ("testuser", "testpass")


def test_entity_events_not_found(client: TestClient, auth):
    """Should return 404 for non-existent entity."""
    response = client.get("/api/v1/entities/9999/events", auth=auth)
    assert response.status_code == 404
    data = response.json()
    assert "Entity not found" in data["detail"]


def test_entity_events_empty(client: TestClient, sample_entities, auth):
    """Should return empty events for entity without events."""
    entity_id = sample_entities["user1"].id
    response = client.get(f"/api/v1/entities/{entity_id}/events", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == entity_id
    assert data["total_count"] == 0
    assert data["items"] == []


def test_entity_events_with_data(client: TestClient, sample_events, auth):
    """Should return events for entity."""
    entity_id = sample_events["entity"].id
    response = client.get(f"/api/v1/entities/{entity_id}/events", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == entity_id
    assert data["total_count"] == 10
    assert len(data["items"]) == 10

    # Verify first item structure
    item = data["items"][0]
    assert "event_id" in item
    assert "event_type" in item
    assert "observed_at" in item
    assert "risk_score" in item
    assert "summary" in item
    assert "normalized_payload" in item

    # Verify chronological order (descending by observed_at)
    timestamps = [item["observed_at"] for item in data["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_entity_events_limit(client: TestClient, sample_events, auth):
    """Should respect limit parameter."""
    entity_id = sample_events["entity"].id

    # Default limit is 100, should get all 10
    response = client.get(f"/api/v1/entities/{entity_id}/events", auth=auth)
    assert len(response.json()["items"]) == 10

    # With limit=5
    response = client.get(f"/api/v1/entities/{entity_id}/events?limit=5", auth=auth)
    assert len(response.json()["items"]) == 5

    # With limit=1
    response = client.get(f"/api/v1/entities/{entity_id}/events?limit=1", auth=auth)
    assert len(response.json()["items"]) == 1


def test_entity_events_payload_includes_data(client: TestClient, sample_events, auth):
    """Should include normalized payload data in response."""
    entity_id = sample_events["entity"].id
    response = client.get(f"/api/v1/entities/{entity_id}/events", auth=auth)
    assert response.status_code == 200
    data = response.json()

    # Verify payloads are included
    for item in data["items"]:
        assert item["normalized_payload"] is not None
        assert "severity" in item["normalized_payload"]


def test_entity_events_event_types_varied(client: TestClient, sample_events, auth):
    """Should include different event types."""
    entity_id = sample_events["entity"].id
    response = client.get(f"/api/v1/entities/{entity_id}/events", auth=auth)
    assert response.status_code == 200
    data = response.json()

    event_types = {item["event_type"] for item in data["items"]}
    assert "suspicious_login" in event_types
    assert "file_access" in event_types
