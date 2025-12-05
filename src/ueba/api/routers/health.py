from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ueba.api.auth import verify_credentials
from ueba.api.dependencies import get_session
from ueba.api.schemas import HealthResponse, SettingsResponse
from ueba.db.models import EntityRiskHistory
from ueba.utils.env import get_env_float, get_env_int

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    session: Session = Depends(get_session),
) -> HealthResponse:
    """
    Health check endpoint - no authentication required.
    
    Verifies database connectivity and returns system status.
    """
    database_connected = False
    try:
        # Try a simple query to verify DB connectivity
        session.execute(text("SELECT 1"))
        database_connected = True
    except Exception:
        pass

    return HealthResponse(
        status="healthy" if database_connected else "degraded",
        database_connected=database_connected,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/api/v1/settings", response_model=SettingsResponse, dependencies=[Depends(verify_credentials)])
def get_settings(
    session: Session = Depends(get_session),
) -> SettingsResponse:
    """
    Get UI settings and system configuration.
    
    Returns baseline window, sigma multiplier, and last analyzer run timestamp.
    """
    sigma_multiplier = get_env_float("UEBA_SIGMA_MULTIPLIER", 3.0)
    baseline_window_days = get_env_int("UEBA_BASELINE_WINDOW_DAYS", 30)

    # Get last analyzer run time (latest EntityRiskHistory with analyzer_service generator)
    last_run_stmt = (
        select(EntityRiskHistory.observed_at)
        .where(
            EntityRiskHistory.reason.is_not(None),
            EntityRiskHistory.reason.contains('"generator": "analyzer_service"'),
            EntityRiskHistory.deleted_at.is_(None),
        )
        .order_by(EntityRiskHistory.observed_at.desc())
        .limit(1)
    )
    last_run_at = session.execute(last_run_stmt).scalar_one_or_none()

    return SettingsResponse(
        sigma_multiplier=sigma_multiplier,
        baseline_window_days=baseline_window_days,
        last_analyzer_run_at=last_run_at,
    )
