from pathlib import Path

import pytest

from bestellbar_bot.parser import ParseError, parse_updates

FIXTURE = Path(__file__).parent / "fixtures" / "product_page.html"


def test_parse_updates_reads_following_updates_div() -> None:
    updates = parse_updates(FIXTURE.read_text(encoding="utf-8"))

    assert len(updates) == 6
    assert updates[0].kind == "availability"
    assert updates[0].title == "PortaSplit bei Cyberport verfügbar"
    assert "kurzfristig bestellbar" in updates[0].summary
    assert updates[0].timestamp_text == "04.07.26 08:42"
    assert updates[0].source_text == "Cyberport"
    assert updates[0].url == "https://www.bestell.bar/r/cyberport"
    assert updates[1].title == "Amazon DE mit neuer Lieferzeit"
    assert updates[5].timestamp_text == "2026-07-03T18:00:00+02:00"


def test_parse_updates_ignores_filters_and_load_more() -> None:
    updates = parse_updates(FIXTURE.read_text(encoding="utf-8"))

    titles = {update.title for update in updates}
    summaries = "\n".join(update.summary for update in updates)

    assert titles.isdisjoint({"Alle", "Verfügbarkeit", "Info", "Mehr laden"})
    assert "Alle\nVerfügbarkeit\nInfo" not in summaries
    assert "Mehr laden" not in summaries


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


def test_parse_updates_raises_for_empty_updates_list() -> None:
    html = """
    <html><body>
      <h2 id="updatesTitle">Online Updates</h2>
      <div><ol></ol><div><button>Mehr laden</button></div></div>
    </body></html>
    """

    with pytest.raises(ParseError, match="no parseable entries"):
        parse_updates(html)


def test_parse_updates_raises_for_missing_heading() -> None:
    with pytest.raises(ParseError, match="updatesTitle"):
        parse_updates("<html><body><h2>Other</h2></body></html>")


def test_parse_updates_raises_for_missing_following_container() -> None:
    with pytest.raises(ParseError, match="container"):
        parse_updates(
            '<html><body><h2 id="updatesTitle">Online Updates</h2></body></html>'
        )
