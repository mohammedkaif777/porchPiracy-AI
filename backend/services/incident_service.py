"""Incident lifecycle: creation, de-duplication, escalation, review and dismissal.

Incident creation is **deterministic**: it happens only when the pure rule engine
says a rule fired. The LLM never creates or changes an incident.

De-duplication follows ``DEVELOPMENT.md`` section 6.2: one incident per
(session, person track, reason group) inside a cooldown window. A later
escalation updates the existing incident instead of raising a new alert.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlmodel import Session, select

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.logging_config import get_logger
from backend.models.event import Event
from backend.models.incident import Incident
from backend.schemas.enums import IncidentStatus, ReasonCode, Severity
from backend.schemas.incident_schema import ThreatAssessment

logger = get_logger(__name__)

#: Reason code families. Two alerts of the same family, for the same person, in
#: the same session belong to the same incident.
REASON_FAMILIES: dict[ReasonCode, str] = {
    ReasonCode.LOITERING_OVER_THRESHOLD: "APPROACH",
    ReasonCode.PACKAGE_INTERACTION: "APPROACH",
    ReasonCode.PACKAGE_MOVED: "TAKEOUT",
    ReasonCode.PACKAGE_REMOVED_UNAUTHORIZED: "TAKEOUT",
}

_SEVERITY_RANK: dict[Severity, int] = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}


class IncidentService:
    """DB-backed service handling the incident lifecycle."""

    def __init__(self, session: Session, cooldown_seconds: float = 30.0) -> None:
        self._session = session
        self._cooldown = cooldown_seconds

    # ------------------------------------------------------------------ query

    def list_incidents(
        self,
        session_id: str | None = None,
        status: IncidentStatus | None = None,
        severity: Severity | None = None,
        limit: int = 100,
    ) -> list[Incident]:
        """Return incidents, newest first, optionally filtered."""
        statement = select(Incident)
        if session_id:
            statement = statement.where(Incident.session_id == session_id)
        if status:
            statement = statement.where(Incident.status == status.value)
        if severity:
            statement = statement.where(Incident.severity == severity.value)
        statement = statement.order_by(Incident.created_at.desc()).limit(limit)  # type: ignore[union-attr]
        return list(self._session.exec(statement).all())

    def get_incident(self, incident_id: str) -> Incident:
        """Return one incident.

        Raises:
            NotFoundError: If the incident does not exist.
        """
        incident = self._session.get(Incident, incident_id)
        if incident is None:
            raise NotFoundError("Incident", incident_id)
        return incident

    def get_events(self, incident: Incident) -> list[Event]:
        """Return the events that triggered the incident, in time order."""
        if not incident.event_ids:
            return []
        statement = (
            select(Event)
            .where(Event.event_id.in_(incident.event_ids))
            .order_by(Event.timestamp_s)  # type: ignore[union-attr]
        )
        return list(self._session.exec(statement).all())

    # ----------------------------------------------------------------- mutate

    def create_or_escalate(
        self,
        assessment: ThreatAssessment,
        session_id: str | None = None,
        video_id: str | None = None,
        now: datetime | None = None,
    ) -> tuple[Incident, bool]:
        """Create an incident for a threat assessment, or escalate an existing one.

        Args:
            assessment: Output of the threat engine.
            session_id: Protection session the events belong to.
            video_id: Video the events came from, used later for evidence.
            now: Wall-clock timestamp, used for bookkeeping only.

        Returns:
            A tuple ``(incident, created)`` where ``created`` is ``True`` when a
            new incident was opened and ``False`` when an existing one was
            escalated.
        """
        if not assessment.should_create_incident or not assessment.reason_codes:
            raise ValidationError("A threat assessment without rules cannot create an incident")

        reference = now or datetime.now(UTC)
        family = self._family_for(assessment.reason_codes)
        existing = self._find_duplicate(assessment, session_id, family)

        if existing is not None:
            return self._escalate(existing, assessment, reference), False

        incident = Incident(
            incident_id=str(uuid.uuid4()),
            session_id=session_id,
            severity=(assessment.severity or Severity.LOW).value,
            reason_codes=[code.value for code in assessment.reason_codes],
            event_ids=list(assessment.event_ids),
            person_track_ids=list(assessment.person_track_ids),
            start_s=assessment.start_s or 0.0,
            end_s=assessment.end_s if assessment.end_s is not None else 0.0,
            status=IncidentStatus.OPEN.value,
            video_id=video_id,
            created_at=reference,
            updated_at=reference,
        )
        self._session.add(incident)
        self._session.commit()
        self._session.refresh(incident)
        logger.info(
            "Incident created incident_id=%s severity=%s reasons=%s session=%s",
            incident.incident_id,
            incident.severity,
            ",".join(incident.reason_codes),
            session_id,
        )
        return incident, True

    def review(
        self,
        incident_id: str,
        status: IncidentStatus,
        note: str | None = None,
        now: datetime | None = None,
    ) -> Incident:
        """Mark an incident as reviewed or dismissed.

        Reviewing an incident never ends the protection session: protection state
        and incident state are separate concerns.
        """
        if status is IncidentStatus.OPEN:
            raise ValidationError("An incident must be reviewed or dismissed, not re-opened here")
        incident = self.get_incident(incident_id)
        incident.status = status.value
        incident.review_note = note
        incident.updated_at = now or datetime.now(UTC)
        self._session.add(incident)
        self._session.commit()
        self._session.refresh(incident)
        logger.info("Incident %s marked as %s", incident_id, status.value)
        return incident

    def set_explanation(self, incident_id: str, explanation: str) -> Incident:
        """Store the LLM explanation on the incident."""
        incident = self.get_incident(incident_id)
        incident.explanation = explanation
        incident.updated_at = datetime.now(UTC)
        self._session.add(incident)
        self._session.commit()
        self._session.refresh(incident)
        return incident

    def set_evidence(self, incident_id: str, evidence_path: str, metadata: str | None = None) -> Incident:
        """Store the evidence bundle path on the incident."""
        incident = self.get_incident(incident_id)
        incident.evidence_path = evidence_path
        incident.evidence_metadata = metadata
        incident.updated_at = datetime.now(UTC)
        self._session.add(incident)
        self._session.commit()
        self._session.refresh(incident)
        return incident

    # ---------------------------------------------------------------- helpers

    def _family_for(self, reason_codes: Sequence[ReasonCode]) -> str:
        """Return the reason family of an assessment."""
        families = {REASON_FAMILIES.get(code, "OTHER") for code in reason_codes}
        if len(families) == 1:
            return families.pop()
        return "MIXED:" + ",".join(sorted(families))

    @staticmethod
    def _parse_codes(reason_codes: Sequence[str]) -> list[ReasonCode]:
        """Parse stored reason codes, ignoring unknown values."""
        parsed: list[ReasonCode] = []
        for code in reason_codes:
            try:
                parsed.append(ReasonCode(code))
            except ValueError:
                continue
        return parsed

    def _find_duplicate(
        self,
        assessment: ThreatAssessment,
        session_id: str | None,
        family: str,
    ) -> Incident | None:
        """Return the open incident that should absorb this assessment, if any.

        The match is ``(session, person track, reason group)``:

        * the same person and the same reason group is always the same
          situation, so the incident is escalated instead of duplicated;
        * the same person with a different reason group inside the cooldown
          window is an escalation of the same incident;
        * the same person with a different reason group after the cooldown gets
          a new incident, because it is a qualitatively different event.
        """
        if session_id is None:
            return None
        statement = (
            select(Incident)
            .where(Incident.session_id == session_id)
            .where(Incident.status == IncidentStatus.OPEN.value)
            .order_by(Incident.created_at.desc())  # type: ignore[union-attr]
        )
        candidates = list(self._session.exec(statement).all())
        if not candidates:
            return None

        event_time = assessment.end_s if assessment.end_s is not None else 0.0

        for candidate in candidates:
            if not self._same_people(candidate, assessment.person_track_ids):
                continue

            candidate_family = self._family_for(self._parse_codes(candidate.reason_codes))
            if candidate_family == family:
                return candidate
            if abs(event_time - candidate.end_s) <= self._cooldown:
                return candidate
        return None

    @staticmethod
    def _same_people(candidate: Incident, person_track_ids: Sequence[int]) -> bool:
        """Return whether the incident involves the same person tracks.

        An incident without any known person track matches everything: we cannot
        prove that it is a different person, and merging is safer than
        duplicating an alert.
        """
        if not candidate.person_track_ids:
            return True
        if not person_track_ids:
            return False
        return bool(set(candidate.person_track_ids) & set(person_track_ids))

    def _escalate(
        self,
        incident: Incident,
        assessment: ThreatAssessment,
        now: datetime,
    ) -> Incident:
        """Raise the severity of an existing incident and merge the new evidence."""
        new_severity = assessment.severity or Severity.LOW
        if _SEVERITY_RANK[new_severity] > _SEVERITY_RANK[Severity(incident.severity)]:
            incident.severity = new_severity.value

        for code in assessment.reason_codes:
            if code.value not in incident.reason_codes:
                incident.reason_codes.append(code.value)

        for event_id in assessment.event_ids:
            if event_id not in incident.event_ids:
                incident.event_ids.append(event_id)

        for track_id in assessment.person_track_ids:
            if track_id not in incident.person_track_ids:
                incident.person_track_ids.append(track_id)

        if assessment.start_s is not None:
            incident.start_s = min(incident.start_s, assessment.start_s)
        if assessment.end_s is not None:
            incident.end_s = max(incident.end_s, assessment.end_s)

        incident.updated_at = now
        self._session.add(incident)
        self._session.commit()
        self._session.refresh(incident)
        logger.info(
            "Incident escalated incident_id=%s severity=%s reasons=%s",
            incident.incident_id,
            incident.severity,
            ",".join(incident.reason_codes),
        )
        return incident
