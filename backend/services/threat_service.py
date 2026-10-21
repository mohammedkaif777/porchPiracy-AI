"""Deterministic threat rule engine.

The engine is a **pure function**: it receives an ordered sequence of events plus
the thresholds, and returns a :class:`~backend.schemas.incident_schema.ThreatAssessment`.
It never reads the clock, never touches the database and never calls a model.
``now`` is not needed here because events carry their own timestamps.

Rule table (``DEVELOPMENT.md`` section 6.2)::

    person passes outside the zone                -> NONE
    person briefly near the package               -> MONITORING
    person near the package for >= loiter time    -> LOW      (LOITERING_OVER_THRESHOLD)
    person interacts with the package             -> MEDIUM   (PACKAGE_INTERACTION)
    package moved by an unidentified person       -> HIGH     (PACKAGE_MOVED)
    package removed with an associated person     -> HIGH     (PACKAGE_REMOVED_UNAUTHORIZED)
    package removed after an authorized retrieval -> no incident

A package disappearing from view is **not** proof of theft: a removal without an
associated person track only produces ``MONITORING``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.schemas.enums import EventType, ReasonCode, Severity, ThreatLevel
from backend.schemas.event_schema import EventCreate
from backend.schemas.incident_schema import ThreatAssessment

#: Event types that can contribute to a threat assessment.
THREAT_EVENT_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.PERSON_APPROACHING,
        EventType.PERSON_NEAR_PACKAGE,
        EventType.LOITERING_DETECTED,
        EventType.PACKAGE_INTERACTION,
        EventType.PACKAGE_MOVEMENT_DETECTED,
        EventType.PACKAGE_REMOVED,
        EventType.PACKAGE_RETRIEVED,
    }
)

#: Event types proving that a person was close to the package.
PERSON_PROXIMITY_EVENT_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.PERSON_APPROACHING,
        EventType.PERSON_NEAR_PACKAGE,
        EventType.LOITERING_DETECTED,
        EventType.PACKAGE_INTERACTION,
    }
)


@dataclass(frozen=True)
class ThreatThresholds:
    """Tunables of the rule engine. Passed in, never read from the environment."""

    loiter_threshold_seconds: float = 8.0
    association_window_seconds: float = 10.0
    near_gap_tolerance_seconds: float = 5.0
    package_movement_px: float = 60.0

    @classmethod
    def from_settings(cls, settings) -> ThreatThresholds:  # noqa: ANN001 - avoids an import cycle
        """Build thresholds from the application settings."""
        return cls(
            loiter_threshold_seconds=settings.loiter_threshold_seconds,
            package_movement_px=settings.package_movement_px,
        )


@dataclass
class _RuleHit:
    """One rule firing, with the evidence that produced it."""

    reason_code: ReasonCode
    severity: Severity
    event_ids: list[str] = field(default_factory=list)
    person_track_ids: list[int] = field(default_factory=list)
    start_s: float = 0.0
    end_s: float = 0.0
    note: str = ""


def assess_threat(
    events: Sequence[EventCreate],
    thresholds: ThreatThresholds | None = None,
) -> ThreatAssessment:
    """Assess the threat level of an ordered event sequence.

    Args:
        events: Events of the active session, in any order (they are sorted here).
        thresholds: Rule thresholds. Defaults to the documented values.

    Returns:
        A :class:`ThreatAssessment` describing the level, the severity, the reason
        codes and whether an incident should be created.
    """
    rules = thresholds or ThreatThresholds()
    ordered = sorted(events, key=lambda event: (event.timestamp_s, event.event_id or ""))
    relevant = [event for event in ordered if event.type in THREAT_EVENT_TYPES]

    if not relevant:
        return ThreatAssessment(level=ThreatLevel.NONE)

    hits: list[_RuleHit] = []
    hits.extend(_detect_loitering(relevant, rules))
    hits.extend(_detect_interaction(relevant))
    hits.extend(_detect_movement(relevant, rules))
    hits.extend(_detect_removal(relevant, rules))

    if not hits:
        # Someone was around but nothing crossed a threshold yet.
        if any(event.type in PERSON_PROXIMITY_EVENT_TYPES for event in relevant):
            return ThreatAssessment(
                level=ThreatLevel.MONITORING,
                detail={"note": "Person activity observed below the loiter threshold."},
            )
        return ThreatAssessment(level=ThreatLevel.NONE)

    severity = max((hit.severity for hit in hits), key=_severity_rank)
    level = _level_for_severity(severity)

    reason_codes: list[ReasonCode] = []
    for hit in hits:
        if hit.reason_code not in reason_codes:
            reason_codes.append(hit.reason_code)

    event_ids: list[str] = []
    person_track_ids: list[int] = []
    for hit in hits:
        for event_id in hit.event_ids:
            if event_id not in event_ids:
                event_ids.append(event_id)
        for track_id in hit.person_track_ids:
            if track_id not in person_track_ids:
                person_track_ids.append(track_id)

    start_s = min(hit.start_s for hit in hits)
    end_s = max(hit.end_s for hit in hits)

    return ThreatAssessment(
        level=level,
        severity=severity,
        reason_codes=reason_codes,
        should_create_incident=True,
        event_ids=event_ids,
        person_track_ids=person_track_ids,
        start_s=start_s,
        end_s=end_s,
        detail={
            "hits": [
                {
                    "reason_code": hit.reason_code.value,
                    "severity": hit.severity.value,
                    "event_ids": hit.event_ids,
                    "person_track_ids": hit.person_track_ids,
                    "note": hit.note,
                }
                for hit in hits
            ]
        },
    )


# --------------------------------------------------------------------- rules


def _detect_loitering(events: Sequence[EventCreate], rules: ThreatThresholds) -> list[_RuleHit]:
    """Fire when a person stayed near the package for longer than the threshold."""
    hits: list[_RuleHit] = []

    explicit = [event for event in events if event.type is EventType.LOITERING_DETECTED]
    for event in explicit:
        track_id = event.track_ids.get("person")
        hits.append(
            _RuleHit(
                reason_code=ReasonCode.LOITERING_OVER_THRESHOLD,
                severity=Severity.LOW,
                event_ids=[event.event_id] if event.event_id else [],
                person_track_ids=[track_id] if track_id is not None else [],
                start_s=event.timestamp_s,
                end_s=event.timestamp_s,
                note=(
                    f"Person was near the package for at least "
                    f"{rules.loiter_threshold_seconds:.1f}s."
                ),
            )
        )
    if explicit:
        return hits

    # No explicit loitering event: derive the stay from the near-package events.
    near_events = [event for event in events if event.type is EventType.PERSON_NEAR_PACKAGE]
    by_person: dict[int | None, list[EventCreate]] = {}
    for event in near_events:
        by_person.setdefault(event.track_ids.get("person"), []).append(event)

    for track_id, group in by_person.items():
        duration = _longest_stay(group, rules.near_gap_tolerance_seconds)
        if duration >= rules.loiter_threshold_seconds:
            first = min(event.timestamp_s for event in group)
            last = max(event.timestamp_s for event in group)
            hits.append(
                _RuleHit(
                    reason_code=ReasonCode.LOITERING_OVER_THRESHOLD,
                    severity=Severity.LOW,
                    event_ids=[event.event_id for event in group if event.event_id],
                    person_track_ids=[track_id] if track_id is not None else [],
                    start_s=first,
                    end_s=last,
                    note=(
                        f"Person stayed near the package for {duration:.1f}s "
                        f"(threshold {rules.loiter_threshold_seconds:.1f}s)."
                    ),
                )
            )
    return hits


def _detect_interaction(events: Sequence[EventCreate]) -> list[_RuleHit]:
    """Fire when a person touched or overlapped the package."""
    hits: list[_RuleHit] = []
    for event in events:
        if event.type is not EventType.PACKAGE_INTERACTION:
            continue
        track_id = event.track_ids.get("person")
        hits.append(
            _RuleHit(
                reason_code=ReasonCode.PACKAGE_INTERACTION,
                severity=Severity.MEDIUM,
                event_ids=[event.event_id] if event.event_id else [],
                person_track_ids=[track_id] if track_id is not None else [],
                start_s=event.timestamp_s,
                end_s=event.timestamp_s,
                note="A person overlapped the package bounding box.",
            )
        )
    return hits


def _detect_movement(events: Sequence[EventCreate], rules: ThreatThresholds) -> list[_RuleHit]:
    """Fire when the package moved. HIGH only when a person is associated."""
    hits: list[_RuleHit] = []
    for event in events:
        if event.type is not EventType.PACKAGE_MOVEMENT_DETECTED:
            continue
        associated, person_ids = _association(event, events, rules.association_window_seconds)
        severity = Severity.HIGH if associated else Severity.MEDIUM
        displacement = _metadata_float(event, "displacement_px", rules.package_movement_px)
        hits.append(
            _RuleHit(
                reason_code=ReasonCode.PACKAGE_MOVED,
                severity=severity,
                event_ids=[event.event_id] if event.event_id else [],
                person_track_ids=person_ids,
                start_s=event.timestamp_s,
                end_s=event.timestamp_s,
                note=(
                    f"Package moved about {displacement:.0f}px from its baseline"
                    + (" while a person was next to it." if associated else ".")
                ),
            )
        )
    return hits


def _detect_removal(events: Sequence[EventCreate], rules: ThreatThresholds) -> list[_RuleHit]:
    """Fire when the package disappeared with an associated person.

    A removal without any association stays at ``MONITORING``: the package may
    have been occluded, collected by the homeowner, or simply left the field of
    view.
    """
    hits: list[_RuleHit] = []
    retrievals = [event for event in events if event.type is EventType.PACKAGE_RETRIEVED]

    for event in events:
        if event.type is not EventType.PACKAGE_REMOVED:
            continue

        authorized = any(
            retrieval.timestamp_s <= event.timestamp_s for retrieval in retrievals
        )
        if authorized:
            continue

        associated, person_ids = _association(event, events, rules.association_window_seconds)
        moved_before = any(
            other.type is EventType.PACKAGE_MOVEMENT_DETECTED
            and 0 <= event.timestamp_s - other.timestamp_s <= rules.association_window_seconds
            for other in events
        )
        if not associated and not moved_before:
            continue

        hits.append(
            _RuleHit(
                reason_code=ReasonCode.PACKAGE_REMOVED_UNAUTHORIZED,
                severity=Severity.HIGH,
                event_ids=[event.event_id] if event.event_id else [],
                person_track_ids=person_ids,
                start_s=event.timestamp_s,
                end_s=event.timestamp_s,
                note=(
                    "The package left the protected area while a person was next to it."
                    if associated
                    else "The package left the protected area after it had been moved."
                ),
            )
        )
    return hits


# ------------------------------------------------------------------- helpers


def _association(
    event: EventCreate,
    events: Sequence[EventCreate],
    window_seconds: float,
) -> tuple[bool, list[int]]:
    """Return whether a person was plausibly responsible for ``event``.

    Association is either explicit (the event carries a person track id) or
    inferred from a person being close to the package shortly before. Inference
    is what makes the rules tolerant of track id flips.

    Returns:
        A tuple ``(associated, person_track_ids)``.
    """
    explicit = event.track_ids.get("person")
    if explicit is not None:
        return True, [explicit]

    person_ids: list[int] = []
    for other in events:
        if other.type not in PERSON_PROXIMITY_EVENT_TYPES:
            continue
        if other.timestamp_s > event.timestamp_s:
            continue
        if event.timestamp_s - other.timestamp_s > window_seconds:
            continue
        track_id = other.track_ids.get("person")
        if track_id is not None and track_id not in person_ids:
            person_ids.append(track_id)
        if track_id is None:
            # A person was close but its id is unknown: the association holds.
            return True, person_ids
    return bool(person_ids), person_ids


def _longest_stay(events: Sequence[EventCreate], gap_tolerance: float) -> float:
    """Return the longest continuous presence of a person in seconds."""
    if not events:
        return 0.0
    timestamps = sorted(event.timestamp_s for event in events)
    longest = 0.0
    current_start = timestamps[0]
    previous = timestamps[0]
    for timestamp in timestamps[1:]:
        if timestamp - previous > gap_tolerance:
            longest = max(longest, previous - current_start)
            current_start = timestamp
        previous = timestamp
    return max(longest, previous - current_start)


def _metadata_float(event: EventCreate, key: str, default: float) -> float:
    """Read a float from the event metadata with a safe default."""
    value = event.metadata.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _severity_rank(severity: Severity) -> int:
    """Return the ordering rank of a severity."""
    return {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}[severity]


def _level_for_severity(severity: Severity) -> ThreatLevel:
    """Map the incident severity onto the session threat level."""
    if severity is Severity.HIGH:
        return ThreatLevel.THREAT
    if severity is Severity.MEDIUM:
        return ThreatLevel.SUSPICIOUS
    if severity is Severity.LOW:
        return ThreatLevel.SUSPICIOUS
    return ThreatLevel.MONITORING
