from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ueba.db.base import Base
from ueba.db.models import Entity, EntityRiskHistory, NormalizedEvent
from ueba.services.analyzer import AnalyzerRepository
from ueba.services.analyzer.pipeline import AnalyzerResult, ExtractedFeatures, RuleEvaluation


@pytest.fixture
def session_factory(tmp_path: Path):
    db_path = tmp_path / "test_analyzer.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    try:
        yield SessionFactory
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_entity(session_factory):
    with session_factory() as session:
        entity = Entity(entity_type="user", entity_value="alice")
        session.add(entity)
        session.commit()
        return entity.id


def test_fetch_entity_event_windows_groups_by_entity_and_day(session_factory, sample_entity):
    with session_factory() as session:
        # Create events over two days for one entity
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        for i in range(3):
            event = NormalizedEvent(
                entity_id=sample_entity,
                event_type="login",
                observed_at=base_time + timedelta(hours=i),
            )
            session.add(event)

        # Next day
        next_day = base_time + timedelta(days=1)
        for i in range(2):
            event = NormalizedEvent(
                entity_id=sample_entity,
                event_type="file_access",
                observed_at=next_day + timedelta(hours=i),
            )
            session.add(event)

        session.commit()

        repo = AnalyzerRepository(session)
        windows = repo.fetch_entity_event_windows()

        assert len(windows) == 2
        assert windows[0].entity_id == sample_entity
        assert len(windows[0].events) == 3
        assert len(windows[1].events) == 2
        assert windows[0].window_start.date() == base_time.date()
        assert windows[1].window_start.date() == next_day.date()


def test_fetch_entity_event_windows_filters_by_time(session_factory, sample_entity):
    with session_factory() as session:
        base_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Events before, during, and after the window
        session.add(
            NormalizedEvent(
                entity_id=sample_entity,
                event_type="before",
                observed_at=base_time - timedelta(days=1),
            )
        )
        session.add(
            NormalizedEvent(
                entity_id=sample_entity,
                event_type="during",
                observed_at=base_time,
            )
        )
        session.add(
            NormalizedEvent(
                entity_id=sample_entity,
                event_type="after",
                observed_at=base_time + timedelta(days=2),
            )
        )
        session.commit()

        repo = AnalyzerRepository(session)
        windows = repo.fetch_entity_event_windows(
            since=base_time,
            until=base_time + timedelta(days=1),
        )

        assert len(windows) == 1
        assert len(windows[0].events) == 1
        assert windows[0].events[0].event_type == "during"


def test_fetch_entity_event_windows_ignores_deleted_and_inactive(session_factory, sample_entity):
    with session_factory() as session:
        base_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Active event
        session.add(
            NormalizedEvent(
                entity_id=sample_entity,
                event_type="active",
                observed_at=base_time,
                status="active",
            )
        )

        # Deleted event
        session.add(
            NormalizedEvent(
                entity_id=sample_entity,
                event_type="deleted",
                observed_at=base_time,
                status="active",
                deleted_at=base_time,
            )
        )

        # Inactive event
        session.add(
            NormalizedEvent(
                entity_id=sample_entity,
                event_type="inactive",
                observed_at=base_time,
                status="inactive",
            )
        )

        session.commit()

        repo = AnalyzerRepository(session)
        windows = repo.fetch_entity_event_windows()

        assert len(windows) == 1
        assert len(windows[0].events) == 1
        assert windows[0].events[0].event_type == "active"


def test_persist_result_creates_new_history(session_factory, sample_entity):
    with session_factory() as session:
        base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        result = AnalyzerResult(
            entity_id=sample_entity,
            window_start=base_time,
            window_end=base_time + timedelta(days=1),
            features=ExtractedFeatures(
                event_count=5,
                highest_severity=8,
                last_observed_at=base_time + timedelta(hours=12),
                event_types=["login", "file_access"],
            ),
            rule_evaluation=RuleEvaluation(
                triggered_rules=["high_severity_detected"],
                metadata={"highest_severity": 8},
            ),
            risk_score=45.0,
        )

        repo = AnalyzerRepository(session)
        history = repo.persist_result(result)
        session.commit()

        assert history.entity_id == sample_entity
        assert history.risk_score == 45.0
        assert history.observed_at == base_time + timedelta(days=1)
        assert "event_count" in history.reason
        assert "highest_severity" in history.reason


def test_persist_result_updates_existing_history(session_factory, sample_entity):
    with session_factory() as session:
        base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        # Create initial history
        initial_result = AnalyzerResult(
            entity_id=sample_entity,
            window_start=base_time,
            window_end=base_time + timedelta(days=1),
            features=ExtractedFeatures(
                event_count=3,
                highest_severity=5,
                last_observed_at=base_time + timedelta(hours=6),
                event_types=["login"],
            ),
            rule_evaluation=RuleEvaluation(),
            risk_score=20.0,
        )

        repo = AnalyzerRepository(session)
        repo.persist_result(initial_result)
        session.commit()

        # Update with new result
        updated_result = AnalyzerResult(
            entity_id=sample_entity,
            window_start=base_time,
            window_end=base_time + timedelta(days=1),
            features=ExtractedFeatures(
                event_count=5,
                highest_severity=8,
                last_observed_at=base_time + timedelta(hours=12),
                event_types=["login", "file_access"],
            ),
            rule_evaluation=RuleEvaluation(triggered_rules=["high_severity_detected"]),
            risk_score=45.0,
        )

        repo.persist_result(updated_result)
        session.commit()

        # Should only have one record
        histories = session.execute(select(EntityRiskHistory)).scalars().all()
        assert len(histories) == 1
        assert histories[0].risk_score == 45.0


def test_get_latest_checkpoint_returns_none_when_empty(session_factory):
    with session_factory() as session:
        repo = AnalyzerRepository(session)
        checkpoint = repo.get_latest_checkpoint()
        assert checkpoint is None


def test_get_latest_checkpoint_returns_max_observed_at(session_factory, sample_entity):
    with session_factory() as session:
        base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        for i in range(3):
            result = AnalyzerResult(
                entity_id=sample_entity,
                window_start=base_time + timedelta(days=i),
                window_end=base_time + timedelta(days=i + 1),
                features=ExtractedFeatures(
                    event_count=1,
                    highest_severity=None,
                    last_observed_at=base_time + timedelta(days=i),
                    event_types=["test"],
                ),
                rule_evaluation=RuleEvaluation(),
                risk_score=10.0,
            )
            repo = AnalyzerRepository(session)
            repo.persist_result(result)

        session.commit()

        checkpoint = repo.get_latest_checkpoint()
        assert checkpoint is not None
        assert checkpoint == base_time + timedelta(days=3)
