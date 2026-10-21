"""Protection session endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from backend.api.dependencies import protection_manager
from backend.api.mappers import protection_to_schema
from backend.schemas.enums import SessionSource
from backend.schemas.protection_schema import (
    ProtectionEndResponse,
    ProtectionSessionRead,
    ProtectionStartRequest,
)
from backend.services.protection_service import ProtectionSessionManager

router = APIRouter(prefix="/protection", tags=["protection"])


@router.post("/start", response_model=ProtectionSessionRead, status_code=201)
def start_protection(
    body: ProtectionStartRequest | None = None,
    manager: ProtectionSessionManager = Depends(protection_manager),
) -> ProtectionSessionRead:
    """Start a new manual protection session."""
    now = datetime.now(UTC)
    payload = body or ProtectionStartRequest()
    record = manager.start_and_activate(
        source=SessionSource.MANUAL,
        package_track_id=payload.package_track_id,
        protection_zone=payload.protection_zone,
        now=now,
    )
    return protection_to_schema(record, now)


@router.post("/end", response_model=ProtectionEndResponse)
def end_protection(
    manager: ProtectionSessionManager = Depends(protection_manager),
) -> ProtectionEndResponse:
    """End the active protection session manually."""
    record = manager.end_session(datetime.now(UTC))
    return ProtectionEndResponse(
        session_id=record.session_id,
        state=record.state,
        message="Protection ended manually",
    )


@router.get("/status", response_model=ProtectionSessionRead)
def protection_status(
    manager: ProtectionSessionManager = Depends(protection_manager),
) -> ProtectionSessionRead:
    """Return the active protection session or an IDLE placeholder."""
    now = datetime.now(UTC)
    manager.check_timeout(now)
    active = manager.get_active_session()
    return protection_to_schema(active, now)
