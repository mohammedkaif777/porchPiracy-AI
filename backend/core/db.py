"""Database engine, session factory and schema creation.

The application uses SQLite through SQLModel. Engine creation is lazy so that
importing this module never touches the filesystem.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from backend.core.config import get_settings

_engine: Engine | None = None


def _ensure_sqlite_directory(url: str) -> None:
    """Create the parent directory of a SQLite file URL if it is missing."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return
    raw_path = url[len(prefix) :]
    if not raw_path or raw_path == ":memory:":
        return
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the given (or configured) database URL."""
    settings = get_settings()
    target_url = url or settings.database_url
    _ensure_sqlite_directory(target_url)

    connect_args: dict[str, object] = {}
    if target_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(target_url, connect_args=connect_args, echo=False)

    if target_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def set_engine(engine: Engine | None) -> None:
    """Replace the process-wide engine. Used by the test suite.

    Pass ``None`` to drop the engine so the next call to :func:`get_engine`
    creates a fresh one.
    """
    global _engine
    _engine = engine


def create_db_and_tables(engine: Engine | None = None) -> Engine:
    """Create every SQLModel table. Safe to call repeatedly."""
    target = engine or get_engine()
    import backend.models  # noqa: F401  (import registers the tables)

    SQLModel.metadata.create_all(target)
    return target


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager yielding a session and committing on success."""
    with Session(get_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
