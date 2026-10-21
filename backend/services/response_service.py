"""Response orchestration: what happens when an incident is raised.

On a new incident the service:

1. notifies the homeowner (dashboard history, plus Telegram when configured);
2. logs the **simulated** deterrent, always labeled as simulated;
3. captures the evidence bundle (clip with blurred faces, key frames);
4. stores a plain-language explanation (local LLM or deterministic template).

The LLM never triggers any of this on its own: the incident was already created
by the deterministic rule engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from backend.core.config import Settings, get_settings
from backend.core.logging_config import get_logger
from backend.integrations.notifications.base import NotificationPayload
from backend.integrations.notifications.dashboard_notifier import DashboardNotifier
from backend.integrations.notifications.telegram_notifier import TelegramNotifier
from backend.models.event import Event
from backend.models.incident import Incident
from backend.schemas.enums import AllowedAction, NotificationChannel
from backend.services.evidence_service import create_evidence, write_metadata
from backend.services.incident_service import IncidentService
from backend.services.llm_service import LLMService, build_summary

logger = get_logger(__name__)

ALERT_PREFIX = "Potential package theft, for review"
DETERRENT_MESSAGE = (
    "Simulated Alexa deterrent: \"This package is being monitored. Please leave it where it is.\""
)


class ResponseService:
    """Runs the side effects of an incident."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._incidents = IncidentService(session)
        self._llm = LLMService(self._settings)

    def handle_new_incident(
        self,
        incident: Incident,
        events: list[Event] | None = None,
        video_path: str | None = None,
    ) -> Incident:
        """Run the full response for a new incident.

        Args:
            incident: The incident that was just created.
            events: The events that triggered it.
            video_path: Original video, used to cut the evidence clip.

        Returns:
            The incident, refreshed with the evidence path and the explanation.
        """
        event_list = events or []
        self._notify_homeowner(incident)
        self._log_deterrent(incident)
        if video_path:
            self._capture_evidence(incident, video_path)
        self._explain(incident, event_list)
        return self._incidents.get_incident(incident.incident_id)

    def handle_escalation(
        self,
        incident: Incident,
        events: list[Event] | None = None,
        video_path: str | None = None,
    ) -> Incident:
        """Run the lighter response for an incident that was escalated.

        The homeowner is only notified again when the cooldown has passed, so a
        long incident never turns into a stream of alerts. The explanation and
        the evidence are refreshed.
        """
        event_list = events or []
        if self._cooldown_elapsed(incident):
            self._notify_homeowner(incident)
        if video_path and not incident.evidence_path:
            self._capture_evidence(incident, video_path)
        self._explain(incident, event_list)
        return self._incidents.get_incident(incident.incident_id)

    def _cooldown_elapsed(self, incident: Incident) -> bool:
        """Return whether the homeowner may be notified again for this incident."""
        from sqlmodel import select  # noqa: PLC0415 - local import keeps the module light

        from backend.models.notification import Notification  # noqa: PLC0415 - local import

        statement = (
            select(Notification)
            .where(Notification.incident_id == incident.incident_id)
            .where(Notification.channel == NotificationChannel.DASHBOARD.value)
            .order_by(Notification.created_at.desc())  # type: ignore[union-attr]
            .limit(1)
        )
        latest = self._session.exec(statement).first()
        if latest is None or latest.created_at is None:
            return True
        latest_created = (
            latest.created_at
            if latest.created_at.tzinfo is not None
            else latest.created_at.replace(tzinfo=UTC)
        )
        elapsed = (datetime.now(UTC) - latest_created).total_seconds()
        return elapsed >= self._settings.incident_cooldown_seconds

    # ------------------------------------------------------------------ pieces

    def _notify_homeowner(self, incident: Incident) -> None:
        """Send the homeowner alert on every available channel."""
        message = self._alert_message(incident)
        payload = NotificationPayload(
            message=message,
            channel=NotificationChannel.DASHBOARD,
            incident_id=incident.incident_id,
            session_id=incident.session_id,
            simulated=True,
            detail={
                "severity": incident.severity,
                "reason_codes": list(incident.reason_codes),
            },
        )
        DashboardNotifier(self._session).notify(payload)

        telegram_payload = NotificationPayload(
            message=message,
            channel=NotificationChannel.TELEGRAM,
            incident_id=incident.incident_id,
            session_id=incident.session_id,
            simulated=False,
        )
        TelegramNotifier(self._settings).notify(telegram_payload)

    def _log_deterrent(self, incident: Incident) -> None:
        """Record the simulated deterrent.

        The record is flagged as simulated so the UI can label it and so a
        simulated feature can never be presented as a real device action.
        """
        payload = NotificationPayload(
            message=DETERRENT_MESSAGE,
            channel=NotificationChannel.DETERRENT,
            incident_id=incident.incident_id,
            session_id=incident.session_id,
            simulated=True,
            detail={"action": AllowedAction.SPEAK_WARNING.value, "device": "Simulated Alexa"},
        )
        DashboardNotifier(self._session).notify(payload)

    def _capture_evidence(self, incident: Incident, video_path: str) -> None:
        """Cut the evidence clip and store its path on the incident."""
        try:
            result = create_evidence(video_path, incident, self._settings)
        except Exception:
            logger.exception("Evidence capture failed for incident %s", incident.incident_id)
            return

        if not result.clip_path:
            logger.warning(
                "No evidence clip for incident %s: %s",
                incident.incident_id,
                result.metadata.get("error", "unknown reason"),
            )
            return

        output_dir = Path(result.clip_path).parent
        write_metadata(result, output_dir)
        self._incidents.set_evidence(
            incident.incident_id,
            result.clip_path,
            metadata=str(result.to_dict()),
        )

    def _explain(self, incident: Incident, events: list[Event]) -> None:
        """Store a plain-language explanation of the incident."""
        event_types = [event.type for event in events]
        summary = build_summary(
            severity=incident.severity,
            reason_codes=list(incident.reason_codes),
            start_s=incident.start_s,
            end_s=incident.end_s,
            event_count=len(events) or len(incident.event_ids),
            event_types=event_types,
        )
        explanation = self._llm.explain(summary)
        self._incidents.set_explanation(incident.incident_id, explanation)

    @staticmethod
    def _alert_message(incident: Incident) -> str:
        """Build the homeowner alert message. Never accuses anyone."""
        reasons = ", ".join(code.replace("_", " ").lower() for code in incident.reason_codes)
        severity = str(incident.severity).lower()
        return (
            f"{ALERT_PREFIX}. A {severity} incident was raised for the protected package "
            f"({reasons}). Please review the evidence clip."
        )
