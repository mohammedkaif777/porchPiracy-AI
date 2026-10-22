"""Unit tests for the deterministic threat rule engine.

One test per row of the rule table in ``DEVELOPMENT.md`` section 6.2:
  - passerby → NONE
  - brief approach → MONITORING
  - loiter → LOW (LOITERING_OVER_THRESHOLD)
  - interaction → MEDIUM (PACKAGE_INTERACTION)
  - movement + person → HIGH (PACKAGE_MOVED)
  - removal without person → no incident
  - authorised retrieval → no incident
"""


from backend.schemas.enums import EventType, ReasonCode, Severity, ThreatLevel
from backend.schemas.event_schema import EventCreate
from backend.services.threat_service import ThreatThresholds, assess_threat


def _event(
    event_id: str,
    event_type: EventType,
    timestamp_s: float,
    person: int | None = None,
    package: int | None = None,
    metadata: dict | None = None,
) -> EventCreate:
    """Helper to build a minimal EventCreate."""
    track_ids: dict[str, int] = {}
    if person is not None:
        track_ids["person"] = person
    if package is not None:
        track_ids["package"] = package
    return EventCreate(
        event_id=event_id,
        type=event_type,
        timestamp_s=timestamp_s,
        track_ids=track_ids,
        metadata=metadata or {},
    )


THRESHOLDS = ThreatThresholds(loiter_threshold_seconds=8.0)


class TestPasserby:
    """A person passes outside the zone → NONE."""

    def test_no_events_returns_none(self) -> None:
        result = assess_threat([], THRESHOLDS)
        assert result.level is ThreatLevel.NONE
        assert result.should_create_incident is False

    def test_only_package_detected_returns_none(self) -> None:
        events = [_event("e1", EventType.PACKAGE_DETECTED, 0.0, package=1)]
        result = assess_threat(events, THRESHOLDS)
        assert result.level is ThreatLevel.NONE


class TestBriefApproach:
    """Person briefly near the package → MONITORING."""

    def test_single_near_event_returns_monitoring(self) -> None:
        events = [_event("e1", EventType.PERSON_NEAR_PACKAGE, 1.0, person=10, package=1)]
        result = assess_threat(events, THRESHOLDS)
        assert result.level is ThreatLevel.MONITORING
        assert result.should_create_incident is False


class TestLoitering:
    """Person near the package for >= loiter time → LOW, LOITERING_OVER_THRESHOLD."""

    def test_explicit_loitering_event(self) -> None:
        events = [_event("e1", EventType.LOITERING_DETECTED, 10.0, person=30)]
        result = assess_threat(events, THRESHOLDS)
        assert result.level is ThreatLevel.SUSPICIOUS
        assert result.severity is Severity.LOW
        assert ReasonCode.LOITERING_OVER_THRESHOLD in result.reason_codes
        assert result.should_create_incident is True

    def test_derived_loitering_from_near_events(self) -> None:
        events = [
            _event("e1", EventType.PERSON_NEAR_PACKAGE, 0.0, person=30),
            _event("e2", EventType.PERSON_NEAR_PACKAGE, 4.0, person=30),
            _event("e3", EventType.PERSON_NEAR_PACKAGE, 9.0, person=30),
        ]
        result = assess_threat(events, THRESHOLDS)
        assert result.should_create_incident is True
        assert ReasonCode.LOITERING_OVER_THRESHOLD in result.reason_codes


class TestInteraction:
    """Person interacts with the package → MEDIUM, PACKAGE_INTERACTION."""

    def test_interaction_event(self) -> None:
        events = [_event("e1", EventType.PACKAGE_INTERACTION, 5.0, person=40, package=1)]
        result = assess_threat(events, THRESHOLDS)
        assert result.level is ThreatLevel.SUSPICIOUS
        assert result.severity is Severity.MEDIUM
        assert ReasonCode.PACKAGE_INTERACTION in result.reason_codes
        assert result.should_create_incident is True


class TestMovementWithPerson:
    """Package moved by an associated person → HIGH, PACKAGE_MOVED."""

    def test_movement_with_person_track(self) -> None:
        events = [
            _event("e1", EventType.PERSON_NEAR_PACKAGE, 1.0, person=50),
            _event("e2", EventType.PACKAGE_MOVEMENT_DETECTED, 3.0, person=50, package=1),
        ]
        result = assess_threat(events, THRESHOLDS)
        assert result.level is ThreatLevel.THREAT
        assert result.severity is Severity.HIGH
        assert ReasonCode.PACKAGE_MOVED in result.reason_codes
        assert result.should_create_incident is True


class TestRemovalWithoutPerson:
    """Package removed without an associated person → no incident."""

    def test_removal_no_association_no_prior_movement(self) -> None:
        events = [_event("e1", EventType.PACKAGE_REMOVED, 10.0)]
        result = assess_threat(events, THRESHOLDS)
        assert result.should_create_incident is False


class TestAuthorisedRetrieval:
    """Package removed after an authorised retrieval → no incident."""

    def test_retrieval_before_removal_blocks_incident(self) -> None:
        events = [
            _event("e1", EventType.PACKAGE_RETRIEVED, 5.0, person=60),
            _event("e2", EventType.PACKAGE_REMOVED, 6.0, person=60),
        ]
        result = assess_threat(events, THRESHOLDS)
        # PACKAGE_REMOVED should be suppressed because of the retrieval.
        assert ReasonCode.PACKAGE_REMOVED_UNAUTHORIZED not in result.reason_codes
