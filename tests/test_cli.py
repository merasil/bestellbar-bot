from pathlib import Path
from typing import Any, ClassVar

from bestellbar_bot import cli
from bestellbar_bot.monitor import CheckResult
from bestellbar_bot.notifiers.base import NotificationError
from bestellbar_bot.parser import Update


class FakePushoverNotifier:
    instances: ClassVar[list["FakePushoverNotifier"]] = []

    def __init__(
        self,
        *,
        api_token: str,
        user_key: str,
        device: str | None = None,
        timeout: float = 15.0,
        **_kwargs: Any,
    ) -> None:
        self.api_token = api_token
        self.user_key = user_key
        self.device = device
        self.timeout = timeout
        self.sent_updates: list[Update] = []
        FakePushoverNotifier.instances.append(self)

    def send_update(self, update: Update) -> None:
        self.sent_updates.append(update)


def test_cli_check_dry_run_exits_successfully(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    seen_update_handler = object()

    def fake_check_once(_cfg, _notifier, *, update_handler=None):
        nonlocal seen_update_handler
        seen_update_handler = update_handler
        return CheckResult(success=True, total_updates=2, seeded_updates=2)

    monkeypatch.setattr(cli, "check_once", fake_check_once)

    exit_code = cli.main(
        [
            "check",
            "--dry-run",
            "--state-file",
            str(tmp_path / "state.json"),
        ]
    )

    assert exit_code == 0
    assert seen_update_handler is None
    assert "success=True" in capsys.readouterr().out


def test_cli_check_print_updates_outputs_new_update_line(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    seen_print_flag = None

    def fake_check_once(cfg, _notifier, *, update_handler=None):
        nonlocal seen_print_flag
        seen_print_flag = cfg.print_updates
        if update_handler is not None:
            update_handler(
                Update(
                    fingerprint="new",
                    kind="info",
                    title="New stock update",
                    summary="Available now",
                    timestamp_text="2026-07-04",
                    source_text="Bestell.bar",
                    url="https://example.com/update",
                )
            )
        return CheckResult(success=True, total_updates=1, new_updates=1)

    monkeypatch.setattr(cli, "check_once", fake_check_once)

    exit_code = cli.main(
        [
            "check",
            "--dry-run",
            "--print-updates",
            "--state-file",
            str(tmp_path / "state.json"),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert seen_print_flag is True
    assert "2026-07-04 - Bestell.bar" in output
    assert "Summary: Available now" not in output
    assert "success=True" in output


def test_cli_print_updates_env_can_be_disabled_by_arg(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seen_print_flag = None
    seen_update_handler = object()

    def fake_check_once(cfg, _notifier, *, update_handler=None):
        nonlocal seen_print_flag, seen_update_handler
        seen_print_flag = cfg.print_updates
        seen_update_handler = update_handler
        return CheckResult(success=True)

    monkeypatch.setenv("BESTELLBAR_PRINT_UPDATES", "true")
    monkeypatch.setattr(cli, "check_once", fake_check_once)

    exit_code = cli.main(
        [
            "check",
            "--dry-run",
            "--no-print-updates",
            "--state-file",
            str(tmp_path / "state.json"),
        ]
    )

    assert exit_code == 0
    assert seen_print_flag is False
    assert seen_update_handler is None


def test_cli_invalid_args_exit_non_zero(capsys) -> None:
    exit_code = None
    try:
        cli.main(["check", "--dry-run", "--interval", "0"])
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 2
    assert "greater than zero" in capsys.readouterr().err


def test_cli_invalid_print_updates_env_exits_non_zero(monkeypatch, capsys) -> None:
    monkeypatch.setenv("BESTELLBAR_PRINT_UPDATES", "maybe")
    exit_code = None
    try:
        cli.main(["check", "--dry-run"])
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 2
    assert "BESTELLBAR_PRINT_UPDATES" in capsys.readouterr().err


def test_cli_test_pushover_sends_one_synthetic_notification(
    monkeypatch,
    capsys,
) -> None:
    FakePushoverNotifier.instances = []

    def fail_check_once(*_args, **_kwargs):
        raise AssertionError("check_once must not be called")

    def fail_watch(*_args, **_kwargs):
        raise AssertionError("watch must not be called")

    monkeypatch.setenv("PUSHOVER_API_TOKEN", "token")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "user")
    monkeypatch.setattr(cli, "PushoverNotifier", FakePushoverNotifier)
    monkeypatch.setattr(cli, "check_once", fail_check_once)
    monkeypatch.setattr(cli, "watch", fail_watch)

    exit_code = cli.main(["test-pushover"])
    output = capsys.readouterr()

    assert exit_code == 0
    assert output.out.strip() == "Pushover test notification sent."
    assert output.err == ""
    assert len(FakePushoverNotifier.instances) == 1
    assert len(FakePushoverNotifier.instances[0].sent_updates) == 1
    update = FakePushoverNotifier.instances[0].sent_updates[0]
    assert update.fingerprint == "pushover-test"
    assert update.kind == "test"
    assert update.source_text == "bestellbar-bot"
    assert update.url == ""


def test_cli_test_pushover_applies_device_timeout_and_message_options(
    monkeypatch,
) -> None:
    FakePushoverNotifier.instances = []
    monkeypatch.setenv("PUSHOVER_API_TOKEN", "token")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "user")
    monkeypatch.setenv("PUSHOVER_DEVICE", "phone")
    monkeypatch.setattr(cli, "PushoverNotifier", FakePushoverNotifier)

    exit_code = cli.main(
        [
            "test-pushover",
            "--timeout",
            "3",
            "--title",
            "Custom title",
            "--message",
            "Custom message",
        ]
    )

    assert exit_code == 0
    notifier = FakePushoverNotifier.instances[0]
    assert notifier.device == "phone"
    assert notifier.timeout == 3
    assert notifier.sent_updates[0].title == "Custom title"
    assert notifier.sent_updates[0].summary == "Custom message"


def test_cli_test_pushover_rejects_missing_credentials(monkeypatch, capsys) -> None:
    monkeypatch.delenv("PUSHOVER_API_TOKEN", raising=False)
    monkeypatch.delenv("PUSHOVER_USER_KEY", raising=False)

    exit_code = None
    try:
        cli.main(["test-pushover"])
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 2
    assert "PUSHOVER_API_TOKEN" in capsys.readouterr().err


def test_cli_test_pushover_reports_notification_failure_without_secrets(
    monkeypatch,
    capsys,
) -> None:
    class RejectingPushoverNotifier(FakePushoverNotifier):
        def send_update(self, update: Update) -> None:
            super().send_update(update)
            raise NotificationError("rejected secret-token for secret-user")

    monkeypatch.setenv("PUSHOVER_API_TOKEN", "secret-token")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "secret-user")
    monkeypatch.setattr(cli, "PushoverNotifier", RejectingPushoverNotifier)

    exit_code = cli.main(["test-pushover"])
    output = capsys.readouterr()

    assert exit_code == 1
    assert "Pushover test notification failed" in output.err
    assert "[redacted]" in output.err
    assert "secret-token" not in output.err
    assert "secret-user" not in output.err
    assert output.out == ""
