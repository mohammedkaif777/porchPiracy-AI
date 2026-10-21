"""Incident contract shared between the backend, the dashboard and the exporters.

Frozen contract, see ``DEVELOPMENT.md`` section 5.3.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.schemas.enums import IncidentStatus, ReasonCode, Severity, ThreatLevel


class IncidentCreate(BaseModel):
    """Internal payload used to open a new incident."""

    model_config = ConfigDict(extra="forbid")

    incident_id: str
    session_id: str | None = None
    severity: Severity
    reason_codes: list[ReasonCode] = Field(min_length=1)
    event_ids: list[str] = Field(min_length=1)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(ge=0.0)
    status: IncidentStatus = IncidentStatus.OPEN


class IncidentRead(BaseModel):
    """A stored incident as exposed by the API."""

    model_config = ConfigDict(extra="forbid")

    incident_id: str
    session_id: str | None = None
    severity: Severity
    reason_codes: list[ReasonCode]
    event_ids: list[str]
    start_s: float
    end_s: float
    status: IncidentStatus
    evidence_path: str | None = None
    explanation: str | None = None
    created_at: datetime | None = None


class IncidentReviewRequest(BaseModel):
    """Body of ``POST /incidents/{id}/review``."""

    model_config = ConfigDict(extra="forbid")

    status: IncidentStatus = Field(
        default=IncidentStatus.REVIEWED,
        description="REVIEWED or DISMISSED. OPEN is not a valid review outcome.",
    )
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _must_be_a_review_outcome(cls, value: IncidentStatus) -> IncidentStatus:
        if value is IncidentStatus.OPEN:
            raise ValueError("status must be REVIEWED or DISMISSED")
        return value


class IncidentDetail(BaseModel):
    """Incident plus the events that triggered it and its evidence bundle."""

    model_config = ConfigDict(extra="forbid")

    incident: IncidentRead
    events: list[dict] = Field(default_factory=list)
    evidence: dict | None = None


class ThreatAssessment(BaseModel):
    """Output of the deterministic threat rule engine.

    Produced by ``backend.services.threat_service.assess_threat`` from an
    ordered event sequence. It never touches the database or the clock.
    """

    model_config = ConfigDict(extra="forbid")

    level: ThreatLevel = ThreatLevel.NONE
    severity: Severity | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    should_create_incident: bool = False
    event_ids: list[str] = Field(default_factory=list)
    person_track_ids: list[int] = Field(default_factory=list)
    start_s: float | None = None
    end_s: float | None = None
    detail: dict = Field(default_factory=dict)
