"""Monitoring workflow for Bestell.bar updates."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from bestellbar_bot.config import AppConfig
from bestellbar_bot.fetcher import FetchError, fetch_page
from bestellbar_bot.notifiers.base import NotificationError, Notifier
from bestellbar_bot.output import get_update_printer
from bestellbar_bot.parser import ParseError, Update, parse_updates
from bestellbar_bot.state import StateError, load_state, save_state

FetchFunc = Callable[[str, float, str], str]
ParseFunc = Callable[[str, str], list[Update]]
FoundUpdateHandler = Callable[[Update], None]


@dataclass(frozen=True)
class CheckResult:
    """Result of one monitoring check."""

    success: bool
    total_updates: int = 0
    new_updates: int = 0
    notified_updates: int = 0
    seeded_updates: int = 0
    error: str | None = None


def check_once(
    cfg: AppConfig,
    notifier: Notifier,
    *,
    fetch_func: FetchFunc = fetch_page,
    parse_func: ParseFunc = parse_updates,
    update_handler: FoundUpdateHandler | None = None,
) -> CheckResult:
    """Fetches, parses, notifies, persists state, and emits found updates."""
    logger = logging.getLogger(__name__)
    try:
        html = fetch_func(cfg.url, cfg.timeout_seconds, cfg.user_agent)
        updates = parse_func(html, cfg.url)
        first_run = not cfg.state_file.exists()
        state = load_state(cfg.state_file)
    except (FetchError, ParseError, StateError) as exc:
        logger.error("Check failed: %s", exc)
        return CheckResult(success=False, error=str(exc))

    if first_run and not cfg.notify_existing:
        state.known_fingerprints.update(update.fingerprint for update in updates)
        state.last_success_at = _utc_now()
        if not cfg.dry_run:
            try:
                save_state(cfg.state_file, state)
            except StateError as exc:
                logger.error("Could not save seeded state: %s", exc)
                return CheckResult(success=False, error=str(exc))
        _handle_found_updates(updates, update_handler)
        return CheckResult(
            success=True,
            total_updates=len(updates),
            seeded_updates=len(updates),
        )

    unseen_updates = [
        update
        for update in updates
        if update.fingerprint not in state.known_fingerprints
    ]
    notified = 0
    for update in reversed(unseen_updates):
        try:
            notifier.send_update(update)
        except NotificationError as exc:
            logger.error("Notification failed: %s", exc)
            return CheckResult(
                success=False,
                total_updates=len(updates),
                new_updates=len(unseen_updates),
                notified_updates=notified,
                error=str(exc),
            )

        notified += 1
        state.known_fingerprints.add(update.fingerprint)
        if not cfg.dry_run:
            try:
                save_state(cfg.state_file, state)
            except StateError as exc:
                logger.error("Could not save notification state: %s", exc)
                return CheckResult(
                    success=False,
                    total_updates=len(updates),
                    new_updates=len(unseen_updates),
                    notified_updates=notified,
                    error=str(exc),
                )

    state.last_success_at = _utc_now()
    if not cfg.dry_run:
        try:
            save_state(cfg.state_file, state)
        except StateError as exc:
            logger.error("Could not save state: %s", exc)
            return CheckResult(success=False, error=str(exc))

    _handle_found_updates(updates, update_handler)
    return CheckResult(
        success=True,
        total_updates=len(updates),
        new_updates=len(unseen_updates),
        notified_updates=notified,
    )


def watch(cfg: AppConfig, notifier: Notifier) -> None:
    """Runs checks continuously until interrupted."""
    logger = logging.getLogger(__name__)
    update_handler = get_update_printer(cfg.print_updates)
    try:
        while True:
            result = check_once(cfg, notifier, update_handler=update_handler)
            if result.success:
                logger.info(
                    "Check complete: total=%s new=%s notified=%s seeded=%s",
                    result.total_updates,
                    result.new_updates,
                    result.notified_updates,
                    result.seeded_updates,
                )
            time.sleep(cfg.interval_seconds)
    except KeyboardInterrupt:
        logger.info("Stopped by user.")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _handle_found_updates(
    updates: list[Update],
    update_handler: FoundUpdateHandler | None,
) -> None:
    if update_handler is None:
        return
    for update in updates:
        update_handler(update)
