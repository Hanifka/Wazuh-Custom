from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


TIMESTAMP = DateTime(timezone=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)


class StatusMixin:
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="active")


class Entity(TimestampMixin, SoftDeleteMixin, StatusMixin, Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_value: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ux_entities_type_value", "entity_type", "entity_value", unique=True),
    )


class RawAlert(TimestampMixin, SoftDeleteMixin, StatusMixin, Base):
    __tablename__ = "raw_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    vendor: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    product: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    severity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )
    original_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    enrichment_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_raw_alerts_entity_observed", "entity_id", "observed_at"),
    )


class NormalizedEvent(TimestampMixin, SoftDeleteMixin, StatusMixin, Base):
    __tablename__ = "normalized_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_alert_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("raw_alerts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    normalized_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    original_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_normalized_events_entity_observed", "entity_id", "observed_at"),
    )


class EntityRiskHistory(TimestampMixin, SoftDeleteMixin, StatusMixin, Base):
    __tablename__ = "entity_risk_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    normalized_event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("normalized_events.id", ondelete="SET NULL"), nullable=True
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_entity_risk_history_entity_observed", "entity_id", "observed_at"),
    )


class TPFPFeedback(TimestampMixin, SoftDeleteMixin, StatusMixin, Base):
    __tablename__ = "tp_fp_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    normalized_event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("normalized_events.id", ondelete="SET NULL"), nullable=True
    )
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )


class ThresholdOverride(TimestampMixin, SoftDeleteMixin, StatusMixin, Base):
    __tablename__ = "threshold_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    analyzer_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    comparison: Mapped[str] = mapped_column(String(16), nullable=False, server_default=">=")
    effective_from: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
