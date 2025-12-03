from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ueba.db.models import EntityRiskHistory, NormalizedEvent

if TYPE_CHECKING:  # pragma: no cover
    from .pipeline import AnalyzerResult

UTC = timezone.utc


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def window_bounds(observed_at: datetime) -> Tuple[datetime, datetime]:
    observed_utc = ensure_utc(observed_at)
    start = observed_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


@dataclass(frozen=True)
class EntityEventWindow:
    entity_id: int
    window_start: datetime
    window_end: datetime
    events: Sequence[NormalizedEvent]


class AnalyzerRepository:
    """Encapsulates analyzer-specific read/write operations."""

    REASON_GENERATOR = "analyzer_service"
    REASON_KIND = "daily_rollup"

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Normalized event queries
    # ------------------------------------------------------------------
    def fetch_entity_event_windows(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[EntityEventWindow]:
        stmt = select(NormalizedEvent).where(
            NormalizedEvent.entity_id.is_not(None),
            NormalizedEvent.deleted_at.is_(None),
            NormalizedEvent.status == "active",
        )

        if since is not None:
            stmt = stmt.where(NormalizedEvent.observed_at >= ensure_utc(since))
        if until is not None:
            stmt = stmt.where(NormalizedEvent.observed_at < ensure_utc(until))

        stmt = stmt.order_by(NormalizedEvent.entity_id, NormalizedEvent.observed_at)

        events: Sequence[NormalizedEvent] = self.session.execute(stmt).scalars().all()
        grouped: Dict[Tuple[int, datetime], List[NormalizedEvent]] = {}

        for event in events:
            if event.entity_id is None:
                continue
            start, _ = window_bounds(event.observed_at)
            key = (event.entity_id, start)
            grouped.setdefault(key, [])
            grouped[key].append(event)

        windows = [
            EntityEventWindow(
                entity_id=entity_id,
                window_start=window_start,
                window_end=window_start + timedelta(days=1),
                events=grouped[(entity_id, window_start)],
            )
            for (entity_id, window_start) in sorted(grouped.keys(), key=lambda item: (item[0], item[1]))
        ]

        return windows

    # ------------------------------------------------------------------
    # Entity risk history helpers
    # ------------------------------------------------------------------
    def persist_result(self, result: "AnalyzerResult") -> EntityRiskHistory:
        payload = {
            "generator": self.REASON_GENERATOR,
            "kind": self.REASON_KIND,
            "window_start": result.window_start.isoformat(),
            "window_end": result.window_end.isoformat(),
            "event_count": result.features.event_count,
            "highest_severity": result.features.highest_severity,
            "last_observed_at": result.features.last_observed_at.isoformat(),
            "rules": {
                "triggered": result.rule_evaluation.triggered_rules,
                "metadata": result.rule_evaluation.metadata,
            },
            "baseline": {
                "avg": result.baseline_avg,
                "sigma": result.baseline_sigma,
                "delta": result.delta,
                "is_anomalous": result.is_anomalous,
            },
        }
        reason = json.dumps(payload, sort_keys=True)

        existing = self._find_history(result.entity_id, result.window_end)
        if existing:
            existing.risk_score = result.risk_score
            existing.reason = reason
            return existing

        history = EntityRiskHistory(
            entity_id=result.entity_id,
            normalized_event_id=None,
            risk_score=result.risk_score,
            observed_at=result.window_end,
            reason=reason,
        )
        self.session.add(history)
        return history

    def latest_history_for_entity(self, entity_id: int) -> Optional[EntityRiskHistory]:
        stmt = (
            select(EntityRiskHistory)
            .where(
                EntityRiskHistory.entity_id == entity_id,
                EntityRiskHistory.deleted_at.is_(None),
            )
            .order_by(EntityRiskHistory.observed_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def _find_history(self, entity_id: int, observed_at: datetime) -> Optional[EntityRiskHistory]:
        stmt = select(EntityRiskHistory).where(
            EntityRiskHistory.entity_id == entity_id,
            EntityRiskHistory.observed_at == ensure_utc(observed_at),
            EntityRiskHistory.deleted_at.is_(None),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Checkpoint helpers
    # ------------------------------------------------------------------
    def get_latest_checkpoint(self) -> Optional[datetime]:
        stmt = select(func.max(EntityRiskHistory.observed_at)).where(
            EntityRiskHistory.reason.is_not(None),
            EntityRiskHistory.reason.contains(f'"generator": "{self.REASON_GENERATOR}"'),
        )
        checkpoint = self.session.execute(stmt).scalar_one_or_none()
        return ensure_utc(checkpoint) if checkpoint is not None else None
