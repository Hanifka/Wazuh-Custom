from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ueba.db.base import Base
from ueba.db.models import Entity, EntityRiskHistory, NormalizedEvent
from ueba.services.analyzer.service import AnalyzerService


@pytest.fixture()
def session_factory(tmp_path: Path):
    db_path = tmp_path / "analyzer_service.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    try:
        yield SessionFactory
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def analyzer_service(session_factory):
    return AnalyzerService(session_factory=session_factory)


def _create_entity(session, entity_type: str, value: str) -> Entity:
    entity = Entity(entity_type=entity_type, entity_value=value)
    session.add(entity)
    session.commit()
    return entity


def _add_event(session, entity_id: int, ts: datetime, event_type: str, severity: int) -> None:
    session.add(
        NormalizedEvent(
            entity_id=entity_id,
            event_type=event_type,
            observed_at=ts,
            normalized_payload={"severity": severity},
        )
    )


def _collect_history(session):
    return session.execute(select(EntityRiskHistory).order_by(EntityRiskHistory.id)).scalars().all()


def test_analyzer_service_rolls_up_events(session_factory, analyzer_service):
    base_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

    with session_factory() as session:
        host = _create_entity(session, "host", "web-1")
        user = _create_entity(session, "user", "alice")

        # Host events spanning two days
        _add_event(session, host.id, base_time, "wazuh_auth", 5)
        _add_event(session, host.id, base_time + timedelta(hours=4), "wazuh_auth", 9)
        _add_event(session, host.id, base_time + timedelta(days=1, hours=1), "wazuh_dns", 3)

        # User events single day
        _add_event(session, user.id, base_time + timedelta(hours=2), "login", 7)
        _add_event(session, user.id, base_time + timedelta(hours=3), "login", 4)
        session.commit()

    processed = analyzer_service.run_once(
        since=base_time,
        until=base_time + timedelta(days=3),
    )

    assert processed == 3  # host day1 + host day2 + user day1

    with session_factory() as session:
        history_rows = _collect_history(session)
        assert len(history_rows) == 3

        first = history_rows[0]
        payload = json.loads(first.reason)
        assert payload["event_count"] == 2
        assert payload["highest_severity"] == 9
        assert payload["generator"] == "analyzer_service"
        assert payload["kind"] == "daily_rollup"
        assert json.loads(history_rows[1].reason)["event_count"] == 1


def test_analyzer_service_is_idempotent(session_factory, analyzer_service):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    with session_factory() as session:
        entity = _create_entity(session, "user", "alice")
        for hour in range(3):
            _add_event(session, entity.id, base_time + timedelta(hours=hour), "login", 6 + hour)
        session.commit()

    processed_first = analyzer_service.run_once(
        since=base_time,
        until=base_time + timedelta(days=1),
    )
    assert processed_first == 1

    # Second run should update, not insert new rows
    processed_second = analyzer_service.run_once(
        since=base_time,
        until=base_time + timedelta(days=1),
    )
    assert processed_second == 1

    with session_factory() as session:
        history_rows = _collect_history(session)
        assert len(history_rows) == 1
        payload = json.loads(history_rows[0].reason)
        assert payload["event_count"] == 3
        assert payload["highest_severity"] == 8


def test_analyzer_service_uses_checkpoint(session_factory, analyzer_service):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    with session_factory() as session:
        entity = _create_entity(session, "host", "web-1")
        # Day 1 events
        _add_event(session, entity.id, base_time + timedelta(hours=1), "auth", 5)
        session.commit()

    # First run processes day 1
    analyzer_service.run_once(
        since=base_time,
        until=base_time + timedelta(days=2),
    )

    with session_factory() as session:
        # Day 2 events
        for hour in range(2):
            _add_event(session, entity.id, base_time + timedelta(days=1, hours=hour), "dns", 4 + hour)
        session.commit()

    # Second run without since should pick up from checkpoint (day 2 only)
    processed = analyzer_service.run_once(until=base_time + timedelta(days=3))
    assert processed == 1

    with session_factory() as session:
        history_rows = _collect_history(session)
        assert len(history_rows) == 2
        # Verify most recent record corresponds to day 2 window end
        latest = history_rows[-1]
        payload = json.loads(latest.reason)
        assert payload["event_count"] == 2
        assert payload["highest_severity"] == 5
