"""Protection state machine.

Two layers live here:

* **Pure functions** (:func:`transition`, :func:`is_expired`,
  :func:`seconds_remaining`) that never touch the database, the filesystem or the
  clock. ``now`` is always passed in. These are the functions with unit tests.
* A thin **session manager** (:class:`ProtectionSessionManager`) that persists
  sessions and delegates every state decision to the pure functions.

The state graph (``DEVELOPMENT.md`` section 6.1)::

    IDLE --delivery/manual--> PACKAGE_DETECTED --> PROTECTION_ACTIVE
                                                            |
              +----------------------+---------------------+------------------+
              v                      v                     v                  v
      PACKAGE_RETRIEVED     PROTECTION_TIMEOUT        MANUAL_END       (events)
              |                      |                     |
              +----------------------+---------------------+
                                     v
                             PROTECTION_ENDED
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from backend.core.exceptions import (
    InvalidTransition,
    NoActiveProtectionError,
    NotFoundError,
    ProtectionAlreadyActiveError,
)
from backend.core.logging_config import get_logger
from backend.models.protection_session import ProtectionSession
from backend.schemas.enums import (
    EventType,
    ProtectionState,
    RuleTrigger,
    SessionSource,
    ThreatLevel,
)

logger = get_logger(__name__)

#: States in which a package is still being protected.
ACTIVE_STATES: frozenset[ProtectionState] = frozenset(
    {ProtectionState.PACKAGE_DETECTED, ProtectionState.PROTECTION_ACTIVE}
)

#: States that end a session.
TERMINAL_STATES: frozenset[ProtectionState] = frozenset(
    {ProtectionState.PROTECTION_ENDED, ProtectionState.PACKAGE_RETRIEVED, ProtectionState.PROTECTION_TIMEOUT}
)

#: The transition table. Anything not listed here is an invalid transition.
TRANSITIONS: dict[ProtectionState, dict[RuleTrigger, ProtectionState]] = {
    ProtectionState.IDLE: {
        RuleTrigger.DELIVERY_CONFIRMED: ProtectionState.PACKAGE_DETECTED,
        RuleTrigger.MANUAL_START: ProtectionState.PACKAGE_DETECTED,
    },
    ProtectionState.PACKAGE_DETECTED: {
        RuleTrigger.PROTECTION_ACTIVATED: ProtectionState.PROTECTION_ACTIVE,
        RuleTrigger.MANUAL_END: ProtectionState.PROTECTION_ENDED,
        RuleTrigger.TIMEOUT_ELAPSED: ProtectionState.PROTECTION_TIMEOUT,
    },
    ProtectionState.PROTECTION_ACTIVE: {
        RuleTrigger.PACKAGE_RETRIEVED: ProtectionState.PACKAGE_RETRIEVED,
        RuleTrigger.TIMEOUT_ELAPSED: ProtectionState.PROTECTION_TIMEOUT,
        RuleTrigger.MANUAL_END: ProtectionState.PROTECTION_ENDED,
    },
    ProtectionState.PACKAGE_RETRIEVED: {
        RuleTrigger.MANUAL_END: ProtectionState.PROTECTION_ENDED,
    },
    ProtectionState.PROTECTION_TIMEOUT: {
        RuleTrigger.MANUAL_END: ProtectionState.PROTECTION_ENDED,
    },
    ProtectionState.PROTECTION_ENDED: {},
}


def transition(
    state: ProtectionState,
    trigger: RuleTrigger,
    now: datetime | None = None,
) -> ProtectionState:
    """Return the state reached by applying ``trigger`` to ``state``.

    This is a pure function: it performs no I/O, reads no clock and has no side
    effects. ``now`` is accepted so callers can pass a single timestamp for a
    whole batch of transitions; it does not influence the result.

    Args:
        state: Current protection state.
        trigger: The event that asks for a state change.
        now: Optional reference time, kept for interface stability.

    Returns:
        The new protection state.

    Raises:
        InvalidTransition: If the trigger is not allowed in the current state.
    """
    allowed = TRANSITIONS.get(state, {})
    if trigger not in allowed:
        raise InvalidTransition(state.value, trigger.value)
    return allowed[trigger]


def can_transition(state: ProtectionState, trigger: RuleTrigger) -> bool:
    """Return whether ``trigger`` is allowed in ``state``."""
    return trigger in TRANSITIONS.get(state, {})


def is_expired(expires_at: datetime, now: datetime) -> bool:
    """Return whether a session deadline has passed at ``now``."""
    return _as_utc(now) >= _as_utc(expires_at)


def seconds_remaining(expires_at: datetime, now: datetime) -> int:
    """Return the whole seconds left before ``expires_at``, never negative."""
    delta = _as_utc(expires_at) - _as_utc(now)
    return max(0, int(delta.total_seconds()))


def _as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def event_to_trigger(event_type: EventType) -> RuleTrigger | None:
    """Map a vision event type onto a state machine trigger."""
    mapping: dict[EventType, RuleTrigger] = {
        EventType.DELIVERY_CONFIRMED: RuleTrigger.DELIVERY_CONFIRMED,
        EventType.PACKAGE_DETECTED: RuleTrigger.PACKAGE_CONFIRMED,
        EventType.PACKAGE_RETRIEVED: RuleTrigger.PACKAGE_RETRIEVED,
    }
    return mapping.get(event_type)


class ProtectionSessionManager:
    """DB-backed session manager built on top of the pure state machine."""

    def __init__(self, session: Session, timeout_minutes: int = 360) -> None:
        self._session = session
        self._timeout_minutes = timeout_minutes

    # ------------------------------------------------------------------ query

    def get_active_session(self) -> ProtectionSession | None:
        """Return the currently active session, if any."""
        statement = (
            select(ProtectionSession)
            .where(ProtectionSession.state.in_([s.value for s in ACTIVE_STATES]))
            .order_by(ProtectionSession.started_at.desc())  # type: ignore[union-attr]
        )
        return self._session.exec(statement).first()

    def get_session(self, session_id: str) -> ProtectionSession:
        """Return a session by id.

        Raises:
            NotFoundError: If the session does not exist.
        """
        session = self._session.get(ProtectionSession, session_id)
        if session is None:
            raise NotFoundError("Protection session", session_id)
        return session

    def list_sessions(self, limit: int = 50) -> list[ProtectionSession]:
        """Return the most recent sessions, newest first."""
        statement = (
            select(ProtectionSession)
            .order_by(ProtectionSession.started_at.desc())  # type: ignore[union-attr]
            .limit(limit)
        )
        return list(self._session.exec(statement).all())

    # ----------------------------------------------------------------- mutate

    def start_session(
        self,
        source: SessionSource = SessionSource.MANUAL,
        package_track_id: int | None = None,
        protection_zone: list[list[float]] | None = None,
        now: datetime | None = None,
        video_id: str | None = None,
    ) -> ProtectionSession:
        """Start a new protection session.

        Raises:
            ProtectionAlreadyActiveError: If a session is already active.
        """
        reference = now or datetime.now(UTC)
        if self.get_active_session() is not None:
            active = self.get_active_session()
            assert active is not None  # noqa: S101 - narrowing for the type checker
            raise ProtectionAlreadyActiveError(active.session_id)

        trigger = (
            RuleTrigger.DELIVERY_CONFIRMED
            if source is not SessionSource.MANUAL
            else RuleTrigger.MANUAL_START
        )
        state = transition(ProtectionState.IDLE, trigger, reference)

        record = ProtectionSession(
            session_id=str(uuid.uuid4()),
            state=state.value,
            source=source.value,
            threat_level=ThreatLevel.NONE.value,
            package_track_id=package_track_id,
            protection_zone=json.dumps(protection_zone) if protection_zone else None,
            started_at=reference,
            expires_at=reference + timedelta(minutes=self._timeout_minutes),
            video_id=video_id,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        logger.info(
            "Protection session started session_id=%s state=%s source=%s",
            record.session_id,
            record.state,
            record.source,
        )
        return record

    def apply_trigger(
        self,
        trigger: RuleTrigger,
        now: datetime | None = None,
        session: ProtectionSession | None = None,
    ) -> ProtectionSession:
        """Apply a trigger to the active session and persist the new state.

        Raises:
            NoActiveProtectionError: If there is no active session.
            InvalidTransition: If the trigger is not allowed in the current state.
        """
        reference = now or datetime.now(UTC)
        target = session or self.get_active_session()
        if target is None:
            raise NoActiveProtectionError()

        new_state = transition(ProtectionState(target.state), trigger, reference)
        target.state = new_state.value
        if new_state in TERMINAL_STATES and new_state is not ProtectionState.PROTECTION_ENDED:
            target.ended_at = reference
            target.end_reason = trigger.value
        self._session.add(target)
        self._session.commit()
        self._session.refresh(target)
        logger.info(
            "Protection transition session_id=%s trigger=%s -> %s",
            target.session_id,
            trigger.value,
            target.state,
        )
        return target

    def end_session(self, now: datetime | None = None) -> ProtectionSession:
        """End the active session manually.

        Raises:
            NoActiveProtectionError: If there is no active session.
        """
        reference = now or datetime.now(UTC)
        target = self.get_active_session()
        if target is None:
            raise NoActiveProtectionError()
        if not can_transition(ProtectionState(target.state), RuleTrigger.MANUAL_END):
            # Already finished: finalise it so the caller always gets a session.
            target.state = ProtectionState.PROTECTION_ENDED.value
            target.ended_at = reference
            target.end_reason = RuleTrigger.MANUAL_END.value
            self._session.add(target)
            self._session.commit()
            self._session.refresh(target)
            return target
        return self.apply_trigger(RuleTrigger.MANUAL_END, reference, target)

    def check_timeout(self, now: datetime | None = None) -> ProtectionSession | None:
        """End the active session if its deadline has passed.

        Returns:
            The expired session when it was closed, otherwise ``None``.
        """
        reference = now or datetime.now(UTC)
        target = self.get_active_session()
        if target is None:
            return None
        if not is_expired(target.expires_at, reference):
            return None
        closed = self.apply_trigger(RuleTrigger.TIMEOUT_ELAPSED, reference, target)
        return self.apply_trigger(RuleTrigger.MANUAL_END, reference, closed)

    def set_threat_level(self, level: ThreatLevel, session: ProtectionSession | None = None) -> None:
        """Persist the current threat level on the session."""
        target = session or self.get_active_session()
        if target is None:
            return
        target.threat_level = level.value
        self._session.add(target)
        self._session.commit()

    def apply_event(
        self,
        event_type: EventType,
        now: datetime | None = None,
        session: ProtectionSession | None = None,
    ) -> ProtectionSession | None:
        """Apply a vision event to the state machine.

        Returns:
            The updated session, or ``None`` when the event does not change the
            state machine.
        """
        trigger = event_to_trigger(event_type)
        if trigger is None:
            return None
        target = session or self.get_active_session()
        if target is None:
            return None
        if not can_transition(ProtectionState(target.state), trigger):
            return None
        return self.apply_trigger(trigger, now, target)


def zone_from_record(record: ProtectionSession) -> list[list[float]] | None:
    """Return the protection zone polygon stored on a session record."""
    if not record.protection_zone:
        return None
    try:
        parsed: Any = json.loads(record.protection_zone)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    return parsed


def summarise_sessions(sessions: Iterable[ProtectionSession]) -> list[dict]:
    """Return a JSON friendly summary of the given sessions."""
    return [
        {
            "session_id": record.session_id,
            "state": record.state,
            "source": record.source,
            "threat_level": record.threat_level,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }
        for record in sessions
    ]
