from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from ueba.config.mapping_loader import load as load_mappings
from ueba.db.base import get_session_factory

from .inputs import AlertInputSource, FileTailSource, MessageQueueStubSource, StdInSource
from .mapper import AlertMapper
from .persistence import PersistenceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def run_mapper_service(
    input_source: AlertInputSource,
    source_name: str = "wazuh",
    database_url: Optional[str] = None,
    mapping_paths: Optional[list] = None,
    batch_size: int = 100,
) -> None:
    logger.info(f"Starting mapper service (source={source_name}, batch_size={batch_size})")

    resolver = load_mappings(mapping_paths)
    logger.info("Loaded mapping configuration")

    SessionFactory = get_session_factory(database_url)
    mapper = AlertMapper(resolver)

    processed = 0
    skipped = 0
    errors = 0

    with SessionFactory() as session:
        persistence = PersistenceManager(session)

        for alert in input_source:
            try:
                result = mapper.map_and_persist(alert, persistence, source=source_name)
                if result["status"] == "success":
                    processed += 1
                elif result["status"] == "skipped":
                    skipped += 1

                if (processed + skipped) % batch_size == 0:
                    session.commit()
                    logger.info(
                        f"Checkpoint: processed={processed}, skipped={skipped}, errors={errors}"
                    )

            except Exception as e:
                errors += 1
                logger.error(f"Error processing alert: {e}", exc_info=True)
                session.rollback()

        session.commit()

    logger.info(f"Mapper service completed: processed={processed}, skipped={skipped}, errors={errors}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="UEBA Mapper Service - Ingest and normalize Wazuh alerts"
    )
    parser.add_argument(
        "--input",
        choices=["stdin", "file", "queue"],
        default="stdin",
        help="Input source type (default: stdin)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to input file (required if --input=file)",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow file for new lines (like tail -f)",
    )
    parser.add_argument(
        "--source",
        default="wazuh",
        help="Source name for alerts (default: wazuh)",
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (default: from DATABASE_URL env or sqlite:///./ueba.db)",
    )
    parser.add_argument(
        "--mapping-paths",
        nargs="+",
        help="Paths to YAML mapping files",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Commit batch size (default: 100)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    if args.input == "stdin":
        input_source: AlertInputSource = StdInSource()
    elif args.input == "file":
        if not args.file:
            parser.error("--file is required when --input=file")
        if not args.file.exists():
            parser.error(f"File not found: {args.file}")
        input_source = FileTailSource(args.file, follow=args.follow)
    elif args.input == "queue":
        logger.warning("Message queue stub - reading from stdin as JSON array")
        data = json.loads(sys.stdin.read())
        if not isinstance(data, list):
            parser.error("Expected JSON array for queue stub")
        input_source = MessageQueueStubSource(data)
    else:
        parser.error(f"Unknown input type: {args.input}")

    run_mapper_service(
        input_source=input_source,
        source_name=args.source,
        database_url=args.database_url,
        mapping_paths=args.mapping_paths,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
