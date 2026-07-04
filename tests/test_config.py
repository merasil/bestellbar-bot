from pathlib import Path

import pytest

from bestellbar_bot.config import ConfigError, load_config


def test_load_config_reads_required_pushover_env(tmp_path: Path) -> None:
    cfg = load_config(
        {"state_file": str(tmp_path / "state.json")},
        {
            "PUSHOVER_API_TOKEN": "token",
            "PUSHOVER_USER_KEY": "user",
            "PUSHOVER_DEVICE": "iphone",
        },
    )

    assert cfg.pushover_token == "token"
    assert cfg.pushover_user_key == "user"
    assert cfg.pushover_device == "iphone"
    assert cfg.state_file == tmp_path / "state.json"


def test_load_config_rejects_missing_pushover_credentials() -> None:
    with pytest.raises(ConfigError, match="PUSHOVER_API_TOKEN"):
        load_config({}, {})


def test_load_config_allows_missing_pushover_credentials_for_dry_run() -> None:
    cfg = load_config({"dry_run": True}, {})

    assert cfg.dry_run is True
    assert cfg.pushover_token is None
    assert cfg.print_updates is False


@pytest.mark.parametrize("key", ["interval", "timeout"])
def test_load_config_rejects_non_positive_timing(key: str) -> None:
    with pytest.raises(ConfigError, match="greater than zero"):
        load_config({"dry_run": True, key: 0}, {})


def test_load_config_applies_cli_overrides(tmp_path: Path) -> None:
    cfg = load_config(
        {
            "dry_run": True,
            "url": "https://example.com/product",
            "state_file": str(tmp_path / "custom.json"),
            "interval": 12,
            "timeout": 3,
            "print_updates": True,
        },
        {
            "BESTELLBAR_URL": "https://ignored.example",
            "BESTELLBAR_INTERVAL": "60",
            "BESTELLBAR_TIMEOUT": "15",
            "BESTELLBAR_PRINT_UPDATES": "false",
        },
    )

    assert cfg.url == "https://example.com/product"
    assert cfg.state_file == tmp_path / "custom.json"
    assert cfg.interval_seconds == 12
    assert cfg.timeout_seconds == 3
    assert cfg.print_updates is True


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_load_config_reads_enabled_print_updates_env(value: str) -> None:
    cfg = load_config(
        {"dry_run": True},
        {"BESTELLBAR_PRINT_UPDATES": value},
    )

    assert cfg.print_updates is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off"])
def test_load_config_reads_disabled_print_updates_env(value: str) -> None:
    cfg = load_config(
        {"dry_run": True},
        {"BESTELLBAR_PRINT_UPDATES": value},
    )

    assert cfg.print_updates is False


def test_load_config_cli_can_disable_print_updates_env() -> None:
    cfg = load_config(
        {"dry_run": True, "print_updates": False},
        {"BESTELLBAR_PRINT_UPDATES": "true"},
    )

    assert cfg.print_updates is False


def test_load_config_rejects_invalid_print_updates_env() -> None:
    with pytest.raises(ConfigError, match="BESTELLBAR_PRINT_UPDATES"):
        load_config({"dry_run": True}, {"BESTELLBAR_PRINT_UPDATES": "maybe"})
