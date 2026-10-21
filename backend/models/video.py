"""SQLModel table for uploaded videos and their analysis runs."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlmodel import Field, SQLModel

from backend.schemas.enums import VideoStatus


def _utcnow() -> datetime:
    """Return the current UTC time (timezone aware)."""
    return datetime.now(UTC)


class Video(SQLModel, table=True):
    """An uploaded video plus the progress of its analysis run."""

    __tablename__ = "videos"

    video_id: str = Field(sa_column=Column(String(64), primary_key=True))
    filename: str = Field(sa_column=Column(String(255)))
    path: str = Field(sa_column=Column(String(512)))
    status: str = Field(default=VideoStatus.UPLOADED.value, sa_column=Column(String(32)))
    progress: float = Field(default=0.0, sa_column=Column(Float))
    frames_processed: int = Field(default=0, sa_column=Column(Integer))
    total_frames: int = Field(default=0, sa_column=Column(Integer))
    current_time_s: float = Field(default=0.0, sa_column=Column(Float))
    duration_s: float = Field(default=0.0, sa_column=Column(Float))
    annotated_path: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
