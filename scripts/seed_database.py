"""Seed the database with mock events from ``samples/mock_events.json``.

Usage::

    python -m scripts.seed_database
    # or
    make seed
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import get_settings  # noqa: E402
from backend.core.db import create_db_and_tables, session_scope  # noqa: E402
from backend.core.logging_config import configure_logging, get_logger  # noqa: E402
from backend.schemas.enums import SessionSource  # noqa: E402
from backend.schemas.event_schema import EventCreate  # noqa: E402
from backend.services.pipeline_service import ingest_event  # noqa: E402
from backend.services.protection_service import ProtectionSessionManager  # noqa: E402

logger = get_logger(__name__)


def seed() -> None:
    """Load mock events and replay them through the ingestion pipeline."""
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_directories()
    create_db_and_tables()

    mock_path = settings.mock_events_path
    if not mock_path.is_file():
        logger.error("Mock events file not found: %s", mock_path)
        sys.exit(1)

    data = json.loads(mock_path.read_text(encoding="utf-8"))
    events = data.get("events", data) if isinstance(data, dict) else data
    if not isinstance(events, list):
        logger.error("Expected a list of events in %s", mock_path)
        sys.exit(1)

    logger.info("Seeding %d events from %s", len(events), mock_path)

    # Start a protection session for the seed run.
    with session_scope() as session:
        manager = ProtectionSessionManager(
            session, timeout_minutes=settings.protection_timeout_minutes,
        )
        active = manager.get_active_session()
        if active is None:
            active = manager.start_session(source=SessionSource.SIMULATED_DELIVERY)
        session_id = active.session_id
        logger.info("Using protection session %s", session_id)

    for index, raw in enumerate(events):
        raw["session_id"] = session_id
        payload = EventCreate(**raw)
        with session_scope() as session:
            result = ingest_event(session, payload, settings)
            status = "NEW INCIDENT" if result.incident_created else (
                "escalated" if result.incident else "ok"
            )
            logger.info(
                "[%d/%d] %s  threat=%s  %s",
                index + 1,
                len(events),
                payload.type.value,
                result.assessment.level.value,
                status,
            )

    logger.info("Seeding complete. %d events ingested.", len(events))


if __name__ == "__main__":
    seed()
