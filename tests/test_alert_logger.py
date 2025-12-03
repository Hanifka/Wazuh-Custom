from __future__ import annotations

import json
from pathlib import Path

import pytest

from ueba.logging import AlertLogger


def test_alert_logger_creates_log_directory(tmp_path: Path):
    log_path = tmp_path / "nested" / "dir" / "alerts.log"
    logger = AlertLogger(log_path)
    
    logger.log_anomaly(
        entity_id=123,
        risk_score=85.0,
        baseline_avg=50.0,
        baseline_sigma=10.0,
        delta=35.0,
        triggered_rules=["high_event_volume"],
    )
    
    assert log_path.exists()
    assert log_path.parent.exists()


def test_alert_logger_writes_newline_delimited_json(tmp_path: Path):
    log_path = tmp_path / "alerts.log"
    logger = AlertLogger(log_path)
    
    logger.log_anomaly(
        entity_id=123,
        risk_score=85.0,
        baseline_avg=50.0,
        baseline_sigma=10.0,
        delta=35.0,
        triggered_rules=["high_event_volume", "high_severity_detected"],
    )
    
    logger.log_anomaly(
        entity_id=456,
        risk_score=92.0,
        baseline_avg=45.0,
        baseline_sigma=8.0,
        delta=47.0,
        triggered_rules=["suspicious_activity"],
    )
    
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 2
    
    # Verify first alert
    alert1 = json.loads(lines[0])
    assert alert1["entity_id"] == 123
    assert alert1["risk_score"] == 85.0
    assert alert1["baseline_avg"] == 50.0
    assert alert1["baseline_sigma"] == 10.0
    assert alert1["delta"] == 35.0
    assert alert1["triggered_rules"] == ["high_event_volume", "high_severity_detected"]
    assert "timestamp" in alert1
    
    # Verify second alert
    alert2 = json.loads(lines[1])
    assert alert2["entity_id"] == 456
    assert alert2["risk_score"] == 92.0


def test_alert_logger_appends_to_existing_file(tmp_path: Path):
    log_path = tmp_path / "alerts.log"
    logger = AlertLogger(log_path)
    
    logger.log_anomaly(
        entity_id=123,
        risk_score=85.0,
        baseline_avg=50.0,
        baseline_sigma=10.0,
        delta=35.0,
        triggered_rules=["rule1"],
    )
    
    # Create new logger instance and append
    logger2 = AlertLogger(log_path)
    logger2.log_anomaly(
        entity_id=456,
        risk_score=90.0,
        baseline_avg=55.0,
        baseline_sigma=12.0,
        delta=35.0,
        triggered_rules=["rule2"],
    )
    
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 2


def test_alert_logger_json_fields_sorted(tmp_path: Path):
    log_path = tmp_path / "alerts.log"
    logger = AlertLogger(log_path)
    
    logger.log_anomaly(
        entity_id=123,
        risk_score=85.0,
        baseline_avg=50.0,
        baseline_sigma=10.0,
        delta=35.0,
        triggered_rules=["rule1"],
    )
    
    line = log_path.read_text().strip()
    
    # Verify keys are sorted (JSON serialization preserves order)
    expected_order = [
        "baseline_avg",
        "baseline_sigma",
        "delta",
        "entity_id",
        "risk_score",
        "timestamp",
        "triggered_rules",
    ]
    
    parsed = json.loads(line)
    assert list(parsed.keys()) == expected_order


def test_alert_logger_handles_empty_rules(tmp_path: Path):
    log_path = tmp_path / "alerts.log"
    logger = AlertLogger(log_path)
    
    logger.log_anomaly(
        entity_id=123,
        risk_score=85.0,
        baseline_avg=50.0,
        baseline_sigma=10.0,
        delta=35.0,
        triggered_rules=[],
    )
    
    line = log_path.read_text().strip()
    alert = json.loads(line)
    assert alert["triggered_rules"] == []


def test_alert_logger_timestamp_is_iso_format(tmp_path: Path):
    log_path = tmp_path / "alerts.log"
    logger = AlertLogger(log_path)
    
    logger.log_anomaly(
        entity_id=123,
        risk_score=85.0,
        baseline_avg=50.0,
        baseline_sigma=10.0,
        delta=35.0,
        triggered_rules=["rule1"],
    )
    
    line = log_path.read_text().strip()
    alert = json.loads(line)
    
    # Verify timestamp is valid ISO format
    from datetime import datetime
    timestamp = datetime.fromisoformat(alert["timestamp"])
    assert timestamp is not None
