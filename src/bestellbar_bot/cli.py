"""Command line interface for bestellbar-bot."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from bestellbar_bot.config import (
    AppConfig,
    ConfigError,
    PushoverConfig,
    load_config,
    load_pushover_config,
)
from bestellbar_bot.monitor import CheckResult, check_once, watch
from bestellbar_bot.notifiers.base import DryRunNotifier, NotificationError, Notifier
from bestellbar_bot.notifiers.pushover import (
    DEFAULT_TEST_MESSAGE,
    DEFAULT_TEST_TITLE,
    PushoverNotifier,
    send_test_notification,
)
from bestellbar_bot.output import get_update_printer


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    if args.command == "test-pushover":
        return _run_test_pushover(args, parser)

    try:
        cfg = load_config(vars(args))
    except ConfigError as exc:
        parser.error(str(exc))

    notifier = _build_notifier(cfg)
    if args.command == "check":
        result = check_once(
            cfg,
            notifier,
            update_handler=get_update_printer(cfg.print_updates),
        )
        _print_check_result(result)
        return 0 if result.success else 1
    if args.command == "watch":
        watch(cfg, notifier)
        return 0

    parser.error("a command is required")
    return 2


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser."""
    parser = argparse.ArgumentParser(prog="bestellbar-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("check", "watch"):
        command_parser = subparsers.add_parser(command)
        _add_common_options(command_parser)

    test_parser = subparsers.add_parser("test-pushover")
    _add_test_pushover_options(test_parser)

    return parser


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", help="Product page URL.")
    parser.add_argument("--state-file", help="Path to the JSON state file.")
    parser.add_argument("--interval", type=float, help="Polling interval in seconds.")
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--notify-existing",
        action="store_true",
        help="Notify for currently visible updates on first run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not send Pushover notifications or write state.",
    )
    parser.add_argument(
        "--print-updates",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Print new updates to stdout.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity.",
    )


def _add_test_pushover_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--title",
        default=DEFAULT_TEST_TITLE,
        help="Notification title for the Pushover test.",
    )
    parser.add_argument(
        "--message",
        default=DEFAULT_TEST_MESSAGE,
        help="Notification message for the Pushover test.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity.",
    )


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _build_notifier(cfg: AppConfig) -> Notifier:
    if cfg.dry_run:
        return DryRunNotifier()

    if cfg.pushover_token is None or cfg.pushover_user_key is None:
        raise ConfigError("Pushover credentials are required.")

    return PushoverNotifier(
        api_token=cfg.pushover_token,
        user_key=cfg.pushover_user_key,
        device=cfg.pushover_device,
        timeout=cfg.timeout_seconds,
    )


def _run_test_pushover(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    try:
        cfg = load_pushover_config(vars(args))
        title = _required_text(args.title, "title")
        message = _required_text(args.message, "message")
    except ConfigError as exc:
        parser.error(str(exc))

    notifier = _build_pushover_notifier(cfg)
    try:
        send_test_notification(notifier, title=title, message=message)
    except NotificationError as exc:
        error = _redact_secrets(str(exc), [cfg.api_token, cfg.user_key])
        print(f"Pushover test notification failed: {error}", file=sys.stderr)
        return 1

    print("Pushover test notification sent.")
    return 0


def _build_pushover_notifier(cfg: PushoverConfig) -> PushoverNotifier:
    return PushoverNotifier(
        api_token=cfg.api_token,
        user_key=cfg.user_key,
        device=cfg.device,
        timeout=cfg.timeout_seconds,
    )


def _required_text(value: object, name: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ConfigError(f"{name} must not be empty.")


def _redact_secrets(message: str, secrets: Sequence[str]) -> str:
    clean_message = message
    for secret in secrets:
        if secret:
            clean_message = clean_message.replace(secret, "[redacted]")
    return clean_message


def _print_check_result(result: CheckResult) -> None:
    output = (
        f"success={result.success} total={result.total_updates} "
        f"new={result.new_updates} notified={result.notified_updates} "
        f"seeded={result.seeded_updates}"
    )
    if result.error:
        output = f"{output} error={result.error}"
    print(output, file=sys.stderr if not result.success else sys.stdout)
