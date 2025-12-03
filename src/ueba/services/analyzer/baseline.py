from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ueba.db.models import EntityRiskHistory


@dataclass(frozen=True)
class BaselineStats:
    avg: float
    sigma: float


class BaselineCalculator:
    def __init__(self, session: Session, window_days: Optional[int] = None, sigma_multiplier: Optional[float] = None):
        self.session = session
        if window_days is None:
            window_days = int(os.getenv("UEBA_BASELINE_WINDOW_DAYS", "30"))
        if sigma_multiplier is None:
            sigma_multiplier = float(os.getenv("UEBA_SIGMA_MULTIPLIER", "3.0"))
        self.window_days = window_days
        self.sigma_multiplier = sigma_multiplier
        self.cache: Dict[int, BaselineStats] = {}

    def get_baseline(self, entity_id: int, until: datetime) -> BaselineStats:
        if entity_id in self.cache:
            return self.cache[entity_id]

        query = (
            select(func.avg(EntityRiskHistory.risk_score), func.stddev_pop(EntityRiskHistory.risk_score))
            .where(
                EntityRiskHistory.entity_id == entity_id,
                EntityRiskHistory.deleted_at.is_(None),
                EntityRiskHistory.observed_at >= until - timedelta(days=self.window_days),
                EntityRiskHistory.observed_at < until,
            )
        )

        result = self.session.execute(query).one()
        avg = result[0] or 0.0
        sigma = result[1] or 0.0
        stats = BaselineStats(avg=avg, sigma=sigma)
        self.cache[entity_id] = stats
        return stats

    def is_anomalous(self, entity_id: int, until: datetime, risk_score: float) -> Tuple[bool, float]:
        stats = self.get_baseline(entity_id, until)
        threshold = stats.avg + self.sigma_multiplier * stats.sigma
        delta = risk_score - stats.avg
        return risk_score > threshold, delta
