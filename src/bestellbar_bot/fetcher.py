"""HTTP fetching for Bestell.bar pages."""

from __future__ import annotations

import httpx


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched successfully."""


def fetch_page(url: str, timeout: float, user_agent: str) -> str:
    """Fetches a URL and returns the response body."""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": user_agent,
    }
    try:
        with httpx.Client(
            follow_redirects=True, headers=headers, timeout=timeout
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise FetchError(f"Fetch failed with HTTP status {status}.") from exc
    except httpx.TimeoutException as exc:
        raise FetchError("Fetch timed out.") from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Fetch failed: {exc.__class__.__name__}.") from exc
    return resp.text
