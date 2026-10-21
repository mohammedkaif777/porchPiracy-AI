"""Local development adapter for the Ring integration.

It never contacts Ring. It simulates a device so the rest of the application
can be developed and tested, and it is always labeled as simulated in the UI
and in the API.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.core.config import Settings, get_settings
from backend.core.logging_config import get_logger
from backend.integrations.ring.base import ActionResult, DeviceStatus, RingEvent, RingIntegration
from backend.schemas.enums import AllowedAction

logger = get_logger(__name__)


class LocalAdapter(RingIntegration):
    """Simulated Ring adapter used for development, tests and the demo."""

    name = "LocalAdapter"
    simulated = True

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_device_status(self) -> DeviceStatus:
        """Return a simulated device status."""
        return DeviceStatus(
            name="Front Door (Local Adapter)",
            online=True,
            battery=82,
            signal="good",
            last_seen=datetime.now(UTC),
            raw={"adapter": self.name, "note": "Simulated device status."},
            simulated=True,
        )

    def get_recent_events(self, limit: int = 20) -> list[RingEvent]:
        """Return simulated device events, enriched with the mock event stream."""
        events: list[RingEvent] = []
        now = datetime.now(UTC)

        for index, sample in enumerate(self._load_mock_events()[:limit]):
            events.append(
                RingEvent(
                    event_id=str(sample.get("event_id") or uuid.uuid4()),
                    event_type=str(sample.get("type", "MOTION")),
                    timestamp=now - timedelta(seconds=60 * (index + 1)),
                    device_name="Front Door (Local Adapter)",
                    description=f"Simulated {sample.get('type', 'motion').lower().replace('_', ' ')} event.",
                    raw={"source": "samples/mock_events.json", "simulated": True},
                    simulated=True,
                )
            )
        return events

    def trigger_supported_action(self, action: AllowedAction) -> ActionResult:
        """Simulate an allowlisted action."""
        logger.info("Simulated Ring action triggered: %s", action.value)
        return ActionResult(
            action=action,
            success=True,
            simulated=True,
            message=f"Simulated {action.value} on the local adapter. No real device was contacted.",
            detail={"adapter": self.name, "action": action.value},
        )

    def capabilities(self) -> list[dict[str, object]]:
        """Return the simulated capabilities of the local adapter."""
        return [
            {"name": "device_status", "supported": True, "simulated": True},
            {"name": "recent_events", "supported": True, "simulated": True},
            {"name": "trigger_action", "supported": True, "simulated": True},
        ]

    def _load_mock_events(self) -> list[dict]:
        """Load the mock event stream, ignoring a missing or invalid file."""
        path = Path(self._settings.mock_events_path)
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read the mock events from %s", path)
            return []
        if isinstance(data, dict):
            data = data.get("events", [])
        return list(data) if isinstance(data, list) else []
