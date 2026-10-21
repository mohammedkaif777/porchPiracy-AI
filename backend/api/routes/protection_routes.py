"""Protection session endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import protection_to_schema
from backend.core.config import Settings
from backend.core.logging_config import get_logger
from backend.schemas.enums import SessionSource
from backend.schemas.protection_schema import (
    ProtectionEndResponse,
    ProtectionSessionRead,
    ProtectionStartRequest,
)
from backend.services.protection_service import ProtectionSessionManager

logger = get_logger(__name__)

router = APIRouter(prefix="/protection", tags=["protection"])


@router.post("/start", response_model=ProtectionSessionRead, status_code=201)
def start_protection(
    body: ProtectionStartRequest,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> ProtectionSessionRead:
    """Start a new manual protection session."""
    now = datetime.now(UTC)
    manager = ProtectionSessionManager(session, timeout_minutes=settings.protection_timeout_minutes)
    record = manager.start_session(
        source=SessionSource.MANUAL,
        package_track_id=body.package_track_id,
        protection_zone=body.protection_zone,
        now=now,
    )
    return protection_to_schema(record, now)


@router.post("/end", response_model=ProtectionEndResponse)
def end_protection(
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> ProtectionEndResponse:
    """End the active protection session manually."""
    manager = ProtectionSessionManager(session, timeout_minutes=settings.protection_timeout_minutes)
    record = manager.end_session(datetime.now(UTC))
    return ProtectionEndResponse(
        session_id=record.session_id,
        state=record.state,
        message="Protection session ended.",
    )


@router.get("/status", response_model=ProtectionSessionRead)
def protection_status(
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> ProtectionSessionRead:
    """Return the active protection session or an IDLE placeholder."""
    now = datetime.now(UTC)
    manager = ProtectionSessionManager(session, timeout_minutes=settings.protection_timeout_minutes)
    manager.check_timeout(now)
    active = manager.get_active_session()
    return protection_to_schema(active, now)
