from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ueba.api.dependencies import get_session
from ueba.api.main import app
from ueba.db.base import Base
from ueba.db.models import Entity, NormalizedEvent, EntityRiskHistory


UTC = timezone.utc


@pytest.fixture()
def session_factory(tmp_path: Path):
    """Create an in-memory SQLite database session factory for tests."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    try:
        yield SessionFactory
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def session(session_factory):
    """Create a session instance."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory, monkeypatch: pytest.MonkeyPatch):
    """Create a FastAPI test client with test database."""
    # Override session dependency
    def override_get_session() -> Generator:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session

    # Set test credentials
    monkeypatch.setenv("UEBA_DASH_USERNAME", "testuser")
    monkeypatch.setenv("UEBA_DASH_PASSWORD", "testpass")

    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_entities(session) -> dict:
    """Create sample entities for testing."""
    entities = {
        "user1": Entity(entity_type="user", entity_value="user@example.com", display_name="Test User"),
        "host1": Entity(entity_type="host", entity_value="host1.internal", display_name="Host 1"),
        "host2": Entity(entity_type="host", entity_value="host2.internal"),
    }
    for entity in entities.values():
        session.add(entity)
    session.commit()
    return entities


@pytest.fixture()
def sample_events(session, sample_entities) -> dict:
    """Create sample normalized events for testing."""
    now = datetime.now(UTC)
    events = []
    user1 = sample_entities["user1"]

    # Create events for the last 10 days
    for i in range(10):
        ts = now - timedelta(days=i)
        event = NormalizedEvent(
            entity_id=user1.id,
            event_type="suspicious_login" if i % 2 == 0 else "file_access",
            observed_at=ts,
            risk_score=50.0 + i * 5,
            summary=f"Event {i}",
            normalized_payload={"severity": 5 + i},
        )
        session.add(event)
        events.append(event)

    session.commit()
    return {"events": events, "entity": user1}


@pytest.fixture()
def sample_risk_history(session, sample_entities) -> dict:
    """Create sample risk history for testing."""
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    user1 = sample_entities["user1"]

    # Create daily risk history for last 10 days
    records = []
    for i in range(10):
        obs_time = now - timedelta(days=i)
        risk_score = 40.0 + i * 3.5

        reason_dict = {
            "generator": "analyzer_service",
            "kind": "daily_rollup",
            "window_start": (obs_time - timedelta(days=1)).isoformat(),
            "window_end": obs_time.isoformat(),
            "event_count": 5 + i,
            "highest_severity": 7 + i,
            "last_observed_at": (obs_time - timedelta(hours=6)).isoformat(),
            "rules": {
                "triggered": ["high_event_volume"] if i > 5 else [],
                "metadata": {},
            },
            "baseline": {
                "avg": 45.0,
                "sigma": 10.0,
                "delta": risk_score - 45.0,
                "is_anomalous": risk_score > 75.0,
            },
        }

        history = EntityRiskHistory(
            entity_id=user1.id,
            risk_score=risk_score,
            observed_at=obs_time,
            reason=json.dumps(reason_dict),
        )
        session.add(history)
        records.append(history)

    session.commit()
    return {"records": records, "entity": user1}
