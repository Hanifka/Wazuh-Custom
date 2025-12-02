# Analyzer Service

The Analyzer Service processes normalized events into entity risk history records by extracting features, evaluating rules, and calculating risk scores.

## Architecture

### Components

1. **Repository Layer** (`repository.py`)
   - Queries normalized events grouped by entity and UTC daily windows
   - Persists entity risk history records with JSON metadata
   - Manages checkpoint state for idempotent processing

2. **Pipeline** (`pipeline.py`)
   - **FeatureExtractor**: Extracts aggregates (event count, highest severity, event types)
   - **RuleEvaluator**: Evaluates threshold-based rules (placeholder for Phase 1)
   - **ScoringStrategy**: Calculates risk scores based on features and rules
   - Pluggable architecture allows swapping implementations

3. **Service** (`service.py`)
   - Orchestrates the analysis workflow
   - Supports one-shot and continuous daemon modes
   - Maintains processing checkpoint for incremental runs

4. **CLI** (`analyzer_service.py`)
   - Command-line interface with argparse
   - Cron-compatible (default: once mode)
   - Supports custom time windows and database URLs

## Usage

### One-Shot Mode (Cron Compatible)

Process events once and exit:

```bash
python -m ueba.services.analyzer.analyzer_service --mode once
```

With custom time window:

```bash
python -m ueba.services.analyzer.analyzer_service \
    --mode once \
    --since 2024-01-01T00:00:00Z \
    --until 2024-01-31T00:00:00Z
```

### Daemon Mode

Run continuously with polling:

```bash
python -m ueba.services.analyzer.analyzer_service \
    --mode daemon \
    --interval 300
```

### Options

- `--mode`: Run mode (once|daemon), default: once
- `--since`: Start time (ISO format), defaults to last checkpoint
- `--until`: End time (ISO format), defaults to start of current UTC day
- `--interval`: Polling interval in seconds for daemon mode, default: 300
- `--database-url`: Database URL override
- `--log-level`: Logging level (DEBUG|INFO|WARNING|ERROR), default: INFO

## Daily Rollup Windows

The analyzer processes events in UTC daily windows:
- Window start: 00:00:00 UTC
- Window end: 23:59:59.999999 UTC (exclusive next day)
- Entity risk history `observed_at` is set to window end

## Checkpoint Mechanism

The analyzer maintains an implicit checkpoint by tracking the maximum `observed_at` in `entity_risk_history` records with `reason` containing `"generator": "analyzer_service"`.

Subsequent runs without `--since` resume from this checkpoint, enabling incremental processing.

## Risk Score Calculation (Phase 0)

Simple scoring formula:
- Event count: min(count * 2, 40) points
- Severity: (highest_severity / 10) * 30 points
- Rules: 30 points per triggered rule
- Capped at 100 points

## Output Format

Each entity/window generates an `entity_risk_history` record with a JSON `reason`:

```json
{
  "generator": "analyzer_service",
  "kind": "daily_rollup",
  "window_start": "2024-01-15T00:00:00+00:00",
  "window_end": "2024-01-16T00:00:00+00:00",
  "event_count": 12,
  "highest_severity": 9,
  "last_observed_at": "2024-01-15T14:30:00+00:00",
  "rules": {
    "triggered": ["high_event_volume", "high_severity_detected"],
    "metadata": {"event_count": 12, "highest_severity": 9}
  }
}
```

## Testing

Unit tests cover:
- Repository functions with SQLite fixtures
- Feature extraction with synthetic events
- Rule evaluation logic
- Scoring calculations
- End-to-end service execution
- Idempotent checkpoint behavior
- Daily boundary handling (UTC)

Run tests:

```bash
pytest tests/test_analyzer_repository.py
pytest tests/test_analyzer_pipeline.py
pytest tests/test_analyzer_service.py
```

## Future Enhancements (Phase 1+)

- Machine learning-based scoring
- Behavioral profiling and baselining
- Anomaly detection
- TP/FP feedback loop integration
- Threshold override support
- Advanced rule engine with conditional logic
