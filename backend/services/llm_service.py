"""Local LLM explanations for incidents.

The LLM is strictly an explainer. It receives a **compact structured summary**
(reason codes, durations, event types), never frames, and it can never create
an incident, change a severity or trigger an action.

When Ollama is disabled or unreachable, a deterministic template produces the
explanation, so the demo never depends on a local model being installed.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from backend.core.config import Settings, get_settings
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are the incident explainer of a home package protection system. "
    "Describe only the provided events. Do not invent details. Do not identify people. "
    "Never state that a crime happened: the wording is always 'potential package theft, "
    "for review'. Answer in 2 to 3 sentences."
)

_REASON_TEXT: dict[str, str] = {
    "LOITERING_OVER_THRESHOLD": "a person stayed near the package longer than the configured threshold",
    "PACKAGE_INTERACTION": "a person's bounding box overlapped the package",
    "PACKAGE_MOVED": "the package moved away from the position where it was delivered",
    "PACKAGE_REMOVED_UNAUTHORIZED": "the package left the protected area while a person was next to it",
}


class LLMService:
    """Generates a short explanation of an incident, with a template fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        """True when the LLM is enabled and reachable."""
        return self._settings.llm_enabled

    def explain(self, summary: dict[str, Any]) -> str:
        """Return a 2 to 3 sentence explanation of the incident summary.

        Args:
            summary: Compact structured summary of the incident.

        Returns:
            The explanation text. Falls back to a deterministic template.
        """
        if self._settings.llm_enabled:
            text = self._explain_with_ollama(summary)
            if text:
                return text
        return template_explanation(summary)

    def _explain_with_ollama(self, summary: dict[str, Any]) -> str | None:
        """Ask the local Ollama instance for an explanation."""
        url = f"{self._settings.ollama_url.rstrip('/')}/api/generate"
        payload = {
            "model": self._settings.ollama_model,
            "prompt": f"{SYSTEM_PROMPT}\n\nIncident summary:\n{json.dumps(summary, indent=2)}",
            "stream": False,
            "options": {"temperature": 0.2},
        }
        try:
            response = httpx.post(url, json=payload, timeout=self._settings.llm_timeout_seconds)
            response.raise_for_status()
            data = response.json()
            text = str(data.get("response", "")).strip()
            return text or None
        except Exception as exc:
            logger.warning("Ollama is unavailable, using the template explanation: %s", exc)
            return None


def template_explanation(summary: dict[str, Any]) -> str:
    """Return a deterministic explanation built from the incident summary.

    The template is the fallback when Ollama is disabled or unavailable. It only
    restates the structured facts, so it can never invent anything.
    """
    severity = str(summary.get("severity", "")).upper()
    reasons = [str(reason) for reason in summary.get("reason_codes", [])]
    duration = summary.get("duration_s")
    event_count = summary.get("event_count", 0)

    described = [_REASON_TEXT.get(reason, reason.replace("_", " ").lower()) for reason in reasons]
    if described:
        joined = "; ".join(described)
        first = f"Potential package theft, for review: {joined}."
    else:
        first = "Potential package theft, for review."

    if duration:
        second = f"The activity lasted about {float(duration):.0f} seconds"
    else:
        second = f"The activity was recorded across {event_count} events"
    if event_count and duration:
        second += f" and was derived from {event_count} recorded events"

    third = "This is a potential incident for homeowner review, not a confirmed theft."
    if severity == "HIGH":
        third = (
            "The evidence is strong, but this still requires homeowner review before any action is taken."
        )

    return f"{first} {second}. {third}"


def build_summary(
    severity: str,
    reason_codes: list[str],
    start_s: float,
    end_s: float,
    event_count: int,
    event_types: list[str] | None = None,
) -> dict[str, Any]:
    """Build the compact summary handed to the LLM."""
    return {
        "severity": severity,
        "reason_codes": list(reason_codes),
        "start_s": start_s,
        "end_s": end_s,
        "duration_s": max(0.0, end_s - start_s),
        "event_count": event_count,
        "event_types": list(event_types or []),
    }
