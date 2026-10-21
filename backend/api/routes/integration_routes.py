"""Notifications and Ring integration status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import notification_to_schema
from backend.core.config import Settings
from backend.core.logging_config import get_logger
from backend.integrations.notifications.dashboard_notifier import DashboardNotifier
from backend.integrations.ring.local_adapter import LocalAdapter
from backend.schemas.system_schema import NotificationRead, RingCapability, RingStatus

logger = get_logger(__name__)

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
    if settings.ring_mode == "real":
        try:
            from backend.integrations.ring.adapter import RealAdapter  # noqa: PLC0415

            adapter = RealAdapter(settings)
        except Exception:
            adapter = LocalAdapter(settings)  # type: ignore[assignment]
    else:
        adapter = LocalAdapter(settings)  # type: ignore[assignment]

    connected = adapter.is_connected()
    device = None
    if connected:
        try:
            device = adapter.get_device_status().to_dict()
        except Exception:
            pass

    caps = adapter.capabilities()
    return RingStatus(
        mode=settings.ring_mode,
        adapter=adapter.name,
        connected=connected,
        simulated=adapter.simulated,
        capabilities=[
            RingCapability(
                name=str(cap["name"]),
                supported=bool(cap.get("supported", False)),
                simulated=bool(cap.get("simulated", True)),
            )
            for cap in caps
        ],
        device=device,
        message=(
            f"Ring integration is running in {settings.ring_mode} mode "
            f"via the {adapter.name}."
        ),
    )
