"""Unit tests for the pure protection state machine.

Tests every valid transition, every invalid transition raising
``InvalidTransition``, timeout detection and ``seconds_remaining``.
"""

from datetime import UTC, datetime, timedelta

import pytest

from backend.core.exceptions import InvalidTransition
from backend.schemas.enums import ProtectionState, RuleTrigger
from backend.services.protection_service import (
    can_transition,
    is_expired,
    seconds_remaining,
    transition,
)


class TestValidTransitions:
    """Test every valid transition in the TRANSITIONS table."""

    def test_idle_to_package_detected_via_delivery(self) -> None:
        result = transition(ProtectionState.IDLE, RuleTrigger.DELIVERY_CONFIRMED)
        assert result is ProtectionState.PACKAGE_DETECTED

    def test_idle_to_package_detected_via_manual(self) -> None:
        result = transition(ProtectionState.IDLE, RuleTrigger.MANUAL_START)
        assert result is ProtectionState.PACKAGE_DETECTED

    def test_package_detected_to_protection_active(self) -> None:
        result = transition(ProtectionState.PACKAGE_DETECTED, RuleTrigger.PROTECTION_ACTIVATED)
        assert result is ProtectionState.PROTECTION_ACTIVE

    def test_package_detected_to_ended_via_manual(self) -> None:
        result = transition(ProtectionState.PACKAGE_DETECTED, RuleTrigger.MANUAL_END)
        assert result is ProtectionState.PROTECTION_ENDED

    def test_package_detected_to_timeout(self) -> None:
        result = transition(ProtectionState.PACKAGE_DETECTED, RuleTrigger.TIMEOUT_ELAPSED)
        assert result is ProtectionState.PROTECTION_TIMEOUT

    def test_active_to_retrieved(self) -> None:
        result = transition(ProtectionState.PROTECTION_ACTIVE, RuleTrigger.PACKAGE_RETRIEVED)
        assert result is ProtectionState.PACKAGE_RETRIEVED

    def test_active_to_timeout(self) -> None:
        result = transition(ProtectionState.PROTECTION_ACTIVE, RuleTrigger.TIMEOUT_ELAPSED)
        assert result is ProtectionState.PROTECTION_TIMEOUT

    def test_active_to_ended_via_manual(self) -> None:
        result = transition(ProtectionState.PROTECTION_ACTIVE, RuleTrigger.MANUAL_END)
        assert result is ProtectionState.PROTECTION_ENDED

    def test_retrieved_to_ended(self) -> None:
        result = transition(ProtectionState.PACKAGE_RETRIEVED, RuleTrigger.MANUAL_END)
        assert result is ProtectionState.PROTECTION_ENDED

    def test_timeout_to_ended(self) -> None:
        result = transition(ProtectionState.PROTECTION_TIMEOUT, RuleTrigger.MANUAL_END)
        assert result is ProtectionState.PROTECTION_ENDED


class TestInvalidTransitions:
    """Every invalid trigger in a state must raise InvalidTransition."""

    @pytest.mark.parametrize(
        ("state", "trigger"),
        [
            (ProtectionState.IDLE, RuleTrigger.PACKAGE_RETRIEVED),
            (ProtectionState.IDLE, RuleTrigger.PROTECTION_ACTIVATED),
            (ProtectionState.IDLE, RuleTrigger.TIMEOUT_ELAPSED),
            (ProtectionState.IDLE, RuleTrigger.MANUAL_END),
            (ProtectionState.PACKAGE_DETECTED, RuleTrigger.DELIVERY_CONFIRMED),
            (ProtectionState.PACKAGE_DETECTED, RuleTrigger.PACKAGE_RETRIEVED),
            (ProtectionState.PROTECTION_ACTIVE, RuleTrigger.DELIVERY_CONFIRMED),
            (ProtectionState.PROTECTION_ACTIVE, RuleTrigger.MANUAL_START),
            (ProtectionState.PROTECTION_ACTIVE, RuleTrigger.PROTECTION_ACTIVATED),
            (ProtectionState.PACKAGE_RETRIEVED, RuleTrigger.DELIVERY_CONFIRMED),
            (ProtectionState.PACKAGE_RETRIEVED, RuleTrigger.TIMEOUT_ELAPSED),
            (ProtectionState.PROTECTION_TIMEOUT, RuleTrigger.DELIVERY_CONFIRMED),
            (ProtectionState.PROTECTION_ENDED, RuleTrigger.MANUAL_END),
            (ProtectionState.PROTECTION_ENDED, RuleTrigger.DELIVERY_CONFIRMED),
        ],
    )
    def test_invalid_transition_raises(self, state: ProtectionState, trigger: RuleTrigger) -> None:
        with pytest.raises(InvalidTransition):
            transition(state, trigger)


class TestCanTransition:
    """Test the ``can_transition`` helper."""

    def test_returns_true_for_valid(self) -> None:
        assert can_transition(ProtectionState.IDLE, RuleTrigger.MANUAL_START) is True

    def test_returns_false_for_invalid(self) -> None:
        assert can_transition(ProtectionState.IDLE, RuleTrigger.MANUAL_END) is False

    def test_returns_false_for_ended(self) -> None:
        assert can_transition(ProtectionState.PROTECTION_ENDED, RuleTrigger.MANUAL_END) is False


class TestExpiry:
    """Test the ``is_expired`` and ``seconds_remaining`` pure helpers."""

    def test_not_expired_before_deadline(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        expires_at = now + timedelta(minutes=30)
        assert is_expired(expires_at, now) is False

    def test_expired_at_deadline(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert is_expired(now, now) is True

    def test_expired_after_deadline(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        expires_at = now - timedelta(seconds=1)
        assert is_expired(expires_at, now) is True

    def test_seconds_remaining_positive(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        expires_at = now + timedelta(minutes=5)
        assert seconds_remaining(expires_at, now) == 300

    def test_seconds_remaining_zero_when_expired(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        expires_at = now - timedelta(seconds=10)
        assert seconds_remaining(expires_at, now) == 0

    def test_seconds_remaining_never_negative(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        expires_at = now - timedelta(hours=1)
        assert seconds_remaining(expires_at, now) == 0
