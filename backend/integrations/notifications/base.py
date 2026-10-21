"""Base contract of the notification layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from backend.schemas.enums import NotificationChannel


@dataclass
class NotificationPayload:
    """A message to deliver to the homeowner."""

    message: str
    channel: NotificationChannel = NotificationChannel.DASHBOARD
    incident_id: str | None = None
    session_id: str | None = None
    simulated: bool = True
    detail: dict[str, Any] = field(default_factory=dict)


class Notifier(ABC):
    """Delivers a notification to one channel."""

    channel: NotificationChannel = NotificationChannel.DASHBOARD

    @abstractmethod
    def notify(self, payload: NotificationPayload) -> bool:
        """Deliver the payload. Returns True when the delivery succeeded."""

    def available(self) -> bool:
        """Return whether this notifier can currently deliver messages."""
        return True
