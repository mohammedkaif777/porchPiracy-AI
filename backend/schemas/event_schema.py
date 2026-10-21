"""Event contract shared between the vision pipeline and the backend.

Frozen contract, see ``DEVELOPMENT.md`` section 5.2.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.schemas.enums import EventType

BBox = list[float]
"""A bounding box as ``[x1, y1, x2, y2]`` in pixels."""


def _validate_bbox(value: BBox) -> BBox:
    if len(value) != 4:
        raise ValueError("bbox must contain exactly 4 numbers: [x1, y1, x2, y2]")
    if value[2] < value[0] or value[3] < value[1]:
        raise ValueError("bbox must satisfy x2 >= x1 and y2 >= y1")
    return [float(v) for v in value]


class Detection(BaseModel):
    """A single object detection in one frame."""

    model_config = ConfigDict(extra="forbid")

    cls: str = Field(description="Object class: 'person' or 'package'.")
    bbox: BBox = Field(description="Bounding box [x1, y1, x2, y2] in pixels.")
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("bbox")
    @classmethod
    def _check_bbox(cls, value: BBox) -> BBox:
        return _validate_bbox(value)


class Track(BaseModel):
    """A tracked object with a stable id inside a single video."""

    model_config = ConfigDict(extra="forbid")

    track_id: int
    cls: str
    bbox: BBox
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("bbox")
    @classmethod
    def _check_bbox(cls, value: BBox) -> BBox:
        return _validate_bbox(value)

    @property
    def center(self) -> tuple[float, float]:
        """Return the centroid ``(cx, cy)`` of the tracked box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class EventCreate(BaseModel):
    """Payload accepted by ``POST /events`` and emitted by the vision pipeline."""

    model_config = ConfigDict(extra="forbid")

    event_id: str | None = Field(default=None, description="Server generated when omitted.")
    session_id: str | None = Field(default=None)
    type: EventType
    timestamp_s: float = Field(ge=0.0, description="Seconds from the start of the video.")
    frame_index: int = Field(default=0, ge=0)
    track_ids: dict[str, int] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bbox: dict[str, BBox] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bbox")
    @classmethod
    def _check_bbox_map(cls, value: dict[str, BBox]) -> dict[str, BBox]:
        return {key: _validate_bbox(box) for key, box in value.items()}


class EventRead(EventCreate):
    """A persisted event as returned by the API."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    created_at: datetime | None = None
