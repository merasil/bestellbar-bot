from pathlib import Path

import pytest

from bestellbar_bot.parser import ParseError, parse_updates

FIXTURE = Path(__file__).parent / "fixtures" / "product_page.html"


def test_parse_updates_reads_following_updates_div() -> None:
    updates = parse_updates(FIXTURE.read_text(encoding="utf-8"))

    assert len(updates) == 2
    assert updates[0].kind == "info"
    assert updates[0].title == "Verfügbarkeit zum Wochenende"
    assert updates[0].source_text == "Amazon DE"
    assert updates[0].url == "https://www.bestell.bar/r/amazon-de"
    assert updates[1].title == "Amazon DE verfügbar"


def test_parse_updates_produces_stable_fingerprints() -> None:
    first = parse_updates(FIXTURE.read_text(encoding="utf-8"))
    second = parse_updates(FIXTURE.read_text(encoding="utf-8"))

    assert [update.fingerprint for update in first] == [
        update.fingerprint for update in second
    ]


def test_parse_updates_uses_heading_text_fallback() -> None:
    html = """
    <html><body>
      <h2>Online Updates</h2>
      <div><article><h3>Fallback title</h3><p>Body</p></article></div>
    </body></html>
    """

    updates = parse_updates(html)

    assert updates[0].title == "Fallback title"


def test_parse_updates_raises_for_missing_heading() -> None:
    with pytest.raises(ParseError, match="updatesTitle"):
        parse_updates("<html><body><h2>Other</h2></body></html>")


def test_parse_updates_raises_for_missing_following_container() -> None:
    with pytest.raises(ParseError, match="container"):
        parse_updates(
            '<html><body><h2 id="updatesTitle">Online Updates</h2></body></html>'
        )
