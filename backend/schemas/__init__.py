"""Shared contracts for porchPiracyAI.

Everything in this package is part of the frozen contract described in
``DEVELOPMENT.md`` section 5. Change it only by announcement, in the same PR.
"""

from backend.schemas.enums import (
    AllowedAction,
    EventType,
    IncidentStatus,
    NotificationChannel,
    PackageStatus,
    ProtectionState,
    ReasonCode,
    RuleTrigger,
    SessionSource,
    Severity,
    ThreatLevel,
    VideoStatus,
)
from backend.schemas.event_schema import (
    BBox,
    Detection,
    EventCreate,
    EventRead,
    Track,
)
from backend.schemas.incident_schema import (
    IncidentCreate,
    IncidentDetail,
    IncidentRead,
    IncidentReviewRequest,
    ThreatAssessment,
)
from backend.schemas.package_schema import PackageRead
from backend.schemas.protection_schema import (
    ProtectionEndResponse,
    ProtectionSessionRead,
    ProtectionStartRequest,
    SimulatedDeliveryRequest,
    Zone,
)
from backend.schemas.system_schema import (
    ActionResult,
    EvidenceKeyFrame,
    EvidenceRead,
    HealthResponse,
    NotificationRead,
    RingCapability,
    RingStatus,
    SettingsRead,
    SettingsUpdate,
    VideoAnalyzeResponse,
    VideoRead,
)

__all__ = [
    "ActionResult",
    "AllowedAction",
    "BBox",
    "Detection",
    "EventCreate",
    "EventRead",
    "EventType",
    "EvidenceKeyFrame",
    "EvidenceRead",
    "HealthResponse",
    "IncidentCreate",
    "IncidentDetail",
    "IncidentRead",
    "IncidentReviewRequest",
    "IncidentStatus",
    "NotificationChannel",
    "NotificationRead",
    "PackageRead",
    "PackageStatus",
    "ProtectionEndResponse",
    "ProtectionSessionRead",
    "ProtectionStartRequest",
    "ProtectionState",
    "ReasonCode",
    "RingCapability",
    "RingStatus",
    "RuleTrigger",
    "SessionSource",
    "SettingsRead",
    "SettingsUpdate",
    "Severity",
    "SimulatedDeliveryRequest",
    "ThreatAssessment",
    "ThreatLevel",
    "Track",
    "VideoAnalyzeResponse",
    "VideoRead",
    "VideoStatus",
    "Zone",
]
