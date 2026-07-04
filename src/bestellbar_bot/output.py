"""Stdout formatting for discovered updates."""

from __future__ import annotations

import sys
from collections.abc import Callable

from bestellbar_bot.parser import Update

UpdatePrinter = Callable[[Update], None]


def format_update(update: Update) -> str:
    """Formats one update as a single stdout line."""
    if update.timestamp_text and update.source_text:
        return f"{update.timestamp_text} - {update.source_text}"
    if update.source_text:
        return update.source_text
    if update.timestamp_text:
        return update.timestamp_text
    return update.title


def print_update(update: Update) -> None:
    """Prints one update to stdout and flushes it."""
    print(format_update(update), file=sys.stdout, flush=True)


def get_update_printer(enabled: bool) -> UpdatePrinter | None:
    """Returns the stdout update printer when output is enabled."""
    if enabled:
        return print_update
    return None
