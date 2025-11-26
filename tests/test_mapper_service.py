from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ueba.config import mapping_loader
from ueba.db.base import Base
from ueba.db.models import Entity, NormalizedEvent, RawAlert
from ueba.services.mapper.mapper import AlertMapper
from ueba.services.mapper.persistence import PersistenceManager


@pytest.fixture()
def session_factory(tmp_path: Path):
    db_path = tmp_path / "ueba_test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    try:
        yield SessionFactory
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def resolver(tmp_path: Path):
    mapping_file = tmp_path / "mapping.yml"
    mapping_file.write_text(
        """
        priority: global
        defaults:
          entity_id: agent.id
          entity_type: host
          severity: data.severity
          timestamp: "@timestamp"
          enrichment:
            agent_name: agent.name
            rule_description: rule.description
        """,
        encoding="utf-8",
    )
    return mapping_loader.load([mapping_file])


def sample_alert(**overrides: Dict) -> Dict:
    alert = {
        "id": "1670000000.1",
        "@timestamp": "2024-01-02T15:04:05Z",
        "agent": {"id": "001", "name": "host-1"},
        "rule": {
            "id": "9100",
            "level": 12,
            "description": "Test Rule",
            "groups": ["authentication_failed"],
        },
        "data": {"srcuser": "alice", "severity": 9},
    }
    alert.update(overrides)
    return alert


def test_mapper_persists_entities_and_events(session_factory, resolver):
    mapper = AlertMapper(resolver)
    alert = sample_alert()

    with session_factory() as session:
        persistence = PersistenceManager(session)
        result = mapper.map_and_persist(alert, persistence, source="wazuh")
        session.commit()

        assert result["status"] == "success"
        assert result["raw_alert_id"] is not None
        assert result["normalized_event_id"] is not None

        entity = session.execute(select(Entity)).scalar_one()
        assert entity.entity_type == "host"
        assert entity.entity_value == "001"
        assert entity.attributes["agent_name"] == "host-1"

        raw_alert = session.execute(select(RawAlert)).scalar_one()
        assert raw_alert.source == "wazuh"
        assert raw_alert.severity == 9
        assert raw_alert.dedupe_hash is not None

        normalized_event = session.execute(select(NormalizedEvent)).scalar_one()
        assert normalized_event.event_type == "wazuh_rule_9100"
        assert normalized_event.summary == "Test Rule"


def test_mapper_deduplicates_alerts(session_factory, resolver):
    mapper = AlertMapper(resolver)
    alert = sample_alert()

    with session_factory() as session:
        persistence = PersistenceManager(session)
        first = mapper.map_and_persist(alert, persistence)
        second = mapper.map_and_persist(alert, persistence)
        session.commit()

        assert first["status"] == "success"
        assert second["status"] == "skipped"
        assert second["reason"] == "duplicate"

        raw_alerts = session.execute(select(RawAlert)).scalars().all()
        assert len(raw_alerts) == 1

        normalized_events = session.execute(select(NormalizedEvent)).scalars().all()
        assert len(normalized_events) == 1


def test_entity_upsert_updates_attributes(session_factory, resolver):
    mapper = AlertMapper(resolver)

    with session_factory() as session:
        persistence = PersistenceManager(session)
        mapper.map_and_persist(sample_alert(), persistence)

        updated_alert = sample_alert(agent={"id": "001", "name": "host-updated"})
        mapper.map_and_persist(updated_alert, persistence)
        session.commit()

        entity = session.execute(select(Entity)).scalar_one()
        assert entity.attributes["agent_name"] == "host-updated"
