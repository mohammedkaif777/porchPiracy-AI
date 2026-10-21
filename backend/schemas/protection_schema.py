"""Protection session contract.

Frozen contract, see ``DEVELOPMENT.md`` section 5.4.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.enums import ProtectionState, SessionSource, ThreatLevel

Zone = list[list[float]]
"""A protection zone polygon as ``[[x, y], [x, y], ...]`` in pixel coordinates."""


class ProtectionStartRequest(BaseModel):
    """Body of ``POST /protection/start``."""

    model_config = ConfigDict(extra="forbid")

    package_track_id: int | None = None
    protection_zone: Zone | None = None


class SimulatedDeliveryRequest(BaseModel):
    """Body of ``POST /simulate/delivery``."""

    model_config = ConfigDict(extra="forbid")

    package_track_id: int | None = None
    protection_zone: Zone | None = None


class ProtectionSessionRead(BaseModel):
    """A protection session as exposed by the API."""

    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None
    state: ProtectionState = ProtectionState.IDLE
    source: SessionSource | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    threat_level: ThreatLevel = ThreatLevel.NONE
    package_track_id: int | None = None
    protection_zone: Zone | None = None
    seconds_remaining: int | None = None


class ProtectionEndResponse(BaseModel):
    """Response of ``POST /protection/end``."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    state: ProtectionState
    message: str
