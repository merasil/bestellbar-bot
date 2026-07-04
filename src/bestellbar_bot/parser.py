"""Parser for Bestell.bar Online Updates."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

DEFAULT_BASE_URL = "https://www.bestell.bar/"
_WHITESPACE_RE = re.compile(r"\s+")
_TIMESTAMP_RE = re.compile(
    r"\b(?:heute|gestern|morgen|vor\s+\d+|am\s+\d{1,2}\.|"
    r"\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)


class ParseError(RuntimeError):
    """Raised when the Online Updates section cannot be parsed."""


@dataclass(frozen=True)
class Update:
    """A normalized Online Updates entry."""

    fingerprint: str
    kind: str
    title: str
    summary: str
    timestamp_text: str
    source_text: str
    url: str


def parse_updates(html: str, base_url: str = DEFAULT_BASE_URL) -> list[Update]:
    """Parses Online Updates from a product page."""
    soup = BeautifulSoup(html, "html.parser")
    heading = _find_updates_heading(soup)
    if heading is None:
        raise ParseError(
            'Could not find Online Updates heading with id "updatesTitle".'
        )

    container = heading.find_next("div")
    if not isinstance(container, Tag):
        raise ParseError("Could not find Online Updates container after heading.")

    nodes = _find_entry_nodes(container)
    if not nodes:
        raise ParseError("Online Updates container has no parseable entries.")

    return [_parse_entry(node, base_url) for node in nodes]


def _find_updates_heading(soup: BeautifulSoup) -> Tag | None:
    heading = soup.find(id="updatesTitle")
    if isinstance(heading, Tag):
        return heading

    for candidate in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if not isinstance(candidate, Tag):
            continue
        text = _normalize_text(candidate.get_text(" ", strip=True)).lower()
        if text == "online updates":
            return candidate
    return None


def _find_entry_nodes(container: Tag) -> list[Tag]:
    direct_nodes = [
        child
        for child in container.find_all(recursive=False)
        if isinstance(child, Tag) and _node_text(child)
    ]
    if direct_nodes:
        return direct_nodes
    return [container] if _node_text(container) else []


def _parse_entry(node: Tag, base_url: str) -> Update:
    lines = _text_lines(node)
    if not lines:
        raise ParseError("Online Updates entry has no text.")

    title_node = node.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    if not isinstance(title_node, Tag):
        title_node = node.find(["strong", "b"])

    title = _node_text(title_node) if isinstance(title_node, Tag) else lines[0]
    kind = _detect_kind(node, lines, title)
    timestamp_text = _detect_timestamp(node, lines)
    link_node = node.find("a", href=True)
    url = ""
    source_text = ""
    if isinstance(link_node, Tag):
        href = str(link_node.get("href", ""))
        url = urljoin(base_url, href)
        source_text = _node_text(link_node)

    summary = _build_summary(lines, title, kind, timestamp_text)
    fingerprint = _fingerprint(
        {
            "kind": kind,
            "title": title,
            "summary": summary,
            "timestamp_text": timestamp_text,
            "source_text": source_text,
            "url": url,
        }
    )
    return Update(
        fingerprint=fingerprint,
        kind=kind,
        title=title,
        summary=summary,
        timestamp_text=timestamp_text,
        source_text=source_text,
        url=url,
    )


def _text_lines(node: Tag) -> list[str]:
    text = node.get_text("\n", strip=True)
    return [
        _normalize_text(line) for line in text.splitlines() if _normalize_text(line)
    ]


def _node_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return _normalize_text(node.get_text(" ", strip=True))


def _normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def _detect_kind(node: Tag, lines: list[str], title: str) -> str:
    kind_attr = node.get("data-kind")
    if isinstance(kind_attr, str) and kind_attr.strip():
        return _normalize_text(kind_attr)

    for class_name in _iter_classes(node):
        lowered = class_name.lower()
        if lowered in {"info", "success", "warning", "danger", "availability"}:
            return class_name

    first_line = lines[0]
    if first_line != title and len(first_line) <= 40:
        return first_line
    return ""


def _iter_classes(node: Tag) -> Iterable[str]:
    classes = node.get("class", [])
    if isinstance(classes, str):
        yield classes
        return
    if isinstance(classes, list):
        for class_name in classes:
            if isinstance(class_name, str):
                yield class_name


def _detect_timestamp(node: Tag, lines: list[str]) -> str:
    time_node = node.find("time")
    if isinstance(time_node, Tag):
        datetime_value = time_node.get("datetime")
        if isinstance(datetime_value, str) and datetime_value.strip():
            return _normalize_text(datetime_value)
        return _node_text(time_node)

    for line in lines:
        if _TIMESTAMP_RE.search(line):
            return line
    return ""


def _build_summary(
    lines: list[str],
    title: str,
    kind: str,
    timestamp_text: str,
) -> str:
    omitted = {title, kind, timestamp_text, ""}
    summary_lines = [line for line in lines if line not in omitted]
    return "\n".join(summary_lines)


def _fingerprint(values: dict[str, str]) -> str:
    normalized_values = {
        key: _normalize_text(value).casefold() for key, value in values.items()
    }
    payload = json.dumps(normalized_values, ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
