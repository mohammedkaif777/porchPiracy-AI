"""Event ingestion and listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import event_to_schema, incident_to_schema
from backend.core.config import Settings
from backend.core.logging_config import get_logger
from backend.models.event import Event
from backend.schemas.enums import EventType
from backend.schemas.event_schema import EventCreate, EventRead
from backend.services.pipeline_service import ingest_event

logger = get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=201)
@router.post("/", status_code=201, include_in_schema=False)
def create_event(
    body: EventCreate,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> dict:
    """Ingest an event through the decision pipeline.

    Returns the persisted event, the threat level, and any incident created.
    """
    result = ingest_event(session, body, settings)
    response: dict = {
        "event": event_to_schema(result.event),
        "threat_level": result.assessment.level.value,
        "incident_created": result.incident_created,
    }
    if result.incident is not None:
        response["incident"] = incident_to_schema(result.incident)
    else:
        response["incident"] = None
    return response


@router.get("", response_model=list[EventRead])
def list_events(
    session: Session = Depends(db_session),
    session_id: str | None = Query(default=None),
    event_type: EventType | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[EventRead]:
    """List events, newest first, with optional filters."""
    statement = select(Event)
    if session_id:
        statement = statement.where(Event.session_id == session_id)
    if event_type:
        statement = statement.where(Event.type == event_type.value)
    statement = statement.order_by(Event.created_at.desc()).limit(limit)  # type: ignore[union-attr]
    return [event_to_schema(record) for record in session.exec(statement).all()]
