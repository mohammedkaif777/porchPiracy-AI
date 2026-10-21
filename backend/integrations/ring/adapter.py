"""Real Ring adapter.

This adapter is the only place that talks to the Ring API. It is selected with
``RING_MODE=real``.

Important: the exact endpoints, authentication scheme and supported actions must
be verified against the documentation the organisers provide. The constants below
follow the public Ring v2 shape and are kept in one place so they can be
adjusted in a single file once the real capabilities are confirmed (see the
validation checklist in ``DEVELOPMENT.md`` section 8).

When the credentials are missing or the API is unreachable the adapter degrades
gracefully: the status endpoint reports the problem and the rest of the
application keeps working.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from backend.core.config import Settings, get_settings
from backend.core.logging_config import get_logger
from backend.integrations.ring.base import ActionResult, DeviceStatus, RingEvent, RingIntegration
from backend.schemas.enums import AllowedAction

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.ring.com"
DEVICES_PATH = "/v2/devices"
EVENTS_PATH = "/v2/events"
SNAPSHOT_PATH = "/v2/snapshot"

#: Actions mapped onto the Ring endpoint that performs them. An action that is
#: not listed here is simply not supported and is never attempted.
ACTION_PATHS: dict[AllowedAction, str] = {
    AllowedAction.SNAPSHOT: SNAPSHOT_PATH,
}


class RealAdapter(RingIntegration):
    """Adapter talking to the real Ring API."""

    name = "RealAdapter"
    simulated = False

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base_url = (self._settings.ring_base_url or DEFAULT_BASE_URL).rstrip("/")

    # ------------------------------------------------------------------ helpers

    @property
    def configured(self) -> bool:
        """True when the credentials needed to reach Ring are present."""
        return bool(self._settings.ring_token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.ring_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a GET request against the Ring API."""
        response = httpx.get(
            f"{self._base_url}{path}",
            headers=self._headers(),
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------- API

    def get_device_status(self) -> DeviceStatus:
        """Return the status of the first available Ring device."""
        if not self.configured:
            return DeviceStatus(
                name="Ring (not configured)",
                online=False,
                raw={"error": "RING_TOKEN is not set"},
                simulated=False,
            )

        payload = self._get(DEVICES_PATH)
        devices = payload.get("device_info", payload) if isinstance(payload, dict) else []
        if not devices:
            return DeviceStatus(
                name="Ring (no device)",
                online=False,
                raw={"error": "The account returned no device"},
                simulated=False,
            )

        device = devices[0]
        return DeviceStatus(
            name=str(device.get("description") or device.get("device_name") or "Ring device"),
            online=bool(device.get("on_data", {}).get("status") == "online"),
            battery=device.get("health", {}).get("battery_percentage"),
            signal=str(device.get("wifi_signal", {}).get("strength", "")) or None,
            last_seen=datetime.now(UTC),
            raw=device,
            simulated=False,
        )

    def get_recent_events(self, limit: int = 20) -> list[RingEvent]:
        """Return the most recent events reported by the Ring account."""
        if not self.configured:
            return []

        payload = self._get(EVENTS_PATH, params={"limit": limit})
        raw_events = payload.get("events", []) if isinstance(payload, dict) else []
        events: list[RingEvent] = []
        for raw in raw_events[:limit]:
            events.append(
                RingEvent(
                    event_id=str(raw.get("id", "")),
                    event_type=str(raw.get("type", "UNKNOWN")),
                    timestamp=_parse_timestamp(raw.get("created_at")),
                    device_name=str(raw.get("device_name", "Ring device")),
                    description=str(raw.get("description", "")),
                    raw=raw,
                    simulated=False,
                )
            )
        return events

    def trigger_supported_action(self, action: AllowedAction) -> ActionResult:
        """Trigger an allowlisted action on the Ring device.

        Only the actions listed in ``ACTION_PATHS`` are attempted. Anything else
        returns a clear "not supported" result instead of guessing an endpoint.
        """
        if not self.configured:
            return ActionResult(
                action=action,
                success=False,
                simulated=False,
                message="Ring is not configured (RING_TOKEN is missing). No action was sent.",
            )

        path = ACTION_PATHS.get(action)
        if path is None:
            return ActionResult(
                action=action,
                success=False,
                simulated=False,
                message=f"The action {action.value} is not supported by this Ring integration.",
            )

        try:
            payload = self._get(path)
        except Exception as exc:
            logger.warning("Ring action %s failed: %s", action.value, exc)
            return ActionResult(
                action=action,
                success=False,
                simulated=False,
                message=f"Ring rejected the action: {exc}",
            )

        return ActionResult(
            action=action,
            success=True,
            simulated=False,
            message=f"{action.value} was sent to the Ring device.",
            detail=payload if isinstance(payload, dict) else {},
        )

    def capabilities(self) -> list[dict[str, Any]]:
        """Return the capabilities of the real adapter."""
        return [
            {"name": "device_status", "supported": True, "simulated": False},
            {"name": "recent_events", "supported": True, "simulated": False},
            {
                "name": "trigger_action",
                "supported": bool(ACTION_PATHS),
                "simulated": False,
            },
        ]


def _parse_timestamp(value: Any) -> datetime:
    """Parse a Ring timestamp, falling back to now."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)
