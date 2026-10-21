"""Unit tests for incident deduplication and escalation.

Tests: same person → escalation (not duplicate), different person → new incident,
review/dismiss opens a new incident window.
"""

from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from backend.models.incident import Incident
from backend.schemas.enums import IncidentStatus, ReasonCode, Severity, ThreatLevel
from backend.schemas.incident_schema import ThreatAssessment
from backend.services.incident_service import IncidentService


def _assessment(
    reason_codes: list[ReasonCode] | None = None,
    severity: Severity = Severity.LOW,
    person_track_ids: list[int] | None = None,
    event_ids: list[str] | None = None,
    start_s: float = 0.0,
    end_s: float = 5.0,
) -> ThreatAssessment:
    return ThreatAssessment(
        level=ThreatLevel.SUSPICIOUS,
        severity=severity,
        reason_codes=reason_codes or [ReasonCode.LOITERING_OVER_THRESHOLD],
        should_create_incident=True,
        event_ids=event_ids or ["evt-1"],
        person_track_ids=person_track_ids or [10],
        start_s=start_s,
        end_s=end_s,
    )


class TestCreateOrEscalate:
    """Test the deduplication logic."""

    def test_first_incident_is_created(self, session: Session) -> None:
        service = IncidentService(session, cooldown_seconds=30.0)
        incident, created = service.create_or_escalate(
            _assessment(), session_id="sess-1",
        )
        assert created is True
        assert incident.status == IncidentStatus.OPEN.value
        assert incident.severity == Severity.LOW.value

    def test_same_person_same_reason_escalates(self, session: Session) -> None:
        service = IncidentService(session, cooldown_seconds=30.0)
        inc1, created1 = service.create_or_escalate(
            _assessment(event_ids=["evt-1"]), session_id="sess-1",
        )
        assert created1 is True

        inc2, created2 = service.create_or_escalate(
            _assessment(
                severity=Severity.MEDIUM,
                reason_codes=[ReasonCode.PACKAGE_INTERACTION],
                event_ids=["evt-2"],
                end_s=6.0,
            ),
            session_id="sess-1",
        )
        assert created2 is False
        assert inc2.incident_id == inc1.incident_id
        assert inc2.severity == Severity.MEDIUM.value  # escalated

    def test_different_person_creates_new_incident(self, session: Session) -> None:
        service = IncidentService(session, cooldown_seconds=30.0)
        inc1, _ = service.create_or_escalate(
            _assessment(person_track_ids=[10], event_ids=["evt-1"]),
            session_id="sess-1",
        )
        inc2, created2 = service.create_or_escalate(
            _assessment(person_track_ids=[99], event_ids=["evt-2"], end_s=100.0),
            session_id="sess-1",
        )
        assert created2 is True
        assert inc2.incident_id != inc1.incident_id


class TestReview:
    """Test that reviewing/dismissing opens a new incident window."""

    def test_review_and_new_incident(self, session: Session) -> None:
        service = IncidentService(session, cooldown_seconds=30.0)
        inc1, _ = service.create_or_escalate(
            _assessment(event_ids=["evt-1"]), session_id="sess-1",
        )
        service.review(inc1.incident_id, IncidentStatus.DISMISSED)

        inc2, created = service.create_or_escalate(
            _assessment(event_ids=["evt-2"], end_s=60.0), session_id="sess-1",
        )
        # After dismissal the old incident is no longer OPEN, so a new one is created.
        assert created is True
        assert inc2.incident_id != inc1.incident_id
