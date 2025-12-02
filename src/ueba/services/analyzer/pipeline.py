from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Sequence

from ueba.db.models import NormalizedEvent

from .repository import ensure_utc


def _extract_severity_from_payload(payload: Optional[Dict[str, Any]]) -> Optional[int]:
    if not isinstance(payload, dict):
        return None

    if "severity" in payload:
        try:
            return int(payload["severity"])
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            return None

    data = payload.get("data")
    if isinstance(data, dict) and "severity" in data:
        try:
            return int(data["severity"])
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            return None

    return None


def _severity_from_event(event: NormalizedEvent) -> Optional[int]:
    return (
        _extract_severity_from_payload(event.normalized_payload)
        or _extract_severity_from_payload(event.original_payload)
        or (int(event.risk_score) if event.risk_score is not None else None)
    )


@dataclass(frozen=True)
class ExtractedFeatures:
    """Simple feature set for Phase 0."""

    event_count: int
    highest_severity: Optional[int]
    last_observed_at: datetime
    event_types: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuleEvaluation:
    """Output of rule evaluation stage."""

    triggered_rules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalyzerResult:
    """Final output of the analyzer pipeline."""

    entity_id: int
    window_start: datetime
    window_end: datetime
    features: ExtractedFeatures
    rule_evaluation: RuleEvaluation
    risk_score: float


class AnalyzerStage(Protocol):
    """Protocol for analyzer pipeline stages."""

    def process(self, **kwargs: Any) -> Any:
        """Execute this stage of the pipeline."""
        ...


class FeatureExtractor(ABC):
    """Base class for feature extraction stages."""

    @abstractmethod
    def extract(self, events: Sequence[NormalizedEvent]) -> ExtractedFeatures:
        """Extract features from a sequence of events."""
        pass


class SimpleFeatureExtractor(FeatureExtractor):
    """Basic feature extractor for Phase 0."""

    def extract(self, events: Sequence[NormalizedEvent]) -> ExtractedFeatures:
        """Extract simple aggregates: count, max severity, last observed, event types."""
        if not events:
            raise ValueError("Cannot extract features from empty event list")

        event_count = len(events)
        severities = [_severity_from_event(e) for e in events]
        severities = [s for s in severities if s is not None]
        highest_severity = int(max(severities)) if severities else None

        last_observed = max(e.observed_at for e in events)
        event_types = sorted({e.event_type for e in events})

        return ExtractedFeatures(
            event_count=event_count,
            highest_severity=highest_severity,
            last_observed_at=ensure_utc(last_observed),
            event_types=event_types,
        )


class RuleEvaluator(ABC):
    """Base class for rule evaluation stages."""

    @abstractmethod
    def evaluate(
        self, entity_id: int, features: ExtractedFeatures, events: Sequence[NormalizedEvent]
    ) -> RuleEvaluation:
        """Evaluate rules based on features and events."""
        pass


class PlaceholderRuleEvaluator(RuleEvaluator):
    """Placeholder rule evaluator for Phase 0."""

    def evaluate(
        self, entity_id: int, features: ExtractedFeatures, events: Sequence[NormalizedEvent]
    ) -> RuleEvaluation:
        """Simple threshold-based rules as placeholder."""
        triggered = []
        metadata = {}

        if features.event_count > 10:
            triggered.append("high_event_volume")
            metadata["event_count"] = features.event_count

        if features.highest_severity is not None and features.highest_severity >= 8:
            triggered.append("high_severity_detected")
            metadata["highest_severity"] = features.highest_severity

        return RuleEvaluation(triggered_rules=triggered, metadata=metadata)


class ScoringStrategy(ABC):
    """Base class for risk scoring strategies."""

    @abstractmethod
    def calculate_score(
        self, entity_id: int, features: ExtractedFeatures, rule_evaluation: RuleEvaluation
    ) -> float:
        """Calculate risk score based on features and rules."""
        pass


class SimpleScoring(ScoringStrategy):
    """Simple scoring strategy for Phase 0."""

    def calculate_score(
        self, entity_id: int, features: ExtractedFeatures, rule_evaluation: RuleEvaluation
    ) -> float:
        """
        Calculate a simple risk score:
        - Base score from event count (0-40 points)
        - Severity bonus (0-30 points)
        - Rule trigger bonus (30 points per rule)
        """
        score = 0.0

        # Event count contribution (cap at 40)
        score += min(features.event_count * 2, 40)

        # Severity contribution (0-30 based on highest severity)
        if features.highest_severity is not None:
            score += (features.highest_severity / 10.0) * 30

        # Rule trigger bonus
        score += len(rule_evaluation.triggered_rules) * 30

        # Cap at 100
        return min(score, 100.0)


class AnalyzerPipeline:
    """Pluggable analyzer pipeline orchestrating feature extraction, rules, and scoring."""

    def __init__(
        self,
        feature_extractor: Optional[FeatureExtractor] = None,
        rule_evaluator: Optional[RuleEvaluator] = None,
        scoring_strategy: Optional[ScoringStrategy] = None,
    ):
        self.feature_extractor = feature_extractor or SimpleFeatureExtractor()
        self.rule_evaluator = rule_evaluator or PlaceholderRuleEvaluator()
        self.scoring_strategy = scoring_strategy or SimpleScoring()

    def analyze(
        self,
        entity_id: int,
        window_start: datetime,
        window_end: datetime,
        events: Sequence[NormalizedEvent],
    ) -> AnalyzerResult:
        """
        Run the full analyzer pipeline for a given entity/window.

        Args:
            entity_id: Entity identifier
            window_start: Start of time window
            window_end: End of time window
            events: Events for this entity/window

        Returns:
            AnalyzerResult with features, rule evaluation, and risk score
        """
        # Stage 1: Feature extraction
        features = self.feature_extractor.extract(events)

        # Stage 2: Rule evaluation
        rule_evaluation = self.rule_evaluator.evaluate(entity_id, features, events)

        # Stage 3: Scoring
        risk_score = self.scoring_strategy.calculate_score(entity_id, features, rule_evaluation)

        return AnalyzerResult(
            entity_id=entity_id,
            window_start=ensure_utc(window_start),
            window_end=ensure_utc(window_end),
            features=features,
            rule_evaluation=rule_evaluation,
            risk_score=risk_score,
        )
