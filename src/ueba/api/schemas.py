from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EntityRosterItem(BaseModel):
    """Represents an entity with latest risk and analysis data."""

    entity_id: int
    entity_type: str
    entity_value: str
    display_name: Optional[str] = None
    latest_risk_score: Optional[float] = None
    baseline_avg: Optional[float] = None
    baseline_sigma: Optional[float] = None
    delta: Optional[float] = None
    is_anomalous: bool = False
    triggered_rules: List[str] = Field(default_factory=list)
    last_observed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EntityRosterResponse(BaseModel):
    """Paginated list of entities with risk data."""

    total_count: int
    page: int
    page_size: int
    items: List[EntityRosterItem]


class RiskHistoryItem(BaseModel):
    """Single risk history window for an entity."""

    observed_at: datetime
    risk_score: float
    baseline_avg: Optional[float] = None
    baseline_sigma: Optional[float] = None
    delta: Optional[float] = None
    is_anomalous: bool = False
    triggered_rules: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class RiskHistoryResponse(BaseModel):
    """Risk history windows for an entity."""

    entity_id: int
    items: List[RiskHistoryItem]


class NormalizedEventItem(BaseModel):
    """A normalized event for an entity."""

    event_id: int
    event_type: str
    observed_at: datetime
    risk_score: Optional[float] = None
    summary: Optional[str] = None
    normalized_payload: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class EventsResponse(BaseModel):
    """Recent events for an entity."""

    entity_id: int
    total_count: int
    items: List[NormalizedEventItem]


class SettingsResponse(BaseModel):
    """UI settings and system configuration."""

    sigma_multiplier: float
    baseline_window_days: int
    last_analyzer_run_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database_connected: bool
    timestamp: datetime
