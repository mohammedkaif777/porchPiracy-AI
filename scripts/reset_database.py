"""Delete and recreate the SQLite database file.

Usage::

    python -m scripts.reset_database
    # or
    make reset-db
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import get_settings  # noqa: E402
from backend.core.db import create_db_and_tables  # noqa: E402
from backend.core.logging_config import configure_logging, get_logger  # noqa: E402

logger = get_logger(__name__)


def reset() -> None:
    """Delete and recreate the database."""
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_directories()

    db_url = settings.database_url
    prefix = "sqlite:///"
    if db_url.startswith(prefix):
        db_path = Path(db_url[len(prefix):])
        if db_path.is_file():
            db_path.unlink()
            logger.info("Deleted database file: %s", db_path)
        else:
            logger.info("Database file does not exist yet: %s", db_path)
    else:
        logger.warning("Non-SQLite database URL, cannot delete file: %s", db_url)

    create_db_and_tables()
    logger.info("Database recreated.")


if __name__ == "__main__":
    reset()
