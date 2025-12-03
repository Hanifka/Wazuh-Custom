from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ueba.db.base import Base
from ueba.db.models import Entity, EntityRiskHistory, NormalizedEvent
from ueba.logging import AlertLogger
from ueba.services.analyzer.service import AnalyzerService


@pytest.fixture()
def session_factory(tmp_path: Path):
    db_path = tmp_path / "analyzer_baseline.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    try:
        yield SessionFactory
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def alert_log_path(tmp_path: Path):
    return tmp_path / "alerts.log"


@pytest.fixture()
def analyzer_service(session_factory, alert_log_path):
    alert_logger = AlertLogger(alert_log_path)
    return AnalyzerService(session_factory=session_factory, alert_logger=alert_logger)


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


def _add_history(session, entity_id: int, observed_at: datetime, risk_score: float) -> None:
    history = EntityRiskHistory(
        entity_id=entity_id,
        risk_score=risk_score,
        observed_at=observed_at,
        reason='{"generator": "analyzer_service"}',
    )
    session.add(history)


def test_analyzer_service_enriches_results_with_baseline(session_factory, analyzer_service):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        entity = _create_entity(session, "user", "alice")
        
        # Create baseline history (30 days)
        for day in range(30):
            _add_history(session, entity.id, base_time + timedelta(days=day), 30.0)
        
        # Add new events for processing
        _add_event(session, entity.id, base_time + timedelta(days=31, hours=1), "login", 5)
        session.commit()
    
    analyzer_service.run_once(
        since=base_time + timedelta(days=31),
        until=base_time + timedelta(days=32),
    )
    
    with session_factory() as session:
        history = (
            session.query(EntityRiskHistory)
            .filter(EntityRiskHistory.entity_id == entity.id)
            .order_by(EntityRiskHistory.observed_at.desc())
            .first()
        )
        
        reason = json.loads(history.reason)
        assert "baseline" in reason
        assert reason["baseline"]["avg"] is not None
        assert reason["baseline"]["sigma"] is not None
        assert reason["baseline"]["delta"] is not None
        assert reason["baseline"]["is_anomalous"] is not None


def test_analyzer_service_logs_anomalies(session_factory, analyzer_service, alert_log_path):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        entity = _create_entity(session, "user", "bob")
        
        # Create stable baseline (avg=20, low sigma)
        for day in range(30):
            _add_history(session, entity.id, base_time + timedelta(days=day), 20.0)
        
        # Add events that will trigger high risk score (anomaly)
        for i in range(15):
            _add_event(
                session,
                entity.id,
                base_time + timedelta(days=31, hours=i),
                "suspicious_activity",
                severity=9,
            )
        session.commit()
    
    analyzer_service.run_once(
        since=base_time + timedelta(days=31),
        until=base_time + timedelta(days=32),
    )
    
    # Verify alert was logged
    assert alert_log_path.exists()
    
    lines = alert_log_path.read_text().strip().split("\n")
    assert len(lines) >= 1
    
    alert = json.loads(lines[0])
    assert alert["entity_id"] == entity.id
    assert alert["risk_score"] > alert["baseline_avg"]
    assert alert["delta"] > 0
    assert "triggered_rules" in alert


def test_analyzer_service_does_not_log_normal_behavior(
    session_factory, analyzer_service, alert_log_path
):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        entity = _create_entity(session, "user", "charlie")
        
        # Create baseline
        for day in range(30):
            _add_history(session, entity.id, base_time + timedelta(days=day), 30.0)
        
        # Add normal events (should not trigger anomaly)
        _add_event(session, entity.id, base_time + timedelta(days=31, hours=1), "login", 5)
        _add_event(session, entity.id, base_time + timedelta(days=31, hours=2), "logout", 3)
        session.commit()
    
    analyzer_service.run_once(
        since=base_time + timedelta(days=31),
        until=base_time + timedelta(days=32),
    )
    
    # Verify no alert was logged
    if alert_log_path.exists():
        content = alert_log_path.read_text().strip()
        assert content == ""


def test_analyzer_service_handles_no_baseline(session_factory, analyzer_service):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        entity = _create_entity(session, "user", "dave")
        
        # No baseline history, just new events
        _add_event(session, entity.id, base_time + timedelta(hours=1), "login", 5)
        session.commit()
    
    # Should not crash when no baseline exists
    processed = analyzer_service.run_once(
        since=base_time,
        until=base_time + timedelta(days=1),
    )
    
    assert processed == 1
    
    with session_factory() as session:
        history = (
            session.query(EntityRiskHistory)
            .filter(EntityRiskHistory.entity_id == entity.id)
            .first()
        )
        
        reason = json.loads(history.reason)
        assert "baseline" in reason
        # When no history, baseline should be 0/0
        assert reason["baseline"]["avg"] == 0.0
        assert reason["baseline"]["sigma"] == 0.0


def test_analyzer_service_baseline_per_entity(session_factory, analyzer_service, alert_log_path):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        entity1 = _create_entity(session, "user", "eve")
        entity2 = _create_entity(session, "user", "frank")
        
        # Different baselines per entity
        for day in range(30):
            _add_history(session, entity1.id, base_time + timedelta(days=day), 20.0)
            _add_history(session, entity2.id, base_time + timedelta(days=day), 80.0)
        
        # Both get similar events, but different scores relative to baseline
        _add_event(session, entity1.id, base_time + timedelta(days=31, hours=1), "login", 5)
        _add_event(session, entity2.id, base_time + timedelta(days=31, hours=1), "login", 5)
        session.commit()
    
    analyzer_service.run_once(
        since=base_time + timedelta(days=31),
        until=base_time + timedelta(days=32),
    )
    
    with session_factory() as session:
        history1 = (
            session.query(EntityRiskHistory)
            .filter(EntityRiskHistory.entity_id == entity1.id)
            .order_by(EntityRiskHistory.observed_at.desc())
            .first()
        )
        
        history2 = (
            session.query(EntityRiskHistory)
            .filter(EntityRiskHistory.entity_id == entity2.id)
            .order_by(EntityRiskHistory.observed_at.desc())
            .first()
        )
        
        reason1 = json.loads(history1.reason)
        reason2 = json.loads(history2.reason)
        
        # Each entity should have its own baseline
        assert reason1["baseline"]["avg"] == pytest.approx(20.0)
        assert reason2["baseline"]["avg"] == pytest.approx(80.0)


def test_analyzer_service_caches_baseline_across_windows(session_factory, analyzer_service):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        entity = _create_entity(session, "user", "grace")
        
        # Create baseline
        for day in range(30):
            _add_history(session, entity.id, base_time + timedelta(days=day), 30.0)
        
        # Multiple days of new events
        for day in range(31, 35):
            _add_event(session, entity.id, base_time + timedelta(days=day, hours=1), "login", 5)
        session.commit()
    
    # Process multiple windows in one run
    processed = analyzer_service.run_once(
        since=base_time + timedelta(days=31),
        until=base_time + timedelta(days=35),
    )
    
    # Baseline should be cached and reused for same entity
    assert processed == 4
