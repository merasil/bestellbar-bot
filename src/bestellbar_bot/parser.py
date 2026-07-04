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
_PRICE_SEPARATOR_RE = re.compile(r"(\d+)\s+,\s+(\d+\s*€)")
_SOURCE_RELATIONS = {"bei", "von"}


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


@dataclass(frozen=True)
class _ParsedEntry:
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
    list_nodes = [
        candidate
        for candidate in container.find_all("ol")
        if isinstance(candidate, Tag)
    ]
    list_entries = [_list_entries(list_node) for list_node in list_nodes]
    parseable_lists = [entries for entries in list_entries if entries]
    if parseable_lists:
        return max(parseable_lists, key=len)
    if list_nodes:
        return []

    return [
        child
        for child in container.find_all(recursive=False)
        if (
            isinstance(child, Tag)
            and child.name in {"article", "li"}
            and _node_text(child)
        )
    ]


def _list_entries(list_node: Tag) -> list[Tag]:
    return [
        child
        for child in list_node.find_all("li", recursive=False)
        if isinstance(child, Tag) and _node_text(child)
    ]


def _parse_entry(node: Tag, base_url: str) -> Update:
    parsed_entry = _parse_structured_entry(node, base_url)
    if parsed_entry is None:
        parsed_entry = _parse_fallback_entry(node, base_url)

    fingerprint = _fingerprint(
        {
            "kind": parsed_entry.kind,
            "title": parsed_entry.title,
            "summary": parsed_entry.summary,
            "timestamp_text": parsed_entry.timestamp_text,
            "source_text": parsed_entry.source_text,
            "url": parsed_entry.url,
        }
    )
    return Update(
        fingerprint=fingerprint,
        kind=parsed_entry.kind,
        title=parsed_entry.title,
        summary=parsed_entry.summary,
        timestamp_text=parsed_entry.timestamp_text,
        source_text=parsed_entry.source_text,
        url=parsed_entry.url,
    )


def _parse_structured_entry(node: Tag, base_url: str) -> _ParsedEntry | None:
    time_node = node.find("time")
    source_node = node.select_one("span.truncate.tw-ej")
    if not isinstance(time_node, Tag) or not isinstance(source_node, Tag):
        return None

    header_node = time_node.parent if isinstance(time_node.parent, Tag) else None
    if header_node is None:
        return None

    header_lines = _text_lines(header_node)
    kind = _first_header_span_text(header_node)
    if not kind:
        return None

    timestamp_text = _clean_timestamp_text(_node_text(time_node))
    if not timestamp_text:
        datetime_value = time_node.get("datetime")
        if isinstance(datetime_value, str):
            timestamp_text = _clean_timestamp_text(datetime_value)

    source_name = _node_text(source_node)
    relation = _find_source_relation(header_lines)
    body_lines = _structured_body_lines(node, header_lines)
    title = body_lines[0] if body_lines else _join_non_empty([kind, source_name])
    detail_text = _format_detail_lines(_structured_detail_lines(kind, body_lines))
    extra_header_text = _format_detail_lines(
        _header_detail_lines(
            header_lines,
            kind=kind,
            relation=relation,
            source_name=source_name,
            timestamp_text=timestamp_text,
        )
    )
    summary = _structured_summary(
        kind=kind,
        detail_text=detail_text,
        extra_header_text=extra_header_text,
    )
    source_text = _join_non_empty(
        [kind, relation, source_name, detail_text, extra_header_text]
    )
    url = _detect_url(node, base_url)

    return _ParsedEntry(
        kind=kind,
        title=title,
        summary=summary,
        timestamp_text=timestamp_text,
        source_text=source_text,
        url=url,
    )


def _parse_fallback_entry(node: Tag, base_url: str) -> _ParsedEntry:
    lines = _text_lines(node)
    if not lines:
        raise ParseError("Online Updates entry has no text.")

    title_node = node.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    if not isinstance(title_node, Tag):
        title_node = node.find(["strong", "b"])

    title = _node_text(title_node) if isinstance(title_node, Tag) else lines[0]
    kind = _detect_kind(node, lines, title)
    timestamp_text = _detect_timestamp(node, lines)
    url = _detect_url(node, base_url)
    source_text = _detect_fallback_source(node)

    summary = _build_summary(lines, title, kind, timestamp_text)
    return _ParsedEntry(
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
        clean_line
        for line in text.splitlines()
        if (clean_line := _normalize_text(line)) and clean_line != "•"
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
        timestamp_text = _clean_timestamp_text(_node_text(time_node))
        if timestamp_text:
            return timestamp_text
        datetime_value = time_node.get("datetime")
        if isinstance(datetime_value, str) and datetime_value.strip():
            return _clean_timestamp_text(datetime_value)

    for line in lines:
        if _TIMESTAMP_RE.search(line):
            return line
    return ""


def _clean_timestamp_text(value: str) -> str:
    return _normalize_text(value).lstrip("• ").strip()


def _first_header_span_text(header_node: Tag) -> str:
    for span in header_node.find_all("span"):
        if isinstance(span, Tag):
            text = _node_text(span)
            if text:
                return text
    return ""


def _find_source_relation(header_lines: list[str]) -> str:
    for line in header_lines:
        if line.casefold() in _SOURCE_RELATIONS:
            return line
    return ""


def _structured_body_lines(node: Tag, header_lines: list[str]) -> list[str]:
    remaining_lines = _remove_lines(_text_lines(node), header_lines)
    return [line for line in remaining_lines if line]


def _remove_lines(lines: list[str], omitted_lines: list[str]) -> list[str]:
    remaining_omissions = omitted_lines.copy()
    kept_lines: list[str] = []
    for line in lines:
        try:
            remaining_omissions.remove(line)
        except ValueError:
            kept_lines.append(line)
    return kept_lines


def _header_detail_lines(
    header_lines: list[str],
    *,
    kind: str,
    relation: str,
    source_name: str,
    timestamp_text: str,
) -> list[str]:
    omitted = {kind, relation, source_name, "Neu", "Uhr", ""}
    detail_lines: list[str] = []
    for line in header_lines:
        if line in omitted:
            continue
        if line.casefold() in _SOURCE_RELATIONS:
            continue
        if timestamp_text and line in timestamp_text:
            continue
        detail_lines.append(line)
    return detail_lines


def _format_detail_lines(lines: list[str]) -> str:
    return _PRICE_SEPARATOR_RE.sub(r"\1,\2", _join_non_empty(lines))


def _structured_detail_lines(kind: str, body_lines: list[str]) -> list[str]:
    if kind.casefold() == "info":
        return body_lines[:1]
    return body_lines


def _structured_summary(
    *,
    kind: str,
    detail_text: str,
    extra_header_text: str,
) -> str:
    if kind.casefold() == "info":
        return ""
    return _join_non_empty([detail_text, extra_header_text])


def _join_non_empty(values: Iterable[str]) -> str:
    return _normalize_text(" ".join(value for value in values if value))


def _detect_url(node: Tag, base_url: str) -> str:
    link_node = node.find("a", href=True)
    if not isinstance(link_node, Tag):
        return ""
    href = str(link_node.get("href", ""))
    return urljoin(base_url, href)


def _detect_fallback_source(node: Tag) -> str:
    source_node = node.select_one("span.truncate.tw-ej")
    if isinstance(source_node, Tag):
        return _node_text(source_node)

    link_node = node.find("a", href=True)
    if isinstance(link_node, Tag):
        return _node_text(link_node)
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
