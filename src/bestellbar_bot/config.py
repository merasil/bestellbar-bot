"""Configuration loading and validation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_URL = "https://www.bestell.bar/p/MTpH/midea-portasplit"
DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_USER_AGENT = "bestellbar-bot/0.1 (+https://www.bestell.bar/)"


class ConfigError(ValueError):
    """Raised when configuration values are missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for one CLI invocation."""

    url: str
    state_file: Path
    interval_seconds: float
    timeout_seconds: float
    user_agent: str
    notify_existing: bool
    dry_run: bool
    print_updates: bool
    pushover_token: str | None
    pushover_user_key: str | None
    pushover_device: str | None


@dataclass(frozen=True)
class PushoverConfig:
    """Pushover-only configuration for test notifications."""

    api_token: str
    user_key: str
    device: str | None
    timeout_seconds: float


def default_state_file() -> Path:
    """Returns the default state file path."""
    state_root = os.environ.get("XDG_STATE_HOME")
    if state_root:
        return Path(state_root) / "bestellbar-bot" / "state.json"
    return Path.home() / ".local" / "state" / "bestellbar-bot" / "state.json"


def load_config(
    overrides: Mapping[str, object] | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    """Loads configuration from environment and explicit overrides."""
    values = overrides or {}
    env_values = env or os.environ

    dry_run = _get_bool(values, "dry_run", default=False)
    notify_existing = _get_bool(values, "notify_existing", default=False)
    print_updates = _get_bool_env(
        values,
        "print_updates",
        env_values.get("BESTELLBAR_PRINT_UPDATES"),
        default=False,
    )
    url = _get_str(values, "url") or env_values.get("BESTELLBAR_URL") or DEFAULT_URL
    interval = _get_float(
        values,
        "interval",
        env_values.get("BESTELLBAR_INTERVAL"),
        DEFAULT_INTERVAL_SECONDS,
    )
    timeout = _get_float(
        values,
        "timeout",
        env_values.get("BESTELLBAR_TIMEOUT"),
        DEFAULT_TIMEOUT_SECONDS,
    )
    user_agent = (
        _get_str(values, "user_agent")
        or env_values.get("BESTELLBAR_USER_AGENT")
        or DEFAULT_USER_AGENT
    )
    state_file_value = (
        _get_str(values, "state_file")
        or env_values.get("BESTELLBAR_STATE_FILE")
        or str(default_state_file())
    )
    pushover_token = _clean_optional(env_values.get("PUSHOVER_API_TOKEN"))
    pushover_user_key = _clean_optional(env_values.get("PUSHOVER_USER_KEY"))
    pushover_device = _clean_optional(env_values.get("PUSHOVER_DEVICE"))

    _validate_url(url)
    _validate_positive(interval, "interval")
    _validate_positive(timeout, "timeout")

    if not dry_run and (not pushover_token or not pushover_user_key):
        raise ConfigError(
            "PUSHOVER_API_TOKEN and PUSHOVER_USER_KEY are required unless "
            "--dry-run is used."
        )

    return AppConfig(
        url=url,
        state_file=Path(state_file_value).expanduser(),
        interval_seconds=interval,
        timeout_seconds=timeout,
        user_agent=user_agent,
        notify_existing=notify_existing,
        dry_run=dry_run,
        print_updates=print_updates,
        pushover_token=pushover_token,
        pushover_user_key=pushover_user_key,
        pushover_device=pushover_device,
    )


def load_pushover_config(
    overrides: Mapping[str, object] | None = None,
    env: Mapping[str, str] | None = None,
) -> PushoverConfig:
    """Loads Pushover configuration for a standalone test notification."""
    values = overrides or {}
    env_values = env or os.environ

    timeout = _get_float(
        values,
        "timeout",
        env_values.get("BESTELLBAR_TIMEOUT"),
        DEFAULT_TIMEOUT_SECONDS,
    )
    _validate_positive(timeout, "timeout")

    api_token = _clean_optional(env_values.get("PUSHOVER_API_TOKEN"))
    user_key = _clean_optional(env_values.get("PUSHOVER_USER_KEY"))
    device = _clean_optional(env_values.get("PUSHOVER_DEVICE"))

    if not api_token or not user_key:
        raise ConfigError("PUSHOVER_API_TOKEN and PUSHOVER_USER_KEY are required.")

    return PushoverConfig(
        api_token=api_token,
        user_key=user_key,
        device=device,
        timeout_seconds=timeout,
    )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean_value = value.strip()
    return clean_value or None


def _get_bool(values: Mapping[str, object], key: str, *, default: bool) -> bool:
    value = values.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{key} must be a boolean value.")


def _get_bool_env(
    values: Mapping[str, object],
    key: str,
    env_value: str | None,
    *,
    default: bool,
) -> bool:
    value = values.get(key)
    if value is not None:
        if isinstance(value, bool):
            return value
        raise ConfigError(f"{key} must be a boolean value.")

    if env_value is None or not env_value.strip():
        return default

    normalized = env_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError("BESTELLBAR_PRINT_UPDATES must be a boolean value.")


def _get_str(values: Mapping[str, object], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        clean_value = value.strip()
        return clean_value or None
    raise ConfigError(f"{key} must be a string value.")


def _get_float(
    values: Mapping[str, object],
    key: str,
    env_value: str | None,
    default: float,
) -> float:
    value = values.get(key)
    raw_value: object = value if value is not None else env_value
    if raw_value is None:
        return default
    if isinstance(raw_value, bool) or not isinstance(raw_value, str | int | float):
        raise ConfigError(f"{key} must be a number.")
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be a number.") from exc


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero.")


def _validate_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("url must be an absolute http or https URL.")
