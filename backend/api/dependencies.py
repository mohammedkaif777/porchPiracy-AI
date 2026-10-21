"""FastAPI dependencies shared by the route modules."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlmodel import Session

from backend.core.config import Settings, get_settings
from backend.core.db import get_session
from backend.services.incident_service import IncidentService
from backend.services.protection_service import ProtectionSessionManager
from backend.services.response_service import ResponseService
from backend.services.threat_service import ThreatThresholds


def db_session() -> Iterator[Session]:
    """Yield a database session for the request."""
    yield from get_session()


def app_settings() -> Settings:
    """Return the application settings."""
    return get_settings()


def protection_manager(
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> ProtectionSessionManager:
    """Return a protection session manager bound to the request session."""
    return ProtectionSessionManager(session, timeout_minutes=settings.protection_timeout_minutes)


def incident_service(
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> IncidentService:
    """Return an incident service bound to the request session."""
    return IncidentService(session, cooldown_seconds=settings.incident_cooldown_seconds)


def response_service(
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> ResponseService:
    """Return a response service bound to the request session."""
    return ResponseService(session, settings)


def threat_thresholds(settings: Settings = Depends(app_settings)) -> ThreatThresholds:
    """Return the thresholds used by the rule engine."""
    return ThreatThresholds.from_settings(settings)
