"""Stdout formatting for discovered updates."""

from __future__ import annotations

import sys
from collections.abc import Callable

from bestellbar_bot.parser import Update

UpdatePrinter = Callable[[Update], None]


def format_update(update: Update) -> str:
    """Formats one update for a concise log stream entry."""
    lines = [f"Update: {update.title}"]
    if update.summary:
        lines.append(f"Summary: {update.summary}")
    if update.timestamp_text:
        lines.append(f"Time: {update.timestamp_text}")
    if update.source_text:
        lines.append(f"Source: {update.source_text}")
    if update.url:
        lines.append(f"URL: {update.url}")
    return "\n".join(lines)


def print_update(update: Update) -> None:
    """Prints one update to stdout and flushes it."""
    print(format_update(update), file=sys.stdout, flush=True)


def get_update_printer(enabled: bool) -> UpdatePrinter | None:
    """Returns the stdout update printer when output is enabled."""
    if enabled:
        return print_update
    return None
