from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth():
    """Default test authentication tuple."""
    return ("testuser", "testpass")


def test_get_feedback_empty(client: TestClient, sample_entities, auth):
    """Should return empty feedback list for entity without feedback."""
    entity_id = sample_entities["user1"].id
    response = client.get(f"/api/v1/entities/{entity_id}/feedback", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == entity_id
    assert data["items"] == []
    assert data["stats"]["tp_count"] == 0
    assert data["stats"]["fp_count"] == 0
    assert data["stats"]["fp_ratio"] == 0.0


def test_get_feedback_not_found(client: TestClient, auth):
    """Should return 404 for non-existent entity."""
    response = client.get("/api/v1/entities/9999/feedback", auth=auth)
    assert response.status_code == 404
    data = response.json()
    assert "Entity not found" in data["detail"]


def test_post_feedback_tp(client: TestClient, sample_entities, auth):
    """Should allow submitting TP feedback."""
    entity_id = sample_entities["user1"].id
    response = client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={"feedback_type": "tp", "notes": "This is a true positive"},
        auth=auth,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["entity_id"] == entity_id
    assert len(data["items"]) == 1
    assert data["items"][0]["feedback_type"] == "tp"
    assert data["items"][0]["notes"] == "This is a true positive"
    assert data["items"][0]["submitted_by"] == "testuser"
    assert data["stats"]["tp_count"] == 1
    assert data["stats"]["fp_count"] == 0
    assert data["stats"]["fp_ratio"] == 0.0


def test_post_feedback_fp(client: TestClient, sample_entities, auth):
    """Should allow submitting FP feedback."""
    entity_id = sample_entities["user1"].id
    response = client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={"feedback_type": "fp", "notes": "False alarm - user was on vacation"},
        auth=auth,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["entity_id"] == entity_id
    assert len(data["items"]) == 1
    assert data["items"][0]["feedback_type"] == "fp"
    assert data["stats"]["tp_count"] == 0
    assert data["stats"]["fp_count"] == 1
    assert data["stats"]["fp_ratio"] == 1.0


def test_post_feedback_invalid_type(client: TestClient, sample_entities, auth):
    """Should reject invalid feedback_type."""
    entity_id = sample_entities["user1"].id
    response = client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={"feedback_type": "invalid", "notes": "Test"},
        auth=auth,
    )
    assert response.status_code == 422
    data = response.json()
    assert "feedback_type must be 'tp' or 'fp'" in data["detail"]


def test_post_feedback_without_notes(client: TestClient, sample_entities, auth):
    """Should allow feedback without notes."""
    entity_id = sample_entities["user1"].id
    response = client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={"feedback_type": "tp"},
        auth=auth,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["items"][0]["notes"] is None


def test_post_feedback_with_event_id(client: TestClient, sample_events, auth):
    """Should allow feedback with normalized_event_id."""
    entity_id = sample_events["entity"].id
    event_id = sample_events["events"][0].id
    response = client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={
            "feedback_type": "tp",
            "normalized_event_id": event_id,
            "notes": "Confirmed suspicious activity",
        },
        auth=auth,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["items"][0]["normalized_event_id"] == event_id


def test_post_feedback_invalid_event_id(client: TestClient, sample_entities, auth):
    """Should reject feedback with non-existent event_id."""
    entity_id = sample_entities["user1"].id
    response = client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={
            "feedback_type": "tp",
            "normalized_event_id": 9999,
            "notes": "Test",
        },
        auth=auth,
    )
    assert response.status_code == 422
    data = response.json()
    assert "not found" in data["detail"]


def test_post_feedback_entity_not_found(client: TestClient, auth):
    """Should return 404 for non-existent entity."""
    response = client.post(
        "/api/v1/entities/9999/feedback",
        json={"feedback_type": "tp", "notes": "Test"},
        auth=auth,
    )
    assert response.status_code == 404
    data = response.json()
    assert "Entity not found" in data["detail"]


def test_feedback_stats_calculation(client: TestClient, sample_entities, auth):
    """Should correctly calculate TP/FP stats."""
    entity_id = sample_entities["user1"].id

    # Submit 3 TP and 2 FP
    for i in range(3):
        client.post(
            f"/api/v1/entities/{entity_id}/feedback",
            json={"feedback_type": "tp"},
            auth=auth,
        )

    for i in range(2):
        client.post(
            f"/api/v1/entities/{entity_id}/feedback",
            json={"feedback_type": "fp"},
            auth=auth,
        )

    response = client.get(f"/api/v1/entities/{entity_id}/feedback", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["tp_count"] == 3
    assert data["stats"]["fp_count"] == 2
    assert abs(data["stats"]["fp_ratio"] - 0.4) < 0.001


def test_feedback_history_order(client: TestClient, sample_entities, auth):
    """Should return feedback in reverse chronological order."""
    entity_id = sample_entities["user1"].id

    # Submit multiple feedback items
    for i in range(3):
        client.post(
            f"/api/v1/entities/{entity_id}/feedback",
            json={"feedback_type": "tp", "notes": f"Feedback {i}"},
            auth=auth,
        )

    response = client.get(f"/api/v1/entities/{entity_id}/feedback", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3

    # Verify reverse chronological order
    timestamps = [item["submitted_at"] for item in data["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_feedback_limit_parameter(client: TestClient, sample_entities, auth):
    """Should respect limit parameter in GET feedback."""
    entity_id = sample_entities["user1"].id

    # Submit 10 feedback items
    for i in range(10):
        client.post(
            f"/api/v1/entities/{entity_id}/feedback",
            json={"feedback_type": "tp"},
            auth=auth,
        )

    # Test default limit (100, so should return all 10)
    response = client.get(f"/api/v1/entities/{entity_id}/feedback", auth=auth)
    assert len(response.json()["items"]) == 10

    # Test custom limit
    response = client.get(f"/api/v1/entities/{entity_id}/feedback?limit=5", auth=auth)
    assert len(response.json()["items"]) == 5


def test_feedback_auth_required(client: TestClient, sample_entities):
    """Should require authentication to access feedback endpoints."""
    entity_id = sample_entities["user1"].id

    # GET without auth
    response = client.get(f"/api/v1/entities/{entity_id}/feedback")
    assert response.status_code == 403

    # POST without auth
    response = client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={"feedback_type": "tp"},
    )
    assert response.status_code == 403


def test_feedback_auth_invalid_credentials(client: TestClient, sample_entities):
    """Should reject invalid credentials."""
    entity_id = sample_entities["user1"].id
    bad_auth = ("wronguser", "wrongpass")

    response = client.get(f"/api/v1/entities/{entity_id}/feedback", auth=bad_auth)
    assert response.status_code == 401


def test_list_entities_includes_feedback_stats(client: TestClient, sample_entities, auth):
    """Should include TP/FP stats in entities list."""
    entity_id = sample_entities["user1"].id

    # Submit some feedback
    client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={"feedback_type": "tp"},
        auth=auth,
    )
    client.post(
        f"/api/v1/entities/{entity_id}/feedback",
        json={"feedback_type": "fp"},
        auth=auth,
    )

    response = client.get("/api/v1/entities", auth=auth)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0

    entity_item = next((item for item in data["items"] if item["entity_id"] == entity_id), None)
    assert entity_item is not None
    assert entity_item["tp_count"] == 1
    assert entity_item["fp_count"] == 1
    assert abs(entity_item["fp_ratio"] - 0.5) < 0.001
