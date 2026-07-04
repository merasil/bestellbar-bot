"""Pushover notification adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from bestellbar_bot.notifiers.base import NotificationError
from bestellbar_bot.parser import Update

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"


@dataclass
class PushoverNotifier:
    """Sends update notifications through Pushover."""

    api_token: str
    user_key: str
    device: str | None = None
    timeout: float = 15.0
    api_url: str = PUSHOVER_API_URL
    http_client: httpx.Client | None = None

    def send_update(self, update: Update) -> None:
        """Sends one Pushover notification."""
        if not self.api_token.strip() or not self.user_key.strip():
            raise NotificationError("Pushover credentials are missing.")

        payload = self._payload(update)
        try:
            if self.http_client is not None:
                resp = self.http_client.post(
                    self.api_url,
                    data=payload,
                    timeout=self.timeout,
                )
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(self.api_url, data=payload)
        except httpx.RequestError as exc:
            raise NotificationError(
                f"Pushover request failed: {exc.__class__.__name__}."
            ) from exc

        _raise_for_pushover_error(resp)

    def _payload(self, update: Update) -> dict[str, str | int]:
        message_parts = [update.summary or update.title]
        if update.timestamp_text:
            message_parts.append(update.timestamp_text)
        if update.source_text:
            message_parts.append(update.source_text)

        payload: dict[str, str | int] = {
            "token": self.api_token,
            "user": self.user_key,
            "title": update.title,
            "message": "\n".join(message_parts),
            "priority": 0,
        }
        if update.url:
            payload["url"] = update.url
            payload["url_title"] = "Open update"
        if self.device:
            payload["device"] = self.device
        return payload


def _raise_for_pushover_error(resp: httpx.Response) -> None:
    if resp.status_code != 200:
        raise NotificationError(
            f"Pushover request failed with HTTP status {resp.status_code}."
        )

    try:
        payload: Any = resp.json()
    except ValueError as exc:
        raise NotificationError("Pushover returned invalid JSON.") from exc

    if not isinstance(payload, dict) or payload.get("status") != 1:
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if isinstance(errors, list) and errors:
            detail = "; ".join(str(error) for error in errors)
            raise NotificationError(f"Pushover rejected the request: {detail}")
        raise NotificationError("Pushover rejected the request.")
