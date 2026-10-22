"""Simulated delivery endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import protection_to_schema
from backend.core.config import Settings
from backend.core.logging_config import get_logger
from backend.schemas.enums import SessionSource
from backend.schemas.protection_schema import ProtectionSessionRead, SimulatedDeliveryRequest
from backend.services.protection_service import ProtectionSessionManager

logger = get_logger(__name__)

router = APIRouter(prefix="/simulate", tags=["simulate"])


@router.post("/delivery", response_model=ProtectionSessionRead, status_code=201)
def simulate_delivery(
    body: SimulatedDeliveryRequest,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> ProtectionSessionRead:
    """Simulate a package delivery, starting a protection session.

    Returns HTTP 409 when a session is already active.
    """
    now = datetime.now(UTC)
    manager = ProtectionSessionManager(session, timeout_minutes=settings.protection_timeout_minutes)
    record = manager.start_session(
        source=SessionSource.SIMULATED_DELIVERY,
        package_track_id=body.package_track_id,
        protection_zone=body.protection_zone,
        now=now,
    )
    return protection_to_schema(record, now)
