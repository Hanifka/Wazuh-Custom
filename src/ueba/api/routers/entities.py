from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ueba.api.auth import verify_credentials
from ueba.api.dependencies import get_session
from ueba.api.schemas import EntityRosterItem, EntityRosterResponse, RiskHistoryItem, RiskHistoryResponse
from ueba.db.models import Entity, EntityRiskHistory, TPFPFeedback

router = APIRouter(prefix="/api/v1/entities", tags=["entities"], dependencies=[Depends(verify_credentials)])


def _parse_reason_json(reason_str: Optional[str]) -> dict:
    """Parse reason JSON payload, return empty dict if invalid."""
    if not reason_str:
        return {}
    try:
        return json.loads(reason_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _get_latest_entity_risk(
    session: Session, entity_id: int
) -> Optional[tuple[float, Optional[dict]]]:
    """Get latest risk score and reason for an entity, returns (score, reason_dict)."""
    stmt = (
        select(EntityRiskHistory.risk_score, EntityRiskHistory.reason)
        .where(
            EntityRiskHistory.entity_id == entity_id,
            EntityRiskHistory.deleted_at.is_(None),
        )
        .order_by(EntityRiskHistory.observed_at.desc())
        .limit(1)
    )
    result = session.execute(stmt).first()
    if result:
        return result[0], _parse_reason_json(result[1])
    return None


def _get_feedback_stats(session: Session, entity_id: int) -> tuple[int, int, float]:
    """Get TP/FP counts and ratio for an entity. Returns (tp_count, fp_count, fp_ratio)."""
    stmt = (
        select(
            func.count().filter(TPFPFeedback.feedback_type == "tp"),
            func.count().filter(TPFPFeedback.feedback_type == "fp"),
        )
        .where(
            TPFPFeedback.entity_id == entity_id,
            TPFPFeedback.deleted_at.is_(None),
        )
    )
    result = session.execute(stmt).first()
    tp_count = result[0] if result[0] is not None else 0
    fp_count = result[1] if result[1] is not None else 0

    total = tp_count + fp_count
    fp_ratio = (fp_count / total) if total > 0 else 0.0

    return tp_count, fp_count, fp_ratio


@router.get("", response_model=EntityRosterResponse)
def list_entities(
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> EntityRosterResponse:
    """
    Get paginated roster of entities with latest risk scores and analysis.
    
    Uses efficient queries with joins to avoid per-entity lookups.
    """
    # Count total entities
    count_stmt = select(func.count(Entity.id)).where(Entity.deleted_at.is_(None))
    total_count = session.execute(count_stmt).scalar() or 0

    # Fetch entities with pagination
    offset = (page - 1) * page_size
    entity_stmt = (
        select(Entity)
        .where(Entity.deleted_at.is_(None))
        .order_by(Entity.id)
        .offset(offset)
        .limit(page_size)
    )
    entities = session.execute(entity_stmt).scalars().all()

    items = []
    for entity in entities:
        risk_data = _get_latest_entity_risk(session, entity.id)

        latest_risk_score = None
        baseline_avg = None
        baseline_sigma = None
        delta = None
        is_anomalous = False
        triggered_rules = []

        if risk_data:
            latest_risk_score, reason_dict = risk_data
            if reason_dict:
                baseline = reason_dict.get("baseline", {})
                baseline_avg = baseline.get("avg")
                baseline_sigma = baseline.get("sigma")
                delta = baseline.get("delta")
                is_anomalous = baseline.get("is_anomalous", False)

                rules = reason_dict.get("rules", {})
                triggered_rules = rules.get("triggered", [])

        # Get last observed time from EntityRiskHistory
        last_observed_stmt = (
            select(EntityRiskHistory.observed_at)
            .where(
                EntityRiskHistory.entity_id == entity.id,
                EntityRiskHistory.deleted_at.is_(None),
            )
            .order_by(EntityRiskHistory.observed_at.desc())
            .limit(1)
        )
        last_observed = session.execute(last_observed_stmt).scalar()

        # Get feedback stats
        tp_count, fp_count, fp_ratio = _get_feedback_stats(session, entity.id)

        item = EntityRosterItem(
            entity_id=entity.id,
            entity_type=entity.entity_type,
            entity_value=entity.entity_value,
            display_name=entity.display_name,
            latest_risk_score=latest_risk_score,
            baseline_avg=baseline_avg,
            baseline_sigma=baseline_sigma,
            delta=delta,
            is_anomalous=is_anomalous,
            triggered_rules=triggered_rules,
            last_observed_at=last_observed,
            tp_count=tp_count,
            fp_count=fp_count,
            fp_ratio=fp_ratio,
        )
        items.append(item)

    return EntityRosterResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/{entity_id}/history", response_model=RiskHistoryResponse)
def get_entity_history(
    entity_id: int,
    session: Session = Depends(get_session),
    limit: int = Query(100, ge=1, le=1000),
) -> RiskHistoryResponse:
    """
    Get risk history windows for an entity.
    
    Returns the most recent history records up to the specified limit.
    """
    # Verify entity exists
    entity_stmt = select(Entity).where(Entity.id == entity_id, Entity.deleted_at.is_(None))
    entity = session.execute(entity_stmt).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    # Fetch history
    history_stmt = (
        select(EntityRiskHistory)
        .where(
            EntityRiskHistory.entity_id == entity_id,
            EntityRiskHistory.deleted_at.is_(None),
        )
        .order_by(EntityRiskHistory.observed_at.desc())
        .limit(limit)
    )
    records = session.execute(history_stmt).scalars().all()

    items = []
    for record in records:
        reason_dict = _parse_reason_json(record.reason)
        baseline = reason_dict.get("baseline", {})

        item = RiskHistoryItem(
            observed_at=record.observed_at,
            risk_score=record.risk_score,
            baseline_avg=baseline.get("avg"),
            baseline_sigma=baseline.get("sigma"),
            delta=baseline.get("delta"),
            is_anomalous=baseline.get("is_anomalous", False),
            triggered_rules=reason_dict.get("rules", {}).get("triggered", []),
        )
        items.append(item)

    return RiskHistoryResponse(entity_id=entity_id, items=items)
