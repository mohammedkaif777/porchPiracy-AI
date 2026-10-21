"""Package contract: the physical parcel the system is protecting."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.enums import PackageStatus


class PackageRead(BaseModel):
    """A detected package as exposed by the API."""

    model_config = ConfigDict(extra="forbid")

    package_id: str
    video_id: str | None = None
    session_id: str | None = None
    track_id: int | None = None
    bbox: list[float] = Field(default_factory=list)
    confidence: float = 0.0
    status: PackageStatus = PackageStatus.DETECTED
    detected_at: datetime | None = None
