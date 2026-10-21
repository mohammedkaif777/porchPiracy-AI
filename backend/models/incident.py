"""SQLModel table for incidents."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, String, Text
from sqlmodel import Field, SQLModel

from backend.schemas.enums import IncidentStatus, Severity


def _utcnow() -> datetime:
    """Return the current UTC time (timezone aware)."""
    return datetime.now(UTC)


class Incident(SQLModel, table=True):
    """An escalated incident. Created only by the deterministic rule engine."""

    __tablename__ = "incidents"

    incident_id: str = Field(sa_column=Column(String(64), primary_key=True))
    session_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    severity: str = Field(default=Severity.LOW.value, sa_column=Column(String(16)))
    reason_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    event_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    person_track_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    start_s: float = Field(default=0.0, sa_column=Column(Float))
    end_s: float = Field(default=0.0, sa_column=Column(Float))
    status: str = Field(default=IncidentStatus.OPEN.value, sa_column=Column(String(16)))
    evidence_path: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    evidence_metadata: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    explanation: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    review_note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    video_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
