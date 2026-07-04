from bestellbar_bot.output import format_update
from bestellbar_bot.parser import Update


def test_format_update_uses_time_and_source_text() -> None:
    output = format_update(
        Update(
            fingerprint="a",
            kind="info",
            title="New update",
            summary="Line one\nLine two",
            timestamp_text="2026-07-04",
            source_text="Bestell.bar",
            url="https://example.com/update",
        )
    )

    assert output == "2026-07-04 - Bestell.bar"
    assert "Line one" not in output
    assert "https://example.com/update" not in output


def test_format_update_uses_source_when_time_is_missing() -> None:
    output = format_update(
        Update(
            fingerprint="a",
            kind="info",
            title="New update",
            summary="Body",
            timestamp_text="",
            source_text="Bestell.bar",
            url="https://example.com/update",
        )
    )

    assert output == "Bestell.bar"


def test_format_update_uses_time_when_source_is_missing() -> None:
    output = format_update(
        Update(
            fingerprint="a",
            kind="info",
            title="New update",
            summary="Body",
            timestamp_text="2026-07-04",
            source_text="",
            url="https://example.com/update",
        )
    )

    assert output == "2026-07-04"


def test_format_update_uses_title_when_time_and_source_are_missing() -> None:
    output = format_update(
        Update(
            fingerprint="a",
            kind="info",
            title="New update",
            summary="Body",
            timestamp_text="",
            source_text="",
            url="",
        )
    )

    assert output == "New update"
