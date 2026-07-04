from typing import Any

import pytest

from bestellbar_bot.notifiers.base import NotificationError
from bestellbar_bot.notifiers.pushover import PushoverNotifier
from bestellbar_bot.parser import Update


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


def _update() -> Update:
    return Update(
        fingerprint="abc",
        kind="info",
        title="Update title",
        summary="Update body",
        timestamp_text="2026-07-04T09:00:00+02:00",
        source_text="Amazon DE",
        url="https://example.com/update",
    )


def test_pushover_sends_expected_payload() -> None:
    client = FakeClient(FakeResponse(200, {"status": 1}))
    notifier = PushoverNotifier(
        api_token="token",
        user_key="user",
        device="iphone",
        http_client=client,  # type: ignore[arg-type]
    )

    notifier.send_update(_update())

    assert client.calls[0]["url"] == "https://api.pushover.net/1/messages.json"
    assert client.calls[0]["data"]["token"] == "token"
    assert client.calls[0]["data"]["user"] == "user"
    assert client.calls[0]["data"]["device"] == "iphone"
    assert client.calls[0]["data"]["title"] == "Update title"
    assert client.calls[0]["data"]["url"] == "https://example.com/update"


def test_pushover_raises_without_leaking_secrets() -> None:
    client = FakeClient(FakeResponse(401, {"status": 0}))
    notifier = PushoverNotifier(
        api_token="secret-token",
        user_key="secret-user",
        http_client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(NotificationError) as exc_info:
        notifier.send_update(_update())

    message = str(exc_info.value)
    assert "401" in message
    assert "secret-token" not in message
    assert "secret-user" not in message


def test_pushover_raises_for_rejected_json_response() -> None:
    client = FakeClient(FakeResponse(200, {"status": 0, "errors": ["bad user"]}))
    notifier = PushoverNotifier(
        api_token="token",
        user_key="user",
        http_client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(NotificationError, match="bad user"):
        notifier.send_update(_update())
