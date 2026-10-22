"""Notifications and Ring integration status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import notification_to_schema
from backend.core.config import Settings
from backend.integrations.notifications.dashboard_notifier import DashboardNotifier
from backend.integrations.ring import get_ring_integration
from backend.schemas.system_schema import NotificationRead, RingCapability, RingStatus

router = APIRouter(tags=["integrations"])


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    session: Session = Depends(db_session),
    incident_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[NotificationRead]:
    """Return the notification history."""
    notifier = DashboardNotifier(session)
    records = notifier.history(incident_id=incident_id, limit=limit)
    return [notification_to_schema(record) for record in records]


@router.get("/ring/status", response_model=RingStatus)
def ring_status(settings: Settings = Depends(app_settings)) -> RingStatus:
    """Return the honest status of the Ring integration."""
    adapter = get_ring_integration()
    device_status = adapter.get_device_status()
    configured = bool(getattr(adapter, "configured", True))
    if adapter.simulated:
        message = "Running on the local development adapter. No Ring device is connected."
    elif not configured:
        message = "RING_TOKEN is not set. The real adapter is selected but not connected."
    elif device_status.online:
        message = f"Connected to {device_status.name}."
    else:
        detail = device_status.raw.get("error") if isinstance(device_status.raw, dict) else None
        message = str(detail or "Ring adapter selected but the device is offline.")
    return RingStatus(
        mode=settings.ring_mode,
        adapter=adapter.name,
        connected=bool(device_status.online),
        simulated=adapter.simulated,
        capabilities=[
            RingCapability(
                name=str(cap.get("name")),
                supported=bool(cap.get("supported", False)),
                simulated=bool(cap.get("simulated", True)),
            )
            for cap in adapter.capabilities()
        ],
        device=device_status.to_dict(),
        message=message,
    )
