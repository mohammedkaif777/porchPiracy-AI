"""Shared enumerations for the porchPiracyAI contracts.

This module is part of the frozen contract (see ``DEVELOPMENT.md`` section 5.1).
Change anything here only by announcement in the group chat, in the same PR that
updates the schema files.

Every enum derives from ``str`` so the values serialise to plain JSON strings and
compare equal to their string representation.
"""

from enum import Enum


class EventType(str, Enum):
    """Events produced by the vision pipeline and consumed by the rule engine."""

    PACKAGE_DETECTED = "PACKAGE_DETECTED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    PERSON_APPROACHING = "PERSON_APPROACHING"
    PERSON_NEAR_PACKAGE = "PERSON_NEAR_PACKAGE"
    LOITERING_DETECTED = "LOITERING_DETECTED"
    PACKAGE_INTERACTION = "PACKAGE_INTERACTION"
    PACKAGE_MOVEMENT_DETECTED = "PACKAGE_MOVEMENT_DETECTED"
    PACKAGE_REMOVED = "PACKAGE_REMOVED"
    PACKAGE_RETRIEVED = "PACKAGE_RETRIEVED"


class ProtectionState(str, Enum):
    """States of the protection state machine (see ``DEVELOPMENT.md`` 6.1)."""

    IDLE = "IDLE"
    PACKAGE_DETECTED = "PACKAGE_DETECTED"
    PROTECTION_ACTIVE = "PROTECTION_ACTIVE"
    PACKAGE_RETRIEVED = "PACKAGE_RETRIEVED"
    PROTECTION_TIMEOUT = "PROTECTION_TIMEOUT"
    PROTECTION_ENDED = "PROTECTION_ENDED"


class Severity(str, Enum):
    """Severity of an incident."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ThreatLevel(str, Enum):
    """Overall threat level of the active protection session."""

    NONE = "NONE"
    MONITORING = "MONITORING"
    SUSPICIOUS = "SUSPICIOUS"
    THREAT = "THREAT"


class ReasonCode(str, Enum):
    """Deterministic reason codes explaining why an incident was raised."""

    LOITERING_OVER_THRESHOLD = "LOITERING_OVER_THRESHOLD"
    PACKAGE_INTERACTION = "PACKAGE_INTERACTION"
    PACKAGE_MOVED = "PACKAGE_MOVED"
    PACKAGE_REMOVED_UNAUTHORIZED = "PACKAGE_REMOVED_UNAUTHORIZED"


class IncidentStatus(str, Enum):
    """Lifecycle of an incident. Independent from the protection state."""

    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    DISMISSED = "DISMISSED"


class SessionSource(str, Enum):
    """What started a protection session."""

    MANUAL = "MANUAL"
    SIMULATED_DELIVERY = "SIMULATED_DELIVERY"
    RING = "RING"


class PackageStatus(str, Enum):
    """Lifecycle of a detected package."""

    DETECTED = "DETECTED"
    MOVED = "MOVED"
    REMOVED = "REMOVED"
    RETRIEVED = "RETRIEVED"


class VideoStatus(str, Enum):
    """Lifecycle of an uploaded video and its analysis run."""

    UPLOADED = "UPLOADED"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NotificationChannel(str, Enum):
    """Channels a homeowner notification can be delivered through."""

    DASHBOARD = "dashboard"
    TELEGRAM = "telegram"
    DETERRENT = "deterrent"


class AllowedAction(str, Enum):
    """Allowlist of external actions that may be triggered on a device.

    Only members of this enum can ever be executed. The LLM has no path to it.
    """

    SPEAK_WARNING = "SPEAK_WARNING"
    ENABLE_SIREN = "ENABLE_SIREN"
    ENABLE_LIGHT = "ENABLE_LIGHT"
    SNAPSHOT = "SNAPSHOT"
    NOTIFY_OWNER = "NOTIFY_OWNER"


class RuleTrigger(str, Enum):
    """Triggers accepted by the pure protection state machine."""

    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    MANUAL_START = "MANUAL_START"
    PACKAGE_CONFIRMED = "PACKAGE_CONFIRMED"
    PROTECTION_ACTIVATED = "PROTECTION_ACTIVATED"
    PACKAGE_RETRIEVED = "PACKAGE_RETRIEVED"
    TIMEOUT_ELAPSED = "TIMEOUT_ELAPSED"
    MANUAL_END = "MANUAL_END"
