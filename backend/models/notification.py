"""SQLModel table for homeowner notifications and deterrent records."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, String, Text
from sqlmodel import Field, SQLModel

from backend.schemas.enums import NotificationChannel


def _utcnow() -> datetime:
    """Return the current UTC time (timezone aware)."""
    return datetime.now(UTC)


class Notification(SQLModel, table=True):
    """A notification delivered to the homeowner or logged as a deterrent.

    ``simulated`` is stored on the record so a simulated feature can never be
    presented as real, even if the UI forgets to render the badge.
    """

    __tablename__ = "notifications"

    notification_id: str = Field(sa_column=Column(String(64), primary_key=True))
    incident_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    session_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    channel: str = Field(default=NotificationChannel.DASHBOARD.value, sa_column=Column(String(32)))
    message: str = Field(default="", sa_column=Column(Text))
    simulated: bool = Field(default=True, sa_column=Column(Boolean))
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
