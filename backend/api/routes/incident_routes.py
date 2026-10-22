"""Incident listing, detail, review, evidence and report endpoints."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from backend.api.dependencies import app_settings, db_session
from backend.api.mappers import event_to_schema, incident_to_schema
from backend.core.config import Settings
from backend.core.exceptions import NotFoundError
from backend.core.logging_config import get_logger
from backend.schemas.enums import IncidentStatus, Severity
from backend.schemas.incident_schema import IncidentDetail, IncidentRead, IncidentReviewRequest
from backend.schemas.system_schema import EvidenceKeyFrame, EvidenceRead
from backend.services.incident_service import IncidentService

logger = get_logger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
    session_id: str | None = Query(default=None),
    status: IncidentStatus | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[IncidentRead]:
    """List incidents, newest first, with optional filters."""
    service = IncidentService(session, cooldown_seconds=settings.incident_cooldown_seconds)
    records = service.list_incidents(
        session_id=session_id,
        status=status,
        severity=severity,
        limit=limit,
    )
    return [incident_to_schema(record) for record in records]


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: str,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> IncidentDetail:
    """Return a single incident with its triggering events and evidence."""
    service = IncidentService(session, cooldown_seconds=settings.incident_cooldown_seconds)
    incident = service.get_incident(incident_id)
    events = service.get_events(incident)
    evidence = _load_evidence(incident.evidence_path)
    return IncidentDetail(
        incident=incident_to_schema(incident),
        events=[event_to_schema(event).model_dump(mode="json") for event in events],
        evidence=evidence,
    )


@router.post("/{incident_id}/review", response_model=IncidentRead)
def review_incident(
    incident_id: str,
    body: IncidentReviewRequest,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> IncidentRead:
    """Mark an incident as reviewed or dismissed."""
    service = IncidentService(session, cooldown_seconds=settings.incident_cooldown_seconds)
    record = service.review(incident_id, body.status, body.note)
    return incident_to_schema(record)


@router.get("/{incident_id}/evidence", response_model=EvidenceRead)
def incident_evidence(
    incident_id: str,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> EvidenceRead:
    """Return the evidence bundle for an incident."""
    service = IncidentService(session, cooldown_seconds=settings.incident_cooldown_seconds)
    incident = service.get_incident(incident_id)
    if not incident.evidence_path:
        raise NotFoundError("Evidence", incident_id)
    evidence_dir = Path(incident.evidence_path)
    meta_path = evidence_dir / "metadata.json"
    metadata: dict = {}
    if meta_path.is_file():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    key_frames: list[EvidenceKeyFrame] = []
    frames_dir = evidence_dir / "key_frames"
    if frames_dir.is_dir():
        for frame_path in sorted(frames_dir.iterdir()):
            if frame_path.suffix.lower() in {".jpg", ".png", ".webp"}:
                key_frames.append(
                    EvidenceKeyFrame(
                        path=str(frame_path),
                        timestamp_s=metadata.get("start_s", 0.0),
                        label=frame_path.stem,
                    )
                )

    clip_path = metadata.get("clip_path")
    return EvidenceRead(
        incident_id=incident_id,
        clip_path=clip_path,
        clip_start_s=metadata.get("clip_start_s"),
        clip_end_s=metadata.get("clip_end_s"),
        key_frames=key_frames,
        faces_blurred=metadata.get("faces_blurred", False),
        metadata=metadata,
    )


@router.get("/{incident_id}/report", response_class=HTMLResponse)
def incident_report(
    incident_id: str,
    session: Session = Depends(db_session),
    settings: Settings = Depends(app_settings),
) -> str:
    """Return a self-contained HTML report with key frames inlined as base64."""
    service = IncidentService(session, cooldown_seconds=settings.incident_cooldown_seconds)
    incident = service.get_incident(incident_id)
    events = service.get_events(incident)

    frames_html = ""
    if incident.evidence_path:
        frames_dir = Path(incident.evidence_path) / "key_frames"
        if frames_dir.is_dir():
            for frame_path in sorted(frames_dir.iterdir()):
                if frame_path.suffix.lower() in {".jpg", ".png", ".webp"}:
                    data = base64.b64encode(frame_path.read_bytes()).decode()
                    mime = "image/jpeg" if frame_path.suffix.lower() == ".jpg" else "image/png"
                    frames_html += (
                        f'<div style="margin:8px 0;">'
                        f'<img src="data:{mime};base64,{data}" '
                        f'style="max-width:640px;border-radius:8px;" />'
                        f'<p style="color:#666;font-size:0.85em;">{frame_path.name}</p>'
                        f'</div>'
                    )

    events_html = ""
    for event in events:
        events_html += f"<tr><td>{event.type}</td><td>{event.timestamp_s:.2f}s</td><td>{event.confidence:.2f}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Incident Report – {incident_id[:8]}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; }}
  h1 {{ color: #d32f2f; }} table {{ width: 100%; border-collapse: collapse; margin: 1em 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #f5f5f5; }} .badge {{ display: inline-block; padding: 4px 12px;
  border-radius: 12px; font-weight: 600; font-size: 0.85em; }}
  .HIGH {{ background: #ffcdd2; color: #b71c1c; }}
  .MEDIUM {{ background: #fff3e0; color: #e65100; }}
  .LOW {{ background: #e8f5e9; color: #2e7d32; }}
</style></head>
<body>
<h1>🛡️ Incident Report</h1>
<p><strong>ID:</strong> {incident.incident_id}</p>
<p><strong>Session:</strong> {incident.session_id or 'N/A'}</p>
<p><strong>Severity:</strong> <span class="badge {incident.severity}">{incident.severity}</span></p>
<p><strong>Status:</strong> {incident.status}</p>
<p><strong>Reasons:</strong> {', '.join(incident.reason_codes)}</p>
<p><strong>Time span:</strong> {incident.start_s:.2f}s – {incident.end_s:.2f}s</p>
{f'<p><strong>Explanation:</strong> {incident.explanation}</p>' if incident.explanation else ''}
<h2>Events</h2>
<table><thead><tr><th>Type</th><th>Time</th><th>Confidence</th></tr></thead>
<tbody>{events_html}</tbody></table>
<h2>Key Frames</h2>
{frames_html if frames_html else '<p style="color:#999;">No key frames available.</p>'}
<hr><p style="color:#999;font-size:0.8em;">Generated by porchPiracyAI</p>
</body></html>"""


def _load_evidence(evidence_path: str | None) -> dict | None:
    """Load evidence metadata from the evidence bundle directory."""
    if not evidence_path:
        return None
    meta = Path(evidence_path) / "metadata.json"
    if meta.is_file():
        return json.loads(meta.read_text(encoding="utf-8"))
    return {"path": evidence_path}
