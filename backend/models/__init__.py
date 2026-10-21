"""SQLModel tables for porchPiracyAI.

Importing this package registers every table on ``SQLModel.metadata``.
"""

from backend.models.event import Event
from backend.models.incident import Incident
from backend.models.notification import Notification
from backend.models.package import Package
from backend.models.protection_session import ProtectionSession
from backend.models.video import Video

__all__ = [
    "Event",
    "Incident",
    "Notification",
    "Package",
    "ProtectionSession",
    "Video",
]
