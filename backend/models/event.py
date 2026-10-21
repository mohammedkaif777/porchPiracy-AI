"""SQLModel table for vision events."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlmodel import Field, SQLModel

from backend.schemas.enums import EventType


def _utcnow() -> datetime:
    """Return the current UTC time (timezone aware)."""
    return datetime.now(UTC)


class Event(SQLModel, table=True):
    """A single event produced by the vision pipeline."""

    __tablename__ = "events"

    event_id: str = Field(sa_column=Column(String(64), primary_key=True))
    session_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    type: str = Field(default=EventType.PACKAGE_DETECTED.value, sa_column=Column(String(64)))
    timestamp_s: float = Field(default=0.0, sa_column=Column(Float))
    frame_index: int = Field(default=0, sa_column=Column(Integer))
    track_ids: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: float = Field(default=1.0, sa_column=Column(Float))
    bbox: dict[str, list[float]] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    video_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
