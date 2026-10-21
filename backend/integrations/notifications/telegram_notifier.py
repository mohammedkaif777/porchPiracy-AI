"""Optional Telegram notifier.

Disabled unless both ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` are set.
It sends a short text alert only. No video, no image and no frame ever leaves
the machine through this channel.
"""

from __future__ import annotations

import httpx

from backend.core.config import Settings, get_settings
from backend.core.logging_config import get_logger
from backend.integrations.notifications.base import NotificationPayload, Notifier
from backend.schemas.enums import NotificationChannel

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier(Notifier):
    """Sends a text alert to a Telegram chat."""

    channel = NotificationChannel.TELEGRAM

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def available(self) -> bool:
        """True when the Telegram credentials are configured."""
        return self._settings.telegram_enabled

    def notify(self, payload: NotificationPayload) -> bool:
        """Send the message to Telegram.

        Returns:
            True when the message was accepted by Telegram.
        """
        if not self.available():
            logger.info("Telegram is not configured, the notification was not sent")
            return False

        url = TELEGRAM_API.format(token=self._settings.telegram_bot_token)
        body = {"chat_id": self._settings.telegram_chat_id, "text": payload.message}
        try:
            response = httpx.post(url, json=body, timeout=10.0)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Telegram delivery failed: %s", exc)
            return False
        return True
