from pathlib import Path

from bestellbar_bot import cli
from bestellbar_bot.monitor import CheckResult


def test_cli_check_dry_run_exits_successfully(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    def fake_check_once(_cfg, _notifier):
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
    assert "success=True" in capsys.readouterr().out


def test_cli_invalid_args_exit_non_zero(capsys) -> None:
    exit_code = None
    try:
        cli.main(["check", "--dry-run", "--interval", "0"])
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 2
    assert "greater than zero" in capsys.readouterr().err
