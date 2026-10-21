"""Base contract of the Ring integration.

The rest of the application never talks to Ring directly. It talks to
:class:`RingIntegration`, so the AI pipeline does not change when the available
Ring capabilities change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.schemas.enums import AllowedAction


@dataclass
class DeviceStatus:
    """Status of the Ring device the system is connected to."""

    name: str = "Unknown device"
    online: bool = False
    battery: int | None = None
    signal: str | None = None
    last_seen: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    simulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "name": self.name,
            "online": self.online,
            "battery": self.battery,
            "signal": self.signal,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "simulated": self.simulated,
        }


@dataclass
class RingEvent:
    """An event reported by a Ring device (motion, delivery, button press...)."""

    event_id: str
    event_type: str
    timestamp: datetime
    device_name: str = "Unknown device"
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    simulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "device_name": self.device_name,
            "description": self.description,
            "simulated": self.simulated,
        }


@dataclass
class ActionResult:
    """Outcome of triggering an allowlisted action on a device."""

    action: AllowedAction
    success: bool
    simulated: bool
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "action": self.action.value,
            "success": self.success,
            "simulated": self.simulated,
            "message": self.message,
            "detail": dict(self.detail),
        }


class RingIntegration(ABC):
    """Abstract Ring integration.

    Implementations expose the device status, the recent events and the actions
    the environment actually supports. The method names are illustrative and may
    be adapted to the real SDK.
    """

    #: Name reported by ``GET /ring/status``.
    name: str = "RingIntegration"

    #: True when the adapter only simulates the Ring behaviour.
    simulated: bool = True

    @abstractmethod
    def get_device_status(self) -> DeviceStatus:
        """Return the status of the connected device."""

    @abstractmethod
    def get_recent_events(self, limit: int = 20) -> list[RingEvent]:
        """Return the most recent events reported by the device."""

    @abstractmethod
    def trigger_supported_action(self, action: AllowedAction) -> ActionResult:
        """Trigger an allowlisted action on the device."""

    def capabilities(self) -> list[dict[str, Any]]:
        """Return the capabilities of this adapter and whether they are real."""
        return [
            {"name": "device_status", "supported": True, "simulated": self.simulated},
            {"name": "recent_events", "supported": True, "simulated": self.simulated},
            {"name": "trigger_action", "supported": True, "simulated": self.simulated},
        ]

    def is_connected(self) -> bool:
        """Return whether the integration can currently reach its backend."""
        try:
            self.get_device_status()
        except Exception:
            return False
        return True
