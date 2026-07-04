"""Notifier interfaces and shared errors."""

from __future__ import annotations

import logging
from typing import Protocol

from bestellbar_bot.parser import Update


class NotificationError(RuntimeError):
    """Raised when an update notification cannot be delivered."""


class Notifier(Protocol):
    """Sends update notifications."""

    def send_update(self, update: Update) -> None:
        """Sends one update notification."""


class DryRunNotifier:
    """Notifier that records intended sends without external side effects."""

    def __init__(self) -> None:
        self.sent_updates: list[Update] = []
        self._logger = logging.getLogger(__name__)

    def send_update(self, update: Update) -> None:
        """Records an update that would have been sent."""
        self.sent_updates.append(update)
        self._logger.info("Dry-run notification: %s", update.title)
