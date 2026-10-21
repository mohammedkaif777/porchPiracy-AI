"""Dashboard notifier: writes the notification history to the database.

This notifier is always enabled. It is the record the dashboard shows, and it
is the reason the notification history is available even when no external
channel is configured.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Session, select

from backend.core.logging_config import get_logger
from backend.integrations.notifications.base import NotificationPayload, Notifier
from backend.models.notification import Notification
from backend.schemas.enums import NotificationChannel

logger = get_logger(__name__)


class DashboardNotifier(Notifier):
    """Persists notifications so the dashboard can show the history."""

    channel = NotificationChannel.DASHBOARD

    def __init__(self, session: Session) -> None:
        self._session = session

    def notify(self, payload: NotificationPayload) -> bool:
        """Store the notification in the database."""
        record = Notification(
            notification_id=str(uuid.uuid4()),
            incident_id=payload.incident_id,
            session_id=payload.session_id,
            channel=payload.channel.value,
            message=payload.message,
            simulated=payload.simulated,
            detail=payload.detail,
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        self._session.commit()
        logger.info(
            "Notification stored channel=%s incident=%s simulated=%s",
            payload.channel.value,
            payload.incident_id,
            payload.simulated,
        )
        return True

    def history(self, incident_id: str | None = None, limit: int = 100) -> list[Notification]:
        """Return the notification history, newest first."""
        statement = select(Notification)
        if incident_id:
            statement = statement.where(Notification.incident_id == incident_id)
        statement = statement.order_by(Notification.created_at.desc()).limit(limit)  # type: ignore[union-attr]
        return list(self._session.exec(statement).all())
