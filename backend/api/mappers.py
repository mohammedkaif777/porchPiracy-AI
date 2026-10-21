"""Conversions between the SQLModel tables and the API schemas."""

from __future__ import annotations

from backend.models.event import Event
from backend.models.incident import Incident
from backend.models.notification import Notification
from backend.models.protection_session import ProtectionSession
from backend.models.video import Video
from backend.schemas.enums import (
    IncidentStatus,
    NotificationChannel,
    PackageStatus,
    ProtectionState,
    ReasonCode,
    SessionSource,
    Severity,
    ThreatLevel,
    VideoStatus,
)
from backend.schemas.event_schema import EventCreate, EventRead
from backend.schemas.incident_schema import IncidentRead
from backend.schemas.package_schema import PackageRead
from backend.schemas.protection_schema import ProtectionSessionRead
from backend.schemas.system_schema import NotificationRead, VideoRead
from backend.services.protection_service import seconds_remaining, zone_from_record


def event_to_schema(record: Event) -> EventRead:
    """Convert an event row into its API representation."""
    return EventRead(
        event_id=record.event_id,
        session_id=record.session_id,
        type=record.type,
        timestamp_s=record.timestamp_s,
        frame_index=record.frame_index,
        track_ids=record.track_ids or {},
        confidence=record.confidence,
        bbox=record.bbox or {},
        metadata=record.metadata_ or {},
        created_at=record.created_at,
    )


def event_to_create(record: Event) -> EventCreate:
    """Convert an event row into the schema the rule engine consumes."""
    return EventCreate(
        event_id=record.event_id,
        session_id=record.session_id,
        type=record.type,
        timestamp_s=record.timestamp_s,
        frame_index=record.frame_index,
        track_ids=record.track_ids or {},
        confidence=record.confidence,
        bbox=record.bbox or {},
        metadata=record.metadata_ or {},
    )


def incident_to_schema(record: Incident) -> IncidentRead:
    """Convert an incident row into its API representation."""
    return IncidentRead(
        incident_id=record.incident_id,
        session_id=record.session_id,
        severity=record.severity,
        reason_codes=[ReasonCode(code) for code in record.reason_codes if _is_reason(code)],
        event_ids=list(record.event_ids or []),
        start_s=record.start_s,
        end_s=record.end_s,
        status=record.status,
        evidence_path=record.evidence_path,
        explanation=record.explanation,
        created_at=record.created_at,
    )


def notification_to_schema(record: Notification) -> NotificationRead:
    """Convert a notification row into its API representation."""
    return NotificationRead(
        notification_id=record.notification_id,
        incident_id=record.incident_id,
        channel=record.channel,
        message=record.message,
        simulated=bool(record.simulated),
        created_at=record.created_at,
    )


def video_to_schema(record: Video) -> VideoRead:
    """Convert a video row into its API representation."""
    return VideoRead(
        video_id=record.video_id,
        filename=record.filename,
        status=record.status,
        progress=record.progress,
        frames_processed=record.frames_processed,
        total_frames=record.total_frames,
        current_time_s=record.current_time_s,
        duration_s=record.duration_s,
        annotated_path=record.annotated_path,
        annotated_ready=bool(record.annotated_path),
        error=record.error,
        created_at=record.created_at,
    )


def protection_to_schema(record: ProtectionSession | None, now=None) -> ProtectionSessionRead:
    """Convert a protection session into its API representation."""
    if record is None:
        return ProtectionSessionRead()
    return ProtectionSessionRead(
        session_id=record.session_id,
        state=record.state,
        source=record.source,
        started_at=record.started_at,
        expires_at=record.expires_at,
        threat_level=record.threat_level,
        package_track_id=record.package_track_id,
        protection_zone=zone_from_record(record),
        seconds_remaining=(
            seconds_remaining(record.expires_at, now) if record.expires_at and now else None
        ),
    )


def package_to_schema(record) -> PackageRead:  # noqa: ANN001 - Package model
    """Convert a package row into its API representation."""
    return PackageRead(
        package_id=record.package_id,
        video_id=record.video_id,
        session_id=record.session_id,
        track_id=record.track_id,
        bbox=list(record.bbox or []),
        confidence=record.confidence,
        status=record.status,
        detected_at=record.detected_at,
    )


def _is_reason(code: str) -> bool:
    """Return whether a stored reason code is known."""
    return code in {member.value for member in ReasonCode}


__all__ = [
    "event_to_create",
    "event_to_schema",
    "incident_to_schema",
    "notification_to_schema",
    "package_to_schema",
    "protection_to_schema",
    "video_to_schema",
]

# Re-exported for convenience so route modules import from a single place.
ENUM_ALIASES = {
    "IncidentStatus": IncidentStatus,
    "NotificationChannel": NotificationChannel,
    "PackageStatus": PackageStatus,
    "ProtectionState": ProtectionState,
    "SessionSource": SessionSource,
    "Severity": Severity,
    "ThreatLevel": ThreatLevel,
    "VideoStatus": VideoStatus,
}
