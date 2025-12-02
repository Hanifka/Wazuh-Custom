from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from ueba.db.base import get_session_factory

from .pipeline import AnalyzerPipeline
from .repository import AnalyzerRepository

logger = logging.getLogger(__name__)


def default_until() -> datetime:
    """Default end time is start of current UTC day (exclusive)."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class AnalyzerService:
    """Service that processes normalized events into entity risk history."""

    def __init__(
        self,
        session_factory=None,
        pipeline: Optional[AnalyzerPipeline] = None,
    ):
        self.session_factory = session_factory or get_session_factory()
        self.pipeline = pipeline or AnalyzerPipeline()

    def run_once(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> int:
        """Process events once and return number of processed windows."""
        processed = 0
        until = until or default_until()

        with self.session_factory() as session:
            repository = AnalyzerRepository(session)

            # Determine checkpoint
            checkpoint = since or repository.get_latest_checkpoint()
            if checkpoint and checkpoint >= until:
                logger.info(
                    "Analyzer checkpoint (%s) is newer than requested window (%s) - nothing to do",
                    checkpoint,
                    until,
                )
                return 0

            windows = repository.fetch_entity_event_windows(since=checkpoint, until=until)
            if not windows:
                logger.info("Analyzer found no windows to process")
                return 0

            for window in windows:
                result = self.pipeline.analyze(
                    entity_id=window.entity_id,
                    window_start=window.window_start,
                    window_end=window.window_end,
                    events=window.events,
                )
                repository.persist_result(result)
                processed += 1

            session.commit()

        logger.info("Analyzer processed %s window(s)", processed)
        return processed

    def run_forever(
        self,
        interval_seconds: int = 300,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> None:
        """Continuously run the analyzer service at fixed intervals."""
        logger.info(
            "Starting analyzer loop (interval=%ss, since=%s, until=%s)",
            interval_seconds,
            since,
            until,
        )
        try:
            while True:
                self.run_once(since=since, until=until)
                since = None  # ensure subsequent runs rely on checkpoint
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Analyzer loop interrupted - shutting down")
