"""System-level contracts: videos, notifications, settings, evidence and Ring status.

These are not part of the original frozen contract list in ``DEVELOPMENT.md``
section 5, but they describe the remaining API payloads. They follow the same
rules: change by announcement, same PR.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.enums import (
    AllowedAction,
    NotificationChannel,
    VideoStatus,
)


class HealthResponse(BaseModel):
    """Response of ``GET /health``."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    service: str = "porchpiracyai"
    version: str = "0.1.0"


class VideoRead(BaseModel):
    """An uploaded video and the state of its analysis run."""

    model_config = ConfigDict(extra="forbid")

    video_id: str
    filename: str
    status: VideoStatus = VideoStatus.UPLOADED
    progress: float = 0.0
    frames_processed: int = 0
    total_frames: int = 0
    current_time_s: float = 0.0
    duration_s: float = 0.0
    annotated_path: str | None = None
    annotated_ready: bool = False
    error: str | None = None
    created_at: datetime | None = None


class VideoAnalyzeResponse(BaseModel):
    """Response of ``POST /videos/{id}/analyze``."""

    model_config = ConfigDict(extra="forbid")

    video_id: str
    status: VideoStatus
    message: str


class NotificationRead(BaseModel):
    """A homeowner notification or deterrent record."""

    model_config = ConfigDict(extra="forbid")

    notification_id: str
    incident_id: str | None = None
    channel: NotificationChannel
    message: str
    simulated: bool = True
    created_at: datetime | None = None


class SettingsRead(BaseModel):
    """Tunable thresholds exposed by ``GET /settings``."""

    model_config = ConfigDict(extra="forbid")

    protection_timeout_minutes: int
    loiter_threshold_seconds: float
    near_package_distance_px: float
    frame_stride: int
    detection_conf_threshold: float
    incident_cooldown_seconds: float
    ring_mode: str
    llm_enabled: bool


class SettingsUpdate(BaseModel):
    """Body of ``PUT /settings``. Only supplied fields are changed."""

    model_config = ConfigDict(extra="forbid")

    protection_timeout_minutes: int | None = Field(default=None, ge=1, le=10080)
    loiter_threshold_seconds: float | None = Field(default=None, ge=0.5, le=3600)
    near_package_distance_px: float | None = Field(default=None, ge=1, le=5000)
    frame_stride: int | None = Field(default=None, ge=1, le=30)
    detection_conf_threshold: float | None = Field(default=None, ge=0.01, le=0.99)
    incident_cooldown_seconds: float | None = Field(default=None, ge=0, le=3600)


class EvidenceKeyFrame(BaseModel):
    """One key frame belonging to an evidence bundle."""

    model_config = ConfigDict(extra="forbid")

    path: str
    timestamp_s: float
    label: str = "key_frame"


class EvidenceRead(BaseModel):
    """The evidence bundle of an incident."""

    model_config = ConfigDict(extra="forbid")

    incident_id: str
    clip_path: str | None = None
    clip_start_s: float | None = None
    clip_end_s: float | None = None
    key_frames: list[EvidenceKeyFrame] = Field(default_factory=list)
    faces_blurred: bool = False
    metadata: dict = Field(default_factory=dict)


class RingCapability(BaseModel):
    """One capability of the Ring integration and whether it is real."""

    model_config = ConfigDict(extra="forbid")

    name: str
    supported: bool
    simulated: bool


class RingStatus(BaseModel):
    """Honest status of the Ring integration."""

    model_config = ConfigDict(extra="forbid")

    mode: str
    adapter: str
    connected: bool
    simulated: bool
    capabilities: list[RingCapability] = Field(default_factory=list)
    device: dict | None = None
    message: str


class ActionResult(BaseModel):
    """Result of triggering an allowlisted action on a device."""

    model_config = ConfigDict(extra="forbid")

    action: AllowedAction
    success: bool
    simulated: bool
    message: str
    detail: dict = Field(default_factory=dict)
