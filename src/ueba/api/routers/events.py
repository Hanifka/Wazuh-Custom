from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ueba.api.auth import verify_credentials
from ueba.api.dependencies import get_session
from ueba.api.schemas import EventsResponse, NormalizedEventItem
from ueba.db.models import Entity, NormalizedEvent

router = APIRouter(prefix="/api/v1/entities", tags=["events"], dependencies=[Depends(verify_credentials)])


@router.get("/{entity_id}/events", response_model=EventsResponse)
def get_entity_events(
    entity_id: int,
    session: Session = Depends(get_session),
    limit: int = Query(100, ge=1, le=1000),
) -> EventsResponse:
    """
    Get recent normalized events for an entity.
    
    Returns the most recent events up to the specified limit.
    """
    # Verify entity exists
    entity_stmt = select(Entity).where(Entity.id == entity_id, Entity.deleted_at.is_(None))
    entity = session.execute(entity_stmt).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    # Count total events
    count_stmt = select(func.count(NormalizedEvent.id)).where(
        NormalizedEvent.entity_id == entity_id,
        NormalizedEvent.deleted_at.is_(None),
    )
    total_count = session.execute(count_stmt).scalar() or 0

    # Fetch events
    events_stmt = (
        select(NormalizedEvent)
        .where(
            NormalizedEvent.entity_id == entity_id,
            NormalizedEvent.deleted_at.is_(None),
        )
        .order_by(NormalizedEvent.observed_at.desc())
        .limit(limit)
    )
    events = session.execute(events_stmt).scalars().all()

    items = [
        NormalizedEventItem(
            event_id=event.id,
            event_type=event.event_type,
            observed_at=event.observed_at,
            risk_score=event.risk_score,
            summary=event.summary,
            normalized_payload=event.normalized_payload,
        )
        for event in events
    ]

    return EventsResponse(entity_id=entity_id, total_count=total_count, items=items)
