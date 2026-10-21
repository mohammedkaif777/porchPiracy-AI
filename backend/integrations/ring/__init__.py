"""Ring integration package.

``RING_MODE`` selects the adapter:

* ``local`` -> :class:`~backend.integrations.ring.local_adapter.LocalAdapter`
  (development and tests, always labeled as simulated);
* ``real``  -> :class:`~backend.integrations.ring.adapter.RealAdapter`.
"""

from backend.integrations.ring.base import (
    ActionResult,
    DeviceStatus,
    RingEvent,
    RingIntegration,
)
from backend.integrations.ring.local_adapter import LocalAdapter

__all__ = [
    "ActionResult",
    "DeviceStatus",
    "LocalAdapter",
    "RingEvent",
    "RingIntegration",
    "get_ring_integration",
]


def get_ring_integration() -> RingIntegration:
    """Return the Ring adapter selected by the configuration."""
    from backend.core.config import get_settings  # noqa: PLC0415 - avoids an import cycle

    settings = get_settings()
    if settings.ring_mode == "real":
        from backend.integrations.ring.adapter import RealAdapter  # noqa: PLC0415 - lazy on purpose

        return RealAdapter(settings)
    return LocalAdapter(settings)
