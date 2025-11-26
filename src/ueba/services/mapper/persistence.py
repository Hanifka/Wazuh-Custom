from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ueba.db.models import Entity, NormalizedEvent, RawAlert


@dataclass
class EntityPayload:
    entity_type: str
    entity_value: str
    display_name: Optional[str]
    attributes: Optional[Dict[str, Any]]


@dataclass
class RawAlertPayload:
    dedupe_hash: str
    entity_id: Optional[int]
    source: str
    vendor: Optional[str]
    product: Optional[str]
    severity: Optional[int]
    observed_at: datetime
    original_payload: Dict[str, Any]
    enrichment_context: Optional[Dict[str, Any]]


@dataclass
class NormalizedEventPayload:
    raw_alert_id: Optional[int]
    entity_id: Optional[int]
    event_type: str
    risk_score: Optional[float]
    observed_at: datetime
    summary: Optional[str]
    normalized_payload: Optional[Dict[str, Any]]
    original_payload: Optional[Dict[str, Any]]


class PersistenceManager:
    """Handles database persistence and idempotency guards."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_entity(self, payload: EntityPayload) -> Entity:
        stmt = select(Entity).where(
            Entity.entity_type == payload.entity_type,
            Entity.entity_value == payload.entity_value,
        )
        entity: Optional[Entity] = self.session.execute(stmt).scalar_one_or_none()

        if entity:
            if payload.display_name and payload.display_name != entity.display_name:
                entity.display_name = payload.display_name
            if payload.attributes:
                current_attrs = dict(entity.attributes or {})
                current_attrs.update(payload.attributes)
                entity.attributes = current_attrs
        else:
            entity = Entity(
                entity_type=payload.entity_type,
                entity_value=payload.entity_value,
                display_name=payload.display_name,
                attributes=payload.attributes or {},
            )
            self.session.add(entity)
            self.session.flush()

        return entity

    def persist_raw_alert(self, payload: RawAlertPayload) -> Tuple[RawAlert, bool]:
        stmt = select(RawAlert).where(RawAlert.dedupe_hash == payload.dedupe_hash)
        existing: Optional[RawAlert] = self.session.execute(stmt).scalar_one_or_none()
        if existing:
            return existing, True

        raw_alert = RawAlert(
            dedupe_hash=payload.dedupe_hash,
            entity_id=payload.entity_id,
            source=payload.source,
            vendor=payload.vendor,
            product=payload.product,
            severity=payload.severity,
            observed_at=payload.observed_at,
            original_payload=payload.original_payload,
            enrichment_context=payload.enrichment_context,
        )
        self.session.add(raw_alert)
        self.session.flush()
        return raw_alert, False

    def persist_normalized_event(
        self, payload: NormalizedEventPayload, skip_if_exists: bool = False
    ) -> Tuple[Optional[NormalizedEvent], bool]:
        if not payload.raw_alert_id:
            return None, False

        if skip_if_exists:
            stmt = select(NormalizedEvent).where(NormalizedEvent.raw_alert_id == payload.raw_alert_id)
            existing: Optional[NormalizedEvent] = self.session.execute(stmt).scalar_one_or_none()
            if existing:
                return existing, True

        normalized_event = NormalizedEvent(
            raw_alert_id=payload.raw_alert_id,
            entity_id=payload.entity_id,
            event_type=payload.event_type,
            risk_score=payload.risk_score,
            observed_at=payload.observed_at,
            summary=payload.summary,
            normalized_payload=payload.normalized_payload,
            original_payload=payload.original_payload,
        )
        self.session.add(normalized_event)
        self.session.flush()
        return normalized_event, False
