from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _default_log_path() -> Path:
    return Path(os.getenv("UEBA_ALERT_LOG_PATH", "./ueba_alerts.log"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlertLogger:
    """Structured alert logger writing newline-delimited JSON."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or _default_log_path()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_anomaly(
        self,
        *,
        entity_id: int,
        risk_score: float,
        baseline_avg: float,
        baseline_sigma: float,
        delta: float,
        triggered_rules: List[str],
    ) -> None:
        payload: Dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "entity_id": entity_id,
            "risk_score": risk_score,
            "baseline_avg": baseline_avg,
            "baseline_sigma": baseline_sigma,
            "delta": delta,
            "triggered_rules": triggered_rules,
        }

        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
