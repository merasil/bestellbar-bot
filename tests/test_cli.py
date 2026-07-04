from pathlib import Path

from bestellbar_bot import cli
from bestellbar_bot.monitor import CheckResult
from bestellbar_bot.parser import Update


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
