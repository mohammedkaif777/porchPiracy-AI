"""Incident listing, detail, review, evidence and report endpoints."""

from __future__ import annotations

import ast
import base64
import html
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from backend.api.dependencies import incident_service
from backend.api.mappers import event_to_schema, incident_to_schema
from backend.core.exceptions import NotFoundError
from backend.models.event import Event
from backend.models.incident import Incident
from backend.schemas.enums import IncidentStatus, Severity
from backend.schemas.incident_schema import IncidentDetail, IncidentRead, IncidentReviewRequest
from backend.schemas.system_schema import EvidenceKeyFrame, EvidenceRead
from backend.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    service: IncidentService = Depends(incident_service),
    session_id: str | None = Query(default=None),
    status: IncidentStatus | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[IncidentRead]:
    """List incidents, newest first, with optional filters."""
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
    service: IncidentService = Depends(incident_service),
) -> IncidentDetail:
    """Return a single incident with its triggering events and evidence."""
    incident = service.get_incident(incident_id)
    events = service.get_events(incident)
    evidence = evidence_from_incident(incident)
    return IncidentDetail(
        incident=incident_to_schema(incident),
        events=[event_to_schema(event).model_dump(mode="json") for event in events],
        evidence=evidence.model_dump(mode="json") if evidence else None,
    )


@router.post("/{incident_id}/review", response_model=IncidentRead)
def review_incident(
    incident_id: str,
    body: IncidentReviewRequest,
    service: IncidentService = Depends(incident_service),
) -> IncidentRead:
    """Mark an incident as reviewed or dismissed. Does not end protection."""
    record = service.review(incident_id, body.status, body.note)
    return incident_to_schema(record)


@router.get("/{incident_id}/evidence", response_model=EvidenceRead)
def incident_evidence(
    incident_id: str,
    service: IncidentService = Depends(incident_service),
) -> EvidenceRead:
    """Return the evidence bundle for an incident."""
    incident = service.get_incident(incident_id)
    evidence = evidence_from_incident(incident)
    if evidence is None:
        raise NotFoundError("Evidence", incident_id)
    return evidence


@router.get("/{incident_id}/report", response_class=HTMLResponse)
def incident_report(
    incident_id: str,
    service: IncidentService = Depends(incident_service),
) -> str:
    """Return a self-contained HTML report with key frames inlined as base64."""
    incident = service.get_incident(incident_id)
    events = service.get_events(incident)
    evidence = evidence_from_incident(incident)
    return _render_report(incident, events, evidence)


def evidence_from_incident(incident: Incident) -> EvidenceRead | None:
    """Build an evidence payload from stored metadata or files next to the clip."""
    data = _parse_metadata(incident.evidence_metadata)
    bundle_dir = _bundle_dir(incident.evidence_path)
    if data is None and bundle_dir is not None:
        meta_path = bundle_dir / "metadata.json"
        if meta_path.is_file():
            data = _parse_metadata(meta_path.read_text(encoding="utf-8"))

    if isinstance(data, dict) and (data.get("clip_path") or data.get("key_frames")):
        frames = [
            EvidenceKeyFrame(
                path=str(frame.get("path", "")),
                timestamp_s=float(frame.get("timestamp_s") or 0.0),
                label=str(frame.get("label") or "key_frame"),
            )
            for frame in data.get("key_frames") or []
            if isinstance(frame, dict)
        ]
        if not frames and bundle_dir is not None:
            frames = _frames_from_dir(bundle_dir)
        return EvidenceRead(
            incident_id=incident.incident_id,
            clip_path=data.get("clip_path") or incident.evidence_path,
            clip_start_s=data.get("clip_start_s"),
            clip_end_s=data.get("clip_end_s"),
            key_frames=frames,
            faces_blurred=bool(data.get("faces_blurred")),
            metadata=dict(data.get("metadata") or {}),
        )

    if incident.evidence_path:
        frames = _frames_from_dir(bundle_dir) if bundle_dir else []
        return EvidenceRead(
            incident_id=incident.incident_id,
            clip_path=incident.evidence_path,
            key_frames=frames,
        )
    return None


def _bundle_dir(evidence_path: str | None) -> Path | None:
    """Return the directory that holds clip, metadata and key frames."""
    if not evidence_path:
        return None
    path = Path(evidence_path)
    if path.is_dir():
        return path
    if path.is_file():
        return path.parent
    return path.parent if path.suffix else path


def _frames_from_dir(bundle_dir: Path) -> list[EvidenceKeyFrame]:
    """Collect image files from a key_frames folder or the bundle directory."""
    frames_dir = bundle_dir / "key_frames"
    search = frames_dir if frames_dir.is_dir() else bundle_dir
    frames: list[EvidenceKeyFrame] = []
    if not search.is_dir():
        return frames
    for frame_path in sorted(search.iterdir()):
        if frame_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            frames.append(
                EvidenceKeyFrame(path=str(frame_path), timestamp_s=0.0, label=frame_path.stem)
            )
    return frames


def _parse_metadata(raw: str | dict | None) -> dict | None:
    """Parse evidence metadata stored as JSON, a dict, or a Python literal."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return None
    return parsed if isinstance(parsed, dict) else None


def _render_report(
    incident: Incident,
    events: list[Event],
    evidence: EvidenceRead | None,
) -> str:
    """Return a single-file HTML report. User-controlled fields are escaped."""
    incident_id = html.escape(incident.incident_id)
    reasons = ", ".join(html.escape(code) for code in incident.reason_codes or [])
    explanation = html.escape(incident.explanation or "")
    events_html = "".join(
        "<tr>"
        f"<td>{html.escape(str(event.type))}</td>"
        f"<td>{event.timestamp_s:.2f}s</td>"
        f"<td>{event.confidence:.2f}</td>"
        "</tr>"
        for event in events
    )
    frames_html = ""
    if evidence:
        for frame in evidence.key_frames:
            path = Path(frame.path)
            if not path.is_file():
                continue
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            suffix = path.suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            label = html.escape(frame.label)
            frames_html += (
                f'<figure><img src="data:{mime};base64,{data}" alt="{label}"/>'
                f"<figcaption>{label} @ {frame.timestamp_s}s</figcaption></figure>"
            )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Evidence report {incident_id[:8]}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; }}
  img {{ max-width: 100%; }} figure {{ margin: 1em 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1em 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  .note {{ color: #555; }}
</style></head>
<body>
<h1>Evidence report</h1>
<p><strong>ID:</strong> {incident_id}</p>
<p><strong>Severity:</strong> {html.escape(str(incident.severity))} ·
<strong>Status:</strong> {html.escape(str(incident.status))}</p>
<p><strong>Reasons:</strong> {reasons or "—"}</p>
<p><strong>Time span:</strong> {incident.start_s:.2f}s – {incident.end_s:.2f}s</p>
{f"<p><strong>Explanation:</strong> {explanation}</p>" if explanation else ""}
<p class="note">Wording: potential package theft, for review. Faces are blurred on exported clips.</p>
<h2>Events</h2>
<table><thead><tr><th>Type</th><th>Time</th><th>Confidence</th></tr></thead>
<tbody>{events_html or "<tr><td colspan='3'>No linked events.</td></tr>"}</tbody></table>
<h2>Key frames</h2>
{frames_html or '<p class="note">No key frames on disk.</p>'}
</body></html>"""
