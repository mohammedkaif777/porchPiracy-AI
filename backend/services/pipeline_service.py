"""Event ingestion pipeline.

One function turns a raw event into the full consequence chain:

``persist event -> update the protection state machine -> assess the threat ->
maybe create or escalate an incident -> run the response``

Both the HTTP endpoint (``POST /events``) and the background analysis task use
it, so the behaviour is identical in both paths.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, select

from backend.core.config import Settings, get_settings
from backend.core.logging_config import get_logger
from backend.models.event import Event
from backend.models.incident import Incident
from backend.models.video import Video
from backend.schemas.enums import EventType
from backend.schemas.event_schema import EventCreate
from backend.schemas.incident_schema import ThreatAssessment
from backend.services.incident_service import IncidentService
from backend.services.protection_service import ProtectionSessionManager
from backend.services.response_service import ResponseService
from backend.services.threat_service import ThreatThresholds, assess_threat

logger = get_logger(__name__)


@dataclass
class IngestResult:
    """Outcome of ingesting one event."""

    event: Event
    assessment: ThreatAssessment
    incident: Incident | None = None
    incident_created: bool = False


def ingest_event(
    session: Session,
    payload: EventCreate,
    settings: Settings | None = None,
    video_id: str | None = None,
) -> IngestResult:
    """Persist an event and run the decision chain it triggers.

    Args:
        session: Database session.
        payload: The event to ingest.
        settings: Application settings.
        video_id: Video the event belongs to, when known.

    Returns:
        An :class:`IngestResult` with the stored event, the threat assessment and
        the incident when one was created or escalated.
    """
    config = settings or get_settings()
    now = datetime.now(UTC)

    record = Event(
        event_id=payload.event_id or str(uuid.uuid4()),
        session_id=payload.session_id,
        type=payload.type.value,
        timestamp_s=payload.timestamp_s,
        frame_index=payload.frame_index,
        track_ids=payload.track_ids or {},
        confidence=payload.confidence,
        bbox=payload.bbox or {},
        metadata_=payload.metadata or {},
        video_id=video_id,
        created_at=now,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    manager = ProtectionSessionManager(session, timeout_minutes=config.protection_timeout_minutes)
    manager.check_timeout(now)
    active = manager.get_active_session()

    if active is not None and not record.session_id:
        record.session_id = active.session_id
        session.add(record)
        session.commit()
        session.refresh(record)

    if active is not None:
        manager.apply_event(EventType(record.type), now, active)

    session_id = record.session_id
    assessment = _assess_session(session, session_id, config)
    if active is not None and session_id == active.session_id:
        manager.set_threat_level(assessment.level, active)

    incident: Incident | None = None
    incident_created = False
    if assessment.should_create_incident and session_id:
        incidents = IncidentService(session, cooldown_seconds=config.incident_cooldown_seconds)
        incident, incident_created = incidents.create_or_escalate(
            assessment,
            session_id=session_id,
            video_id=video_id or _video_id_for_session(session, session_id),
        )
        events = _session_events(session, session_id)
        response = ResponseService(session, config)
        source_video = _video_path_for_session(session, session_id)
        if incident_created:
            response.handle_new_incident(incident, events, source_video)
        else:
            response.handle_escalation(incident, events, source_video)
        incident = incidents.get_incident(incident.incident_id)

    return IngestResult(
        event=record,
        assessment=assessment,
        incident=incident,
        incident_created=incident_created,
    )


def _assess_session(
    session: Session,
    session_id: str | None,
    settings: Settings,
) -> ThreatAssessment:
    """Run the rule engine over the events of a session."""
    events = _session_events(session, session_id)
    payload = [
        EventCreate(
            event_id=event.event_id,
            session_id=event.session_id,
            type=event.type,
            timestamp_s=event.timestamp_s,
            frame_index=event.frame_index,
            track_ids=event.track_ids or {},
            confidence=event.confidence,
            bbox=event.bbox or {},
            metadata=event.metadata_ or {},
        )
        for event in events
    ]
    return assess_threat(payload, ThreatThresholds.from_settings(settings))


def _session_events(session: Session, session_id: str | None) -> list[Event]:
    """Return the events of a session in chronological order."""
    if not session_id:
        return []
    statement = (
        select(Event)
        .where(Event.session_id == session_id)
        .order_by(Event.timestamp_s, Event.created_at)  # type: ignore[union-attr]
    )
    return list(session.exec(statement).all())


def _video_id_for_session(session: Session, session_id: str) -> str | None:
    """Return the video id linked to a protection session."""
    from backend.models.protection_session import ProtectionSession  # noqa: PLC0415

    record = session.get(ProtectionSession, session_id)
    return record.video_id if record else None


def _video_path_for_session(session: Session, session_id: str) -> str | None:
    """Return the path of the video linked to a protection session."""
    video_id = _video_id_for_session(session, session_id)
    if not video_id:
        return None
    record = session.get(Video, video_id)
    return record.path if record else None
