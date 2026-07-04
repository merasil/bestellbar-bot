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
        },
        {
            "BESTELLBAR_URL": "https://ignored.example",
            "BESTELLBAR_INTERVAL": "60",
            "BESTELLBAR_TIMEOUT": "15",
        },
    )

    assert cfg.url == "https://example.com/product"
    assert cfg.state_file == tmp_path / "custom.json"
    assert cfg.interval_seconds == 12
    assert cfg.timeout_seconds == 3
