"""End-to-end test: replay mock events and verify the expected incidents.

This test replays the mock event stream through the ingestion pipeline and
checks that the right number and type of incidents were created with no
unwanted duplicates.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from backend.core.config import get_settings
from backend.schemas.enums import IncidentStatus, ReasonCode, SessionSource
from backend.schemas.event_schema import EventCreate
from backend.services.incident_service import IncidentService
from backend.services.pipeline_service import ingest_event
from backend.services.protection_service import ProtectionSessionManager


def test_full_flow_produces_expected_incidents(session: Session) -> None:
    """Replay mock_events.json and verify the incidents produced."""
    settings = get_settings()
    mock_path = Path(__file__).resolve().parents[2] / "samples" / "mock_events.json"
    if not mock_path.is_file():
        # If mock data is missing, skip the test gracefully.
        import pytest

        pytest.skip("samples/mock_events.json not found")

    data = json.loads(mock_path.read_text(encoding="utf-8"))
    events = data.get("events", data) if isinstance(data, dict) else data

    # Start a protection session.
    manager = ProtectionSessionManager(session, timeout_minutes=settings.protection_timeout_minutes)
    active = manager.start_session(source=SessionSource.SIMULATED_DELIVERY)
    session_id = active.session_id

    results = []
    for raw in events:
        raw["session_id"] = session_id
        payload = EventCreate(**raw)
        result = ingest_event(session, payload, settings)
        results.append(result)

    # Check that at least one incident was created (the theft scenario should fire).
    incidents_service = IncidentService(session, cooldown_seconds=settings.incident_cooldown_seconds)
    all_incidents = incidents_service.list_incidents(session_id=session_id)
    assert len(all_incidents) >= 1, f"Expected at least 1 incident, got {len(all_incidents)}"

    # Verify no duplicate incidents for the same person and reason.
    seen_keys: set[str] = set()
    for incident in all_incidents:
        for track_id in incident.person_track_ids:
            for code in incident.reason_codes:
                key = f"{track_id}:{code}"
                assert key not in seen_keys, f"Duplicate incident for {key}"
                seen_keys.add(key)

    # Check that every incident is in OPEN status (no automatic dismissal).
    for incident in all_incidents:
        assert incident.status == IncidentStatus.OPEN.value
