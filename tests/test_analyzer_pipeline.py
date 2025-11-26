from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ueba.db.models import NormalizedEvent
from ueba.services.analyzer.pipeline import (
    AnalyzerPipeline,
    ExtractedFeatures,
    PlaceholderRuleEvaluator,
    RuleEvaluation,
    SimpleFeatureExtractor,
    SimpleScoring,
)


def test_feature_extractor_basic_aggregates():
    base_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    events = [
        NormalizedEvent(
            id=1,
            entity_id=100,
            event_type="login",
            observed_at=base_time,
            normalized_payload={"severity": 5},
        ),
        NormalizedEvent(
            id=2,
            entity_id=100,
            event_type="file_access",
            observed_at=base_time,
            normalized_payload={"severity": 8},
        ),
        NormalizedEvent(
            id=3,
            entity_id=100,
            event_type="login",
            observed_at=base_time,
            risk_score=3.0,
        ),
    ]

    extractor = SimpleFeatureExtractor()
    features = extractor.extract(events)

    assert features.event_count == 3
    assert features.highest_severity == 8
    assert features.last_observed_at == base_time
    assert set(features.event_types) == {"login", "file_access"}


def test_feature_extractor_handles_missing_severity():
    base_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    events = [
        NormalizedEvent(
            id=1,
            entity_id=100,
            event_type="login",
            observed_at=base_time,
        ),
    ]

    extractor = SimpleFeatureExtractor()
    features = extractor.extract(events)

    assert features.event_count == 1
    assert features.highest_severity is None


def test_feature_extractor_raises_on_empty_events():
    extractor = SimpleFeatureExtractor()
    with pytest.raises(ValueError, match="empty event list"):
        extractor.extract([])


def test_rule_evaluator_triggers_high_event_volume():
    features = ExtractedFeatures(
        event_count=15,
        highest_severity=5,
        last_observed_at=datetime.now(timezone.utc),
        event_types=["login"],
    )

    evaluator = PlaceholderRuleEvaluator()
    result = evaluator.evaluate(100, features, [])

    assert "high_event_volume" in result.triggered_rules
    assert result.metadata["event_count"] == 15


def test_rule_evaluator_triggers_high_severity():
    features = ExtractedFeatures(
        event_count=5,
        highest_severity=9,
        last_observed_at=datetime.now(timezone.utc),
        event_types=["alert"],
    )

    evaluator = PlaceholderRuleEvaluator()
    result = evaluator.evaluate(100, features, [])

    assert "high_severity_detected" in result.triggered_rules
    assert result.metadata["highest_severity"] == 9


def test_rule_evaluator_no_triggers():
    features = ExtractedFeatures(
        event_count=5,
        highest_severity=3,
        last_observed_at=datetime.now(timezone.utc),
        event_types=["login"],
    )

    evaluator = PlaceholderRuleEvaluator()
    result = evaluator.evaluate(100, features, [])

    assert len(result.triggered_rules) == 0


def test_simple_scoring_event_count_only():
    features = ExtractedFeatures(
        event_count=10,
        highest_severity=None,
        last_observed_at=datetime.now(timezone.utc),
        event_types=["login"],
    )
    rules = RuleEvaluation()

    scorer = SimpleScoring()
    score = scorer.calculate_score(100, features, rules)

    assert score == 20.0  # 10 events * 2 = 20


def test_simple_scoring_with_severity():
    features = ExtractedFeatures(
        event_count=5,
        highest_severity=10,
        last_observed_at=datetime.now(timezone.utc),
        event_types=["alert"],
    )
    rules = RuleEvaluation()

    scorer = SimpleScoring()
    score = scorer.calculate_score(100, features, rules)

    assert score == 40.0  # (5*2) + (10/10 * 30) = 10 + 30 = 40


def test_simple_scoring_with_rules():
    features = ExtractedFeatures(
        event_count=5,
        highest_severity=5,
        last_observed_at=datetime.now(timezone.utc),
        event_types=["alert"],
    )
    rules = RuleEvaluation(triggered_rules=["high_event_volume", "high_severity_detected"])

    scorer = SimpleScoring()
    score = scorer.calculate_score(100, features, rules)

    # (5*2) + (5/10*30) + (2*30) = 10 + 15 + 60 = 85
    assert score == 85.0


def test_simple_scoring_capped_at_100():
    features = ExtractedFeatures(
        event_count=50,  # Would give 100 (capped at 40)
        highest_severity=10,  # Gives 30
        last_observed_at=datetime.now(timezone.utc),
        event_types=["alert"],
    )
    rules = RuleEvaluation(triggered_rules=["rule1", "rule2"])  # 60 points

    scorer = SimpleScoring()
    score = scorer.calculate_score(100, features, rules)

    # 40 + 30 + 60 = 130, capped at 100
    assert score == 100.0


def test_analyzer_pipeline_end_to_end():
    base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    events = [
        NormalizedEvent(
            id=i,
            entity_id=100,
            event_type="login" if i % 2 == 0 else "file_access",
            observed_at=base_time,
            normalized_payload={"severity": 7 + (i % 3)},
        )
        for i in range(12)
    ]

    pipeline = AnalyzerPipeline()
    result = pipeline.analyze(
        entity_id=100,
        window_start=base_time,
        window_end=base_time,
        events=events,
    )

    assert result.entity_id == 100
    assert result.features.event_count == 12
    assert result.features.highest_severity == 9
    assert "high_event_volume" in result.rule_evaluation.triggered_rules
    assert "high_severity_detected" in result.rule_evaluation.triggered_rules
    assert result.risk_score > 0
