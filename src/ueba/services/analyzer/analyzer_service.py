from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from typing import Optional

from .service import AnalyzerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def parse_datetime(value: str) -> datetime:
    """Parse ISO-format datetime string."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def main() -> None:
    """Main entrypoint for analyzer service CLI."""
    parser = argparse.ArgumentParser(
        description="UEBA Analyzer Service - Process normalized events into risk scores"
    )
    parser.add_argument(
        "--mode",
        choices=["once", "daemon"],
        default="once",
        help="Run mode: once (cron-compatible) or daemon (continuous loop)",
    )
    parser.add_argument(
        "--since",
        type=parse_datetime,
        help="Start time (ISO format, e.g., 2024-01-01T00:00:00Z). Defaults to last checkpoint.",
    )
    parser.add_argument(
        "--until",
        type=parse_datetime,
        help="End time (ISO format, exclusive). Defaults to start of current UTC day.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Polling interval in seconds for daemon mode (default: 300)",
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (default: from DATABASE_URL env or sqlite:///./ueba.db)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Import here to respect database-url override
    if args.database_url:
        import os

        os.environ["DATABASE_URL"] = args.database_url

    service = AnalyzerService()

    if args.mode == "once":
        logger.info("Running analyzer in one-shot mode")
        processed = service.run_once(since=args.since, until=args.until)
        logger.info("Analyzer completed: processed=%s windows", processed)
    elif args.mode == "daemon":
        logger.info("Running analyzer in daemon mode (interval=%ss)", args.interval)
        service.run_forever(
            interval_seconds=args.interval,
            since=args.since,
            until=args.until,
        )


if __name__ == "__main__":
    main()
