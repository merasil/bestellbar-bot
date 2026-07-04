"""Persistent state for known update fingerprints."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


class StateError(RuntimeError):
    """Raised when state cannot be loaded or saved safely."""


@dataclass
class BotState:
    """Persisted bot state."""

    known_fingerprints: set[str] = field(default_factory=set)
    last_success_at: str | None = None

    def to_json(self) -> dict[str, object]:
        """Converts the state to a JSON-serializable mapping."""
        return {
            "schema_version": SCHEMA_VERSION,
            "known_fingerprints": sorted(self.known_fingerprints),
            "last_success_at": self.last_success_at,
        }


def load_state(path: Path) -> BotState:
    """Loads state from disk, treating a missing file as empty state."""
    if not path.exists():
        return BotState()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"State file is not valid JSON: {path}") from exc
    except OSError as exc:
        raise StateError(f"Could not read state file: {path}") from exc

    if not isinstance(raw, dict):
        raise StateError("State file must contain a JSON object.")
    return _state_from_json(raw)


def save_state(path: Path, state: BotState) -> None:
    """Atomically saves state to disk."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StateError(f"Could not create state directory: {path.parent}") from exc

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            json.dump(state.to_json(), tmp_file, ensure_ascii=True, indent=2)
            tmp_file.write("\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        raise StateError(f"Could not write state file: {path}") from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()


def _state_from_json(raw: dict[str, Any]) -> BotState:
    schema_version = raw.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise StateError(f"Unsupported state schema version: {schema_version!r}.")

    known = raw.get("known_fingerprints")
    if not isinstance(known, list) or not all(isinstance(item, str) for item in known):
        raise StateError("State field known_fingerprints must be a list of strings.")

    last_success_at = raw.get("last_success_at")
    if last_success_at is not None and not isinstance(last_success_at, str):
        raise StateError("State field last_success_at must be a string or null.")

    return BotState(known_fingerprints=set(known), last_success_at=last_success_at)
