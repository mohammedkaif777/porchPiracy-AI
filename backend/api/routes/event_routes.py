"""Event ingestion and listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import event_to_schema, incident_to_schema
from backend.core.config import Settings
from backend.models.event import Event
from backend.schemas.enums import EventType, ThreatLevel
from backend.schemas.event_schema import EventCreate, EventRead
from backend.schemas.incident_schema import IncidentRead
from backend.services.pipeline_service import ingest_event

router = APIRouter(prefix="/events", tags=["events"])


class EventIngestResponse(BaseModel):
    """Response of ``POST /events``."""

    model_config = ConfigDict(extra="forbid")

    event: EventRead
    threat_level: ThreatLevel
    incident_created: bool
    incident: IncidentRead | None = None


@router.post("", response_model=EventIngestResponse, status_code=201)
@router.post("/", response_model=EventIngestResponse, status_code=201, include_in_schema=False)
def create_event(
    body: EventCreate,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> EventIngestResponse:
    """Ingest an event through the decision pipeline."""
    result = ingest_event(session, body, settings)
    return EventIngestResponse(
        event=event_to_schema(result.event),
        threat_level=result.assessment.level,
        incident_created=result.incident_created,
        incident=incident_to_schema(result.incident) if result.incident else None,
    )


@router.get("", response_model=list[EventRead])
def list_events(
    session: Session = Depends(db_session),
    session_id: str | None = Query(default=None),
    video_id: str | None = Query(default=None),
    event_type: EventType | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[EventRead]:
    """List events, newest first, with optional filters."""
    statement = select(Event)
    if session_id:
        statement = statement.where(Event.session_id == session_id)
    if video_id:
        statement = statement.where(Event.video_id == video_id)
    if event_type:
        statement = statement.where(Event.type == event_type.value)
    statement = statement.order_by(Event.created_at.desc()).limit(limit)  # type: ignore[union-attr]
    return [event_to_schema(record) for record in session.exec(statement).all()]
