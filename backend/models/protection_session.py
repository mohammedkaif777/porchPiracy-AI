"""SQLModel table for the protection session."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlmodel import Field, SQLModel

from backend.schemas.enums import ProtectionState, SessionSource, ThreatLevel


def _utcnow() -> datetime:
    """Return the current UTC time (timezone aware)."""
    return datetime.now(UTC)


class ProtectionSession(SQLModel, table=True):
    """One protection session. Only one session is active at a time in the MVP."""

    __tablename__ = "protection_sessions"

    session_id: str = Field(sa_column=Column(String(64), primary_key=True))
    state: str = Field(default=ProtectionState.IDLE.value, sa_column=Column(String(32)))
    source: str = Field(default=SessionSource.MANUAL.value, sa_column=Column(String(32)))
    threat_level: str = Field(default=ThreatLevel.NONE.value, sa_column=Column(String(32)))
    package_track_id: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    protection_zone: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    started_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    end_reason: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    video_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
