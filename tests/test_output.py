from bestellbar_bot.output import format_update
from bestellbar_bot.parser import Update


def test_format_update_includes_available_fields() -> None:
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

    assert "Update: New update" in output
    assert "Summary: Line one\nLine two" in output
    assert "Time: 2026-07-04" in output
    assert "Source: Bestell.bar" in output
    assert "URL: https://example.com/update" in output


def test_format_update_omits_empty_optional_fields() -> None:
    output = format_update(
        Update(
            fingerprint="a",
            kind="info",
            title="New update",
            summary="",
            timestamp_text="",
            source_text="",
            url="",
        )
    )

    assert output == "Update: New update"
