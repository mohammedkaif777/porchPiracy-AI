"""SQLModel table for detected packages."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlmodel import Field, SQLModel

from backend.schemas.enums import PackageStatus


def _utcnow() -> datetime:
    """Return the current UTC time (timezone aware)."""
    return datetime.now(UTC)


class Package(SQLModel, table=True):
    """A package seen by the vision pipeline."""

    __tablename__ = "packages"

    package_id: str = Field(sa_column=Column(String(64), primary_key=True))
    video_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    session_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    track_id: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    bbox: list[float] = Field(default_factory=list, sa_column=Column(JSON))
    confidence: float = Field(default=0.0, sa_column=Column(Float))
    status: str = Field(default=PackageStatus.DETECTED.value, sa_column=Column(String(32)))
    detected_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
