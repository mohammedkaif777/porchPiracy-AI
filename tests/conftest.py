"""Shared test fixtures for the porchPiracyAI test suite.

Every test gets a temporary in-memory SQLite database and a fresh settings
override. No network, no filesystem beyond the temp dir, no sleeps.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Override the database URL and env BEFORE importing anything from the backend.
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory
os.environ["RING_MODE"] = "local"
os.environ["LLM_ENABLED"] = "false"
os.environ["USE_MOCK"] = "true"

from backend.core.config import Settings, reload_settings  # noqa: E402
from backend.core.db import set_engine  # noqa: E402


@pytest.fixture(autouse=True)
def _test_settings() -> Iterator[None]:
    """Ensure settings are reloaded fresh for each test."""
    reload_settings()
    yield
    reload_settings()


@pytest.fixture(autouse=True)
def engine() -> Iterator[Engine]:
    """Create a fresh in-memory SQLite engine with all tables."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import backend.models  # noqa: F401 — registers the tables

    SQLModel.metadata.create_all(eng)
    set_engine(eng)
    yield eng
    set_engine(None)


@pytest.fixture()
def session(engine: Engine) -> Iterator[Session]:
    """Yield a session bound to the in-memory test engine."""
    with Session(engine) as sess:
        yield sess


@pytest.fixture()
def settings() -> Settings:
    """Return the test settings."""
    return reload_settings()


@pytest.fixture()
def client(engine: Engine) -> Iterator[TestClient]:
    """Return a TestClient bound to the FastAPI app with the test database."""
    from main import app  # noqa: E402, PLC0415

    with TestClient(app) as tc:
        yield tc
