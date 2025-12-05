from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ueba.api.auth import verify_credentials
from ueba.api.dependencies import get_session
from ueba.api.schemas import FeedbackResponse, FeedbackStats, FeedbackSubmissionRequest, FeedbackItem
from ueba.db.models import Entity, NormalizedEvent, TPFPFeedback

router = APIRouter(prefix="/api/v1/entities", tags=["feedback"], dependencies=[Depends(verify_credentials)])


def _get_feedback_stats(session: Session, entity_id: int) -> FeedbackStats:
    """Calculate TP/FP stats for an entity."""
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

    return FeedbackStats(tp_count=tp_count, fp_count=fp_count, fp_ratio=fp_ratio)


@router.get("/{entity_id}/feedback", response_model=FeedbackResponse)
def get_feedback(
    entity_id: int,
    session: Session = Depends(get_session),
    limit: int = Query(100, ge=1, le=1000),
) -> FeedbackResponse:
    """
    Get feedback history and statistics for an entity.

    Returns recent feedback submissions and aggregated TP/FP stats.
    """
    # Verify entity exists
    entity_stmt = select(Entity).where(Entity.id == entity_id, Entity.deleted_at.is_(None))
    entity = session.execute(entity_stmt).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    # Fetch feedback history
    feedback_stmt = (
        select(TPFPFeedback)
        .where(
            TPFPFeedback.entity_id == entity_id,
            TPFPFeedback.deleted_at.is_(None),
        )
        .order_by(TPFPFeedback.submitted_at.desc())
        .limit(limit)
    )
    feedback_records = session.execute(feedback_stmt).scalars().all()

    items = [
        FeedbackItem(
            feedback_id=record.id,
            feedback_type=record.feedback_type,
            normalized_event_id=record.normalized_event_id,
            notes=record.notes,
            submitted_by=record.submitted_by,
            submitted_at=record.submitted_at,
        )
        for record in feedback_records
    ]

    stats = _get_feedback_stats(session, entity_id)

    return FeedbackResponse(entity_id=entity_id, items=items, stats=stats)


@router.post("/{entity_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    entity_id: int,
    request: FeedbackSubmissionRequest,
    session: Session = Depends(get_session),
    username: str = Depends(verify_credentials),
) -> FeedbackResponse:
    """
    Submit feedback (TP/FP marking) for an entity.

    Validates feedback_type is 'tp' or 'fp', stores the submission, and returns
    updated TP/FP counts and false-positive ratio for real-time UI updates.
    """
    # Verify entity exists
    entity_stmt = select(Entity).where(Entity.id == entity_id, Entity.deleted_at.is_(None))
    entity = session.execute(entity_stmt).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    # Validate feedback_type
    if request.feedback_type not in ("tp", "fp"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="feedback_type must be 'tp' or 'fp'",
        )

    # If normalized_event_id is provided, verify it exists
    if request.normalized_event_id:
        event_stmt = (
            select(NormalizedEvent).where(
                NormalizedEvent.id == request.normalized_event_id,
                NormalizedEvent.deleted_at.is_(None),
            )
        )
        event = session.execute(event_stmt).scalar_one_or_none()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Normalized event {request.normalized_event_id} not found",
            )

    # Create feedback record
    feedback = TPFPFeedback(
        entity_id=entity_id,
        normalized_event_id=request.normalized_event_id,
        feedback_type=request.feedback_type,
        notes=request.notes,
        submitted_by=username,
    )
    session.add(feedback)
    session.commit()

    # Fetch updated feedback history
    feedback_stmt = (
        select(TPFPFeedback)
        .where(
            TPFPFeedback.entity_id == entity_id,
            TPFPFeedback.deleted_at.is_(None),
        )
        .order_by(TPFPFeedback.submitted_at.desc())
        .limit(100)
    )
    feedback_records = session.execute(feedback_stmt).scalars().all()

    items = [
        FeedbackItem(
            feedback_id=record.id,
            feedback_type=record.feedback_type,
            normalized_event_id=record.normalized_event_id,
            notes=record.notes,
            submitted_by=record.submitted_by,
            submitted_at=record.submitted_at,
        )
        for record in feedback_records
    ]

    stats = _get_feedback_stats(session, entity_id)

    return FeedbackResponse(entity_id=entity_id, items=items, stats=stats)
