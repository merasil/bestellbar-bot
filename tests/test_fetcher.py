from collections.abc import Callable
from typing import Any

import httpx
import pytest

from bestellbar_bot import fetcher
from bestellbar_bot.fetcher import FetchError, fetch_page


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code
        self.request = httpx.Request("GET", "https://example.com/product")

    def raise_for_status(self) -> None:
        if 200 <= self.status_code < 300:
            return

        response = httpx.Response(self.status_code, request=self.request)
        raise httpx.HTTPStatusError(
            f"HTTP status {self.status_code}",
            request=self.request,
            response=response,
        )


class FakeClient:
    def __init__(
        self,
        response: FakeResponse | None = None,
        error_factory: Callable[[str], Exception] | None = None,
    ) -> None:
        self.response = response or FakeResponse("")
        self.error_factory = error_factory
        self.requested_urls: list[str] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get(self, url: str) -> FakeResponse:
        self.requested_urls.append(url)
        if self.error_factory is not None:
            raise self.error_factory(url)
        return self.response


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    client: FakeClient,
) -> list[dict[str, Any]]:
    client_kwargs: list[dict[str, Any]] = []

    def fake_client_factory(**kwargs: Any) -> FakeClient:
        client_kwargs.append(kwargs)
        return client

    monkeypatch.setattr(fetcher.httpx, "Client", fake_client_factory)
    return client_kwargs


def test_fetch_page_returns_html_for_successful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient(FakeResponse("<html>available</html>"))
    _patch_client(monkeypatch, client)

    body = fetch_page("https://example.com/product", 3.5, "test-agent")

    assert body == "<html>available</html>"
    assert client.requested_urls == ["https://example.com/product"]


def test_fetch_page_sends_request_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient(FakeResponse("<html></html>"))
    client_kwargs = _patch_client(monkeypatch, client)

    fetch_page("https://example.com/product", 7.25, "bestellbar-test-agent")

    assert client_kwargs[0]["follow_redirects"] is True
    assert client_kwargs[0]["timeout"] == 7.25
    assert client_kwargs[0]["headers"]["User-Agent"] == "bestellbar-test-agent"
    assert "text/html" in client_kwargs[0]["headers"]["Accept"]


def test_fetch_page_raises_fetch_error_for_non_success_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient(FakeResponse("Service unavailable", status_code=503))
    _patch_client(monkeypatch, client)

    with pytest.raises(FetchError, match="HTTP status 503"):
        fetch_page("https://example.com/product", 3.5, "test-agent")


def test_fetch_page_raises_fetch_error_for_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout_error(url: str) -> httpx.TimeoutException:
        request = httpx.Request("GET", url)
        return httpx.TimeoutException("request timed out", request=request)

    client = FakeClient(error_factory=timeout_error)
    _patch_client(monkeypatch, client)

    with pytest.raises(FetchError, match="timed out"):
        fetch_page("https://example.com/product", 3.5, "test-agent")


def test_fetch_page_raises_fetch_error_for_request_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def connect_error(url: str) -> httpx.ConnectError:
        request = httpx.Request("GET", url)
        return httpx.ConnectError("connection failed", request=request)

    client = FakeClient(error_factory=connect_error)
    _patch_client(monkeypatch, client)

    with pytest.raises(FetchError, match="ConnectError"):
        fetch_page("https://example.com/product", 3.5, "test-agent")
