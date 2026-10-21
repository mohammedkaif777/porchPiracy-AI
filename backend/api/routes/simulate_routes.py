"""Simulated delivery endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from backend.api.dependencies import protection_manager
from backend.api.mappers import protection_to_schema
from backend.schemas.enums import SessionSource
from backend.schemas.protection_schema import ProtectionSessionRead, SimulatedDeliveryRequest
from backend.services.protection_service import ProtectionSessionManager

router = APIRouter(prefix="/simulate", tags=["simulate"])


@router.post("/delivery", response_model=ProtectionSessionRead, status_code=201)
def simulate_delivery(
    body: SimulatedDeliveryRequest | None = None,
    manager: ProtectionSessionManager = Depends(protection_manager),
) -> ProtectionSessionRead:
    """Simulate a package delivery and activate protection.

    Returns HTTP 409 when a session is already active. The source is
    ``SIMULATED_DELIVERY`` so the UI can label it Simulated.
    """
    now = datetime.now(UTC)
    payload = body or SimulatedDeliveryRequest()
    record = manager.start_and_activate(
        source=SessionSource.SIMULATED_DELIVERY,
        package_track_id=payload.package_track_id,
        protection_zone=payload.protection_zone,
        now=now,
    )
    return protection_to_schema(record, now)
