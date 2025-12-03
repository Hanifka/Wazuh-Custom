from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ueba.db.base import Base
from ueba.db.models import Entity, EntityRiskHistory
from ueba.services.analyzer.baseline import BaselineCalculator, BaselineStats


@pytest.fixture
def session_factory(tmp_path: Path):
    db_path = tmp_path / "test_baseline.db"
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


def _add_history(session, entity_id: int, observed_at: datetime, risk_score: float):
    history = EntityRiskHistory(
        entity_id=entity_id,
        risk_score=risk_score,
        observed_at=observed_at,
        reason='{"generator": "test"}',
    )
    session.add(history)


def test_baseline_calculator_returns_zero_when_no_history(session_factory, sample_entity):
    with session_factory() as session:
        calc = BaselineCalculator(session)
        baseline = calc.get_baseline(sample_entity, datetime.now(timezone.utc))
        
        assert baseline.avg == 0.0
        assert baseline.sigma == 0.0


def test_baseline_calculator_computes_avg_and_sigma(session_factory, sample_entity):
    base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        for day in range(10):
            _add_history(
                session,
                sample_entity,
                base_time + timedelta(days=day),
                risk_score=20.0 + day * 5,
            )
        session.commit()
        
        calc = BaselineCalculator(session, window_days=30)
        until = base_time + timedelta(days=11)
        baseline = calc.get_baseline(sample_entity, until)
        
        # avg: (20 + 25 + 30 + 35 + 40 + 45 + 50 + 55 + 60 + 65) / 10 = 42.5
        assert baseline.avg == pytest.approx(42.5)
        assert baseline.sigma > 0


def test_baseline_calculator_respects_window_days(session_factory, sample_entity):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        # Add 40 days of history
        for day in range(40):
            _add_history(
                session,
                sample_entity,
                base_time + timedelta(days=day),
                risk_score=30.0,
            )
        # Add one outlier 35 days ago
        _add_history(
            session,
            sample_entity,
            base_time + timedelta(days=5),
            risk_score=100.0,
        )
        session.commit()
        
        # With 30-day window, old outlier should be excluded
        calc = BaselineCalculator(session, window_days=30)
        until = base_time + timedelta(days=41)
        baseline = calc.get_baseline(sample_entity, until)
        
        # Should be close to 30.0 since outlier is outside window
        assert baseline.avg < 35.0


def test_baseline_calculator_caches_results(session_factory, sample_entity):
    base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        for day in range(5):
            _add_history(
                session,
                sample_entity,
                base_time + timedelta(days=day),
                risk_score=20.0,
            )
        session.commit()
        
        calc = BaselineCalculator(session)
        until = base_time + timedelta(days=6)
        
        # First call should compute
        baseline1 = calc.get_baseline(sample_entity, until)
        
        # Second call should use cache
        baseline2 = calc.get_baseline(sample_entity, until)
        
        assert baseline1 is baseline2
        assert sample_entity in calc.cache


def test_is_anomalous_detects_outliers(session_factory, sample_entity):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        # Create baseline: avg=30, sigma=5
        for day in range(10):
            _add_history(
                session,
                sample_entity,
                base_time + timedelta(days=day),
                risk_score=25.0 + (day % 3) * 5,  # varies between 25, 30, 35
            )
        session.commit()
        
        calc = BaselineCalculator(session, sigma_multiplier=2.0)
        until = base_time + timedelta(days=11)
        
        # Normal score should not be anomalous
        is_anom, delta = calc.is_anomalous(sample_entity, until, 35.0)
        assert not is_anom
        
        # High score should be anomalous (> avg + 2*sigma)
        is_anom, delta = calc.is_anomalous(sample_entity, until, 80.0)
        assert is_anom
        assert delta > 0


def test_is_anomalous_returns_delta(session_factory, sample_entity):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        for day in range(5):
            _add_history(
                session,
                sample_entity,
                base_time + timedelta(days=day),
                risk_score=50.0,
            )
        session.commit()
        
        calc = BaselineCalculator(session)
        until = base_time + timedelta(days=6)
        
        is_anom, delta = calc.is_anomalous(sample_entity, until, 60.0)
        
        # delta = 60.0 - 50.0 = 10.0
        assert delta == pytest.approx(10.0)


def test_baseline_calculator_handles_multiple_entities(session_factory):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        entity1 = Entity(entity_type="user", entity_value="alice")
        entity2 = Entity(entity_type="user", entity_value="bob")
        session.add(entity1)
        session.add(entity2)
        session.commit()
        
        # Different baselines for different entities
        for day in range(5):
            _add_history(session, entity1.id, base_time + timedelta(days=day), 20.0)
            _add_history(session, entity2.id, base_time + timedelta(days=day), 80.0)
        session.commit()
        
        calc = BaselineCalculator(session)
        until = base_time + timedelta(days=6)
        
        baseline1 = calc.get_baseline(entity1.id, until)
        baseline2 = calc.get_baseline(entity2.id, until)
        
        assert baseline1.avg == pytest.approx(20.0)
        assert baseline2.avg == pytest.approx(80.0)


def test_baseline_calculator_respects_env_vars(session_factory, sample_entity, monkeypatch):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    monkeypatch.setenv("UEBA_BASELINE_WINDOW_DAYS", "5")
    monkeypatch.setenv("UEBA_SIGMA_MULTIPLIER", "2.5")
    
    with session_factory() as session:
        for day in range(10):
            _add_history(session, sample_entity, base_time + timedelta(days=day), 30.0)
        session.commit()
        
        # Calculator should read from env
        calc = BaselineCalculator(session)
        assert calc.window_days == 5
        assert calc.sigma_multiplier == 2.5


def test_baseline_calculator_filters_deleted_history(session_factory, sample_entity):
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    with session_factory() as session:
        # Add normal history
        for day in range(5):
            _add_history(session, sample_entity, base_time + timedelta(days=day), 30.0)
        
        # Add deleted history with high score
        deleted_history = EntityRiskHistory(
            entity_id=sample_entity,
            risk_score=100.0,
            observed_at=base_time + timedelta(days=3),
            reason='{"generator": "test"}',
            deleted_at=base_time + timedelta(days=10),
        )
        session.add(deleted_history)
        session.commit()
        
        calc = BaselineCalculator(session)
        until = base_time + timedelta(days=11)
        baseline = calc.get_baseline(sample_entity, until)
        
        # Deleted history should be excluded, avg should be ~30
        assert baseline.avg == pytest.approx(30.0)
